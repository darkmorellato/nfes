import io
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from backend.database import get_nfe_detail, get_db_connection
from backend.config import settings


def generate_dacce_pdf(chave: str, n_seq: int = 1) -> io.BytesIO:
    """Gera o Documento Auxiliar da Carta de Correção Eletrônica (DACCE) oficial em PDF.

    Levanta ValueError se o evento de CC-e (110110) não estiver registrado no banco,
    pois o DACCE sem protocolo real da SEFAZ não tem validade fiscal.
    """
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    doc = get_nfe_detail(chave_clean) or {}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM nfe_events WHERE chave = ? AND tipo_evento = '110110' ORDER BY n_seq DESC LIMIT 1",
            (chave_clean,),
        )
        evento = cursor.fetchone()

    if not evento:
        raise ValueError(
            f"Evento de CC-e (110110) não encontrado para a chave {chave_clean}. "
            "A Carta de Correção deve estar registrada na SEFAZ antes de gerar o DACCE."
        )

    justificativa = evento["x_motivo"]
    protocolo = evento["protocolo"]
    dh_evento = evento["dh_evento"]

    buf = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buf, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=13, alignment=1, textColor=colors.HexColor("#1B4F72"), fontName="Helvetica-Bold")
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=8, alignment=1, textColor=colors.HexColor("#555555"))
    header_style = ParagraphStyle("Header", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=colors.white)
    normal_bold = ParagraphStyle("NormalBold", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold")
    normal_text = ParagraphStyle("NormalText", parent=styles["Normal"], fontSize=9)

    elements = []

    # Cabeçalho
    elements.append(Paragraph("DACCE - DOCUMENTO AUXILIAR DA CARTA DE CORREÇÃO ELETRÔNICA", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Não possui valor fiscal como documento de circulação. Comprovante de retificação homologado pela SEFAZ.", sub_style))
    elements.append(Spacer(1, 12))

    # Tabela 1: Identificação da NF-e
    data_nfe = [
        [Paragraph("IDENTIFICAÇÃO DA NOTA FISCAL ELETRÔNICA", header_style), ""],
        [Paragraph("<b>Chave de Acesso:</b>", normal_bold), Paragraph(chave_clean, normal_text)],
        [Paragraph("<b>Número / Série:</b>", normal_bold), Paragraph(f"{doc.get('numero', '—')} / Série {doc.get('serie', '1')}", normal_text)],
        [Paragraph("<b>Data de Emissão NF-e:</b>", normal_bold), Paragraph(str(doc.get("data_emissao", "—"))[:19].replace("T", " "), normal_text)],
        [Paragraph("<b>Emitente:</b>", normal_bold), Paragraph(f"{doc.get('emitente_nome', '—')} ({doc.get('emitente_cnpj', '')})", normal_text)],
        [Paragraph("<b>Destinatário:</b>", normal_bold), Paragraph(f"{doc.get('destinatario_nome', '—')} ({doc.get('destinatario_cnpj', '')})", normal_text)],
    ]
    t1 = Table(data_nfe, colWidths=[150, 390])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#1B4F72")),
        ('SPAN', (0, 0), (1, 0)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t1)
    elements.append(Spacer(1, 10))

    # Tabela 2: Dados da CC-e
    data_cce = [
        [Paragraph("DADOS DO EVENTO - CARTA DE CORREÇÃO (CC-e)", header_style), ""],
        [Paragraph("<b>Órgão Receptor:</b>", normal_bold), Paragraph(f"SEFAZ {doc.get('emitente_uf', 'SP')}", normal_text)],
        [Paragraph("<b>Ambiente:</b>", normal_bold), Paragraph("Produção (1)" if not settings.HOMOLOGACAO else "Homologação (2)", normal_text)],
        [Paragraph("<b>Sequencial do Evento:</b>", normal_bold), Paragraph(f"nSeqEvento = {n_seq}", normal_text)],
        [Paragraph("<b>Protocolo de Homologação:</b>", normal_bold), Paragraph(f"<b>{protocolo}</b> (Status 135 - Evento Registrado e Vinculado a NF-e)", normal_text)],
        [Paragraph("<b>Data/Hora do Registro:</b>", normal_bold), Paragraph(str(dh_evento)[:19].replace("T", " "), normal_text)],
    ]
    t2 = Table(data_cce, colWidths=[150, 390])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#2874A6")),
        ('SPAN', (0, 0), (1, 0)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 10))

    # Tabela 3: Texto da Correção
    data_corr = [
        [Paragraph("CORREÇÕES APLICADAS (TEXTO RETIFICADOR)", header_style)],
        [Paragraph("<b>Condições de Uso:</b> A Carta de Correção é disciplinada pelo § 1º-A do art. 7º do Convênio S/N, de 15 de dezembro de 1970 e pode ser utilizada para regularização de erro ocorrido na emissão de documento fiscal, desde que o erro não esteja relacionado com: I - as variáveis que determinam o valor do imposto; II - a correção de dados cadastrais que implique mudança do remetente ou do destinatário; III - a data de emissão ou de saída.", normal_text)],
        [Paragraph(f"<b>Texto da Retificação:</b><br/><br/><b>{justificativa}</b>", normal_text)],
    ]
    t3 = Table(data_corr, colWidths=[540])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#117A65")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t3)

    doc_pdf.build(elements)
    buf.seek(0)
    return buf
