import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import nfe, nfce, mdfe, nfse, cert, status, reports, danfe, gestao, emissao
from backend.routers.auth import router as auth_router
from backend.database import init_db
from backend.config import settings, allowed_origins_list
from backend.services.sync_service import start_background_sync, stop_background_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa banco de dados SQLite
    init_db()
    # Define intervalo padrão de sincronização: 60 minutos / 1 hora (respeita janela oficial da SEFAZ)
    from backend.database import get_sync_state, set_sync_state
    set_sync_state("auto_sync_interval_mins", "60")
    if not get_sync_state("auto_sync_enabled", ""):
        set_sync_state("auto_sync_enabled", "true")
    # Inicia robô de sincronização em segundo plano
    start_background_sync()
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
