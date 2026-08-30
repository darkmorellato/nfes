import io
from typing import Optional, Dict, Any, List
from datetime import datetime
import openpyxl

from backend.database import list_certificates_db, get_db_connection
from backend.utils.excel_helpers import (
    HEADER_FILL, HEADER_FONT, TITLE_FONT, SUB_FONT, TOTAL_FILL, BOLD_FONT,
    CURRENCY_FMT, NUM_FMT, THIN_BORDER, format_cnpj, apply_header_row, apply_title, apply_subtitle, auto_adjust_columns,
)


def generate_fiscal_excel(mes: Optional[int] = None, ano: Optional[int] = None) -> io.BytesIO:
    """Gera uma planilha Excel .xlsx profissional e estilizada com abas separadas por empresa."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    wb = openpyxl.Workbook()
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    certs = list_certificates_db()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chave, empresa_cnpj, numero, serie, modelo, emitente_cnpj, emitente_nome,
                   destinatario_cnpj, destinatario_nome, data_emissao,
                   valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi, situacao
            FROM nfe_docs
            WHERE data_emissao LIKE ?
            ORDER BY empresa_cnpj, data_emissao ASC
        """, (f"{mes_str}%",))
        docs_mes = [dict(r) for r in cursor.fetchall()]

    # ================================================================
    # 1. ABA RESUMO CONSOLIDADO
    # ================================================================
    ws_resumo = wb.create_sheet(title="Resumo Consolidado")
    ws_resumo.views.sheetView[0].showGridLines = True

    apply_title(ws_resumo, 1, 1, f"FECHAMENTO FISCAL CONSOLIDADO - {mes:02d}/{ano:04d}")
    apply_subtitle(ws_resumo, 2, 1, f"Gerado em {now.strftime('%d/%m/%Y %H:%M:%S')} - Grupo Empresarial Multi-Empresas")

    headers_emp = ["CNPJ Empresa", "Razão Social", "Qtd Notas", "Total Compras (R$)", "Total ICMS (R$)", "Total PIS (R$)", "Total COFINS (R$)"]
    ws_resumo.append([])
    ws_resumo.append(["RESUMO POR EMPRESA"])
    ws_resumo["A4"].font = Font(name="Calibri", size=12, bold=True, color="2C3E50")

    ws_resumo.append(headers_emp)
    header_row_idx = 5
    apply_header_row(ws_resumo, header_row_idx, headers_emp)

    curr_row = 6
    for c in certs:
        c_cnpj = c["cnpj"]
        c_docs = [d for d in docs_mes if d.get("empresa_cnpj") == c_cnpj or c_cnpj in (d.get("destinatario_cnpj") or "")]
        qtd = len(c_docs)
        v_tot = sum(float(d.get("valor_total") or 0) for d in c_docs)
        v_icms = sum(float(d.get("valor_icms") or 0) for d in c_docs)
        v_pis = sum(float(d.get("valor_pis") or 0) for d in c_docs)
        v_cof = sum(float(d.get("valor_cofins") or 0) for d in c_docs)

        cnpj_fmt = format_cnpj(c_cnpj)

        ws_resumo.append([cnpj_fmt, c["razao_social"], qtd, v_tot, v_icms, v_pis, v_cof])

        ws_resumo.cell(row=curr_row, column=3).number_format = NUM_FMT
        for col_i in range(4, 8):
            ws_resumo.cell(row=curr_row, column=col_i).number_format = CURRENCY_FMT
        curr_row += 1

    total_row = curr_row
    ws_resumo.append([
        "TOTAL DO GRUPO", "", f"=SUM(C6:C{total_row-1})", f"=SUM(D6:D{total_row-1})",
        f"=SUM(E6:E{total_row-1})", f"=SUM(F6:F{total_row-1})", f"=SUM(G6:G{total_row-1})"
    ])
    for col_i in range(1, 8):
        c_cell = ws_resumo.cell(row=total_row, column=col_i)
        c_cell.fill = TOTAL_FILL
        c_cell.font = BOLD_FONT
        if col_i >= 4:
            c_cell.number_format = CURRENCY_FMT

    # ================================================================
    # 2. ABAS INDIVIDUAIS POR EMPRESA
    # ================================================================
    headers_doc = [
        "Data Emissão", "Número", "Série", "Chave de Acesso", "CNPJ Emitente",
        "Razão Social Emitente", "Valor Total (R$)", "ICMS (R$)", "PIS (R$)", "COFINS (R$)", "IPI (R$)", "Situação"
    ]

    for c in certs:
        c_cnpj = c["cnpj"]
        short_name = (c["razao_social"][:25]).strip()
        for ch in ["\\", "/", "?", "*", "[", "]", ":"]:
            short_name = short_name.replace(ch, "_")

        ws = wb.create_sheet(title=short_name)
        ws.views.sheetView[0].showGridLines = True

        apply_title(ws, 1, 1, f"{c['razao_social']} - CNPJ {c['cnpj']}")
        apply_subtitle(ws, 2, 1, f"Fechamento Fiscal de Compras e Entradas: {mes:02d}/{ano:04d}")

        ws.append([])
        ws.append(headers_doc)
        h_row = 4
        apply_header_row(ws, h_row, headers_doc)

        c_docs = [d for d in docs_mes if d.get("empresa_cnpj") == c_cnpj or c_cnpj in (d.get("destinatario_cnpj") or "")]

        r_idx = 5
        for d in c_docs:
            dt_str = d.get("data_emissao", "")
            if dt_str and len(dt_str) >= 10:
                try:
                    dt_val = datetime.fromisoformat(dt_str.replace("Z", "")).strftime("%d/%m/%Y")
                except Exception:
                    dt_val = dt_str[:10]
            else:
                dt_val = dt_str

            ws.append([
                dt_val,
                d.get("numero", ""),
                d.get("serie", "1"),
                d.get("chave", ""),
                d.get("emitente_cnpj", ""),
                d.get("emitente_nome", ""),
                float(d.get("valor_total") or 0),
                float(d.get("valor_icms") or 0),
                float(d.get("valor_pis") or 0),
                float(d.get("valor_cofins") or 0),
                float(d.get("valor_ipi") or 0),
                d.get("situacao", "Autorizada"),
            ])

            for col_i in range(7, 12):
                ws.cell(row=r_idx, column=col_i).number_format = CURRENCY_FMT
            r_idx += 1

        if c_docs:
            tot_r = r_idx
            ws.append([
                "TOTAL", "", "", f"{len(c_docs)} nota(s)", "", "",
                f"=SUM(G5:G{tot_r-1})", f"=SUM(H5:H{tot_r-1})", f"=SUM(I5:I{tot_r-1})",
                f"=SUM(J5:J{tot_r-1})", f"=SUM(K5:K{tot_r-1})", ""
            ])
            for col_i in range(1, 13):
                c_cell = ws.cell(row=tot_r, column=col_i)
                c_cell.fill = TOTAL_FILL
                c_cell.font = BOLD_FONT
                if 7 <= col_i <= 11:
                    c_cell.number_format = CURRENCY_FMT

    auto_adjust_columns(ws_resumo)
    for sheet in wb.worksheets:
        if sheet != ws_resumo:
            auto_adjust_columns(sheet)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

