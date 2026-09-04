"""
Serviço de Trilha de Auditoria Imutável (Audit Trail).

Garante conformidade com a LGPD (Lei 13.709/2018) e com as normas do SPED / SEFAZ,
registrando quem executou qual ação, em qual documento fiscal, a partir de qual IP
e em qual data/hora.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import Request

from backend.database import get_db_connection

logger = logging.getLogger("nfe.audit")


def record_audit(
    acao: str,
    entidade: str,
    entidade_id: Optional[str] = None,
    usuario_email: Optional[str] = None,
    usuario_nome: Optional[str] = None,
    ip: Optional[str] = None,
    detalhe: Optional[str] = None,
    status: str = "SUCESSO",
    request: Optional[Request] = None,
) -> bool:
    """Registra uma entrada imutável na trilha de auditoria."""
    now = datetime.now().isoformat()

    # Se uma request FastAPI foi informada, extrai IP e dados de sessão automaticamente
    resolved_ip = ip
    resolved_email = usuario_email
    resolved_nome = usuario_nome

    if request is not None:
        if not resolved_ip:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                resolved_ip = forwarded.split(",")[0].strip()
            else:
                resolved_ip = request.client.host if request.client else "127.0.0.1"

        if not resolved_email:
            token = request.headers.get("X-Session-Token", "").strip()
            if token:
                try:
                    from backend.routers.auth import get_session
                    sess = get_session(token)
                    if sess:
                        resolved_email = sess.get("email")
                        resolved_nome = sess.get("nome")
                except Exception:
                    pass

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (
                    timestamp, usuario_email, usuario_nome, acao, entidade, entidade_id, ip, detalhe, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now,
                resolved_email or "SISTEMA",
                resolved_nome or "Sistema Automático",
                acao,
                entidade,
                entidade_id or "",
                resolved_ip or "127.0.0.1",
                detalhe or "",
                status,
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"[Audit] Falha ao registrar log de auditoria ({acao}/{entidade}): {e}")
        return False


def list_audit_logs(
    acao: Optional[str] = None,
    entidade: Optional[str] = None,
    usuario_email: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Consulta os registros de auditoria com paginação e filtros."""
    offset = max(0, (page - 1) * limit)
    conditions = []
    params: List[Any] = []

    if acao:
        conditions.append("acao = ?")
        params.append(acao)

    if entidade:
        conditions.append("entidade = ?")
        params.append(entidade)

    if usuario_email:
        conditions.append("usuario_email LIKE ?")
        params.append(f"%{usuario_email}%")

    if data_inicio:
        conditions.append("timestamp >= ?")
        params.append(data_inicio)

    if data_fim:
        conditions.append("timestamp <= ?")
        params.append(data_fim + "T23:59:59")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) as total FROM audit_logs {where_clause}", params)
        r = cursor.fetchone()
        total = r["total"] if r else 0

        cursor.execute(f"""
            SELECT id, timestamp, usuario_email, usuario_nome, acao, entidade, entidade_id, ip, detalhe, status
            FROM audit_logs
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        rows = [dict(row) for row in cursor.fetchall()]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "logs": rows,
    }
