import io
from typing import Optional, Dict, Any, List
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.database import list_certificates_db, get_db_connection


def generate_fiscal_excel(mes: Optional[int] = None, ano: Optional[int] = None) -> io.BytesIO:
    """Gera uma planilha Excel .xlsx profissional e estilizada com abas separadas por empresa."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    wb = openpyxl.Workbook()
    # Remove aba padrão inicial
    if "Sheet" in wb.sheetnames:
        wb.remove(wb["Sheet"])

    # Estilos Visuais
    header_fill = PatternFill(start_color="1B4F72", end_color="1B4F72", fill_type="solid")  # Azul Corporativo
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1B4F72")
    sub_font = Font(name="Calibri", size=10, italic=True, color="555555")
    total_fill = PatternFill(start_color="EAEDED", end_color="EAEDED", fill_type="solid")
    bold_font = Font(name="Calibri", size=10, bold=True)
    currency_fmt = "R$ #,##0.00"
    num_fmt = "#,##0"

    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

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

    ws_resumo["A1"] = f"FECHAMENTO FISCAL CONSOLIDADO - {mes:02d}/{ano:04d}"
    ws_resumo["A1"].font = title_font
    ws_resumo["A2"] = f"Gerado em {now.strftime('%d/%m/%Y %H:%M:%S')} - Grupo Empresarial Multi-Empresas"
    ws_resumo["A2"].font = sub_font

    # Resumo por Empresa
    headers_emp = ["CNPJ Empresa", "Razão Social", "Qtd Notas", "Total Compras (R$)", "Total ICMS (R$)", "Total PIS (R$)", "Total COFINS (R$)"]
    ws_resumo.append([])
    ws_resumo.append(["RESUMO POR EMPRESA"])
    ws_resumo["A4"].font = Font(name="Calibri", size=12, bold=True, color="2C3E50")

    ws_resumo.append(headers_emp)
    header_row_idx = 5
    for col_idx in range(1, len(headers_emp) + 1):
        cell = ws_resumo.cell(row=header_row_idx, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    curr_row = 6
    for c in certs:
        c_cnpj = c["cnpj"]
        c_docs = [d for d in docs_mes if d.get("empresa_cnpj") == c_cnpj or c_cnpj in (d.get("destinatario_cnpj") or "")]
        qtd = len(c_docs)
        v_tot = sum(float(d.get("valor_total") or 0) for d in c_docs)
        v_icms = sum(float(d.get("valor_icms") or 0) for d in c_docs)
        v_pis = sum(float(d.get("valor_pis") or 0) for d in c_docs)
        v_cof = sum(float(d.get("valor_cofins") or 0) for d in c_docs)

        cnpj_fmt = f"{c_cnpj[:2]}.{c_cnpj[2:5]}.{c_cnpj[5:8]}/{c_cnpj[8:12]}-{c_cnpj[12:]}" if len(c_cnpj) == 14 else c_cnpj

        ws_resumo.append([cnpj_fmt, c["razao_social"], qtd, v_tot, v_icms, v_pis, v_cof])

        # Formatação
        ws_resumo.cell(row=curr_row, column=3).number_format = num_fmt
        for col_i in range(4, 8):
            ws_resumo.cell(row=curr_row, column=col_i).number_format = currency_fmt
        curr_row += 1

    # Linha Total Grupo
    total_row = curr_row
    ws_resumo.append([
        "TOTAL DO GRUPO", "", f"=SUM(C6:C{total_row-1})", f"=SUM(D6:D{total_row-1})",
        f"=SUM(E6:E{total_row-1})", f"=SUM(F6:F{total_row-1})", f"=SUM(G6:G{total_row-1})"
    ])
    for col_i in range(1, 8):
        c_cell = ws_resumo.cell(row=total_row, column=col_i)
        c_cell.fill = total_fill
        c_cell.font = bold_font
        if col_i >= 4:
            c_cell.number_format = currency_fmt

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
        # Remove caracteres inválidos para nomes de abas Excel
        for ch in ["\\", "/", "?", "*", "[", "]", ":"]:
            short_name = short_name.replace(ch, "_")

        ws = wb.create_sheet(title=short_name)
        ws.views.sheetView[0].showGridLines = True

        ws["A1"] = f"{c['razao_social']} - CNPJ {c['cnpj']}"
        ws["A1"].font = title_font
        ws["A2"] = f"Fechamento Fiscal de Compras e Entradas: {mes:02d}/{ano:04d}"
        ws["A2"].font = sub_font

        ws.append([])
        ws.append(headers_doc)
        h_row = 4
        for col_idx in range(1, len(headers_doc) + 1):
            cell = ws.cell(row=h_row, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

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
                ws.cell(row=r_idx, column=col_i).number_format = currency_fmt
            r_idx += 1

        # Linha de Totais da Empresa
        if c_docs:
            tot_r = r_idx
            ws.append([
                "TOTAL", "", "", f"{len(c_docs)} nota(s)", "", "",
                f"=SUM(G5:G{tot_r-1})", f"=SUM(H5:H{tot_r-1})", f"=SUM(I5:I{tot_r-1})",
                f"=SUM(J5:J{tot_r-1})", f"=SUM(K5:K{tot_r-1})", ""
            ])
            for col_i in range(1, 13):
                c_cell = ws.cell(row=tot_r, column=col_i)
                c_cell.fill = total_fill
                c_cell.font = bold_font
                if 7 <= col_i <= 11:
                    c_cell.number_format = currency_fmt

    # Ajuste automático de largura de colunas em todas as abas
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if val.startswith("="):
                    max_len = max(max_len, 14)
                else:
                    max_len = max(max_len, len(val))
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 45)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
