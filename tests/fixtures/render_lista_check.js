/**
 * Renderiza a tabela de "Minhas NF-e" com dados REAIS da API e falha se o
 * HTML resultante não tiver linhas.
 *
 * Motivo: um identificador solto dentro do JSON.stringify (ex.: `$event` sem
 * aspas) lança ReferenceError no meio do render e a tela fica vazia sem
 * nenhum erro visível para o usuário.
 *
 * Uso: node render_lista_check.js <documentos.js> <payload.json>
 */
const fs = require("fs");

const modulo = process.argv[2];
const payload = process.argv[3];
if (!modulo || !payload || !fs.existsSync(modulo) || !fs.existsSync(payload)) {
    consoleReal_error("uso: node render_lista_check.js <documentos.js> <payload.json>");
    process.exit(2);
}

/* Guarda o console real antes dos stubs */
const consoleReal = { log: console.log.bind(console), error: console.error.bind(console) };

const falhas = [];

/* ------------------------- DOM mínimo ------------------------------- */
const elementos = {};
function elemento(id) {
    if (!elementos[id]) {
        elementos[id] = {
            id,
            innerHTML: "",
            textContent: "",
            value: "",
            style: {},
            classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
            scrollIntoView() {},
            focus() {},
            click() {},
            addEventListener() {},
        };
    }
    return elementos[id];
}

global.window = global;
global.document = {
    getElementById: (id) => elemento(id),
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
    createElement: () => elemento("__novo_" + Math.random()),
    body: elemento("__body"),
};
global.AppState = { gestaoDocs: [], saidasNfe: [] };
global.toast = { error() {}, warning() {}, success() {}, info() {} };

/* --------------------- helpers que vêm de outros módulos ------------- */
global.fmtDataHoraBR = (v) => (v ? String(v) : "—");
global.getSituacaoBadgeHtml = (s) => `<span class="badge">${String(s || "")}</span>`;
global.formatarChaveVertical = (c) => String(c || "");
global.renderEmptyState = () => {};
/* definido em manifestacao.js, que o harness não carrega */
global.atualizarSelecaoLote = () => {};
global.abrirDrawerDetalhes = () => {};

/* utils.js real (escapeHtml, escapeAttrJson, escapeInlineExpr, fmtDate…) */
eval(fs.readFileSync(require("path").join(__dirname, "..", "..", "frontend", "js", "utils.js"), "utf8"));

/* resposta real da API */
const dados = JSON.parse(fs.readFileSync(payload, "utf-8"));
global.apiGet = async () => ({ success: true, data: dados, status: 200 });

/* ------------------------- carrega o módulo ------------------------- */
try {
    eval(fs.readFileSync(modulo, "utf-8"));
} catch (e) {
    falhas.push(`falha ao carregar o módulo: ${e.message}`);
}

if (typeof global.loadGestaoDocs !== "function" && typeof loadGestaoDocs !== "function") {
    falhas.push("loadGestaoDocs não foi definida pelo módulo");
}

(async () => {
    try {
        await loadGestaoDocs(1);
    } catch (e) {
        falhas.push(`loadGestaoDocs lançou exceção: ${e.message}`);
    }

    const alvo = elemento("gestao-lista-resultado");
    const html = alvo.innerHTML || "";
    const corpo = /<tbody[^>]*>([\s\S]*?)<\/tbody>/.exec(html);
    const linhas = ((corpo ? corpo[1] : html).match(/<tr[\s>]/g) || []).length;
    const esperado = (dados.documentos || []).length;

    if (esperado > 0) {
        if (linhas === 0) {
            falhas.push(
                `a tabela ficou VAZIA: a API devolveu ${esperado} notas mas o render produziu 0 linhas`
            );
        } else if (linhas !== esperado) {
            falhas.push(`esperava ${esperado} linhas e veio ${linhas}`);
        }
        if (html.includes("Carregando notas fiscais")) {
            falhas.push("o rótulo de carregamento não foi substituído");
        }
        // nenhum marcador de delegação pode ter sobrado "solto"
        if (/\[\s*\$event|\[\s*\$this/.test(html)) {
            falhas.push("marcador $event/$this sem aspas no HTML gerado");
        }
        // nenhum onclick inline pode voltar
        if (/(^|[^-\w])(onclick|onchange)="/.test(html)) {
            falhas.push("handler inline reapareceu no HTML gerado");
        }
    }

    if (falhas.length) {
        consoleReal.error("FALHAS (" + falhas.length + "):");
        for (const f of falhas) consoleReal.error("  - " + f);
        process.exit(1);
    }
    consoleReal.log(
        `OK: tabela "Minhas NF-e" renderizou ${linhas} linhas a partir de ${esperado} notas reais`
    );
})();


function consoleReal_error(...a) { consoleReal.error(...a); }
