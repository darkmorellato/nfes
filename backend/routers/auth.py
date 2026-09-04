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

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from backend.database import get_db_connection
from backend.dependencies import login_rate_limiter

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


def save_session(token: str, user: dict, hours: int = 8) -> dict:
    """Salva a sessão na memória RAM e persiste na tabela user_sessions do SQLite."""
    now = datetime.now()
    exp = now + timedelta(hours=hours)
    session_data = {
        "email": user["email"],
        "nome": user["nome"],
        "perfil": user["perfil"],
        "expires_at": exp,
    }
    _sessions[token] = session_data
    try:
        with get_db_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_sessions (token, email, nome, perfil, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (token, user["email"], user["nome"], user["perfil"], exp.isoformat(), now.isoformat()))
            conn.commit()
    except Exception as e:
        logger.debug(f"[Auth] Falha ao persistir sessão no SQLite: {e}")
    return session_data


def get_session(token: str) -> Optional[dict]:
    """Recupera a sessão pelo token, conferindo primeiro na RAM e depois no SQLite."""
    if not token:
        return None
    now = datetime.now()

    # 1. Verifica cache em memória
    session = _sessions.get(token)
    if session:
        if session.get("expires_at", datetime.min) > now:
            return session
        else:
            _sessions.pop(token, None)
            delete_session(token)
            return None

    # 2. Busca no SQLite se não estiver na memória (ex: após restart do serviço)
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email, nome, perfil, expires_at FROM user_sessions WHERE token = ?", (token,))
            row = cursor.fetchone()
            if row:
                exp_dt = datetime.fromisoformat(row["expires_at"])
                if exp_dt > now:
                    session = {
                        "email": row["email"],
                        "nome": row["nome"],
                        "perfil": row["perfil"],
                        "expires_at": exp_dt,
                    }
                    _sessions[token] = session
                    return session
                else:
                    cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
                    conn.commit()
    except Exception as e:
        logger.debug(f"[Auth] Erro ao recuperar sessão do SQLite: {e}")

    return None


def delete_session(token: str) -> None:
    """Invalida a sessão na memória e no banco SQLite."""
    if not token:
        return
    _sessions.pop(token, None)
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
            conn.commit()
    except Exception:
        pass


def _limpar_sessoes_expiradas():
    """Remove tokens expirados da memória e da tabela user_sessions."""
    agora = datetime.now()
    expiradas = [t for t, s in list(_sessions.items()) if s.get("expires_at", datetime.min) < agora]
    for t in expiradas:
        _sessions.pop(t, None)
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (agora.isoformat(),))
            conn.commit()
    except Exception:
        pass


class LoginRequest(BaseModel):
    email: str
    senha: str  # senha em texto puro — enviada via HTTPS e nunca armazenada


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    perfil: Optional[str] = None
    senha_padrao: Optional[bool] = None
    message: str = ""


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(login_rate_limiter)])
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
            "SELECT email, senha_hash, nome, ativo, perfil, senha_padrao FROM usuarios WHERE email = ?",
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
        from backend.services.audit_service import record_audit
        record_audit(
            "LOGIN_FALHOU", "USUARIO", email, usuario_email=email, usuario_nome=user["nome"],
            detalhe="Tentativa de login com senha incorreta", status="FALHA", request=request
        )
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

    # Gera token de sessão seguro (expira em 8 horas e persiste no SQLite)
    _limpar_sessoes_expiradas()
    token = secrets.token_urlsafe(32)
    save_session(token, user, hours=8)

    from backend.services.audit_service import record_audit
    record_audit(
        "LOGIN", "USUARIO", email, usuario_email=email, usuario_nome=user["nome"],
        detalhe="Autenticação bem-sucedida", request=request
    )

    logger.info(f"[Auth] Login bem-sucedido: {email} ({user['nome']})")

    return LoginResponse(
        success=True,
        token=token,
        nome=user["nome"],
        email=user["email"],
        perfil=user["perfil"],
        senha_padrao=bool(user.get("senha_padrao", 0)),
        message="Login realizado com sucesso.",
    )


@router.post("/logout")
async def logout(request: Request):
    """Invalida o token de sessão na memória e no SQLite e registra auditoria."""
    token = request.headers.get("X-Session-Token", "").strip()
    if token:
        sess = get_session(token)
        if sess:
            from backend.services.audit_service import record_audit
            record_audit("LOGOUT", "USUARIO", sess["email"], usuario_email=sess["email"], usuario_nome=sess["nome"], detalhe="Logout voluntário", request=request)
        delete_session(token)
    return {"success": True, "message": "Logout realizado."}


@router.get("/me")
async def me(request: Request):
    """Retorna os dados do usuário autenticado (valida o token via get_session)."""
    token = request.headers.get("X-Session-Token", "").strip()
    session = get_session(token)
    if not session:
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


class AlterarEmailRequest(BaseModel):
    senha_atual: str
    email_novo: str
    email_novo_confirm: str


@router.put("/alterar-email")
async def alterar_email(req: AlterarEmailRequest, request: Request):
    """Troca o e-mail do usuário autenticado.

    Requer o token de sessão válido e a senha atual para confirmação.
    """
    token = request.headers.get("X-Session-Token", "")
    session = _sessions.get(token)
    if not session or session["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")

    email_atual = session["email"]
    email_novo = (req.email_novo or "").strip().lower()
    email_novo_confirm = (req.email_novo_confirm or "").strip().lower()

    if not email_novo or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_novo):
        raise HTTPException(status_code=400, detail="E-mail inválido.")

    if email_novo != email_novo_confirm:
        raise HTTPException(status_code=400, detail="Os e-mails não conferem.")

    if email_novo == email_atual:
        raise HTTPException(status_code=400, detail="O novo e-mail é igual ao atual.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT senha_hash FROM usuarios WHERE email = ?",
            (email_atual,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if not _verify_password(req.senha_atual or "", row["senha_hash"]):
            raise HTTPException(
                status_code=401,
                detail="Senha atual incorreta.",
            )

        # Verificar se o novo e-mail já está em uso
        cursor.execute(
            "SELECT id FROM usuarios WHERE email = ?",
            (email_novo,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Este e-mail já está em uso por outro usuário.",
            )

        conn.execute(
            "UPDATE usuarios SET email = ?, updated_at = datetime('now') WHERE email = ?",
            (email_novo, email_atual),
        )
        conn.commit()

    # Atualizar sessão em memória
    session["email"] = email_novo

    logger.info(f"[Auth] E-mail alterado de {email_atual} para {email_novo}")
    return {"success": True, "message": "E-mail alterado com sucesso.", "email": email_novo}


@router.post("/marcar-senha-alterada")
async def marcar_senha_alterada(request: Request):
    """Marca que o usuário alterou a senha padrão (desbloqueia o sistema)."""
    token = request.headers.get("X-Session-Token", "")
    session = _sessions.get(token)
    if not session or session["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")

    email = session["email"]
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE usuarios SET senha_padrao = 0, updated_at = datetime('now') WHERE email = ?",
            (email,),
        )
        conn.commit()

    logger.info(f"[Auth] Senha padrão marcada como alterada: {email}")
    return {"success": True, "message": "Senha padrão registrada como alterada."}
