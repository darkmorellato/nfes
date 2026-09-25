/**
 * Prova que escapeForInlineHandler neutraliza XSS em handlers inline.
 *
 * Cenário real: o valor vai para um atributo HTML, o parser HTML decodifica as
 * entidades e SÓ DEPOIS o JavaScript avalia o handler. O teste reproduz essa
 * ordem (decode → eval) e falha se qualquer payload executar código.
 *
 * Uso: node xss_check.js <caminho/para/utils.js>
 */
const fs = require("fs");
const path = require("path");

const utilsPath = process.argv[2];
if (!utilsPath || !fs.existsSync(utilsPath)) {
    console.error("utils.js não encontrado: " + utilsPath);
    process.exit(2);
}

// Carrega escapeForInlineHandler / escapeHtml no escopo global deste script
eval(fs.readFileSync(utilsPath, "utf8"));

/** Reproduz a decodificação de entidades feita pelo parser HTML de atributo. */
function decodeHtmlEntities(s) {
    return String(s)
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, "&");
}

const HOSTILE = [
    "O'Brien'); globalThis.__pwned = 1; //",
    '"); globalThis.__pwned = 1; //',
    "\\'); globalThis.__pwned = 1; //",
    "&#39;); globalThis.__pwned = 1; //",
    "</button><img src=x onerror=globalThis.__pwned=1>",
    "a\nb'); globalThis.__pwned = 1; //",
    "`); globalThis.__pwned = 1; //",
    "${globalThis.__pwned = 1}",
];

let falhas = [];

// --- Caso 1: valor entre aspas (o caso mais comum) -----------------------
for (const payload of HOSTILE) {
    const attr = `enviar('${escapeForInlineHandler(payload)}')`;
    const js = decodeHtmlEntities(attr);

    let recebido = null;
    const enviar = (v) => { recebido = v; };
    globalThis.__pwned = 0;

    try {
        // eslint-disable-next-line no-new-func
        new Function("enviar", `return (${js});`)(enviar);
    } catch (e) {
        falhas.push(`aspas: handler quebrou com ${JSON.stringify(payload)} → ${e.message}`);
        continue;
    }
    if (globalThis.__pwned) {
        falhas.push(`XSS via aspas simples: ${JSON.stringify(payload)}`);
    }
    if (recebido !== payload) {
        falhas.push(
            `valor adulterado: esperado ${JSON.stringify(payload)} e veio ${JSON.stringify(recebido)}`
        );
    }
}

// --- Caso 2: valor SEM aspas (contexto de expressão) ---------------------
for (const payload of HOSTILE) {
    const attr = `processar(${escapeInlineExpr(payload)})`;
    const js = decodeHtmlEntities(attr);

    let recebido = null;
    const processar = (v) => { recebido = v; };
    globalThis.__pwned = 0;

    try {
        // eslint-disable-next-line no-new-func
        new Function("processar", `return (${js});`)(processar);
    } catch (e) {
        falhas.push(`sem aspas: handler quebrou com ${JSON.stringify(payload)} → ${e.message}`);
        continue;
    }
    if (globalThis.__pwned) {
        falhas.push(`XSS sem aspas: ${JSON.stringify(payload)}`);
    }
    if (recebido !== payload) {
        falhas.push(
            `sem aspas, valor adulterado: esperado ${JSON.stringify(payload)} e veio ${JSON.stringify(recebido)}`
        );
    }
}

// --- Caso 3: número continua sendo número (não vira string) -------------
const attrNum = `mostrar(${escapeInlineExpr(42)})`;
const jsNum = decodeHtmlEntities(attrNum);
let tipoNumero = null;
new Function("mostrar", `return (${jsNum});`)((v) => { tipoNumero = typeof v; });
if (tipoNumero !== "number") {
    falhas.push(`interpolação numérica virou ${tipoNumero} (esperado number)`);
}

// --- Caso 4: controle — escapeHtml sozinho NÃO protege ------------------
// Se ele protegesse, o teste de XSS estaria medindo nada.
const attrInseguro = `enviar('${escapeHtml(HOSTILE[0])}')`;
const jsInseguro = decodeHtmlEntities(attrInseguro);
globalThis.__pwned = 0;
let recebidoControle = undefined;
let quebrouControle = false;
try {
    new Function("enviar", `return (${jsInseguro});`)((v) => { recebidoControle = v; });
} catch (_) {
    quebrouControle = true;   // quebra o handler: também é falha do escapeHtml
}
const controleDemonstrouFalha =
    globalThis.__pwned === 1 || quebrouControle || recebidoControle !== HOSTILE[0];
if (!controleDemonstrouFalha) {
    falhas.push(
        "o controle não conseguiu demonstrar que escapeHtml é inseguro aqui; " +
        "o cenário do teste perdeu o sentido"
    );
}
globalThis.__pwned = 0;

if (falhas.length) {
    console.error("FALHAS (" + falhas.length + "):");
    for (const f of falhas) console.error("  - " + f);
    process.exit(1);
}
console.log("OK: handlers inline seguros contra XSS (4 cenários, " + HOSTILE.length + " payloads)");
