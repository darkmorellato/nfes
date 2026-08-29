import os
import secrets
import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _default_secret_key() -> str:
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    generated = secrets.token_urlsafe(48)
    logger.warning(
        "SECRET_KEY não definida via env var. Usando chave aleatória gerada agora. "
        "Em produção, defina SECRET_KEY para garantir portabilidade dos dados criptografados (Fernet). "
        "Sem uma SECRET_KEY fixa, senhas de certificados e outros dados cifrados não poderão ser "
        "descriptografados após reinício do servidor."
    )
    return generated


def _default_debug() -> bool:
    return os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes", "on")


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
    CERT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "certs")
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    HOMOLOGACAO: bool = True
    DEFAULT_UF: str = "SP"
    TIMEOUT: int = 60
    ALLOWED_ORIGINS: str = _default_origins()

    FIREBASE_API_KEY: str = ""
    FIREBASE_AUTH_DOMAIN: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_STORAGE_BUCKET: str = ""
    FIREBASE_MESSAGING_SENDER_ID: str = ""
    FIREBASE_APP_ID: str = ""
    FIREBASE_MEASUREMENT_ID: str = ""
    FIREBASE_ENABLED: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

os.makedirs(settings.CERT_DIR, exist_ok=True)
os.makedirs(settings.DATA_DIR, exist_ok=True)


def allowed_origins_list() -> list[str]:
    raw = (settings.ALLOWED_ORIGINS or "").strip()
    if not raw or raw == "*":
        return ["*"] if raw == "*" else []
    return [o.strip() for o in raw.split(",") if o.strip()]
