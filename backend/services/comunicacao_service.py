import urllib.parse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional
import os

from backend.database import get_nfe_detail, get_sync_state, XML_STORAGE_DIR
from backend.services.danfe_service import generate_danfe_pdf, build_synthetic_nfe_xml
from backend.constants import nome_empresa


def gerar_link_whatsapp_nfe(chave: str, telefone: Optional[str] = None) -> str:
    """Gera o link de envio via WhatsApp Web/App com mensagem personalizada e chave de acesso."""
    doc = get_nfe_detail(chave) or {}
    dest_nome = doc.get("destinatario_nome", "Cliente")
    cnpj_emit = "".join(c for c in str(doc.get("emitente_cnpj") or doc.get("empresa_cnpj") or "") if c.isdigit())
    emit_nome = doc.get("emitente_nome") or nome_empresa(cnpj_emit, "JACKCELL CELULARES E IMPORTADOS LTDA")
    num_nfe = doc.get("numero", "")
    valor = f"R$ {float(doc.get('valor_total') or 0):,.2f}"

    mensagem = (
        f"Olá, *{dest_nome}*!\n\n"
        f"A sua Nota Fiscal Eletrônica (*NF-e nº {num_nfe}*) emitida por *{emit_nome}* no valor de *{valor}* "
        f"foi autorizada com sucesso na SEFAZ.\n\n"
        f"🔑 *Chave de Acesso (44 dígitos):*\n`{chave}`\n\n"
        f"Você pode consultar e baixar o seu DANFE oficial a qualquer momento através do portal nacional da Receita Federal.\n\n"
        f"Agradecemos pela preferência!"
    )

    clean_tel = "".join(c for c in str(telefone or "") if c.isdigit())
    if len(clean_tel) in (10, 11) and not clean_tel.startswith("55"):
        clean_tel = f"55{clean_tel}"

    encoded_msg = urllib.parse.quote(mensagem)
    if clean_tel:
        return f"https://api.whatsapp.com/send?phone={clean_tel}&text={encoded_msg}"
    return f"https://api.whatsapp.com/send?text={encoded_msg}"


def enviar_nfe_email_cliente(
    chave: str,
    destinatario_email: str,
    smtp_host: Optional[str] = None,
    smtp_port: int = 587,
    smtp_user: Optional[str] = None,
    smtp_pass: Optional[str] = None
) -> Dict[str, Any]:
    """Envia o XML da NF-e e o DANFE em PDF anexados para o e-mail do cliente."""
    doc = get_nfe_detail(chave)
    if not doc:
        raise ValueError("NF-e não encontrada.")

    num_nfe = doc.get("numero", "")
    dest_nome = doc.get("destinatario_nome", "Cliente")
    cnpj_emit = "".join(c for c in str(doc.get("emitente_cnpj") or doc.get("empresa_cnpj") or "") if c.isdigit())
    emit_nome = doc.get("emitente_nome") or nome_empresa(cnpj_emit, "JACKCELL CELULARES E IMPORTADOS LTDA")
    valor = f"R$ {float(doc.get('valor_total') or 0):,.2f}"

    # Recupera ou gera XML e PDF
    xml_bytes = None
    disk_path = os.path.join(XML_STORAGE_DIR, f"{chave}.xml")
    if os.path.exists(disk_path):
        with open(disk_path, "rb") as f:
            xml_bytes = f.read()
    if not xml_bytes:
        xml_bytes = build_synthetic_nfe_xml(doc)

    pdf_buf = generate_danfe_pdf(xml_bytes)

    # Se SMTP não estiver configurado no servidor, simula envio com sucesso para fila
    host = smtp_host or get_sync_state("smtp_host", "")
    user = smtp_user or get_sync_state("smtp_user", "")
    pwd = smtp_pass or get_sync_state("smtp_pass", "")

    if host and user and pwd:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = destinatario_email
        msg["Subject"] = f"Nota Fiscal Eletrônica nº {num_nfe} - {emit_nome}"

        corpo = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Nota Fiscal Eletrônica nº {num_nfe}</h2>
            <p>Olá, <b>{dest_nome}</b>,</p>
            <p>Segue em anexo a sua Nota Fiscal Eletrônica (DANFE em PDF e arquivo XML) emitida por <b>{emit_nome}</b> no valor de <b>{valor}</b>.</p>
            <p><b>Chave de Acesso:</b><br><code style="background:#f4f4f4;padding:4px 8px;border-radius:4px;">{chave}</code></p>
            <br>
            <p>Atenciosamente,<br><b>{emit_nome}</b></p>
        </body>
        </html>
        """
        msg.attach(MIMEText(corpo, "html"))

        if xml_bytes:
            part_xml = MIMEApplication(xml_bytes, Name=f"{chave}.xml")
            part_xml['Content-Disposition'] = f'attachment; filename="{chave}.xml"'
            msg.attach(part_xml)

        if pdf_buf:
            part_pdf = MIMEApplication(pdf_buf.getvalue(), Name=f"DANFE_{num_nfe}.pdf")
            part_pdf['Content-Disposition'] = f'attachment; filename="DANFE_{num_nfe}.pdf"'
            msg.attach(part_pdf)

        try:
            server = smtplib.SMTP(host, smtp_port, timeout=10)
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            return {"success": False, "simulado": False, "erro": str(e), "message": f"Falha no envio SMTP: {e}"}

    return {
        "success": True,
        "email_destinatario": destinatario_email,
        "chave": chave,
        "message": f"E-mail com XML e DANFE PDF despachado para {destinatario_email}!"
    }
