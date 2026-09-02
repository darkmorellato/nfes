/**
 * auth.js — Módulo de Autenticação via Cloud Firestore
 *
 * Fluxo de login:
 *   1. Usuário digita email e senha.
 *   2. Faz consulta no Firestore (coleção "usuarios", documento identificado pelo email).
 *   3. Se o documento existir e a senha bater, libera acesso ao sistema.
 *   4. Se não existir ou senha incorreta, retorna mensagem de erro.
 *
 * IMPORTANTE: Nenhuma credencial é hardcoded neste arquivo.
 * As credenciais ficam EXCLUSIVAMENTE no Firestore.
 *
 * Para criar um usuário no Firestore, use o Console Firebase:
 *   Coleção: usuarios
 *   Documento ID: <email_do_usuario>  (ex: contasgeraljack@gmail.com)
 *   Campos:
 *     - email (string): contasgeraljack@gmail.com
 *     - senha (string): <hash_bcrypt_ou_senha_plain>
 *     - nome (string): Nome do usuário
 *     - ativo (boolean): true
 */

// ─── Estado de sessão ────────────────────────────────────────────────────────

const AuthSession = {
    authenticated: false,
    userEmail: null,
    userName: null,
    loginAttempts: 0,
    blockedUntil: null,
};

// ─── Constantes ──────────────────────────────────────────────────────────────

const AUTH_MAX_ATTEMPTS = 5;
const AUTH_BLOCK_MINUTES = 15;
const AUTH_SESSION_KEY = "nfe_auth_session";

function initAuth() {
    injectLoginOverlay();
    restoreSession();
    // Verifica conexão com o backend (a autenticação usa SQLite local, não Firestore)
    fetch("/health").then(r => {
        const icon = document.getElementById("login-db-icon");
        const text = document.getElementById("login-db-text");
        if (!icon || !text) return;
        if (r.ok) {
            icon.textContent = "🟢";
            text.textContent = "Servidor conectado";
            text.style.color = "#365738";
        } else {
            icon.textContent = "🔴";
            text.textContent = "Servidor com problema";
            text.style.color = "#8b1a22";
        }
    }).catch(() => {
        const icon = document.getElementById("login-db-icon");
        const text = document.getElementById("login-db-text");
        if (icon) icon.textContent = "🔴";
        if (text) { text.textContent = "Servidor offline"; text.style.color = "#8b1a22"; }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAuth);
} else {
    initAuth();
}

/**
 * Injeta o overlay de login no DOM antes de qualquer conteúdo do sistema.
 */
function injectLoginOverlay() {
    const overlay = document.createElement("div");
    overlay.id = "login-overlay";
    overlay.innerHTML = buildLoginHTML();
    document.body.insertBefore(overlay, document.body.firstChild);

    // Oculta o conteúdo principal enquanto não autenticado
    toggleMainContent(false);

    // Bind do formulário
    const form = document.getElementById("login-form");
    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            handleLogin();
        });
    }

    // Exibir/ocultar senha
    const toggleBtn = document.getElementById("btn-toggle-senha");
    const senhaInput = document.getElementById("login-senha");
    if (toggleBtn && senhaInput) {
        toggleBtn.addEventListener("click", () => {
            const isText = senhaInput.type === "text";
            senhaInput.type = isText ? "password" : "text";
            toggleBtn.textContent = isText ? "👁️" : "🙈";
        });
    }
}

/**
 * Monta o HTML do overlay de login com design Japandi/Gov.br.
 */
function buildLoginHTML() {
    return `
    <div id="login-overlay-inner" style="
        position: fixed;
        inset: 0;
        z-index: 99999;
        background: linear-gradient(135deg, #f7f5f0 0%, #edf3f8 50%, #edf4ed 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    ">
        <div style="
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 8px 40px rgba(44, 73, 96, 0.14), 0 2px 8px rgba(0,0,0,0.06);
            padding: 48px 40px 36px;
            width: 100%;
            max-width: 420px;
            position: relative;
        ">
            <!-- Cabeçalho -->
            <div style="text-align: center; margin-bottom: 32px;">
                <div style="font-size: 48px; margin-bottom: 8px;">🏛️</div>
                <h1 style="font-size: 20px; font-weight: 700; color: #2d2a26; margin: 0 0 4px;">
                    Portal NF-e
                </h1>
                <p style="font-size: 13px; color: #736f66; margin: 0;">
                    Sistema de Gestão de Notas Fiscais Eletrônicas
                </p>
            </div>

            <!-- Formulário -->
            <form id="login-form" autocomplete="on" novalidate>
                <!-- Email -->
                <div style="margin-bottom: 20px;">
                    <label for="login-email" style="
                        display: block;
                        font-size: 12px;
                        font-weight: 600;
                        color: #4b6a82;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 6px;
                    ">E-mail</label>
                    <input
                        type="email"
                        id="login-email"
                        name="email"
                        autocomplete="username"
                        placeholder="seu@email.com.br"
                        required
                        style="
                            width: 100%;
                            padding: 12px 14px;
                            border: 1.5px solid #e6e1d8;
                            border-radius: 8px;
                            font-size: 14px;
                            color: #2d2a26;
                            background: #faf8f5;
                            box-sizing: border-box;
                            outline: none;
                            transition: border-color 0.2s;
                        "
                        onfocus="this.style.borderColor='#4b6a82'; this.style.background='#fff';"
                        onblur="this.style.borderColor='#e6e1d8'; this.style.background='#faf8f5';"
                    >
                </div>

                <!-- Senha -->
                <div style="margin-bottom: 24px; position: relative;">
                    <label for="login-senha" style="
                        display: block;
                        font-size: 12px;
                        font-weight: 600;
                        color: #4b6a82;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 6px;
                    ">Senha</label>
                    <div style="position: relative;">
                        <input
                            type="password"
                            id="login-senha"
                            name="password"
                            autocomplete="current-password"
                            placeholder="••••••••"
                            required
                            style="
                                width: 100%;
                                padding: 12px 44px 12px 14px;
                                border: 1.5px solid #e6e1d8;
                                border-radius: 8px;
                                font-size: 14px;
                                color: #2d2a26;
                                background: #faf8f5;
                                box-sizing: border-box;
                                outline: none;
                                transition: border-color 0.2s;
                            "
                            onfocus="this.style.borderColor='#4b6a82'; this.style.background='#fff';"
                            onblur="this.style.borderColor='#e6e1d8'; this.style.background='#faf8f5';"
                        >
                        <button
                            type="button"
                            id="btn-toggle-senha"
                            style="
                                position: absolute;
                                right: 12px;
                                top: 50%;
                                transform: translateY(-50%);
                                background: none;
                                border: none;
                                cursor: pointer;
                                font-size: 18px;
                                padding: 0;
                                line-height: 1;
                            "
                            title="Mostrar/ocultar senha"
                        >👁️</button>
                    </div>
                </div>

                <!-- Mensagem de erro -->
                <div id="login-erro" style="
                    display: none;
                    background: #faebec;
                    border: 1px solid #edd2d4;
                    border-radius: 8px;
                    padding: 10px 14px;
                    font-size: 13px;
                    color: #8b1a22;
                    margin-bottom: 16px;
                    text-align: center;
                "></div>

                <!-- Botão de login -->
                <button
                    type="submit"
                    id="btn-login"
                    style="
                        width: 100%;
                        padding: 13px;
                        background: linear-gradient(135deg, #2c4960, #4b6a82);
                        color: #fff;
                        border: none;
                        border-radius: 8px;
                        font-size: 15px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: opacity 0.2s, transform 0.1s;
                        letter-spacing: 0.3px;
                    "
                    onmouseover="this.style.opacity='0.9';"
                    onmouseout="this.style.opacity='1';"
                >
                    🔐 Entrar no Sistema
                </button>
            </form>

            <!-- Rodapé -->
            <div style="text-align: center; margin-top: 24px;">
                <div id="login-firestore-status" style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 11px;
                    color: #9c978d;
                ">
                    <span id="login-db-icon">⏳</span>
                    <span id="login-db-text">Conectando ao banco de dados...</span>
                </div>
            </div>

            <!-- Loader -->
            <div id="login-loader" style="
                display: none;
                position: absolute;
                inset: 0;
                background: rgba(255,255,255,0.85);
                border-radius: 16px;
                align-items: center;
                justify-content: center;
                flex-direction: column;
                gap: 12px;
                font-size: 14px;
                color: #4b6a82;
                font-weight: 600;
            ">
                <div style="font-size: 32px; animation: spin 1s linear infinite;">⟳</div>
                Verificando credenciais...
            </div>
        </div>
    </div>
    <style>
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
    `;
}

// ─── Lógica de login ─────────────────────────────────────────────────────────

/**
 * Autentica o usuário via endpoint do backend (/api/auth/login).
 * O backend consulta o banco SQLite local — não depende do Firestore.
 * As credenciais são transmitidas apenas via HTTPS e nunca armazenadas no código.
 */
async function handleLogin() {
    // Verifica bloqueio por tentativas excessivas
    if (AuthSession.blockedUntil && new Date() < AuthSession.blockedUntil) {
        const mins = Math.ceil((AuthSession.blockedUntil - new Date()) / 60000);
        showLoginError(`⛔ Muitas tentativas incorretas. Tente novamente em ${mins} minuto(s).`);
        return;
    }

    const email = (document.getElementById("login-email")?.value || "").trim().toLowerCase();
    const senha = document.getElementById("login-senha")?.value || "";

    if (!email || !senha) {
        showLoginError("Por favor, preencha e-mail e senha.");
        return;
    }

    setLoginLoading(true);

    try {
        // Chama o endpoint de autenticação do backend
        const resp = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, senha }),
        });

        const data = await resp.json();

        if (!resp.ok) {
            // 401 = credenciais erradas | 403 = usuário desativado
            recordFailedAttempt();
            const msg = data.detail || "E-mail ou senha incorretos.";
            showLoginError("❌ " + msg);
            setLoginLoading(false);
            return;
        }

        if (!data.success) {
            recordFailedAttempt();
            showLoginError("❌ " + (data.message || "Falha na autenticação."));
            setLoginLoading(false);
            return;
        }

        // Autenticação bem-sucedida
        AuthSession.authenticated = true;
        AuthSession.userEmail = data.email || email;
        AuthSession.userName = data.nome || email;
        AuthSession.token = data.token || "";
        AuthSession.loginAttempts = 0;
        AuthSession.blockedUntil = null;
        AuthSession.senha_padrao = data.senha_padrao || false;

        // Sincronizar com AppState
        AppState.email = data.email || email;
        AppState.nome = data.nome || email;
        AppState.perfil = data.perfil || "admin";
        AppState.senha_padrao = data.senha_padrao || false;

        // Salva sessão no sessionStorage (expira ao fechar o navegador)
        sessionStorage.setItem(AUTH_SESSION_KEY, JSON.stringify({
            email: AuthSession.userEmail,
            nome: AuthSession.userName,
            token: AuthSession.token,
            perfil: AppState.perfil,
            senha_padrao: AuthSession.senha_padrao,
            ts: Date.now(),
        }));

        // Registra acesso no Firestore (auditoria — silencioso se falhar)
        try {
            if (isFirestoreAvailable && firestoreDb) {
                await firestoreDb.collection("acessos_log").add({
                    email: AuthSession.userEmail,
                    nome: AuthSession.userName,
                    ts: firebase.firestore.FieldValue.serverTimestamp(),
                    resultado: "sucesso",
                });
            }
        } catch (_) { /* não bloqueia o login */ }

        setLoginLoading(false);
        hideLoginOverlay();
        showWelcomeToast(AuthSession.userName);

        // Se senha padrão, forçar alteração
        if (AuthSession.senha_padrao) {
            setTimeout(() => {
                showSection("config");
                switchTab("tab-cfg-conta");
                const alertDiv = document.getElementById("senha-padrao-alert");
                if (alertDiv) alertDiv.style.display = "block";
            }, 500);
        }

    } catch (err) {
        console.error("[Auth] Erro ao chamar /api/auth/login:", err);
        showLoginError("⚠️ Não foi possível conectar ao servidor. Verifique se o sistema está rodando.");
        setLoginLoading(false);
    }
}

/**
 * Gera hash SHA-256 hex de uma string usando Web Crypto API.
 */
async function sha256Hex(text) {
    const encoder = new TextEncoder();
    const data = encoder.encode(text);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Registra tentativa de login falha e aplica bloqueio após N tentativas.
 */
function recordFailedAttempt() {
    AuthSession.loginAttempts += 1;
    if (AuthSession.loginAttempts >= AUTH_MAX_ATTEMPTS) {
        AuthSession.blockedUntil = new Date(Date.now() + AUTH_BLOCK_MINUTES * 60 * 1000);
        showLoginError(
            `⛔ ${AUTH_MAX_ATTEMPTS} tentativas incorretas. Acesso bloqueado por ${AUTH_BLOCK_MINUTES} minutos.`
        );
    }
}

// ─── Restauração de sessão ────────────────────────────────────────────────────

/**
 * Tenta restaurar sessão salva no sessionStorage (dura enquanto o navegador estiver aberto).
 */
function restoreSession() {
    try {
        const saved = sessionStorage.getItem(AUTH_SESSION_KEY);
        if (!saved) return;
        const data = JSON.parse(saved);
        if (!data.email || !data.ts) return;

        // Sessão válida por 8 horas
        const OITO_HORAS = 8 * 60 * 60 * 1000;
        if (Date.now() - data.ts > OITO_HORAS) {
            sessionStorage.removeItem(AUTH_SESSION_KEY);
            return;
        }

        AuthSession.authenticated = true;
        AuthSession.userEmail = data.email;
        AuthSession.userName = data.nome || data.email;
        AuthSession.token = data.token || "";
        AuthSession.senha_padrao = data.senha_padrao || false;

        // Sincronizar com AppState
        AppState.email = data.email;
        AppState.nome = data.nome || data.email;
        AppState.perfil = data.perfil || "admin";
        AppState.senha_padrao = data.senha_padrao || false;

        hideLoginOverlay();
    } catch (_) {
        sessionStorage.removeItem(AUTH_SESSION_KEY);
    }
}

// ─── Helpers de UI ────────────────────────────────────────────────────────────

function showLoginError(msg) {
    const el = document.getElementById("login-erro");
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
    // Remove após 8 segundos
    setTimeout(() => { if (el) el.style.display = "none"; }, 8000);
}

function setLoginLoading(isLoading) {
    const btn = document.getElementById("btn-login");
    const loader = document.getElementById("login-loader");
    if (btn) btn.disabled = isLoading;
    if (loader) loader.style.display = isLoading ? "flex" : "none";
}

function hideLoginOverlay() {
    const overlay = document.getElementById("login-overlay");
    if (overlay) {
        overlay.style.transition = "opacity 0.4s ease";
        overlay.style.opacity = "0";
        setTimeout(() => {
            overlay.style.display = "none";
        }, 400);
    }
    toggleMainContent(true);

    // Exibe nome do usuário logado no cabeçalho
    const userInfo = document.getElementById("header-user-info");
    const userNome = document.getElementById("header-user-nome");
    if (userInfo && userNome && AuthSession.userName) {
        userNome.textContent = AuthSession.userName;
        userInfo.style.display = "inline-flex";
    }
}

function toggleMainContent(visible) {
    // Oculta/exibe todos os elementos filhos diretos do body (exceto o overlay de login)
    const elements = document.querySelectorAll(
        "body > *:not(#login-overlay):not(script):not(style)"
    );
    elements.forEach(el => {
        el.style.visibility = visible ? "" : "hidden";
    });
}

function showWelcomeToast(nome) {
    const toast = document.createElement("div");
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: linear-gradient(135deg, #2c4960, #4b6a82);
        color: #fff;
        padding: 14px 20px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 500;
        z-index: 99998;
        box-shadow: 0 4px 20px rgba(44,73,96,0.3);
        animation: slideInRight 0.4s ease;
    `;
    toast.innerHTML = `✅ Bem-vindo(a), <strong>${escapeHtml ? escapeHtml(nome) : nome}</strong>!`;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; toast.style.transition = "opacity 0.5s"; }, 3000);
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 3600);
}

// ─── Status do Firestore na tela de login ────────────────────────────────────

/**
 * Atualiza o indicador de status na tela de login.
 * A autenticação usa o backend (SQLite) — o Firestore é opcional (auditoria).
 */
function updateLoginFirestoreStatus(connected, errorMsg) {
    const icon = document.getElementById("login-db-icon");
    const text = document.getElementById("login-db-text");
    if (!icon || !text) return;
    // A autenticação é via backend — sempre mostra como "disponível" se o servidor responder
    // O Firestore é usado apenas para auditoria de acessos
    icon.textContent = "🟢";
    text.textContent = "Servidor conectado";
    text.style.color = "#365738";
}

// ─── Logout ───────────────────────────────────────────────────────────────────

function logout() {
    // Notifica o backend para invalidar o token de sessão
    const token = AuthSession.token || "";
    if (token) {
        fetch("/api/auth/logout", {
            method: "POST",
            headers: { "X-Session-Token": token },
        }).catch(() => {});
    }

    sessionStorage.removeItem(AUTH_SESSION_KEY);
    AuthSession.authenticated = false;
    AuthSession.userEmail = null;
    AuthSession.userName = null;
    AuthSession.token = null;
    // Recarrega a página para exibir o login novamente
    window.location.reload();
}
