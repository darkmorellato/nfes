const API_BASE = window.location.origin;

/**
 * Recupera o token de sessão armazenado em AuthSession (memória)
 * ou em sessionStorage (persistente entre reloads).
 * Lê de ambos porque este módulo pode ser carregado antes de auth.js.
 */
function _getSessionToken() {
    if (typeof AuthSession !== "undefined" && AuthSession && AuthSession.token) {
        return AuthSession.token;
    }
    try {
        const raw = sessionStorage.getItem("nfe_auth_session");
        if (raw) {
            const parsed = JSON.parse(raw);
            return (parsed && parsed.token) || "";
        }
    } catch (_) { /* sessionStorage indisponível */ }
    return "";
}

/**
 * Adiciona o header X-Session-Token aos headers fornecidos se houver token.
 * Todos os endpoints protegidos exigem este header desde o hardening
 * de segurança (require_session em dependencies.py).
 */
function _withAuth(headers) {
    const h = Object.assign({}, headers || {});
    if (!h["X-Session-Token"] && !h["x-session-token"]) {
        const token = _getSessionToken();
        if (token) h["X-Session-Token"] = token;
    }
    return h;
}

async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: _withAuth({
            "Content-Type": "application/json",
            ...(options.headers || {}),
        }),
        ...options,
    };

    try {
        const response = await fetch(url, config);
        const data = await response.json();
        return { success: response.ok, data, status: response.status };
    } catch (error) {
        return { success: false, data: { error: error.message }, status: 0 };
    }
}

async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: "GET" });
}

async function apiPost(endpoint, body) {
    return apiRequest(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

async function apiUploadForm(endpoint, formData) {
    const url = `${API_BASE}${endpoint}`;
    // Para FormData o browser define Content-Type com boundary; só
    // adicionamos o X-Session-Token.
    const headers = _withAuth({});
    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData,
            headers,
        });
        const data = await response.json();
        return { success: response.ok, data, status: response.status };
    } catch (error) {
        return { success: false, data: { error: error.message }, status: 0 };
    }
}

/**
 * Faz download de um arquivo (PDF, XML, ZIP, Excel) enviando o token de
 * sessão. Devolve { ok, blob, filename, error } para a função chamadora
 * decidir o que fazer.
 */
async function apiDownload(endpoint, defaultFilename) {
    const url = `${API_BASE}${endpoint}`;
    try {
        const response = await fetch(url, { headers: _withAuth({}) });
        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const j = await response.json();
                if (j && j.detail) detail = j.detail;
            } catch (_) { /* resposta sem JSON */ }
            return { ok: false, status: response.status, error: detail };
        }
        const blob = await response.blob();
        // Tenta extrair nome do Content-Disposition; cai no default.
        let filename = defaultFilename;
        const cd = response.headers.get("Content-Disposition") || "";
        const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
        if (m && m[1]) filename = decodeURIComponent(m[1]);
        return { ok: true, blob, filename };
    } catch (error) {
        return { ok: false, status: 0, error: error.message };
    }
}

/**
 * Wrapper genérico para fetch com autenticação.
 * Retorna o Response do fetch (não parseado).
 */
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: _withAuth(options.headers || {}),
        ...options,
    };
    return fetch(url, config);
}
