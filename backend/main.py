import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import nfe, nfce, mdfe, nfse, cert, status, reports, danfe, gestao, emissao
from backend.routers.auth import router as auth_router
from backend.database import init_db
from backend.config import settings, allowed_origins_list
from backend.services.sync_service import start_background_sync, stop_background_sync

logger = logging.getLogger(__name__)


def _safe_firestore_auto_pull() -> None:
    """Pull automático do Firestore no startup (silencioso se falhar).

    Roda em thread daemon, então não bloqueia o startup do servidor.
    Idempotente: o save_nfe_doc() faz upsert, então rodar várias vezes é seguro.
    """
    try:
        from backend.services.firestore_service import (
            _get_api_key,
            _get_project_id,
            pull_from_firestore,
        )
        if not _get_api_key() or not _get_project_id():
            logger.info("[Firestore] Pull automático na inicialização ignorado: credenciais ausentes.")
            return
        logger.info("[Firestore] Pull automático na inicialização: baixando NF-es da nuvem...")
        result = pull_from_firestore()
        logger.info(
            f"[Firestore] Pull automático concluído: "
            f"{result.get('imported', 0)}/{result.get('total_cloud', 0)} NF-es importadas."
        )
    except Exception as e:
        logger.warning(f"[Firestore] Pull automático falhou (silencioso): {e}")


def _safe_firestore_auto_sync_cadastros() -> None:
    """Auto-sync de cadastros (clientes/produtos) Firestore→SQLite no startup.

    Roda em thread daemon, não bloqueia o startup. Idempotente.
    Pode ser desabilitado com `firestore_auto_sync_cadastros_enabled=false` no sync_state.
    """
    try:
        from backend.services.firestore_service import (
            _get_api_key,
            _get_project_id,
            sincronizar_clientes_firestore_para_sqlite,
            sincronizar_produtos_firestore_para_sqlite,
        )
        if not _get_api_key() or not _get_project_id():
            logger.info("[Firestore] Auto-sync de cadastros ignorado: credenciais ausentes.")
            return
        logger.info("[Firestore] Auto-sync de cadastros no startup: baixando clientes e produtos...")
        r1 = sincronizar_clientes_firestore_para_sqlite()
        logger.info(
            f"[Firestore] Auto-sync clientes: {r1.get('imported', 0)}/{r1.get('total_nuvem', 0)} importados."
        )
        r2 = sincronizar_produtos_firestore_para_sqlite()
        logger.info(
            f"[Firestore] Auto-sync produtos: {r2.get('imported', 0)}/{r2.get('total_nuvem', 0)} importados."
        )
    except Exception as e:
        logger.warning(f"[Firestore] Auto-sync de cadastros falhou (silencioso): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa migrações versionadas do Alembic e inicializa SQLite
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")
        if os.path.exists(alembic_ini_path):
            cfg = Config(alembic_ini_path)
            command.upgrade(cfg, "head")
            logger.info("[DB] Migrações Alembic aplicadas com sucesso (HEAD).")
        else:
            init_db()
    except Exception as e:
        logger.warning(f"[DB] Aviso ao rodar migrações Alembic: {e}")
        init_db()

    # Define intervalo padrão de sincronização: 60 minutos / 1 hora (respeita janela oficial da SEFAZ)
    from backend.database import get_sync_state, set_sync_state
    set_sync_state("auto_sync_interval_mins", "60")
    if not get_sync_state("auto_sync_enabled", ""):
        set_sync_state("auto_sync_enabled", "true")
    # Inicia robô de sincronização em segundo plano
    start_background_sync()

    # Pull automático do Firestore em background (não bloqueia o startup).
    # Pode ser desabilitado definindo `firestore_auto_pull_enabled=false` no sync_state.
    if get_sync_state("firestore_auto_pull_enabled", "true") == "true":
        import threading
        threading.Thread(
            target=_safe_firestore_auto_pull,
            daemon=True,
            name="firestore-auto-pull",
        ).start()

    # Auto-sync de cadastros (clientes/produtos) em background, depois do pull das NF-es.
    # Idempotente. Pode ser desabilitado com `firestore_auto_sync_cadastros_enabled=false`.
    if get_sync_state("firestore_auto_sync_cadastros_enabled", "true") == "true":
        import threading
        threading.Thread(
            target=_safe_firestore_auto_sync_cadastros,
            daemon=True,
            name="firestore-auto-sync-cadastros",
        ).start()
    yield
    # Finaliza tarefas em segundo plano
    stop_background_sync()


app = FastAPI(
    title="NFE Manager - Interface PyNFe",
    description="Interface de gerenciamento de NF-e/NFC-e/MDF-e/NFS-e via PyNFe",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID & Request Tracing middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    import secrets
    req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = f"req_{secrets.token_hex(6)}"
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse
    req_id = getattr(request.state, "request_id", "req_unknown")
    logger.error(f"[Erro Interno][{req_id}] {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno do servidor.",
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _frontend_dir() -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = os.path.join(meipass, "frontend")
        if os.path.isdir(cand):
            return cand
    return os.path.join(BASE_DIR, "frontend")


FRONTEND_DIR = _frontend_dir()
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

app.include_router(status.router, prefix="/api", tags=["Status"])
app.include_router(cert.router, prefix="/api", tags=["Certificado"])
app.include_router(reports.router, prefix="/api", tags=["Relatórios"])
app.include_router(danfe.router, prefix="/api/danfe", tags=["DANFE"])
app.include_router(gestao.router, prefix="/api", tags=["Gestão e Inteligência"])
app.include_router(emissao.router, prefix="/api", tags=["Emissão de NF-e e Cadastros"])
app.include_router(nfe.router, prefix="/api/nfe", tags=["NF-e"])
app.include_router(nfce.router, prefix="/api/nfce", tags=["NFC-e"])
app.include_router(mdfe.router, prefix="/api/mdfe", tags=["MDF-e"])
app.include_router(nfse.router, prefix="/api/nfse", tags=["NFS-e"])
app.include_router(auth_router, prefix="/api", tags=["Autenticação"])


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    ico_path = os.path.join(FRONTEND_DIR, "favicon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path, media_type="image/x-icon")
    return HTMLResponse(status_code=404)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nfe-manager"}


@app.get("/api/firebase-config")
async def get_firebase_config():
    """Endpoint para o frontend obter a configuração do Firebase (compatível com Spark free tier)."""
    return {
        "apiKey": settings.FIREBASE_API_KEY,
        "authDomain": settings.FIREBASE_AUTH_DOMAIN,
        "projectId": settings.FIREBASE_PROJECT_ID,
        "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
        "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
        "appId": settings.FIREBASE_APP_ID,
        "measurementId": settings.FIREBASE_MEASUREMENT_ID,
    }
