"""
Router de autenticação do sistema NFE.

Endpoint: POST /api/auth/login
  - Recebe email e senha (plain text via HTTPS)
  - Compara com o hash armazenado no SQLite (bcrypt com fallback SHA-256 legado)
  - Retorna token de sessão simples se válido
  - SEM hardcode de credenciais — tudo vem do banco SQLite

A tabela 'usuarios' é criada e populada automaticamente pelo init_db().
"""
import hashlib
import re
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

# bcrypt é importado preguiçosamente para que o módulo continue
# carregando em ambientes sem a dependência instalada.
_bcrypt_mod = None


def _get_bcrypt():
    global _bcrypt_mod
    if _bcrypt_mod is None:
        try:
            import bcrypt as _bc
            _bcrypt_mod = _bc
        except ImportError:
            logger.warning(
                "[Auth] 'bcrypt' não está instalado — usando fallback SHA-256. "
                "Instale com: pip install 'passlib[bcrypt]' ou 'bcrypt'."
            )
            _bcrypt_mod = False  # marca como indisponível
    return _bcrypt_mod or None


_BCRYPT_PREFIX = "bcrypt$"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _hash_password(plain: str) -> str:
    """Gera hash bcrypt. Fallback para SHA-256 se bcrypt não estiver disponível."""
    bcrypt = _get_bcrypt()
    if bcrypt:
        return _BCRYPT_PREFIX + bcrypt.hashpw(
            plain.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")
    # Fallback: SHA-256 sem sal (legado) — manter para não quebrar
    # ambientes sem bcrypt instalado, mas recomendar a migração.
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _verify_password(plain: str, stored: str) -> bool:
    """Verifica senha contra hash. Suporta bcrypt e SHA-256 legado."""
    if not stored:
        return False

    # Hash bcrypt: prefixo "bcrypt$"
    if stored.startswith(_BCRYPT_PREFIX):
        bcrypt = _get_bcrypt()
        if not bcrypt:
            return False
        try:
            return bcrypt.checkpw(
                plain.encode("utf-8"),
                stored[len(_BCRYPT_PREFIX):].encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    # Hash SHA-256 legado (64 hex chars) — comparação em tempo constante
    if _SHA256_RE.match(stored):
        return hashlib.sha256(plain.encode("utf-8")).hexdigest() == stored

    # Formato desconhecido: rejeita
    return False


def _is_legacy_hash(stored: str) -> bool:
    """True se o hash precisar ser migrado para bcrypt no próximo login válido."""
    return bool(stored) and not stored.startswith(_BCRYPT_PREFIX)


def _limpar_sessoes_expiradas():
    agora = datetime.now()
    expiradas = [t for t, s in _sessions.items() if s["expires_at"] < agora]
    for t in expiradas:
        del _sessions[t]


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


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request):
    """
    Autentica o usuário consultando a tabela 'usuarios' do SQLite local.
    Senhas são verificadas via bcrypt (com fallback SHA-256 para hashes legados).
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

    if not _verify_password(senha, user["senha_hash"]):
        logger.warning(f"[Auth] Senha incorreta para: {email}")
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    # Migração silenciosa: se o hash armazenado ainda é legado (SHA-256),
    # reescreve como bcrypt após login válido. Falha silenciosa se bcrypt
    # não estiver disponível — o login continua funcionando normalmente.
    if _is_legacy_hash(user["senha_hash"]) and _get_bcrypt():
        try:
            novo_hash = _hash_password(senha)
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE usuarios SET senha_hash = ? WHERE email = ?",
                    (novo_hash, email),
                )
                conn.commit()
            logger.info(f"[Auth] Hash de senha migrado para bcrypt: {email}")
        except Exception as e:
            logger.warning(f"[Auth] Falha ao migrar hash para bcrypt: {e}")

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


class AlterarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


@router.post("/alterar-senha")
async def alterar_senha(req: AlterarSenhaRequest, request: Request):
    """Troca a senha do usuário autenticado.

    Requer o token de sessão válido. Persiste o novo hash com bcrypt
    (ou SHA-256 como fallback, se bcrypt não estiver instalado).
    """
    token = request.headers.get("X-Session-Token", "")
    session = _sessions.get(token)
    if not session or session["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")

    email = session["email"]
    if not req.senha_nova or len(req.senha_nova) < 6:
        raise HTTPException(
            status_code=400,
            detail="A nova senha deve ter ao menos 6 caracteres.",
        )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT senha_hash FROM usuarios WHERE email = ?",
            (email,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if not _verify_password(req.senha_atual or "", row["senha_hash"]):
            raise HTTPException(
                status_code=401,
                detail="Senha atual incorreta.",
            )
        novo_hash = _hash_password(req.senha_nova)
        conn.execute(
            "UPDATE usuarios SET senha_hash = ? WHERE email = ?",
            (novo_hash, email),
        )
        conn.commit()

    logger.info(f"[Auth] Senha alterada para: {email}")
    return {"success": True, "message": "Senha alterada com sucesso."}
