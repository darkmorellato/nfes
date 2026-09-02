"""Envia todos os XMLs de NF-e de uma pasta para o Cloud Firestore (BatchWrite).

Uso:
    python upload_xmls_to_firestore.py /home/dark/Desktop/nfes\ host/

Usa a API Firestore BatchWrite (commit) para enviar até 500 operações
por request, reduzindo drasticamente o número de chamadas HTTP.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent
REPO = BASE_DIR.parent if BASE_DIR.name == "scripts" else BASE_DIR
sys.path.insert(0, str(REPO))


def _load_env() -> None:
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()
API_KEY = os.environ.get("FIREBASE_API_KEY", "").strip()
PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "").strip()

if not API_KEY or not PROJECT_ID:
    print("[ERRO] FIREBASE_API_KEY e/ou FIREBASE_PROJECT_ID não definidos.")
    sys.exit(1)

try:
    from backend.services.danfe_service import parse_nfe_xml
except Exception as e:
    print(f"[ERRO] Falha ao importar parse_nfe_xml: {e}")
    sys.exit(1)


# ================================================================
# Firestore helpers
# ================================================================

def _py_to_fs(val: Any) -> Dict[str, Any]:
    if val is None:
        return {"nullValue": "NULL_VALUE"}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, list):
        return {"arrayValue": {"values": [_py_to_fs(x) for x in val]}}
    if isinstance(val, dict):
        return {"mapValue": {"fields": {k: _py_to_fs(v) for k, v in val.items() if v is not None}}}
    return {"stringValue": str(val)}


def _fields(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _py_to_fs(v) for k, v in d.items() if v is not None}


def _doc_name(*parts: str) -> str:
    path = "/".join(parts)
    return f"projects/{PROJECT_ID}/databases/(default)/documents/{path}"


def _commit(writes: List[Dict[str, Any]], label: str = "") -> bool:
    """Envia batch de writes via Firestore commit API. Máx 500 por batch."""
    url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/databases/(default)/documents:commit?key={API_KEY}"
    )
    body = {"writes": writes}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                headers={"Content-Type": "application/json"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 15.0 * (attempt + 1)
                print(f"  [429] Rate limit — aguardando {wait:.0f}s... (batch {label})")
                time.sleep(wait)
                continue
            if attempt == 5:
                print(f"  [ERRO] Commit HTTP {e.code} (batch {label})")
                return False
            time.sleep(5.0 * (attempt + 1))
        except Exception as e:
            if attempt == 5:
                print(f"  [ERRO] Commit falhou: {e} (batch {label})")
                return False
            time.sleep(5.0 * (attempt + 1))
    return False


def _list_collection(collection: str) -> Set[str]:
    """Lista todos os IDs de documentos de uma coleção."""
    ids: Set[str] = set()
    page_token: Optional[str] = None
    while True:
        params = {"pageSize": "300", "key": API_KEY}
        if page_token:
            params["pageToken"] = page_token
        url = (
            f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
            f"/databases/(default)/documents/{collection}"
        ) + "?" + urllib.parse.urlencode(params)
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(10.0 * (attempt + 1))
                    continue
                return ids
            except Exception:
                return ids
        else:
            break
        for d in data.get("documents", []):
            name = d.get("name", "")
            doc_id = name.split("/")[-1]
            if len(doc_id) == 44 and doc_id.isdigit():
                ids.add(doc_id)
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(1.0)
    return ids


# ================================================================
# Parse
# ================================================================

def _to_float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def processar_arquivo(caminho: Path) -> Optional[Dict[str, Any]]:
    nome = caminho.name
    if "procInutNFe" in nome or "procEventoNFe" in nome:
        return None
    chave_esperada = caminho.stem.strip()
    if len(chave_esperada) != 44 or not chave_esperada.isdigit():
        return None
    try:
        xml_bytes = caminho.read_bytes()
    except Exception:
        return None
    try:
        parsed = parse_nfe_xml(xml_bytes)
    except Exception:
        return None
    if not parsed or parsed.get("error"):
        return None
    chave = parsed.get("chave") or chave_esperada
    if len(chave) != 44:
        chave = chave_esperada

    ident = parsed.get("identificacao", {}) or {}
    emit = parsed.get("emitente", {}) or {}
    dest = parsed.get("destinatario", {}) or {}
    totais = parsed.get("totais", {}) or {}
    prot = parsed.get("protocolo") or {}

    v_total = _to_float(totais.get("v_nf") or totais.get("valor_total"))
    v_icms = _to_float(totais.get("v_icms"))
    v_pis = _to_float(totais.get("v_pis"))
    v_cofins = _to_float(totais.get("v_cofins"))
    v_ipi = _to_float(totais.get("v_ipi"))

    tp_nf = ident.get("tipo_operacao") or ident.get("tp_nf")
    try:
        tipo_doc = int(tp_nf) if tp_nf is not None else 1
    except Exception:
        tipo_doc = 1

    emit_cnpj = emit.get("cnpj") or ""
    dest_cnpj = dest.get("cnpj") or dest.get("cpf") or ""

    cabecalho = {
        "chave": chave,
        "numero": str(ident.get("numero") or ""),
        "serie": str(ident.get("serie") or "1"),
        "modelo": str(ident.get("modelo") or "55"),
        "tipo_doc": tipo_doc,
        "empresa_cnpj": emit_cnpj,
        "emitente_cnpj": emit_cnpj,
        "emitente_nome": (emit.get("nome") or "").strip(),
        "emitente_uf": emit.get("uf") or "",
        "destinatario_cnpj": dest_cnpj,
        "destinatario_nome": (dest.get("nome") or "").strip(),
        "destinatario_uf": dest.get("uf") or "",
        "data_emissao": ident.get("data_emissao") or "",
        "data_autorizacao": parsed.get("data_autorizacao") or "",
        "valor_total": round(v_total, 2),
        "valor_icms": round(v_icms, 2),
        "valor_pis": round(v_pis, 2),
        "valor_cofins": round(v_cofins, 2),
        "valor_ipi": round(v_ipi, 2),
        "situacao": "Autorizada",
        "nsu": "0",
        "has_xml": True,
        "xml_raw": xml_bytes.decode("utf-8", errors="replace"),
        "protocolo": prot,
        "updated_at": datetime.now().isoformat(),
    }

    itens_out: List[Dict[str, Any]] = []
    for idx, p in enumerate(parsed.get("produtos", []) or [], start=1):
        itens_out.append({
            "n_item": int(p.get("n_item") or idx),
            "ordem": idx,
            "codigo": p.get("codigo") or "",
            "ean": p.get("ean") or "",
            "descricao": p.get("descricao") or "",
            "ncm": p.get("ncm") or "",
            "cfop": p.get("cfop") or "",
            "unidade": p.get("unidade") or "",
            "quantidade": _to_float(p.get("quantidade")),
            "valor_unitario": _to_float(p.get("valor_unitario")),
            "valor_total": _to_float(p.get("valor_total")),
            "cst": p.get("cst") or "",
            "v_icms": _to_float(p.get("v_icms")),
            "v_bc_icms": _to_float(p.get("v_bc_icms")),
            "aliquota_icms": _to_float(p.get("aliquota_icms")),
        })

    return {"chave": chave, "cabecalho": cabecalho, "itens": itens_out}


# ================================================================
# Main
# ================================================================

def main():
    if len(sys.argv) < 2:
        print("Uso: python upload_xmls_to_firestore.py /caminho/da/pasta")
        sys.exit(1)

    pasta = Path(sys.argv[1]).expanduser()
    if not pasta.is_dir():
        print(f"[ERRO] Pasta não encontrada: {pasta}")
        sys.exit(1)

    print(f"[INFO] Pasta: {pasta}")
    print(f"[INFO] Project: {PROJECT_ID}")

    # Listar chaves existentes é opcional — como usamos upsert (PATCH),
    # podemos pular a listagem se o Firestore estiver com rate limit.
    skip_list = "--skip-list" in sys.argv
    if skip_list:
        chaves_existentes: Set[str] = set()
        print("[INFO] Listagem pulada (--skip-list).")
    else:
        print("[INFO] Listando chaves existentes no Firestore...")
        chaves_existentes = _list_collection("nfe_docs")
        print(f"[INFO] {len(chaves_existentes)} chaves já existem.")

    arquivos = sorted(p for p in pasta.glob("*.xml"))
    print(f"[INFO] {len(arquivos)} arquivos .xml encontrados.")

    BATCH_SIZE = 50  # writes por batch (mínimo para evitar 429)

    # Fase 1: Parsear todos os XMLs e montar writes
    print("[FASE 1] Parseando XMLs e montando writes...")
    all_writes: List[Dict[str, Any]] = []
    nfe_count = 0
    item_count = 0
    parse_erros = 0
    skips = 0

    for i, arq in enumerate(arquivos, start=1):
        nome = arq.name
        if "procInutNFe" in nome or "procEventoNFe" in nome:
            skips += 1
            continue
        chave = arq.stem.strip()
        if len(chave) != 44 or not chave.isdigit():
            skips += 1
            continue

        try:
            dados = processar_arquivo(arq)
        except Exception:
            parse_erros += 1
            continue
        if not dados:
            skips += 1
            continue

        ch = dados["chave"]

        # Write do cabeçalho
        doc_ref = _doc_name("nfe_docs", ch)
        all_writes.append({
            "update": {
                "name": doc_ref,
                "fields": _fields(dados["cabecalho"]),
            }
        })
        nfe_count += 1

        # Writes dos itens
        for idx, it in enumerate(dados["itens"], start=1):
            item_ref = _doc_name("nfe_docs", ch, "itens", f"item_{idx:03d}")
            all_writes.append({
                "update": {
                    "name": item_ref,
                    "fields": _fields(it),
                }
            })
            item_count += 1

        if i % 100 == 0:
            print(f"  ... {i}/{len(arquivos)} XMLs processados, {len(all_writes)} writes pendentes")

    print(f"[FASE 1 OK] {nfe_count} NF-e, {item_count} itens, {parse_erros} erros, {skips} pulados")
    print(f"[INFO] Total de writes: {len(all_writes)}")

    if not all_writes:
        print("[INFO] Nada para enviar.")
        return

    # Fase 2: Enviar em batches
    batches = [all_writes[i:i + BATCH_SIZE] for i in range(0, len(all_writes), BATCH_SIZE)]
    print(f"[FASE 2] Enviando {len(batches)} batch(es) de até {BATCH_SIZE} writes cada...")

    ok_batches = 0
    falha_batches = 0
    t0 = time.time()

    for b_idx, batch in enumerate(batches, start=1):
        pct = (b_idx / len(batches)) * 100
        print(f"  Batch {b_idx}/{len(batches)} ({len(batch)} writes, {pct:.0f}%)...", end=" ", flush=True)
        ok = _commit(batch, label=f"{b_idx}/{len(batches)}")
        if ok:
            print("OK")
            ok_batches += 1
        else:
            print("FALHOU")
            falha_batches += 1
        # Pausa entre batches para evitar 429
        if b_idx < len(batches):
            time.sleep(10.0)

    dt = time.time() - t0
    print()
    print("=" * 60)
    print(f"Concluído em {dt:.1f}s")
    print(f"  • Batches OK: {ok_batches}/{len(batches)}")
    print(f"  • Batches com falha: {falha_batches}")
    print(f"  • NF-e: {nfe_count} (itens: {item_count})")
    print("=" * 60)


if __name__ == "__main__":
    main()
