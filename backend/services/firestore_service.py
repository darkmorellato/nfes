"""
Serviço de Sincronização em Tempo Real com o Google Cloud Firestore.

Plano Firebase: SPARK (gratuito).
Este serviço usa SOMENTE a REST API pública do Firestore com a
chave de API do projeto — sem Cloud Functions, sem triggers e
sem credenciais de service account. Tudo é executado a partir do
backend local (ou do navegador do usuário).

ATENÇÃO: a ``FIREBASE_API_KEY`` precisa estar configurada em
``.env`` (ou nas variáveis de ambiente). Se não estiver, o serviço
retorna um erro amigável e segue em frente.
"""
import json
import logging
import os
import threading
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.config import settings
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

# Cache de validação: uma vez que detectarmos que a chave não está
# configurada, paramos de poluir os logs com avisos repetidos.
_API_KEY_MISSING_WARNED = False
_PROJECT_ID_MISSING_WARNED = False


def _get_api_key() -> str:
    """Lê a API key do Firebase do ambiente. Não há fallback hardcoded."""
    global _API_KEY_MISSING_WARNED
    key = (getattr(settings, "FIREBASE_API_KEY", "") or "").strip()
    if not key and not _API_KEY_MISSING_WARNED:
        logger.warning(
            "[Firestore] FIREBASE_API_KEY não configurada em .env — "
            "sincronização com a nuvem desativada. Defina a chave no .env "
            "para habilitar."
        )
        _API_KEY_MISSING_WARNED = True
    return key


def _get_project_id() -> str:
    """Lê o project_id do Firebase do ambiente. Não há fallback hardcoded."""
    global _PROJECT_ID_MISSING_WARNED
    pid = (getattr(settings, "FIREBASE_PROJECT_ID", "") or "").strip()
    if not pid and not _PROJECT_ID_MISSING_WARNED:
        logger.warning(
            "[Firestore] FIREBASE_PROJECT_ID não configurado em .env — "
            "sincronização com a nuvem desativada."
        )
        _PROJECT_ID_MISSING_WARNED = True
    return pid

def _py_to_firestore_value(val: Any) -> Dict[str, Any]:
    if val is None:
        return {"nullValue": None}
    elif isinstance(val, bool):
        return {"booleanValue": val}
    elif isinstance(val, int):
        return {"integerValue": str(val)}
    elif isinstance(val, float):
        return {"doubleValue": val}
    elif isinstance(val, str):
        return {"stringValue": val}
    elif isinstance(val, list):
        return {"arrayValue": {"values": [_py_to_firestore_value(x) for x in val]}}
    elif isinstance(val, dict):
        return {"mapValue": {"fields": {k: _py_to_firestore_value(v) for k, v in val.items()}}}
    else:
        return {"stringValue": str(val)}

def _py_dict_to_firestore_fields(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _py_to_firestore_value(v) for k, v in d.items() if v is not None}

def format_nfe_payload(doc: Dict[str, Any]) -> Dict[str, Any]:
    chave = "".join(c for c in str(doc.get("chave", "")) if c.isdigit())
    data_emi = str(doc.get("data_emissao") or "")
    competencia = data_emi[:7] if len(data_emi) >= 7 else ""

    empresa_cnpj = "".join(c for c in str(doc.get("empresa_cnpj") or "") if c.isdigit())
    emit_cnpj = "".join(c for c in str(doc.get("emitente_cnpj") or "") if c.isdigit())
    dest_cnpj = "".join(c for c in str(doc.get("destinatario_cnpj") or "") if c.isdigit())

    def _to_float(v):
        if not v:
            return 0.0
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    return {
        "chave": chave,
        "empresa_cnpj": empresa_cnpj or dest_cnpj or emit_cnpj,
        "competencia": competencia,
        "numero": str(doc.get("numero") or ""),
        "serie": str(doc.get("serie") or ""),
        "modelo": str(doc.get("modelo") or ("65" if chave[20:22] == "65" else "55")),
        "tipo_doc": int(doc.get("tipo_doc") or 0),
        "emitente_cnpj": emit_cnpj,
        "emitente_nome": str(doc.get("emitente_nome") or ""),
        "emitente_uf": str(doc.get("emitente_uf") or ""),
        "destinatario_cnpj": dest_cnpj,
        "destinatario_nome": str(doc.get("destinatario_nome") or ""),
        "destinatario_uf": str(doc.get("destinatario_uf") or ""),
        "data_emissao": data_emi,
        "data_autorizacao": str(doc.get("data_autorizacao") or ""),
        "valor_total": _to_float(doc.get("valor_total")),
        "valor_icms": _to_float(doc.get("valor_icms")),
        "valor_pis": _to_float(doc.get("valor_pis")),
        "valor_cofins": _to_float(doc.get("valor_cofins")),
        "valor_ipi": _to_float(doc.get("valor_ipi")),
        "situacao": str(doc.get("situacao") or "Autorizada"),
        "nsu": str(doc.get("nsu") or "0"),
        "has_xml": bool(doc.get("has_xml", False)),
        "updated_at": datetime.now().isoformat(),
    }

def sync_single_nfe(doc: Dict[str, Any]) -> bool:
    chave = "".join(c for c in str(doc.get("chave", "")) if c.isdigit())
    if len(chave) != 44:
        return False

    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return False

    payload = format_nfe_payload(doc)
    fields = _py_dict_to_firestore_fields(payload)

    doc_path = f"projects/{project_id}/databases/(default)/documents/nfe_docs/{chave}"
    url = f"https://firestore.googleapis.com/v1/{doc_path}?key={api_key}"

    body = json.dumps({"fields": fields}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH", headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.warning(f"[Firestore] Erro ao sincronizar NF-e {chave}: {e}")
        return False

def sync_single_nfe_async(doc: Dict[str, Any]) -> None:
    threading.Thread(target=sync_single_nfe, args=(doc,), daemon=True).start()


def sync_nfe_items_to_firestore(chave: str, itens: List[Dict[str, Any]]) -> bool:
    """Sincroniza itens de uma NF-e para a subcoleção nfe_docs/{chave}/itens no Firestore."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id or not itens:
        return False

    commit_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:commit?key={api_key}"
    writes = []

    for idx, item in enumerate(itens):
        item_id = f"item_{idx + 1:03d}"
        fields = _py_dict_to_firestore_fields({
            "n_item": int(item.get("n_item") or idx + 1),
            "codigo": str(item.get("codigo") or ""),
            "ean": str(item.get("ean") or ""),
            "descricao": str(item.get("descricao") or ""),
            "ncm": str(item.get("ncm") or ""),
            "cfop": str(item.get("cfop") or ""),
            "unidade": str(item.get("unidade") or ""),
            "quantidade": float(item.get("quantidade") or 0),
            "valor_unitario": float(item.get("valor_unitario") or 0),
            "valor_total": float(item.get("valor_total") or 0),
            "cst": str(item.get("cst") or ""),
            "v_icms": float(item.get("v_icms") or 0),
        })
        doc_name = f"projects/{project_id}/databases/(default)/documents/nfe_docs/{chave}/itens/{item_id}"
        writes.append({"update": {"name": doc_name, "fields": fields}})

    if not writes:
        return False

    body_bytes = json.dumps({"writes": writes}).encode("utf-8")
    req = urllib.request.Request(commit_url, data=body_bytes, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.warning(f"[Firestore] Erro ao sincronizar itens da NF-e {chave}: {e}")
        return False


def sync_nfe_items_to_firestore_async(chave: str, itens: List[Dict[str, Any]]) -> None:
    threading.Thread(target=sync_nfe_items_to_firestore, args=(chave, itens), daemon=True).start()

def sync_event_to_firestore(event: Dict[str, Any]) -> bool:
    chave = "".join(c for c in str(event.get("chave", "")) if c.isdigit())
    if not chave:
        return False

    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return False

    tipo = str(event.get("tipo_evento") or "")
    n_seq = str(event.get("n_seq") or "1")
    event_doc_id = f"{chave}_{tipo}_{n_seq}"

    payload = {
        "chave": chave,
        "tipo_evento": tipo,
        "desc_evento": str(event.get("desc_evento") or ""),
        "n_seq": int(n_seq),
        "dh_evento": str(event.get("dh_evento") or datetime.now().isoformat()),
        "protocolo": str(event.get("protocolo") or ""),
        "c_stat": str(event.get("c_stat") or ""),
        "x_motivo": str(event.get("x_motivo") or ""),
        "created_at": datetime.now().isoformat(),
    }
    fields = _py_dict_to_firestore_fields(payload)

    doc_path = f"projects/{project_id}/databases/(default)/documents/nfe_events/{event_doc_id}"
    url = f"https://firestore.googleapis.com/v1/{doc_path}?key={api_key}"
    body = json.dumps({"fields": fields}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH", headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.warning(f"[Firestore] Erro ao sincronizar evento {event_doc_id}: {e}")
        return False

def sync_event_to_firestore_async(event: Dict[str, Any]) -> None:
    threading.Thread(target=sync_event_to_firestore, args=(event,), daemon=True).start()

def sync_all_database_to_firestore(batch_size: int = 30) -> Dict[str, Any]:
    import time as _time

    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return {"success": False, "error": "Credenciais do Firebase não configuradas."}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emitente_cnpj, emitente_nome, emitente_uf, destinatario_cnpj, destinatario_nome, destinatario_uf, data_emissao, data_autorizacao, valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi, situacao, nsu, has_xml FROM nfe_docs ORDER BY data_emissao DESC")
        all_docs = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT chave, n_item, codigo, ean, descricao, ncm, cfop, unidade, quantidade, valor_unitario, valor_total, cst, v_icms FROM nfe_items ORDER BY chave, n_item")
        all_items = [dict(r) for r in cursor.fetchall()]

    items_by_chave: Dict[str, list] = {}
    for item in all_items:
        ch = item.pop("chave")
        items_by_chave.setdefault(ch, []).append(item)

    total = len(all_docs)
    if total == 0:
        return {"success": True, "total": 0, "synced": 0, "message": "Nenhuma nota fiscal encontrada no banco local."}

    commit_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:commit?key={api_key}"
    synced_count = 0
    errors_count = 0
    items_synced = 0

    for i in range(0, total, batch_size):
        batch_slice = all_docs[i:i + batch_size]
        writes = []

        for doc in batch_slice:
            chave = doc.get("chave")
            if not chave or len(chave) != 44:
                continue

            payload = format_nfe_payload(doc)
            fields = _py_dict_to_firestore_fields(payload)

            doc_name = f"projects/{project_id}/databases/(default)/documents/nfe_docs/{chave}"
            writes.append({"update": {"name": doc_name, "fields": fields}})

            emp_cnpj = payload.get("empresa_cnpj")
            if emp_cnpj:
                emp_doc_name = f"projects/{project_id}/databases/(default)/documents/empresas/{emp_cnpj}/nfe_docs/{chave}"
                writes.append({"update": {"name": emp_doc_name, "fields": fields}})

            itens = items_by_chave.get(chave, [])
            for idx, item in enumerate(itens):
                item_id = f"item_{idx + 1:03d}"
                item_fields = _py_dict_to_firestore_fields({
                    "n_item": int(item.get("n_item") or idx + 1),
                    "codigo": str(item.get("codigo") or ""),
                    "ean": str(item.get("ean") or ""),
                    "descricao": str(item.get("descricao") or ""),
                    "ncm": str(item.get("ncm") or ""),
                    "cfop": str(item.get("cfop") or ""),
                    "unidade": str(item.get("unidade") or ""),
                    "quantidade": float(item.get("quantidade") or 0),
                    "valor_unitario": float(item.get("valor_unitario") or 0),
                    "valor_total": float(item.get("valor_total") or 0),
                    "cst": str(item.get("cst") or ""),
                    "v_icms": float(item.get("v_icms") or 0),
                })
                item_doc_name = f"projects/{project_id}/databases/(default)/documents/nfe_docs/{chave}/itens/{item_id}"
                writes.append({"update": {"name": item_doc_name, "fields": item_fields}})
                items_synced += 1

        if not writes:
            continue

        body_bytes = json.dumps({"writes": writes}).encode("utf-8")
        req = urllib.request.Request(
            commit_url,
            data=body_bytes,
            method="POST",
            headers={"Content-Type": "application/json"}
        )

        max_retries = 5
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    if resp.status in (200, 201):
                        synced_count += len(batch_slice)
                        logger.info(f"[Firestore Batch] Progresso: {synced_count}/{total} notas.")
                        break
                    else:
                        errors_count += len(batch_slice)
                        break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_retries - 1:
                    wait = (2 ** attempt) * 2
                    logger.warning(f"[Firestore Batch] Rate limit (429). Aguardando {wait}s...")
                    _time.sleep(wait)
                    continue
                else:
                    logger.error(f"[Firestore Batch] Erro {e.code} no lote {i}: {e}")
                    errors_count += len(batch_slice)
                    break
            except Exception as batch_err:
                logger.error(f"[Firestore Batch] Erro no lote {i}: {batch_err}")
                errors_count += len(batch_slice)
                break

        _time.sleep(0.5)

    return {
        "success": True,
        "total": total,
        "synced": synced_count,
        "items_synced": items_synced,
        "errors": errors_count,
        "project_id": project_id,
        "timestamp": datetime.now().isoformat(),
        "message": f"Sincronização concluída: {synced_count} notas + {items_synced} itens enviados ao Firestore!",
    }


# ====================================================================
# PULL: FIRESTORE → SQLITE (leitura da nuvem para o banco local)
# ====================================================================
# Idempotente: chama save_nfe_doc() que faz ON CONFLICT(chave) DO UPDATE.
# Pode rodar quantas vezes quiser sem duplicar registros.

def _firestore_value_to_py(val: Any) -> Any:
    """Decodifica um campo Firestore (formato {stringValue, integerValue, ...}) para Python."""
    if not isinstance(val, dict):
        return None
    if "stringValue" in val:
        return val["stringValue"]
    if "integerValue" in val:
        try:
            return int(val["integerValue"])
        except (ValueError, TypeError):
            return 0
    if "doubleValue" in val:
        try:
            return float(val["doubleValue"])
        except (ValueError, TypeError):
            return 0.0
    if "booleanValue" in val:
        return bool(val["booleanValue"])
    if "nullValue" in val:
        return None
    if "timestampValue" in val:
        return val["timestampValue"]
    if "mapValue" in val:
        return _firestore_fields_to_dict(val["mapValue"].get("fields", {}))
    if "arrayValue" in val:
        return [_firestore_value_to_py(x) for x in val["arrayValue"].get("values", [])]
    return None


def _firestore_fields_to_dict(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Decodifica um dict de campos Firestore para dict Python plano."""
    return {k: _firestore_value_to_py(v) for k, v in fields.items()}


def list_all_nfe_docs_from_firestore(page_size: int = 300) -> List[Dict[str, Any]]:
    """Lista TODAS as NF-es da coleção nfe_docs no Firestore (paginado via nextPageToken)."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        logger.warning("[Firestore] Credenciais não configuradas — pull cancelado.")
        return []

    base_url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/nfe_docs"
    )
    all_docs: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    pages_fetched = 0

    while True:
        params = {"pageSize": str(page_size), "key": api_key}
        if page_token:
            params["pageToken"] = page_token
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"[Firestore] Erro ao listar nfe_docs (página {pages_fetched}): {e}")
            break

        for doc in data.get("documents", []):
            fields = doc.get("fields", {})
            py = _firestore_fields_to_dict(fields)
            all_docs.append(py)

        pages_fetched += 1
        page_token = data.get("nextPageToken")
        logger.info(
            f"[Firestore] Listagem de nfe_docs: página {pages_fetched} ok "
            f"(acumulado: {len(all_docs)} docs)."
        )
        if not page_token:
            break

    return all_docs


def pull_from_firestore() -> Dict[str, Any]:
    """One-shot: puxa TODAS as NF-es do Firestore e faz upsert no SQLite local.

    Idempotente — pode rodar várias vezes sem duplicar (chave é PRIMARY KEY).
    Também puxa itens da subcoleção nfe_docs/{chave}/itens.
    """
    from backend.database.nfe_docs import save_nfe_doc

    docs = list_all_nfe_docs_from_firestore(page_size=300)
    total = len(docs)
    sucessos = 0
    falhas = 0
    ignorados = 0
    itens_total = 0

    for d in docs:
        chave = "".join(c for c in str(d.get("chave") or "") if c.isdigit())
        if len(chave) != 44:
            ignorados += 1
            continue

        itens = _list_itens_subcollection(chave)
        if itens:
            d["produtos"] = itens
            itens_total += len(itens)

        if save_nfe_doc(d):
            sucessos += 1
        else:
            falhas += 1

    logger.info(
        f"[Firestore] Pull concluído: {sucessos}/{total} NF-es importadas, "
        f"{itens_total} itens, {falhas} falhas, {ignorados} ignoradas."
    )
    return {
        "success": True,
        "total_cloud": total,
        "imported": sucessos,
        "items_imported": itens_total,
        "failed": falhas,
        "skipped": ignorados,
        "timestamp": datetime.now().isoformat(),
        "message": (
            f"Pull do Cloud Firestore concluído: {sucessos} de {total} "
            f"NF-es + {itens_total} itens importados para o banco local."
        ),
    }


def _list_itens_subcollection(chave: str) -> List[Dict[str, Any]]:
    """Lista itens da subcoleção nfe_docs/{chave}/itens no Firestore."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return []

    url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/nfe_docs/{chave}/itens?key={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    itens = []
    for d in data.get("documents", []):
        py = _firestore_fields_to_dict(d.get("fields", {}))
        itens.append(py)
    return itens


# ====================================================================
# CONSOLIDAÇÃO DE CADASTROS (clientes + produtos) A PARTIR DAS NF-es
# ====================================================================
# Varre o SQLite e consolida emitentes+destinatários em 'clientes' e itens
# em 'produtos'. Idempotente: PATCH no Firestore (atualiza se existir).

def _normalizar_doc_id(cnpj_ou_nome: str) -> str:
    """Doc ID: só dígitos do CNPJ/CPF (11 ou 14 dígitos), ou hash do nome se vazio."""
    digits = "".join(c for c in str(cnpj_ou_nome or "") if c.isdigit())
    if len(digits) in (11, 14):
        return digits
    # Fallback: hash determinístico do nome (caso raro: cliente sem CNPJ)
    import hashlib
    return "_nome_" + hashlib.sha1(
        str(cnpj_ou_nome or "").strip().upper().encode()
    ).hexdigest()[:16]


def _norm_nome(s: str) -> str:
    """Nome canônico: UPPER + trim + colapsa espaços."""
    return " ".join((s or "").upper().split())


def _upsert_firestore_doc(collection: str, doc_id: str, payload: Dict[str, Any]) -> bool:
    """PATCH em /v1/.../documents/{collection}/{doc_id} — idempotente."""
    import unicodedata

    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return False
    # Sanitiza o doc_id: Firestore doc IDs vão no PATH da URL, então precisam
    # ser ASCII puro. Decompomos acentos (NFD) e removemos combining chars,
    # depois substituímos qualquer não-alfanumérico por '_'.
    normalized = unicodedata.normalize("NFD", str(doc_id))
    ascii_only = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in ascii_only)
    doc_path = (
        f"projects/{project_id}/databases/(default)/documents/{collection}/{safe_id}"
    )
    url = f"https://firestore.googleapis.com/v1/{doc_path}?key={api_key}"
    body = json.dumps({"fields": _py_dict_to_firestore_fields(payload)}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="PATCH", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        logger.warning(f"[Firestore] Erro upsert {collection}/{safe_id}: {e}")
        return False


def consolidar_clientes_do_sqlite() -> Dict[str, Any]:
    """Varre TODAS as NF-es do SQLite e consolida emitentes + destinatários
    na coleção 'clientes' do Firestore. Idempotente."""
    import sqlite3

    from backend.config import settings as _settings

    db_path = os.path.join(_settings.DATA_DIR, "nfe_database.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT chave, tipo_doc, emitente_cnpj, emitente_nome, emitente_uf,
               destinatario_cnpj, destinatario_nome, destinatario_uf,
               data_emissao, valor_total
        FROM nfe_docs
        WHERE (emitente_cnpj != '' OR destinatario_cnpj != '')
    """).fetchall()
    conn.close()

    clientes: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        for papel, cnpj, nome, uf in [
            ("emitente", r["emitente_cnpj"], r["emitente_nome"], r["emitente_uf"]),
            ("destinatario", r["destinatario_cnpj"], r["destinatario_nome"], r["destinatario_uf"]),
        ]:
            if not cnpj and not nome:
                continue
            doc_id = _normalizar_doc_id(cnpj or nome)
            entry = clientes.setdefault(doc_id, {
                "doc_id": doc_id,
                "cnpj_cpf": "".join(c for c in str(cnpj or "") if c.isdigit()),
                "nomes": {},
                "ufs": {},
                "total_nfes": 0,
                "total_como_emitente": 0,
                "total_como_destinatario": 0,
                "valor_total_operado": 0.0,
                "primeira_nfe": None,
                "ultima_nfe": None,
            })
            nome_norm = _norm_nome(nome) if nome else "(SEM NOME)"
            entry["nomes"][nome_norm] = entry["nomes"].get(nome_norm, 0) + 1
            if uf:
                entry["ufs"][uf] = entry["ufs"].get(uf, 0) + 1
            entry["total_nfes"] += 1
            if papel == "emitente":
                entry["total_como_emitente"] += 1
            else:
                entry["total_como_destinatario"] += 1
            entry["valor_total_operado"] += float(r["valor_total"] or 0)
            data_emi = (r["data_emissao"] or "")[:10]
            if data_emi:
                if not entry["primeira_nfe"] or data_emi < entry["primeira_nfe"]:
                    entry["primeira_nfe"] = data_emi
                if not entry["ultima_nfe"] or data_emi > entry["ultima_nfe"]:
                    entry["ultima_nfe"] = data_emi

    sucessos = 0
    falhas = 0
    for doc_id, e in clientes.items():
        nome_canon = (
            max(e["nomes"].items(), key=lambda kv: kv[1])[0]
            if e["nomes"] else "(SEM NOME)"
        )
        uf_principal = (
            max(e["ufs"].items(), key=lambda kv: kv[1])[0]
            if e["ufs"] else ""
        )
        if e["total_como_emitente"] > 0 and e["total_como_destinatario"] > 0:
            papel = "ambos"
        elif e["total_como_emitente"] > 0:
            papel = "fornecedor"
        else:
            papel = "cliente"

        payload = {
            "cnpj_cpf": e["cnpj_cpf"],
            "nome": nome_canon,
            "uf": uf_principal,
            "papel": papel,
            "total_nfes": e["total_nfes"],
            "total_como_emitente": e["total_como_emitente"],
            "total_como_destinatario": e["total_como_destinatario"],
            "valor_total_operado": round(e["valor_total_operado"], 2),
            "primeira_nfe": e["primeira_nfe"] or "",
            "ultima_nfe": e["ultima_nfe"] or "",
            "variantes_nome": sorted(e["nomes"].keys()),
            "updated_at": datetime.now().isoformat(),
        }
        if _upsert_firestore_doc("clientes", doc_id, payload):
            sucessos += 1
        else:
            falhas += 1

    logger.info(
        f"[Firestore] Consolidação de clientes: {sucessos}/{len(clientes)} importados, {falhas} falhas."
    )
    return {
        "success": True,
        "total_unicos": len(clientes),
        "imported": sucessos,
        "failed": falhas,
        "timestamp": datetime.now().isoformat(),
        "message": (
            f"Consolidação de clientes concluída: {sucessos} de {len(clientes)} "
            f"clientes/fornecedores enviados para a coleção 'clientes' do Firestore."
        ),
    }


def consolidar_produtos_do_sqlite() -> Dict[str, Any]:
    """Varre a tabela nfe_items e consolida produtos por código (ou EAN,
    ou hash da descrição) na coleção 'produtos' do Firestore. Idempotente."""
    import hashlib
    import sqlite3

    from backend.config import settings as _settings

    db_path = os.path.join(_settings.DATA_DIR, "nfe_database.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT i.codigo, i.ean, i.descricao, i.ncm, i.cfop, i.unidade,
               i.quantidade, i.valor_unitario, i.valor_total, d.data_emissao
        FROM nfe_items i
        JOIN nfe_docs d ON d.chave = i.chave
    """).fetchall()
    conn.close()

    produtos: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        codigo = (r["codigo"] or "").strip()
        ean = (r["ean"] or "").strip()
        if codigo:
            doc_id = "cod_" + codigo
        elif ean:
            doc_id = "ean_" + ean
        else:
            doc_id = "desc_" + hashlib.sha1(
                (r["descricao"] or "").strip().upper().encode()
            ).hexdigest()[:16]

        entry = produtos.setdefault(doc_id, {
            "codigo": codigo,
            "ean": ean,
            "ncm": (r["ncm"] or "").strip(),
            "descricoes": {},
            "cfops": {},
            "unidades": {},
            "total_nfes": 0,
            "quantidade_total": 0.0,
            "valor_total": 0.0,
            "preco_min": None,
            "preco_max": None,
            "primeira_venda": None,
            "ultima_venda": None,
        })
        desc = (r["descricao"] or "").strip()
        if desc:
            entry["descricoes"][desc] = entry["descricoes"].get(desc, 0) + 1
        cfop = (r["cfop"] or "").strip()
        if cfop:
            entry["cfops"][cfop] = entry["cfops"].get(cfop, 0) + 1
        un = (r["unidade"] or "").strip()
        if un:
            entry["unidades"][un] = entry["unidades"].get(un, 0) + 1

        entry["total_nfes"] += 1
        qty = float(r["quantidade"] or 0)
        val = float(r["valor_total"] or 0)
        entry["quantidade_total"] += qty
        entry["valor_total"] += val
        vu = float(r["valor_unitario"] or 0)
        if vu > 0:
            if entry["preco_min"] is None or vu < entry["preco_min"]:
                entry["preco_min"] = vu
            if entry["preco_max"] is None or vu > entry["preco_max"]:
                entry["preco_max"] = vu
        data_v = (r["data_emissao"] or "")[:10]
        if data_v:
            if not entry["primeira_venda"] or data_v < entry["primeira_venda"]:
                entry["primeira_venda"] = data_v
            if not entry["ultima_venda"] or data_v > entry["ultima_venda"]:
                entry["ultima_venda"] = data_v

    sucessos = 0
    falhas = 0
    for doc_id, e in produtos.items():
        desc_canon = (
            max(e["descricoes"].items(), key=lambda kv: kv[1])[0]
            if e["descricoes"] else ""
        )
        cfop_mf = (
            max(e["cfops"].items(), key=lambda kv: kv[1])[0]
            if e["cfops"] else ""
        )
        un_mf = (
            max(e["unidades"].items(), key=lambda kv: kv[1])[0]
            if e["unidades"] else ""
        )
        preco_medio = (
            (e["valor_total"] / e["quantidade_total"])
            if e["quantidade_total"] > 0 else 0.0
        )

        payload = {
            "codigo": e["codigo"],
            "ean": e["ean"],
            "descricao": desc_canon,
            "ncm": e["ncm"],
            "cfop_mais_frequente": cfop_mf,
            "unidade_mais_frequente": un_mf,
            "total_nfes": e["total_nfes"],
            "quantidade_total": round(e["quantidade_total"], 4),
            "valor_total": round(e["valor_total"], 2),
            "preco_medio": round(preco_medio, 4),
            "preco_min": round(e["preco_min"] or 0, 4),
            "preco_max": round(e["preco_max"] or 0, 4),
            "primeira_venda": e["primeira_venda"] or "",
            "ultima_venda": e["ultima_venda"] or "",
            "updated_at": datetime.now().isoformat(),
        }
        if _upsert_firestore_doc("produtos", doc_id, payload):
            sucessos += 1
        else:
            falhas += 1

    logger.info(
        f"[Firestore] Consolidação de produtos: {sucessos}/{len(produtos)} importados, {falhas} falhas."
    )
    return {
        "success": True,
        "total_unicos": len(produtos),
        "imported": sucessos,
        "failed": falhas,
        "timestamp": datetime.now().isoformat(),
        "message": (
            f"Consolidação de produtos concluída: {sucessos} de {len(produtos)} "
            f"produtos enviados para a coleção 'produtos' do Firestore."
        ),
    }


# ====================================================================
# SYNC: Firestore → SQLite (cad_clientes / cad_produtos)
# ====================================================================

def listar_itens_firestore_por_chaves(chaves: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Para cada chave, busca a subcoleção ``nfe_docs/{chave}/itens`` no Firestore.

    Retorna ``{chave: [itens_dict, ...]}``. Chaves sem itens no Firestore
    ficam com lista vazia.

    Usado pelo Excel detalhado como fallback quando o SQLite não tem
    ``nfe_items`` mas o Firestore tem (caso típico após upload de XMLs).
    """
    out: Dict[str, List[Dict[str, Any]]] = {ch: [] for ch in chaves}
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id or not chaves:
        return out

    base_url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/nfe_docs"
    )

    for ch in chaves:
        # Tenta também puxar o xml_raw do cabeçalho (caso queira aproveitar)
        try:
            doc_url = f"{base_url}/{ch}?key={api_key}"
            with urllib.request.urlopen(doc_url, timeout=15) as resp:
                doc_data = json.loads(resp.read())
            xml_raw = ""
            try:
                xml_raw = doc_data.get("fields", {}).get("xml_raw", {}).get("stringValue", "") or ""
            except Exception:
                xml_raw = ""
        except Exception:
            xml_raw = ""

        # Lista os itens
        itens_url = f"{base_url}/{ch}/itens?key={api_key}"
        try:
            with urllib.request.urlopen(itens_url, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception:
            continue

        itens_list: List[Dict[str, Any]] = []
        for d in data.get("documents", []):
            py = _firestore_fields_to_dict(d.get("fields", {}))
            if xml_raw:
                py["__xml_raw"] = xml_raw
            itens_list.append(py)
        out[ch] = itens_list

    return out


def _list_collection_from_firestore(collection: str, page_size: int = 300) -> List[Dict[str, Any]]:
    """Lista TODOS os documentos de uma coleção do Firestore (paginado)."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return []

    base_url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/{collection}"
    )
    all_docs: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    pages = 0

    while True:
        params = {"pageSize": str(page_size), "key": api_key}
        if page_token:
            params["pageToken"] = page_token
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"[Firestore] Erro ao listar {collection} (página {pages}): {e}")
            break
        for d in data.get("documents", []):
            all_docs.append(_firestore_fields_to_dict(d.get("fields", {})))
        page_token = data.get("nextPageToken")
        pages += 1
        if not page_token:
            break

    logger.info(f"[Firestore] Listagem de '{collection}': {len(all_docs)} docs em {pages} página(s).")
    return all_docs


def sincronizar_clientes_firestore_para_sqlite() -> Dict[str, Any]:
    """Copia a coleção 'clientes' do Firestore para a tabela cad_clientes do SQLite.
    Idempotente: docs existentes são atualizados pelo cpf_cnpj."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return {"success": False, "error": "Firestore não configurado"}

    docs = _list_collection_from_firestore("clientes")
    if not docs:
        return {"success": False, "error": "Coleção 'clientes' vazia ou inacessível"}

    # Importa sob demanda para evitar ciclo
    from backend.database.cadastros import save_cliente

    sucessos = 0
    falhas = 0
    pulados = 0
    for d in docs:
        cnpj_cpf = "".join(c for c in str(d.get("cnpj_cpf") or "") if c.isdigit())
        if len(cnpj_cpf) not in (11, 14):
            pulados += 1
            continue
        try:
            save_cliente({
                "cpf_cnpj": cnpj_cpf,
                "razao_social": (d.get("nome") or f"CLIENTE {cnpj_cpf}").strip(),
                "nome_fantasia": "",
                "ie": "",
                "indicador_ie": 9,
                "uf": (d.get("uf") or "SP").strip().upper(),
                "email": "",
                "telefone": "",
                "cep": "",
                "logradouro": "",
                "numero": "",
                "complemento": "",
                "bairro": "",
                "municipio": "",
                "cod_municipio": "3550308",
            })
            sucessos += 1
        except Exception as e:
            logger.warning(f"[Sync] Falha ao inserir cliente {cnpj_cpf}: {e}")
            falhas += 1

    logger.info(
        f"[Sync] Clientes Firestore→SQLite: {sucessos}/{len(docs)} importados, "
        f"{falhas} falhas, {pulados} pulados."
    )
    return {
        "success": True,
        "total_nuvem": len(docs),
        "imported": sucessos,
        "failed": falhas,
        "skipped": pulados,
        "message": f"{sucessos} de {len(docs)} clientes copiados para cad_clientes.",
    }


def sincronizar_produtos_firestore_para_sqlite() -> Dict[str, Any]:
    """Copia a coleção 'produtos' do Firestore para a tabela cad_produtos do SQLite.
    Idempotente: docs existentes são atualizados pelo codigo."""
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return {"success": False, "error": "Firestore não configurado"}

    docs = _list_collection_from_firestore("produtos")
    if not docs:
        return {"success": False, "error": "Coleção 'produtos' vazia ou inacessível"}

    from backend.database.cadastros import save_produto

    sucessos = 0
    falhas = 0
    pulados = 0
    for d in docs:
        codigo = (d.get("codigo") or "").strip()
        ean = (d.get("ean") or "").strip()
        if not codigo and not ean:
            pulados += 1
            continue
        try:
            preco_medio = 0.0
            try:
                preco_medio = float(d.get("preco_medio") or 0)
            except (TypeError, ValueError):
                preco_medio = 0.0
            save_produto({
                "codigo": codigo or f"EAN-{ean}",
                "descricao": (d.get("descricao") or "").strip() or f"PRODUTO {codigo or ean}",
                "ncm": (d.get("ncm") or "").strip(),
                "cfop_padrao": (d.get("cfop_mais_frequente") or "5102").strip(),
                "unidade": (d.get("unidade_mais_frequente") or "UN").strip(),
                "gtin": ean,
                "preco_venda": preco_medio,
                "preco_custo": 0.0,
                "estoque_atual": 0.0,
                "estoque_minimo": 0.0,
                "ativo": 1,
                "origem": 0,
                "csosn_cst": "102",
                "aliquota_icms": 0.0,
            })
            sucessos += 1
        except Exception as e:
            logger.warning(f"[Sync] Falha ao inserir produto {codigo or ean}: {e}")
            falhas += 1

    logger.info(
        f"[Sync] Produtos Firestore→SQLite: {sucessos}/{len(docs)} importados, "
        f"{falhas} falhas, {pulados} pulados."
    )
    return {
        "success": True,
        "total_nuvem": len(docs),
        "imported": sucessos,
        "failed": falhas,
        "skipped": pulados,
        "message": f"{sucessos} de {len(docs)} produtos copiados para cad_produtos.",
    }


def delete_nfes_from_firestore(chaves: List[str], empresa_cnpjs: Optional[List[str]] = None) -> int:
    """Exclui documentos de NF-e do Cloud Firestore em lote (na raiz nfe_docs e subcoleções empresas/cnpj/nfe_docs)."""
    if not chaves:
        return 0
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return 0

    commit_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:commit?key={api_key}"
    deleted_count = 0
    batch_size = 200

    clean_chaves = [c for c in chaves if c and len(c) == 44]
    if not clean_chaves:
        return 0

    for i in range(0, len(clean_chaves), batch_size):
        batch_slice = clean_chaves[i:i + batch_size]
        writes = []
        for ch in batch_slice:
            doc_name = f"projects/{project_id}/databases/(default)/documents/nfe_docs/{ch}"
            writes.append({"delete": doc_name})
            if empresa_cnpjs:
                for emp in set(empresa_cnpjs):
                    if emp:
                        emp_clean = "".join(c for c in str(emp) if c.isdigit())
                        if emp_clean:
                            emp_doc_name = f"projects/{project_id}/databases/(default)/documents/empresas/{emp_clean}/nfe_docs/{ch}"
                            writes.append({"delete": emp_doc_name})

        if not writes:
            continue

        body_bytes = json.dumps({"writes": writes}).encode("utf-8")
        req = urllib.request.Request(
            commit_url,
            data=body_bytes,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 201):
                    deleted_count += len(batch_slice)
        except Exception as e:
            logger.warning(f"[Firestore] Erro ao excluir lote no Firestore: {e}")

    return deleted_count

