"""
Dependências compartilhadas do FastAPI (autenticação, autorização).

Toda a API, com exceção de /api/auth/login, /health, / e /favicon.ico,
exige um token de sessão válido no header ``X-Session-Token``.

O token é gerado por :mod:`backend.routers.auth` ao fazer login e fica
armazenado em memória no dict ``_sessions``. Esta dependência apenas
valida que o token existe e não expirou.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status


def _get_sessions() -> dict:
    """Importação tardia para evitar ciclo: auth importa main indiretamente."""
    from backend.routers.auth import _sessions
    return _sessions


def require_session(request: Request) -> dict:
    """
    Valida o header ``X-Session-Token`` e devolve os dados da sessão.

    Lança ``HTTP 401`` se o token estiver ausente, inválido ou expirado.
    """
    token = request.headers.get("X-Session-Token", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não informada. Faça login em /api/auth/login.",
        )

    sessions = _get_sessions()
    session = sessions.get(token)
    if not session or session.get("expires_at", datetime.min) < datetime.now():
        # Limpa o token expirado do dict para não acumular lixo.
        sessions.pop(token, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Faça login novamente.",
        )
    return session


def require_admin(session: dict = Depends(require_session)) -> dict:
    """
    Exige perfil ``admin`` na sessão autenticada.

    Use em endpoints sensíveis como exclusão de certificado, mudança de
    configuração, sync forçado e download de pacotes contábeis.
    """
    if session.get("perfil") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operação restrita ao perfil administrador.",
        )
    return session
