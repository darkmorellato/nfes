import io
import os
import tempfile
from typing import Optional
from datetime import datetime, timedelta

import matplotlib

# Meses abreviados em pt-BR para rótulos de gráficos e relatórios.
_MESES_PT_BR = ["jan", "fev", "mar", "abr", "mai", "jun",
                "jul", "ago", "set", "out", "nov", "dez"]


def _fmt_mes_br(iso_ou_yyyy_mm: str) -> str:
    """Converte 'YYYY-MM' (ou ISO completo) em 'mmm/aaaa' (pt-BR).

    Usado para rótulos do eixo X de gráficos de relatório.
    """
    if not iso_ou_yyyy_mm:
        return "—"
    s = str(iso_ou_yyyy_mm)
    if len(s) < 7 or s[4] != "-":
        return s
    y, m = s[0:4], s[5:7]
    try:
        return f"{_MESES_PT_BR[int(m) - 1]}/{y}"
    except (ValueError, IndexError):
        return s
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patheffects
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.config import settings
from backend.database import (
    get_db_connection,
    get_analytics_dashboard,
    get_price_divergences,
    get_auditoria_fornecedores,
    get_dre_tendencia,
)


def _register_fonts():
    try:
        pdfmetrics.registerFont(TTFont('Helvetica', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('Helvetica-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
    except Exception:
        pass


def _create_temp_image(fig) -> str:
    temp_dir = tempfile.gettempdir()
    filename = f"report_chart_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
    filepath = os.path.join(temp_dir, filename)
    fig.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return filepath


def _generate_status_data(periodo_dias: int):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT situacao, COUNT(*) as cnt FROM nfe_docs "
            "WHERE data_emissao >= ? AND data_emissao <= ? "
            "GROUP BY situacao ORDER BY cnt DESC",
            (start_str, end_str + "T23:59:59"),
        )
        rows = cursor.fetchall()

    status_labels = []
    status_counts = []
    for row in rows:
        status_labels.append(row["situacao"] or "Sem status")
        status_counts.append(row["cnt"])

    if not status_labels:
        status_labels = ['Autorizado', 'Cancelado', 'Rejeitado', 'Em Processamento', 'Denegado']
        status_counts = [0, 0, 0, 0, 0]

    total = sum(status_counts)
    status_percentages = [
        round((count / total) * 100, 1) if total > 0 else 0
        for count in status_counts
    ]

    return {
        'periodo': f"{start_str} a {end_str}",
        'total': total,
        'status': list(zip(status_labels, status_counts, status_percentages))
    }


def _generate_monthly_data(meses: int):
    end_date = datetime.now()
    months = []
    month_prefixes = []
    for i in range(meses - 1, -1, -1):
        d = end_date - timedelta(days=30 * i)
        months.append(_fmt_mes_br(d.strftime('%Y-%m')))
        month_prefixes.append(d.strftime('%Y-%m'))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in month_prefixes)
        cursor.execute(
            f"SELECT substr(data_emissao, 1, 7) as mes, COUNT(*) as cnt "
            f"FROM nfe_docs WHERE substr(data_emissao, 1, 7) IN ({placeholders}) "
            f"GROUP BY mes ORDER BY mes",
            month_prefixes,
        )
        rows = cursor.fetchall()
        counts_map = {r["mes"]: r["cnt"] for r in rows}

    values = [counts_map.get(mp, 0) for mp in month_prefixes]
    return {'meses': months, 'valores': values}


def _generate_compliance_data(periodo_dias: int):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM nfe_docs WHERE data_emissao >= ? AND data_emissao <= ?",
            (start_str, end_str + "T23:59:59"),
        )
        total_docs = cursor.fetchone()["cnt"]

    divergencias = get_price_divergences(limit=200)
    docs_con_divergencia = len(divergencias)

    audit = get_auditoria_fornecedores()
    docs_conformes = max(0, total_docs - docs_con_divergencia)
    docs_pendentes = 0
    taxa_conformidade = round((docs_conformes / total_docs) * 100, 2) if total_docs > 0 else 100

    return {
        'periodo': f"{start_str} a {end_str}",
        'total_documentos': total_docs,
        'documentos_conformes': docs_conformes,
        'documentos_pendentes': docs_pendentes,
        'taxa_conformidade': taxa_conformidade,
        'divergencias': docs_con_divergencia,
        'alertas': docs_con_divergencia
    }


def _generate_emitter_data(periodo_dias: int):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=periodo_dias)

    dash = get_analytics_dashboard(mes=end_date.month, ano=end_date.year)
    top_fornecedores = dash.get('top_fornecedores', [])[:5]

    result = []
    for f in top_fornecedores:
        result.append({
            'razao_social': f.get('emitente_nome', '—'),
            'cnpj': f.get('emitente_cnpj', ''),
            'quantidade': f.get('qtd_notas', 0),
            'percentual': 0
        })

    total_value = sum(e['quantidade'] for e in result)
    for e in result:
        e['percentual'] = round((e['quantidade'] / total_value) * 100, 2) if total_value > 0 else 0

    return {
        'periodo': f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
        'emissores': result,
        'total_emissores': len(result),
        'total_documentos': total_value
    }


def _build_status_chart(data) -> str:
    labels = [s[0] for s in data['status']]
    sizes = [s[1] for s in data['status']]
    colors_pie = ['#2ecc71', '#e74c3c', '#f39c12', '#3498db', '#9b59b6']

    fig, ax = plt.subplots(figsize=(6, 4))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors_pie, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 9}
    )
    ax.set_title('Distribuição de Status de Documentos Fiscais', fontsize=11, fontweight='bold')
    plt.tight_layout()
    return _create_temp_image(fig)


def _build_monthly_chart(data) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(data['meses'], data['valores'], color='#007a55')
    ax.set_title('Volume de Documentos por Mês', fontsize=11, fontweight='bold')
    ax.set_ylabel('Quantidade', fontsize=9)
    ax.set_xlabel('Mês/Ano', fontsize=9)
    ax.tick_params(axis='x', rotation=45, labelsize=8)
    ax.tick_params(axis='y', labelsize=8)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    return _create_temp_image(fig)


def _make_title_style(styles):
    return ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#007a55'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )


def _make_heading_style(styles):
    return ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#007a55'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )


def _make_body_style(styles):
    return ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        alignment=TA_LEFT
    )


def _make_table_style():
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007a55')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
    ])


def generate_invoice_status_report(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = 30
) -> io.BytesIO:
    data = _generate_status_data(periodo_dias)
    chart_path = _build_status_chart(data)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = _make_title_style(styles)
    heading_style = _make_heading_style(styles)
    body_style = _make_body_style(styles)

    story = []
    story.append(Paragraph("Relatório de Status de Documentos Fiscais", title_style))
    story.append(Paragraph(f"Período: {data['periodo']}", body_style))
    story.append(Paragraph(f"UF: {(uf or settings.DEFAULT_UF).upper()} | Ambiente: {'Homologação' if homologacao else 'Produção'}", body_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"<b>Total de Documentos:</b> {data['total']}", body_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Distribuição por Status", heading_style))
    table_data = [['Status', 'Quantidade', 'Percentual']]
    for status, count, pct in data['status']:
        table_data.append([status, str(count), f"{pct}%"])

    table = Table(table_data, colWidths=[8*cm, 4*cm, 4*cm])
    table.setStyle(_make_table_style())
    story.append(table)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Gráfico de Distribuição", heading_style))
    story.append(Image(chart_path, width=14*cm, height=9.33*cm))
    story.append(PageBreak())

    try:
        doc.build(story)
        buffer.seek(0)
        return buffer
    finally:
        if os.path.exists(chart_path):
            try:
                os.remove(chart_path)
            except OSError:
                pass


def generate_monthly_volume_report(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    meses: int = 6
) -> io.BytesIO:
    data = _generate_monthly_data(meses)
    chart_path = _build_monthly_chart(data)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = _make_title_style(styles)
    heading_style = _make_heading_style(styles)
    body_style = _make_body_style(styles)

    story = []
    story.append(Paragraph("Relatório de Volume Mensal de Documentos", title_style))
    story.append(Paragraph(f"Período: {meses} meses", body_style))
    story.append(Paragraph(f"UF: {(uf or settings.DEFAULT_UF).upper()} | Ambiente: {'Homologação' if homologacao else 'Produção'}", body_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Volume por Mês", heading_style))
    table_data = [['Mês/Ano', 'Quantidade']]
    for mes, valor in zip(data['meses'], data['valores']):
        table_data.append([mes, str(valor)])

    table = Table(table_data, colWidths=[8*cm, 8*cm])
    table.setStyle(_make_table_style())
    story.append(table)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Gráfico de Volume Mensal", heading_style))
    story.append(Image(chart_path, width=14*cm, height=9.33*cm))
    story.append(PageBreak())

    try:
        doc.build(story)
        buffer.seek(0)
        return buffer
    finally:
        if os.path.exists(chart_path):
            try:
                os.remove(chart_path)
            except OSError:
                pass


def generate_compliance_report(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = 30
) -> io.BytesIO:
    data = _generate_compliance_data(periodo_dias)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = _make_title_style(styles)
    heading_style = _make_heading_style(styles)
    body_style = _make_body_style(styles)

    story = []
    story.append(Paragraph("Relatório de Conformidade Fiscal", title_style))
    story.append(Paragraph(f"Período: {data['periodo']}", body_style))
    story.append(Paragraph(f"UF: {(uf or settings.DEFAULT_UF).upper()} | Ambiente: {'Homologação' if homologacao else 'Produção'}", body_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Métricas de Conformidade", heading_style))
    metrics = [
        ['Métrica', 'Valor'],
        ['Total de Documentos', str(data['total_documentos'])],
        ['Documentos Conformes', str(data['documentos_conformes'])],
        ['Documentos Pendentes', str(data['documentos_pendentes'])],
        ['Taxa de Conformidade', f"{data['taxa_conformidade']}%"],
        ['Divergências', str(data['divergencias'])],
        ['Alertas', str(data['alertas'])]
    ]

    table = Table(metrics, colWidths=[8*cm, 8*cm])
    table.setStyle(_make_table_style())
    story.append(table)
    story.append(Spacer(1, 0.5*cm))

    if data['taxa_conformidade'] >= 95:
        status_text = "Excelente"
        status_color = colors.HexColor('#2ecc71')
    elif data['taxa_conformidade'] >= 85:
        status_text = "Bom"
        status_color = colors.HexColor('#f39c12')
    else:
        status_text = "Atenção"
        status_color = colors.HexColor('#e74c3c')

    story.append(Paragraph(f"Status Geral: <b>{status_text}</b> (Taxa de Conformidade: {data['taxa_conformidade']}%)", body_style))
    story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_emitter_report(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = 30
) -> io.BytesIO:
    data = _generate_emitter_data(periodo_dias)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = _make_title_style(styles)
    heading_style = _make_heading_style(styles)
    body_style = _make_body_style(styles)

    story = []
    story.append(Paragraph("Relatório de Emissores de Documentos Fiscais", title_style))
    story.append(Paragraph(f"Período: {data['periodo']}", body_style))
    story.append(Paragraph(f"UF: {(uf or settings.DEFAULT_UF).upper()} | Ambiente: {'Homologação' if homologacao else 'Produção'}", body_style))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Top Emissores", heading_style))
    table_data = [['Razão Social', 'CNPJ', 'Quantidade', 'Percentual']]
    for emitter in data['emissores']:
        table_data.append([
            emitter['razao_social'],
            emitter['cnpj'],
            str(emitter['quantidade']),
            f"{emitter['percentual']}%"
        ])

    table = Table(table_data, colWidths=[6*cm, 5*cm, 3*cm, 3*cm])
    table.setStyle(_make_table_style())
    story.append(table)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"<b>Total de Emissores:</b> {data['total_emissores']}", body_style))
    story.append(Paragraph(f"<b>Total de Documentos:</b> {data['total_documentos']}", body_style))
    story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer
