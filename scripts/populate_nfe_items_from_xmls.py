"""Lê os XMLs da pasta e popula nfe_items + xml_raw no SQLite.

Uso:
    python populate_nfe_items_from_xmls.py /home/dark/Desktop/nfes\ host/

É instantâneo (leitura local) e garante que o Excel detalhado funcione.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO = BASE_DIR.parent if BASE_DIR.name == "scripts" else BASE_DIR
sys.path.insert(0, str(REPO))

from backend.services.danfe_service import parse_nfe_xml
from backend.database import get_db_connection

def main():
    if len(sys.argv) < 2:
        print("Uso: python populate_nfe_items_from_xmls.py /caminho/da/pasta")
        sys.exit(1)

    pasta = Path(sys.argv[1]).expanduser()
    if not pasta.is_dir():
        print(f"[ERRO] Pasta não encontrada: {pasta}")
        sys.exit(1)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        arquivos = sorted(p for p in pasta.glob("*.xml"))
        print(f"[INFO] {len(arquivos)} XMLs encontrados em {pasta}")

        atualizados = 0
        novos_items = 0
        erros = 0
        pulados = 0

        for i, arq in enumerate(arquivos, start=1):
            nome = arq.stem.strip()
            if nome.upper().startswith("NFE-"):
                nome = nome[4:]
            if len(nome) != 44 or not nome.isdigit():
                pulados += 1
                continue
            if "procInutNFe" in nome or "procEventoNFe" in nome:
                pulados += 1
                continue

            try:
                xml_bytes = arq.read_bytes()
            except Exception:
                erros += 1
                continue

            try:
                parsed = parse_nfe_xml(xml_bytes)
            except Exception:
                erros += 1
                continue

            if not parsed or parsed.get("error"):
                pulados += 1
                continue

            chave = parsed.get("chave") or nome
            if len(chave) != 44:
                chave = nome

            xml_raw = xml_bytes.decode("utf-8", errors="replace")

            cursor.execute(
                "UPDATE nfe_docs SET xml_raw = COALESCE(NULLIF(xml_raw, ''), ?) WHERE chave = ?",
                (xml_raw, chave),
            )

            cursor.execute("SELECT COUNT(*) FROM nfe_items WHERE chave = ?", (chave,))
            n_items = cursor.fetchone()[0]

            produtos = parsed.get("produtos", []) or []
            if not produtos:
                pulados += 1
                continue

            if n_items > 0:
                atualizados += 1
                if i % 200 == 0:
                    conn.commit()
                    print(f"  ... {i}/{len(arquivos)}")
                continue

            for idx, p in enumerate(produtos, start=1):
                cursor.execute(
                    """
                    INSERT INTO nfe_items (
                        chave, n_item, codigo, ean, descricao, ncm, cfop, unidade,
                        quantidade, valor_unitario, valor_total, cst, v_icms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chave,
                        int(p.get("n_item") or idx),
                        p.get("codigo") or "",
                        p.get("ean") or "",
                        p.get("descricao") or "",
                        p.get("ncm") or "",
                        p.get("cfop") or "",
                        p.get("unidade") or "",
                        float(p.get("quantidade") or 0),
                        float(p.get("valor_unitario") or 0),
                        float(p.get("valor_total") or 0),
                        p.get("cst") or "",
                        float(p.get("v_icms") or 0),
                    ),
                )
                novos_items += 1

            if i % 200 == 0:
                conn.commit()
                print(f"  ... {i}/{len(arquivos)} (items inseridos: {novos_items})")

        conn.commit()

    print()
    print("=" * 60)
    print(f"Concluído!")
    print(f"  • Items novos inseridos: {novos_items}")
    print(f"  • NF-e já com items: {atualizados}")
    print(f"  • Pulados: {pulados}")
    print(f"  • Erros: {erros}")
    print("=" * 60)


if __name__ == "__main__":
    main()
