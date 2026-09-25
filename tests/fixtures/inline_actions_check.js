/**
 * Prova que a delegação de handlers (inline-actions.js) reproduz a semântica
 * dos antigos atributos inline — sem eval e sem 'unsafe-inline'.
 *
 * Uso: node inline_actions_check.js <frontend/js/inline-actions.js>
 */
const fs = require("fs");

const caminho = process.argv[2];
if (!caminho || !fs.existsSync(caminho)) {
    consoleReal.error("inline-actions.js não encontrado: " + caminho);
    process.exit(2);
}

const falhas = [];
const consoleReal = console;   // preserva o console antes do stub

/* ------------------------------------------------------------------ */
/* DOM mínimo: captura os listeners registrados pela runtime           */
/* ------------------------------------------------------------------ */
const listeners = {};

global.window = global;
global.document = {
    addEventListener(tipo, fn) {
        (listeners[tipo] = listeners[tipo] || []).push(fn);
    },
    getElementById() { return null; },
};

let consoleErros = [];
global.console = {
    log() {},
    warn() {},
    error(...a) { consoleErros.push(a.join(" ")); },
};

// Carrega a runtime (registra os listeners)
eval(fs.readFileSync(caminho, "utf8"));

const tipos = Object.keys(listeners);
if (!tipos.includes("click") || !tipos.includes("submit")) {
    falhas.push("a runtime não registrou os listeners de click/submit: " + tipos.join(","));
}

/* ------------------------------------------------------------------ */
/* Elemento falso com cadeia de ancestrais                             */
/* ------------------------------------------------------------------ */
function elemento(attrs, pai) {
    const el = {
        attrs: attrs || {},
        parentElement: pai || null,
        getAttribute(nome) { return this.attrs[nome] || null; },
        closest(seletor) {
            const nome = seletor.replace(/[[\]]/g, "");
            let atual = this;
            while (atual) {
                if (atual.attrs[nome] !== undefined && atual.attrs[nome] !== null) return atual;
                atual = atual.parentElement;
            }
            return null;
        },
    };
    return el;
}

function disparar(tipo, alvo, extra) {
    const ev = Object.assign({
        type: tipo,
        target: alvo,
        currentTarget: null,
        cancelBubble: false,
        defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; },
        stopPropagation() { this.cancelBubble = true; },
    }, extra || {});

    // A runtime usa currentTarget = elemento com o atributo; simulamos isso
    // percorrendo como o navegador faria: listener único no document.
    for (const fn of listeners[tipo] || []) fn(ev);
    return ev;
}

/* ------------------------------------------------------------------ */
/* 1) Chamada simples com argumentos literais                          */
/* ------------------------------------------------------------------ */
let chamada = null;
global.showSection = (nome) => { chamada = nome; };

let alvo = elemento({
    "data-onclick": JSON.stringify({ fn: "showSection", args: ["gestao-docs"], ret: true }),
});
let ev = disparar("click", alvo);
if (chamada !== "gestao-docs") falhas.push(`argumento não repassado: ${chamada}`);
if (!ev.defaultPrevented) falhas.push("ret:true não chamou preventDefault()");

/* ------------------------------------------------------------------ */
/* 2) $event e $this                                                    */
/* ------------------------------------------------------------------ */
let recebido = { ev: null, el: null };
global.pegarTudo = (evArg, elArg) => { recebido = { ev: evArg, el: elArg }; };

const elementoComHandler = elemento({
    "data-onchange": JSON.stringify({ fn: "pegarTudo", args: ["$event", "$this"] }),
});
disparar("change", elementoComHandler);
if (recebido.ev === null) falhas.push("$event não foi repassado");
if (recebido.el !== elementoComHandler) falhas.push("$this não é o elemento com o atributo");

/* ------------------------------------------------------------------ */
/* 3) Sequência de comandos (ordem preservada)                          */
/* ------------------------------------------------------------------ */
const ordem = [];
global.fecharDrawer = () => ordem.push("fechar");
global.verDanfe = (ch) => ordem.push("danfe:" + ch);

alvo = elemento({
    "data-onclick": JSON.stringify({
        seq: [
            { fn: "fecharDrawer", args: [] },
            { fn: "verDanfe", args: ["351234..."] },
        ],
    }),
});
disparar("click", alvo);
if (ordem.join("|") !== "fechar|danfe:351234...") {
    falhas.push("seq fora de ordem: " + ordem.join("|"));
}

/* ------------------------------------------------------------------ */
/* 4) stopPropagation impede o ancestral                               */
/* ------------------------------------------------------------------ */
const disparos = [];
global.pararPropagacao = (ev) => ev.stopPropagation();
global.ancestral = () => disparos.push("ancestral");

const pai = elemento({ "data-onclick": JSON.stringify({ fn: "ancestral", args: [] }) });
const filho = elemento({ "data-onclick": JSON.stringify({ fn: "pararPropagacao", args: ["$event"] }) }, pai);
disparar("click", filho);
if (disparos.length !== 0) {
    falhas.push("stopPropagation no filho não impediu o ancestral (inline fazia isso)");
}

// Sem stopPropagation, o ancestral também roda (como nos handlers inline)
disparos.length = 0;
const filhoSemStop = elemento({ "data-onclick": JSON.stringify({ fn: "ancestral", args: [] }) }, pai);
disparar("click", filhoSemStop);
if (disparos.length !== 2) {
    falhas.push(`esperava filho+ancestral (2 disparos) e houve ${disparos.length}`);
}

/* ------------------------------------------------------------------ */
/* 5) Função desconhecida não derruba a página                         */
/* ------------------------------------------------------------------ */
consoleErros = [];
alvo = elemento({ "data-onclick": JSON.stringify({ fn: "funcaoQueNaoExiste", args: [] }) });
disparar("click", alvo);
if (!consoleErros.some((m) => m.includes("funcaoQueNaoExiste"))) {
    falhas.push("função desconhecida não foi reportada em log");
}

/* ------------------------------------------------------------------ */
/* 6) JSON malformado não derruba a página                             */
/* ------------------------------------------------------------------ */
consoleErros = [];
alvo = elemento({ "data-onclick": "{isso nao e json}" });
disparar("click", alvo);
if (!consoleErros.some((m) => m.includes("JSON inválido"))) {
    falhas.push("JSON inválido não foi reportado em log");
}

/* ------------------------------------------------------------------ */
/* 7) Erro dentro de um handler é isolado                              */
/* ------------------------------------------------------------------ */
consoleErros = [];
global.quebra = () => { throw new Error("boom"); };
alvo = elemento({ "data-onclick": JSON.stringify({ fn: "quebra", args: [] }) });
disparar("click", alvo);
if (!consoleErros.some((m) => m.includes("boom"))) {
    falhas.push("exceção do handler não foi capturada");
}

if (falhas.length) {
    consoleReal.error("FALHAS (" + falhas.length + "):");
    for (const f of falhas) consoleReal.error("  - " + f);
    process.exit(1);
}
consoleReal.log("OK: delegação de handlers reproduz a semântica inline (7 cenários)");
