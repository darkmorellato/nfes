"""
Router de autenticação do sistema NFE.

Endpoint: POST /api/auth/login
  - Recebe email e senha (plain text via HTTPS)
  - Compara SHA-256(senha) com o hash armazenado no SQLite
  - Retorna token de sessão simples se válido
  - SEM hardcode de credenciais — tudo vem do banco SQLite

A tabela 'usuarios' é criada e populada automaticamente pelo init_db().
"""
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Sessões em memória: token → {email, nome, expires_at}
# Em produção use Redis ou JWT; para uso local/interno isso é suficiente.
_sessions: dict = {}


class LoginRequest(BaseModel):
    email: str
    senha: str  # senha em texto puro — enviada via HTTPS e nunca armazenada


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    perfil: Optional[str] = None
    message: str = ""


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _limpar_sessoes_expiradas():
    agora = datetime.now()
    expiradas = [t for t, s in _sessions.items() if s["expires_at"] < agora]
    for t in expiradas:
        del _sessions[t]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request):
    """
    Autentica o usuário consultando a tabela 'usuarios' do SQLite local.
    A senha é comparada via SHA-256 — nunca armazenamos texto puro.
    """
    email = (req.email or "").strip().lower()
    senha = req.senha or ""

    if not email or not senha:
        raise HTTPException(status_code=400, detail="E-mail e senha são obrigatórios.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email, senha_hash, nome, ativo, perfil FROM usuarios WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()

    if not row:
        logger.warning(f"[Auth] Tentativa de login com e-mail inexistente: {email}")
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    user = dict(row)

    if not user.get("ativo"):
        raise HTTPException(status_code=403, detail="Usuário desativado.")

    # Compara SHA-256 da senha digitada com o hash armazenado
    if _sha256(senha) != user["senha_hash"]:
        logger.warning(f"[Auth] Senha incorreta para: {email}")
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    # Gera token de sessão seguro (expira em 8 horas)
    _limpar_sessoes_expiradas()
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "email": user["email"],
        "nome": user["nome"],
        "perfil": user["perfil"],
        "expires_at": datetime.now() + timedelta(hours=8),
    }

    logger.info(f"[Auth] Login bem-sucedido: {email} ({user['nome']})")

    return LoginResponse(
        success=True,
        token=token,
        nome=user["nome"],
        email=user["email"],
        perfil=user["perfil"],
        message="Login realizado com sucesso.",
    )


@router.post("/logout")
async def logout(request: Request):
    """Invalida o token de sessão."""
    token = request.headers.get("X-Session-Token", "")
    if token and token in _sessions:
        del _sessions[token]
    return {"success": True, "message": "Logout realizado."}


@router.get("/me")
async def me(request: Request):
    """Retorna os dados do usuário autenticado (valida o token)."""
    token = request.headers.get("X-Session-Token", "")
    session = _sessions.get(token)
    if not session or session["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
    return {
        "email": session["email"],
        "nome": session["nome"],
        "perfil": session["perfil"],
    }
