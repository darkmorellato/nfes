from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection

def add_notification(title: str, message: str, tipo: str = "info", chave: Optional[str] = None) -> int:
    """Registra uma notificação de evento fiscal no banco de dados com prevenção ativa de duplicidade."""
    now = datetime.now().isoformat()
    chave_clean = "".join(c for c in str(chave or "") if c.isdigit())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Se houver chave (44 dígitos), verifica se já existe uma notificação para a mesma chave
        if chave_clean and len(chave_clean) == 44:
            cursor.execute("SELECT id, title, message FROM notifications WHERE chave = ? ORDER BY id DESC LIMIT 1", (chave_clean,))
            row = cursor.fetchone()
            if row:
                # Atualiza com a notificação mais recente/detalhada sem gerar card duplicado
                cursor.execute("""
                    UPDATE notifications
                    SET title = ?, message = ?, tipo = ?, created_at = ?
                    WHERE id = ?
                """, (title, message, tipo, now, row["id"]))
                conn.commit()
                return row["id"]

        cursor.execute("""
            INSERT INTO notifications (title, message, tipo, chave, read, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (title, message, tipo, chave_clean if chave_clean else (chave or ""), now))
        conn.commit()
        return cursor.lastrowid

def list_notifications(limit: int = 30, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Lista as notificações recentes únicas registradas pelo robô de sincronização."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        unread_cond = "WHERE read = 0" if unread_only else ""

        # Garante deduplicação por chave única mantendo a notificação mais recente
        query = f"""
            SELECT * FROM notifications
            WHERE id IN (
                SELECT MAX(id) FROM notifications
                {unread_cond}
                GROUP BY (CASE WHEN chave != '' AND chave IS NOT NULL THEN chave ELSE CAST(id AS TEXT) END)
            )
            ORDER BY created_at DESC LIMIT ?
        """
        cursor.execute(query, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def mark_notifications_read() -> bool:
    """Marca todas as notificações pendentes como lidas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        conn.commit()
        return True


# ====================================================================
# AUDITOR DE PREÇOS & ALERTA DE VARIAÇÃO DE CUSTOS
# ====================================================================
