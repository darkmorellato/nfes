import urllib.request
import json
import logging
from typing import Optional

from backend.database import add_notification, get_sync_state
from backend.services.crypto_service import decrypt_secret, is_encrypted

logger = logging.getLogger(__name__)


def _read_secret(key: str) -> str:
    """Lê um valor de sync_state, descriptografando se necessário.

    Suporta tanto valores já cifrados (escritos pelas rotas mais novas)
    quanto legados em texto puro (anteriores a este fix).
    """
    val = get_sync_state(key, "") or ""
    if not val:
        return ""
    if is_encrypted(val):
        try:
            return decrypt_secret(val)
        except Exception:
            # Se a chave Fernet tiver sido rotacionada, melhor falhar
            # silenciosamente do que vazar texto cifrado como se fosse o segredo.
            return ""
    return val


DEFAULT_WHATSAPP_NUMBERS = ["5519989354849", "5519990151809"]


def get_whatsapp_alert_numbers() -> list[str]:
    """Retorna os números configurados para receber alertas via WhatsApp."""
    custom_raw = _read_secret("whatsapp_alert_numbers")
    if custom_raw:
        nums = [n.strip().replace("+", "").replace("-", "").replace(" ", "") for n in custom_raw.split(",") if n.strip()]
        if nums:
            return nums
    return DEFAULT_WHATSAPP_NUMBERS


def gerar_link_whatsapp_alerta(phone: str, title: str, message: str, chave: Optional[str] = None) -> str:
    """Gera link formatado do WhatsApp Web para envio direto de alerta."""
    clean_phone = phone.strip().replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    txt = f"🚨 *{title}*\n\n{message}"
    if chave:
        txt += f"\n\n🔑 *Chave:* `{chave}`"
    import urllib.parse
    return f"https://api.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(txt)}"


def dispatch_notification(title: str, message: str, tipo: str = "info", chave: Optional[str] = None) -> bool:
    """Registra notificação local e envia via Webhook/Telegram/WhatsApp se configurado."""
    # 1. Registra no banco SQLite local
    add_notification(title, message, tipo=tipo, chave=chave)

    # 2. Envia para Webhook / Discord / Slack se configurado
    webhook_url = _read_secret("notification_webhook_url")
    if webhook_url and webhook_url.startswith("http"):
        try:
            payload = json.dumps({
                "title": f"🔔 {title}",
                "content": f"**{title}**\n{message}" + (f"\nChave: `{chave}`" if chave else ""),
                "tipo": tipo,
                "chave": chave,
            }).encode("utf-8")
            req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"Falha ao disparar webhook de notificação: {e}")

    # 3. Envia para Telegram se configurado
    bot_token = _read_secret("telegram_bot_token")
    chat_id = _read_secret("telegram_chat_id")
    if bot_token and chat_id:
        try:
            tg_text = f"🔔 *{title}*\n{message}" + (f"\n`{chave}`" if chave else "")
            tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = json.dumps({"chat_id": chat_id, "text": tg_text, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(tg_url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"Falha ao enviar notificação Telegram: {e}")

    return True

