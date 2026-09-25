"""
Dependências compartilhadas do FastAPI (autenticação, autorização).

Toda a API, com exceção de ``/api/auth/login``, ``/health``, ``/`` e
``/favicon.ico``, exige um token de sessão válido no header ``X-Session-Token``.

Segredos de implementação (por que as coisas são assim):

* **Só header, nunca query string.** O token também era aceito em ``?token=``,
  o que o vazava em logs de proxy, histórico do navegador e cabeçalho
  ``Referer``. Downloads usam ``apiDownload``, que já envia o header.
* **Sem passe de IP.** Havia um ramo que concedia sessão falsa a qualquer
  host ``127.0.0.1``/``192.168.x``/``10.x``/``172.x`` sem token — com bind em
  ``0.0.0.0``, qualquer máquina da LAN baixava o ``.db`` inteiro (hashes de
  senha, tokens e senhas de certificado). A sincronização P2P agora usa o
  segredo compartilhado ``X-Sync-Token`` (:data:`settings.SYNC_TOKEN`).
* **Rate limit por IP real.** ``X-Forwarded-For`` só é considerado quando
  ``TRUST_PROXY=true`` (proxy reverso configurado); sem isso qualquer cliente
  forjava o header e zera o limite de força bruta do login.
"""
from __future__ import annotations


import hmac
import time
from fastapi import Depends, HTTPException, Request, status

from backend.config import settings


def _get_sessions() -> dict:
    """Importação tardia para evitar ciclo: auth importa main indiretamente."""
    from backend.routers.auth import _sessions
    return _sessions


def _token_da_requisicao(request: Request) -> str:
    """Token de sessão — exclusivamente do header ``X-Session-Token``."""
    return request.headers.get("X-Session-Token", "").strip()


def _sessao_do_token(token: str) -> dict | None:
    from backend.routers.auth import get_session
    return get_session(token)


def _unauthorized(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_session(request: Request) -> dict:
    """
    Valida o header ``X-Session-Token`` e devolve os dados da sessão.

    Verifica o cache em memória e o banco SQLite (para persistir pós-restart).
    Lança ``HTTP 401`` se o token estiver ausente, inválido ou expirado.
    """
    token = _token_da_requisicao(request)
    if not token:
        raise _unauthorized(
            "Sessão não informada. Faça login e envie o header X-Session-Token."
        )

    session = _sessao_do_token(token)
    if not session:
        raise _unauthorized("Sessão inválida ou expirada. Faça login novamente.")
    return session


def require_session_ou_sync(request: Request) -> dict:
    """
    Sessão válida **ou** ``X-Sync-Token`` conferindo com o segredo da instalação.

    Usado apenas nas rotas de sincronização P2P (``/api/gestao/rede/*``), em que
    uma máquina da LAN chama a outra sem que o operador tenha login na máquina
    de destino. O token é opaco, gerado por instalação e comparado em tempo
    constante.
    """
    session = None
    token = _token_da_requisicao(request)
    if token:
        session = _sessao_do_token(token)
        if session:
            return session

    sync = request.headers.get("X-Sync-Token", "").strip()
    if sync and hmac.compare_digest(sync, settings.SYNC_TOKEN):
        return {
            "username": "sincronizacao_p2p",
            "nome": "Sincronização de rede",
            "perfil": "operador",
            "origem": "sync_token",
        }

    if token:
        raise _unauthorized("Sessão inválida ou expirada. Faça login novamente.")
    raise _unauthorized(
        "Autenticação necessária: envie X-Session-Token ou X-Sync-Token válido."
    )


def require_admin(session: dict = Depends(require_session)) -> dict:
    """
    Exige perfil ``admin`` na sessão autenticada.

    Use em endpoints sensíveis: exclusão de certificado, limpeza de base,
    atualização/reinicio do sistema, download de banco e de backups fiscais.
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

    def _ip_real(self, request: Request) -> str:
        # X-Forwarded-For só vale atrás de um proxy de confiança; caso contrário
        # é simplesmente um header que o próprio cliente controla.
        if settings.TRUST_PROXY:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "0.0.0.0"

    def __call__(self, request: Request) -> None:
        now = time.time()

        # Poda periódica: sem ela o dicionário cresce para cada IP que já
        # bateu no limite e nunca mais volta (DoS por memória).
        if len(self._history) > 512:
            self.limpar()

        ip = self._ip_real(request)

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

    def limpar(self) -> int:
        """Poda entradas expiradas — evita crescimento ilimitado de memória."""
        cutoff = time.time() - self.window_seconds
        expirados = [ip for ip, ts in list(self._history.items()) if not ts or max(ts) < cutoff]
        for ip in expirados:
            del self._history[ip]
        return len(expirados)


# Instâncias reutilizáveis de rate limit
login_rate_limiter = RateLimiter(requests=10, window_seconds=60, action_name="tentativas de login")
credencial_rate_limiter = RateLimiter(requests=5, window_seconds=300, action_name="alterações de credencial")
sefaz_rate_limiter = RateLimiter(requests=30, window_seconds=60, action_name="consultas à SEFAZ")
