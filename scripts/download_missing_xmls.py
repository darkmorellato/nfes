"""Baixa XMLs que faltam via SEFAZ e salva no SQLite + Firestore.

Uso:
    python download_missing_xmls.py

Busca todas as NF-e sem itens no banco, consulta a SEFAZ via consChNFe,
e salva o XML completo + itens. Requer certificado digital ativo.
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parent
REPO = BASE_DIR.parent if BASE_DIR.name == "scripts" else BASE_DIR
sys.path.insert(0, str(REPO))

from backend.config import settings
from backend.database import get_db_connection, get_certificate_record
from backend.services.danfe_service import parse_nfe_xml, parse_distribuicao_xml
from backend.database.nfe_docs import save_nfe_doc
from backend.services.sync_service import _calcular_cooldown_656

# Forçar PRODUÇÃO para buscar XMLs completos (resNFe não tem itens)
# homologacao=False = www1.nfe.fazenda.gov.br (produção)
PRODUCAO = True


def main():
    print("[INFO] Buscando NF-e sem itens no banco...")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.chave, d.empresa_cnpj, d.emitente_cnpj, d.numero, d.emitente_nome
            FROM nfe_docs d
            WHERE NOT EXISTS (SELECT 1 FROM nfe_items i WHERE i.chave = d.chave)
            ORDER BY d.data_emissao DESC
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        print("[INFO] Todas as NF-e já têm itens. Nada a fazer.")
        return

    print(f"[INFO] {len(rows)} NF-e sem itens encontradas.")

    # Agrupar por empresa (cada empresa usa seu próprio certificado)
    por_empresa: Dict[str, list] = {}
    sem_empresa: list = []
    for r in rows:
        emp = r.get("empresa_cnpj") or ""
        if not emp or not get_certificate_record(emp):
            alt = r.get("emitente_cnpj") or ""
            alt_clean = "".join(c for c in str(alt) if c.isdigit())
            if alt_clean and get_certificate_record(alt_clean):
                emp = alt_clean
        if emp and get_certificate_record(emp):
            por_empresa.setdefault(emp, []).append(r)
        else:
            sem_empresa.append(r)

    print(f"[INFO] Empresas com certificado: {len(por_empresa)}")
    print(f"[INFO] NF-e sem certificado: {len(sem_empresa)}")

    total_sucessos = 0
    total_falhas = 0
    t0 = time.time()

    for emp_cnpj, nfe_list in por_empresa.items():
        chaves = [r["chave"] for r in nfe_list]
        print(f"\n--- Empresa {emp_cnpj} ({len(chaves)} NF-e) ---")

        # Verificar cooldown 656 antes de começar
        cooldown = _calcular_cooldown_656(emp_cnpj)
        if cooldown:
            from datetime import datetime
            wait_min = max(0, (cooldown - datetime.now()).total_seconds() / 60)
            if wait_min > 0:
                print(f"  [COOLDOWN] Empresa bloqueada pela SEFAZ. Aguardando {wait_min:.0f} min...")
                time.sleep(wait_min * 60 + 10)  # +10s de margem
                print(f"  [COOLDOWN] Cooldown expirado. Continuando...")

        from pynfe.processamento.comunicacao import ComunicacaoSefaz

        cert_rec = get_certificate_record(emp_cnpj)
        cert_path = cert_rec.get("path")
        cert_pwd = cert_rec.get("password")
        uf = settings.DEFAULT_UF.upper()
        homolog = not PRODUCAO  # False = produção

        try:
            con = ComunicacaoSefaz(uf, cert_path, cert_pwd, homologacao=homolog)
        except Exception as e:
            print(f"  [ERRO] Falha ao conectar: {e}")
            total_falhas += len(chaves)
            continue

        for i, chave in enumerate(chaves, start=1):
            print(f"  [{i}/{len(chaves)}] {chave[:20]}...", end=" ", flush=True)

            try:
                resp = con.consulta_distribuicao(cnpj=emp_cnpj, chave=chave)
                if resp.status_code != 200:
                    print(f"ERRO HTTP {resp.status_code}")
                    total_falhas += 1
                    continue

                parsed = parse_distribuicao_xml(resp.text)
                c_stat = parsed.get("c_stat", "")

                if c_stat == "656":
                    print(f"SEFAZ bloqueou (656) — aguardando 60s...")
                    time.sleep(60)
                    # Retry uma vez
                    resp = con.consulta_distribuicao(cnpj=emp_cnpj, chave=chave)
                    if resp.status_code != 200:
                        print(f"ERRO retry HTTP {resp.status_code}")
                        total_falhas += 1
                        continue
                    parsed = parse_distribuicao_xml(resp.text)
                    c_stat = parsed.get("c_stat", "")
                    if c_stat == "656":
                        print(f"BLOQUEADO (656) — parando esta empresa.")
                        total_falhas += len(chaves) - i + 1
                        break

                documentos = parsed.get("documentos", [])
                c_stat = parsed.get("c_stat", "")
                motivo = parsed.get("motivo", "")
                xml_encontrado = None
                dados_doc = None

                for doc in documentos:
                    tag = doc.get("tag", "")
                    xml_raw = doc.get("xml_raw", "")
                    if tag in ("nfeProc", "NFe") and xml_raw:
                        xml_encontrado = xml_raw
                        try:
                            dados_doc = parse_nfe_xml(xml_raw.encode("utf-8"))
                        except Exception:
                            dados_doc = None
                        break
                    elif tag == "resNFe":
                        dados_doc = {
                            "chave": doc.get("chave") or chave,
                            "nome_emitente": doc.get("nome_emitente", ""),
                            "cnpj_emitente": doc.get("cnpj_emitente", ""),
                            "valor_total": doc.get("valor_total", 0),
                            "data_emissao": doc.get("data_emissao", ""),
                            "situacao": doc.get("situacao", "Autorizada"),
                        }
                        break

                # Fallback: se consChNFe não retornou XML completo, tenta via NSU
                if not xml_encontrado:
                    # Buscar NSU desta nota no banco
                    nsu_val = None
                    with get_db_connection() as conn_check:
                        cur_check = conn_check.cursor()
                        cur_check.execute("SELECT nsu FROM nfe_docs WHERE chave = ?", (chave,))
                        row_nsu = cur_check.fetchone()
                        if row_nsu and row_nsu[0] and row_nsu[0] != "0":
                            nsu_val = row_nsu[0]

                    if nsu_val:
                        try:
                            resp_nsu = con.consulta_distribuicao(cnpj=emp_cnpj, nsu=nsu_val)
                            if resp_nsu.status_code == 200:
                                parsed_nsu = parse_distribuicao_xml(resp_nsu.text)
                                for doc in parsed_nsu.get("documentos", []):
                                    tag = doc.get("tag", "")
                                    xml_raw = doc.get("xml_raw", "")
                                    if tag in ("nfeProc", "NFe") and xml_raw:
                                        xml_encontrado = xml_raw
                                        try:
                                            dados_doc = parse_nfe_xml(xml_raw.encode("utf-8"))
                                        except Exception:
                                            dados_doc = None
                                        break
                            time.sleep(1.0)
                        except Exception:
                            pass

                if not dados_doc:
                    print("NF-e não localizada")
                    total_falhas += 1
                    continue

                dados_doc["nsu"] = "0"
                dados_doc["empresa_cnpj"] = emp_cnpj
                dados_doc["tipo_doc"] = 1
                dados_doc["data_autorizacao"] = dados_doc.get("data_autorizacao") or ""
                dados_doc["situacao"] = dados_doc.get("situacao") or "Autorizada"

                if save_nfe_doc(dados_doc, xml_raw=xml_encontrado, empresa_cnpj=emp_cnpj):
                    n_itens = len(dados_doc.get("produtos", []))
                    print(f"OK ({n_itens} itens)")
                    total_sucessos += 1
                else:
                    print("ERRO save")
                    total_falhas += 1

                time.sleep(4.0)  # Rate limit: 20 consultas/hora = 1 a cada 3 min

            except Exception as e:
                print(f"ERRO: {e}")
                total_falhas += 1

    dt = time.time() - t0

    if sem_empresa:
        print(f"\n[AVISO] {len(sem_empresa)} NF-e sem certificado cadastrado — ignoradas.")

    print()
    print("=" * 60)
    print(f"Concluído em {dt:.1f}s")
    print(f"  • Sucessos: {total_sucessos}")
    print(f"  • Falhas: {total_falhas}")
    print(f"  • NF-e sem certificado: {len(sem_empresa)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
