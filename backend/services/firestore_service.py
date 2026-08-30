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
import threading
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

def sync_all_database_to_firestore(batch_size: int = 200) -> Dict[str, Any]:
    api_key = _get_api_key()
    project_id = _get_project_id()
    if not api_key or not project_id:
        return {"success": False, "error": "Credenciais do Firebase não configuradas."}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emitente_cnpj, emitente_nome, emitente_uf, destinatario_cnpj, destinatario_nome, destinatario_uf, data_emissao, data_autorizacao, valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi, situacao, nsu, has_xml FROM nfe_docs ORDER BY data_emissao DESC")
        all_docs = [dict(r) for r in cursor.fetchall()]

    total = len(all_docs)
    if total == 0:
        return {"success": True, "total": 0, "synced": 0, "message": "Nenhuma nota fiscal encontrada no banco local."}

    commit_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents:commit?key={api_key}"
    synced_count = 0
    errors_count = 0

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
            writes.append({
                "update": {
                    "name": doc_name,
                    "fields": fields,
                }
            })

            emp_cnpj = payload.get("empresa_cnpj")
            if emp_cnpj:
                emp_doc_name = f"projects/{project_id}/databases/(default)/documents/empresas/{emp_cnpj}/nfe_docs/{chave}"
                writes.append({
                    "update": {
                        "name": emp_doc_name,
                        "fields": fields,
                    }
                })

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
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201):
                    synced_count += len(batch_slice)
                    logger.info(f"[Firestore Batch] Progresso: {synced_count}/{total} notas enviadas.")
                else:
                    errors_count += len(batch_slice)
        except Exception as batch_err:
            logger.error(f"[Firestore Batch] Erro no lote {i}-{i+batch_size}: {batch_err}")
            errors_count += len(batch_slice)

    return {
        "success": True,
        "total": total,
        "synced": synced_count,
        "errors": errors_count,
        "project_id": project_id,
        "timestamp": datetime.now().isoformat(),
        "message": f"Sincronização com o Cloud Firestore concluída: {synced_count} de {total} notas fiscais sincronizadas com sucesso!",
    }
