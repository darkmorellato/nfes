/**
 * Delegação de eventos dos elementos (substitui os handlers inline).
 *
 * Por quê: o CSP com `script-src 'self'` **bloqueia** `onclick="..."`, `onchange="..."`
 * e companhia. Como o index.html tem mais de 200 desses e o restante do sistema
 * precisa de um CSP que impeça XSS injetado por terceiros, os handlers viram
 * atributos de dados e passam a ser resolvidos aqui.
 *
 * Formato:
 *     data-onclick='{"fn":"showSection","args":["gestao-docs"],"ret":false}'
 *
 * - `fn`  → função global chamada (verificada: só chama o que existe);
 * - `args`→ array JSON; os marcadores especiais são:
 *              "$event" → o objeto Event disparado;
 *              "$this"  → o elemento que disparou (event.currentTarget);
 * - `ret` → true quando o handler original tinha `return false`
 *           (equivalente a event.preventDefault()).
 *
 * Nada aqui usa eval/new Function: o JSON é apenas serialização de DADOS.
 */
(function () {
    "use strict";

    var EVENTOS = ["click", "change", "submit", "input", "blur", "focus", "dblclick", "keydown", "keyup"];

    function montarArgumentos(spec, evento, elemento) {
        var args = spec && spec.args;
        if (!Array.isArray(args)) return [];
        return args.map(function (a) {
            if (a === "$event") return evento;
            if (a === "$this") return elemento;
            return a;
        });
    }

    /**
     * Resolve `fn` contra `window`, aceitando caminho pontilhado
     * (`toast.success`, `navigator.clipboard.writeText`).
     */
    function resolverFuncao(caminho) {
        if (typeof caminho !== "string" || !caminho) return null;
        var partes = caminho.split(".");
        var atual = window;
        for (var i = 0; i < partes.length; i++) {
            if (atual === null || atual === undefined) return null;
            atual = atual[partes[i]];
        }
        return typeof atual === "function" ? { fn: atual, dono: null } : null;
    }

    function executar(spec, evento, elemento) {
        if (spec.stop && evento.stopPropagation) evento.stopPropagation();

        // `seq` reproduz handlers compostos (ex.: fechar modal e abrir outro)
        var passos = Array.isArray(spec.seq) ? spec.seq : [spec];
        for (var i = 0; i < passos.length; i++) {
            var passo = passos[i];
            var alvo = resolverFuncao(passo.fn);
            if (!alvo) {
                if (window.console && console.error) {
                    console.error("[inline-actions] função desconhecida: " + passo.fn);
                }
                return;
            }
            try {
                alvo.fn.apply(elemento, montarArgumentos(passo, evento, elemento));
            } catch (erro) {
                if (window.console && console.error) {
                    console.error("[inline-actions] erro em " + passo.fn + ":", erro);
                }
                return;
            }
            // Um passo pode ter interrompido a propagação.
            if (evento.cancelBubble) return;
        }
    }

    function resolverSpec(elemento, nome) {
        var bruto = elemento.getAttribute(nome);
        if (!bruto) return null;
        try {
            var spec = JSON.parse(bruto);
            // Aceita chamada simples (`fn`) ou sequência (`seq`).
            var valido = spec && (
                typeof spec.fn === "string" ||
                (Array.isArray(spec.seq) && spec.seq.length > 0)
            );
            return valido ? spec : null;
        } catch (e) {
            // Handler malformado não deve derrubar a página inteira.
            if (window.console && console.error) {
                console.error("[inline-actions] JSON inválido em " + nome + ": " + bruto);
            }
            return null;
        }
    }

    /**
     * Reproduz a semântica dos handlers inline: o elemento mais próximo dispara
     * primeiro e, se o handler não interromper a propagação, os ancestrais
     * seguem em ordem. Um simples `closest()` ignoraria os ancestrais — e é
     * exatamente o que o overlay do command palette dependia de `stopPropagation`.
     */
    function despachar(evento, tipo) {
        var alvo = evento.target;
        if (!alvo || typeof alvo.closest !== "function") return;

        // O atributo gerado é `data-on<evento>` (ex.: data-onclick), não `data-<evento>`.
        var atributo = "data-on" + tipo;
        // Primeiro o elemento mais próximo; depois sobe enquanto não forem parados.
        var elemento = alvo.closest("[" + atributo + "]");
        while (elemento && !evento.cancelBubble) {
            var spec = resolverSpec(elemento, atributo);
            if (spec) {
                if (spec.ret) evento.preventDefault();
                executar(spec, evento, elemento);
            }
            elemento = elemento.parentElement
                ? elemento.parentElement.closest("[" + atributo + "]")
                : null;
        }
    }

    EVENTOS.forEach(function (tipo) {
        document.addEventListener(tipo, function (evento) {
            despachar(evento, tipo);
        }, false);
    });
})();


/* =========================================================================
   Funções auxiliares dos 28 handlers que não eram uma chamada simples.
   Cada uma corresponde a um antigo atributo inline do index.html.
   ========================================================================= */

/** Antigo: onclick="document.getElementById('gestao-input-xml-lote').click();" */
function abrirInputXmlLote() {
    document.getElementById("gestao-input-xml-lote")?.click();
}

/** Antigo: onclick="document.getElementById('input-arquivos-import-saidas').click();" */
function abrirSeletorArquivosSaidas() {
    document.getElementById("input-arquivos-import-saidas")?.click();
}

/** Antigo: onchange="atualizarProximoNumeroNfe(); atualizarCardEmitenteInfo();" */
function aoMudarSerieEmissao() {
    atualizarProximoNumeroNfe();
    atualizarCardEmitenteInfo();
}

/** Antigo: onclick="document.getElementById('emissao-chave-referenciada').value='';" */
function limparChaveReferenciada() {
    const campo = document.getElementById("emissao-chave-referenciada");
    if (campo) campo.value = "";
    const card = document.getElementById("card-chave-referenciada");
    if (card) card.style.display = "none";
}

/** Antigo: onchange="sincronizarAbaSituacao(this.value); carregarNfeSaidas(1);" */
function aoMudarFiltroSituacao(evento) {
    const valor = (evento && evento.currentTarget ? evento.currentTarget.value : "") || "";
    sincronizarAbaSituacao(valor);
    carregarNfeSaidas(1);
}

/** Antigo: onsubmit="event.preventDefault(); toast.warning('EPEC...');" */
function epecNaoImplementada(evento) {
    if (evento) evento.preventDefault();
    if (typeof toast !== "undefined") {
        toast.warning("Registro de EPEC não implementado: requer webservice dedicado não exposto pela PyNFe.");
    }
}

/** Antigo: onsubmit="event.preventDefault(); carregarLimpezaPreview();" */
function aoEnviarPreviewLimpeza(evento) {
    if (evento) evento.preventDefault();
    carregarLimpezaPreview();
}

/** Antigo: onblur="buscarCepViaCep(document.getElementById('emissao-dest-cep').value);" */
function buscarCepDestinoInformando() {
    const campo = document.getElementById("emissao-dest-cep");
    buscarCepViaCep(campo ? campo.value : "");
}

/** Antigo: onblur="buscarCepCertViaCep(document.getElementById('modal-cert-fiscal-cep').value);" */
function buscarCepCertificadoInformando() {
    const campo = document.getElementById("modal-cert-fiscal-cep");
    buscarCepCertViaCep(campo ? campo.value : "");
}

/** Antigo: onclick="document.getElementById('modal-debug-nfe').style.display='none'" */
function fecharModalDebugNfe() {
    const modal = document.getElementById("modal-debug-nfe");
    if (modal) modal.style.display = "none";
}

/** Antigo: onclick="if(event.target===this) fecharCommandPalette();" */
function aoClicarOverlayCommandPalette(evento) {
    const overlay = evento && evento.currentTarget;
    if (evento && overlay && evento.target === overlay) fecharCommandPalette();
}

/** Antigo: onclick="event.stopPropagation()" (contêiner do command palette). */
function pararPropagacao(evento) {
    if (evento) evento.stopPropagation();
}

/** Antigo: onclick="location.reload()" */
function recarregarPagina() {
    window.location.reload();
}

/** Antigo: onchange de `emissao-chave-referenciada` + trocar para a aba DANFE. */
function visualizarDANFEDaChave(chave) {
    const campo = document.getElementById("danfe-chave-input");
    if (campo) campo.value = chave;
    showSection("danfe");
    switchTab("tab-chave-danfe");
    document.getElementById("form-danfe-chave")?.dispatchEvent(
        new Event("submit", { cancelable: true })
    );
}

/** Antigo: oninput de `distribuicao-nsu` + disparar o formulário de distribuição. */
function aplicarNsuEDistribuir(valor) {
    const campo = document.getElementById("distribuicao-nsu");
    if (campo) campo.value = valor;
    document.getElementById("form-distribuicao")?.dispatchEvent(
        new Event("submit", { cancelable: true })
    );
}

/** Estilos de foco dos campos de login (antes onfocus/onblur inline). */
function realcarCampoAuth(campo) {
    if (!campo) return;
    campo.style.borderColor = "#4b6a82";
    campo.style.background = "#fff";
}

function soltarCampoAuth(campo) {
    if (!campo) return;
    campo.style.borderColor = "#e6e1d8";
    campo.style.background = "#faf8f5";
}

/** Botão ✕ do banner de cooldown da SEFAZ. */
function fecharBannerCooldownSeFaz() {
    const banner = document.getElementById("global-sefaz-cooldown-banner");
    if (banner) banner.style.display = "none";
}

/**
 * Abre a gaveta de detalhes apenas se o clique NÃO foi num botão/input/link
 * da linha.
 *
 * Antigo: `onclick="if (!event.target.closest('button, input, a')) abrirDrawerDetalhes('…')"`.
 * A guarda é essencial: sem ela, clicar em "📋 Copiar" ou em qualquer ação da
 * linha também abriria a gaveta por cima.
 */
function abrirDrawerDetalhesSeNaoAlvo(evento, chave) {
    if (evento && evento.target && typeof evento.target.closest === "function"
        && evento.target.closest("button, input, a, select, textarea")) {
        return;
    }
    abrirDrawerDetalhes(chave);
}

/** Antigo: onclick="window.print()" — `window.print` não é função global chamável. */
function imprimirPagina() {
    window.print();
}

/**
 * Botão "➕ Adicionar certificado A1" da lista de certificados.
 *
 * A função foi referenciada desde sempre mas nunca existiu — o clique não fazia
 * nada. Agora leva à aba de certificados e abre o seletor de arquivo.
 */
function abrirModalCadCert() {
    if (typeof showSection === "function") showSection("certificado");
    const campo = document.getElementById("cert-file");
    if (campo) {
        campo.scrollIntoView({ behavior: "smooth", block: "center" });
        campo.click();
    }
}
