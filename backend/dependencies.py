"""
Dependências compartilhadas do FastAPI (autenticação, autorização).

Toda a API, com exceção de /api/auth/login, /health, / e /favicon.ico,
exige um token de sessão válido no header ``X-Session-Token``.

O token é gerado por :mod:`backend.routers.auth` ao fazer login e fica
armazenado em memória no dict ``_sessions``. Esta dependência apenas
valida que o token existe e não expirou.
"""
from __future__ import annotations


from fastapi import Depends, HTTPException, Request, status


def _get_sessions() -> dict:
    """Importação tardia para evitar ciclo: auth importa main indiretamente."""
    from backend.routers.auth import _sessions
    return _sessions


def require_session(request: Request) -> dict:
    """
    Valida o header ``X-Session-Token`` e devolve os dados da sessão.

    Verifica o cache em memória e o banco SQLite (para persistir pós-restart).
    Lança ``HTTP 401`` se o token estiver ausente, inválido ou expirado.
    """
    token = request.headers.get("X-Session-Token", "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão não informada. Faça login em /api/auth/login.",
        )

    from backend.routers.auth import get_session
    session = get_session(token)
    if not session:
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


class RateLimiter:
    """Rate limiter por endereço IP utilizando janela deslizante em memória."""

    def __init__(self, requests: int = 5, window_seconds: int = 60, action_name: str = "requisições"):
        self.max_requests = requests
        self.window_seconds = window_seconds
        self.action_name = action_name
        self._history: dict[str, list[float]] = {}

    def __call__(self, request: Request) -> None:
        import time
        now = time.time()
        # Identifica IP (considerando cabeçalho X-Forwarded-For caso haja proxy reverso)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "127.0.0.1"

        # Limpa entradas com mais de window_seconds
        cutoff = now - self.window_seconds
        timestamps = [t for t in self._history.get(ip, []) if t > cutoff]

        if len(timestamps) >= self.max_requests:
            oldest = timestamps[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Limite de {self.max_requests} {self.action_name} excedido. Tente novamente em {retry_after} segundos.",
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        self._history[ip] = timestamps


# Instâncias reutilizáveis de rate limit
login_rate_limiter = RateLimiter(requests=10, window_seconds=60, action_name="tentativas de login")
