import urllib.request
import json
import logging
from typing import Optional, Dict, Any

from backend.database import add_notification, get_sync_state

logger = logging.getLogger(__name__)


def dispatch_notification(title: str, message: str, tipo: str = "info", chave: Optional[str] = None) -> bool:
    """Registra notificação local e envia via Webhook/Telegram se configurado."""
    # 1. Registra no banco SQLite local
    add_notification(title, message, tipo=tipo, chave=chave)

    # 2. Envia para Webhook / Discord / Slack se configurado
    webhook_url = get_sync_state("notification_webhook_url", "")
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
    bot_token = get_sync_state("telegram_bot_token", "")
    chat_id = get_sync_state("telegram_chat_id", "")
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
