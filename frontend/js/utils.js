function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
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
