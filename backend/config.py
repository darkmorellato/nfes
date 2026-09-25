import os
import secrets
import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _xdg_data_root() -> str:
    return os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")


def _resolve_data_dir() -> str:
    env = os.environ.get("NFE_DATA_DIR")
    if env:
        return os.path.abspath(env)
    repo_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    if os.path.isdir(repo_data):
        return repo_data
    return os.path.join(_xdg_data_root(), "nfe-manager", "data")


def _resolve_cert_dir() -> str:
    env = os.environ.get("NFE_CERT_DIR")
    if env:
        return os.path.abspath(env)
    return os.path.join(_xdg_data_root(), "nfe-manager", "certs")


def _default_secret_key() -> str:
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    # Persiste uma chave gerada uma vez no data dir para não quebrar a
    # descriptografia Fernet de senhas de certificado entre execuções.
    key_file = os.path.join(_resolve_data_dir(), ".secret_key")
    try:
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                content = f.read().strip()
                if content:
                    return content
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        generated = secrets.token_urlsafe(48)
        with open(key_file, "w") as f:
            f.write(generated)
        os.chmod(key_file, 0o600)
        return generated
    except Exception:
        logger.warning(
            "SECRET_KEY não definida e não foi possível persistir. Usando chave aleatória por execução."
        )
        return secrets.token_urlsafe(48)


def _default_debug() -> bool:
    return os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes", "on")


def _trust_proxy() -> bool:
    """Só confie em ``X-Forwarded-For`` quando houver um proxy reverso de verdade.

    Com ``False`` (padrão) o header é ignorado: qualquer cliente da LAN poderia
    forjar o IP e burlar o rate limit de força bruta do login.
    """
    return os.environ.get("TRUST_PROXY", "False").lower() in ("1", "true", "yes", "on")


def _default_sync_token() -> str:
    """Segredo compartilhado para a sincronização P2P entre máquinas.

    Substitui o antigo "bypass por IP": qualquer host da rede passava pela
    autenticação sem token e conseguia baixar o banco inteiro. Agora a troca de
    dados exige este token (``X-Sync-Token``), gerado por instalação e gravado
    com permissão ``0600``.
    """
    env = os.environ.get("NFE_SYNC_TOKEN")
    if env:
        return env
    token_file = os.path.join(_resolve_data_dir(), ".sync_token")
    try:
        if os.path.exists(token_file):
            with open(token_file, "r") as f:
                content = f.read().strip()
                if content:
                    return content
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        generated = secrets.token_urlsafe(32)
        with open(token_file, "w") as f:
            f.write(generated)
        os.chmod(token_file, 0o600)
        return generated
    except Exception:
        logger.warning(
            "NFE_SYNC_TOKEN não definido e não foi possível persistir. "
            "Usando token aleatório por execução (a sincronização em rede falhará entre reinícios)."
        )
        return secrets.token_urlsafe(32)


def _default_origins() -> str:
    return os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
    )


class Settings(BaseSettings):
    APP_NAME: str = "NFE Manager"
    DEBUG: bool = _default_debug()
    SECRET_KEY: str = _default_secret_key()
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CERT_DIR: str = _resolve_cert_dir()
    DATA_DIR: str = _resolve_data_dir()
    PORT: int = int(os.environ.get("NFE_PORT", "8000"))
    HOST: str = os.environ.get("NFE_HOST", "0.0.0.0")
    HOMOLOGACAO: bool = True
    DEFAULT_UF: str = "SP"
    TIMEOUT: int = 60
    ALLOWED_ORIGINS: str = _default_origins()
    TRUST_PROXY: bool = _trust_proxy()
    SYNC_TOKEN: str = _default_sync_token()
    # Verificação TLS dos WS da SEFAZ (ver backend/services/tls_sefaz.py)
    SEFAZ_VERIFY_TLS: bool = (
        os.environ.get("SEFAZ_VERIFY_TLS", "True").lower() in ("1", "true", "yes", "on")
    )
    SEFAZ_CA_BUNDLE: str = os.environ.get("SEFAZ_CA_BUNDLE", "")

    FIREBASE_API_KEY: str = os.environ.get("FIREBASE_API_KEY", "AIzaSyAoq7xuMCJde6AXHmVMKt8c7NGYQlHMsX4")
    FIREBASE_AUTH_DOMAIN: str = os.environ.get("FIREBASE_AUTH_DOMAIN", "nfes-dd7ab.firebaseapp.com")
    FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "nfes-dd7ab")
    FIREBASE_STORAGE_BUCKET: str = os.environ.get("FIREBASE_STORAGE_BUCKET", "nfes-dd7ab.firebasestorage.app")
    FIREBASE_MESSAGING_SENDER_ID: str = os.environ.get("FIREBASE_MESSAGING_SENDER_ID", "845868073907")
    FIREBASE_APP_ID: str = os.environ.get("FIREBASE_APP_ID", "1:845868073907:web:3075c8479fb4e34a5d01c6")
    FIREBASE_MEASUREMENT_ID: str = os.environ.get("FIREBASE_MEASUREMENT_ID", "G-4346B1KGE7")
    FIREBASE_ENABLED: bool = True

    PRIMARY_SERVER_URL: str = os.environ.get("PRIMARY_SERVER_URL", "http://192.168.3.97:8000")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def _normalize_paths(self) -> "Settings":
        """Garante caminhos graváveis e absolutos.

        Prioridade: NFE_DATA_DIR / NFE_CERT_DIR (explícitos, do ambiente real) >
        valor vindo do .env (pode ser relativo) > default XDG.
        Relativos são resolvidos contra a raiz do repo; o default XDG já é
        absoluto. Assim o bundle read-only redireciona para ~/.local/share,
        e o .env existente (CERT_DIR=./certs) continua funcional em dev.
        """
        repo = self.BASE_DIR
        d = os.environ.get("NFE_DATA_DIR") or self.DATA_DIR
        if not os.path.isabs(d):
            d = os.path.abspath(os.path.join(repo, d))
        self.DATA_DIR = d
        c = os.environ.get("NFE_CERT_DIR") or self.CERT_DIR
        if not os.path.isabs(c):
            c = os.path.abspath(os.path.join(repo, c))
        self.CERT_DIR = c
        return self


settings = Settings()

os.makedirs(settings.CERT_DIR, exist_ok=True)
os.makedirs(settings.DATA_DIR, exist_ok=True)


def allowed_origins_list() -> list[str]:
    """Lista de origens permitidas pelo CORS.

    Importante: por padrão aceita apenas origens locais. O caractere
    curinga '*' é explicitamente rejeitado para impedir que um deploy
    em rede local exponha o sistema inteiro a qualquer site do browser.
    """
    raw = (settings.ALLOWED_ORIGINS or "").strip()
    if not raw:
        # default seguro: origens locais
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    if raw == "*":
        # '*' foi desativado por segurança. Caso o operador precise
        # liberar, defina explicitamente uma lista em ALLOWED_ORIGINS.
        return [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]
