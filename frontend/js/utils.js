function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/**
 * Escapa um valor para uso DENTRO de um handler inline (onclick="...").
 *
 * `escapeHtml` NÃO serve aqui: ele vira `&#39;`, o parser HTML decodifica de
 * volta para `'` **antes** de o JavaScript avaliar o handler — então um nome
 * como `O'Brien'); alert(1); //` quebrava a string e executava código
 * (XSS armazenado, ex.: nome de cliente vindo de XML de terceiro).
 *
 * A ordem importa: `&` primeiro (senão `&#39;` vindo do dado seria decodificado),
 * depois as barras invertidas, depois as aspas e por fim os caracteres de tag.
 */
function escapeForInlineHandler(value) {
    return String(value === null || value === undefined ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/\\/g, "\\\\")
        .replace(/'/g, "\\'")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n")
        .replace(/\u2028/g, "\\u2028")
        .replace(/\u2029/g, "\\u2029");
}

/**
 * Para interpolações SEM aspas (contexto de expressão, ex.: `f(${x})`).
 *
 * `JSON.stringify` já produz um literal JS válido (string entre aspas, número
 * como número). Aí só escapa para o **atributo HTML** — em especial `"` →
 * `&quot;`, senão a aspa fecharia o atributo. As barras invertidas NÃO são
 * tocadas: re-escapá-las corromperia o literal (o `\"` viraria `\\"` e
 * reabriria a string).
 */
function escapeInlineExpr(value) {
    const literal = JSON.stringify(value === undefined ? null : value);
    return String(literal)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/**
 * Escapa um **JSON já serializado** para ir dentro de um atributo HTML
 * entre aspas duplas (uso: `data-onclick="${escapeAttrJson(JSON.stringify(spec))}"`).
 */
function escapeAttrJson(json) {
    return String(json)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/"/g, "&quot;");
}

function cleanDigits(str) {
    return String(str || "").replace(/\D/g, "");
}

function formatCnpj(value) {
    const digits = cleanDigits(value);
    if (digits.length === 14) {
        return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
    }
    return value;
}

/** Formata CNPJ (14) ou CPF (11); devolve o valor original se não bater. */
function formatCpfCnpj(value) {
    const digits = cleanDigits(value);
    if (digits.length === 14) return formatCnpj(digits);
    if (digits.length === 11) {
        return digits.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
    }
    return value == null ? "" : String(value);
}

function fmtMoney(v) {
    const n = parseFloat(String(v || 0).replace(",", "."));
    if (isNaN(n)) return "0,00";
    return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(v) {
    if (!v || v === "—") return v || "—";
    try { return new Date(v).toLocaleString("pt-BR"); } catch { return v; }
}

function fmtDateShort(v) {
    if (!v) return "—";
    try { return new Date(v).toLocaleDateString("pt-BR"); } catch { return v; }
}

function downloadBlob(blob, filename) {
    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
}

function ufFromChave(chave) {
    if (!chave) return null;
    const d = String(chave).replace(/\D/g, "");
    if (d.length < 2) return null;
    const codigo = d.substring(0, 2);
    const found = Object.entries(window.UF_CODIGOS || {}).find(([, c]) => String(c) === codigo);
    return found ? found[0] : null;
}

function renderAutoUfBadge(ufDetectada, ufConfig) {
    if (!ufDetectada || ufDetectada === ufConfig) return "";
    return `<div class="uf-auto-badge">
        <b>UF auto-detectada da chave:</b> ${ufDetectada}
        &nbsp;|&nbsp; <b>UF configurada:</b> ${ufConfig}
        &nbsp;<small>(consulta será roteada automaticamente para a SEFAZ de ${ufDetectada})</small>
    </div>`;
}
