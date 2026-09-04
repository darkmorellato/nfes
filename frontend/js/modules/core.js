// ====================================================================
// CORE — Estado Global, Configurações de Ambiente & Helpers Básicos
// ====================================================================

const AppState = {
    ambiente: "producao",
    uf: "SP",
    certLoaded: false,
    email: "",
    nome: "",
    perfil: "",
    senha_padrao: false,
};

function getSituacaoBadgeHtml(sit) {
    let s = String(sit || "Autorizada").trim();
    if (s === "1") s = "Autorizada";
    else if (s === "2") s = "Denegada";
    else if (s === "3") s = "Cancelada";
    const sLower = s.toLowerCase();
    
    // 1. Cancelada / Denegada / Inutilizada / Desconhecimento -> Vermelha
    if (sLower.includes("cancelad") || sLower.includes("denegad") || sLower.includes("inutiliz") || sLower.includes("desconhecimento")) {
        return `<span class="badge badge-status-cancelada" style="font-size:9.5px;padding:2.5px 8px;border-radius:9999px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">🔴 ${escapeHtml(s)}</span>`;
    }
    
    // 2. Pendente / Em Processamento / Enviada / Aguardando -> Amarela
    if (sLower.includes("pendente") || sLower.includes("processamento") || sLower.includes("aguardando") || sLower.includes("enviada")) {
        return `<span class="badge badge-status-pendente" style="font-size:9.5px;padding:2.5px 8px;border-radius:9999px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">🟡 ${escapeHtml(s)}</span>`;
    }
    
    // 3. Rejeitada / Divergente / Erro / Operação Não Realizada -> Laranja
    if (sLower.includes("rejeitad") || sLower.includes("divergen") || sLower.includes("erro") || sLower.includes("não realizada")) {
        return `<span class="badge badge-status-rejeitada" style="font-size:9.5px;padding:2.5px 8px;border-radius:9999px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">🟠 ${escapeHtml(s)}</span>`;
    }
    
    // 4. Autorizada / Confirmada / Ciência / Padrão -> Verde
    return `<span class="badge badge-status-autorizada" style="font-size:9.5px;padding:2.5px 8px;border-radius:9999px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">🟢 ${escapeHtml(s)}</span>`;
}


function formatarChaveVertical(chave) {
    const raw = String(chave || "").replace(/\D/g, "");
    if (raw.length !== 44) {
        return escapeHtml(chave || "—");
    }
    const l1 = raw.slice(0, 4) + " " + raw.slice(4, 8) + " " + raw.slice(8, 12);
    const l2 = raw.slice(12, 16) + " " + raw.slice(16, 20) + " " + raw.slice(20, 24);
    const l3 = raw.slice(24, 28) + " " + raw.slice(28, 32) + " " + raw.slice(32, 36);
    const l4 = raw.slice(36, 40) + " " + raw.slice(40, 44);
    return `${l1}<br>${l2}<br>${l3}<br>${l4}`;
}

function copiarChaveAcesso(chave, btn) {
    if (!chave) return;
    const chaveSemEspaco = String(chave).replace(/\D/g, "");
    
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(chaveSemEspaco).then(() => {
            exibirFeedbackCopiaChave(btn);
        }).catch(() => {
            fallbackCopiarTexto(chaveSemEspaco);
            exibirFeedbackCopiaChave(btn);
        });
    } else {
        fallbackCopiarTexto(chaveSemEspaco);
        exibirFeedbackCopiaChave(btn);
    }
}

function fallbackCopiarTexto(texto) {
    const textArea = document.createElement("textarea");
    textArea.value = texto;
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
        document.execCommand('copy');
    } catch (err) {
        console.error('Erro no fallback de cópia:', err);
    }
    document.body.removeChild(textArea);
}

function exibirFeedbackCopiaChave(btn) {
    if (!btn) return;
    const originalContent = btn.innerHTML;
    const originalBackground = btn.style.background;
    
    btn.innerHTML = `✅ <span style="font-size:9px;font-weight:bold;color:#15803d;">Copiado!</span>`;
    btn.style.background = "var(--pastel-green-bg)";
    btn.style.borderRadius = "4px";
    btn.style.padding = "2px 6px";
    
    setTimeout(() => {
        btn.innerHTML = originalContent;
        btn.style.background = originalBackground;
        btn.style.padding = "2px 5px";
    }, 1500);
}

function init() {
    loadSettings();
    setupMenuNavigation();
    setupTabs();
    setupForms();
    setupSearch();
    setupUfPortal();
    updateBadges();
    setupHashNavigation();
    checkCertStatus();
    loadCertificatesUI();
    carregarKpisInicio();
    verificarAtualizacoes(false);
}


function setupHashNavigation() {
    const fromHash = () => {
        const hash = (window.location.hash || "").replace("#", "").trim();
        if (hash && document.getElementById(`section-${hash}`)) {
            showSection(hash);
        } else {
            showSection("inicio");
        }
    };

    window.addEventListener("hashchange", fromHash);
    fromHash();
}


function loadSettings() {
    const saved = localStorage.getItem("nfe_settings");
    if (saved) {
        try {
            const settings = JSON.parse(saved);
            AppState.ambiente = settings.ambiente || "producao";
            AppState.uf = settings.uf || "SP";
        } catch (e) {
            console.error("Erro ao carregar configurações:", e);
        }
    }

    const ambienteRadio = document.querySelector(`input[name="ambiente"][value="${AppState.ambiente}"]`);
    if (ambienteRadio) ambienteRadio.checked = true;

    const ufSelect = document.getElementById("config-uf-select");
    if (ufSelect) ufSelect.value = AppState.uf;
}


function saveSettings() {
    localStorage.setItem("nfe_settings", JSON.stringify({
        ambiente: AppState.ambiente,
        uf: AppState.uf,
    }));
}


function updateBadges() {
    const ambienteBadge = document.getElementById("breadcrumb-ambiente");
    const ufBadge = document.getElementById("breadcrumb-uf");

    if (ambienteBadge) {
        const isProd = AppState.ambiente === "producao";
        ambienteBadge.textContent = isProd ? "🟢 Produção" : "🟡 Homologação";
        ambienteBadge.classList.toggle("producao", isProd);
        ambienteBadge.title = `Ambiente Atual: ${isProd ? 'Produção (Notas Fiscais Reais)' : 'Homologação (Testes)'}. Clique para alternar.`;
    }

    if (ufBadge) {
        ufBadge.textContent = `UF: ${AppState.uf}`;
    }
}

async function alternarAmbienteRapido() {
    const isAtualProd = AppState.ambiente === "producao";
    const novoAmb = isAtualProd ? "homologacao" : "producao";
    const msgConfirm = isAtualProd
        ? "Deseja mudar para o ambiente de HOMOLOGAÇÃO (Ambiente de Testes da SEFAZ)?"
        : "⚠️ ATENÇÃO: Deseja mudar para o ambiente de PRODUÇÃO?\n\nTodas as notas emitidas terão VALIDADE JURÍDICA E FISCAL REAL perante a Receita Federal e a SEFAZ.";

    const confirma = await showConfirmModal({
        title: isAtualProd ? "Mudar para Homologação" : "Mudar para Produção",
        message: msgConfirm,
        confirmText: "Sim, alterar",
        cancelText: "Cancelar",
        icon: isAtualProd ? "🟡" : "🟢",
    });
    if (confirma) {
        AppState.ambiente = novoAmb;
        saveSettings();
        updateBadges();

        const ambienteRadio = document.querySelector(`input[name="ambiente"][value="${AppState.ambiente}"]`);
        if (ambienteRadio) ambienteRadio.checked = true;

        if (typeof verificarStatusSefazRealtime === "function") verificarStatusSefazRealtime(false);
        if (typeof atualizarProximoNumeroNfe === "function") atualizarProximoNumeroNfe();

        toast.success(`Ambiente alterado com sucesso para: ${AppState.ambiente === "producao" ? "PRODUÇÃO" : "HOMOLOGAÇÃO"}`);
    }
}



window.AppState = AppState;

// Áudio e Alertas Sonoros
function tocarSomAlerta(tipo = "info") {
    try {
        const audioHabilitado = localStorage.getItem("nfe_audio_alert_enabled") !== "false";
        if (!audioHabilitado) return;

        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;

        const ctx = new AudioCtx();
        if (ctx.state === "suspended") {
            ctx.resume();
        }

        const now = ctx.currentTime;
        let freqs = [587.33, 880.00]; // D5 -> A5
        if (tipo === "alerta" || tipo === "cancelamento") {
            freqs = [783.99, 659.25, 523.25]; // G5 -> E5 -> C5
        } else if (tipo === "cc_e" || tipo === "nfe_nova") {
            freqs = [523.25, 659.25, 783.99, 1046.50]; // C5 -> E5 -> G5 -> C6
        }

        freqs.forEach((freq, idx) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now + idx * 0.11);

            gain.gain.setValueAtTime(0, now + idx * 0.11);
            gain.gain.linearRampToValueAtTime(0.18, now + idx * 0.11 + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.11 + 0.32);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(now + idx * 0.11);
            osc.stop(now + idx * 0.11 + 0.33);
        });
    } catch (e) {
        console.warn("Áudio Web não disponível:", e);
    }
}

function toggleAudioAlerts(enabled) {
    localStorage.setItem("nfe_audio_alert_enabled", enabled ? "true" : "false");
    toast.info(`Alertas sonoros ${enabled ? 'ativados' : 'desativados'}.`);
}

function testarSomAlertaWeb() {
    tocarSomAlerta("cc_e");
    toast.success("🔊 Som de alerta reproduzido com sucesso!");
}

window._lastNotifTimestamp = null;


// Busca e Portais
function setupSearch() {
    const btnBuscar = document.getElementById("btnBuscar");
    const campoBusca = document.getElementById("campoBusca");

    const doSearch = () => {
        const termo = (campoBusca?.value || "").trim();
        if (termo) {
            window.open(`https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx`, "_blank");
        }
    };

    if (btnBuscar) btnBuscar.addEventListener("click", (e) => { e.preventDefault(); doSearch(); });
    if (campoBusca) campoBusca.addEventListener("keypress", (e) => {
        if (e.key === "Enter") { e.preventDefault(); doSearch(); }
    });
}


function setupUfPortal() {
    const select = document.getElementById("selectUfPortal");
    if (select) {
        select.addEventListener("change", function () {
            if (this.value) window.open(this.value, "_blank");
            this.value = "";
        });
    }
}



// Formulários Principais
function setupForms() {
    document.getElementById("form-status")?.addEventListener("submit", handleStatusServico);
    document.getElementById("form-consulta-chave")?.addEventListener("submit", handleConsultaChave);
    document.getElementById("form-consulta-cadastro")?.addEventListener("submit", handleConsultaCadastro);
    document.getElementById("form-manifestacao")?.addEventListener("submit", handleManifestacao);
    document.getElementById("form-cert-upload")?.addEventListener("submit", handleCertUpload);
    document.getElementById("btn-cert-info")?.addEventListener("click", showCertInfo);
    document.getElementById("form-config-ambiente")?.addEventListener("submit", handleConfigAmbiente);
    document.getElementById("form-config-uf")?.addEventListener("submit", handleConfigUF);
    document.getElementById("form-rel-status")?.addEventListener("submit", handleRelStatus);
    document.getElementById("form-rel-volume")?.addEventListener("submit", handleRelVolume);
    document.getElementById("form-rel-compliance")?.addEventListener("submit", handleRelCompliance);
    document.getElementById("form-rel-emissores")?.addEventListener("submit", handleRelEmissores);
    document.getElementById("form-danfe-chave")?.addEventListener("submit", handleDanfeChave);
    document.getElementById("form-danfe-upload")?.addEventListener("submit", handleDanfeUpload);
    document.getElementById("form-ncm")?.addEventListener("submit", handleNcm);
    document.getElementById("form-gtin")?.addEventListener("submit", handleGtin);
    document.getElementById("form-ccc")?.addEventListener("submit", handleCcc);
    document.getElementById("form-distribuicao")?.addEventListener("submit", handleDistribuicao);
    document.getElementById("form-epec")?.addEventListener("submit", handleEpec);
    document.getElementById("btn-distribuicao-proximo")?.addEventListener("click", handleDistribuicaoProximo);
    document.getElementById("btn-distribuicao-nsu")?.addEventListener("click", handleDistribuicaoNsuEspecifico);
    document.getElementById("form-inutilizacao")?.addEventListener("submit", handleInutilizacao);
    document.getElementById("btn-inu-consultar")?.addEventListener("click", handleInutilizacaoConsulta);
    document.getElementById("form-carta-correcao")?.addEventListener("submit", handleCartaCorrecao);
    document.getElementById("form-cancelamento")?.addEventListener("submit", handleCancelamento);
    // Novos formulários de Gestão
    document.getElementById("form-gestao-filtro")?.addEventListener("submit", handleGestaoFiltro);
    document.getElementById("btn-gestao-limpar")?.addEventListener("click", handleGestaoLimpar);
    document.getElementById("btn-sync-executar-agora")?.addEventListener("click", handleSyncExecutarAgora);
    document.getElementById("btn-sync-atualizar-status")?.addEventListener("click", loadSyncStatus);
    document.getElementById("btn-debug-nfe")?.addEventListener("click", abrirDebugNfe);
    document.getElementById("form-sync-config")?.addEventListener("submit", handleSyncConfig);
    document.getElementById("form-analytics-periodo")?.addEventListener("submit", handleAnalyticsPeriodo);
    document.getElementById("form-analytics-precos")?.addEventListener("submit", handleAnalyticsPrecos);
    document.getElementById("form-contabil-exportar")?.addEventListener("submit", handleContabilExportar);
    document.getElementById("contabil-mes")?.addEventListener("change", loadContabilPrevia);
    document.getElementById("contabil-ano")?.addEventListener("change", loadContabilPrevia);
    document.getElementById("gestao-input-xml-lote")?.addEventListener("change", handleImportXmlLote);

    // Formulários de Conta (Configurações)
    document.getElementById("form-alterar-senha")?.addEventListener("submit", handleAlterarSenha);
    document.getElementById("form-alterar-email")?.addEventListener("submit", handleAlterarEmail);
}


// Validações GTIN
function gtinTipoProduto(prefixo3) {
    const p = parseInt(prefixo3, 10);
    if (isNaN(p)) return "Desconhecido";
    if (p >= 789 && p <= 790) return "Brasil (GS1 Brasil)";
    if (p >= 0 && p <= 19) return "EUA / Canadá (UCC)";
    if (p >= 300 && p <= 379) return "França (GS1 France)";
    if (p >= 400 && p <= 440) return "Alemanha (GS1 Germany)";
    if (p >= 450 && p <= 459) return "Japão (GS1 Japan)";
    if (p >= 460 && p <= 469) return "Rússia (GS1 Russia)";
    if (p >= 470 && p <= 479) return "Quirguistão (GS1 Kyrgyzstan)";
    if (p >= 480 && p <= 489) return "Taiwan (GS1 Taiwan)";
    if (p >= 490 && p <= 499) return "Japão (GS1 Japan)";
    if (p >= 500 && p <= 509) return "Reino Unido (GS1 UK)";
    if (p >= 520 && p <= 521) return "Grécia (GS1 Greece)";
    if (p >= 540 && p <= 549) return "Bélgica/Luxemburgo (GS1 Belgium/Luxembourg)";
    if (p >= 560 && p <= 569) return "Portugal (GS1 Portugal)";
    if (p >= 570 && p <= 579) return "Dinamarca (GS1 Denmark)";
    if (p >= 590 && p <= 599) return "Polônia (GS1 Poland)";
    if (p >= 600 && p <= 601) return "África do Sul (GS1 South Africa)";
    if (p >= 640 && p <= 649) return "Finlândia (GS1 Finland)";
    if (p >= 690 && p <= 699) return "China (GS1 China)";
    if (p >= 700 && p <= 709) return "Noruega (GS1 Norway)";
    if (p >= 729 && p <= 729) return "Israel (GS1 Israel)";
    if (p >= 730 && p <= 739) return "Suécia (GS1 Sweden)";
    if (p >= 740 && p <= 749) return "Uruguai (GS1 Uruguay)";
    if (p >= 750 && p <= 759) return "México (GS1 Mexico)";
    if (p >= 760 && p <= 769) return "Suíça (GS1 Switzerland)";
    if (p >= 770 && p <= 779) return "Colômbia (GS1 Colombia)";
    if (p >= 780 && p <= 789) return "Chile (GS1 Chile)";
    if (p >= 790 && p <= 799) return "Argentina (GS1 Argentina)";
    if (p >= 800 && p <= 839) return "Itália (GS1 Italy)";
    if (p >= 840 && p <= 849) return "Espanha (GS1 Spain)";
    if (p >= 850 && p <= 859) return "Cuba (GS1 Cuba)";
    if (p >= 860 && p <= 869) return "Turquia (GS1 Turkey)";
    if (p >= 870 && p <= 879) return "Holanda (GS1 Netherlands)";
    if (p >= 880 && p <= 889) return "Coreia do Sul (GS1 South Korea)";
    if (p >= 890 && p <= 899) return "Índia (GS1 India)";
    if (p >= 900 && p <= 919) return "Áustria (GS1 Austria)";
    if (p >= 930 && p <= 939) return "Austrália (GS1 Australia)";
    if (p >= 940 && p <= 949) return "Nova Zelândia (GS1 New Zealand)";
    if (p >= 950 && p <= 959) return "GS1 Global Office";
    return "Prefixo GS1 internacional";
}

function validarGTIN(codigo) {
    const digits = String(codigo || "").replace(/\D/g, "");
    if (!digits) {
        return { valido: false, codigo: "", tipo: "Inválido", comprimento: 0, digito: null, erro: "Código vazio" };
    }
    const compr = [8, 12, 13, 14].indexOf(digits.length) === -1 ? 0 : digits.length;
    if (compr === 0) {
        return { valido: false, codigo: digits, tipo: "Comprimento inválido", comprimento: digits.length, digito: null, erro: "GTIN deve ter 8, 12, 13 ou 14 dígitos" };
    }
    const corpo = digits.slice(0, -1);
    const dvInformado = parseInt(digits.slice(-1), 10);
    let soma = 0;
    let multiplicador = 3;
    for (let i = corpo.length - 1; i >= 0; i--) {
        soma += parseInt(corpo[i], 10) * multiplicador;
        multiplicador = (multiplicador === 3) ? 1 : 3;
    }
    const resto = soma % 10;
    const dvCalculado = (resto === 0) ? 0 : (10 - resto);
    const valido = dvCalculado === dvInformado;
    return {
        valido,
        codigo: digits,
        tipo: "GTIN-" + compr,
        comprimento: compr,
        digito: dvInformado,
        digitoCalculado: dvCalculado,
        pais: gtinTipoProduto(digits.substring(0, 3)),
    };
}


// Helpers de UI e Download
function showResult(elementId, data, type = "info") {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.style.display = "block";
    element.className = `result ${type}`;

    if (data && data.error && !data.status_code) {
        element.classList.add("error");
        element.innerHTML = `<pre>${data.error}</pre>`;
        return;
    }

    if (typeof data === "object") {
        element.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    } else {
        element.innerHTML = `<pre>${data}</pre>`;
    }
}


function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    element.style.display = "block";
    element.className = "result info";
    element.innerHTML = "<p>Processando, aguarde...</p>";
}


async function downloadPdf(url, filename) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
        toast.error("Erro ao gerar relatório: " + error.message);
    }
}
