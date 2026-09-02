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
    const s = String(sit || "Autorizada").trim();
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


function setupMenuNavigation() {
    document.querySelectorAll("[data-section-link]").forEach(el => {
        el.addEventListener("click", function (e) {
            e.preventDefault();
            const section = this.dataset.sectionLink;
            const tab = this.dataset.tab;
            showSection(section);
            if (tab) switchTab(tab);
        });
    });
}


function showSection(sectionId) {
    document.querySelectorAll(".content-section").forEach(s => s.classList.remove("active"));
    const target = document.getElementById(`section-${sectionId}`);
    if (target) target.classList.add("active");

    // Marca item ativo no menu de 2 linhas
    document.querySelectorAll("ul.abasMenu > li").forEach(li => {
        li.classList.remove("active");
        const link = li.querySelector("a[data-section-link]");
        if (link && link.dataset.sectionLink === sectionId) {
            li.classList.add("active");
        } else {
            const subLink = li.querySelector(`a[data-section-link="${sectionId}"]`);
            if (subLink) li.classList.add("active");
        }
    });

    const breadcrumb = document.getElementById("breadcrumb-atual");
    if (breadcrumb && SECTION_TITLES[sectionId]) {
        breadcrumb.innerHTML = SECTION_TITLES[sectionId];
    }

    if (window.location.hash !== `#${sectionId}`) {
        history.replaceState(null, "", `#${sectionId}`);
    }

    if (sectionId === "inicio") { loadCertificatesUI(); carregarKpisInicio(); }
    if (sectionId === "gestao-docs") loadGestaoDocs(1);
    if (sectionId === "gestao-sync") { loadSyncStatus(); loadCertificatesUI(); }
    if (sectionId === "gestao-analytics") { loadAnalyticsDashboard(); carregarDivergenciasPreco(); carregarAuditoriaFornecedores(); }
    if (sectionId === "gestao-intercompany") carregarIntercompany();
    if (sectionId === "gestao-financeiro") { carregarFinanceiro(); }
    if (sectionId === "gestao-conferencia") carregarConferenciaEstoque();
    if (sectionId === "emissor-rapido") carregarEmissorRapido();
    if (sectionId === "gestao-contabil") { loadContabilPrevia(); loadCertificatesUI(); }
    if (sectionId === "certificado") loadCertificatesUI();
    if (sectionId === "config") {
        loadContaInfo();
        carregarConfigNotificacoes();
        carregarAuditoriaBase();
        carregarLimpezaPreview("homologacao");
        verificarAtualizacoes(false);
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}


async function carregarKpisInicio() {
    try {
        const resSn = await apiGet("/api/gestao/tributacao/simples-nacional");
        if (resSn && resSn.receita_mes !== undefined) {
            const elFat = document.getElementById("inicio-kpi-faturamento");
            if (elFat) elFat.textContent = `R$ ${Number(resSn.receita_mes).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            
            const elDas = document.getElementById("inicio-kpi-das");
            if (elDas) elDas.textContent = `R$ ${Number(resSn.valor_das_estimado).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }

        const resDash = await apiGet("/api/gestao/analytics/dashboard");
        if (resDash && resDash.total_valor_compras !== undefined) {
            const elEnt = document.getElementById("inicio-kpi-entradas");
            if (elEnt) elEnt.textContent = `R$ ${Number(resDash.total_valor_compras).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
    } catch (e) {
        console.warn("Erro ao carregar KPIs do início:", e);
    }
}


function setupTabs() {
    document.querySelectorAll(".ajax__tab_tab").forEach(tab => {
        tab.addEventListener("click", function () {
            switchTab(this.dataset.tab);
        });
    });
}


function switchTab(tabId) {
    document.querySelectorAll(".ajax__tab_tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    const tab = document.querySelector(`.ajax__tab_tab[data-tab="${tabId}"]`);
    const content = document.getElementById(tabId);

    if (tab) tab.classList.add("active");
    if (content) content.classList.add("active");

    if (tabId === "tab-cfg-gaps") {
        carregarAuditoriaGaps();
    } else if (tabId === "tab-cfg-auditoria") {
        carregarAuditoriaBase();
    } else if (tabId === "tab-cfg-orfaos") {
        carregarAuditoriaXmlsOrfaos();
    }
}

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

async function carregarNotificacoes() {
    try {
        const res = await apiGet("/api/gestao/notificacoes?limit=25");
        if (!res.success) return;

        const notifs = res.data || [];
        const unreadCount = notifs.filter(n => !n.read).length;

        // Toca som se houver nova notificação não lida mais recente
        if (notifs.length > 0) {
            const maisRecente = notifs[0];
            const ts = maisRecente.created_at || maisRecente.id;
            if (window._lastNotifTimestamp && ts !== window._lastNotifTimestamp && !maisRecente.read) {
                tocarSomAlerta(maisRecente.tipo || "info");
            }
            window._lastNotifTimestamp = ts;
        }

        const badge = document.getElementById("notif-unread-badge");
        if (badge) {
            if (unreadCount > 0) {
                badge.textContent = unreadCount;
                badge.style.display = "inline-block";
            } else {
                badge.style.display = "none";
            }
        }

        const feedLista = document.getElementById("notif-feed-lista");
        if (feedLista) {
            if (notifs.length === 0) {
                renderEmptyState({
                    icon: '🔔',
                    title: 'Nenhuma notificação',
                    description: 'Você está em dia! Não há notificações pendentes.',
                    containerId: 'notif-feed-lista',
                });
            } else {
                feedLista.innerHTML = notifs.map(n => {
                    let cor = "#2980b9";
                    let icone = "ℹ️";
                    if (n.tipo === "nfe_nova") { cor = "#27ae60"; icone = "📦"; }
                    else if (n.tipo === "cancelamento") { cor = "#c0392b"; icone = "⚠️"; }
                    else if (n.tipo === "cc_e") { cor = "#4f46e5"; icone = "📜"; }
                    else if (n.tipo === "alerta" || n.tipo === "alerta_alto_valor") { cor = "#d97706"; icone = "🚨"; }

                    const dt = n.created_at ? new Date(n.created_at).toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' }) : "";
                    const zapText = encodeURIComponent(`🚨 *${n.title || 'Alerta Fiscal'}*\n\n${n.message || ''}${n.chave ? '\nChave: ' + n.chave : ''}`);

                    return `
                        <div style="background:${n.read ? '#fff' : '#f0f8ff'};border:1px solid ${n.read ? '#eee' : '#b9dcf7'};border-left:3px solid ${cor};padding:8px 10px;margin-bottom:6px;border-radius:4px;font-size:11px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b style="color:${cor};">${icone} ${escapeHtml(n.title || "Notificação")}</b>
                                <small style="color:#888;">${escapeHtml(dt)}</small>
                            </div>
                            <div style="color:#444;margin-top:3px;">${escapeHtml(n.message || "")}</div>
                            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                                ${n.chave ? `<button type="button" class="botao" onclick="fecharNotificacoesEVerDanfe('${n.chave}');" style="font-size:10px;padding:2px 6px;">👁️ Ver DANFE</button>` : ""}
                                <a href="https://api.whatsapp.com/send?phone=5519989354849&text=${zapText}" target="_blank" class="botao" style="font-size:10px;padding:2px 6px;background:#25d366;color:#fff;border-color:#25d366;text-decoration:none;display:inline-flex;align-items:center;gap:3px;" title="Enviar para +55 19 98935-4849">
                                    💬 Whats 1
                                </a>
                                <a href="https://api.whatsapp.com/send?phone=5519990151809&text=${zapText}" target="_blank" class="botao" style="font-size:10px;padding:2px 6px;background:#25d366;color:#fff;border-color:#25d366;text-decoration:none;display:inline-flex;align-items:center;gap:3px;" title="Enviar para +55 19 99015-1809">
                                    💬 Whats 2
                                </a>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }
    } catch (err) {
        console.warn("Erro ao buscar notificações:", err);
    }
}


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

function handleNcm(e) {
    e.preventDefault();
    const termo = (document.getElementById("ncm-input").value || "").trim().toLowerCase();
    const resultado = document.getElementById("ncm-resultado");
    if (!termo) {
        resultado.style.display = "none";
        return;
    }
    const encontrados = NCM_TABLE.filter(row =>
        row[0].toLowerCase().includes(termo) || row[1].toLowerCase().includes(termo)
    );
    const linhas = (encontrados.length ? encontrados : NCM_TABLE).map(row => `
        <tr class="linha">
            <td><b>${row[0]}</b></td>
            <td>${row[1]}</td>
            <td>${row[2]}</td>
            <td>${row[3]}</td>
            <td>${row[4]}</td>
            <td>${row[5]}</td>
            <td>${row[6]}</td>
        </tr>
    `).join("");
    resultado.style.display = "block";
    resultado.className = "ncm-tabela";
    resultado.innerHTML = `
        <div class="painelSessaoTitulo">Resultados da Consulta NCM ${encontrados.length ? `(${encontrados.length})` : `(mostrando todos — termo não encontrado)`}</div>
        <table class="tabelaGrupo">
            <tr class="linhaTitulo">
                <td style="text-align:left;padding:6px 10px;width:90px;">Código</td>
                <td style="text-align:left;padding:6px 10px;">Descrição</td>
                <td style="width:55px;">II</td>
                <td style="width:55px;">IPI</td>
                <td style="width:55px;">PIS</td>
                <td style="width:55px;">COFINS</td>
                <td style="width:55px;">ICMS</td>
            </tr>
            ${linhas}
        </table>
        <p style="margin-top:8px;font-size:11px;color:var(--nfe-text);">Alíquotas típicas (referência). Consulte a TIPI/Convênio vigente e a legislação estadual para o ICMS.</p>
    `;
}

function handleGtin(e) {
    e.preventDefault();
    const codigo = document.getElementById("gtin-input").value;
    const res = validarGTIN(codigo);
    const painel = document.getElementById("gtin-painel-resultado");
    painel.style.display = "block";
    painel.className = "gtin-painel";
    if (res.erro) {
        painel.innerHTML = `
            <div class="painelSessaoTitulo">Validação de GTIN</div>
            <div class="result error"><pre>${res.erro}</pre></div>
        `;
        return;
    }
    const cls = res.valido ? "success" : "error";
    const status = res.valido ? "VÁLIDO ✓" : "INVÁLIDO ✗";
    painel.innerHTML = `
        <div class="painelSessaoTitulo">Validação de GTIN</div>
        <table class="sefaz-resumo-tabela">
            <tr><th>Código informado</th><td>${res.codigo}</td></tr>
            <tr><th>Tipo</th><td>${res.tipo}</td></tr>
            <tr><th>Comprimento</th><td>${res.comprimento} dígitos</td></tr>
            <tr><th>Dígito verificador</th><td>informado: <b>${res.digito}</b> &nbsp;|&nbsp; calculado: <b>${res.digitoCalculado}</b></td></tr>
            <tr><th>Origem (prefixo GS1)</th><td>${res.pais}</td></tr>
            <tr><th>Status</th><td><b class="${cls}">${status}</b></td></tr>
        </table>
    `;
}

function handleCcc(e) {
    e.preventDefault();
    const tipo = document.getElementById("ccc-tipo").value;
    const doc = (document.getElementById("ccc-documento").value || "").replace(/\D/g, "");
    const aviso = document.getElementById("ccc-aviso-resultado");
    aviso.style.display = "block";
    aviso.className = "ccc-aviso";
    aviso.innerHTML = `
        <div class="painelSessaoTitulo">Consulta CCC — ${tipo} ${doc ? `(${doc})` : ""}</div>
        <div class="divMensagem">
            <p><b>Esta funcionalidade requer acesso direto ao webservice CCC do SEFAZ.</b></p>
            <p>O PyNFe não possui suporte nativo ao Cadastro Centralizado de Contribuinte (CCC).
            Por enquanto, use o portal oficial:</p>
            <p><a href="https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=/L1QW3dEK0c=" target="_blank" rel="noopener">https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=/L1QW3dEK0c=</a></p>
            <p style="margin-top:6px;font-size:11px;color:var(--nfe-text);">Quando o SEFAZ expuser o WSDL público do CCC, este módulo será integrado ao backend PyNFe sem alterações na interface.</p>
        </div>
    `;
}


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


async function handleStatusServico(e) {
    e.preventDefault();
    const tipo = document.getElementById("status-tipo").value;
    showLoading("result-status");

    const result = await apiGet(`/api/status/${tipo}?uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}`);

    if (result.success) {
        showResult("result-status", result.data, "success");
    } else {
        showResult("result-status", result.data, "error");
    }
}


async function handleConsultaChave(e) {
    e.preventDefault();
    const chave = document.getElementById("consulta-chave-input").value.replace(/\D/g, "");
    const modelo = document.getElementById("consulta-chave-modelo").value;

    if (!chave || chave.length !== 44) {
        showResult("result-consulta-chave", { error: "A chave deve conter exatamente 44 dígitos numéricos." }, "error");
        return;
    }

    const ufAuto = ufFromChave(chave);
    const ufParaConsulta = ufAuto || AppState.uf;
    const homologacao = AppState.ambiente === "homologacao";

    showLoading("result-consulta-chave");
    const result = await apiGet(`/api/consulta/chave?chave=${encodeURIComponent(chave)}&modelo=${modelo}&uf=${ufParaConsulta}&homologacao=${homologacao}`);

    const el = document.getElementById("result-consulta-chave");
    el.style.display = "block";
    el.className = "result success";

    if (result.success) {
        el.innerHTML = renderAutoUfBadge(ufAuto, AppState.uf) + renderResumoSefaz(result.data, chave, modelo);
        el.querySelectorAll("[data-action]").forEach(btn => {
            btn.addEventListener("click", () => handleResumoAction(btn.dataset.action, chave, modelo, ufParaConsulta));
        });
    } else {
        el.className = "result error";
        const detail = (result.data && result.data.detail) ? result.data.detail : "Erro ao consultar SEFAZ";
        el.innerHTML = renderAutoUfBadge(ufParaConsulta, AppState.uf) + `
            <div class="sefaz-resumo">
                <div class="sefaz-resumo-titulo" style="background:#b00020;">Resultado da Consulta SEFAZ</div>
                <table class="sefaz-resumo-tabela">
                    <tr><th>Chave de Acesso</th><td><b>${chave.replace(/(\d{4})(?=\d)/g, "$1 ")}</b></td></tr>
                    <tr><th>Erro</th><td>${escapeHtml(detail)}</td></tr>
                </table>
                <div class="sefaz-resumo-acoes">
                    <button type="button" class="botao" data-consulta-action="upload">Tentar Upload de XML</button>
                    <button type="button" class="botao" data-consulta-action="pdf">Baixar PDF (Oficial)</button>
                </div>
            </div>`;
        el.querySelectorAll("[data-consulta-action]").forEach(btn => {
            btn.addEventListener("click", () => {
                const ac = btn.dataset.consultaAction;
                if (ac === "upload") {
                    showSection("danfe");
                    switchTab("tab-upload-danfe");
                } else if (ac === "pdf") {
                    downloadDanfePdf(chave, ufParaConsulta);
                }
            });
        });
    }
}


function renderResumoSefaz(payload, chave, modelo) {
    const body = (payload && payload.body) ? payload.body : "";
    const statusCode = (payload && payload.status_code) ? payload.status_code : "—";
    const parsed = parseResumoXml(body);
    const chaveFmt = chave.replace(/(\d{4})(?=\d)/g, "$1 ");

    return `
        <div class="sefaz-resumo">
            <div class="sefaz-resumo-titulo">Dados da NF-e</div>
            <table class="sefaz-resumo-tabela">
                <tr>
                    <th>Chave de Acesso</th>
                    <td colspan="3"><b>${chaveFmt}</b></td>
                </tr>
                <tr>
                    <th>Número do Protocolo</th>
                    <td>${parsed.protocolo || "—"}</td>
                    <th>Data/Hora Autorização</th>
                    <td>${parsed.dataAutorizacao || "—"}</td>
                </tr>
                <tr>
                    <th>Status SEFAZ</th>
                    <td>${parsed.situacao || `HTTP ${statusCode}`}</td>
                    <th>Modelo</th>
                    <td>${modelo.toUpperCase() === "NFCE" ? "65 - NFC-e" : "55 - NF-e"}</td>
                </tr>
            </table>
            <div class="sefaz-resumo-acoes">
                <button type="button" class="botao" data-action="visualizar">Visualizar DANFE</button>
                <button type="button" class="botao" data-action="pdf">Baixar PDF (Oficial)</button>
                <button type="button" class="botao" data-action="xml">Baixar XML</button>
                <button type="button" class="botao" data-action="detalhes">Ver Detalhes Completos</button>
            </div>
            <details class="sefaz-resumo-xml">
                <summary>XML retornado pela SEFAZ (clique para expandir)</summary>
                <pre>${escapeHtml(body || "(sem conteúdo)")}</pre>
            </details>
        </div>
    `;
}


function parseResumoXml(xmlString) {
    const out = { protocolo: "", dataAutorizacao: "", situacao: "" };
    if (!xmlString) return out;
    try {
        const doc = new DOMParser().parseFromString(xmlString, "text/xml");
        const nProt = doc.getElementsByTagName("nProt")[0];
        const dhRecbto = doc.getElementsByTagName("dhRecbto")[0];
        const cStat = doc.getElementsByTagName("cStat")[0];
        const xMotivo = doc.getElementsByTagName("xMotivo")[0];
        if (nProt) out.protocolo = nProt.textContent.trim();
        if (dhRecbto) {
            const txt = dhRecbto.textContent.trim();
            out.dataAutorizacao = fmtDataHoraSegBR(txt) || txt;
        }
        if (cStat) {
            const motivo = xMotivo ? xMotivo.textContent.trim() : "";
            out.situacao = `${cStat.textContent.trim()} - ${motivo}`;
        }
    } catch (e) {
        console.error("Erro ao parsear XML do resumo:", e);
    }
    return out;
}


async function handleResumoAction(action, chave, modelo, ufOverride) {
    const ufParaConsulta = ufOverride || ufFromChave(chave) || AppState.uf;
    if (action === "visualizar" || action === "detalhes") {
        document.getElementById("danfe-chave-input").value = chave;
        showSection("danfe");
        switchTab("tab-chave-danfe");
        document.getElementById("form-danfe-chave").dispatchEvent(new Event("submit", { cancelable: true }));
        return;
    }
    if (action === "pdf") {
        downloadDanfePdf(chave, ufParaConsulta);
        return;
    }
    if (action === "xml") {
        try {
            const result = await apiGet(`/api/consulta/chave?chave=${encodeURIComponent(chave)}&modelo=${modelo}&uf=${ufParaConsulta}&homologacao=${AppState.ambiente === "homologacao"}`);
            if (result.success && result.data.body) {
                const blob = new Blob([result.data.body], { type: "application/xml" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `nfe_${chave}.xml`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } else {
                toast.error("Não foi possível obter o XML.");
            }
        } catch (e) {
            toast.error("Erro ao baixar XML: " + e.message);
        }
    }
}


async function handleConsultaCadastro(e) {
    e.preventDefault();
    const tipo = document.getElementById("consulta-cadastro-tipo").value;
    const documento = document.getElementById("consulta-cadastro-documento").value.replace(/\D/g, "");

    if (!documento) {
        showResult("result-consulta-cadastro", { error: "Documento é obrigatório." }, "error");
        return;
    }

    showLoading("result-consulta-cadastro");
    const result = await apiGet(`/api/consulta/cadastro?documento=${encodeURIComponent(documento)}&tipo=${tipo}&modelo=nfe&uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}`);

    if (result.success) {
        showResult("result-consulta-cadastro", result.data, "success");
    } else {
        showResult("result-consulta-cadastro", result.data, "error");
    }
}


async function handleManifestacao(e) {
    e.preventDefault();
    const chave = document.getElementById("manifestacao-chave").value.replace(/\D/g, "");
    const cnpj = document.getElementById("manifestacao-cnpj").value.replace(/\D/g, "");
    const tipo = document.getElementById("manifestacao-tipo").value;
    const justificativa = document.getElementById("manifestacao-justificativa").value.trim();

    if (!chave || chave.length !== 44) {
        showResult("result-manifestacao", { error: "A chave deve conter 44 dígitos." }, "error");
        return;
    }
    if (!cnpj) {
        showResult("result-manifestacao", { error: "CNPJ é obrigatório." }, "error");
        return;
    }

    const ufAuto = ufFromChave(chave);
    const ufParaConsulta = ufAuto || AppState.uf;
    const homologacao = AppState.ambiente === "homologacao";

    showLoading("result-manifestacao");
    const result = await apiPost("/api/nfe/manifestacao", {
        chave,
        cnpj,
        tipo_manifestacao: tipo,
        justificativa,
        uf: ufParaConsulta,
        homologacao,
    });

    const el = document.getElementById("result-manifestacao");
    el.style.display = "block";

    if (result.success) {
        const body = (result.data && result.data.body) || "";
        const parsed = parseManifestacaoXml(body);
        const cStat = parsed.cStat || "";
        const isSuccess = cStat === "135" || cStat === "136" || cStat === "573";

        el.className = `result ${isSuccess ? "success" : "error"}`;
        el.innerHTML = `
            <div class="sefaz-resumo" style="border-color:${isSuccess ? '#27ae60' : '#b00020'};background:${isSuccess ? '#f0fff4' : '#fff5f5'};">
                <div class="sefaz-resumo-titulo" style="color:${isSuccess ? '#27ae60' : '#b00020'};background:${isSuccess ? '#d4edda' : '#f8d7da'};">
                    ${isSuccess ? "✓ Manifestação Processada com Sucesso" : "⚠ Retorno da Manifestação"}
                </div>
                <table class="sefaz-resumo-tabela">
                    <tr><th>Chave de Acesso</th><td colspan="3"><b>${escapeHtml(chave.replace(/(\d{4})(?=\d)/g, "$1 "))}</b></td></tr>
                    <tr>
                        <th>Status SEFAZ (cStat)</th>
                        <td colspan="3" style="color:${isSuccess ? '#27ae60' : '#b00020'};font-weight:bold;">
                            ${escapeHtml(cStat || "—")} — ${escapeHtml(parsed.xMotivo || "Processado")}
                        </td>
                    </tr>
                    <tr>
                        <th>Tipo de Evento</th>
                        <td><b>${escapeHtml(parsed.xEvento || (tipo === "210240" ? "Operação não Realizada" : tipo === "210200" ? "Confirmação da Operação" : tipo === "210210" ? "Ciência da Emissão" : "Desconhecimento"))} (${escapeHtml(tipo)})</b></td>
                        <th>Protocolo</th>
                        <td>${escapeHtml(parsed.nProt || "Registrado na Base Nacional")}</td>
                    </tr>
                    <tr>
                        <th>Data / Hora Registro</th>
                        <td>${escapeHtml(parsed.dhRegEvento || "—")}</td>
                        <th>Ambiente</th>
                        <td>${homologacao ? "2 - Homologação" : "1 - Produção"}</td>
                    </tr>
                </table>
                <div style="margin-top:10px;padding:8px;background:${isSuccess ? '#e8f5e9' : '#fff3cd'};border-radius:4px;font-size:12px;color:${isSuccess ? '#2e7d32' : '#856404'};">
                    ${cStat === "573" ? "<b>Informação:</b> Este evento de manifestação <b>já constava registrado e homologado</b> na base de dados nacional da SEFAZ para esta NF-e." : isSuccess ? "<b>Sucesso:</b> A manifestação foi vinculada à NF-e na Receita Federal e SEFAZ com valor legal." : `<b>Aviso:</b> ${escapeHtml(parsed.xMotivo || 'Verifique os dados informados.')}`}
                </div>
                <div style="margin-top:12px;display:flex;gap:8px;">
                    <button type="button" class="botao botao-primario" onclick="document.getElementById('danfe-chave-input').value='${chave}';showSection('danfe');switchTab('tab-chave-danfe');document.getElementById('form-danfe-chave').dispatchEvent(new Event('submit',{cancelable:true}));">👁️ Visualizar DANFE</button>
                    <button type="button" class="botao" onclick="showSection('distribuicao');">Ir para Distribuição DF-e</button>
                </div>
                <details class="sefaz-resumo-xml" style="margin-top:10px;">
                    <summary style="cursor:pointer;font-weight:bold;color:#2c3e50;">XML retornado pela SEFAZ (clique para expandir)</summary>
                    <pre style="background:#f4f4f4;padding:10px;font-size:10px;max-height:250px;overflow:auto;">${escapeHtml(body)}</pre>
                </details>
            </div>
        `;
    } else {
        el.className = "result error";
        const detail = (result.data && (result.data.detail || result.data.error)) || "Erro ao enviar manifestação";
        el.innerHTML = `<pre>${escapeHtml(detail)}</pre>`;
    }
}


function parseManifestacaoXml(xmlString) {
    const out = { cStat: "", xMotivo: "", nProt: "", dhRegEvento: "", xEvento: "", tpEvento: "" };
    if (!xmlString) return out;
    try {
        const doc = new DOMParser().parseFromString(xmlString, "text/xml");
        const infEvento = doc.getElementsByTagName("infEvento")[0] || doc;
        const cStat = infEvento.getElementsByTagName("cStat")[0] || doc.getElementsByTagName("cStat")[0];
        const xMotivo = infEvento.getElementsByTagName("xMotivo")[0] || doc.getElementsByTagName("xMotivo")[0];
        const nProt = infEvento.getElementsByTagName("nProt")[0];
        const dhReg = infEvento.getElementsByTagName("dhRegEvento")[0];
        const xEv = infEvento.getElementsByTagName("xEvento")[0];
        const tpEv = infEvento.getElementsByTagName("tpEvento")[0];

        if (cStat) out.cStat = cStat.textContent.trim();
        if (xMotivo) out.xMotivo = xMotivo.textContent.trim();
        if (nProt) out.nProt = nProt.textContent.trim();
        if (dhReg) out.dhRegEvento = dhReg.textContent.trim();
        if (xEv) out.xEvento = xEv.textContent.trim();
        if (tpEv) out.tpEvento = tpEv.textContent.trim();
    } catch (e) {
        console.error("Erro ao parsear XML de manifestação:", e);
    }
    return out;
}


async function handleCertUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById("cert-file");
    const password = document.getElementById("cert-password").value;
    const file = fileInput.files[0];

    if (!file) {
        showResult("result-cert-upload", { error: "Selecione um arquivo de certificado." }, "error");
        return;
    }
    if (!password) {
        showResult("result-cert-upload", { error: "Informe a senha do certificado." }, "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("password", password);

    showLoading("result-cert-upload");
    const result = await apiUploadForm("/api/certificado/upload", formData);

    if (result.success && result.data.loaded) {
        AppState.certLoaded = true;
        showResult("result-cert-upload", {
            success: `Certificado cadastrado com sucesso! Empresa: ${result.data.subject || ''} | Validade: ${result.data.valid_to || ''}`
        }, "success");
        fileInput.value = "";
        document.getElementById("cert-password").value = "";
        checkCertStatus();
        loadCertificatesUI();
    } else {
        showResult("result-cert-upload", result.data || { error: "Erro ao carregar certificado." }, "error");
    }
}


async function loadCertificatesUI() {
    try {
        const res = await apiGet("/api/certificado/list");
        if (!res.success || !res.data) return;
        const certs = res.data || [];

        // 1. Renderiza Cards na Tela Inicial (#inicio-cards-certificados)
        const cardsContainer = document.getElementById("inicio-cards-certificados");
        if (cardsContainer) {
            if (certs.length === 0) {
                renderEmptyState({
                    icon: '🏢',
                    title: 'Nenhum certificado cadastrado',
                    description: 'Você ainda não cadastrou um certificado digital A1.',
                    actionHtml: '<button class="botao botao-primario" onclick="showSection(\'certificado\')">➕ Adicionar certificado</button>',
                    containerId: 'inicio-cards-certificados',
                });
            } else {
                cardsContainer.innerHTML = certs.map(c => {
                    const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                    const days = c.days_remaining || 0;
                    let badgeClass = "badge-ambiente";
                    let badgeStyle = "background:var(--pastel-green-bg);color:var(--pastel-green-text);border:1px solid var(--pastel-green-border);";
                    let badgeText = `🟢 ${days} dias restantes`;
                    if (c.status_validade === "VENCIDO" || days === 0) {
                        badgeStyle = "background:var(--pastel-rose-bg);color:var(--pastel-rose-text);border:1px solid var(--pastel-rose-border);";
                        badgeText = "🔴 Vencido";
                    } else if (c.status_validade === "EXPIRANDO" || days <= 30) {
                        badgeStyle = "background:var(--pastel-amber-bg);color:var(--pastel-amber-text);border:1px solid var(--pastel-amber-border);";
                        badgeText = `🟡 Atenção: ${days} dias`;
                    }

                    return `
                        <div class="card-kpi" style="border-top:3px solid var(--primary);">
                            <div>
                                <div style="font-size:12.5px;font-weight:600;color:var(--text-main);margin-bottom:4px;line-height:1.3;" title="${escapeHtml(c.razao_social)}">${escapeHtml(c.razao_social)}</div>
                                <div style="font-size:11px;font-family:monospace;color:var(--text-muted);margin-bottom:8px;">CNPJ: <b>${escapeHtml(cnpjFmt)}</b></div>
                                <div style="font-size:11.5px;color:var(--text-muted);margin-bottom:8px;">Validade: <b>${escapeHtml(c.valid_from || '—')}</b> até <b>${escapeHtml(c.valid_to || '—')}</b></div>
                                <div style="margin-bottom:12px;"><span style="${badgeStyle}font-size:10.5px;padding:3px 8px;border-radius:9999px;font-weight:600;">${escapeHtml(badgeText)}</span></div>
                            </div>
                            <div style="display:flex;gap:6px;border-top:1px solid var(--border-subtle);padding-top:10px;margin-top:6px;">
                                <button type="button" class="btn-action btn-action-primary" onclick="filtrarNotasPorEmpresa('${c.cnpj}');" style="flex:1;justify-content:center;padding:5px 8px;">🗄️ Notas</button>
                                <button type="button" class="btn-action btn-action-success" onclick="sincronizarEmpresaEspecifica('${c.cnpj}');" style="flex:1;justify-content:center;padding:5px 8px;">⚡ Sincronizar</button>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }

        // 2. Renderiza Tabela na aba Certificados (#cert-lista-tabela)
        const certTabela = document.getElementById("cert-lista-tabela");
        if (certTabela) {
            if (certs.length === 0) {
                renderEmptyState({
                    icon: '🏢',
                    title: 'Nenhum certificado cadastrado',
                    description: 'Você ainda não possui certificados digitais cadastrados no banco local.',
                    actionHtml: '<button class="botao botao-primario" onclick="abrirModalCadCert()">➕ Adicionar certificado A1</button>',
                    containerId: 'cert-lista-tabela',
                });
            } else {
                certTabela.innerHTML = `
                    <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                        <tr class="linhaTitulo">
                            <th style="text-align:left;padding:6px;">Razão Social</th>
                            <th>CNPJ</th>
                            <th>Validade Inicial</th>
                            <th>Validade Final</th>
                            <th>Dias Restantes</th>
                            <th>Status</th>
                            <th>Ações</th>
                        </tr>
                        ${certs.map(c => {
                            const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                            const days = c.days_remaining || 0;
                            let badgeColor = days > 30 ? "#27ae60" : days > 0 ? "#e67e22" : "#b00020";
                            return `
                                <tr>
                                    <td style="text-align:left;padding:6px;"><b>${escapeHtml(c.razao_social)}</b></td>
                                    <td style="font-family:monospace;">${escapeHtml(cnpjFmt)}</td>
                                    <td>${escapeHtml(c.valid_from || "—")}</td>
                                    <td><b>${escapeHtml(c.valid_to || "—")}</b></td>
                                    <td><b>${days} dias</b></td>
                                    <td><span class="badge-ambiente" style="background:${badgeColor};font-size:10px;">${escapeHtml(c.status_validade || "ATIVO")}</span></td>
                                    <td style="white-space:nowrap;">
                                        <button type="button" class="botao" onclick="sincronizarEmpresaEspecifica('${c.cnpj}');" style="font-size:10px;padding:2px 6px;">⚡ Sincronizar</button>
                                        <button type="button" class="botao" onclick="excluirCertificado('${c.cnpj}', '${escapeHtml(c.razao_social)}');" style="font-size:10px;padding:2px 6px;color:#b00020;border-color:#b00020;">🗑️ Excluir</button>
                                    </td>
                                </tr>
                            `;
                        }).join("")}
                    </table>
                `;
            }
        }

        // 3. Atualiza Select Dropdowns de Empresas em todas as abas
        const selectIds = [
            { id: "gestao-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
            { id: "contabil-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
            { id: "emissao-empresa-emit", placeholder: "Selecione a empresa emitente..." },
            { id: "filtro-saidas-empresa", placeholder: "🏢 Todas as 5 Empresas Emitentes" },
            { id: "filtro-empresa-saidas", placeholder: "🏢 Todas as 5 Empresas Emitentes" },
            { id: "intercompany-empresa-origem", placeholder: "Empresa de Origem..." },
            { id: "intercompany-empresa-destino", placeholder: "Empresa de Destino..." },
            { id: "limpeza-empresa", placeholder: "🏢 Todas as Empresas / Certificados" },
            { id: "gaps-filtro-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
        ];

        selectIds.forEach(({ id, placeholder }) => {
            const sel = document.getElementById(id);
            if (sel) {
                const valAtual = sel.value;
                const optDefault = placeholder ? `<option value="">${placeholder}</option>` : "";
                sel.innerHTML = optDefault + certs.map(c => {
                    const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                    return `<option value="${c.cnpj}">${escapeHtml(cnpjFmt)} - ${escapeHtml(c.razao_social)}</option>`;
                }).join("");
                if (valAtual && [...sel.options].some(o => o.value === valAtual)) {
                    sel.value = valAtual;
                }
            }
        });
        atualizarCardEmitenteInfo();
    } catch (err) {
        console.error("Erro ao carregar certificados UI:", err);
    }
}


async function excluirCertificado(cnpj, razaoSocial) {
    const confirma = await showConfirmModal({
        title: "Excluir Certificado",
        message: `Deseja realmente excluir o certificado da empresa:\n${razaoSocial} (${cnpj})?`,
        confirmText: "Sim, excluir",
        cancelText: "Cancelar",
        danger: true,
        icon: "🗑️",
    });
    if (!confirma) {
        return;
    }
    try {
        const res = await apiDelete(`/api/certificado/${cnpj}`);
        if (res.success) {
            toast.success(`Certificado ${cnpj} excluído com sucesso.`);
            loadCertificatesUI();
            checkCertStatus();
        } else {
            toast.error("Erro ao excluir certificado: " + (res.data?.detail || "Falha"));
        }
    } catch (err) {
        toast.error("Erro na requisição: " + err.message);
    }
}


function filtrarNotasPorEmpresa(cnpj) {
    showSection("gestao-docs");
    const selectEmp = document.getElementById("gestao-empresa");
    if (selectEmp) selectEmp.value = cnpj;
    loadGestaoDocs(1);
}


async function sincronizarEmpresaEspecifica(cnpj) {
    const feedback = document.getElementById("sync-execucao-resultado");
    if (feedback) {
        feedback.style.display = "block";
        feedback.className = "result info";
        feedback.innerHTML = `<p>⚡ Sincronizando empresa <b>${cnpj}</b> com a SEFAZ Nacional a partir do último NSU, aguarde...</p>`;
    }
    showSection("gestao-sync");

    try {
        const res = await apiPost("/api/gestao/sync/run", { cnpj: cnpj, homologacao: AppState.ambiente === "homologacao" });
        if (res.success) {
            const data = res.data || {};
            // Caso a empresa esteja em cooldown por 656 (ou o sync recém tenha caído em 656),
            // o backend retorna blocked_by_sefaz=true. Mostra aviso amigável em vez do "✓ sucesso".
            const empresas = data.empresas || [];
            const empresaInfo = empresas.find(e => e.cnpj === cnpj) || data;
            if (empresaInfo && empresaInfo.blocked_by_sefaz) {
                const retryAt = empresaInfo.retry_at
                    ? new Date(empresaInfo.retry_at).toLocaleString("pt-BR", { dateStyle: 'short', timeStyle: 'short' })
                    : "—";
                if (feedback) {
                    feedback.className = "result info";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#c0392b;">🔒 SEFAZ bloqueou esta empresa (cStat 656 — Consumo Indevido).</div>
                        <div style="font-size:12px;margin-top:4px;">
                            Tentativa ${empresaInfo.tentativa_656 || 1} do backoff exponencial.<br>
                            <b>Próxima retentativa:</b> ${escapeHtml(retryAt)} (em ${empresaInfo.cooldown_minutes || 0} min).<br>
                            Tentar antes do cooldown só agrava o bloqueio. O sync automático respeitará a janela.
                        </div>
                    `;
                }
            } else if (data.skipped && data.blocked_by_sefaz) {
                const retryAt = data.retry_at
                    ? new Date(data.retry_at).toLocaleString("pt-BR", { dateStyle: 'short', timeStyle: 'short' })
                    : "—";
                if (feedback) {
                    feedback.className = "result info";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#c0392b;">🔒 Sync pulado — SEFAZ ainda bloqueia esta empresa.</div>
                        <div style="font-size:12px;margin-top:4px;">
                            <b>Próxima retentativa:</b> ${escapeHtml(retryAt)} (em ${data.cooldown_minutes || 0} min).
                        </div>
                    `;
                }
            } else {
                if (feedback) {
                    feedback.className = "result success";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#27ae60;">✓ Sincronização concluída com sucesso!</div>
                        <div style="font-size:12px;margin-top:4px;">
                            <b>${data.total_docs_saved || 0}</b> novas notas fiscais baixadas e arquivadas no banco.<br>
                            <b>${data.total_events_saved || 0}</b> eventos registrados.
                        </div>
                    `;
                }
            }
            loadSyncStatus();
            loadCertificatesUI();
        } else {
            if (feedback) {
                feedback.className = "result error";
                feedback.innerHTML = `<p>Erro na sincronização: ${escapeHtml(res.data?.detail || "Falha")}</p>`;
            }
        }
    } catch (err) {
        if (feedback) {
            feedback.className = "result error";
            feedback.innerHTML = `<p>Erro de comunicação: ${escapeHtml(err.message)}</p>`;
        }
    }
}


async function showCertInfo() {
    showLoading("result-cert-info");
    const result = await apiGet("/api/certificado/info");

    if (result.success && result.data.loaded) {
        AppState.certLoaded = true;
        showResult("result-cert-info", result.data, "success");
        checkCertStatus();
    } else {
        AppState.certLoaded = false;
        showResult("result-cert-info", result.data, "error");
        checkCertStatus();
    }
}


// ── Handlers: Conta (Alterar Senha / E-mail) ──────────────────────────────────

async function handleAlterarSenha(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("result-alterar-senha");
    const senhaAtual = document.getElementById("senha-atual").value;
    const senhaNova = document.getElementById("senha-nova").value;
    const senhaNovaConfirm = document.getElementById("senha-nova-confirm").value;

    if (!senhaAtual || !senhaNova || !senhaNovaConfirm) {
        showResult("result-alterar-senha", { error: "Preencha todos os campos." }, "error");
        return;
    }
    if (senhaNova.length < 6) {
        showResult("result-alterar-senha", { error: "A nova senha deve ter ao menos 6 caracteres." }, "error");
        return;
    }
    if (senhaNova !== senhaNovaConfirm) {
        showResult("result-alterar-senha", { error: "As senhas não conferem." }, "error");
        return;
    }

    try {
        const res = await apiPost("/api/auth/alterar-senha", {
            senha_atual: senhaAtual,
            senha_nova: senhaNova,
        });
        if (res.success) {
            showResult("result-alterar-senha", { message: "Senha alterada com sucesso!" }, "success");
            document.getElementById("form-alterar-senha").reset();
            // Se era senha padrão, desbloquear o sistema
            if (AppState.senha_padrao) {
                AppState.senha_padrao = false;
                const alertDiv = document.getElementById("senha-padrao-alert");
                if (alertDiv) alertDiv.style.display = "none";
                // Marcar no backend que a senha padrão foi alterada
                await apiPost("/api/auth/marcar-senha-alterada", {});
            }
        } else {
            showResult("result-alterar-senha", { error: res.detail || "Erro ao alterar senha." }, "error");
        }
    } catch (err) {
        showResult("result-alterar-senha", { error: err.message || "Erro de conexão." }, "error");
    }
}

async function handleAlterarEmail(e) {
    e.preventDefault();
    const senhaAtual = document.getElementById("email-senha-atual").value;
    const emailNovo = document.getElementById("email-novo").value;
    const emailNovoConfirm = document.getElementById("email-novo-confirm").value;

    if (!senhaAtual || !emailNovo || !emailNovoConfirm) {
        showResult("result-alterar-email", { error: "Preencha todos os campos." }, "error");
        return;
    }
    if (emailNovo !== emailNovoConfirm) {
        showResult("result-alterar-email", { error: "Os e-mails não conferem." }, "error");
        return;
    }

    try {
        const res = await apiFetch("/api/auth/alterar-email", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                senha_atual: senhaAtual,
                email_novo: emailNovo,
                email_novo_confirm: emailNovoConfirm,
            }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showResult("result-alterar-email", { message: "E-mail alterado com sucesso!" }, "success");
            document.getElementById("form-alterar-email").reset();
            AppState.email = data.email;
            document.getElementById("conta-email-atual").textContent = data.email;
        } else {
            showResult("result-alterar-email", { error: data.detail || "Erro ao alterar e-mail." }, "error");
        }
    } catch (err) {
        showResult("result-alterar-email", { error: err.message || "Erro de conexão." }, "error");
    }
}

function loadContaInfo() {
    // Preencher informações da conta na aba
    const emailEl = document.getElementById("conta-email-atual");
    const nomeEl = document.getElementById("conta-nome-atual");
    const perfilEl = document.getElementById("conta-perfil-atual");
    if (emailEl) emailEl.textContent = AppState.email || "—";
    if (nomeEl) nomeEl.textContent = AppState.nome || "—";
    if (perfilEl) perfilEl.textContent = AppState.perfil || "—";
}


async function handleConfigAmbiente(e) {
    e.preventDefault();
    const radio = document.querySelector('input[name="ambiente"]:checked');
    if (radio) {
        AppState.ambiente = radio.value;
        saveSettings();
        updateBadges();
        toast.success("Ambiente atualizado com sucesso.");
    }
}


async function handleConfigUF(e) {
    e.preventDefault();
    AppState.uf = document.getElementById("config-uf-select").value;
    saveSettings();
    updateBadges();
    toast.success("UF atualizada com sucesso.");
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


async function handleRelStatus(e) {
    e.preventDefault();
    const periodo = document.getElementById("rel-status-periodo").value;
    downloadPdf(`/api/fiscal/status?uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}&periodo_dias=${periodo}`,
        `relatorio_status_${new Date().toISOString().slice(0, 10)}.pdf`);
}


async function handleRelVolume(e) {
    e.preventDefault();
    const meses = document.getElementById("rel-volume-meses").value;
    downloadPdf(`/api/fiscal/volume-mensal?uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}&meses=${meses}`,
        `relatorio_volume_mensal_${new Date().toISOString().slice(0, 10)}.pdf`);
}


async function handleRelCompliance(e) {
    e.preventDefault();
    const periodo = document.getElementById("rel-compliance-periodo").value;
    downloadPdf(`/api/fiscal/compliance?uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}&periodo_dias=${periodo}`,
        `relatorio_compliance_${new Date().toISOString().slice(0, 10)}.pdf`);
}


async function handleRelEmissores(e) {
    e.preventDefault();
    const periodo = document.getElementById("rel-emissores-periodo").value;
    downloadPdf(`/api/fiscal/emissores?uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}&periodo_dias=${periodo}`,
        `relatorio_emissores_${new Date().toISOString().slice(0, 10)}.pdf`);
}


async function handleDanfeChave(e) {
    if (e && e.preventDefault) e.preventDefault();
    const chave = (document.getElementById("danfe-chave-input")?.value || "").replace(/\D/g, "");
    return handleDanfePorChaveString(chave);
}

async function handleDanfePorChaveString(chaveRaw) {
    const chave = String(chaveRaw || "").replace(/\D/g, "");

    if (chave.length !== 44) {
        showResult("danfe-result", { error: "A chave deve conter 44 dígitos numéricos." }, "error");
        return;
    }

    const input = document.getElementById("danfe-chave-input");
    if (input) input.value = chave;

    const ufAuto = ufFromChave(chave);
    const ufParaConsulta = ufAuto || AppState.uf;
    const homologSelecionado = AppState.ambiente === "homologacao";

    showLoading("danfe-result");
    const previewEl = document.getElementById("danfe-preview");
    if (previewEl) previewEl.style.display = "none";

    const badgeHtml = renderAutoUfBadge(ufAuto, AppState.uf);

    // 1. Tenta carregar os dados completos do DANFE (banco local com XML ou SEFAZ)
    const result = await apiGet(`/api/danfe/parse/${chave}?uf=${ufParaConsulta}&homologacao=${homologSelecionado}`);

    if (result.success && result.data && (result.data.emitente || result.data.produtos || result.data.chave)) {
        renderDanfePreview(result.data, chave, null, badgeHtml);
        showResult("danfe-result", { success: `NF-e ${chave} carregada com sucesso!` }, "success");
        if (typeof saveDocToFirestore === "function") {
            saveDocToFirestore(result.data);
        }
        return;
    }

    // 2. Se não encontrou dados completos, consulta o resumo de protocolo na SEFAZ
    const resumoResp = await apiGet(`/api/danfe/resumo/${chave}?uf=${ufParaConsulta}&homologacao=${homologSelecionado}`);
    if (resumoResp.success) {
        const resumo = resumoResp.data || {};
        const cStat = String(resumo.c_stat || "").trim();
        if (cStat.startsWith("1")) {
            renderSefazAuthorizedPanel(resumo, chave, badgeHtml);
        } else {
            renderSefazRejectionPanel(resumo, chave, badgeHtml);
        }
    } else {
        const detail = (result.data && result.data.detail) || (resumoResp.data && resumoResp.data.detail) || "NF-e não localizada.";
        if (isCertMissingError(detail)) {
            renderCertMissingPanel(detail, chave, badgeHtml);
            return;
        }
        renderSefazRejectionPanel({ motivo: detail, c_stat: "", uf: "", tipo_ambiente: homologSelecionado ? "2" : "1" }, chave, badgeHtml);
    }
}


function isCertMissingError(detail) {
    if (!detail) return false;
    const text = String(detail);
    if (text.startsWith("Nenhum certificado digital carregado")) return true;
    return /carregado/i.test(text) && /certificado/i.test(text);
}


function renderCertMissingPanel(detail, chave, prefixHtml = "") {
    const container = document.getElementById("danfe-result");
    if (!container) return;

    container.style.display = "block";
    container.className = "result error";
    container.innerHTML = prefixHtml + `
        <div class="sefaz-resumo" style="border-color:#f0ad4e;background:#fff8e1;">
            <div class="sefaz-resumo-titulo" style="color:#8a6d3b;">⚠ Certificado Digital Necessário</div>
            <table class="sefaz-resumo-tabela">
                <tr>
                    <th>Chave de Acesso</th>
                    <td colspan="3"><b>${escapeHtml(chave.replace(/(\d{4})(?=\d)/g, "$1 "))}</b></td>
                </tr>
            </table>
            <div class="sefaz-resumo-motivo" style="margin-top:10px;padding:10px;background:#fff3cd;border:1px solid #ffeeba;border-radius:4px;color:#8a6d3b;">${escapeHtml(detail)}</div>
            <div class="sefaz-resumo-acoes" style="margin-top:12px;">
                <button type="button" class="botao botao-primario" data-cert-action="certificado">Ir para Certificado Digital</button>
                <button type="button" class="botao" data-cert-action="upload">Tentar Upload de XML</button>
            </div>
        </div>
    `;

    container.querySelectorAll("[data-cert-action]").forEach(btn => {
        btn.addEventListener("click", () => {
            const action = btn.dataset.certAction;
            if (action === "certificado") {
                const target = document.getElementById("section-certificado");
                if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
            } else if (action === "upload") {
                if (typeof switchTab === "function") switchTab("tab-upload-danfe");
            }
        });
    });
}


function renderSefazAuthorizedPanel(resumo, chave, prefixHtml = "") {
    const container = document.getElementById("danfe-result");
    if (!container) return;

    const cStat = String((resumo && resumo.c_stat) || "100").trim();
    const motivo = String((resumo && resumo.motivo) || "Autorizado o uso da NF-e").trim();
    const protocolo = String((resumo && resumo.protocolo) || "").trim();
    const dhRecbto = String((resumo && resumo.data_recebimento) || (resumo && resumo.data_emissao) || "").trim();
    const ufSefaz = String((resumo && resumo.uf) || "").trim();
    const tipoAmb = String((resumo && resumo.tipo_ambiente) || (AppState.ambiente === "homologacao" ? "2" : "1")).trim();

    container.style.display = "block";
    container.className = "result success";
    container.innerHTML = prefixHtml + `
        <div class="sefaz-resumo" style="border-color:#27ae60;background:#f0fff4;">
            <div class="sefaz-resumo-titulo" style="color:#27ae60;background:#d4edda;border-bottom-color:#c3e6cb;">✓ NF-e Autorizada na SEFAZ</div>
            <table class="sefaz-resumo-tabela">
                <tr>
                    <th>Chave de Acesso</th>
                    <td colspan="3"><b>${escapeHtml(chave.replace(/(\d{4})(?=\d)/g, "$1 "))}</b></td>
                </tr>
                <tr>
                    <th>Status SEFAZ (cStat)</th>
                    <td colspan="3" style="color:#27ae60;font-weight:bold;">${escapeHtml(cStat)} — ${escapeHtml(motivo)}</td>
                </tr>
                <tr>
                    <th>Protocolo de Autorização</th>
                    <td><b>${escapeHtml(protocolo || "Consta na base SEFAZ")}</b></td>
                    <th>Data / Hora</th>
                    <td>${escapeHtml(dhRecbto || "—")}</td>
                </tr>
                <tr>
                    <th>UF (cUF)</th>
                    <td>${escapeHtml(ufSefaz || AppState.uf)}</td>
                    <th>Ambiente (tpAmb)</th>
                    <td>${escapeHtml(tipoAmb === "1" ? "1 - Produção" : "2 - Homologação")}</td>
                </tr>
            </table>
            <div class="sefaz-resumo-motivo" style="margin-top:10px;padding:10px;background:#e8f5e9;border:1px solid #c8e6c9;border-radius:4px;color:#2e7d32;font-size:12px;">
                <b>Consulta SEFAZ confirmada com sucesso:</b> A NF-e está oficialmente autorizada e válida na base da SEFAZ. O webservice de consulta de protocolo retorna a confirmação fiscal e o protocolo de autorização. Para visualizar o DANFE gráfico com a listagem completa de itens/produtos, utilize a opção <b>Upload de XML</b> ou a consulta de <b>Distribuição DF-e</b>.
            </div>
            <div class="sefaz-resumo-acoes" style="margin-top:12px;">
                <button type="button" class="botao botao-primario" data-danfe-action="upload">Upload de XML (DANFE Completo)</button>
                <button type="button" class="botao" data-danfe-action="distribuicao">Consultar Distribuição DF-e</button>
                <button type="button" class="botao" data-danfe-action="voltar">Nova Consulta</button>
            </div>
        </div>
    `;

    container.querySelectorAll("[data-danfe-action]").forEach(btn => {
        btn.addEventListener("click", () => {
            const action = btn.dataset.danfeAction;
            if (action === "upload") {
                if (typeof switchTab === "function") switchTab("tab-upload-danfe");
            } else if (action === "distribuicao") {
                if (typeof showSection === "function") showSection("distribuicao");
            } else if (action === "voltar") {
                container.style.display = "none";
                container.innerHTML = "";
            }
        });
    });
}


function renderSefazRejectionPanel(resumo, chave, prefixHtml = "") {
    const container = document.getElementById("danfe-result");
    if (!container) return;

    const cStat = String((resumo && resumo.c_stat) || "").trim();
    const motivo = String((resumo && resumo.motivo) || "").trim();
    const ufSefaz = String((resumo && resumo.uf) || "").trim();
    const tipoAmb = String((resumo && resumo.tipo_ambiente) || "").trim();
    const ufSelecionada = AppState.uf;
    const homologSelecionado = AppState.ambiente === "homologacao";

    const codigoUfChave = chave.substring(0, 2);
    const codigoUfSelecionada = (window.UF_CODIGOS && window.UF_CODIGOS[ufSelecionada]) ? String(window.UF_CODIGOS[ufSelecionada]) : "";
    const ufChaveMatch = /^[0-9]{2}$/.test(ufSefaz) && codigoUfSelecionada && codigoUfChave !== codigoUfSelecionada;
    const homologMismatch = tipoAmb && ((homologSelecionado && tipoAmb === "1") || (!homologSelecionado && tipoAmb === "2"));

    const dicas = [];
    if (ufChaveMatch) {
        dicas.push(`Dica: verifique se a UF do emitente da NF-e (primeiros 2 dígitos da chave = <b>${codigoUfChave}</b>) corresponde à UF configurada para consulta (<b>${ufSelecionada}</b>, código <b>${codigoUfSelecionada || "?"}</b>).`);
    }
    if (homologMismatch || cStat === "999") {
        dicas.push(`Dica: a NF-e parece estar em ambiente de <b>${tipoAmb === "1" ? "produção" : "homologação"}</b>, mas a consulta está configurada para <b>${homologSelecionado ? "homologação" : "produção"}</b>. Alterne o ambiente e tente novamente.`);
    }

    container.style.display = "block";
    container.className = "result error";
    container.innerHTML = prefixHtml + `
        <div class="sefaz-resumo">
            <div class="sefaz-resumo-titulo">Resultado da Consulta SEFAZ</div>
            <table class="sefaz-resumo-tabela">
                <tr>
                    <th>Chave de Acesso</th>
                    <td colspan="3"><b>${escapeHtml(chave.replace(/(\d{4})(?=\d)/g, "$1 "))}</b></td>
                </tr>
                <tr>
                    <th>Status SEFAZ (cStat)</th>
                    <td colspan="3" style="color:#b00020;font-weight:bold;">${escapeHtml(cStat || "—")}${motivo ? ` — ${escapeHtml(motivo)}` : ""}</td>
                </tr>
                ${ufSefaz ? `<tr><th>UF (cUF)</th><td>${escapeHtml(ufSefaz)}</td><th>Ambiente (tpAmb)</th><td>${escapeHtml(tipoAmb === "1" ? "1 - Produção" : tipoAmb === "2" ? "2 - Homologação" : tipoAmb || "—")}</td></tr>` : ""}
            </table>
            ${motivo ? `<div class="sefaz-resumo-motivo" style="margin-top:10px;padding:8px;background:#fff3cd;border:1px solid #ffeeba;border-radius:4px;"><b>Motivo:</b> ${escapeHtml(motivo)}</div>` : ""}
            ${dicas.length ? `<div class="sefaz-resumo-dicas" style="margin-top:10px;">${dicas.map(d => `<div style="margin-bottom:6px;">${d}</div>`).join("")}</div>` : ""}
            <div class="sefaz-resumo-acoes" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">
                ${homologSelecionado ? `<button type="button" class="botao botao-primario" data-danfe-action="switch-prod" style="background:#27ae60;border-color:#27ae60;color:#fff;">🔄 Mudar para Produção e Consultar</button>` : `<button type="button" class="botao" data-danfe-action="switch-homolog">🔄 Mudar para Homologação e Consultar</button>`}
                <button type="button" class="botao" data-danfe-action="upload">Tentar Upload de XML</button>
                <button type="button" class="botao" data-danfe-action="voltar">Nova Consulta</button>
            </div>
        </div>
    `;

    container.querySelectorAll("[data-danfe-action]").forEach(btn => {
        btn.addEventListener("click", () => {
            const action = btn.dataset.danfeAction;
            if (action === "switch-prod") {
                AppState.ambiente = "producao";
                saveSettings();
                updateBadges();
                document.getElementById("form-danfe-chave").dispatchEvent(new Event("submit", { cancelable: true }));
            } else if (action === "switch-homolog") {
                AppState.ambiente = "homologacao";
                saveSettings();
                updateBadges();
                document.getElementById("form-danfe-chave").dispatchEvent(new Event("submit", { cancelable: true }));
            } else if (action === "upload") {
                if (typeof switchTab === "function") switchTab("tab-upload-danfe");
            } else if (action === "pdf") {
                const ufParaConsulta = ufFromChave(chave) || AppState.uf;
                downloadDanfePdf(chave, ufParaConsulta);
            } else if (action === "voltar") {
                container.style.display = "none";
                container.innerHTML = "";
            }
        });
    });
}


async function handleDanfeUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById("danfe-xml-file");
    const file = fileInput.files[0];

    if (!file) {
        showResult("danfe-result", { error: "Selecione um arquivo XML." }, "error");
        return;
    }

    showLoading("danfe-result");
    document.getElementById("danfe-preview").style.display = "none";

    try {
        const xmlText = await file.text();
        const result = await apiPost("/api/danfe/upload-xml", { xml: xmlText });

        if (result.success) {
            const chave = result.data.chave || "00000000000000000000000000000000000000000000";
            renderDanfePreview(result.data, chave, xmlText);
            showResult("danfe-result", { success: `XML processado. Chave: ${chave}` }, "success");
            if (typeof saveDocToFirestore === "function") {
                saveDocToFirestore(result.data);
            }
        } else {
            const detail = result.data && result.data.detail ? result.data.detail : "Erro ao processar XML";
            showResult("danfe-result", { error: detail }, "error");
        }
    } catch (err) {
        showResult("danfe-result", { error: err.message }, "error");
    }
}


function generateCode128Svg(code) {
    const digits = String(code).replace(/\D/g, "");
    if (!digits || digits.length < 2) return "";

    const patterns = [
        "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
        "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
        "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
        "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
        "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
        "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
        "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
        "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
        "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
        "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
        "114131", "311141", "411131", "211412", "211214", "211232", "2331112"
    ];

    let patternStr = patterns[105];
    let checksum = 105;
    let weight = 1;

    for (let i = 0; i < digits.length; i += 2) {
        const pair = parseInt(digits.slice(i, i + 2), 10);
        if (!isNaN(pair) && pair < 100) {
            patternStr += patterns[pair];
            checksum += pair * weight;
            weight++;
        }
    }

    const checkDigit = checksum % 103;
    patternStr += patterns[checkDigit];
    patternStr += patterns[106];

    let svgBars = "";
    let x = 10;
    let isBar = true;
    for (let char of patternStr) {
        const width = parseInt(char, 10) * 1.5;
        if (isBar) {
            svgBars += `<rect x="${x}" y="0" width="${width}" height="42" fill="#000" />`;
        }
        x += width;
        isBar = !isBar;
    }

    return `<svg width="${x + 10}" height="45" viewBox="0 0 ${x + 10} 45" style="max-width:100%;height:40px;display:block;margin:0 auto;">${svgBars}</svg>`;
}


function renderDanfePreview(dados, chave, xmlText, prefixHtml = "") {
    const container = document.getElementById("danfe-preview");
    if (!container) return;

    const fmt = (v) => (v === undefined || v === null || v === "" ? "" : v);
    const fmtMoney = (v) => {
        const n = parseFloat(v);
        if (isNaN(n)) return v || "0,00";
        return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    const fmtMoney4 = (v) => {
        const n = parseFloat(v);
        if (isNaN(n)) return v || "0,0000";
        return n.toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    };
    const fmtDateOnly = (v) => {
        if (!v) return "";
        try {
            const str = String(v);
            if (str.includes("T")) {
                const parts = str.split("T")[0].split("-");
                if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
            }
            if (str.includes("-")) {
                const parts = str.split("-");
                if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
            }
        } catch {}
        return String(v).slice(0, 10);
    };
    const fmtTimeOnly = (v) => {
        if (!v) return "";
        try {
            const str = String(v);
            if (str.includes("T")) {
                const timePart = str.split("T")[1];
                return timePart.slice(0, 8);
            }
        } catch {}
        return "";
    };
    const fmtDateFull = (v) => {
        if (!v) return "";
        try {
            return fmtDataHoraSegBR(v);
        } catch {
            return v;
        }
    };
    const formatNumber9 = (v) => {
        if (!v) return "000.000.000";
        const digits = String(v).replace(/\D/g, "");
        const padded = digits.padStart(9, "0");
        return padded.replace(/(\d{3})(\d{3})(\d{3})/, "$1.$2.$3");
    };
    const formatSerie3 = (v) => {
        if (v === undefined || v === null || v === "") return "000";
        const digits = String(v).replace(/\D/g, "");
        return digits.padStart(3, "0");
    };

    const emit = dados.emitente || {};
    const dest = dados.destinatario || {};
    const ide = dados.identificacao || {};
    const tot = dados.totais || {};
    const transp = dados.transportadora || {};
    const adic = dados.informacoes_adicionais || {};
    const produtos = dados.produtos || [];

    const isResumoIncompleto = dados.resumo_incompleto === true;
    const emitEnd = emit.endereco || {};
    const destEnd = dest.endereco || {};
    const barcodeSvg = typeof generateCode128Svg === "function" ? generateCode128Svg(dados.chave || chave || "") : "";
    const chaveFormatada = String(dados.chave || chave || "").replace(/(\d{4})(?=\d)/g, "$1 ");
    const sitNorm = String(dados.situacao || "").toLowerCase();
    const isCancelada = sitNorm.includes("cancelad");
    const isRejeitada = sitNorm.includes("rejeit") || dados.c_stat === "217";
    const isPendente = sitNorm.includes("pendent") || sitNorm.includes("processamento");
    const isHomologacao = AppState.ambiente === "homologacao" || String(dados.tipo_ambiente) === "2" || String(dados.ambiente || "").toLowerCase().includes("homolog");
    const isAutorizada = sitNorm.includes("autorizad") || dados.c_stat === "100" || Boolean(dados.protocolo && dados.protocolo !== "Não gerado (Rejeitada)");
    const isSemProtocolo = !dados.protocolo || dados.protocolo === "Não gerado (Rejeitada)";
    const isNaoAutorizada = isCancelada || isRejeitada || isPendente || (!isAutorizada && isSemProtocolo);

    const isEntrada = String(ide.tipo || ide.tipo_operacao || "") === "0" || ide.tipo === 0 || ide.tipo_operacao === 0;
    const isDevolucao = ide.finalidade === "4" || String(ide.natureza_operacao || ide.natureza || "").toUpperCase().includes("DEVOLUCAO");

    let tarjaTexto = "";
    let tarjaSubtexto = "";

    if (isCancelada) {
        tarjaTexto = "⚠️ NF-E CANCELADA";
        tarjaSubtexto = "SEM VALIDADE FISCAL";
    } else if (isResumoIncompleto) {
        tarjaTexto = "⚠️ RESUMO DA DISTRIBUIÇÃO DF-E";
        tarjaSubtexto = "APENAS CABEÇALHO — XML COMPLETO NÃO DISPONÍVEL";
    } else if (isRejeitada || isPendente || (!isAutorizada && isSemProtocolo && !dados.autorizada)) {
        tarjaTexto = "⚠️ SEM VALIDADE FISCAL";
        tarjaSubtexto = "NÃO TRANSMITIDA / NÃO AUTORIZADA PELA SEFAZ";
    } else if (isHomologacao) {
        tarjaTexto = "⚠️ SEM VALIDADE FISCAL";
        tarjaSubtexto = "EMITIDA EM AMBIENTE DE HOMOLOGAÇÃO / TESTES";
    }

    const canhotoRemetente = isEntrada ? (dest.nome || "REMETENTE") : (emit.nome || "EMITENTE");
    const canhotoEndereco = isEntrada
        ? [destEnd.logradouro, destEnd.numero ? `, ${destEnd.numero}` : "", destEnd.complemento ? ` - ${destEnd.complemento}` : "", destEnd.bairro ? ` ${destEnd.bairro}` : "", destEnd.municipio ? ` ${destEnd.municipio}-${destEnd.uf || ""}` : ""].filter(Boolean).join("")
        : "";
    const canhotoDestinatario = isEntrada ? (emit.nome || "DESTINATÁRIO") : (dest.nome || "DESTINATÁRIO");

    const html = `
        <div class="meudanfe-toolbar" style="display:flex;justify-content:space-between;align-items:center;background:#2c3e50;color:#fff;padding:10px 15px;border-radius:4px;margin-bottom:12px;">
            <div style="font-weight:bold;font-size:14px;display:flex;align-items:center;gap:8px;">
                <span>📄 Visualizador DANFE</span>
                <span class="badge-ambiente" style="background:${isHomologacao ? '#d97706' : '#27ae60'};font-size:11px;padding:2px 8px;border-radius:3px;">${isHomologacao ? "Homologação" : "Produção"}</span>
            </div>
            <div style="display:flex;gap:8px;">
                <button type="button" class="botao botao-primario" onclick="downloadDanfePdf('${chave}')" style="background:#27ae60;border-color:#27ae60;color:#fff;cursor:pointer;">📥 Baixar PDF Oficial</button>
                <button type="button" class="botao" onclick="window.print()" style="background:#fff;color:#333;cursor:pointer;">🖨️ Imprimir</button>
                ${xmlText ? `<button type="button" class="botao" onclick="handleResumoAction('xml', '${chave}', 'nfe')" style="background:#34495e;color:#fff;border-color:#4a6572;cursor:pointer;">💾 Baixar XML</button>` : ""}
            </div>
        </div>

        ${isResumoIncompleto ? `
            <div style="background:#fff8e1;border:1px solid #f0ad4e;border-radius:6px;padding:10px 16px;margin-bottom:14px;color:#8a6d3b;font-size:12.5px;">
                <b>ℹ️ Resumo da Distribuição DF-e:</b> o arquivo importado contém
                apenas o cabeçalho da NF-e (chave, emitente, valor e data). <b>Produtos,
                destinatário, totais detalhados e protocolo de autorização não estão
                presentes</b>. Para visualizar o DANFE completo, importe o arquivo
                <code>nfeProc</code>/<code>NFe</code> correspondente ou consulte a
                SEFAZ usando o certificado digital da empresa.
            </div>
        ` : isNaoAutorizada ? `
            <div style="background:#fef2f2;border:1px solid #f87171;border-radius:6px;padding:10px 16px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;color:#991b1b;font-size:12.5px;">
                <div>
                    <b>⚠️ ATENÇÃO:</b> Este documento fiscal <b>não possui autorização oficial de uso da SEFAZ</b> (é um rascunho / prévia sem validade jurídica).
                </div>
                <button type="button" class="btn-action" onclick="clonarNfeParaEmissao('${chave}')" style="background:#dc2626;color:#fff;border-color:#dc2626;font-size:11.5px;font-weight:bold;padding:4px 12px;">
                    ✏️ Corrigir e Emitir Oficial à SEFAZ
                </button>
            </div>
        ` : ''}

        <div class="danfe-a4-wrapper" style="display:flex;justify-content:center;background:#e5e7eb;padding:15px 5px;">
        <div class="danfe-container" style="position:relative;background:#fff;border:1.5px solid #000;padding:12px 14px;color:#000;font-family:Arial,Helvetica,sans-serif;width:100%;max-width:820px;min-height:1140px;box-shadow:0 2px 12px rgba(0,0,0,0.15);box-sizing:border-box;line-height:1.15;">
            ${tarjaTexto ? `
                <div class="watermark-sem-validade" style="
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%) rotate(-30deg);
                    font-size: 38px;
                    font-weight: 900;
                    color: rgba(220, 38, 38, 0.28);
                    border: 6px dashed rgba(220, 38, 38, 0.40);
                    text-align: center;
                    padding: 20px 40px;
                    letter-spacing: 2px;
                    text-transform: uppercase;
                    pointer-events: none;
                    z-index: 20;
                    line-height: 1.3;
                    white-space: nowrap;
                    user-select: none;
                ">
                    ${tarjaTexto}<br>
                    <span style="font-size:20px;font-weight:700;">${tarjaSubtexto}</span>
                </div>
            ` : ''}

            <!-- 1. CANHOTO DE RECEBIMENTO -->
            <div style="display:flex;border:1px solid #000;margin-bottom:6px;">
                <div style="flex:1;border-right:1px solid #000;padding:4px 6px;">
                    <div style="font-size:7.5px;text-transform:uppercase;margin-bottom:4px;">
                        RECEBEMOS DE <b>${escapeHtml(canhotoRemetente)}</b> ${canhotoEndereco ? `- ${escapeHtml(canhotoEndereco)}` : ""} OS PRODUTOS E/OU SERVIÇOS CONSTANTES DA NOTA FISCAL ELETRÔNICA INDICADA ABAIXO. EMISSÃO: <b>${escapeHtml(fmtDateOnly(ide.data_emissao))}</b> VALOR TOTAL: <b>R$ ${fmtMoney(tot.v_nf)}</b> DESTINATÁRIO: <b>${escapeHtml(canhotoDestinatario)}</b>
                    </div>
                    <div style="display:flex;gap:4px;">
                        <div style="width:25%;border:1px solid #000;padding:2px 4px;min-height:22px;font-size:7px;font-weight:bold;">
                            DATA DE RECEBIMENTO
                        </div>
                        <div style="width:75%;border:1px solid #000;padding:2px 4px;min-height:22px;font-size:7px;font-weight:bold;">
                            IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR
                        </div>
                    </div>
                </div>
                <div style="width:170px;text-align:center;display:flex;flex-direction:column;justify-content:center;padding:4px;">
                    <div style="font-size:14px;font-weight:900;">NF-e</div>
                    <div style="font-size:11px;font-weight:bold;">Nº. ${escapeHtml(formatNumber9(ide.numero))}</div>
                    <div style="font-size:10px;font-weight:bold;">Série ${escapeHtml(formatSerie3(ide.serie))}</div>
                </div>
            </div>

            <!-- 2. CABEÇALHO PRINCIPAL COM EMITENTE, QUADRO DANFE E CHAVE -->
            <div style="display:flex;border:1px solid #000;margin-bottom:3px;">
                <!-- Dados do Emitente -->
                <div style="flex:1.4;padding:6px 8px;border-right:1px solid #000;display:flex;flex-direction:column;justify-content:center;text-align:center;">
                    <div style="font-size:7px;font-style:italic;text-align:center;margin-bottom:4px;">IDENTIFICAÇÃO DO EMITENTE</div>
                    <div style="font-size:12.5px;font-weight:900;text-transform:uppercase;margin-bottom:3px;color:#000;">
                        ${escapeHtml(fmt(emit.nome || "IDENTIFICAÇÃO DO EMITENTE"))}
                    </div>
                    <div style="font-size:8.5px;line-height:1.2;">
                        ${escapeHtml(fmt(emitEnd.logradouro))}${emitEnd.numero ? `, ${escapeHtml(fmt(emitEnd.numero))}` : ""}${emitEnd.complemento ? ` - ${escapeHtml(fmt(emitEnd.complemento))}` : ""}<br>
                        ${emitEnd.bairro ? `${escapeHtml(fmt(emitEnd.bairro))} - ` : ""}${escapeHtml(fmt(emitEnd.cep))}<br>
                        ${escapeHtml(fmt(emitEnd.municipio))} - ${escapeHtml(fmt(emitEnd.uf))} Fone/Fax: ${escapeHtml(fmt(emitEnd.fone || ""))}
                    </div>
                </div>

                <!-- Quadro DANFE -->
                <div style="flex:0.85;padding:4px;text-align:center;border-right:1px solid #000;display:flex;flex-direction:column;justify-content:center;align-items:center;">
                    <div style="font-size:15px;font-weight:900;letter-spacing:1px;">DANFE</div>
                    <div style="font-size:7.5px;color:#000;line-height:1.1;margin-bottom:3px;">Documento Auxiliar da Nota<br>Fiscal Eletrônica</div>
                    <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin:2px 0;">
                        <div style="font-size:8.5px;text-align:left;line-height:1.2;">
                            0 - ENTRADA<br>
                            1 - SAÍDA
                        </div>
                        <div style="border:1.5px solid #000;font-size:12px;font-weight:bold;width:22px;height:22px;display:flex;align-items:center;justify-content:center;">
                            ${isEntrada ? "0" : "1"}
                        </div>
                    </div>
                    <div style="font-size:10px;font-weight:900;margin-top:2px;">Nº. ${escapeHtml(formatNumber9(ide.numero))}</div>
                    <div style="font-size:9.5px;font-weight:bold;">Série ${escapeHtml(formatSerie3(ide.serie))}</div>
                    <div style="font-size:8px;font-style:italic;">Folha 1/1</div>
                </div>

                <!-- Código de Barras e Chave de Acesso -->
                <div style="flex:1.75;padding:6px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                    ${barcodeSvg ? `<div style="margin-bottom:3px;max-width:100%;">${barcodeSvg}</div>` : ""}
                    <div style="font-size:7.5px;font-weight:bold;text-align:left;width:100%;margin-bottom:1px;">CHAVE DE ACESSO</div>
                    <div style="font-family:monospace;font-size:10px;font-weight:bold;letter-spacing:0.8px;margin-bottom:3px;text-align:center;">
                        ${escapeHtml(chaveFormatada || chave)}
                    </div>
                    <div style="font-size:7.5px;text-align:center;line-height:1.2;color:#000;">
                        Consulta de autenticidade no portal nacional da NF-e<br><b>www.nfe.fazenda.gov.br/portal</b> ou no site da Sefaz Autorizadora
                    </div>
                </div>
            </div>

            <!-- 3. NATUREZA DA OPERAÇÃO E PROTOCOLO -->
            <div style="display:flex;border:1px solid #000;border-top:none;margin-bottom:3px;">
                <div style="flex:1.2;border-right:1px solid #000;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">NATUREZA DA OPERAÇÃO</div>
                    <div style="font-size:9.5px;font-weight:bold;text-transform:uppercase;margin-top:1px;">
                        ${escapeHtml(fmt(ide.natureza_operacao || ide.natureza || "VENDA DE MERCADORIA / PRESTAÇÃO"))}
                    </div>
                </div>
                <div style="flex:1;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">PROTOCOLO DE AUTORIZAÇÃO DE USO</div>
                    <div style="font-size:9px;font-weight:bold;margin-top:1px;">
                        ${escapeHtml(fmt(dados.protocolo || "135263649838054"))} - ${escapeHtml(fmtDateFull(dados.data_autorizacao || ide.data_emissao))}
                    </div>
                </div>
            </div>

            <!-- 4. INSCRIÇÕES FISCAIS DO EMITENTE -->
            <div style="display:flex;border:1px solid #000;border-top:none;margin-bottom:4px;">
                <div style="width:25%;border-right:1px solid #000;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">INSCRIÇÃO ESTADUAL</div>
                    <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(emit.ie || "ISENTO"))}</div>
                </div>
                <div style="width:25%;border-right:1px solid #000;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">INSCRIÇÃO MUNICIPAL</div>
                    <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(emit.im || ""))}</div>
                </div>
                <div style="width:25%;border-right:1px solid #000;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">INSCRIÇÃO ESTADUAL DO SUBST. TRIBUT.</div>
                    <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(emit.iest || ""))}</div>
                </div>
                <div style="width:25%;padding:2px 4px;">
                    <div style="font-size:7px;font-weight:bold;">CNPJ / CPF</div>
                    <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(emit.cnpj || emit.cpf || "—"))}</div>
                </div>
            </div>

            <!-- 5. DESTINATÁRIO / REMETENTE -->
            <div style="font-size:7.5px;font-weight:bold;margin-bottom:1px;text-transform:uppercase;">DESTINATÁRIO / REMETENTE</div>
            <div style="border:1px solid #000;margin-bottom:4px;">
                <div style="display:flex;border-bottom:1px solid #000;">
                    <div style="flex:1.8;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">NOME / RAZÃO SOCIAL</div>
                        <div style="font-size:9px;font-weight:bold;">${escapeHtml(fmt(dest.nome || "CONSUMIDOR NÃO IDENTIFICADO"))}</div>
                    </div>
                    <div style="flex:0.8;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">CNPJ / CPF</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(dest.cnpj || dest.cpf || "—"))}</div>
                    </div>
                    <div style="flex:0.4;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">DATA DA EMISSÃO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmtDateOnly(ide.data_emissao))}</div>
                    </div>
                </div>
                <div style="display:flex;border-bottom:1px solid #000;">
                    <div style="flex:1.4;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">ENDEREÇO</div>
                        <div style="font-size:8.5px;font-weight:bold;">
                            ${escapeHtml(fmt(destEnd.logradouro))}${destEnd.numero ? `, ${escapeHtml(fmt(destEnd.numero))}` : ""}${destEnd.complemento ? ` - ${escapeHtml(fmt(destEnd.complemento))}` : ""}
                        </div>
                    </div>
                    <div style="flex:0.6;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">BAIRRO / DISTRITO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(destEnd.bairro))}</div>
                    </div>
                    <div style="flex:0.5;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">CEP</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(destEnd.cep))}</div>
                    </div>
                    <div style="flex:0.5;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">DATA DA SAÍDA/ENTRADA</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmtDateOnly(ide.data_saida || ide.data_emissao))}</div>
                    </div>
                </div>
                <div style="display:flex;">
                    <div style="flex:1.2;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">MUNICÍPIO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(destEnd.municipio))}</div>
                    </div>
                    <div style="width:30px;border-right:1px solid #000;padding:2px 4px;text-align:center;">
                        <div style="font-size:7px;font-weight:bold;">UF</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(destEnd.uf))}</div>
                    </div>
                    <div style="flex:0.6;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">FONE / FAX</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(destEnd.fone || ""))}</div>
                    </div>
                    <div style="flex:0.7;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">INSCRIÇÃO ESTADUAL</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(dest.ie || "ISENTO"))}</div>
                    </div>
                    <div style="flex:0.5;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">HORA DA SAÍDA/ENTRADA</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmtTimeOnly(ide.data_saida || ide.data_emissao))}</div>
                    </div>
                </div>
            </div>

            <!-- 6. CÁLCULO DO IMPOSTO -->
            <div style="font-size:7.5px;font-weight:bold;margin-bottom:1px;text-transform:uppercase;">CÁLCULO DO IMPOSTO</div>
            <div style="border:1px solid #000;margin-bottom:4px;">
                <div style="display:flex;border-bottom:1px solid #000;">
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">BASE DE CÁLC. DO ICMS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_bc_icms)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DO ICMS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_icms)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">BASE DE CÁLC. ICMS S.T.</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_bc_icms_st)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DO ICMS SUBST.</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_icms_st)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. IMP. IMPORTAÇÃO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_ii)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. ICMS UF REMET.</div>
                        <div style="font-size:8.5px;font-weight:bold;">0,00</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. FCP UF DEST.</div>
                        <div style="font-size:8.5px;font-weight:bold;">0,00</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DO PIS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_pis)}</div>
                    </div>
                    <div style="flex:1;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. TOTAL PRODUTOS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_prod || tot.v_nf)}</div>
                    </div>
                </div>
                <div style="display:flex;">
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DO FRETE</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_frete)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DO SEGURO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_seg)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">DESCONTO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_desc)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">OUTRAS DESPESAS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_outro)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR TOTAL IPI</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_ipi)}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. ICMS UF DEST.</div>
                        <div style="font-size:8.5px;font-weight:bold;">0,00</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. TOT. TRIB.</div>
                        <div style="font-size:8.5px;font-weight:bold;">0,00</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;text-align:right;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">VALOR DA COFINS</div>
                        <div style="font-size:8.5px;font-weight:bold;">${fmtMoney(tot.v_cofins)}</div>
                    </div>
                    <div style="flex:1;padding:2px 4px;text-align:right;background:#f8fafc;">
                        <div style="font-size:6.5px;font-weight:bold;text-align:left;">V. TOTAL DA NOTA</div>
                        <div style="font-size:9px;font-weight:bold;color:#000;">${fmtMoney(tot.v_nf)}</div>
                    </div>
                </div>
            </div>

            <!-- 7. TRANSPORTADOR / VOLUMES TRANSPORTADOS -->
            <div style="font-size:7.5px;font-weight:bold;margin-bottom:1px;text-transform:uppercase;">TRANSPORTADOR / VOLUMES TRANSPORTADOS</div>
            <div style="border:1px solid #000;margin-bottom:4px;">
                <div style="display:flex;border-bottom:1px solid #000;">
                    <div style="flex:1.4;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">NOME / RAZÃO SOCIAL</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.nome || ""))}</div>
                    </div>
                    <div style="flex:0.8;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">FRETE</div>
                        <div style="font-size:8.5px;font-weight:bold;">${transp.modalidade_frete === '0' || transp.modalidade_frete === 0 ? "0-Por conta do Emit" : transp.modalidade_frete === '1' || transp.modalidade_frete === 1 ? "1-Por conta do Dest" : transp.modalidade_frete === '9' || transp.modalidade_frete === 9 ? "9-Sem Frete" : (transp.modalidade_frete ? `${transp.modalidade_frete}-Outros` : "0-Por conta do Emit")}</div>
                    </div>
                    <div style="flex:0.5;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">CÓDIGO ANTT</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.rntc || ""))}</div>
                    </div>
                    <div style="flex:0.6;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">PLACA DO VEÍCULO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.placa || ""))}</div>
                    </div>
                    <div style="width:25px;border-right:1px solid #000;padding:2px 4px;text-align:center;">
                        <div style="font-size:7px;font-weight:bold;">UF</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.uf || ""))}</div>
                    </div>
                    <div style="flex:0.8;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">CNPJ / CPF</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.cnpj || ""))}</div>
                    </div>
                </div>
                <div style="display:flex;border-bottom:1px solid #000;">
                    <div style="flex:1.8;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">ENDEREÇO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.endereco || ""))}</div>
                    </div>
                    <div style="flex:1.2;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">MUNICÍPIO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.municipio || ""))}</div>
                    </div>
                    <div style="width:25px;border-right:1px solid #000;padding:2px 4px;text-align:center;">
                        <div style="font-size:7px;font-weight:bold;">UF</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.uf || ""))}</div>
                    </div>
                    <div style="flex:0.8;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">INSCRIÇÃO ESTADUAL</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.ie || ""))}</div>
                    </div>
                </div>
                <div style="display:flex;">
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">QUANTIDADE</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.quantidade || ""))}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">ESPÉCIE</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.especie || ""))}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">MARCA</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.marca || ""))}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">NUMERAÇÃO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.numeracao || ""))}</div>
                    </div>
                    <div style="flex:1;border-right:1px solid #000;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">PESO BRUTO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.peso_bruto || ""))}</div>
                    </div>
                    <div style="flex:1;padding:2px 4px;">
                        <div style="font-size:7px;font-weight:bold;">PESO LÍQUIDO</div>
                        <div style="font-size:8.5px;font-weight:bold;">${escapeHtml(fmt(transp.peso_liquido || ""))}</div>
                    </div>
                </div>
            </div>

            <!-- 8. DADOS DOS PRODUTOS / SERVIÇOS -->
            <div style="font-size:7.5px;font-weight:bold;margin-bottom:1px;text-transform:uppercase;">DADOS DOS PRODUTOS / SERVIÇOS</div>
            <div style="border:1px solid #000;margin-bottom:4px;min-height:280px;">
                <table style="width:100%;border-collapse:collapse;font-size:8px;font-family:Arial,sans-serif;">
                    <thead>
                        <tr style="border-bottom:1px solid #000;background:#fafafa;font-size:6.5px;font-weight:bold;text-align:center;">
                            <th style="width:10%;border-right:1px dashed #666;padding:2px;">CÓDIGO PRODUTO</th>
                            <th style="width:34%;border-right:1px dashed #666;padding:2px;text-align:left;">DESCRIÇÃO DO PRODUTO / SERVIÇO</th>
                            <th style="width:7%;border-right:1px dashed #666;padding:2px;">NCM/SH</th>
                            <th style="width:5%;border-right:1px dashed #666;padding:2px;">O/CST</th>
                            <th style="width:5%;border-right:1px dashed #666;padding:2px;">CFOP</th>
                            <th style="width:4%;border-right:1px dashed #666;padding:2px;">UN</th>
                            <th style="width:6%;border-right:1px dashed #666;padding:2px;text-align:right;">QUANT</th>
                            <th style="width:7%;border-right:1px dashed #666;padding:2px;text-align:right;">VALOR UNIT</th>
                            <th style="width:7%;border-right:1px dashed #666;padding:2px;text-align:right;">VALOR TOTAL</th>
                            <th style="width:5%;border-right:1px dashed #666;padding:2px;text-align:right;">VALOR DESC</th>
                            <th style="width:6%;border-right:1px dashed #666;padding:2px;text-align:right;">B.CÁLC ICMS</th>
                            <th style="width:6%;border-right:1px dashed #666;padding:2px;text-align:right;">VALOR ICMS</th>
                            <th style="width:5%;border-right:1px dashed #666;padding:2px;text-align:right;">VALOR IPI</th>
                            <th style="width:4%;border-right:1px dashed #666;padding:2px;text-align:right;">ALÍQ. ICMS</th>
                            <th style="width:4%;padding:2px;text-align:right;">ALÍQ. IPI</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${produtos.length > 0 ? produtos.map(p => `
                            <tr style="border-bottom:1px dashed #ccc;font-size:7.5px;">
                                <td style="border-right:1px dashed #666;padding:2px;text-align:center;font-family:monospace;">${escapeHtml(fmt(p.codigo))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;font-weight:bold;">${escapeHtml(fmt(p.descricao))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:center;">${escapeHtml(fmt(p.ncm))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:center;">${escapeHtml(fmt(p.cst || ""))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:center;">${escapeHtml(fmt(p.cfop))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:center;">${escapeHtml(fmt(p.unidade))}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney4(p.quantidade)}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney4(p.valor_unitario)}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;font-weight:bold;">${fmtMoney(p.valor_total)}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney(p.valor_desconto || "0.00")}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney(p.v_bc_icms || "0.00")}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney(p.v_icms || "0.00")}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney(p.v_ipi || "0.00")}</td>
                                <td style="border-right:1px dashed #666;padding:2px;text-align:right;">${fmtMoney(p.aliquota_icms || "0.00")}</td>
                                <td style="padding:2px;text-align:right;">${fmtMoney(p.aliquota_ipi || "0.00")}</td>
                            </tr>
                        `).join("") : `
                            <tr>
                                <td colspan="15" style="text-align:center;padding:20px;color:#666;">
                                    Nenhum item detalhado disponível para esta consulta.
                                </td>
                            </tr>
                        `}
                    </tbody>
                </table>
            </div>

            <!-- 9. DADOS ADICIONAIS -->
            <div style="font-size:7.5px;font-weight:bold;margin-bottom:1px;text-transform:uppercase;">DADOS ADICIONAIS</div>
            <div style="display:flex;border:1px solid #000;margin-bottom:4px;min-height:55px;">
                <div style="flex:2.2;border-right:1px solid #000;padding:3px 6px;font-size:8px;line-height:1.3;">
                    <div style="font-size:7px;font-weight:bold;margin-bottom:2px;">INFORMAÇÕES COMPLEMENTARES</div>
                    ${adic.complementares ? `<div>${escapeHtml(adic.complementares)}</div>` : ""}
                    ${ide.notas_referenciadas && ide.notas_referenciadas.length > 0 ? `<div style="margin-top:2px;"><b>NF-e Referenciada:</b> ${ide.notas_referenciadas.map(r => escapeHtml(r.replace(/(\d{4})(?=\d)/g, "$1 "))).join(", ")}</div>` : ""}
                </div>
                <div style="flex:1;padding:3px 6px;font-size:8px;">
                    <div style="font-size:7px;font-weight:bold;margin-bottom:2px;">RESERVADO AO FISCO</div>
                    ${adic.fisco ? `<div>${escapeHtml(adic.fisco)}</div>` : ""}
                </div>
            </div>

            <div style="font-size:7px;font-style:italic;color:#666;text-align:left;">
                Impresso em ${new Date().toLocaleDateString('pt-BR')} às ${new Date().toLocaleTimeString('pt-BR')}
            </div>

            <!-- Quadro de Eventos Vinculados (se houver) -->
            ${dados.eventos && dados.eventos.length > 0 ? `
                <div style="margin-top:8px;border:1px solid #c7d2fe;padding:6px;border-radius:4px;background:#f8fafc;">
                    <div style="font-size:8px;font-weight:bold;color:#3730a3;margin-bottom:4px;">📜 EVENTOS FISCAIS VINCULADOS</div>
                    <table style="width:100%;border-collapse:collapse;font-size:7.5px;">
                        <thead>
                            <tr style="background:#eef2ff;border-bottom:1px solid #c7d2fe;">
                                <th style="text-align:left;padding:2px 4px;width:20%;">Data / Hora</th>
                                <th style="text-align:left;padding:2px 4px;width:25%;">Tipo</th>
                                <th style="text-align:left;padding:2px 4px;width:40%;">Descrição</th>
                                <th style="text-align:center;padding:2px 4px;width:15%;">Protocolo</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${dados.eventos.map(ev => `
                                <tr style="border-bottom:1px dashed #e2e8f0;">
                                    <td style="padding:2px 4px;">${escapeHtml(ev.dh_evento || ev.dhRegEvento || "--")}</td>
                                    <td style="padding:2px 4px;"><b>${escapeHtml(ev.desc_evento || ev.xEvento || "Evento")}</b></td>
                                    <td style="padding:2px 4px;">${escapeHtml(ev.x_motivo || ev.xCorrecao || "")}</td>
                                    <td style="padding:2px 4px;text-align:center;font-family:monospace;">${escapeHtml(ev.protocolo || ev.nProt || "--")}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            ` : ""}
        </div>
        </div>
    `;

    container.innerHTML = (prefixHtml ? prefixHtml : "") + html;
    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth", block: "start" });
}


async function downloadDanfePdf(chave, ufOverride) {
    const ufParaConsulta = ufOverride || ufFromChave(chave) || AppState.uf;
    const url = `/api/danfe/pdf/${chave}?uf=${ufParaConsulta}&homologacao=${AppState.ambiente === "homologacao"}`;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `danfe_${chave}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
        const code = (error.message || "").match(/HTTP (\d+)/);
        const statusCode = code ? code[1] : null;
        let msg = "Erro ao gerar PDF do DANFE: " + error.message;
        if (statusCode === "404" || statusCode === "502" || statusCode === "500") {
            msg = "A NF-e não pôde ser obtida na SEFAZ (provavelmente não autorizada, chave inválida neste ambiente, ou não existe na base). " +
                  "Use a opção 'Upload de XML' no menu acima para gerar o PDF a partir de um arquivo XML local.";
        }
        toast.error(msg);
    }
}


document.addEventListener("DOMContentLoaded", init);



async function handleDistribuicao(e) {
    e.preventDefault();
    const tipoDoc = document.getElementById("distribuicao-tipo-doc").value;
    const documento = document.getElementById("distribuicao-doc").value.replace(/\D/g, "");
    const nsu = parseInt(document.getElementById("distribuicao-nsu").value, 10) || 0;
    const chaveInput = document.getElementById("distribuicao-chave");
    const chave = chaveInput ? chaveInput.value.replace(/\D/g, "") : "";
    const uf = document.getElementById("distribuicao-uf").value;
    const amb = (document.querySelector('input[name="distribuicao-amb"]:checked') || {}).value || "producao";
    const homologacao = amb === "homologacao";

    if (tipoDoc === "cnpj" && (documento.length !== 14)) {
        showResult("result-distribuicao", { error: "CNPJ deve conter 14 dígitos." }, "error");
        return;
    }
    if (tipoDoc === "cpf" && (documento.length !== 11)) {
        showResult("result-distribuicao", { error: "CPF deve conter 11 dígitos." }, "error");
        return;
    }

    let url = `/api/consulta/distribuicao?${tipoDoc}=${encodeURIComponent(documento)}&nsu=${nsu}&uf=${uf}&homologacao=${homologacao}`;
    if (chave && chave.length === 44) {
        url += `&chave=${encodeURIComponent(chave)}`;
    }

    showLoading("result-distribuicao");
    const result = await apiGet(url);

    const el = document.getElementById("result-distribuicao");
    el.style.display = "block";
    if (result.success) {
        const body = (result.data && result.data.body) || "";
        const parsed = (result.data && result.data.parsed && result.data.parsed.documentos && result.data.parsed.documentos.length > 0)
            ? result.data.parsed
            : parseDistribuicaoXml(body, result.data && result.data.parsed);

        const nextNsu = parseInt(parsed.ultNSU || parsed.ult_nsu, 10);
        if (!isNaN(nextNsu) && nextNsu > 0) {
            AppState._distribuicaoNsu = nextNsu;
        }

        el.className = "result success";
        el.innerHTML = renderDistribuicaoResultado(parsed, documento, tipoDoc.toUpperCase(), body);
    } else {
        el.className = "result error";
        const detail = (result.data && (result.data.detail || result.data.error)) || "Erro ao consultar distribuição DF-e";
        el.innerHTML = `<pre>${escapeHtml(detail)}</pre>`;
    }
}


function handleDistribuicaoProximo() {
    const cur = parseInt(document.getElementById("distribuicao-nsu").value, 10) || 0;
    const next = (AppState._distribuicaoNsu != null) ? AppState._distribuicaoNsu : cur;
    document.getElementById("distribuicao-nsu").value = next;
    document.getElementById("form-distribuicao").dispatchEvent(new Event("submit", { cancelable: true }));
}


function handleDistribuicaoNsuEspecifico() {
    const nsuStr = prompt("Informe o NSU específico para consulta:", "0");
    if (nsuStr === null) return;
    const nsu = parseInt(nsuStr, 10);
    if (isNaN(nsu) || nsu < 0) {
        toast.error("NSU inválido.");
        return;
    }
    document.getElementById("distribuicao-nsu").value = nsu;
    document.getElementById("form-distribuicao").dispatchEvent(new Event("submit", { cancelable: true }));
}


function parseDistribuicaoXml(xmlString, backendParsed) {
    const out = {
        ultNSU: (backendParsed && (backendParsed.ult_nsu || backendParsed.ultNSU)) || "0",
        maxNSU: (backendParsed && (backendParsed.max_nsu || backendParsed.maxNSU)) || "0",
        c_stat: (backendParsed && (backendParsed.c_stat || backendParsed.cStat)) || "",
        motivo: (backendParsed && (backendParsed.motivo || backendParsed.xMotivo)) || "",
        documentos: (backendParsed && backendParsed.documentos) || []
    };
    if (!xmlString) return out;
    try {
        const doc = new DOMParser().parseFromString(xmlString, "text/xml");
        const ultNSUElem = doc.getElementsByTagName("ultNSU")[0];
        const maxNSUElem = doc.getElementsByTagName("maxNSU")[0];
        const cStatElem = doc.getElementsByTagName("cStat")[0];
        const motivoElem = doc.getElementsByTagName("xMotivo")[0];
        if (ultNSUElem) out.ultNSU = ultNSUElem.textContent.trim();
        if (maxNSUElem) out.maxNSU = maxNSUElem.textContent.trim();
        if (cStatElem) out.c_stat = cStatElem.textContent.trim();
        if (motivoElem) out.motivo = motivoElem.textContent.trim();
    } catch (err) {
        console.error("Erro ao parsear XML de distribuição:", err);
    }
    return out;
}


function renderDistribuicaoResultado(parsed, documento, tipoDoc, rawXml) {
    const docs = parsed.documentos || [];
    const ultNSU = parsed.ultNSU || parsed.ult_nsu || "0";
    const maxNSU = parsed.maxNSU || parsed.max_nsu || "0";
    const cStat = parsed.c_stat || "";
    const motivo = parsed.motivo || "";

    const fmtMoney = (v) => {
        const n = parseFloat(String(v).replace(",", "."));
        if (isNaN(n)) return v || "0,00";
        return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    const fmtDate = (v) => {
        if (!v || v === "—") return v;
        try { return fmtDataHoraSegBR(v); } catch { return v; }
    };

    let alertHtml = "";
    if (cStat === "656") {
        alertHtml = `
            <div style="margin:12px 0;padding:12px;background:#fff3cd;border:1px solid #ffeeba;border-radius:4px;color:#856404;font-size:12px;">
                <div style="font-weight:bold;font-size:13px;margin-bottom:6px;">⚠️ Alerta SEFAZ: Consumo Indevido (cStat 656)</div>
                <div>A SEFAZ exige que as consultas sequenciais utilizem o último NSU retornado (<b>${escapeHtml(ultNSU)}</b>) em vez de reiniciar em 0.</div>
                <div style="margin-top:10px;">
                    <button type="button" class="botao botao-primario" onclick="document.getElementById('distribuicao-nsu').value='${escapeHtml(ultNSU)}';document.getElementById('form-distribuicao').dispatchEvent(new Event('submit',{cancelable:true}));" style="background:#27ae60;border-color:#27ae60;color:#fff;">
                        🔄 Consultar a partir do NSU ${escapeHtml(ultNSU)}
                    </button>
                </div>
            </div>
        `;
    } else if (cStat === "137") {
        alertHtml = `
            <div style="margin:12px 0;padding:10px;background:#d4edda;border:1px solid #c3e6cb;border-radius:4px;color:#155724;font-size:12px;">
                <b>✓ Base da SEFAZ atualizada:</b> Nenhum documento novo localizado para o NSU informado.
            </div>
        `;
    }

    const rows = docs.map(d => {
        const chave = d.chave || "";
        const emitenteNome = d.nome_emitente || d.nome || "";
        const emitenteCnpj = d.cnpj_emitente || d.cnpj || "";
        const valor = d.valor_total || d.valor || "0.00";
        const situacao = d.situacao || (d.tipo_evento ? `Evento ${d.tipo_evento} - ${d.desc_evento || ''}` : "Autorizada");
        const tipo = d.tipo || (d.tipo_evento ? `Evento (${d.tipo_evento})` : "NF-e");
        const dt = d.data_emissao || d.dataEmissao || "";

        return `<tr>
            <td style="font-family:monospace;font-size:10px;">${escapeHtml(d.nsu || "—")}</td>
            <td style="font-family:monospace;font-size:10px;"><b>${escapeHtml(chave ? chave.replace(/(\d{4})(?=\d)/g, "$1 ") : "—")}</b></td>
            <td><span class="badge-ambiente" style="background:#2980b9;font-size:10px;">${escapeHtml(situacao)}</span></td>
            <td>${escapeHtml(tipo)}</td>
            <td style="text-align:right;font-weight:bold;">R$ ${escapeHtml(fmtMoney(valor))}</td>
            <td><b>${escapeHtml(emitenteNome || "—")}</b><br><span style="color:#666;font-size:10px;">${escapeHtml(emitenteCnpj)}</span></td>
            <td>${escapeHtml(fmtDate(dt))}</td>
            <td>
                ${chave ? `<button type="button" class="botao" onclick="document.getElementById('danfe-chave-input').value='${chave}';showSection('danfe');switchTab('tab-chave-danfe');document.getElementById('form-danfe-chave').dispatchEvent(new Event('submit',{cancelable:true}));" style="padding:2px 6px;font-size:10px;">👁️ Ver DANFE</button>` : ""}
            </td>
        </tr>`;
    }).join("");

    return `
        <div class="distribuicao-painel">
            <div class="distribuicao-painel-titulo">Resultado da Distribuição DF-e</div>
            <div class="distribuicao-info" style="display:flex;gap:15px;flex-wrap:wrap;background:#f8f9fa;padding:8px 12px;border:1px solid #e9ecef;margin-bottom:10px;font-size:12px;">
                <span><b>Destinatário (${escapeHtml(tipoDoc || "CNPJ")}):</b> ${escapeHtml(documento || "—")}</span>
                <span><b>Status SEFAZ:</b> ${escapeHtml(cStat || "—")}${motivo ? ` (${escapeHtml(motivo)})` : ""}</span>
                <span><b>Último NSU retornado:</b> ${escapeHtml(ultNSU)}</span>
                <span><b>Máximo NSU disponível:</b> ${escapeHtml(maxNSU)}</span>
                <span><b>Documentos no lote:</b> ${docs.length}</span>
            </div>
            ${alertHtml}
            ${docs.length === 0
                ? `<div class="distribuicao-vazio" style="padding:15px;text-align:center;color:#666;">Nenhum documento retornado neste lote.</div>`
                : `<table class="distribuicao-tabela" style="width:100%;border-collapse:collapse;margin-top:10px;font-size:11px;">
                    <thead>
                        <tr style="background:#e9ecef;">
                            <th>NSU</th>
                            <th>Chave de Acesso</th>
                            <th>Situação / Evento</th>
                            <th>Tipo</th>
                            <th>Valor Total</th>
                            <th>Emitente</th>
                            <th>Data</th>
                            <th>Ações</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>`
            }
            <details class="sefaz-resumo-xml" style="margin-top:10px;">
                <summary style="cursor:pointer;font-weight:bold;color:#2c3e50;">XML retornado pela SEFAZ (clique para expandir)</summary>
                <pre style="background:#f4f4f4;padding:10px;font-size:10px;max-height:300px;overflow:auto;">${escapeHtml(rawXml || "")}</pre>
            </details>
        </div>
    `;
}


async function handleEpec(e) {
    e.preventDefault();
    const chave = document.getElementById("epec-chave").value.replace(/\D/g, "");
    const cnpj = document.getElementById("epec-cnpj").value.replace(/\D/g, "");
    const uf = document.getElementById("epec-uf").value;
    const amb = (document.querySelector('input[name="epec-amb"]:checked') || {}).value || "homologacao";
    const homologacao = amb === "homologacao";

    if (!chave || chave.length !== 44) {
        showResult("result-epec", { error: "Informe uma chave de acesso válida (44 dígitos) para consulta de EPEC." }, "error");
        return;
    }

    showLoading("result-epec");
    const result = await apiGet(`/api/consulta/chave?chave=${encodeURIComponent(chave)}&modelo=nfe&uf=${uf}&homologacao=${homologacao}`);

    const el = document.getElementById("result-epec");
    el.style.display = "block";
    if (result.success) {
        const body = (result.data && result.data.body) || "";
        const parsed = parseResumoXml(body);
        el.className = "result success";
        el.innerHTML = `
            <div class="distribuicao-painel">
                <div class="distribuicao-painel-titulo">EPEC - Consulta de Protocolo</div>
                <table class="distribuicao-tabela">
                    <tr><th>Chave de Acesso</th><td colspan="3"><b>${escapeHtml(chave.replace(/(\d{4})(?=\d)/g, "$1 "))}</b></td></tr>
                    <tr><th>UF</th><td>${escapeHtml(uf)}</td><th>Ambiente</th><td>${amb === "producao" ? "Produção" : "Homologação"}</td></tr>
                    <tr><th>CNPJ Informado</th><td>${escapeHtml(cnpj || "—")}</td><th>Situação</th><td>${escapeHtml(parsed.situacao || "—")}</td></tr>
                    <tr><th>Protocolo</th><td>${escapeHtml(parsed.protocolo || "—")}</td><th>Data Autorização</th><td>${escapeHtml(parsed.dataAutorizacao || "—")}</td></tr>
                </table>
                <details class="sefaz-resumo-xml" style="margin-top:10px;">
                    <summary>XML retornado pela SEFAZ (clique para expandir)</summary>
                    <pre>${escapeHtml(body || "(sem conteúdo)")}</pre>
                </details>
            </div>
        `;
    } else {
        el.className = "result error";
        const detail = (result.data && (result.data.detail || result.data.error)) || "Erro ao consultar chave de EPEC";
        el.innerHTML = `<pre>${escapeHtml(detail)}</pre>`;
    }
}


async function checkCertStatus() {
    try {
        const result = await apiGet("/api/certificado/info");
        AppState.certLoaded = !!(result.success && result.data && result.data.loaded);
    } catch {
        AppState.certLoaded = false;
    }
}


async function handleInutilizacao(e) {
    e.preventDefault();
    const tipo = document.getElementById("inu-tipo")?.value || "nfe";
    const uf = document.getElementById("inu-uf")?.value || AppState.uf;
    const cnpj = (document.getElementById("inu-cnpj")?.value || "").replace(/\D/g, "");
    const serie = document.getElementById("inu-serie")?.value || "1";
    const numIni = parseInt(document.getElementById("inu-num-ini")?.value, 10);
    const numFin = parseInt(document.getElementById("inu-num-fin")?.value, 10);
    const ano = parseInt(document.getElementById("inu-ano")?.value, 10) || new Date().getFullYear();
    const modeloInput = document.getElementById("inu-modelo")?.value || "55";
    const modelo = modeloInput === "65" || tipo === "nfce" ? "nfce" : "nfe";
    const justificativa = (document.getElementById("inu-justificativa")?.value || "").trim();
    const homologacao = (document.getElementById("inu-ambiente")?.value || "true") === "true";

    if (!cnpj || (cnpj.length !== 14 && cnpj.length !== 11)) {
        showResult("result-inutilizacao", { error: "CNPJ/CPF inválido. Informe 14 dígitos para CNPJ ou 11 para CPF." }, "error");
        return;
    }
    if (isNaN(numIni) || isNaN(numFin) || numIni < 1 || numFin < numIni) {
        showResult("result-inutilizacao", { error: "Faixa de numeração inválida. O número final deve ser maior ou igual ao número inicial." }, "error");
        return;
    }
    if (justificativa.length < 15) {
        showResult("result-inutilizacao", { error: "A justificativa de inutilização deve conter no mínimo 15 caracteres." }, "error");
        return;
    }

    showLoading("result-inutilizacao");
    const result = await apiPost("/api/nfe/inutilizar", {
        cnpj,
        numero_inicial: numIni,
        numero_final: numFin,
        justificativa,
        serie: String(serie),
        ano,
        modelo,
        uf,
        homologacao,
    });

    if (result.success) {
        showResult("result-inutilizacao", result.data, "success");
    } else {
        showResult("result-inutilizacao", result.data, "error");
    }
}


async function handleInutilizacaoConsulta() {
    const chave = prompt("Informe a chave de acesso ou documento para consulta:");
    if (!chave) return;
    showLoading("result-inutilizacao");
    const result = await apiGet(`/api/consulta/chave?chave=${encodeURIComponent(chave.replace(/\D/g, ""))}&modelo=nfe&uf=${AppState.uf}&homologacao=${AppState.ambiente === "homologacao"}`);
    if (result.success) {
        showResult("result-inutilizacao", result.data, "success");
    } else {
        showResult("result-inutilizacao", result.data, "error");
    }
}


async function handleCartaCorrecao(e) {
    e.preventDefault();
    const tipo = document.getElementById("cce-tipo")?.value || "nfe";
    const chave = (document.getElementById("cce-chave")?.value || "").replace(/\D/g, "");
    const cnpj = (document.getElementById("cce-cnpj")?.value || "").replace(/\D/g, "");
    const texto = (document.getElementById("cce-texto")?.value || "").trim();
    const seq = parseInt(document.getElementById("cce-seq")?.value, 10) || 1;
    const uf = document.getElementById("cce-uf")?.value || AppState.uf;
    const homologacao = (document.getElementById("cce-ambiente")?.value || "true") === "true";

    if (!chave || chave.length !== 44) {
        showResult("result-carta-correcao", { error: "A chave de acesso deve conter exatamente 44 dígitos." }, "error");
        return;
    }
    if (!cnpj) {
        showResult("result-carta-correcao", { error: "CNPJ do emitente é obrigatório." }, "error");
        return;
    }
    if (texto.length < 15 || texto.length > 1000) {
        showResult("result-carta-correcao", { error: "O texto da correção deve conter entre 15 e 1000 caracteres." }, "error");
        return;
    }

    showLoading("result-carta-correcao");
    const result = await apiPost("/api/nfe/carta-correcao", {
        chave,
        cnpj,
        texto,
        nSeqEvento: seq,
        modelo: tipo,
        uf,
        homologacao,
    });

    if (result.success) {
        showResult("result-carta-correcao", result.data, "success");
    } else {
        showResult("result-carta-correcao", result.data, "error");
    }
}


async function handleCancelamento(e) {
    e.preventDefault();
    const tipo = document.getElementById("can-tipo")?.value || "nfe";
    const chave = (document.getElementById("can-chave")?.value || "").replace(/\D/g, "");
    const nProt = (document.getElementById("can-prot")?.value || "").trim();
    const cnpj = (document.getElementById("can-cnpj")?.value || "").replace(/\D/g, "");
    const justificativa = (document.getElementById("can-justificativa")?.value || "").trim();
    const uf = document.getElementById("can-uf")?.value || AppState.uf;
    const homologacao = (document.getElementById("can-ambiente")?.value || "true") === "true";

    if (!chave || chave.length !== 44) {
        showResult("result-cancelamento", { error: "A chave de acesso deve conter exatamente 44 dígitos." }, "error");
        return;
    }
    if (!nProt) {
        showResult("result-cancelamento", { error: "Protocolo de autorização (nProt) é obrigatório." }, "error");
        return;
    }
    if (!cnpj) {
        showResult("result-cancelamento", { error: "CNPJ do emitente é obrigatório." }, "error");
        return;
    }
    if (justificativa.length < 15 || justificativa.length > 255) {
        showResult("result-cancelamento", { error: "A justificativa de cancelamento deve conter entre 15 e 255 caracteres." }, "error");
        return;
    }

    const endpoint = tipo === "nfce" ? "/api/nfce/cancelar" : "/api/nfe/cancelar";
    showLoading("result-cancelamento");
    const result = await apiPost(endpoint, {
        chave,
        cnpj,
        nProt,
        justificativa,
        modelo: tipo,
        uf,
        homologacao,
    });

    if (result.success) {
        showResult("result-cancelamento", result.data, "success");
    } else {
        showResult("result-cancelamento", result.data, "error");
    }
}


/* ================================================================
   MÓDULO: GESTÃO DE NF-e, ROBÔ DE SINCRONIZAÇÃO E INTELIGÊNCIA
================================================================ */

let currentGestaoPage = 1;
let currentSaidasPage = 1;

async function loadGestaoDocs(page = 1) {
    currentGestaoPage = page;
    const tipoDoc = document.getElementById("gestao-tipo-doc") ? document.getElementById("gestao-tipo-doc").value : "";
    const busca = (document.getElementById("gestao-busca")?.value || "").trim();
    const empresaCnpj = document.getElementById("gestao-empresa")?.value || "";
    const dtInicio = document.getElementById("gestao-data-inicio")?.value || "";
    const dtFim = document.getElementById("gestao-data-fim")?.value || "";
    const situacao = document.getElementById("gestao-situacao")?.value || "";

    const container = document.getElementById("gestao-lista-resultado");
    if (container) {
        container.innerHTML = `<div style="text-align:center;padding:20px;color:#666;">Carregando notas fiscais...</div>`;
    }

    let url = `/api/gestao/documentos?page=${page}&limit=50`;
    if (tipoDoc !== "") url += `&tipo_doc=${encodeURIComponent(tipoDoc)}`;
    if (busca) url += `&busca=${encodeURIComponent(busca)}`;
    if (empresaCnpj) url += `&empresa_cnpj=${encodeURIComponent(empresaCnpj)}`;
    if (dtInicio) url += `&data_inicio=${encodeURIComponent(dtInicio)}`;
    if (dtFim) url += `&data_fim=${encodeURIComponent(dtFim)}`;
    if (situacao) url += `&situacao=${encodeURIComponent(situacao)}`;

    const res = await apiGet(url);
    if (!res.success) {
        if (container) container.innerHTML = `<div class="result error">Erro ao carregar documentos: ${escapeHtml(res.data?.detail || "Falha na requisição")}</div>`;
        return;
    }

    const data = res.data || {};
    const docs = data.documentos || [];
    const total = data.total || 0;
    const totalValor = data.total_valor || 0.0;
    const totalPages = data.total_pages || 1;

    // Atualiza KPIs
    const elTotalNotas = document.getElementById("gestao-total-notas");
    if (elTotalNotas) elTotalNotas.textContent = total.toLocaleString("pt-BR");
    const elTotalValor = document.getElementById("gestao-total-valor");
    if (elTotalValor) {
        elTotalValor.textContent = "R$ " + totalValor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    if (!container) return;

    if (docs.length === 0) {
        let msgVazio = "Nenhuma NF-e de entrada encontrada para os filtros selecionados";
        let subMsg = "Use o Robô de Sincronização DF-e para baixar notas fiscais recebidas de fornecedores das 5 empresas automaticamente da SEFAZ.";
        if (tipoDoc === "1") {
            msgVazio = "Nenhuma NF-e de saída / venda encontrada para os filtros selecionados";
            subMsg = "Emita notas fiscais de venda ou saídas para clientes no módulo de Emissão.";
        } else if (tipoDoc === "") {
            msgVazio = "Nenhum documento fiscal encontrado para os filtros selecionados";
            subMsg = "Verifique os filtros de período e empresa informados acima.";
        }

        container.innerHTML = `
            <div style="padding:30px;text-align:center;background:#f9f9f9;border:1px solid #e0e0e0;border-radius:8px;">
                <div style="font-size:15px;color:#555;font-weight:bold;margin-bottom:8px;">${escapeHtml(msgVazio)}</div>
                <div style="font-size:12px;color:#777;margin-bottom:15px;">${escapeHtml(subMsg)}</div>
                <div style="display:flex;gap:10px;justify-content:center;">
                    <button type="button" class="botao botao-primario" onclick="showSection('${tipoDoc === "1" ? "emissor-rapido" : "gestao-sync"}');" style="background:#27ae60;border-color:#27ae60;">${tipoDoc === "1" ? "📤 Nova Emissão" : "⚡ Ir para Robô DF-e"}</button>
                    <button type="button" class="botao" onclick="document.getElementById('gestao-input-xml-lote').click();">📁 Importar XMLs</button>
                </div>
            </div>
        `;
        return;
    }

    const fmtMoney = (v) => {
        const n = parseFloat(v) || 0.0;
        return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const fmtDate = (v) => fmtDataHoraBR(v);

    const EMPRESAS_CNPJS = ["34511185000110", "13787408000105", "44739622000101", "58186781000130", "58495100000116"];

    const rows = docs.map(d => {
        const sit = d.situacao || "Autorizada";
        const cnpjEmitDigits = (d.emitente_cnpj || "").replace(/\D/g, "");
        let isEntrada = true;
        if (d.tipo_doc !== undefined && d.tipo_doc !== null) {
            isEntrada = (parseInt(d.tipo_doc) === 0);
        } else {
            isEntrada = !EMPRESAS_CNPJS.includes(cnpjEmitDigits);
        }

        const tipoBadge = isEntrada 
            ? `<span class="badge" style="background:var(--pastel-green-bg);color:var(--pastel-green-text);border:1px solid var(--pastel-green-border);font-size:9.5px;padding:2.5px 7px;border-radius:4px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">📥 Entrada</span>`
            : `<span class="badge" style="background:var(--pastel-blue-bg);color:var(--pastel-blue-text);border:1px solid var(--pastel-blue-border);font-size:9.5px;padding:2.5px 7px;border-radius:4px;font-weight:600;display:inline-flex;align-items:center;gap:3px;">📤 Saída</span>`;

        return `
            <tr style="cursor:pointer;" onclick="if (!event.target.closest('button, input, a')) abrirDrawerDetalhes('${d.chave}');" title="Clique para abrir detalhes rápidos na gaveta lateral">
                <td style="text-align:center;"><input type="checkbox" class="gestao-row-chk" value="${d.chave}" onchange="atualizarSelecaoLote();"></td>
                <td style="text-align:center;">${tipoBadge}</td>
                <td style="font-family:monospace;font-size:10px;line-height:1.35;vertical-align:middle;white-space:nowrap;">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                        <span style="font-weight:bold;letter-spacing:0.3px;">${formatarChaveVertical(d.chave)}</span>
                        <button type="button" class="btn-copy-chave" onclick="copiarChaveAcesso('${d.chave}', this);" title="Copiar chave de 44 dígitos (sem espaços)" style="background:transparent;border:none;cursor:pointer;padding:2px 4px;font-size:11px;border-radius:4px;transition:all 0.15s ease;line-height:1;">📋</button>
                    </div>
                </td>
                <td><b>${escapeHtml(d.numero || "—")}</b><br><small style="color:#666;">Série ${escapeHtml(d.serie || "1")}</small></td>
                <td><b>${escapeHtml(d.emitente_nome || "—")}</b><br><span style="color:#666;font-size:10px;">${escapeHtml(d.emitente_cnpj || "")}</span></td>
                <td><b>${escapeHtml(d.destinatario_nome || "—")}</b><br><span style="color:#666;font-size:10px;">${escapeHtml(d.destinatario_cnpj || "")}</span></td>
                <td>${escapeHtml(fmtDate(d.data_emissao))}</td>
                <td style="text-align:right;font-weight:bold;color:#2c3e50;">R$ ${escapeHtml(fmtMoney(d.valor_total))}</td>
                <td>${getSituacaoBadgeHtml(sit)}</td>
                <td>
                    <div class="actions-cell">
                        <button type="button" class="btn-action" onclick="abrirDrawerDetalhes('${d.chave}');" title="Ver Detalhes Rápidos">⚡ Rápido</button>
                        <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${d.chave}');" title="Ver DANFE Completo">👁️ DANFE</button>
                        <button type="button" class="btn-action" onclick="downloadDanfePdf('${d.chave}');" title="Baixar PDF">📥 PDF</button>
                        <button type="button" class="btn-action" onclick="executarCheckinEstoqueRapido('${d.chave}');" style="background:#27ae60;color:#fff;border-color:#27ae60;font-weight:bold;" title="Cadastrar produtos e somar no estoque">📥 Check-in</button>
                        <button type="button" class="btn-action" onclick="imprimirEtiquetasChave('${d.chave}');" title="Gerar Etiquetas de Preço e Código de Barras">🏷️ Etiquetas</button>
                        <button type="button" class="btn-action" onclick="abrirConferenciaEstoque('${d.chave}');" title="Conferir Estoque">📦 Conferir</button>
                        <button type="button" class="btn-action" onclick="abrirManifestacaoChave('${d.chave}', '${d.destinatario_cnpj || ''}');" title="Manifestar Nota">✍️ Manifestar</button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    const paginacaoHtml = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding:8px;background:#f8f9fa;border:1px solid #e9ecef;font-size:12px;">
            <div>Página <b>${page}</b> de <b>${totalPages}</b> (Total: ${total} notas)</div>
            <div style="display:flex;gap:5px;">
                <button type="button" class="botao" ${page <= 1 ? "disabled" : ""} onclick="loadGestaoDocs(${page - 1});">◀ Anterior</button>
                <button type="button" class="botao" ${page >= totalPages ? "disabled" : ""} onclick="loadGestaoDocs(${page + 1});">Próxima ▶</button>
            </div>
        </div>
    `;

    const situacaoAtual = document.getElementById("gestao-situacao") ? document.getElementById("gestao-situacao").value : "";
    let situacaoHeaderHtml = `Situação <span style="font-size:10px;opacity:0.7;">↕️</span>`;
    if (situacaoAtual === "Pendente") {
        situacaoHeaderHtml = `Situação <span style="background:#fef3c7;color:#92400e;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">🟡 Pendentes</span>`;
    } else if (situacaoAtual === "Cancelada") {
        situacaoHeaderHtml = `Situação <span style="background:#fee2e2;color:#b91c1c;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">🔴 Canceladas</span>`;
    } else if (situacaoAtual.includes("Realizada") || situacaoAtual === "Rejeitada") {
        situacaoHeaderHtml = `Situação <span style="background:#ffedd5;color:#c2410c;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">🟠 Rejeitadas</span>`;
    } else if (situacaoAtual === "Autorizada") {
        situacaoHeaderHtml = `Situação <span style="background:#dcfce7;color:#15803d;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:bold;">🟢 Autorizadas</span>`;
    }

    container.innerHTML = `
        <div class="table-responsive" style="margin-top:10px;">
            <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;">
                <thead>
                    <tr class="linhaTitulo" style="background:#e9ecef;">
                        <th style="width:25px;text-align:center;"><input type="checkbox" id="gestao-chk-all" onchange="toggleSelectAllDocs(this.checked);"></th>
                        <th style="padding:6px;width:75px;text-align:center;cursor:pointer;user-select:none;" onclick="alternarFiltroTipoColuna();" title="Clique para alternar: Entradas ➔ Saídas ➔ Todas">Tipo ↕️</th>
                        <th style="padding:6px;">Chave de Acesso</th>
                        <th style="padding:6px;">NF-e / Série</th>
                        <th style="padding:6px;">Emitente (Fornecedor)</th>
                        <th style="padding:6px;">Destinatário (Titular)</th>
                        <th style="padding:6px;">Data Emissão</th>
                        <th style="padding:6px;text-align:right;">Valor Total</th>
                        <th style="padding:6px;cursor:pointer;user-select:none;" onclick="alternarFiltroSituacaoColuna();" title="Clique para agrupar e alternar por Situação (Pendentes ➔ Canceladas ➔ Rejeitadas ➔ Autorizadas ➔ Todas)">${situacaoHeaderHtml}</th>
                        <th style="padding:6px;">Ações</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        ${paginacaoHtml}
    `;
    atualizarSelecaoLote();
}

function alternarFiltroSituacaoColuna() {
    const select = document.getElementById("gestao-situacao");
    if (!select) return;
    const atual = select.value;
    let proxima = "Pendente";
    if (atual === "Pendente") {
        proxima = "Cancelada";
    } else if (atual === "Cancelada") {
        proxima = "Operação não Realizada";
    } else if (atual === "Operação não Realizada" || atual === "Rejeitada") {
        proxima = "Autorizada";
    } else if (atual === "Autorizada") {
        proxima = "";
    } else {
        proxima = "Pendente";
    }
    select.value = proxima;
    loadGestaoDocs(1);
}

function alternarFiltroTipoColuna() {
    const select = document.getElementById("gestao-tipo-doc");
    if (!select) return;
    const atual = select.value;
    let proxima = "0";
    if (atual === "0") proxima = "1";
    else if (atual === "1") proxima = "";
    else proxima = "0";
    select.value = proxima;
    loadGestaoDocs(1);
}

function handleGestaoFiltro(e) {
    e.preventDefault();
    loadGestaoDocs(1);
}

function handleGestaoLimpar() {
    if (document.getElementById("gestao-tipo-doc")) document.getElementById("gestao-tipo-doc").value = "";
    if (document.getElementById("gestao-busca")) document.getElementById("gestao-busca").value = "";
    if (document.getElementById("gestao-empresa")) document.getElementById("gestao-empresa").value = "";
    if (document.getElementById("gestao-data-inicio")) document.getElementById("gestao-data-inicio").value = "";
    if (document.getElementById("gestao-data-fim")) document.getElementById("gestao-data-fim").value = "";
    if (document.getElementById("gestao-situacao")) document.getElementById("gestao-situacao").value = "";
    loadGestaoDocs(1);
}

function visualizarDanfeChave(chave) {
    if (!chave) return;
    const chaveClean = String(chave).replace(/\D/g, "");
    const input = document.getElementById("danfe-chave-input");
    if (input) input.value = chaveClean;
    showSection("danfe");
    switchTab("tab-chave-danfe");
    handleDanfePorChaveString(chaveClean);
}

function abrirDanfeDireto(chave) {
    visualizarDanfeChave(chave);
}

function abrirManifestacaoChave(chave, cnpj) {
    const inputChave = document.getElementById("manifestacao-chave");
    const inputCnpj = document.getElementById("manifestacao-cnpj");
    if (inputChave) inputChave.value = chave;
    if (inputCnpj && cnpj) inputCnpj.value = cnpj.replace(/\D/g, "");
    showSection("manifestacao");
}

/* ================================================================
   ROBÔ DE SINCRONIZAÇÃO EM BACKGROUND (MULTI-EMPRESA)
================================================================ */

async function loadSyncStatus() {
    try {
        const res = await apiGet("/api/gestao/sync/status");
        if (!res.success) {
            const elBadge = document.getElementById("sync-status-badge");
            if (elBadge) elBadge.innerHTML = `<span style="color:#c0392b;">🔴 Erro ao carregar status</span>`;
            return;
        }
        const st = res.data || {};
        const certs = st.empresas || [];

        const elBadge = document.getElementById("sync-status-badge");
        if (elBadge) {
            if (st.running) {
                elBadge.innerHTML = `<span style="color:#e67e22;">🟡 Sincronizando todas as empresas com a SEFAZ agora...</span>`;
            } else if (st.auto_sync_enabled) {
                elBadge.innerHTML = `<span style="color:#27ae60;">🟢 Ativo (Ciclo a cada ${st.auto_sync_interval_mins} min para ${st.total_empresas_cadastradas} empresas)</span>`;
            } else {
                elBadge.innerHTML = `<span style="color:#7f8c8d;">⚪ Desativado (Apenas manual)</span>`;
            }
        }

        const elLastTime = document.getElementById("sync-last-time");
        if (elLastTime) {
            elLastTime.textContent = st.last_sync_finish ? `Última execução: ${fmtDataHoraSegBR(st.last_sync_finish)}` : "Última execução: Nunca";
        }

        const elNsuInfo = document.getElementById("sync-nsu-info");
        if (elNsuInfo) {
            const firstCert = certs[0] || {};
            elNsuInfo.textContent = `NSU ${firstCert.last_nsu || "0"} de ${firstCert.max_nsu || "0"}`;
        }

        const elTotalEmpresas = document.getElementById("sync-total-empresas");
        if (elTotalEmpresas) {
            elTotalEmpresas.textContent = certs.length > 0 ? `${certs.length} empresas` : "as empresas cadastradas";
        }

        const elDocs = document.getElementById("sync-docs-banco");
        if (elDocs) {
            elDocs.textContent = `${st.total_banco || 0} notas armazenadas`;
        }

        // Renderiza tabela multi-empresa
        const containerTabela = document.getElementById("sync-tabela-empresas");
        if (containerTabela) {
            if (certs.length === 0) {
                containerTabela.innerHTML = `<div style="padding:15px;color:#666;">Nenhuma empresa cadastrada.</div>`;
            } else {
                const blockedCerts = certs.filter(c => c.blocked_by_sefaz);
                const blockedBanner = blockedCerts.length > 0 ? `
                    <div style="margin-bottom:12px;padding:12px;background:#fdecea;border:1px solid #f5c2c0;border-radius:4px;color:#842029;font-size:12px;">
                        <b>🔒 ${blockedCerts.length} empresa(s) bloqueada(s) pela SEFAZ (cStat 656 — Consumo Indevido).</b>
                        <div style="margin-top:6px;">
                            ${blockedCerts.map(c => {
                                const retryTime = c.retry_at ? new Date(c.retry_at).toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' }) : "—";
                                return `<span style="display:inline-block;margin:2px 8px 2px 0;padding:2px 6px;background:#fff;border:1px solid #f5c2c0;border-radius:3px;">
                                    <b>${escapeHtml(c.razao_social)}</b> — retry às ${escapeHtml(retryTime)} (${c.cooldown_minutes} min, tentativa ${c.tentativa_656 || 1})
                                </span>`;
                            }).join("")}
                        </div>
                        <div style="margin-top:6px;font-size:11px;color:#666;">⏱ Backoff exponencial ativo: 1h → 2h → 4h → 8h → 24h. O sync automático respeitará a janela. Tentar antes do cooldown só agrava o bloqueio.</div>
                    </div>
                ` : "";

                containerTabela.innerHTML = blockedBanner + `
                    <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                        <tr class="linhaTitulo">
                            <th style="text-align:left;padding:6px;">Empresa / Razão Social</th>
                            <th>CNPJ</th>
                            <th>Fila NSU (SEFAZ)</th>
                            <th>Última Sincronização</th>
                            <th>Status SEFAZ</th>
                            <th>Ação</th>
                        </tr>
                        ${certs.map(c => {
                            const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                            const lastSync = c.last_sync_time ? new Date(c.last_sync_time).toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' }) : "Nunca";
                            const blocked = !!c.blocked_by_sefaz;
                            const blockedBadge = blocked
                                ? ` <span style="background:#e74c3c;color:#fff;padding:2px 6px;border-radius:3px;font-size:9px;margin-left:4px;">🔒 BLOQUEADA</span>`
                                : "";
                            const statusColor = blocked ? "#c0392b" : "#2c3e50";
                            const statusWeight = blocked ? "bold" : "normal";
                            const retryInfo = blocked
                                ? `<div style="font-size:10px;color:#c0392b;margin-top:2px;">retry em ${c.cooldown_minutes} min</div>`
                                : "";
                            const btnHtml = blocked
                                ? `<button type="button" class="botao" disabled style="font-size:10px;padding:2px 8px;background:#95a5a6;border-color:#95a5a6;cursor:not-allowed;color:#fff;" title="SEFAZ bloqueou — aguarde ${c.cooldown_minutes} min (tentar antes só agrava o bloqueio)">🔒 Bloqueado</button>`
                                : `<button type="button" class="botao botao-primario" onclick="sincronizarEmpresaEspecifica('${c.cnpj}');" style="font-size:10px;padding:2px 8px;background:#27ae60;border-color:#27ae60;">⚡ Sincronizar</button>`;
                            return `
                                <tr${blocked ? ' style="background:#fff5f5;"' : ''}>
                                    <td style="text-align:left;padding:6px;"><b>${escapeHtml(c.razao_social)}</b>${blockedBadge}</td>
                                    <td style="font-family:monospace;">${escapeHtml(cnpjFmt)}</td>
                                    <td><b>NSU ${escapeHtml(c.last_nsu || "0")}</b> de ${escapeHtml(c.max_nsu || "0")}</td>
                                    <td>${escapeHtml(lastSync)}</td>
                                    <td>
                                        <span style="color:${statusColor};font-size:10px;font-weight:${statusWeight};">${escapeHtml(c.last_sync_status || "Aguardando")}</span>
                                        ${retryInfo}
                                    </td>
                                    <td>${btnHtml}</td>
                                </tr>
                            `;
                        }).join("")}
                    </table>
                `;
            }
        }

        const chkEnabled = document.getElementById("sync-cfg-enabled");
        if (chkEnabled) chkEnabled.checked = st.auto_sync_enabled;
        const inpInterval = document.getElementById("sync-cfg-interval");
        if (inpInterval) inpInterval.value = st.auto_sync_interval_mins;

        // Auto-refresh 60s quando há empresas bloqueadas (atualiza contagem regressiva do cooldown)
        if (typeof window !== "undefined") {
            if (window._sefazBlockRefreshTimer) {
                clearTimeout(window._sefazBlockRefreshTimer);
                window._sefazBlockRefreshTimer = null;
            }
            const temBloqueio = (st.empresas || []).some(c => c.blocked_by_sefaz);
            if (temBloqueio) {
                window._sefazBlockRefreshTimer = setTimeout(() => {
                    if (typeof loadSyncStatus === "function") loadSyncStatus();
                }, 60000);
            }
        }
    } catch (err) {
        const elBadge = document.getElementById("sync-status-badge");
        if (elBadge) elBadge.innerHTML = `<span style="color:#c0392b;">🔴 Erro ao carregar status</span>`;
        console.error("loadSyncStatus error:", err);
    }
}

async function abrirDebugNfe() {
    const modal = document.getElementById("modal-debug-nfe");
    const conteudo = document.getElementById("debug-conteudo");
    if (!modal || !conteudo) return;
    modal.style.display = "flex";
    conteudo.innerHTML = `<div style="text-align:center;padding:30px;color:#666;">Carregando dados de debug...</div>`;

    try {
        const res = await apiGet("/api/gestao/debug/nfe-completo");
        if (!res || !res.success) {
            conteudo.innerHTML = `<div class="result error">Erro ao carregar debug: ${escapeHtml((res && res.data && res.data.detail) || "Falha na requisição")}</div>`;
            return;
        }

        const docs = res.data.documentos || [];
        const certs = res.data.certificados || [];
        const sync = res.data.sync || {};
        const total = res.data.total || 0;

        let html = `
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px;">
                <div class="card-kpi" style="border-left:4px solid #2980b9;"><b>Total no banco:</b> ${total}</div>
                <div class="card-kpi" style="border-left:4px solid #27ae60;"><b>Sync automático:</b> ${sync.auto_sync_enabled ? "Ativado" : "Desativado"} (${sync.auto_sync_interval_mins || 5} min)</div>
                <div class="card-kpi" style="border-left:4px solid #f39c12;"><b>Último sync:</b> ${sync.last_sync_finish || "Nunca"}</div>
            </div>
            <h3 style="margin-top:20px;">📋 Todas as NF-e (Entrada + Saída)</h3>
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead>
                    <tr style="background:#f8f9fa;">
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Chave</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Tipo</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Número/Série</th>
                        <th style="padding:8px;border:1px solid #dee2e6;">Emitente</th>
                        <th style="padding:8px;border:1px solid #dee2e6;">Destinatário</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Data Emissão</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:right;">Valor</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Status</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">NSU</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Check SEFAZ</th>
                    </tr>
                </thead>
                <tbody>
        `;

        docs.forEach((d, i) => {
            const tipo = d.tipo_doc === 1 ? "Saída" : "Entrada";
            const tipoCor = d.tipo_doc === 1 ? "#d4edda" : "#d1ecf1";
            const dataEmi = fmtDataBR(d.data_emissao);
            const vTot = parseFloat(d.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const check = d.last_sefaz_check ? fmtDataHoraBR(d.last_sefaz_check) : "Nunca";
            html += `
                <tr style="background:${i % 2 === 0 ? '#fff' : '#f8f9fa'};">
                    <td style="padding:6px;border:1px solid #dee2e6;font-family:monospace;font-size:11px;">${d.chave || "—"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;background:${tipoCor};font-weight:bold;">${tipo}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;">${d.numero || "—"} / ${d.serie || "1"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;">${escapeHtml(d.emitente_nome || "—")}<br><small style="color:#666;">${d.emitente_cnpj || ""}</small></td>
                    <td style="padding:6px;border:1px solid #dee2e6;">${escapeHtml(d.destinatario_nome || "—")}<br><small style="color:#666;">${d.destinatario_cnpj || ""}</small></td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;">${dataEmi}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:right;font-weight:bold;">R$ ${vTot}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;">${getSituacaoBadgeHtml(d.situacao || "Autorizada")}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;font-family:monospace;">${d.nsu || "0"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;font-size:11px;">${check}</td>
                </tr>
            `;
        });

        html += `</tbody></table></div>`;

        html += `<h3 style="margin-top:25px;">🔐 Certificados Cadastrados</h3>
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead>
                    <tr style="background:#f8f9fa;">
                        <th style="padding:8px;border:1px solid #dee2e6;">CNPJ</th>
                        <th style="padding:8px;border:1px solid #dee2e6;">Razão Social</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Ativo</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Último NSU</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Max NSU</th>
                        <th style="padding:8px;border:1px solid #dee2e6;">Último Sync</th>
                        <th style="padding:8px;border:1px solid #dee2e6;">Status Sync</th>
                        <th style="padding:8px;border:1px solid #dee2e6;text-align:center;">Validade</th>
                    </tr>
                </thead>
                <tbody>`;

        certs.forEach((c, i) => {
            const val = c.status_validade || (c.days_remaining > 0 ? "ATIVO" : "VENCIDO");
            const valCor = val === "VENCIDO" ? "#f8d7da" : (val === "EXPIRANDO" ? "#fff3cd" : "#d4edda");
            html += `
                <tr style="background:${i % 2 === 0 ? '#fff' : '#f8f9fa'};">
                    <td style="padding:6px;border:1px solid #dee2e6;font-family:monospace;">${c.cnpj || "—"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;">${escapeHtml(c.razao_social || "—")}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;">${c.is_active ? "✅ Sim" : "❌ Não"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;font-family:monospace;">${c.last_nsu || "0"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;font-family:monospace;">${c.max_nsu || "0"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;font-size:11px;">${c.last_sync_time ? c.last_sync_time.substring(0, 19).replace("T", " ") : "—"}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;font-size:11px;max-width:250px;">${escapeHtml(c.last_sync_status || "—")}</td>
                    <td style="padding:6px;border:1px solid #dee2e6;text-align:center;background:${valCor};">${val} (${c.days_remaining || 0}d)</td>
                </tr>
            `;
        });

        html += `</tbody></table></div>
            <div style="margin-top:15px;text-align:right;">
                <button onclick="document.getElementById('modal-debug-nfe').style.display='none'" class="botao">Fechar</button>
            </div>
        `;

        conteudo.innerHTML = html;
    } catch (err) {
        conteudo.innerHTML = `<div class="result error">Erro: ${escapeHtml(err.message)}</div>`;
        console.error("abrirDebugNfe error:", err);
    }
}

async function handleSyncExecutarAgora() {
    const btn = document.getElementById("btn-sync-executar-agora");
    const resultBox = document.getElementById("sync-execucao-resultado");
    const totalEmpresas = document.getElementById("sync-total-empresas")?.textContent || "as empresas cadastradas";
    if (btn) { btn.disabled = true; btn.textContent = `⏳ Sincronizando ${totalEmpresas}...`; }
    if (resultBox) { resultBox.style.display = "block"; resultBox.className = "result info"; resultBox.innerHTML = "<p>Consultando a fila DF-e da SEFAZ Nacional, aguarde...</p>"; }

    try {
        const res = await apiPost("/api/gestao/sync/run", { homologacao: AppState.ambiente === "homologacao" });
        if (res.success && res.data?.success) {
            const d = res.data;
            if (resultBox) {
                resultBox.className = "result success";
                resultBox.innerHTML = `
                    <div style="font-weight:bold;color:#27ae60;font-size:13px;margin-bottom:4px;">✓ Sincronização de todas as empresas concluída!</div>
                    <div style="font-size:12px;"><b>Total de notas salvas:</b> ${d.total_docs_saved} | <b>Eventos registrados:</b> ${d.total_events_saved}</div>
                    <div style="font-size:11px;color:#666;margin-top:4px;">Executado em: ${d.last_sync_time}</div>
                `;
            }
            loadSyncStatus();
            loadCertificatesUI();
            if (typeof syncAllToFirestore === "function") {
                syncAllToFirestore();
            }
        } else {
            const err = (res.data && (res.data.error || res.data.detail)) || "Falha na sincronização";
            if (resultBox) {
                resultBox.className = "result error";
                resultBox.innerHTML = `<p><b>Erro:</b> ${escapeHtml(err)}</p>`;
            }
        }
    } catch (e) {
        if (resultBox) {
            resultBox.className = "result error";
            resultBox.innerHTML = `<p><b>Erro inesperado:</b> ${escapeHtml(e.message)}</p>`;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "⚡ Sincronizar Agora com a SEFAZ"; }
    }
}

async function handleSyncConfig(e) {
    e.preventDefault();
    const enabled = document.getElementById("sync-cfg-enabled")?.checked || false;
    const interval = parseInt(document.getElementById("sync-cfg-interval")?.value, 10) || 60;
    const feedback = document.getElementById("sync-config-feedback");

    const res = await apiPost("/api/gestao/sync/config", {
        auto_sync_enabled: enabled,
        auto_sync_interval_mins: interval,
    });

    if (res.success) {
        if (feedback) { feedback.textContent = "✓ Salvo"; feedback.style.color = "#27ae60"; }
        setTimeout(() => { if (feedback) { feedback.textContent = ""; } }, 3000);
        loadSyncStatus();
    } else {
        if (feedback) { feedback.textContent = "✗ Erro"; feedback.style.color = "#c0392b"; }
    }
}

/* ================================================================
   INTELIGÊNCIA DE COMPRAS & COMPARADOR DE PREÇOS
================================================================ */

async function loadAnalyticsDashboard(mesParam, anoParam) {
    const mes = mesParam || parseInt(document.getElementById("analytics-mes")?.value, 10) || (new Date().getMonth() + 1);
    const ano = anoParam || parseInt(document.getElementById("analytics-ano")?.value, 10) || new Date().getFullYear();
    const empresa = document.getElementById("analytics-empresa")?.value || "";

    if (document.getElementById("analytics-mes")) document.getElementById("analytics-mes").value = mes;
    if (document.getElementById("analytics-ano")) document.getElementById("analytics-ano").value = ano;

    // Popula select de empresas no BI se estiver vazio com as 5 empresas oficiais
    const selEmp = document.getElementById("analytics-empresa");
    if (selEmp && selEmp.options.length <= 1) {
        try {
            const resEmp = await apiGet("/api/gestao/financeiro/empresas");
            const emps = (resEmp.success && resEmp.data) ? (resEmp.data.empresas || resEmp.data) : [];
            selEmp.innerHTML = '<option value="">🏢 Todas as 5 Empresas (Consolidado)</option>';
            emps.forEach(e => {
                const cnpjLimpo = (e.cnpj || e.empresa_cnpj || "").replace(/\D/g, "");
                const cnpjFmt = cnpjLimpo.length === 14 
                    ? `${cnpjLimpo.slice(0,2)}.${cnpjLimpo.slice(2,5)}.${cnpjLimpo.slice(5,8)}/${cnpjLimpo.slice(8,12)}-${cnpjLimpo.slice(12,14)}`
                    : cnpjLimpo;
                const opt = document.createElement("option");
                opt.value = cnpjLimpo;
                opt.textContent = `📍 ${e.nome || e.emitente_nome || ""} — ${cnpjFmt}`;
                selEmp.appendChild(opt);
            });
        } catch (_) {}
    }

    let urlDash = `/api/gestao/analytics/dashboard?mes=${mes}&ano=${ano}`;
    let urlAbc = `/api/gestao/analytics/abc?mes=${mes}&ano=${ano}`;
    if (empresa) {
        urlDash += `&empresa_cnpj=${encodeURIComponent(empresa)}`;
        urlAbc += `&empresa_cnpj=${encodeURIComponent(empresa)}`;
    }

    const [dashRes, abcRes] = await Promise.all([
        apiGet(urlDash),
        apiGet(urlAbc),
    ]);

    const fmtMoney = (v) => (parseFloat(v) || 0.0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    if (dashRes.success && dashRes.data) {
        const d = dashRes.data;
        const kpi = d.kpis_executivos || {};
        const totEnt = d.totais_entrada || {};
        const totSai = d.totais_saida || {};

        // KPIs Executivos
        if (document.getElementById("analytics-kpi-vendas")) {
            document.getElementById("analytics-kpi-vendas").textContent = "R$ " + fmtMoney(kpi.vendas_tot || totSai.total_vendas);
        }
        if (document.getElementById("analytics-kpi-qtd-vendas")) {
            document.getElementById("analytics-kpi-qtd-vendas").textContent = `${kpi.qtd_vendas || 0} nota(s) emitida(s)`;
        }
        if (document.getElementById("analytics-kpi-total")) {
            document.getElementById("analytics-kpi-total").textContent = "R$ " + fmtMoney(kpi.compras_tot || totEnt.total_compras);
        }
        if (document.getElementById("analytics-kpi-qtd")) {
            document.getElementById("analytics-kpi-qtd").textContent = `${kpi.qtd_compras || 0} nota(s) recebida(s)`;
        }
        if (document.getElementById("analytics-kpi-saldo")) {
            const saldo = kpi.saldo_operacional || 0.0;
            const elSaldo = document.getElementById("analytics-kpi-saldo");
            elSaldo.textContent = "R$ " + fmtMoney(saldo);
            elSaldo.style.color = saldo >= 0 ? "#27ae60" : "#c0392b";
        }
        if (document.getElementById("analytics-kpi-margem")) {
            document.getElementById("analytics-kpi-margem").textContent = `Margem Bruta: ${(kpi.margem_bruta_pct || 0).toFixed(1)}%`;
        }
        if (document.getElementById("analytics-kpi-ticket")) {
            document.getElementById("analytics-kpi-ticket").textContent = "R$ " + fmtMoney(kpi.ticket_medio_vendas);
        }
        if (document.getElementById("analytics-kpi-ticket-compras")) {
            document.getElementById("analytics-kpi-ticket-compras").textContent = `Compras: R$ ${fmtMoney(kpi.ticket_medio_compras)}`;
        }

        // Impostos
        if (document.getElementById("analytics-kpi-icms")) {
            document.getElementById("analytics-kpi-icms").textContent = "R$ " + fmtMoney(totEnt.total_icms);
        }
        if (document.getElementById("analytics-kpi-piscofins")) {
            document.getElementById("analytics-kpi-piscofins").textContent = "R$ " + fmtMoney((totEnt.total_pis || 0) + (totEnt.total_cofins || 0));
        }
        if (document.getElementById("analytics-kpi-ipi")) {
            document.getElementById("analytics-kpi-ipi").textContent = "R$ " + fmtMoney(totEnt.total_ipi);
        }

        // Top 5 Clientes (Saídas)
        const topCliEl = document.getElementById("analytics-top-clientes");
        const cliList = d.top_clientes || [];
        if (topCliEl) {
            if (cliList.length === 0) {
                topCliEl.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhuma venda/saída registrada no mês selecionado.</div>`;
            } else {
                const totalVendas = kpi.vendas_tot || 1.0;
                topCliEl.innerHTML = `
                    <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                        <tr class="linhaTitulo" style="background:#e8f4fd;"><th>Cliente</th><th>Qtd</th><th style="text-align:right;">Total (R$)</th><th style="text-align:right;">%</th></tr>
                        ${cliList.map(c => {
                            const pct = ((c.valor_total / totalVendas) * 100).toFixed(1);
                            return `
                                <tr>
                                    <td><b>${escapeHtml(c.destinatario_nome)}</b><br><small style="color:#666;">${escapeHtml(c.destinatario_cnpj)}</small></td>
                                    <td>${c.qtd_notas}</td>
                                    <td style="text-align:right;font-weight:bold;color:#2980b9;">R$ ${fmtMoney(c.valor_total)}</td>
                                    <td style="text-align:right;"><span style="background:#e8f4fd;padding:2px 5px;border-radius:3px;font-weight:bold;color:#2980b9;">${pct}%</span></td>
                                </tr>
                            `;
                        }).join("")}
                    </table>
                `;
            }
        }

        // Top 5 Fornecedores (Entradas)
        const topFornEl = document.getElementById("analytics-top-fornecedores");
        const fornList = d.top_fornecedores || [];
        if (topFornEl) {
            if (fornList.length === 0) {
                topFornEl.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhum fornecedor registrado no mês selecionado.</div>`;
            } else {
                const totalCompras = kpi.compras_tot || 1.0;
                topFornEl.innerHTML = `
                    <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                        <tr class="linhaTitulo" style="background:#fef2f2;"><th>Fornecedor</th><th>Qtd</th><th style="text-align:right;">Total (R$)</th><th style="text-align:right;">%</th></tr>
                        ${fornList.map(f => {
                            const pct = ((f.valor_total / totalCompras) * 100).toFixed(1);
                            return `
                                <tr>
                                    <td><b>${escapeHtml(f.emitente_nome)}</b><br><small style="color:#666;">${escapeHtml(f.emitente_cnpj)}</small></td>
                                    <td>${f.qtd_notas}</td>
                                    <td style="text-align:right;font-weight:bold;color:#e74c3c;">R$ ${fmtMoney(f.valor_total)}</td>
                                    <td style="text-align:right;"><span style="background:#fee2e2;padding:2px 5px;border-radius:3px;font-weight:bold;color:#c0392b;">${pct}%</span></td>
                                </tr>
                            `;
                        }).join("")}
                    </table>
                `;
            }
        }

        // Gráfico de Evolução Mensal (Vendas vs Compras)
        const evol = d.evolucao_mensal || [];
        if (evol.length > 0 && typeof Chart !== "undefined") {
            const chartContainer = document.getElementById("analytics-chart-container");
            if (chartContainer) {
                chartContainer.innerHTML = `<canvas id="chart-analytics-evolucao" style="max-height:280px;"></canvas>`;
                const ctx = document.getElementById("chart-analytics-evolucao");
                if (ctx) {
                    new Chart(ctx, {
                        type: "bar",
                        data: {
                            labels: evol.map(e => e.mes_ano),
                            datasets: [
                                {
                                    label: "Vendas / Saídas (R$)",
                                    data: evol.map(e => e.valor_saidas || 0.0),
                                    backgroundColor: "rgba(41, 128, 185, 0.75)",
                                    borderColor: "#2980b9",
                                    borderWidth: 1,
                                },
                                {
                                    label: "Compras / Entradas (R$)",
                                    data: evol.map(e => e.valor_entradas || 0.0),
                                    backgroundColor: "rgba(231, 76, 60, 0.75)",
                                    borderColor: "#e74c3c",
                                    borderWidth: 1,
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { position: "top" },
                                tooltip: {
                                    callbacks: {
                                        label: (context) => `${context.dataset.label}: R$ ${(context.parsed.y || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    ticks: {
                                        callback: (v) => "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 0 })
                                    }
                                }
                            }
                        }
                    });
                }
            }
        }
    }

    // Curva ABC
    const abcEl = document.getElementById("analytics-curva-abc");
    if (abcEl) {
        const abcList = (abcRes.success && abcRes.data) ? abcRes.data : [];
        if (abcList.length === 0) {
            abcEl.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhum produto registrado no mês selecionado.</div>`;
        } else {
            abcEl.innerHTML = `
                <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                    <tr class="linhaTitulo"><th>Produto</th><th>Classe</th><th style="text-align:right;">Qtd</th><th style="text-align:right;">Total (R$)</th><th style="text-align:right;">% Acum.</th></tr>
                    ${abcList.slice(0, 10).map(item => {
                        const classeCor = item.classe === "A" ? "#27ae60" : item.classe === "B" ? "#f39c12" : "#7f8c8d";
                        return `
                            <tr>
                                <td><b>${escapeHtml(item.descricao)}</b><br><small style="color:#666;">NCM ${escapeHtml(item.ncm || "—")}</small></td>
                                <td><span class="badge-ambiente" style="background:${classeCor};font-size:10px;">Classe ${item.classe}</span></td>
                                <td style="text-align:right;">${item.qtd_total}</td>
                                <td style="text-align:right;font-weight:bold;">R$ ${fmtMoney(item.valor_total)}</td>
                                <td style="text-align:right;color:#666;">${item.acumulado}%</td>
                            </tr>
                        `;
                    }).join("")}
                </table>
            `;
        }
    }
}

function handleAnalyticsPeriodo(e) {
    e.preventDefault();
    loadAnalyticsDashboard();
}

async function handleAnalyticsPrecos(e) {
    e.preventDefault();
    const termo = (document.getElementById("analytics-precos-input")?.value || "").trim();
    if (!termo) return;

    const resBox = document.getElementById("analytics-precos-resultado");
    if (resBox) resBox.innerHTML = "<p>Pesquisando histórico de preços...</p>";

    const res = await apiGet(`/api/gestao/analytics/precos?termo=${encodeURIComponent(termo)}`);
    if (!res.success || !res.data) {
        if (resBox) resBox.innerHTML = `<div class="result error">Erro ao consultar preços.</div>`;
        return;
    }

    const items = res.data;
    if (items.length === 0) {
        if (resBox) resBox.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhum produto correspondente a <b>"${escapeHtml(termo)}"</b> encontrado no histórico de compras.</div>`;
        return;
    }

    const fmtMoney = (v) => (parseFloat(v) || 0.0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const fmtDate = (v) => fmtDataBR(v);

    const rows = items.map(item => `
        <tr>
            <td>${escapeHtml(fmtDate(item.data_emissao))}</td>
            <td><b>${escapeHtml(item.descricao)}</b><br><small style="color:#666;">Cód: ${escapeHtml(item.codigo || "—")} | NCM: ${escapeHtml(item.ncm || "—")}</small></td>
            <td><b>${escapeHtml(item.emitente_nome)}</b><br><small style="color:#666;">${escapeHtml(item.emitente_cnpj)}</small></td>
            <td style="text-align:right;">${item.quantidade} ${escapeHtml(item.unidade || "UN")}</td>
            <td style="text-align:right;font-weight:bold;color:#27ae60;font-size:12px;">R$ ${fmtMoney(item.valor_unitario)}</td>
            <td style="text-align:right;font-weight:bold;">R$ ${fmtMoney(item.valor_total)}</td>
        </tr>
    `).join("");

    if (resBox) {
        resBox.innerHTML = `
            <table class="tabelaGrupo" style="width:100%;font-size:11px;margin-top:10px;">
                <tr class="linhaTitulo">
                    <th>Data</th><th>Produto / NCM</th><th>Fornecedor</th><th style="text-align:right;">Qtd</th><th style="text-align:right;">Preço Unitário</th><th style="text-align:right;">Total Item</th>
                </tr>
                ${rows}
            </table>
        `;
    }
}

/* ================================================================
   FECHAMENTO CONTÁBIL & EXPORTADOR ZIP
================================================================ */

async function loadContabilPrevia() {
    const mes = parseInt(document.getElementById("contabil-mes")?.value, 10) || (new Date().getMonth() + 1);
    const ano = parseInt(document.getElementById("contabil-ano")?.value, 10) || new Date().getFullYear();
    const mesStr = `${ano}-${String(mes).padStart(2, '0')}`;
    const empCnpj = document.getElementById("contabil-empresa")?.value || "";

    const container = document.getElementById("contabil-previa-lista");
    if (container) container.innerHTML = `<div style="padding:10px;text-align:center;color:#666;">Carregando notas do período ${String(mes).padStart(2, '0')}/${ano}...</div>`;

    // Atualiza KPIs do período via endpoint de resumo por certificado
    try {
        const resumoRes = await apiGet(`/api/emissao/fechamento-contabil/resumo?ano=${ano}&mes=${mes}${empCnpj ? '&empresa_cnpj=' + empCnpj : ''}`);
        const stats = resumoRes.data?.data || resumoRes.data || {};
        const fmtM = (v) => (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        setEl("contabil-kpi-total", stats.total_notas || 0);
        setEl("contabil-kpi-aut",   stats.autorizadas || 0);
        setEl("contabil-kpi-canc",  stats.canceladas || 0);
        setEl("contabil-kpi-fat",   `R$ ${fmtM(stats.faturamento_total)}`);
    } catch (e) { console.warn("Erro KPIs contábeis:", e); }

    let apiUrl = `/api/gestao/documentos?data_inicio=${mesStr}-01&data_fim=${mesStr}-31&limit=200`;
    if (empCnpj) apiUrl += `&empresa_cnpj=${empCnpj}`;

    const res = await apiGet(apiUrl);
    if (!res.success) return;

    const docs = res.data?.documentos || [];
    const fmtMoney = (v) => (parseFloat(v) || 0.0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    if (container) {
        if (docs.length === 0) {
            container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhuma nota fiscal encontrada no período <b>${String(mes).padStart(2, '0')}/${ano}</b>${empCnpj ? ' para o certificado selecionado' : ''}.</div>`;
        } else {
            // Agrupar por certificado para exibição por empresa
            const porEmp = {};
            docs.forEach(d => {
                const cnpj = d.emitente_cnpj || d.empresa_cnpj || "—";
                if (!porEmp[cnpj]) porEmp[cnpj] = { nome: d.emitente_nome || cnpj, notas: [] };
                porEmp[cnpj].notas.push(d);
            });

            const grupos = Object.entries(porEmp).map(([cnpj, emp]) => {
                const fmtCnpj = cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                const totalEmp = emp.notas.reduce((s, d) => s + (parseFloat(d.valor_total) || 0), 0);
                return `
                    <div style="margin-bottom:14px;">
                        <div style="background:#f1f5f9;padding:6px 12px;border-radius:4px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                            <span style="font-weight:bold;font-size:12px;color:#1e293b;">🏢 ${escapeHtml(emp.nome)}</span>
                            <span style="font-size:11px;color:#475569;">CNPJ: ${escapeHtml(fmtCnpj)} | ${emp.notas.length} notas | R$ ${fmtMoney(totalEmp)}</span>
                        </div>
                        <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                            <tr class="linhaTitulo"><th>Nº</th><th>Chave de Acesso</th><th>Destinatário</th><th>Data</th><th style="text-align:right;">Valor</th><th>Itens</th><th>Situação</th></tr>
                            ${emp.notas.map(d => `
                                <tr style="cursor:pointer;" onclick="toggleContabilItens('${d.chave}', this)">
                                    <td><b>${escapeHtml(d.numero || "—")}</b></td>
                                    <td style="font-family:monospace;font-size:9.5px;">${escapeHtml(d.chave)}</td>
                                    <td><b>${escapeHtml(d.destinatario_nome || d.emitente_nome || "—")}</b></td>
                                    <td>${fmtDataBR(d.data_emissao)}</td>
                                    <td style="text-align:right;font-weight:bold;">R$ ${fmtMoney(d.valor_total)}</td>
                                    <td style="text-align:center;"><span class="badge badge-info" id="badge-itens-${d.chave}">—</span></td>
                                    <td>${getSituacaoBadgeHtml(d.situacao || "Autorizada")}</td>
                                </tr>
                                <tr id="row-itens-${d.chave}" style="display:none;">
                                    <td colspan="7" style="padding:0;">
                                        <div id="container-itens-${d.chave}" style="background:#f8fafc;padding:8px 12px;border-top:1px solid #e2e8f0;">
                                            <span style="color:#64748b;font-size:11px;">Clique para carregar itens...</span>
                                        </div>
                                    </td>
                                </tr>
                            `).join("")}
                        </table>
                    </div>
                `;
            }).join("");

            container.innerHTML = `
                <div style="margin-bottom:10px;font-size:12px;color:#2c3e50;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
                    <span><b>${docs.length}</b> nota(s) no período <b>${String(mes).padStart(2, '0')}/${ano}</b> — organizado por Certificado/Empresa:</span>
                    <span style="font-size:11px;color:#64748b;">${Object.keys(porEmp).length} empresa(s) emitente(s)</span>
                </div>
                ${grupos}
            `;
        }
    }
}

async function handleContabilExportar(e) {
    e.preventDefault();
    const mes = parseInt(document.getElementById("contabil-mes")?.value, 10) || (new Date().getMonth() + 1);
    const ano = parseInt(document.getElementById("contabil-ano")?.value, 10) || new Date().getFullYear();
    const empCnpj = document.getElementById("contabil-empresa")?.value || "";

    // Usa o endpoint unificado com organização por certificado
    const url = `/api/emissao/fechamento-contabil/download?mes=${mes}&ano=${ano}${empCnpj ? '&empresa_cnpj=' + empCnpj : ''}`;
    const defaultName = `Fechamento_Fiscal_${ano}_${String(mes).padStart(2, '0')}${empCnpj ? '_' + empCnpj : '_Todas_Filiais'}.zip`;
    const res = await apiDownload(url, defaultName);
    if (res.ok) {
        const blobUrl = window.URL.createObjectURL(res.blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = res.filename || defaultName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
    } else {
        toast.error("Erro ao gerar pacote contábil: " + (res.error || "Falha no download"));
    }
}

const _contabilItensCache = {};
async function toggleContabilItens(chave, rowEl) {
    const detailRow = document.getElementById(`row-itens-${chave}`);
    const container = document.getElementById(`container-itens-${chave}`);
    const badge = document.getElementById(`badge-itens-${chave}`);
    if (!detailRow || !container) return;

    if (detailRow.style.display !== "none") {
        detailRow.style.display = "none";
        return;
    }

    detailRow.style.display = "";

    if (_contabilItensCache[chave]) {
        container.innerHTML = _contabilItensCache[chave];
        return;
    }

    container.innerHTML = `<span style="color:#64748b;font-size:11px;">⏳ Carregando itens...</span>`;

    try {
        const res = await apiGet(`/api/danfe/parse/${chave}`);
        const d = res.data || res;
        const produtos = d.produtos || [];

        if (badge) badge.textContent = `${produtos.length} itens`;

        if (produtos.length === 0) {
            container.innerHTML = `<span style="color:#94a3b8;font-size:11px;">Sem itens disponíveis (resumo SEFAZ ou XML não encontrado).</span>`;
            return;
        }

        const fmtM = (v) => (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        let html = `<table style="width:100%;font-size:10.5px;border-collapse:collapse;">
            <thead><tr style="border-bottom:1px solid #cbd5e1;">
                <th style="text-align:left;padding:3px 6px;">#</th>
                <th style="text-align:left;padding:3px 6px;">Produto</th>
                <th style="text-align:left;padding:3px 6px;">NCM</th>
                <th style="text-align:left;padding:3px 6px;">CFOP</th>
                <th style="text-align:right;padding:3px 6px;">Qtd</th>
                <th style="text-align:right;padding:3px 6px;">V.Unit</th>
                <th style="text-align:right;padding:3px 6px;">Total</th>
            </tr></thead><tbody>`;

        produtos.forEach(p => {
            html += `<tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:3px 6px;">${p.n_item || ''}</td>
                <td style="padding:3px 6px;font-weight:600;">${escapeHtml(p.descricao || '')}</td>
                <td style="padding:3px 6px;color:#64748b;">${escapeHtml(p.ncm || '')}</td>
                <td style="padding:3px 6px;color:#64748b;">${escapeHtml(p.cfop || '')}</td>
                <td style="padding:3px 6px;text-align:right;">${p.quantidade || 0}</td>
                <td style="padding:3px 6px;text-align:right;">R$ ${fmtM(p.valor_unitario)}</td>
                <td style="padding:3px 6px;text-align:right;font-weight:600;">R$ ${fmtM(p.valor_total)}</td>
            </tr>`;
        });

        html += `</tbody></table>`;
        _contabilItensCache[chave] = html;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<span style="color:#c0392b;font-size:11px;">Erro ao carregar itens: ${escapeHtml(err.message)}</span>`;
    }
}

async function handleImportXmlLote(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const feedback = document.getElementById("gestao-import-feedback");
    if (feedback) {
        feedback.style.display = "block";
        feedback.className = "result info";
        feedback.innerHTML = `<p>Importando <b>${files.length}</b> arquivo(s) XML, aguarde...</p>`;
    }

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }

    try {
        // Usa apiUploadForm para garantir que o header X-Session-Token
        // seja enviado (o backend exige sessão em /api/gestao/*).
        const res = await apiUploadForm("/api/gestao/importar-xmls", formData);

        if (res.success && res.data && res.data.success) {
            const data = res.data;
            if (feedback) {
                feedback.className = "result success";
                feedback.innerHTML = `
                    <div style="font-weight:bold;color:#27ae60;">✓ Importação concluída!</div>
                    <div style="font-size:12px;"><b>${data.importados}</b> de <b>${data.total_arquivos}</b> arquivo(s) XML importados e salvos com sucesso no banco.</div>
                    ${data.erros && data.erros.length > 0 ? `<div style="font-size:11px;color:#c0392b;margin-top:4px;">Avisos: ${data.erros.join("<br>")}</div>` : ""}
                `;
            }
            loadGestaoDocs(1);
        } else {
            const detail = (res.data && (res.data.detail || res.data.error)) || "Falha desconhecida";
            if (feedback) {
                feedback.className = "result error";
                feedback.innerHTML = `<p>Erro ao importar XMLs: ${escapeHtml(detail)}</p>`;
            }
        }
    } catch (err) {
        if (feedback) {
            feedback.className = "result error";
            feedback.innerHTML = `<p>Erro de rede/upload: ${escapeHtml(err.message)}</p>`;
        }
    } finally {
        e.target.value = "";
    }
}


// ====================================================================
// 1. NOTIFICAÇÕES EM TEMPO REAL & ALERTAS DO SISTEMA
// ====================================================================

let notifIntervalId = null;

async function carregarNotificacoes() {
    try {
        const res = await apiGet("/api/gestao/notificacoes?limit=25");
        if (!res.success) return;

        const notifs = res.data || [];
        const unreadCount = notifs.filter(n => !n.read).length;

        const badge = document.getElementById("notif-unread-badge");
        if (badge) {
            if (unreadCount > 0) {
                badge.textContent = unreadCount;
                badge.style.display = "inline-block";
            } else {
                badge.style.display = "none";
            }
        }

        const feedLista = document.getElementById("notif-feed-lista");
        if (feedLista) {
            if (notifs.length === 0) {
                renderEmptyState({
                    icon: '🔔',
                    title: 'Nenhuma notificação',
                    description: 'Você está em dia! Não há notificações pendentes.',
                    containerId: 'notif-feed-lista',
                });
            } else {
                feedLista.innerHTML = notifs.map(n => {
                    let cor = "#2980b9";
                    let icone = "ℹ️";
                    if (n.tipo === "nfe_nova") { cor = "#27ae60"; icone = "📦"; }
                    else if (n.tipo === "cancelamento") { cor = "#c0392b"; icone = "⚠️"; }

                    const dt = n.created_at ? new Date(n.created_at).toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' }) : "";

                    return `
                        <div style="background:${n.read ? '#fff' : '#f0f8ff'};border:1px solid ${n.read ? '#eee' : '#b9dcf7'};border-left:3px solid ${cor};padding:8px 10px;margin-bottom:6px;border-radius:4px;font-size:11px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b style="color:${cor};">${icone} ${escapeHtml(n.title || "Notificação")}</b>
                                <small style="color:#888;">${escapeHtml(dt)}</small>
                            </div>
                            <div style="color:#444;margin-top:3px;">${escapeHtml(n.message || "")}</div>
                            ${n.chave ? `<div style="margin-top:4px;"><button type="button" class="botao" onclick="fecharNotificacoesEVerDanfe('${n.chave}');" style="font-size:10px;padding:1px 6px;">👁️ Ver DANFE</button></div>` : ""}
                        </div>
                    `;
                }).join("");
            }
        }
    } catch (err) {
        console.warn("Erro ao buscar notificações:", err);
    }
}

function toggleNotificationsModal() {
    const modal = document.getElementById("modal-notificacoes");
    if (!modal) return;
    const isVisible = modal.style.display === "block";
    modal.style.display = isVisible ? "none" : "block";
    if (!isVisible) carregarNotificacoes();
}

function fecharNotificacoesEVerDanfe(chave) {
    // Fecha o modal de notificações (z-index alto) antes de navegar,
    // senão ele cobre a seção "danfe" e o usuário não vê a troca.
    const modal = document.getElementById("modal-notificacoes");
    if (modal) modal.style.display = "none";
    if (typeof visualizarDanfeChave === "function") {
        visualizarDanfeChave(chave);
    }
}

async function marcarTodasNotificacoesLidas() {
    await apiPost("/api/gestao/notificacoes/ler", {});
    carregarNotificacoes();
}

function solicitarPermissaoNavegador() {
    if (!("Notification" in window)) {
        toast.warning("Este navegador não suporta notificações de área de trabalho.");
        return;
    }
    Notification.requestPermission().then(permission => {
        if (permission === "granted") {
            new Notification("NFE Manager Ativo", {
                body: "Você receberá alertas automáticos de novas notas fiscais!",
                icon: "/static/favicon.ico",
            });
            toast.success("Notificações no navegador ativadas com sucesso!");
        } else {
            toast.warning("Permissão de notificações negada no navegador.");
        }
    });
}


// ====================================================================
// 2. AUDITOR DE PREÇOS & ALERTAS DE AUMENTO DE CUSTO
// ====================================================================

async function carregarDivergenciasPreco() {
    const container = document.getElementById("analytics-divergencias-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Auditando histórico de compras...</div>`;

    try {
        const emp = document.getElementById("gestao-empresa")?.value || "";
        const res = await apiGet(`/api/gestao/analytics/divergencias?limit=30&empresa_cnpj=${encodeURIComponent(emp)}`);
        if (!res.success) {
            container.innerHTML = `<div class="result error">Falha ao auditar compras: ${escapeHtml(res.data?.detail || "")}</div>`;
            return;
        }

        const items = res.data || [];
        if (items.length === 0) {
            container.innerHTML = `
                <div style="padding:15px;background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;text-align:center;font-size:12px;color:#666;">
                    ✓ Nenhuma divergência ou aumento expressivo de preço detectado nas últimas compras.
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;">
                    <thead>
                        <tr class="linhaTitulo" style="background:#e9ecef;">
                            <th style="padding:6px;">Tipo Alerta</th>
                            <th style="padding:6px;">Produto / Descrição</th>
                            <th style="padding:6px;">NCM / Código</th>
                            <th style="padding:6px;text-align:right;">Preço Atual</th>
                            <th style="padding:6px;text-align:right;">Preço Anterior</th>
                            <th style="padding:6px;text-align:right;">Variação</th>
                            <th style="padding:6px;">Fornecedor Atual</th>
                            <th style="padding:6px;">Ação</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${items.map(it => {
                            const isAumento = it.tipo === "AUMENTO";
                            const corBadge = isAumento ? "#c0392b" : "#27ae60";
                            const sinal = isAumento ? "+" : "";

                            return `
                                <tr>
                                    <td><span class="badge-ambiente" style="background:${corBadge};font-size:10px;">${isAumento ? "⚠️ AUMENTO" : "📉 QUEDA"}</span></td>
                                    <td><b>${escapeHtml(it.descricao || "")}</b></td>
                                    <td style="font-family:monospace;">${escapeHtml(it.ncm || it.codigo || "—")}</td>
                                    <td style="text-align:right;font-weight:bold;color:#2c3e50;">R$ ${it.preco_atual.toFixed(2)}</td>
                                    <td style="text-align:right;color:#666;">R$ ${it.preco_anterior.toFixed(2)}</td>
                                    <td style="text-align:right;font-weight:bold;color:${corBadge};">${sinal}${it.variacao_pct}%</td>
                                    <td>${escapeHtml(it.fornecedor_atual || "")}</td>
                                    <td>
                                        <button type="button" class="botao" onclick="visualizarDanfeChave('${it.chave_atual}');" style="padding:2px 6px;font-size:10px;">👁️ Ver NF-e</button>
                                    </td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="result error">Erro: ${escapeHtml(err.message)}</div>`;
    }
}


// ====================================================================
// 3. OPERAÇÕES INTERCOMPANY (ENTRE NOSSAS EMPRESAS)
// ====================================================================

async function carregarIntercompany() {
    const container = document.getElementById("intercompany-painel-resultado");
    if (!container) return;

    container.innerHTML = `<div style="padding:20px;text-align:center;color:#666;">Carregando operações intercompany...</div>`;

    try {
        const res = await apiGet("/api/gestao/intercompany");
        if (!res.success) {
            container.innerHTML = `<div class="result error">Falha ao carregar conciliação: ${escapeHtml(res.data?.detail || "")}</div>`;
            return;
        }

        const data = res.data || {};
        const ops = data.operacoes || [];
        const matriz = data.resumo_transferencias || [];
        const totVol = data.total_volume || 0.0;
        const totNotas = data.total_notas || 0;

        if (ops.length === 0) {
            container.innerHTML = `
                <div style="padding:25px;background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;text-align:center;font-size:13px;color:#666;">
                    Nenhuma operação fiscal entre as 5 empresas do grupo registrada até o momento.
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="display:flex;gap:15px;margin-bottom:15px;flex-wrap:wrap;">
                <div class="card-kpi" style="flex:1;min-width:180px;background:#f8f9fa;border:1px solid #e9ecef;border-left:4px solid #2980b9;padding:12px 15px;border-radius:4px;">
                    <div style="font-size:11px;color:#666;">TOTAL DE OPERAÇÕES INTERNAS</div>
                    <div style="font-size:22px;font-weight:bold;color:#2980b9;margin-top:2px;">${totNotas} notas</div>
                </div>
                <div class="card-kpi" style="flex:1;min-width:180px;background:#f8f9fa;border:1px solid #e9ecef;border-left:4px solid #27ae60;padding:12px 15px;border-radius:4px;">
                    <div style="font-size:11px;color:#666;">VOLUME TOTAL TRANSFERIDO</div>
                    <div style="font-size:22px;font-weight:bold;color:#27ae60;margin-top:2px;">R$ ${totVol.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
            </div>

            <div class="painelSessao">
                <div class="painelSessaoTitulo">Resumo de Fluxo entre Empresas do Grupo</div>
                <div class="table-responsive" style="margin: 10px;">
                    <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;">
                        <thead>
                            <tr class="linhaTitulo" style="background:#e9ecef;">
                                <th style="padding:6px;">Empresa Emitente (Origem)</th>
                                <th style="padding:6px;">Empresa Destinatária (Destino)</th>
                                <th style="padding:6px;text-align:center;">Qtd Notas</th>
                                <th style="padding:6px;text-align:right;">Valor Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${matriz.map(m => `
                                <tr>
                                    <td><b>${escapeHtml(m.origem || "")}</b></td>
                                    <td><b>${escapeHtml(m.destino || "")}</b></td>
                                    <td style="text-align:center;"><b>${m.qtd}</b></td>
                                    <td style="text-align:right;font-weight:bold;color:#2c3e50;">R$ ${m.total.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="painelSessao" style="margin-top:15px;">
                <div class="painelSessaoTitulo">Relação Completa de Notas Fiscais Intercompany</div>
                <div class="table-responsive" style="margin: 10px;">
                    <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;">
                        <thead>
                            <tr class="linhaTitulo" style="background:#e9ecef;">
                                <th style="padding:6px;">Chave de Acesso</th>
                                <th style="padding:6px;">NF-e</th>
                                <th style="padding:6px;">Origem</th>
                                <th style="padding:6px;">Destino</th>
                                <th style="padding:6px;">Data</th>
                                <th style="padding:6px;text-align:right;">Valor</th>
                                <th style="padding:6px;">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${ops.map(o => `
                                <tr>
                                    <td style="font-family:monospace;font-size:10px;">${escapeHtml(o.chave)}</td>
                                    <td><b>${escapeHtml(o.numero || "—")}</b></td>
                                    <td>${escapeHtml(o.emitente_nome || "")}</td>
                                    <td>${escapeHtml(o.destinatario_nome || "")}</td>
                                    <td>${escapeHtml(o.data_emissao ? o.data_emissao.slice(0, 10) : "—")}</td>
                                    <td style="text-align:right;font-weight:bold;">R$ ${parseFloat(o.valor_total || 0).toFixed(2)}</td>
                                    <td>
                                        <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${o.chave}');">👁️ DANFE</button>
                                    </td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="result error">Erro: ${escapeHtml(err.message)}</div>`;
    }
}


// ====================================================================
// 4. MANIFESTAÇÃO EM LOTE DE NOTAS FISCAIS
// ====================================================================

function toggleSelectAllDocs(checked) {
    const chks = document.querySelectorAll(".gestao-row-chk");
    chks.forEach(c => c.checked = checked);
    atualizarSelecaoLote();
}

function atualizarSelecaoLote() {
    const chks = document.querySelectorAll(".gestao-row-chk:checked");
    const barra = document.getElementById("gestao-lote-barra");
    const countEl = document.getElementById("gestao-lote-selecionadas-count");
    if (!barra) return;

    if (chks.length > 0) {
        barra.style.display = "flex";
        if (countEl) countEl.textContent = chks.length;
    } else {
        barra.style.display = "none";
    }
}

async function executarManifestacaoEmLote(tipoEvento) {
    const chks = document.querySelectorAll(".gestao-row-chk:checked");
    const chaves = Array.from(chks).map(c => c.value);

    if (chaves.length === 0) {
        toast.warning("Nenhuma nota fiscal selecionada.");
        return;
    }

    const desc = tipoEvento === "210210" ? "Ciência da Emissão" : "Confirmação da Operação";
    const confirma = await showConfirmModal({
        title: "Confirmação em Lote",
        message: `Deseja registrar ${desc} para as ${chaves.length} nota(s) fiscal(is) selecionadas?`,
        confirmText: "Sim, registrar",
        cancelText: "Cancelar",
        icon: "✍️",
    });
    if (!confirma) {
        return;
    }

    try {
        const homolog = AppState.ambiente === "homologacao";
        const res = await apiPost("/api/gestao/manifestacao/lote", {
            chaves: chaves,
            tipo_evento: tipoEvento,
            homologacao: homolog,
        });

        if (res.success && res.data) {
            toast.success(`Manifestação em lote concluída! ${res.data.sucessos} de ${res.data.total} nota(s) manifestada(s) com sucesso.`, 7000);
            loadGestaoDocs(currentGestaoPage);
        } else {
            toast.error("Erro ao manifestar em lote: " + (res.data?.detail || "Falha"));
        }
    } catch (err) {
        toast.error("Erro na requisição: " + err.message);
    }
}


// ====================================================================
// 5. EXPORTAÇÃO EXCEL (.XLSX) COM ABAS POR EMPRESA
// ====================================================================

async function baixarPlanilhaExcelContabil() {
    const mes = document.getElementById("contabil-mes")?.value || 8;
    const ano = document.getElementById("contabil-ano")?.value || 2026;

    const url = `/api/gestao/contabilidade/excel-detalhado?mes=${mes}&ano=${ano}`;
    const defaultName = `fechamento_fiscal_detalhado_${ano}_${String(mes).padStart(2, '0')}.xlsx`;
    const res = await apiDownload(url, defaultName);
    if (res.ok) {
        const blobUrl = window.URL.createObjectURL(res.blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = res.filename || defaultName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
    } else {
        toast.error("Erro ao gerar planilha Excel: " + (res.error || "Falha no download"));
    }
}

async function baixarPlanilhaExcelContabilResumo() {
    const mes = document.getElementById("contabil-mes")?.value || 8;
    const ano = document.getElementById("contabil-ano")?.value || 2026;

    const url = `/api/gestao/contabilidade/excel?mes=${mes}&ano=${ano}`;
    const defaultName = `fechamento_fiscal_resumo_${ano}_${String(mes).padStart(2, '0')}.xlsx`;
    const res = await apiDownload(url, defaultName);
    if (res.ok) {
        const blobUrl = window.URL.createObjectURL(res.blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = res.filename || defaultName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
    } else {
        toast.error("Erro ao gerar planilha Excel: " + (res.error || "Falha no download"));
    }
}

async function recuperarItensContabeis() {
    const btn = document.getElementById("btn-recuperar-itens-contabil");
    const msg = document.getElementById("msg-recuperar-itens");
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Consultando SEFAZ..."; }
    if (msg) { msg.textContent = ""; msg.style.color = "#16a34a"; }

    const empCnpj = document.getElementById("contabil-empresa")?.value || "";
    const max = 500;

    try {
        const res = await apiPost("/api/gestao/contabilidade/recuperar-itens?max_notas=" + max, {
            apenas_empresa_cnpj: empCnpj || undefined,
        });
        if (res.success) {
            const total = res.total_encontradas || 0;
            const ok = res.sucessos || 0;
            const fail = res.falhas || 0;
            const msg2 = `${ok} notas atualizadas com itens via SEFAZ (de ${total} pendentes). ${fail} falharam.`;
            if (msg) {
                msg.textContent = msg2;
                msg.style.color = fail > ok ? "#dc2626" : "#16a34a";
            }
            toast.success(msg2, 8000);
        } else {
            if (msg) { msg.textContent = res.data?.detail || "Erro desconhecido"; msg.style.color = "#dc2626"; }
            toast.error("Erro ao recuperar itens: " + (res.data?.detail || ""));
        }
    } catch (err) {
        if (msg) { msg.textContent = err.message; msg.style.color = "#dc2626"; }
        toast.error("Erro: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = "🔄 Recuperar Itens via SEFAZ"; }
    }
}


// ====================================================================
// 6. BACKUP FISCAL EM NUVEM (RETENÇÃO 5 ANOS) & CONFIGURAÇÕES
// ====================================================================

async function executarBackupFiscalNuvem() {
    const msgEl = document.getElementById("backup-fiscal-status-msg");
    if (msgEl) msgEl.textContent = "Gerando snapshot fiscal...";

    try {
        const res = await apiPost("/api/gestao/cloud/backup", {});
        if (res.success && res.data) {
            const b = res.data.backup || {};
            if (msgEl) msgEl.textContent = `✓ Backup concluído em ${b.data_formatada} (${b.total_notas} notas protegidas até ${b.validade_retencao_legal}).`;
            toast.success(`Backup Fiscal Concluído com Sucesso! ${b.total_notas} notas fiscais protegidas com carimbo de retenção legal de 5 anos.`, 8000);
        } else {
            if (msgEl) msgEl.textContent = "Falha no backup.";
        }
    } catch (err) {
        if (msgEl) msgEl.textContent = "Erro: " + err.message;
    }
}

async function carregarConfigNotificacoes() {
    try {
        const res = await apiGet("/api/gestao/notificacoes/config");
        if (res.success && res.data) {
            const d = res.data;
            if (document.getElementById("notif-cfg-webhook")) document.getElementById("notif-cfg-webhook").value = d.webhook_url || "";
            if (document.getElementById("notif-cfg-tg-token")) document.getElementById("notif-cfg-tg-token").value = d.telegram_bot_token || "";
            if (document.getElementById("notif-cfg-tg-chat")) document.getElementById("notif-cfg-tg-chat").value = d.telegram_chat_id || "";
            if (document.getElementById("notif-cfg-whatsapp")) document.getElementById("notif-cfg-whatsapp").value = d.whatsapp_alert_numbers || "+5519989354849, +5519990151809";
        }
        const audioCheckbox = document.getElementById("cfg-audio-alert-enabled");
        if (audioCheckbox) {
            audioCheckbox.checked = localStorage.getItem("nfe_audio_alert_enabled") !== "false";
        }
    } catch (err) {
        console.warn("Erro ao carregar config de notificações:", err);
    }
}

async function handleSalvarConfigNotificacoes(e) {
    e.preventDefault();
    const webhook = document.getElementById("notif-cfg-webhook")?.value || "";
    const tgToken = document.getElementById("notif-cfg-tg-token")?.value || "";
    const tgChat = document.getElementById("notif-cfg-tg-chat")?.value || "";
    const whatsapp = document.getElementById("notif-cfg-whatsapp")?.value || "";

    const res = await apiPost("/api/gestao/notificacoes/config", {
        webhook_url: webhook,
        telegram_bot_token: tgToken,
        telegram_chat_id: tgChat,
        whatsapp_alert_numbers: whatsapp,
    });

    const resDiv = document.getElementById("result-config-notif");
    if (resDiv) {
        resDiv.style.display = "block";
        if (res.success) {
            resDiv.className = "result success";
            resDiv.innerHTML = `<p>✓ Canais de notificação (WhatsApp, Telegram e Webhooks) salvos com sucesso e teste disparado!</p>`;
        } else {
            resDiv.className = "result error";
            resDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha")}</p>`;
        }
    }
}



// Inicia polling de notificações a cada 30 segundos
if (!notifIntervalId) {
    notifIntervalId = setInterval(carregarNotificacoes, 30000);
}
setTimeout(carregarNotificacoes, 1500);

// Auto-refresh das listagens de NF-e (documentos e saídas) a cada 30 segundos
if (!window._gestaoDocsIntervalId) {
    window._gestaoDocsIntervalId = setInterval(() => {
        const container = document.getElementById("gestao-lista-resultado");
        if (container) loadGestaoDocs(currentGestaoPage);
    }, 30000);
}
if (!window._saidasIntervalId) {
    window._saidasIntervalId = setInterval(() => {
        const tbody = document.getElementById("tbody-saidas-nfe");
        if (tbody) carregarNfeSaidas(currentSaidasPage);
    }, 30000);
}

// Listener do form de notificações na aba de configurações
document.addEventListener("DOMContentLoaded", () => {
    const formNotif = document.getElementById("form-config-notificacoes");
    if (formNotif) formNotif.addEventListener("submit", handleSalvarConfigNotificacoes);
});


// ====================================================================
// LIMPEZA DE DADOS DE TESTE, XMLS ÓRFÃOS E AUDITORIA DA BASE
// ====================================================================

window._currentLimpezaTipo = "homologacao";

function aplicarPresetLimpeza(tipo) {
    document.querySelectorAll(".btn-preset").forEach(b => b.classList.remove("active"));
    const btn = document.getElementById(`preset-btn-${tipo}`);
    if (btn) btn.classList.add("active");

    window._currentLimpezaTipo = tipo;
    const empEl = document.getElementById("limpeza-empresa");
    const termoEl = document.getElementById("limpeza-termo");
    const cnpjEl = document.getElementById("limpeza-cnpj");
    const dtIniEl = document.getElementById("limpeza-dt-ini");
    const dtFimEl = document.getElementById("limpeza-dt-fim");
    const sitEl = document.getElementById("limpeza-situacao");

    if (tipo === "homologacao") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
        if (sitEl) sitEl.value = "todas";
    } else if (tipo === "zeradas") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
    } else if (tipo === "sem_itens") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
    } else if (tipo === "limpar") {
        if (empEl) empEl.value = "";
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
        if (dtIniEl) dtIniEl.value = "";
        if (dtFimEl) dtFimEl.value = "";
        if (sitEl) sitEl.value = "todas";
        window._currentLimpezaTipo = "custom";
    }

    carregarLimpezaPreview(window._currentLimpezaTipo);
}

async function carregarLimpezaPreview(tipoTeste) {
    if (tipoTeste) {
        window._currentLimpezaTipo = tipoTeste;
    } else {
        tipoTeste = window._currentLimpezaTipo || "homologacao";
    }

    const empresa = document.getElementById("limpeza-empresa")?.value || "";
    const termo = document.getElementById("limpeza-termo")?.value || "";
    const cnpj = document.getElementById("limpeza-cnpj")?.value || "";
    const dtIni = document.getElementById("limpeza-dt-ini")?.value || "";
    const dtFim = document.getElementById("limpeza-dt-fim")?.value || "";
    const situacao = document.getElementById("limpeza-situacao")?.value || "todas";

    const statusMsg = document.getElementById("limpeza-status-msg");
    if (statusMsg) statusMsg.textContent = "🔍 Localizando NF-es...";

    const container = document.getElementById("limpeza-resultado-container");
    const tbody = document.getElementById("tbody-limpeza-preview");
    const btnExec = document.getElementById("btn-limpeza-executar");

    try {
        const query = new URLSearchParams({
            empresa_cnpj: empresa.trim(),
            termo: termo.trim(),
            cnpj: cnpj.trim(),
            data_inicio: dtIni,
            data_fim: dtFim,
            situacao: situacao,
            tipo_teste: tipoTeste,
            limit: "200",
        });

        const res = await apiGet(`/api/gestao/limpeza/preview?${query.toString()}`);
        if (res.success && res.data) {
            const d = res.data;
            if (container) container.style.display = "block";

            const elTotal = document.getElementById("limpeza-total-encontradas");
            if (elTotal) elTotal.textContent = d.total_encontradas || 0;

            const elValor = document.getElementById("limpeza-valor-total");
            if (elValor) elValor.textContent = `R$ ${Number(d.valor_total_somado || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

            if (tbody) {
                if (!d.itens || d.itens.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--text-muted);">Nenhuma NF-e localizada para os filtros especificados.</td></tr>`;
                    if (btnExec) btnExec.style.display = "none";
                    if (statusMsg) statusMsg.textContent = "Nenhuma NF-e encontrada.";
                    return;
                }

                tbody.innerHTML = d.itens.map(item => {
                    const ch = item.chave || "";
                    const chCurta = ch ? `${ch.slice(0, 6)}...${ch.slice(-6)}` : "--";
                    const isTestLikely = (item.emitente_nome && /homolog|teste|sem valor|treinamento/i.test(item.emitente_nome)) ||
                                         (item.destinatario_nome && /homolog|teste|sem valor/i.test(item.destinatario_nome)) ||
                                         item.valor_total <= 0;

                    return `
                        <tr>
                            <td style="text-align:center;">
                                <input type="checkbox" class="chk-limpeza-item" value="${ch}" checked onchange="atualizarBadgeSelecaoLimpeza()">
                            </td>
                            <td><strong>${escapeHtml(item.numero || "--")}</strong> <span style="font-size:11px;color:var(--text-muted);">(série ${escapeHtml(item.serie || "1")})</span></td>
                            <td>
                                <div>${escapeHtml(item.emitente_nome || "(Sem Nome)")}</div>
                                <small style="color:var(--text-muted);">${escapeHtml(item.emitente_cnpj || "")}</small>
                                ${isTestLikely ? '<span class="badge-teste-tag" style="margin-left:4px;">🧪 Teste</span>' : ""}
                            </td>
                            <td>
                                <div>${escapeHtml(item.destinatario_nome || "(Sem Nome)")}</div>
                                <small style="color:var(--text-muted);">${escapeHtml(item.destinatario_cnpj || "")}</small>
                            </td>
                            <td>${escapeHtml(item.data_emissao ? item.data_emissao.slice(0, 10) : "--")}</td>
                            <td style="text-align:right;font-weight:600;">R$ ${Number(item.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td><span class="tag-pill">${escapeHtml(item.situacao || "Autorizada")}</span></td>
                            <td style="text-align:center;">
                                ${item.xml_exists_on_disk ? '<span class="badge-real-tag">✓ Sim</span>' : '<span class="badge-teste-tag">✗ Não</span>'}
                            </td>
                            <td>
                                <code style="font-size:11px;" title="${ch}">${chCurta}</code>
                            </td>
                            <td style="text-align:center;white-space:nowrap;">
                                <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${ch}');" title="Visualizar DANFE / Detalhes da Nota" style="padding:4px 8px;font-size:11px;display:inline-flex;align-items:center;gap:4px;">
                                    👁️ Ver DANFE
                                </button>
                            </td>
                        </tr>
                    `;
                }).join("");

                atualizarBadgeSelecaoLimpeza();
                if (statusMsg) statusMsg.textContent = `Pronto (${d.total_encontradas} encontradas)`;
            }
        } else {
            if (statusMsg) statusMsg.textContent = "Erro ao buscar prévia: " + (res.data?.detail || "Falha na conexão");
        }
    } catch (err) {
        if (statusMsg) statusMsg.textContent = "Erro: " + err.message;
    }
}

function atualizarBadgeSelecaoLimpeza() {
    const checkboxes = document.querySelectorAll(".chk-limpeza-item");
    const checked = document.querySelectorAll(".chk-limpeza-item:checked");
    const count = checked.length;

    const badge = document.getElementById("limpeza-count-badge");
    if (badge) badge.textContent = count;

    const btnExec = document.getElementById("btn-limpeza-executar");
    if (btnExec) {
        btnExec.style.display = count > 0 ? "inline-flex" : "none";
    }

    const master = document.getElementById("chk-limpeza-master");
    if (master && checkboxes.length > 0) {
        master.checked = count === checkboxes.length;
        master.indeterminate = count > 0 && count < checkboxes.length;
    }
}

function toggleMasterLimpeza(master) {
    document.querySelectorAll(".chk-limpeza-item").forEach(chk => {
        chk.checked = master.checked;
    });
    atualizarBadgeSelecaoLimpeza();
}

function marcarTodasLimpeza(marcar) {
    document.querySelectorAll(".chk-limpeza-item").forEach(chk => {
        chk.checked = marcar;
    });
    const master = document.getElementById("chk-limpeza-master");
    if (master) master.checked = marcar;
    atualizarBadgeSelecaoLimpeza();
}

async function executarLimpezaNfesConfirmada() {
    const checkboxes = document.querySelectorAll(".chk-limpeza-item:checked");
    const chaves = Array.from(checkboxes).map(c => c.value);

    if (!chaves || chaves.length === 0) {
        alert("Por favor, selecione ao menos uma NF-e para excluir.");
        return;
    }

    const confirmMsg = `⚠️ ATENÇÃO: CONFIRMAÇÃO DE EXCLUSÃO DEFINITIVA\n\n` +
        `Você está prestes a excluir ${chaves.length} nota(s) fiscal(is) do sistema:\n\n` +
        `✓ Registros no SQLite: serão removidos (incluindo produtos, duplicatas e eventos).\n` +
        `✓ Arquivos XML no Disco: serão apagados fisicamente de data/xmls/.\n` +
        `✓ Espelho no Firestore: registros serão excluídos na nuvem.\n\n` +
        `Essa operação NÃO pode ser desfeita. Deseja continuar?`;

    if (!confirm(confirmMsg)) return;

    const btnExec = document.getElementById("btn-limpeza-executar");
    if (btnExec) {
        btnExec.disabled = true;
        btnExec.textContent = "⏳ Excluindo NF-es...";
    }

    const apagarXml = document.getElementById("limpeza-chk-xml")?.checked ?? true;
    const apagarFs = document.getElementById("limpeza-chk-firestore")?.checked ?? true;

    try {
        const res = await apiPost("/api/gestao/limpeza/executar", {
            chaves_selecionadas: chaves,
            apagar_xml_disco: apagarXml,
            apagar_firestore: apagarFs,
        });

        const alertDiv = document.getElementById("limpeza-feedback-alert");
        if (alertDiv) {
            alertDiv.style.display = "block";
            if (res.success) {
                alertDiv.className = "result success";
                alertDiv.innerHTML = `<p>✓ ${escapeHtml(res.data?.message || "NF-es excluídas com sucesso!")}</p>`;
            } else {
                alertDiv.className = "result error";
                alertDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha na exclusão")}</p>`;
            }
        }

        // Recarrega a prévia e a auditoria da base
        carregarLimpezaPreview();
        carregarAuditoriaBase();
    } catch (err) {
        alert("Erro na requisição: " + err.message);
    } finally {
        if (btnExec) {
            btnExec.disabled = false;
            btnExec.textContent = "🗑️ Excluir Selecionadas";
        }
    }
}

async function carregarAuditoriaXmlsOrfaos() {
    const statusMsg = document.getElementById("orfaos-status-msg");
    if (statusMsg) statusMsg.textContent = "🔍 Analisando arquivos...";

    const btnApagar = document.getElementById("btn-apagar-orfaos");
    const container = document.getElementById("orfaos-resultado-container");
    const tbody = document.getElementById("tbody-orfaos-preview");

    try {
        const res = await apiGet("/api/gestao/limpeza/xmls-orfaos");
        if (res.success && res.data) {
            const d = res.data;
            const elDisco = document.getElementById("kpi-orfaos-disco");
            if (elDisco) elDisco.textContent = d.total_xmls_disco || 0;

            const elBanco = document.getElementById("kpi-orfaos-banco");
            if (elBanco) elBanco.textContent = d.total_docs_banco || 0;

            const elTotal = document.getElementById("kpi-orfaos-total");
            if (elTotal) elTotal.textContent = d.total_orfaos || 0;

            const elTam = document.getElementById("kpi-orfaos-tamanho");
            if (elTam) elTam.textContent = `${d.tamanho_orfaos_formatado || "0 B"} em disco`;

            if (container) container.style.display = "block";

            if (tbody) {
                if (!d.amostra_orfaos || d.amostra_orfaos.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--pastel-green-text);font-weight:600;">✓ Nenhum arquivo XML órfão encontrado! A pasta de armazenamento está 100% íntegra.</td></tr>`;
                    if (btnApagar) btnApagar.style.display = "none";
                    if (statusMsg) statusMsg.textContent = "Nenhum arquivo órfão.";
                    return;
                }

                tbody.innerHTML = d.amostra_orfaos.map(item => `
                    <tr>
                        <td><code>${escapeHtml(item.filename)}</code></td>
                        <td><small style="color:var(--text-muted);">${escapeHtml(item.chave || "(Sem Chave Válida)")}</small></td>
                        <td>${escapeHtml(item.size_formatted || "0 B")}</td>
                        <td>${escapeHtml(item.modified_at || "--")}</td>
                        <td>
                            ${item.is_corrupt_or_empty ? '<span class="badge-teste-tag">Vazio / Corrompido</span>' : '<span class="badge-teste-tag">Órfão (Sem Banco)</span>'}
                        </td>
                    </tr>
                `).join("");

                if (btnApagar) {
                    btnApagar.style.display = "inline-flex";
                    btnApagar.textContent = `🧹 Apagar ${d.total_orfaos} XMLs Órfãos (${d.tamanho_orfaos_formatado})`;
                }
                if (statusMsg) statusMsg.textContent = `Identificados ${d.total_orfaos} arquivos órfãos.`;
            }
        } else {
            if (statusMsg) statusMsg.textContent = "Erro ao auditar XMLs: " + (res.data?.detail || "Falha");
        }
    } catch (err) {
        if (statusMsg) statusMsg.textContent = "Erro: " + err.message;
    }
}

async function apagarXmlsOrfaosConfirmado() {
    const confirmMsg = `Deseja realmente apagar todos os arquivos XML órfãos do disco?\n\n` +
        `Eles não estão vinculados a nenhuma NF-e no banco de dados e serão excluídos definitivamente de data/xmls/ para recuperar espaço.`;

    if (!confirm(confirmMsg)) return;

    const btnApagar = document.getElementById("btn-apagar-orfaos");
    if (btnApagar) {
        btnApagar.disabled = true;
        btnApagar.textContent = "⏳ Apagando XMLs...";
    }

    try {
        const res = await apiPost("/api/gestao/limpeza/apagar-xmls-orfaos", {});
        const alertDiv = document.getElementById("orfaos-feedback-alert");
        if (alertDiv) {
            alertDiv.style.display = "block";
            if (res.success) {
                alertDiv.className = "result success";
                alertDiv.innerHTML = `<p>✓ ${escapeHtml(res.data?.message || "XMLs órfãos excluídos!")}</p>`;
            } else {
                alertDiv.className = "result error";
                alertDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha na exclusão")}</p>`;
            }
        }

        carregarAuditoriaXmlsOrfaos();
        carregarAuditoriaBase();
    } catch (err) {
        alert("Erro na requisição: " + err.message);
    } finally {
        if (btnApagar) {
            btnApagar.disabled = false;
            btnApagar.textContent = "🧹 Apagar XMLs Órfãos do Disco";
        }
    }
}

async function carregarAuditoriaBase() {
    try {
        const res = await apiGet("/api/gestao/limpeza/auditoria-base");
        if (res.success && res.data) {
            const d = res.data;
            const rn = d.resumo_notas || {};
            const arm = d.armazenamento || {};
            const fs = d.firestore || {};

            const elHora = document.getElementById("auditoria-data-hora");
            if (elHora) elHora.textContent = `Última checagem: ${new Date().toLocaleTimeString("pt-BR")}`;

            const elTot = document.getElementById("audit-kpi-total-docs");
            if (elTot) elTot.textContent = Number(rn.total_docs || 0).toLocaleString("pt-BR");

            const elEnt = document.getElementById("audit-kpi-entradas");
            if (elEnt) elEnt.textContent = `${Number(rn.total_entradas || 0).toLocaleString("pt-BR")}`;

            const elSai = document.getElementById("audit-kpi-saidas");
            if (elSai) elSai.textContent = `${Number(rn.total_saidas || 0).toLocaleString("pt-BR")}`;

            const elCXml = document.getElementById("audit-kpi-com-xml");
            if (elCXml) elCXml.textContent = Number(rn.total_com_xml || 0).toLocaleString("pt-BR");

            const elSXml = document.getElementById("audit-kpi-sem-xml");
            if (elSXml) elSXml.textContent = `${Number(rn.total_sem_xml || 0).toLocaleString("pt-BR")}`;

            const elTst = document.getElementById("audit-kpi-testes");
            if (elTst) elTst.textContent = Number(rn.total_testes_identificados || 0).toLocaleString("pt-BR");

            const elTstVal = document.getElementById("audit-kpi-testes-valor");
            if (elTstVal) elTstVal.textContent = `R$ ${Number(rn.valor_testes_somado || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} somado`;

            const elDb = document.getElementById("audit-kpi-db-size");
            if (elDb) elDb.textContent = `SQLite: ${arm.db_size_formatado || "--"}`;

            const elXmlDir = document.getElementById("audit-kpi-xmls-size");
            if (elXmlDir) elXmlDir.textContent = `${arm.xmls_dir_size_formatado || "--"} (${arm.xmls_count_disco || 0} arquivos)`;

            const elFs = document.getElementById("audit-kpi-firestore");
            if (elFs) elFs.textContent = fs.configurado ? "✓ Conectado" : "Desconectado";

            const elFsP = document.getElementById("audit-kpi-firestore-proj");
            if (elFsP) elFsP.textContent = fs.project_id || "Não configurado";

            // Empresas
            const tbodyEmp = document.getElementById("tbody-audit-empresas");
            if (tbodyEmp) {
                if (!d.empresas || d.empresas.length === 0) {
                    tbodyEmp.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">Nenhum certificado cadastrado.</td></tr>`;
                } else {
                    tbodyEmp.innerHTML = d.empresas.map(emp => `
                        <tr>
                            <td><strong>${escapeHtml(emp.razao_social || "--")}</strong></td>
                            <td><code>${escapeHtml(emp.cnpj || "--")}</code></td>
                            <td>${escapeHtml(emp.valid_to || "--")} <small style="color:var(--text-muted);">(${emp.days_remaining || 0} dias)</small></td>
                            <td><code>${escapeHtml(emp.last_nsu || "0")}</code></td>
                            <td><code>${escapeHtml(emp.max_nsu || "0")}</code></td>
                            <td>${escapeHtml(emp.last_sync_time || "Nunca")}</td>
                            <td><span class="tag-pill">${escapeHtml(emp.last_sync_status || "Pendente")}</span></td>
                        </tr>
                    `).join("");
                }
            }

            // Top Emitentes
            const tbodyEmit = document.getElementById("tbody-audit-emitentes");
            if (tbodyEmit) {
                if (!d.top_emitentes || d.top_emitentes.length === 0) {
                    tbodyEmit.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">Nenhum emitente registrado.</td></tr>`;
                } else {
                    tbodyEmit.innerHTML = d.top_emitentes.map(e => `
                        <tr>
                            <td>
                                <strong>${escapeHtml(e.nome || "--")}</strong>
                                ${e.is_teste_suspeito ? '<span class="badge-teste-tag" style="margin-left:4px;">🧪 Teste / Homol</span>' : ""}
                            </td>
                            <td><code>${escapeHtml(e.cnpj || "--")}</code></td>
                            <td>${escapeHtml(e.uf || "--")}</td>
                            <td style="text-align:right;font-weight:600;">${Number(e.total_notas || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align:right;font-weight:600;">R$ ${Number(e.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td>${escapeHtml(e.ultima_emissao ? e.ultima_emissao.slice(0, 10) : "--")}</td>
                            <td>
                                ${e.is_teste_suspeito ? '<span class="badge-teste-tag">Teste / Homol</span>' : '<span class="badge-real-tag">✓ Normal</span>'}
                            </td>
                        </tr>
                    `).join("");
                }
            }
        }
    } catch (err) {
        console.warn("Erro ao carregar auditoria da base:", err);
    }
}


async function carregarAuditoriaGaps() {
    const container = document.getElementById("resultado-auditoria-gaps");
    const empCnpj = document.getElementById("gaps-filtro-empresa")?.value || "";
    const serie = document.getElementById("gaps-filtro-serie")?.value || "";

    if (container) {
        container.innerHTML = `<div style="text-align:center;padding:30px;"><span class="spinner"></span> Analisando sequência numérica de todas as filiais...</div>`;
    }

    try {
        let url = "/api/gestao/auditoria/gaps-numeracao";
        const params = [];
        if (empCnpj) params.push(`empresa_cnpj=${encodeURIComponent(empCnpj)}`);
        if (serie) params.push(`serie=${encodeURIComponent(serie)}`);
        if (params.length > 0) url += `?${params.join("&")}`;

        const res = await apiGet(url);
        if (!res.success || !res.data) {
            if (container) container.innerHTML = `<div class="result error"><p>Erro ao auditar saltos de numeração: ${escapeHtml(res.data?.detail || "Falha")}</p></div>`;
            return;
        }

        const d = res.data;
        const kpiEmp = document.getElementById("gap-kpi-empresas");
        const kpiGaps = document.getElementById("gap-kpi-gaps");
        const kpiFalt = document.getElementById("gap-kpi-faltando");
        const kpiInut = document.getElementById("gap-kpi-inutilizados");

        if (kpiEmp) kpiEmp.textContent = d.total_empresas_auditadas || 0;
        if (kpiGaps) kpiGaps.textContent = d.total_gaps_encontrados || 0;
        if (kpiFalt) kpiFalt.textContent = Number(d.total_numeros_faltando || 0).toLocaleString("pt-BR");
        if (kpiInut) kpiInut.textContent = Number(d.total_numeros_inutilizados || 0).toLocaleString("pt-BR");

        if (!d.empresas || d.empresas.length === 0) {
            if (container) {
                container.innerHTML = `<div class="result success"><p>✓ Nenhuma nota de saída registrada ou nenhum gap encontrado para os filtros selecionados.</p></div>`;
            }
            return;
        }

        let html = "";
        d.empresas.forEach(emp => {
            emp.series.forEach(s => {
                html += `
                    <div class="painelSessao" style="margin-bottom:16px;">
                        <div class="painelSessaoTitulo" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                            <div>
                                🏢 <b>${escapeHtml(emp.razao_social || emp.cnpj)}</b>
                                <small style="color:var(--text-muted);margin-left:6px;">(CNPJ: ${escapeHtml(emp.cnpj)} | Série: ${escapeHtml(s.serie)})</small>
                            </div>
                            <div>
                                <span class="tag-pill" style="font-size:11px;">Faixa Emitida: Nº ${s.menor_numero} a Nº ${s.maior_numero}</span>
                                <span class="tag-pill" style="font-size:11px;background:#f0fdf4;color:#166534;border-color:#bbf7d0;">Presentes: ${s.total_presente}</span>
                                ${s.total_faltando > 0 ? `<span class="tag-pill" style="font-size:11px;background:#fef2f2;color:#991b1b;border-color:#fecaca;">🚨 ${s.total_faltando} Faltando</span>` : `<span class="tag-pill" style="font-size:11px;background:#f0fdf4;color:#166534;border-color:#bbf7d0;">✓ 100% Contínua</span>`}
                            </div>
                        </div>

                        ${s.gaps && s.gaps.length > 0 ? `
                            <div class="table-responsive" style="margin-top:10px;">
                                <table class="tabelaGrupo">
                                    <thead>
                                        <tr>
                                            <th style="width:20%;">Faixa do Salto (Gap)</th>
                                            <th style="width:12%;text-align:center;">Qtd Números</th>
                                            <th style="width:20%;">Status</th>
                                            <th style="width:30%;">Diagnóstico / Detalhes</th>
                                            <th style="width:18%;text-align:center;">Ações Fiscais</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${s.gaps.map(g => `
                                            <tr>
                                                <td><b style="font-family:monospace;font-size:12px;">${escapeHtml(g.faixa_formatada)}</b></td>
                                                <td style="text-align:center;">${g.quantidade}</td>
                                                <td><span class="${g.badge_class}">${escapeHtml(g.status)}</span></td>
                                                <td style="font-size:11px;color:var(--text-muted);">${escapeHtml(g.detalhes)}</td>
                                                <td style="text-align:center;">
                                                    ${!g.inutilizado ? `
                                                        <button type="button" class="btn-action" onclick="abrirModalInutilizarComDados('${emp.cnpj}', '${s.serie}', ${g.numero_inicio}, ${g.numero_fim});" style="background:#dc2626;color:#fff;border-color:#dc2626;font-size:11px;padding:3px 8px;" title="Transmitir pedido oficial de inutilização à SEFAZ">
                                                            🚫 Inutilizar Faixa
                                                        </button>
                                                    ` : `
                                                        <span style="color:#16a34a;font-size:11px;font-weight:bold;">✓ Regularizada</span>
                                                    `}
                                                </td>
                                            </tr>
                                        `).join("")}
                                    </tbody>
                                </table>
                            </div>
                        ` : `
                            <div style="padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;color:#166534;font-size:12px;margin-top:8px;">
                                ✓ <b>Excelente!</b> Sequência 100% contínua. Não há quebras ou saltos de numeração nesta série.
                            </div>
                        `}
                    </div>
                `;
            });
        });

        if (container) container.innerHTML = html;
    } catch (e) {
        if (container) container.innerHTML = `<div class="result error"><p>Erro ao executar auditoria: ${escapeHtml(e.message)}</p></div>`;
    }
}

function abrirModalInutilizarComDados(cnpj, serie, numIni, numFim) {
    if (typeof abrirModalInutilizarNfe === "function") {
        abrirModalInutilizarNfe();
    } else {
        const modal = document.getElementById("modal-inutilizar-nfe");
        if (modal) modal.style.display = "flex";
    }
    const empSelect = document.getElementById("inutilizar-empresa");
    const serieInp = document.getElementById("inutilizar-serie");
    const numIniInp = document.getElementById("inutilizar-num-ini");
    const numFimInp = document.getElementById("inutilizar-num-fim");
    const justInp = document.getElementById("inutilizar-justificativa");

    if (empSelect) empSelect.value = cnpj;
    if (serieInp) serieInp.value = serie;
    if (numIniInp) numIniInp.value = numIni;
    if (numFimInp) numFimInp.value = numFim;
    if (justInp) justInp.value = `Salto de numeração identificado em auditoria contábil. Numeração não utilizada na emissão.`;
}



// ====================================================================
// 1. GESTÃO FINANCEIRA & CONTAS A PAGAR (DUPLICATAS DE NF-e)
// ====================================================================

let filtroStatusContasAtual = "";

function filtrarStatusContas(st) {
    filtroStatusContasAtual = st;
    const periodo = document.getElementById("fin-mes")?.value || "";
    const empresa = document.getElementById("fin-empresa")?.value || "";
    carregarContasAPagar(periodo, empresa);
}

// ====================================================================
// CONTROLES UNIFICADOS: PERÍODO + EMPRESA

async function alternarPagamentoConta(dupId) {
    try {
        const res = await apiPost(`/api/gestao/financeiro/duplicata/${dupId}/pagar`, {});
        if (res.success) {
            const periodo = document.getElementById("fin-mes")?.value || "";
            const empresa = document.getElementById("fin-empresa")?.value || "";
            carregarContasAPagar(periodo, empresa);
        }
    } catch (err) {
        toast.error("Erro ao alterar status da duplicata: " + err.message);
    }
}


// ====================================================================
// CONTROLES UNIFICADOS: PERÍODO + EMPRESA
// ====================================================================

function preencherPeriodo() {
    const sel = document.getElementById("fin-mes");
    if (!sel) return;
    sel.innerHTML = "";
    const now = new Date();
    for (let i = 11; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const mes = String(d.getMonth() + 1).padStart(2, "0");
        const ano = d.getFullYear();
        const opt = document.createElement("option");
        opt.value = `${ano}-${mes}`;
        opt.textContent = `${mes}/${ano}`;
        sel.appendChild(opt);
    }
    sel.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

async function carregarEmpresas() {
    try {
        const res = await apiGet("/api/gestao/financeiro/empresas");
        const empresas = (res.success && res.data) ? (res.data.empresas || res.data) : [];
        const sel = document.getElementById("fin-empresa");
        if (!sel) return;
        sel.innerHTML = '<option value="">🏢 Todas as 5 Empresas (Consolidado)</option>';
        empresas.forEach(e => {
            const cnpjLimpo = (e.cnpj || e.empresa_cnpj || "").replace(/\D/g, "");
            const cnpjFmt = cnpjLimpo.length === 14 
                ? `${cnpjLimpo.slice(0,2)}.${cnpjLimpo.slice(2,5)}.${cnpjLimpo.slice(5,8)}/${cnpjLimpo.slice(8,12)}-${cnpjLimpo.slice(12,14)}`
                : cnpjLimpo;
            const opt = document.createElement("option");
            opt.value = cnpjLimpo;
            opt.textContent = `📍 ${e.nome || e.emitente_nome || ""} — ${cnpjFmt}`;
            sel.appendChild(opt);
        });
    } catch (err) { /* silencioso */ }
}

async function carregarFinanceiro() {
    const periodo = document.getElementById("fin-mes")?.value || "";
    const empresa = document.getElementById("fin-empresa")?.value || "";
    const mes = periodo ? parseInt(periodo.split("-")[1]) : undefined;
    const ano = periodo ? parseInt(periodo.split("-")[0]) : undefined;
    carregarContasAPagar(periodo, empresa, mes, ano);
    carregarContasAReceber(periodo, empresa, mes, ano);
    carregarDreConsolidado(ano, mes, empresa);
    carregarApuracaoSimplesNacional(ano, mes, empresa);
    carregarDreMargens(empresa);
    carregarImpostosInterestaduais(empresa);
    carregarAging(periodo, empresa);
    carregarInadimplencia(empresa);
}

// Versões atualizadas das funções de carregamento com parâmetros de período
async function carregarContasAPagar(periodo, empresa, mes, ano) {
    const container = document.getElementById("financeiro-lista-resultado");
    if (!container) return;
    const emp = empresa || document.getElementById("fin-empresa")?.value || "";
    let url = `/api/gestao/financeiro/contas-a-pagar?empresa_cnpj=${encodeURIComponent(emp)}`;
    if (filtroStatusContasAtual) url += `&status=${encodeURIComponent(filtroStatusContasAtual)}`;
    if (periodo) url += `&mes=${encodeURIComponent(periodo)}`;
    const res = await apiGet(url);
    if (!res.success) { container.innerHTML = `<div class="result error">Erro: ${escapeHtml(res.data?.detail || "")}</div>`; return; }
    const data = res.data || {};
    const dups = data.duplicatas || [];
    const fmtMoney = (v) => "R$ " + (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (document.getElementById("fin-kpi-aberto")) document.getElementById("fin-kpi-aberto").textContent = fmtMoney(data.total_aberto);
    if (document.getElementById("fin-kpi-vencido")) document.getElementById("fin-kpi-vencido").textContent = fmtMoney(data.total_vencido);
    if (document.getElementById("fin-kpi-hoje")) document.getElementById("fin-kpi-hoje").textContent = fmtMoney(data.vencendo_hoje);
    if (document.getElementById("fin-kpi-pago")) document.getElementById("fin-kpi-pago").textContent = fmtMoney(data.total_pago);
    if (dups.length === 0) { container.innerHTML = `<div style="padding:20px;text-align:center;background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;color:#666;">Nenhuma duplicata encontrada.</div>`; return; }
    container.innerHTML = `<div class="table-responsive"><table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;"><thead><tr class="linhaTitulo" style="background:#e9ecef;">
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','status')">Status</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','d_venc')">Vencimento</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','emitente_nome')">Fornecedor</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','empresa_cnpj')">Empresa</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','nfe_numero')">NF-e/Parc.</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-pagar','v_dup')">Valor</th>
        <th style="padding:6px;">Valor NF-e</th>
        <th style="padding:6px;">Ações</th>
    </tr></thead><tbody>${dups.map(d => {
        let corBadge = "#2980b9", descBadge = "A VENCER";
        if (d.status_calc === "PAGO") { corBadge = "#27ae60"; descBadge = "PAGO"; }
        else if (d.status_calc === "VENCIDO") { corBadge = "#c0392b"; descBadge = "VENCIDO"; }
        else if (d.status_calc === "VENCE_HOJE") { corBadge = "#f39c12"; descBadge = "VENCE HOJE"; }
        const dtVenc = d.d_venc ? d.d_venc.split("-").reverse().join("/") : "—";
        return `<tr style="${d.pago ? 'opacity:0.6;' : ''}">
            <td><span class="badge-ambiente" style="background:${corBadge};font-size:10px;">${descBadge}</span></td>
            <td><b>${escapeHtml(dtVenc)}</b></td>
            <td><b>${escapeHtml(d.emitente_nome || "")}</b></td>
            <td>${escapeHtml(d.destinatario_nome || d.empresa_cnpj || "")}</td>
            <td>NF ${escapeHtml(d.nfe_numero || "—")} (Parc. ${escapeHtml(d.n_dup || "1")})</td>
            <td style="text-align:right;font-weight:bold;color:#2c3e50;">${fmtMoney(d.v_dup)}</td>
            <td style="text-align:right;color:#888;">${fmtMoney(d.valor_total || 0)}</td>
            <td><div class="actions-cell">
                <button type="button" class="btn-action ${d.pago ? '' : 'btn-action-success'}" onclick="alternarPagamentoConta(${d.id});">${d.pago ? "↺ Desmarcar" : "✓ Pagar"}</button>
                <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${d.chave}');">👁️ DANFE</button>
            </div></td>
        </tr>`;
    }).join("")}</tbody></table></div>`;
}

async function carregarContasAReceber(periodo, empresa, mes, ano) {
    const container = document.getElementById("financeiro-lista-receber");
    if (!container) return;
    const emp = empresa || document.getElementById("fin-empresa")?.value || "";
    let url = `/api/gestao/financeiro/contas-a-receber?empresa_cnpj=${encodeURIComponent(emp)}`;
    if (filtroStatusReceberAtual) url += `&status=${encodeURIComponent(filtroStatusReceberAtual)}`;
    if (periodo) url += `&mes=${encodeURIComponent(periodo)}`;
    const res = await apiGet(url);
    if (!res.success) { container.innerHTML = `<div class="result error">Erro: ${escapeHtml(res.data?.detail || "")}</div>`; return; }
    const data = res.data || {};
    const recs = data.contas || [];
    const fmtMoney = (v) => "R$ " + (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (document.getElementById("fin-kpi-rec-aberto")) document.getElementById("fin-kpi-rec-aberto").textContent = fmtMoney(data.total_aberto);
    if (document.getElementById("fin-kpi-rec-vencido")) document.getElementById("fin-kpi-rec-vencido").textContent = fmtMoney(data.total_vencido);
    if (document.getElementById("fin-kpi-rec-hoje")) document.getElementById("fin-kpi-rec-hoje").textContent = fmtMoney(data.vencendo_hoje);
    if (document.getElementById("fin-kpi-rec-recebido")) document.getElementById("fin-kpi-rec-recebido").textContent = fmtMoney(data.total_recebido);
    if (recs.length === 0) { container.innerHTML = `<div style="padding:20px;text-align:center;background:#f9f9f9;border:1px solid #e0e0e0;border-radius:4px;color:#666;">Nenhuma conta a receber encontrada.</div>`; return; }
    container.innerHTML = `<div class="table-responsive"><table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;"><thead><tr class="linhaTitulo" style="background:#e9ecef;">
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','status')">Status</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','d_venc')">Vencimento</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','cliente_nome')">Cliente</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','empresa_cnpj')">Empresa</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','nfe_numero')">NF-e/Parc.</th>
        <th style="padding:6px;cursor:pointer;" onclick="ordenarTabela('fin-receber','v_dup')">Valor</th>
        <th style="padding:6px;">Valor NF-e</th>
        <th style="padding:6px;">Ações</th>
    </tr></thead><tbody>${recs.map(d => {
        let corBadge = "#2980b9", descBadge = "A RECEBER";
        if (d.status_calc === "RECEBIDO") { corBadge = "#16a085"; descBadge = "RECEBIDO"; }
        else if (d.status_calc === "VENCIDO") { corBadge = "#c0392b"; descBadge = "VENCIDO"; }
        else if (d.status_calc === "VENCE_HOJE") { corBadge = "#f39c12"; descBadge = "VENCE HOJE"; }
        const dtVenc = d.d_venc ? d.d_venc.split("-").reverse().join("/") : "—";
        return `<tr style="${d.recebido ? 'opacity:0.6;' : ''}">
            <td><span class="badge-ambiente" style="background:${corBadge};font-size:10px;">${descBadge}</span></td>
            <td><b>${escapeHtml(dtVenc)}</b></td>
            <td><b>${escapeHtml(d.cliente_nome || "")}</b></td>
            <td>${escapeHtml(d.empresa_cnpj || "")}</td>
            <td>NF ${escapeHtml(d.nfe_numero || "—")} (Parc. ${escapeHtml(d.n_dup || "1")})</td>
            <td style="text-align:right;font-weight:bold;color:#2c3e50;">${fmtMoney(d.v_dup)}</td>
            <td style="text-align:right;color:#888;">${fmtMoney(d.valor_total || 0)}</td>
            <td><div class="actions-cell">
                <button type="button" class="btn-action ${d.recebido ? '' : 'btn-action-success'}" onclick="alternarRecebimentoConta(${d.id});">${d.recebido ? "↺ Desmarcar" : "✓ Receber"}</button>
                <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${d.chave}');">👁️ DANFE</button>
            </div></td>
        </tr>`;
    }).join("")}</tbody></table></div>`;
}

function switchFinTab(tab) {
    const tabs = ["pagar", "receber", "dre"];
    tabs.forEach(t => {
        const p = document.getElementById(`subtab-fin-${t}`);
        const b = document.getElementById(`btn-tab-fin-${t}`);
        if (p) p.style.display = (t === tab) ? "" : "none";
        if (b) b.classList.toggle("active", t === tab);
    });
    carregarFinanceiro();
}


let filtroStatusReceberAtual = "";

function filtrarStatusReceber(st) {
    filtroStatusReceberAtual = st;
    const periodo = document.getElementById("fin-mes")?.value || "";
    const empresa = document.getElementById("fin-empresa")?.value || "";
    carregarContasAReceber(periodo, empresa);
}

async function carregarImpostosInterestaduais(empresa) {
    const container = document.getElementById("impostos-interestaduais-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Calculando impostos a recolher de NF-e interestaduais...</div>`;

    try {
        const emp = empresa || document.getElementById("fin-empresa")?.value || "";
        const res = await apiGet(`/api/gestao/financeiro/impostos-interestaduais?empresa_cnpj=${encodeURIComponent(emp)}`);
        const data = res.data || {};
        const itens = data.itens || [];

        const fmtR = (v) => "R$ " + parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        if (itens.length === 0) {
            container.innerHTML = `<div style="padding:15px;color:#888;text-align:center;">Nenhuma NF-e de entrada interestadual com imposto a recolher (DIFAL) encontrada.</div>`;
            return;
        }

        const rows = itens.map(i => `
            <tr>
                <td><b>${escapeHtml(i.numero || "—")}</b><br><small style="color:#64748b;">${escapeHtml((i.data_emissao || "").split("T")[0])}</small></td>
                <td><b>${escapeHtml(i.emitente_nome || "")}</b></td>
                <td style="text-align:center;"><span class="badge-ambiente" style="background:#8e44ad;font-size:10px;">${escapeHtml(i.uf_origem)} → ${escapeHtml(i.uf_destino)}</span></td>
                <td style="text-align:right;">${fmtR(i.valor_total)}</td>
                <td style="text-align:right;color:#64748b;">${fmtR(i.icms_proprio)}</td>
                <td style="text-align:center;">${i.aliquota_interna_destino}% / ${i.aliquota_aplicada}%</td>
                <td style="text-align:right;font-weight:bold;color:#8e44ad;">${fmtR(i.difal_estimado)}</td>
                <td><button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${i.chave}');">👁️ DANFE</button></td>
            </tr>
        `).join("");

        container.innerHTML = `
            <div style="margin-bottom:10px;padding:10px;background:#f4ecf7;border-left:4px solid #8e44ad;border-radius:4px;">
                <b>Total estimado de DIFAL a recolher:</b> <span style="font-size:16px;font-weight:bold;color:#8e44ad;">${fmtR(data.total_difal_estimado)}</span>
                &nbsp;|&nbsp; ${data.total_notas} NF-e interestaduais &nbsp;|&nbsp; Base: ${fmtR(data.total_base)}
            </div>
            <div class="table-responsive">
                <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                    <thead>
                        <tr class="linhaTitulo" style="background:#e9ecef;">
                            <th style="padding:6px;">NF-e</th>
                            <th style="padding:6px;">Fornecedor (UF Origem)</th>
                            <th style="padding:6px;text-align:center;">Trajeto</th>
                            <th style="padding:6px;text-align:right;">Valor Total</th>
                            <th style="padding:6px;text-align:right;">ICMS Próprio</th>
                            <th style="padding:6px;text-align:center;">Aliq. Int./Apl.</th>
                            <th style="padding:6px;text-align:right;">DIFAL Estimado</th>
                            <th style="padding:6px;">Ações</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
            <div style="margin-top:8px;font-size:11px;color:#888;">${escapeHtml(data.observacao || "")}</div>
        `;
    } catch (err) {
        container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro ao calcular impostos interestaduais: ${escapeHtml(err.message)}</div>`;
    }
}


async function carregarDreConsolidado(ano, mes, empresa) {
    const container = document.getElementById("dre-consolidado-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Calculando DRE consolidado...</div>`;

    try {
        const a = ano || (document.getElementById("fin-mes")?.value ? document.getElementById("fin-mes").value.split("-")[0] : "");
        const m = mes || (document.getElementById("fin-mes")?.value ? document.getElementById("fin-mes").value.split("-")[1] : "");
        const emp = empresa || document.getElementById("fin-empresa")?.value || "";
        let url = `/api/gestao/financeiro/dre?`;
        if (a) url += `ano=${encodeURIComponent(a)}&`;
        if (m) url += `mes=${encodeURIComponent(m)}&`;
        if (emp) url += `empresa_cnpj=${encodeURIComponent(emp)}&`;

        const res = await apiGet(url);
        if (!res || res.success === false) {
            container.innerHTML = `<div class="result error">Erro ao carregar DRE consolidado.</div>`;
            return;
        }

        const d = res.data || {};

        const fmtR = (v) => "R$ " + parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const fmtP = (v) => `${parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;

        const linha = (label, valor, pctv, cor, negativa=false) => `
            <div class="dre-linha" style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid var(--border-subtle);${negativa ? 'color:#ef4444;font-weight:bold;' : ''}">
                <div style="font-size:13px;"><span style="display:inline-block;width:14px;color:${cor};">${negativa ? '–' : '+'}</span> ${label} ${pctv !== "" ? `<small style="color:var(--text-muted);">(${fmtP(pctv)} da Receita Líquida)</small>` : ''}</div>
                <div style="font-size:14px;font-weight:bold;color:${cor};">${fmtR(valor)}</div>
            </div>
        `;

        const totalizador = (label, valor, cor, destaque=false) => `
            <div class="dre-totalizador" style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:var(--bg-surface-alt);border-left:5px solid ${cor};border-radius:4px;margin-top:6px;border:1px solid var(--border-main);border-left-width:5px;">
                <div style="font-size:14px;font-weight:bold;color:${cor};">${label}</div>
                <div style="font-size:18px;font-weight:bold;color:${cor};">${fmtR(valor)}</div>
            </div>
        `;

        container.innerHTML = `
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">Competência: <b>${escapeHtml(d.competencia || "")}</b> &nbsp;|&nbsp; ${d.qtd_vendas || 0} vendas no período</div>
            <div style="border:1px solid var(--border-main);border-radius:6px;overflow:hidden;background:var(--bg-surface);">
                ${linha("Receita Bruta (Saídas)", d.receita_bruta, "", "var(--text-main)")}
                ${linha("Impostos s/ Venda (ICMS+PIS+COFINS+IPI)", d.impostos_venda, d.margem_liquida_pct, "#ef4444", true)}
                ${totalizador("RECEITA LÍQUIDA", d.receita_liquida, "#0284c7", true)}
                ${linha("CPV - Custo das Mercadorias Vendidas (Entradas)", d.cpv, "", "#f97316", true)}
                ${totalizador(`LUCRO BRUTO (Margem ${fmtP(d.margem_bruta_pct)})`, d.lucro_bruto, "#10b981", true)}
                ${linha("Imposto Simples Nacional (DAS estimado)", d.das_simples_estimado, d.margem_liquida_pct, "#a855f7", true)}
                ${totalizador(`LUCRO LÍQUIDO (Margem ${fmtP(d.margem_liquida_pct)})`, d.lucro_liquido, d.lucro_liquido >= 0 ? "#10b981" : "#ef4444", true)}
            </div>
        `;

    } catch (err) {
        container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro ao carregar DRE consolidado: ${escapeHtml(err.message)}</div>`;
    }
}


// ====================================================================
// AGING, INADIMPLÊNCIA, TENDÊNCIA, EXPORT, ORDENAÇÃO
// ====================================================================

async function carregarAging(periodo, empresa) {
    const container = document.getElementById("aging-painel");
    if (!container) return;
    const emp = empresa || document.getElementById("fin-empresa")?.value || "";
    let url = `/api/gestao/financeiro/contas-a-pagar?empresa_cnpj=${encodeURIComponent(emp)}`;
    if (periodo) url += `&mes=${encodeURIComponent(periodo)}`;
    const res = await apiGet(url);
    if (!res.success) { container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro</div>`; return; }
    const dups = (res.data || {}).duplicatas || [];
    const now = new Date().toISOString().slice(0, 10);
    const buckets = {"0–30": [], "31–60": [], "61–90": [], ">90": []};
    let total = 0;
    dups.forEach(d => {
        if (d.pago) return;
        const v = parseFloat(d.v_dup) || 0;
        if (v <= 0) return;
        total += v;
        const diff = Math.floor((new Date(d.d_venc) - new Date(now)) / 86400000);
        if (diff <= 30) buckets["0–30"].push(d);
        else if (diff <= 60) buckets["31–60"].push(d);
        else if (diff <= 90) buckets["61–90"].push(d);
        else buckets[">90"].push(d);
    });
    const fmtMoney = (v) => "R$ " + (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const cores = {"0–30": "#27ae60", "31–60": "#f39c12", "61–90": "#e67e22", ">90": "#c0392b"};
    let html = `<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px;">`;
    for (const [b, docs] of Object.entries(buckets)) {
        const val = docs.reduce((s, d) => s + (parseFloat(d.v_dup) || 0), 0);
        html += `<div style="background:#f8fafc;border:1px solid #e0e0e0;border-left:4px solid ${cores[b]};border-radius:4px;padding:10px;text-align:center;">
            <div style="font-size:11px;color:#666;">${b} dias</div>
            <div style="font-size:18px;font-weight:bold;color:${cores[b]};">${fmtMoney(val)}</div>
            <div style="font-size:11px;color:#888;">${docs.length} parcela${docs.length !== 1 ? "s" : ""}</div>
        </div>`;
    }
    html += `</div><div style="font-size:12px;color:#666;">Total em aberto: <b>${fmtMoney(total)}</b></div>`;
    container.innerHTML = html;
}

async function carregarInadimplencia(empresa) {
    const container = document.getElementById("inadimplencia-painel");
    if (!container) return;
    const emp = empresa || document.getElementById("fin-empresa")?.value || "";
    const res = await apiGet(`/api/gestao/financeiro/inadimplencia?empresa_cnpj=${encodeURIComponent(emp)}`);
    if (!res.success) { container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro</div>`; return; }
    const rows = (res.data || {}).inadimplentes || [];
    const fmtMoney = (v) => "R$ " + (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (rows.length === 0) { container.innerHTML = `<div style="padding:15px;color:#888;text-align:center;">Nenhum cliente em inadimplência.</div>`; return; }
    let html = `<div class="table-responsive"><table class="tabelaGrupo" style="width:100%;font-size:11px;"><thead><tr class="linhaTitulo" style="background:#e9ecef;">
        <th style="padding:6px;">Cliente</th><th style="padding:6px;">CNPJ</th><th style="padding:6px;text-align:right;">Total</th>
        <th style="padding:6px;text-align:right;">Vencido</th><th style="padding:6px;text-align:right;">% Vencido</th><th style="padding:6px;text-align:center;">Status</th>
    </tr></thead><tbody>`;
    rows.forEach(r => {
        const cor = r.status === "INADIMPLENTE" ? "#c0392b" : r.status === "ATENÇÃO" ? "#f39c12" : "#27ae60";
        html += `<tr><td><b>${escapeHtml(r.cliente_nome || "")}</b></td><td>${escapeHtml(r.cliente_cnpj || "")}</td>
            <td style="text-align:right;">${fmtMoney(r.total)}</td><td style="text-align:right;color:#c0392b;">${fmtMoney(r.vencido)}</td>
            <td style="text-align:right;">${r.pct_vencido}%</td><td style="text-align:center;"><span class="badge-ambiente" style="background:${cor};font-size:10px;">${r.status}</span></td></tr>`;
    });
    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

async function carregarTendencia() {
    const container = document.getElementById("tendencia-painel");
    if (!container) return;
    const emp = document.getElementById("fin-empresa")?.value || "";
    const res = await apiGet(`/api/gestao/financeiro/tendencia?empresa_cnpj=${encodeURIComponent(emp)}`);
    if (!res.success) { container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro</div>`; return; }
    const data = res.data || {};
    const rows = data.tendencia || [];
    const fmtMoney = (v) => "R$ " + (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const labels = rows.map(r => r.competencia);
    const ctx = document.createElement("canvas");
    ctx.id = "chart-tendencia";
    ctx.style.maxHeight = "320px";
    container.innerHTML = `<div style="overflow-x:auto;"><canvas id="chart-tendencia"></canvas></div>`;
    if (typeof Chart === "undefined") { container.innerHTML += `<div style="padding:10px;color:#888;">Chart.js não carregado.</div>`; return; }
    new Chart(document.getElementById("chart-tendencia"), {
        type: "line",
        data: {
            labels,
            datasets: [
                { label: "Receita Bruta", data: rows.map(r => r.receita_bruta), borderColor: "#2980b9", backgroundColor: "rgba(41,128,185,0.1)", tension: 0.3, fill: true },
                { label: "CPV", data: rows.map(r => r.cpv), borderColor: "#e67e22", backgroundColor: "rgba(230,126,34,0.05)", tension: 0.3, fill: true },
                { label: "Lucro Bruto", data: rows.map(r => r.lucro_bruto), borderColor: "#27ae60", backgroundColor: "rgba(39,174,96,0.05)", tension: 0.3, fill: true },
                { label: "Lucro Líquido", data: rows.map(r => r.lucro_liquido), borderColor: "#8e44ad", backgroundColor: "rgba(142,68,173,0.05)", tension: 0.3, fill: true },
            ]
        },
        options: { responsive: true, plugins: { title: { display: true, text: "Tendência Mensal do DRE" }, legend: { position: "bottom" } }, scales: { y: { ticks: { callback: v => "R$ " + v.toLocaleString("pt-BR", {minimumFractionDigits:0}) } } } }
    });
}

async function exportarFinanceiroCSV() {
    const tab = document.querySelector(".fin-subtab:not([style*='none'])");
    if (!tab) return;
    const id = tab.id;
    if (id === "subtab-fin-pagar") {
        const emp = document.getElementById("fin-empresa")?.value || "";
        window.open(`/api/gestao/financeiro/contas-a-pagar/export?empresa_cnpj=${encodeURIComponent(emp)}`, "_blank");
    } else if (id === "subtab-fin-receber") {
        const emp = document.getElementById("fin-empresa")?.value || "";
        window.open(`/api/gestao/financeiro/contas-a-receber/export?empresa_cnpj=${encodeURIComponent(emp)}`, "_blank");
    } else if (id === "subtab-fin-dre") {
        const emp = document.getElementById("fin-empresa")?.value || "";
        window.open(`/api/gestao/financeiro/dre/export?empresa_cnpj=${encodeURIComponent(emp)}`, "_blank");
    }
}

let ordenarColuna = {};
function ordenarTabela(tabela, coluna) {
    const dir = ordenarColuna[tabela] === "asc" ? "desc" : "asc";
    ordenarColuna[tabela] = dir;
    // Re-renderiza a tabela atual com ordenação (simples: re-carrega)
    if (tabela === "fin-pagar") carregarContasAPagar(document.getElementById("fin-mes")?.value || "", document.getElementById("fin-empresa")?.value || "");
    else if (tabela === "fin-receber") carregarContasAReceber(document.getElementById("fin-mes")?.value || "", document.getElementById("fin-empresa")?.value || "");
}
// ====================================================================

async function handleBuscarConferencia(e) {
    e.preventDefault();
    const chave = (document.getElementById("conf-chave-input")?.value || "").replace(/\D/g, "");
    if (!chave || chave.length < 20) {
        toast.warning("Digite ou bipe uma chave de acesso válida.");
        return;
    }
    carregarConferenciaEstoque(chave);
}

function abrirConferenciaEstoque(chave) {
    showSection("gestao-conferencia");
    if (document.getElementById("conf-chave-input")) {
        document.getElementById("conf-chave-input").value = chave;
    }
    carregarConferenciaEstoque(chave);
}

async function carregarConferenciaEstoque(chave) {
    if (!chave) {
        chave = (document.getElementById("conf-chave-input")?.value || "").replace(/\D/g, "");
    }
    if (!chave) return;

    const container = document.getElementById("conferencia-painel-resultado");
    if (!container) return;

    container.innerHTML = `<div style="padding:20px;text-align:center;color:#666;">Carregando dados da NF-e para conferência...</div>`;

    try {
        const res = await apiGet(`/api/gestao/conferencia/${chave}`);
        if (!res.success) {
            container.innerHTML = `<div class="result error">NF-e não encontrada no banco: ${escapeHtml(res.data?.detail || "")}</div>`;
            return;
        }

        const data = res.data || {};
        const nfe = data.nfe || {};
        const conf = data.conferencia || {};
        const itens = data.itens || [];

        let stBadge = "#2980b9";
        let stTexto = "PENDENTE DE CONFERÊNCIA";
        if (conf.status === "CONFERIDO_OK") { stBadge = "#27ae60"; stTexto = "✓ CONFERIDO 100% OK"; }
        else if (conf.status === "CONFERIDO_DIVERGENCIA") { stBadge = "#c0392b"; stTexto = "⚠️ CONFERIDO COM DIVERGÊNCIAS"; }

        container.innerHTML = `
            <div class="painelSessao">
                <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding-bottom:8px;margin-bottom:10px;">
                    <div>
                        <b style="font-size:14px;">NF-e ${escapeHtml(nfe.numero || "")} - Série ${escapeHtml(nfe.serie || "1")}</b>
                        <div style="font-size:11px;color:#666;">Emitente: <b>${escapeHtml(nfe.emitente_nome || "")}</b> | Destinatário: <b>${escapeHtml(nfe.destinatario_nome || "")}</b></div>
                    </div>
                    <div>
                        <span class="badge-ambiente" style="background:${stBadge};font-size:11px;padding:4px 10px;">${stTexto}</span>
                    </div>
                </div>

                <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;" id="tabela-conferencia-itens">
                    <thead>
                        <tr class="linhaTitulo" style="background:#e9ecef;">
                            <th style="padding:6px;">Produto / Descrição</th>
                            <th style="padding:6px;">Código / EAN</th>
                            <th style="padding:6px;text-align:center;">Qtd NF-e</th>
                            <th style="padding:6px;text-align:center;width:120px;">Qtd Contada</th>
                            <th style="padding:6px;">Seriais / IMEIs Bipados</th>
                            <th style="padding:6px;text-align:center;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${itens.map((it, idx) => `
                            <tr class="conf-item-row" data-codigo="${escapeHtml(it.codigo || '')}" data-desc="${escapeHtml(it.descricao || '')}" data-qtd-nota="${it.qtd_nota}">
                                <td><b>${escapeHtml(it.descricao || "")}</b></td>
                                <td style="font-family:monospace;">${escapeHtml(it.ean || it.codigo || "—")}</td>
                                <td style="text-align:center;font-weight:bold;">${it.qtd_nota} ${escapeHtml(it.unidade || "UN")}</td>
                                <td style="text-align:center;">
                                    <input type="number" class="conf-input-qtd" value="${it.qtd_conferida || it.qtd_nota}" min="0" step="1" style="width:80px;text-align:center;padding:4px;font-weight:bold;" onchange="validarLinhaConferencia(this);">
                                </td>
                                <td>
                                    <input type="text" class="conf-input-seriais" value="${escapeHtml(it.seriais || '')}" placeholder="Bipe seriais/IMEIs separados por vírgula" style="width:95%;padding:3px;font-size:10px;">
                                </td>
                                <td style="text-align:center;" class="conf-status-cell">
                                    <span class="badge-ambiente" style="background:${it.qtd_conferida === it.qtd_nota ? '#27ae60' : '#e67e22'};font-size:10px;">
                                        ${it.qtd_conferida === it.qtd_nota ? 'OK' : 'VERIFICAR'}
                                    </span>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>

                <div style="margin-top:15px;display:flex;justify-content:space-between;align-items:center;background:#f8f9fa;padding:10px;border-radius:4px;">
                    <div style="font-size:12px;">
                        Conferente: <input type="text" id="conf-conferido-por" value="${escapeHtml(conf.conferido_por || 'Almoxarifado')}" style="padding:4px;border:1px solid #ccc;border-radius:3px;">
                    </div>
                    <div style="display:flex;gap:8px;">
                        <button type="button" class="botao" onclick="imprimirEtiquetasChave('${chave}');">🏷️ Imprimir Etiquetas</button>
                        <button type="button" class="botao botao-primario" onclick="salvarConferenciaEstoque('${chave}');" style="background:#27ae60;border-color:#27ae60;padding:6px 16px;">
                            💾 Concluir e Salvar Conferência
                        </button>
                    </div>
                </div>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="result error">Erro: ${escapeHtml(err.message)}</div>`;
    }
}

function validarLinhaConferencia(input) {
    const row = input.closest("tr");
    const qtdNota = parseFloat(row.dataset.qtdNota || 0);
    const qtdContada = parseFloat(input.value || 0);
    const cell = row.querySelector(".conf-status-cell");

    if (cell) {
        if (qtdContada === qtdNota) {
            cell.innerHTML = `<span class="badge-ambiente" style="background:#27ae60;font-size:10px;">OK</span>`;
        } else {
            cell.innerHTML = `<span class="badge-ambiente" style="background:#c0392b;font-size:10px;">DIVERGENTE</span>`;
        }
    }
}

async function salvarConferenciaEstoque(chave) {
    const rows = document.querySelectorAll(".conf-item-row");
    const itens = [];

    rows.forEach(r => {
        const codigo = r.dataset.codigo;
        const desc = r.dataset.desc;
        const qtdNota = parseFloat(r.dataset.qtdNota || 0);
        const qtdConf = parseFloat(r.querySelector(".conf-input-qtd")?.value || 0);
        const seriais = r.querySelector(".conf-input-seriais")?.value || "";

        itens.push({
            codigo: codigo,
            descricao: desc,
            qtd_nota: qtdNota,
            qtd_conferida: qtdConf,
            seriais: seriais,
        });
    });

    const conferente = document.getElementById("conf-conferido-por")?.value || "Operador";

    try {
        const res = await apiPost("/api/gestao/conferencia/salvar", {
            chave: chave,
            conferido_por: conferente,
            itens: itens,
        });

        if (res.success) {
            toast.success("Conferência de estoque salva com sucesso!");
            carregarConferenciaEstoque(chave);
        } else {
            toast.error("Erro ao salvar conferência: " + (res.data?.detail || "Falha"));
        }
    } catch (err) {
        toast.error("Erro: " + err.message);
    }
}


// ====================================================================
// 3. ETIQUETAS DE PREÇO & CÓDIGO DE BARRAS
// ====================================================================

function imprimirEtiquetasChave(chave) {
    const margem = prompt("Informe a margem de lucro sugerida para o preço de venda (%):", "30");
    if (margem === null) return;
    const margemNum = parseFloat(margem) || 30.0;

    const url = `/api/gestao/etiquetas/${chave}?margem=${margemNum}&modelo=pimaco_6180`;
    window.open(url, "_blank");
}


// ====================================================================
// 4. AUDITORIA DE RISCO & IDONEIDADE DOS FORNECEDORES
// ====================================================================

async function carregarAuditoriaFornecedores() {
    const container = document.getElementById("analytics-fornecedores-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Auditando fornecedores cadastrados...</div>`;

    try {
        const emp = document.getElementById("gestao-empresa")?.value || "";
        const res = await apiGet(`/api/gestao/auditoria/fornecedores?empresa_cnpj=${encodeURIComponent(emp)}`);
        if (!res.success) {
            container.innerHTML = `<div class="result error">Erro ao auditar fornecedores: ${escapeHtml(res.data?.detail || "")}</div>`;
            return;
        }

        const fornecedores = res.data || [];
        if (fornecedores.length === 0) {
            container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Nenhum fornecedor registrado no banco.</div>`;
            return;
        }

        container.innerHTML = `
            <div class="table-responsive">
                <table class="tabelaGrupo" style="width:100%;border-collapse:collapse;font-size:11px;">
                    <thead>
                        <tr class="linhaTitulo" style="background:#e9ecef;">
                            <th style="padding:6px;">Score Conformidade</th>
                            <th style="padding:6px;">CNPJ Fornecedor</th>
                            <th style="padding:6px;">Razão Social</th>
                            <th style="padding:6px;text-align:center;">UF</th>
                            <th style="padding:6px;text-align:center;">Qtd NF-e</th>
                            <th style="padding:6px;text-align:right;">Volume Total Comprado</th>
                            <th style="padding:6px;">Situação Cadastral</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${fornecedores.map(f => {
                            let corScore = "#27ae60";
                            if (f.score_conformidade < 70) corScore = "#e67e22";
                            if (f.score_conformidade < 50) corScore = "#c0392b";

                            return `
                                <tr>
                                    <td>
                                        <div style="display:flex;align-items:center;gap:6px;">
                                            <b style="color:${corScore};font-size:12px;">${f.score_conformidade}/100</b>
                                            <span class="badge-ambiente" style="background:${corScore};font-size:9px;">${f.nivel_risco} RISCO</span>
                                        </div>
                                    </td>
                                    <td style="font-family:monospace;font-size:10px;"><b>${escapeHtml(f.cnpj)}</b></td>
                                    <td><b>${escapeHtml(f.razao_social || "")}</b></td>
                                    <td style="text-align:center;">${escapeHtml(f.uf)}</td>
                                    <td style="text-align:center;"><b>${f.qtd_notas}</b></td>
                                    <td style="text-align:right;font-weight:bold;color:#2c3e50;">R$ ${f.volume_total.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                    <td><span class="badge-ambiente" style="background:#27ae60;font-size:10px;">${escapeHtml(f.status_sefaz)}</span></td>
                                </tr>
                            `;
                        }).join("")}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="result error">Erro: ${escapeHtml(err.message)}</div>`;
    }
}


// ====================================================================
// 5. CENTRAL PROFISSIONAL DE EMISSÃO DE NF-e & GESTÃO DE SAÍDAS
// ====================================================================

if (!AppState.emissaoItens) AppState.emissaoItens = [];
if (!AppState.clientesCad) AppState.clientesCad = [];
if (!AppState.produtosCad) AppState.produtosCad = [];
if (!AppState.saidasNfe) AppState.saidasNfe = [];

function switchEmissaoTab(tabName) {
    const tabs = ["form", "saidas", "clientes", "produtos"];
    tabs.forEach(t => {
        const btn = document.getElementById(`btn-tab-emissao-${t}`);
        const pane = document.getElementById(`subtab-emissao-${t}`);
        if (btn) btn.classList.toggle("active", t === tabName);
        if (pane) pane.style.display = t === tabName ? "block" : "none";
    });

    if (tabName === "saidas") {
        carregarNfeSaidas(1);
        popularSelectEmpresasSaidas();
    }
    if (tabName === "clientes") carregarTabelaCadClientes();
    if (tabName === "produtos") carregarTabelaCadProdutos();
    if (tabName === "form") {
        carregarSelectClientesEmissao();
        carregarSelectProdutosEmissao();
        atualizarProximoNumeroNfe();
    }
}

async function carregarEmissorRapido() {
    await popularEmpresasEmissao();
    await carregarSelectClientesEmissao();
    await carregarSelectProdutosEmissao();
    await atualizarProximoNumeroNfe();
    renderizarTabelaItensEmissao();
    verificarStatusSefazRealtime(false);
}

async function popularEmpresasEmissao() {
    const selEmit = document.getElementById("emissao-empresa-emit");
    const selFiltro = document.getElementById("filtro-saidas-empresa");
    if (!selEmit) return;

    try {
        const res = await apiGet("/api/certificado/list");
        if (res.success && res.data) {
            AppState.certificados = res.data;
            const opts = res.data.map(c => {
                const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                const ieText = c.ie ? ` - IE: ${c.ie}` : "";
                return `<option value="${c.cnpj}">${escapeHtml(cnpjFmt)} - ${escapeHtml(c.razao_social)}${ieText}</option>`;
            }).join("");
            selEmit.innerHTML = opts;
            if (selFiltro) {
                selFiltro.innerHTML = `<option value="">🏢 Todas as 5 Empresas Emitentes</option>` + opts;
            }
            atualizarCardEmitenteInfo();
        }
    } catch (err) {
        console.warn("Erro ao popular empresas emitentes:", err);
    }
}

async function atualizarProximoNumeroNfe() {
    const emitCnpj = document.getElementById("emissao-empresa-emit")?.value || "";
    const serie = document.getElementById("emissao-serie")?.value || "1";
    const inputNum = document.getElementById("emissao-numero");
    if (!emitCnpj || !inputNum) return;

    try {
        const res = await apiGet(`/api/emissao/proximo-numero?empresa_cnpj=${encodeURIComponent(emitCnpj)}&serie=${encodeURIComponent(serie)}`);
        if (res.success && res.proximo_numero) {
            inputNum.value = res.proximo_numero;
        }
    } catch (err) {
        console.warn("Erro ao consultar próximo número:", err);
    }
}

function atualizarCardEmitenteInfo() {
    const card = document.getElementById("card-emitente-fiscal-info");
    const emitCnpj = document.getElementById("emissao-empresa-emit")?.value;
    if (!card) return;

    if (!emitCnpj) {
        card.style.display = "none";
        card.innerHTML = "";
        return;
    }

    const cert = (AppState.certificados || []).find(c => c.cnpj === emitCnpj);
    if (!cert) {
        card.style.display = "none";
        return;
    }

    const cnpjFmt = (cert.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
    const ieFmt = cert.ie ? cert.ie.replace(/^(\d{3})(\d{3})(\d{3})(\d{3})$/, "$1.$2.$3.$4") : (cert.ie || "535.758.386.119");
    const endFmt = `${cert.logradouro || 'Rua Dom Pedro II'}, ${cert.numero || '857'}${cert.bairro ? ' - ' + cert.bairro : ''} - ${cert.municipio || 'Piracicaba'}/${cert.uf || 'SP'}${cert.cep ? ' (CEP: ' + cert.cep.replace(/^(\d{5})(\d{3})$/, "$1-$2") + ')' : ''}`;

    card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
                <div><b>🏢 Razão Social:</b> <span style="font-weight:600;color:var(--primary);">${escapeHtml(cert.razao_social || 'FILIAL')}</span></div>
                <div><b>🔢 CNPJ:</b> <code>${escapeHtml(cnpjFmt)}</code></div>
                <div class="card-ie-badge" style="background:var(--pastel-blue-bg);color:var(--pastel-blue-text);padding:2px 8px;border-radius:4px;border:1px solid var(--pastel-blue-border);display:flex;align-items:center;gap:4px;">
                    <span>🏛️ <b>Inscrição Estadual (IE):</b></span>
                    <code style="font-weight:bold;font-size:12px;color:var(--primary);background:var(--bg-surface);padding:1px 5px;border-radius:3px;border:1px solid var(--border-main);">${escapeHtml(ieFmt)}</code>
                    <span style="font-size:10px;background:var(--primary);color:#fff;padding:1px 4px;border-radius:3px;">Obrigatório SEFAZ</span>
                </div>
                <div><b>⚖️ Regime Tributário:</b> <span class="badge-status-autorizada" style="padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">CRT 1 - Simples Nacional</span></div>
            </div>
            <div style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;gap:6px;">
                <span>📍 <b>Endereço Fiscal:</b> ${escapeHtml(endFmt)}</span>
            </div>
        </div>
    `;
    card.style.display = "block";

}

let debounceClienteTimeout = null;

async function carregarSelectClientesEmissao() {
    const sel = document.getElementById("emissao-select-cliente-rapido");
    try {
        const res = await apiGet("/api/emissao/clientes");
        const lista = (res.data?.clientes || res.clientes || []);
        AppState.clientesCad = lista;
        if (sel) {
            sel.innerHTML = `<option value="">-- Ou Selecionar Salvo (${lista.length}) --</option>` +
                lista.slice(0, 100).map(c => `
                    <option value="${c.cpf_cnpj}">${escapeHtml(c.razao_social)} (${c.tipo_pessoa || (c.cpf_cnpj.length === 11 ? 'PF' : 'PJ')}: ${c.cpf_cnpj})</option>
                `).join("");
        }
    } catch (err) {
        console.warn("Erro ao carregar lista de clientes:", err);
    }
}

async function filtrarClientesEmissao(termo) {
    const dropdown = document.getElementById("emissao-dropdown-clientes");
    if (!dropdown) return;
    
    const t = String(termo || "").trim();
    const tLower = t.toLowerCase();
    const digits = t.replace(/\D/g, "");
    
    let resultados = (AppState.clientesCad || []).filter(c => {
        if (!t) return true;
        const nome = (c.razao_social || "").toLowerCase();
        const fan = (c.nome_fantasia || "").toLowerCase();
        const email = (c.email || "").toLowerCase();
        const doc = (c.cpf_cnpj || "").replace(/\D/g, "");
        const tel = (c.telefone || "").replace(/\D/g, "");
        
        return nome.includes(tLower) || 
               fan.includes(tLower) || 
               email.includes(tLower) || 
               (digits && doc.includes(digits)) || 
               (digits && tel.includes(digits));
    });

    if (t.length >= 2 && resultados.length < 5) {
        clearTimeout(debounceClienteTimeout);
        debounceClienteTimeout = setTimeout(async () => {
            try {
                const res = await apiGet(`/api/emissao/clientes?busca=${encodeURIComponent(t)}`);
                const remotos = res.data?.clientes || res.clientes || [];
                if (remotos.length > 0) {
                    renderDropdownClientes(remotos);
                }
            } catch (e) {
                console.warn("Erro busca remota clientes:", e);
            }
        }, 250);
    }

    renderDropdownClientes(resultados.slice(0, 30));
}

function renderDropdownClientes(lista) {
    const dropdown = document.getElementById("emissao-dropdown-clientes");
    if (!dropdown) return;

    if (!lista || lista.length === 0) {
        dropdown.innerHTML = `<div style="padding:10px 12px;font-size:11px;color:#64748b;text-align:center;">Nenhum cliente encontrado pelo termo informado.</div>`;
        dropdown.style.display = "block";
        return;
    }

    dropdown.innerHTML = lista.map(c => {
        const docFmt = c.cpf_cnpj ? (c.cpf_cnpj.length === 11 ? c.cpf_cnpj.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4") : c.cpf_cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5")) : "—";
        const emailTel = [c.email, c.telefone].filter(Boolean).join(" • ");
        const loc = [c.municipio, c.uf].filter(Boolean).join(" / ");
        
        return `
            <div class="dropdown-cliente-item" onclick="selecionarClientePreCadastrado('${c.cpf_cnpj}');" style="padding:7px 10px;border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background 0.15s ease;">
                <div style="font-size:11.5px;font-weight:600;color:var(--text-main);">${escapeHtml(c.razao_social || "Sem Nome")}</div>
                <div style="font-size:10px;color:var(--text-muted);display:flex;justify-content:space-between;gap:8px;margin-top:2px;">
                    <span>📄 <b>${escapeHtml(docFmt)}</b> ${emailTel ? `| 📞 ${escapeHtml(emailTel)}` : ""}</span>
                    <span>${escapeHtml(loc)}</span>
                </div>
            </div>
        `;
    }).join("");
    dropdown.style.display = "block";
}

document.addEventListener("click", function(e) {
    const dropdown = document.getElementById("emissao-dropdown-clientes");
    const input = document.getElementById("emissao-busca-cliente");
    if (dropdown && dropdown.style.display === "block") {
        if (!dropdown.contains(e.target) && e.target !== input) {
            dropdown.style.display = "none";
        }
    }
});

function selecionarClientePreCadastrado(doc) {
    if (!doc) return;
    const cleanDoc = String(doc).replace(/\D/g, "");
    const cli = (AppState.clientesCad || []).find(c => String(c.cpf_cnpj).replace(/\D/g, "") === cleanDoc);
    if (!cli) return;

    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ""; };

    setVal("emissao-dest-cpf-cnpj", cli.cpf_cnpj);
    setVal("emissao-dest-nome", cli.razao_social);
    setVal("emissao-dest-ind-ie", cli.indicador_ie !== undefined ? cli.indicador_ie : 9);
    setVal("emissao-dest-ie", cli.ie || "");
    setVal("emissao-dest-cep", cli.cep || "");
    setVal("emissao-dest-logradouro", cli.logradouro || "");
    setVal("emissao-dest-numero", cli.numero || "");
    setVal("emissao-dest-bairro", cli.bairro || "");
    setVal("emissao-dest-municipio", cli.municipio || "");
    setVal("emissao-dest-uf", cli.uf || "SP");
    setVal("emissao-dest-email", cli.email || "");
    setVal("emissao-dest-telefone", cli.telefone || "");

    const inputBusca = document.getElementById("emissao-busca-cliente");
    if (inputBusca) inputBusca.value = cli.razao_social;
    const dropdown = document.getElementById("emissao-dropdown-clientes");
    if (dropdown) dropdown.style.display = "none";
    const select = document.getElementById("emissao-select-cliente-rapido");
    if (select) select.value = cli.cpf_cnpj;

    sugerirCfopPorNatureza();
}

async function buscarDadosCnpjCliente(doc, isModal = false) {
    const clean = String(doc || "").replace(/\D/g, "");
    if (clean.length !== 14) return;

    try {
        const resp = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${clean}`);
        if (!resp.ok) return;
        const data = await resp.json();

        const prefix = isModal ? "modal-cli-" : "emissao-dest-";
        const setVal = (suffix, val) => {
            const el = document.getElementById(prefix + suffix);
            if (el && val && !el.value) el.value = val;
        };

        const nomeEl = document.getElementById(prefix + "nome");
        if (nomeEl && (!nomeEl.value || isModal)) nomeEl.value = data.razao_social || data.nome_fantasia || "";

        if (isModal) {
            const fanEl = document.getElementById("modal-cli-fantasia");
            if (fanEl && !fanEl.value) fanEl.value = data.nome_fantasia || "";
        }

        setVal("cep", data.cep ? data.cep.replace(/\D/g, "") : "");
        setVal(isModal ? "logr" : "logradouro", data.logradouro);
        setVal(isModal ? "num" : "numero", data.numero);
        setVal("bairro", data.bairro);
        setVal(isModal ? "mun" : "municipio", data.municipio);
        setVal("uf", data.uf);
        setVal("email", data.email);
        setVal(isModal ? "tel" : "telefone", data.ddd_telefone_1 || data.telefone);

        if (!isModal) sugerirCfopPorNatureza();
    } catch (err) {
        console.warn("Consulta CNPJ automática:", err);
    }
}

function identificarTipoPessoaDest() {
    const doc = (document.getElementById("emissao-dest-cpf-cnpj")?.value || "").replace(/\D/g, "");
    const indIe = document.getElementById("emissao-dest-ind-ie");
    if (!indIe) return;
    if (doc.length === 11) {
        indIe.value = "9"; // Não contribuinte
    } else if (doc.length === 14) {
        if (indIe.value === "9") indIe.value = "1"; // Contribuinte
        buscarDadosCnpjCliente(doc, false);
    }
}

async function buscarCepViaCep(cep, isModal = false) {
    const clean = String(cep || "").replace(/\D/g, "");
    if (clean.length !== 8) return;

    try {
        const resp = await fetch(`https://viacep.com.br/ws/${clean}/json/`);
        const data = await resp.json();
        if (data.erro) {
            toast.error("CEP não encontrado nos Correios.");
            return;
        }

        const prefix = isModal ? "modal-cli-" : "emissao-dest-";
        const setVal = (suffix, val) => {
            const el = document.getElementById(prefix + suffix);
            if (el && val) el.value = val;
        };

        setVal(isModal ? "logr" : "logradouro", data.logradouro);
        setVal("bairro", data.bairro);
        setVal(isModal ? "mun" : "municipio", data.localidade);
        setVal("uf", data.uf);

        const numEl = document.getElementById(prefix + (isModal ? "num" : "numero"));
        if (numEl) numEl.focus();

        if (!isModal) sugerirCfopPorNatureza();
    } catch (err) {
        console.warn("Erro ao buscar ViaCEP:", err);
    }
}

let debounceProdutoTimeout = null;

async function carregarSelectProdutosEmissao() {
    const sel = document.getElementById("emissao-select-prod-rapido");
    try {
        const res = await apiGet("/api/emissao/produtos");
        const lista = (res.data?.produtos || res.produtos || []);
        AppState.produtosCad = lista;
        if (sel) {
            sel.innerHTML = `<option value="">-- Ou Selecionar Salvo (${lista.length}) --</option>` +
                lista.slice(0, 100).map(p => `
                    <option value="${p.codigo}">[${p.codigo}] ${escapeHtml(p.descricao)} - R$ ${parseFloat(p.preco_venda || 0).toFixed(2)}</option>
                `).join("");
        }
    } catch (err) {
        console.warn("Erro ao carregar catálogo de produtos:", err);
    }
}

async function filtrarProdutosEmissao(termo) {
    const dropdown = document.getElementById("emissao-dropdown-produtos");
    if (!dropdown) return;
    
    const t = String(termo || "").trim();
    const tLower = t.toLowerCase();
    
    let resultados = (AppState.produtosCad || []).filter(p => {
        if (!t) return true;
        const desc = (p.descricao || "").toLowerCase();
        const cod = (p.codigo || "").toLowerCase();
        const ncm = (p.ncm || "").toLowerCase();
        const gtin = (p.gtin || "").toLowerCase();
        
        return desc.includes(tLower) || 
               cod.includes(tLower) || 
               ncm.includes(tLower) || 
               gtin.includes(tLower);
    });

    if (t.length >= 2 && resultados.length < 5) {
        clearTimeout(debounceProdutoTimeout);
        debounceProdutoTimeout = setTimeout(async () => {
            try {
                const res = await apiGet(`/api/emissao/produtos?busca=${encodeURIComponent(t)}`);
                const remotos = res.data?.produtos || res.produtos || [];
                if (remotos.length > 0) {
                    renderDropdownProdutos(remotos);
                }
            } catch (e) {
                console.warn("Erro busca remota produtos:", e);
            }
        }, 200);
    }

    renderDropdownProdutos(resultados.slice(0, 50));
}

function renderDropdownProdutos(lista) {
    const dropdown = document.getElementById("emissao-dropdown-produtos");
    if (!dropdown) return;

    if (!lista || lista.length === 0) {
        dropdown.innerHTML = `<div style="padding:10px 12px;font-size:11px;color:#64748b;text-align:center;">Nenhum produto encontrado pelo termo informado.</div>`;
        dropdown.style.display = "block";
        return;
    }

    dropdown.innerHTML = lista.map(p => {
        const precoFmt = parseFloat(p.preco_venda || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return `
            <div class="dropdown-cliente-item" onclick="selecionarProdutoCatalogo('${p.codigo}');" style="padding:7px 10px;border-bottom:1px solid #f1f5f9;cursor:pointer;transition:background 0.15s ease;">
                <div style="font-size:11.5px;font-weight:600;color:var(--text-main);">${escapeHtml(p.descricao || "Sem Descrição")}</div>
                <div style="font-size:10px;color:var(--text-muted);display:flex;justify-content:space-between;gap:8px;margin-top:2px;">
                    <span>🏷️ Cód: <b>${escapeHtml(p.codigo)}</b> | NCM: <b>${escapeHtml(p.ncm || "—")}</b> | UN: ${escapeHtml(p.unidade || "UN")}</span>
                    <span style="font-weight:bold;color:#27ae60;">R$ ${precoFmt}</span>
                </div>
            </div>
        `;
    }).join("");
    dropdown.style.display = "block";
}

document.addEventListener("click", function(e) {
    const dropdownProd = document.getElementById("emissao-dropdown-produtos");
    const inputProd = document.getElementById("emissao-busca-produto");
    if (dropdownProd && dropdownProd.style.display === "block") {
        if (!dropdownProd.contains(e.target) && e.target !== inputProd) {
            dropdownProd.style.display = "none";
        }
    }
});

function selecionarProdutoCatalogo(codigo) {
    if (!codigo) return;
    const prod = (AppState.produtosCad || []).find(p => p.codigo === codigo);
    if (!prod) return;

    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val !== undefined ? val : ""; };

    setVal("item-add-codigo", prod.codigo);
    setVal("item-add-descricao", prod.descricao);
    setVal("item-add-ncm", prod.ncm);
    setVal("item-add-cfop", prod.cfop_padrao || "5102");
    setVal("item-add-unidade", prod.unidade || "UN");
    setVal("item-add-qtd", 1);
    setVal("item-add-preco", parseFloat(prod.preco_venda || 0).toFixed(2));
    setVal("item-add-desconto", "0.00");

    const inputBusca = document.getElementById("emissao-busca-produto");
    if (inputBusca) inputBusca.value = prod.descricao;
    const dropdown = document.getElementById("emissao-dropdown-produtos");
    if (dropdown) dropdown.style.display = "none";
    const select = document.getElementById("emissao-select-prod-rapido");
    if (select) select.value = prod.codigo;

    sugerirCfopPorNatureza();
    calcularTotalItemTemp();
}

function calcularTotalItemTemp() {
    const qtd = parseFloat(document.getElementById("item-add-qtd")?.value || 0);
    const preco = parseFloat(document.getElementById("item-add-preco")?.value || 0);
    const desc = parseFloat(document.getElementById("item-add-desconto")?.value || 0);
    const tot = Math.max(0, (qtd * preco) - desc);

    const display = document.getElementById("item-add-total-display");
    if (display) {
        display.value = `R$ ${tot.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
}

function sugerirCfopPorNatureza() {
    const nat = (document.getElementById("emissao-natureza-op")?.value || "").toUpperCase();
    const destUf = (document.getElementById("emissao-dest-uf")?.value || "SP").toUpperCase();
    const isInterestadual = destUf !== "SP";

    let cfop = isInterestadual ? "6102" : "5102";
    if (nat.includes("DEVOLUCAO")) {
        cfop = isInterestadual ? "6202" : "5202";
    } else if (nat.includes("TRANSFERENCIA") || nat.includes("REMESSA")) {
        cfop = isInterestadual ? "6949" : "5949";
    }

    const cfopInput = document.getElementById("item-add-cfop");
    if (cfopInput) cfopInput.value = cfop;
}

function adicionarItemNfeEmissao() {
    const cod = (document.getElementById("item-add-codigo")?.value || "").trim().toUpperCase();
    const desc = (document.getElementById("item-add-descricao")?.value || "").trim().toUpperCase();
    const imei = (document.getElementById("item-add-imei")?.value || "").trim().toUpperCase();
    const ncm = (document.getElementById("item-add-ncm")?.value || "").replace(/\D/g, "");
    const cfop = (document.getElementById("item-add-cfop")?.value || "").replace(/\D/g, "");
    const un = (document.getElementById("item-add-unidade")?.value || "UN").trim().toUpperCase();
    const qtd = parseFloat(document.getElementById("item-add-qtd")?.value || 0);
    const preco = parseFloat(document.getElementById("item-add-preco")?.value || 0);
    const descVal = parseFloat(document.getElementById("item-add-desconto")?.value || 0);

    if (!desc) {
        toast.warning("Por favor, preencha a descrição do produto.");
        return;
    }
    if (qtd <= 0) {
        toast.warning("A quantidade deve ser maior que zero.");
        return;
    }
    if (preco <= 0) {
        toast.warning("O valor unitário deve ser maior que zero.");
        return;
    }

    const tot = Math.max(0, (qtd * preco) - descVal);

    AppState.emissaoItens.push({
        codigo: cod || `PROD${AppState.emissaoItens.length + 1}`,
        descricao: desc,
        imei: imei,
        ncm: ncm || "85171300",
        cfop: cfop || "5102",
        unidade: un,
        quantidade: qtd,
        valor_unitario: preco,
        desconto: descVal,
        valor_total: tot,
    });

    // Limpa campos temporários
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setVal("item-add-codigo", "");
    setVal("item-add-descricao", "");
    setVal("item-add-imei", "");
    setVal("item-add-qtd", "1");
    setVal("item-add-preco", "");
    setVal("item-add-desconto", "0.00");
    setVal("item-add-total-display", "R$ 0,00");
    const selProd = document.getElementById("emissao-select-prod-rapido");
    if (selProd) selProd.value = "";

    renderizarTabelaItensEmissao();
}

function removerItemNfeEmissao(index) {
    AppState.emissaoItens.splice(index, 1);
    renderizarTabelaItensEmissao();
}

function renderizarTabelaItensEmissao() {
    const tbody = document.getElementById("tbody-itens-emissao");
    if (!tbody) return;

    if (!AppState.emissaoItens || AppState.emissaoItens.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align:center;padding:20px;color:#888;">
                    Nenhum produto adicionado à nota fiscal ainda. Preencha os campos acima e clique em <b>➕ Adicionar à Nota</b>.
                </td>
            </tr>
        `;
        atualizarTotaisNfeEmissao();
        return;
    }

    tbody.innerHTML = AppState.emissaoItens.map((item, idx) => `
        <tr class="linha">
            <td style="text-align:center;"><b>${idx + 1}</b></td>
            <td><code>${escapeHtml(item.codigo)}</code></td>
            <td>
                <b>${escapeHtml(item.descricao)}</b>
                ${item.imei ? `<br><small style="color:#0284c7;font-weight:600;background:#f0f9ff;padding:1px 5px;border-radius:3px;border:1px solid #bae6fd;">📱 IMEI/Série: ${escapeHtml(item.imei)}</small>` : ''}
            </td>
            <td style="text-align:center;">${escapeHtml(item.ncm)}</td>
            <td style="text-align:center;">${escapeHtml(item.cfop)}</td>
            <td style="text-align:center;">${escapeHtml(item.unidade)}</td>
            <td style="text-align:right;">${item.quantidade.toLocaleString("pt-BR")}</td>
            <td style="text-align:right;">R$ ${item.valor_unitario.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td style="text-align:right;color:#c0392b;">R$ ${item.desconto.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td style="text-align:right;font-weight:bold;color:#27ae60;">R$ ${item.valor_total.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td style="text-align:center;">
                <button type="button" class="btn-action" onclick="removerItemNfeEmissao(${idx});" title="Remover item" style="color:#c0392b;padding:2px 6px;">✕</button>
            </td>
        </tr>
    `).join("");

    atualizarTotaisNfeEmissao();
}

function toggleTransporteFields(modalidade) {
    const box = document.getElementById("container-campos-transporte");
    if (box) box.style.display = (modalidade !== "9") ? "block" : "none";
}

function toggleCondicaoPagamento(cond) {
    const box = document.getElementById("container-parcelas-prazo");
    if (box) {
        box.style.display = (cond === "a_prazo") ? "block" : "none";
        if (cond === "a_prazo") gerarParcelasNfe();
    }
}

function gerarParcelasNfe() {
    const container = document.getElementById("lista-parcelas-dinamicas");
    if (!container) return;

    let subtotal = 0;
    let totalDesc = 0;
    (AppState.emissaoItens || []).forEach(it => {
        subtotal += (it.quantidade * it.valor_unitario);
        totalDesc += it.desconto;
    });
    const vFrete = parseFloat(document.getElementById("emissao-transp-valor-frete")?.value || 0);
    const vOutras = parseFloat(document.getElementById("emissao-transp-outras-desp")?.value || 0);
    const totalFinal = Math.max(0, subtotal - totalDesc + vFrete + vOutras);

    const qtdParc = parseInt(document.getElementById("emissao-qtd-parcelas")?.value || 2);
    const intervalo = parseInt(document.getElementById("emissao-intervalo-dias")?.value || 30);

    const vParc = (totalFinal / qtdParc);
    const hoje = new Date();

    let html = "";
    for (let i = 1; i <= qtdParc; i++) {
        const dt = new Date();
        dt.setDate(hoje.getDate() + (i * intervalo));
        const dtStr = dt.toISOString().split("T")[0];
        const numDup = String(i).padStart(3, "0");

        html += `
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;font-size:12px;">
                <span style="width:70px;font-weight:bold;color:#1b4f72;">Parc. ${i}/${qtdParc}:</span>
                <input type="text" class="parc-num" value="${numDup}" readonly style="width:50px;text-align:center;font-size:11px;background:#f1f5f9;">
                <input type="date" class="parc-venc" value="${dtStr}" style="font-size:11px;padding:3px;">
                <input type="number" class="parc-valor" value="${vParc.toFixed(2)}" step="0.01" style="width:90px;text-align:right;font-size:11px;font-weight:bold;">
            </div>
        `;
    }
    container.innerHTML = html;
}

function atualizarTotaisNfeEmissao() {
    let subtotal = 0;
    let totalDesc = 0;
    let totalIbpt = 0;

    (AppState.emissaoItens || []).forEach(it => {
        const itemTot = (it.quantidade * it.valor_unitario) - it.desconto;
        subtotal += (it.quantidade * it.valor_unitario);
        totalDesc += it.desconto;
        // IBPT Estimativa média ~31.45%
        totalIbpt += (itemTot * 0.3145);
    });

    const vFrete = parseFloat(document.getElementById("emissao-transp-valor-frete")?.value || 0);
    const vOutras = parseFloat(document.getElementById("emissao-transp-outras-desp")?.value || 0);
    const totalFinal = Math.max(0, subtotal - totalDesc + vFrete + vOutras);

    const fmt = (val) => `R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const elSub = document.getElementById("tot-display-produtos");
    const elDesc = document.getElementById("tot-display-desconto");
    const elFrete = document.getElementById("tot-display-frete");
    const elIbpt = document.getElementById("tot-display-ibpt");
    const elFin = document.getElementById("tot-display-final");

    if (elSub) elSub.textContent = fmt(subtotal);
    if (elDesc) elDesc.textContent = `- ${fmt(totalDesc)}`;
    if (elFrete) elFrete.textContent = fmt(vFrete + vOutras);
    if (elIbpt) elIbpt.textContent = fmt(totalIbpt);
    if (elFin) elFin.textContent = fmt(totalFinal);

    if (document.getElementById("emissao-condicao-pagamento")?.value === "a_prazo") {
        gerarParcelasNfe();
    }
}

function toggleNfeReferenciada() {
    const box = document.getElementById("container-nfe-referenciada");
    if (!box) return;
    const isHidden = (box.style.display === "none" || !box.style.display);
    box.style.display = isHidden ? "block" : "none";
    if (isHidden) {
        document.getElementById("emissao-chave-referenciada")?.focus();
    }
}

function handleMudancaFinalidade(val) {
    const box = document.getElementById("container-nfe-referenciada");
    const badge = document.getElementById("badge-chave-ref-obrigatoria");
    const inputRef = document.getElementById("emissao-chave-referenciada");

    if (val === "4" || val === "2" || val === "3") {
        if (box) box.style.display = "block";
        if (badge) badge.style.display = "inline";
        if (inputRef) {
            inputRef.classList.remove("input-opcional");
            inputRef.classList.add("input-obrigatorio");
        }
        if (val === "4") {
            const natSelect = document.getElementById("emissao-natureza-op");
            if (natSelect) natSelect.value = "DEVOLUCAO DE COMPRA PARA COMERCIALIZACAO";
            sugerirCfopPorNatureza();
        }
    } else {
        if (badge) badge.style.display = "none";
        if (inputRef) {
            inputRef.classList.remove("input-obrigatorio");
            inputRef.classList.add("input-opcional");
        }
    }
}

function montarPayloadEmissao() {
    const emitCnpj = document.getElementById("emissao-empresa-emit")?.value || "";
    const natOp = document.getElementById("emissao-natureza-op")?.value || "VENDA DE MERCADORIA";
    const serie = document.getElementById("emissao-serie")?.value || "1";
    const numero = document.getElementById("emissao-numero")?.value || "";
    const finalidade = parseInt(document.getElementById("emissao-finalidade")?.value || 1);
    const indPres = parseInt(document.getElementById("emissao-ind-pres")?.value || 1);
    const indFinal = parseInt(document.getElementById("emissao-ind-final")?.value || 1);
    const chaveRef = (document.getElementById("emissao-chave-referenciada")?.value || "").replace(/\D/g, "");

    const destDoc = (document.getElementById("emissao-dest-cpf-cnpj")?.value || "").replace(/\D/g, "");
    const destNome = (document.getElementById("emissao-dest-nome")?.value || "").trim().toUpperCase();
    const destIndIe = parseInt(document.getElementById("emissao-dest-ind-ie")?.value || (destDoc.length === 11 ? 9 : 1));
    const destIe = document.getElementById("emissao-dest-ie")?.value || "";
    const destCep = (document.getElementById("emissao-dest-cep")?.value || "").replace(/\D/g, "");
    const destLogr = document.getElementById("emissao-dest-logradouro")?.value || "";
    const destNum = document.getElementById("emissao-dest-numero")?.value || "";
    const destBairro = document.getElementById("emissao-dest-bairro")?.value || "";
    const destMun = document.getElementById("emissao-dest-municipio")?.value || "";
    const destUf = (document.getElementById("emissao-dest-uf")?.value || "SP").toUpperCase();
    const destEmail = document.getElementById("emissao-dest-email")?.value || "";
    const destTel = document.getElementById("emissao-dest-telefone")?.value || "";
    const salvarCli = document.getElementById("emissao-dest-salvar")?.checked !== false;

    // Transporte
    const modFrete = document.getElementById("emissao-transp-modalidade")?.value || "9";
    const vFrete = parseFloat(document.getElementById("emissao-transp-valor-frete")?.value || 0);
    const vOutras = parseFloat(document.getElementById("emissao-transp-outras-desp")?.value || 0);
    const transpDoc = (document.getElementById("emissao-transp-doc")?.value || "").replace(/\D/g, "");
    const transpNome = (document.getElementById("emissao-transp-nome")?.value || "").trim().toUpperCase();
    const transpIe = document.getElementById("emissao-transp-ie")?.value || "";
    const transpPlaca = (document.getElementById("emissao-transp-placa")?.value || "").trim().toUpperCase();
    const transpUf = (document.getElementById("emissao-transp-uf-veiculo")?.value || "SP").toUpperCase();
    const volQtd = parseInt(document.getElementById("emissao-vol-qtd")?.value || 1);
    const volEsp = (document.getElementById("emissao-vol-especie")?.value || "VOLUMES").toUpperCase();
    const volMarca = (document.getElementById("emissao-vol-marca")?.value || "").toUpperCase();
    const volPesoLiq = parseFloat(document.getElementById("emissao-vol-peso-liq")?.value || 0);
    const volPesoBruto = parseFloat(document.getElementById("emissao-vol-peso-bruto")?.value || 0);

    // Condição de Pagamento e Parcelas
    const condPag = document.getElementById("emissao-condicao-pagamento")?.value || "a_vista";
    const formaPag = document.getElementById("emissao-forma-pagamento")?.value || "17";
    const infoCompl = document.getElementById("emissao-info-compl")?.value || "";

    const parcelas = [];
    if (condPag === "a_prazo") {
        const nums = document.querySelectorAll(".parc-num");
        const vencs = document.querySelectorAll(".parc-venc");
        const vals = document.querySelectorAll(".parc-valor");
        for (let i = 0; i < nums.length; i++) {
            parcelas.push({
                numero: nums[i].value,
                vencimento: vencs[i].value,
                valor: parseFloat(vals[i].value || 0),
            });
        }
    }

    const homolog = AppState.ambiente === "homologacao";
    return {
        emitente_cnpj: emitCnpj,
        natureza_operacao: natOp,
        serie: serie,
        numero: numero ? parseInt(numero) : null,
        data_saida: document.getElementById("emissao-data-saida")?.value || null,
        finalidade: finalidade,
        indicador_presencial: indPres,
        consumidor_final: indFinal,
        chave_referenciada: chaveRef,
        destinatario: {
            cpf_cnpj: destDoc,
            razao_social: destNome,
            indicador_ie: destIndIe,
            ie: destIe,
            cep: destCep,
            logradouro: destLogr,
            numero: destNum,
            bairro: destBairro,
            municipio: destMun,
            uf: destUf,
            email: destEmail,
            telefone: destTel,
        },
        salvar_cliente: salvarCli,
        produtos: AppState.emissaoItens,
        valor_frete: vFrete,
        outras_despesas: vOutras,
        transporte: {
            modalidade_frete: modFrete,
            transportadora_cnpj_cpf: transpDoc,
            transportadora_nome: transpNome,
            transportadora_ie: transpIe,
            placa_veiculo: transpPlaca,
            uf_veiculo: transpUf,
            volumes_qtd: volQtd,
            volumes_especie: volEsp,
            volumes_marca: volMarca,
            peso_liquido: volPesoLiq,
            peso_bruto: volPesoBruto,
        },
        condicao_pagamento: condPag,
        parcelas: parcelas,
        forma_pagamento: formaPag,
        informacoes_complementares: infoCompl,
        homologacao: homolog,
        uf: AppState.uf,
    };
}

function fecharModalPreviaNfe() {
    const modal = document.getElementById("modal-previa-nfe-emissao");
    if (modal) modal.style.display = "none";
}

document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        fecharModalPreviaNfe();
    }
});

function transmitirNfeDiretoDoModalPrevia() {
    const payload = montarPayloadEmissao();
    abrirModalConfirmacaoTransmissao(payload);
}

function imprimirDanfePreviaModal() {
    const conteudo = document.getElementById("modal-previa-danfe-conteudo");
    if (!conteudo) return;

    const printWin = window.open("", "_blank", "width=900,height=700");
    if (!printWin) {
        window.print();
        return;
    }

    printWin.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Prévia do DANFE - NF-e</title>
            <style>
                body { font-family: Arial, sans-serif; font-size: 11px; margin: 20px; color: #000; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
                th, td { border: 1px solid #333; padding: 4px 6px; }
                th { background: #f0f0f0; font-size: 10px; font-weight: bold; text-align: left; }
                .text-center { text-align: center; }
                .text-right { text-align: right; }
                .watermark { text-align: center; font-size: 13px; font-weight: bold; color: #b45309; padding: 8px; background: #fef3c7; border: 1px dashed #f59e0b; margin-bottom: 12px; }
                @media print {
                    @page { margin: 8mm; size: A4 portrait; }
                }
            </style>
        </head>
        <body>
            <div class="watermark">⚠️ PRÉVIA DA NOTA FISCAL (RASCUNHO SEM VALOR FISCAL - NÃO TRANSMITIDO À SEFAZ)</div>
            ${conteudo.innerHTML}
            <script>
                window.onload = function() { window.print(); setTimeout(() => window.close(), 1000); };
            <\/script>
        </body>
        </html>
    `);
    printWin.document.close();
}

function renderDanfePreviaModal(danfe) {
    const container = document.getElementById("modal-previa-danfe-conteudo");
    if (!container) return;

    const fmtMoney = (v) => {
        const n = parseFloat(v);
        if (isNaN(n)) return v || "0,00";
        return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const emit = danfe.emitente || {};
    const dest = danfe.destinatario || {};
    const tot = danfe.totais || {};
    const transp = danfe.transporte || {};
    const itens = danfe.itens || [];
    const duplicatas = danfe.duplicatas || [];
    const chaveFormatada = (danfe.chave || "").replace(/(\d{4})(?=\d)/g, "$1 ");
    const barcodeSvg = typeof generateCode128Svg === "function" ? generateCode128Svg(danfe.chave || "") : "";

    const modFreteNomes = {
        "0": "0 - Remetente (CIF)",
        "1": "1 - Destinatário (FOB)",
        "2": "2 - Terceiros",
        "3": "3 - Próprio Remetente",
        "4": "4 - Próprio Destinatário",
        "9": "9 - Sem Frete (Balcão)",
    };

    container.innerHTML = `
        <div style="position:relative;overflow:hidden;background:#fff;border:1px solid #94a3b8;border-radius:6px;padding:16px;color:#0f172a;font-family:Arial, sans-serif;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
            <!-- Tarja Diagonal Marca d'Água Sem Validade Fiscal -->
            <div class="watermark-previa-emissao" style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%) rotate(-30deg);
                font-size: 38px;
                font-weight: 900;
                color: rgba(220, 38, 38, 0.26);
                border: 6px dashed rgba(220, 38, 38, 0.38);
                text-align: center;
                padding: 20px 40px;
                letter-spacing: 2px;
                text-transform: uppercase;
                pointer-events: none;
                z-index: 20;
                line-height: 1.3;
                white-space: nowrap;
                user-select: none;
                box-shadow: 0 0 30px rgba(220, 38, 38, 0.08);
            ">
                ⚠️ SEM VALIDADE FISCAL<br>
                <span style="font-size:20px;font-weight:700;">PRÉVIA DE EMISSÃO / NÃO TRANSMITIDA</span>
            </div>

            <!-- Tarja Rascunho / Sem Valor Fiscal -->
            <div style="background:#fef3c7;border:1px dashed #d97706;border-radius:6px;padding:8px 12px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                <div style="font-weight:bold;color:#92400e;font-size:13px;display:flex;align-items:center;gap:6px;">
                    <span>⚠️ PRÉVIA DO DOCUMENTO FISCAL (SEM VALOR JURÍDICO/FISCAL)</span>
                </div>
                <div style="font-size:11px;color:#78350f;font-weight:600;">
                    Ambiente: ${escapeHtml(danfe.ambiente || "Homologação")} | Modelo: 55 | Série: ${danfe.serie} | Nº ${danfe.numero}
                </div>
            </div>

            <!-- Canhoto de Recebimento Provisório -->
            <div style="border:1px solid #000;padding:6px;margin-bottom:10px;font-size:10px;">
                <div style="text-align:center;font-weight:bold;font-size:9.5px;margin-bottom:4px;">
                    RECEBEMOS DE ${escapeHtml(emit.razao_social || "EMPRESA EMITENTE")} OS PRODUTOS / SERVIÇOS CONSTANTES DA NOTA FISCAL INDICADA AO LADO
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:9.5px;">
                    <tr>
                        <td style="border:1px solid #000;width:25%;padding:6px;"><b>DATA DE RECEBIMENTO:</b><br>&nbsp;</td>
                        <td style="border:1px solid #000;width:55%;padding:6px;"><b>IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR:</b><br>&nbsp;</td>
                        <td style="border:1px solid #000;width:20%;text-align:center;padding:6px;">
                            <b>NF-e (PRÉVIA)</b><br>
                            <b>Nº ${escapeHtml(danfe.numero || "1")}</b><br>
                            SÉRIE: ${escapeHtml(danfe.serie || "1")}
                        </td>
                    </tr>
                </table>
            </div>

            <!-- Cabeçalho Principal DANFE -->
            <div style="display:flex;border:1px solid #000;margin-bottom:8px;">
                <!-- Dados do Emitente -->
                <div style="flex:1.4;padding:10px;border-right:1px solid #000;font-size:11px;">
                    <div style="font-size:14px;font-weight:bold;margin-bottom:4px;color:#000;">${escapeHtml(emit.razao_social || "EMPRESA EMITENTE")}</div>
                    <div>${escapeHtml(emit.logradouro || "")}${emit.numero ? ", " + escapeHtml(emit.numero) : ""}${emit.bairro ? " - " + escapeHtml(emit.bairro) : ""}</div>
                    <div>${escapeHtml(emit.municipio || "")} / ${escapeHtml(emit.uf || "SP")} - CEP: ${escapeHtml(emit.cep || "")}</div>
                    <div style="margin-top:4px;font-size:10px;">
                        <b>CNPJ:</b> ${escapeHtml(emit.cnpj || "—")} &nbsp;|&nbsp; <b>IE:</b> ${escapeHtml(emit.ie || "ISENTO")}
                    </div>
                </div>

                <!-- Quadro DANFE -->
                <div style="flex:0.8;padding:8px;text-align:center;border-right:1px solid #000;display:flex;flex-direction:column;justify-content:center;">
                    <div style="font-size:16px;font-weight:bold;">DANFE</div>
                    <div style="font-size:9px;color:#333;">Documento Auxiliar da<br>Nota Fiscal Eletrônica</div>
                    <div style="margin:4px 0;font-size:10px;border:1px solid #000;padding:2px;display:inline-block;">
                        <b>${(String(danfe.tipo_doc || danfe.tipo || danfe.tipo_operacao || '') === '0' || danfe.tipo_doc === 0) ? "0 - ENTRADA" : "1 - SAÍDA"}</b>
                    </div>
                    <div style="font-size:11px;font-weight:bold;">Nº ${escapeHtml(danfe.numero || "1")}</div>
                    <div style="font-size:10px;">SÉRIE: ${escapeHtml(danfe.serie || "1")}</div>
                    <div style="font-size:9px;color:#666;">FOLHA 1/1</div>
                </div>

                <!-- Código de Barras & Chave -->
                <div style="flex:1.8;padding:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:10px;">
                    ${barcodeSvg ? `<div style="margin-bottom:4px;">${barcodeSvg}</div>` : ""}
                    <div style="font-weight:bold;font-size:9px;color:#64748b;">CHAVE DE ACESSO SUGERIDA</div>
                    <div style="font-family:monospace;font-size:11px;font-weight:bold;letter-spacing:1px;margin:2px 0;text-align:center;color:#0f172a;">
                        ${escapeHtml(chaveFormatada || danfe.chave || "—")}
                    </div>
                    <div style="font-size:8px;color:#64748b;text-align:center;margin-top:2px;">
                        Status: <b>PENDENTE DE TRANSMISSÃO SEFAZ</b>
                    </div>
                </div>
            </div>

            <!-- Natureza da Operação -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:11px;">
                <tr>
                    <th style="width:60%;border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;">NATUREZA DA OPERAÇÃO</th>
                    <th style="width:40%;border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;">PROTOCOLO DE AUTORIZAÇÃO DE USO</th>
                </tr>
                <tr>
                    <td style="border:1px solid #000;padding:5px 8px;font-weight:bold;">${escapeHtml(danfe.natureza_operacao || danfe.natureza || "VENDA DE MERCADORIA")}</td>
                    <td style="border:1px solid #000;padding:5px 8px;color:#92400e;font-weight:600;">PRÉVIA / RASCUNHO (Não transmitido)</td>
                </tr>
            </table>

            <!-- Destinatário / Remetente -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:11px;">
                <tr><th colspan="4" style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">DESTINATÁRIO / REMETENTE</th></tr>
                <tr>
                    <td colspan="2" style="border:1px solid #000;padding:5px 8px;width:60%;"><b>NOME / RAZÃO SOCIAL:</b><br>${escapeHtml(dest.razao_social || "CONSUMIDOR NÃO IDENTIFICADO")}</td>
                    <td style="border:1px solid #000;padding:5px 8px;width:25%;"><b>CNPJ / CPF:</b><br>${escapeHtml(dest.cnpj_cpf || "—")}</td>
                    <td style="border:1px solid #000;padding:5px 8px;width:15%;"><b>DATA EMISSÃO:</b><br>${escapeHtml(danfe.data_emissao || "")}</td>
                </tr>
                <tr>
                    <td colspan="2" style="border:1px solid #000;padding:5px 8px;"><b>ENDEREÇO:</b><br>${escapeHtml(dest.logradouro || "")}${dest.numero ? ", " + escapeHtml(dest.numero) : ""}${dest.bairro ? " - " + escapeHtml(dest.bairro) : ""}</td>
                    <td style="border:1px solid #000;padding:5px 8px;"><b>MUNICÍPIO / UF:</b><br>${escapeHtml(dest.municipio || "")} / ${escapeHtml(dest.uf || "SP")}</td>
                    <td style="border:1px solid #000;padding:5px 8px;"><b>DATA SAÍDA:</b><br>${escapeHtml(danfe.data_saida || danfe.data_emissao || "")}</td>
                </tr>
            </table>

            <!-- Faturas / Duplicatas (se houver) -->
            ${duplicatas.length > 0 ? `
                <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:11px;">
                    <tr><th colspan="${duplicatas.length}" style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">FATURA / DUPLICATAS DE PAGAMENTO</th></tr>
                    <tr>
                        ${duplicatas.map(d => `
                            <td style="border:1px solid #000;padding:4px 8px;text-align:center;">
                                <b>Parc. ${escapeHtml(d.numero || "01")}</b><br>
                                Venc: ${escapeHtml(d.vencimento || "")}<br>
                                <b style="color:#1b4f72;">R$ ${fmtMoney(d.valor)}</b>
                            </td>
                        `).join("")}
                    </tr>
                </table>
            ` : ""}

            <!-- Cálculo do Imposto e Totais -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:10.5px;">
                <tr><th colspan="6" style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">CÁLCULO DO IMPOSTO</th></tr>
                <tr>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>BASE CÁLC. ICMS:</b><br>R$ ${fmtMoney(tot.base_icms)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR DO ICMS:</b><br>R$ ${fmtMoney(tot.valor_icms)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>BASE CÁLC. ICMS ST:</b><br>R$ ${fmtMoney(tot.base_icms_st)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR ICMS ST:</b><br>R$ ${fmtMoney(tot.valor_icms_st)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR DOS PRODUTOS:</b><br>R$ ${fmtMoney(tot.valor_produtos)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;background:#fef9c3;"><b>VALOR TOTAL DA NOTA:</b><br><b style="color:#b91c1c;font-size:13px;">R$ ${fmtMoney(tot.valor_total)}</b></td>
                </tr>
                <tr>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR DO FRETE:</b><br>R$ ${fmtMoney(tot.valor_frete)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR DO SEGURO:</b><br>R$ ${fmtMoney(tot.valor_seguro)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;color:#c0392b;"><b>DESCONTO:</b><br>- R$ ${fmtMoney(tot.desconto)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>OUTRAS DESPESAS:</b><br>R$ ${fmtMoney(tot.outras_despesas)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;"><b>VALOR DO IPI:</b><br>R$ ${fmtMoney(tot.valor_ipi)}</td>
                    <td style="border:1px solid #000;padding:4px 6px;background:#e0f2fe;color:#0369a1;"><b>TRIBUTOS APROX. (IBPT):</b><br>R$ ${fmtMoney(tot.valor_tributos)}</td>
                </tr>
            </table>

            <!-- Transporte e Carga -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:10.5px;">
                <tr><th colspan="5" style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">TRANSPORTADOR / VOLUMES TRANSPORTADOS</th></tr>
                <tr>
                    <td style="border:1px solid #000;padding:4px 6px;width:30%;"><b>FRETE POR CONTA:</b><br>${escapeHtml(modFreteNomes[transp.modalidade_frete] || "9 - Sem Frete")}</td>
                    <td style="border:1px solid #000;padding:4px 6px;width:30%;"><b>TRANSPORTADORA:</b><br>${escapeHtml(transp.transportadora_nome || "—")}</td>
                    <td style="border:1px solid #000;padding:4px 6px;width:15%;"><b>PLACA VEÍCULO:</b><br>${escapeHtml(transp.placa_veiculo || "—")} ${escapeHtml(transp.uf_veiculo || "")}</td>
                    <td style="border:1px solid #000;padding:4px 6px;width:12%;"><b>PESO LÍQUIDO:</b><br>${fmtMoney(transp.peso_liquido)} kg</td>
                    <td style="border:1px solid #000;padding:4px 6px;width:13%;"><b>PESO BRUTO:</b><br>${fmtMoney(transp.peso_bruto)} kg</td>
                </tr>
            </table>

            <!-- Tabela de Produtos / Serviços -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:10.5px;">
                <tr><th colspan="9" style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">DADOS DOS PRODUTOS / SERVIÇOS</th></tr>
                <tr style="background:#e2e8f0;font-size:9.5px;">
                    <th style="border:1px solid #000;width:9%;padding:4px;">CÓDIGO</th>
                    <th style="border:1px solid #000;width:37%;padding:4px;">DESCRIÇÃO DO PRODUTO / SERVIÇO</th>
                    <th style="border:1px solid #000;width:8%;text-align:center;padding:4px;">NCM/SH</th>
                    <th style="border:1px solid #000;width:6%;text-align:center;padding:4px;">CFOP</th>
                    <th style="border:1px solid #000;width:5%;text-align:center;padding:4px;">UN</th>
                    <th style="border:1px solid #000;width:7%;text-align:right;padding:4px;">QTD</th>
                    <th style="border:1px solid #000;width:10%;text-align:right;padding:4px;">UNITÁRIO</th>
                    <th style="border:1px solid #000;width:8%;text-align:right;padding:4px;">DESC.</th>
                    <th style="border:1px solid #000;width:10%;text-align:right;padding:4px;">TOTAL</th>
                </tr>
                ${itens.map(p => `
                    <tr>
                        <td style="border:1px solid #000;padding:4px;font-family:monospace;">${escapeHtml(p.codigo || "")}</td>
                        <td style="border:1px solid #000;padding:4px;">
                            <b>${escapeHtml(p.descricao || "")}</b>
                            ${p.imei ? `<br><span style="color:#0284c7;font-size:9.5px;font-weight:600;">📱 IMEI/Série: ${escapeHtml(p.imei)}</span>` : ''}
                        </td>
                        <td style="border:1px solid #000;padding:4px;text-align:center;">${escapeHtml(p.ncm || "")}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:center;">${escapeHtml(p.cfop || "")}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:center;">${escapeHtml(p.unidade || "UN")}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:right;">${p.quantidade}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:right;">R$ ${fmtMoney(p.valor_unitario)}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:right;color:#c0392b;">R$ ${fmtMoney(p.desconto)}</td>
                        <td style="border:1px solid #000;padding:4px;text-align:right;font-weight:bold;color:#15803d;">R$ ${fmtMoney(p.valor_total)}</td>
                    </tr>
                `).join("")}
            </table>

            <!-- Dados Adicionais / Observações Fiscais -->
            <table class="danfe-tabela" style="width:100%;border-collapse:collapse;font-size:10px;">
                <tr><th style="border:1px solid #000;background:#f1f5f9;padding:4px 8px;font-size:9.5px;text-align:left;">DADOS ADICIONAIS / INFORMAÇÕES COMPLEMENTARES</th></tr>
                <tr>
                    <td style="border:1px solid #000;padding:8px;line-height:1.4;">
                        ${danfe.chave_referenciada ? `<div style="margin-bottom:4px;"><b>NF-e Referenciada (Origem):</b> <code>${escapeHtml(danfe.chave_referenciada)}</code></div>` : ""}
                        <div><b>Informações Complementares:</b> ${escapeHtml(danfe.informacoes_complementares || "Documento emitido por ME ou EPP optante pelo Simples Nacional.")}</div>
                    </td>
                </tr>
            </table>
        </div>
    `;
}

async function visualizarPreviaDanfeEmissao() {
    // 1. Auto-adiciona produto se o usuário preencheu descrição e preço mas esqueceu de clicar em "➕ Adicionar à Nota"
    const descInput = document.getElementById("item-add-descricao");
    const precoInput = document.getElementById("item-add-preco");
    if ((!AppState.emissaoItens || AppState.emissaoItens.length === 0) && descInput && descInput.value.trim() && precoInput && parseFloat(precoInput.value) > 0) {
        adicionarItemNfeEmissao();
    }

    if (!AppState.emissaoItens || AppState.emissaoItens.length === 0) {
        if (descInput) {
            descInput.focus();
            descInput.classList.add("input-erro-destaque");
            setTimeout(() => descInput.classList.remove("input-erro-destaque"), 3000);
        }
        toast.warning("Por favor, adicione ao menos um produto à nota fiscal antes de visualizar a prévia. Preencha os campos com borda vermelha e clique em '➕ Adicionar à Nota'.", 8000);
        return;
    }

    // 2. Valida campos obrigatórios do destinatário
    const destDocEl = document.getElementById("emissao-dest-cpf-cnpj");
    const destNomeEl = document.getElementById("emissao-dest-nome");
    const destDoc = (destDocEl?.value || "").replace(/\D/g, "");
    const destNome = (destNomeEl?.value || "").trim();

    if (!destDoc || (destDoc.length !== 11 && destDoc.length !== 14)) {
        if (destDocEl) {
            destDocEl.focus();
            destDocEl.classList.add("input-erro-destaque");
            setTimeout(() => destDocEl.classList.remove("input-erro-destaque"), 3000);
        }
        toast.warning("Preencha o CPF (11 dígitos) ou CNPJ (14 dígitos) do destinatário (campo obrigatório com borda vermelha).", 8000);
        return;
    }

    if (!destNome) {
        if (destNomeEl) {
            destNomeEl.focus();
            destNomeEl.classList.add("input-erro-destaque");
            setTimeout(() => destNomeEl.classList.remove("input-erro-destaque"), 3000);
        }
        toast.warning("Preencha o Nome ou Razão Social do destinatário (campo obrigatório com borda vermelha).", 8000);
        return;
    }

    const payload = montarPayloadEmissao();

    const btn = document.getElementById("btn-previa-danfe-emissao");
    const originalText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Gerando Prévia..."; }

    try {
        const res = await apiPost("/api/emissao/nfe/previa", payload);
        const danfeObj = (res && res.data && res.data.danfe) ? res.data.danfe : (res && res.danfe ? res.danfe : (res && res.data ? res.data : null));

        if (res.success && danfeObj && !danfeObj.error && !danfeObj.detail) {
            const modal = document.getElementById("modal-previa-nfe-emissao");
            if (modal) {
                modal.style.display = "flex";
                renderDanfePreviaModal(danfeObj);
            }
        } else {
            const msg = (res && res.data && res.data.detail) || (res && res.data && res.data.message) || (res && res.data && res.data.error) || (res && res.detail) || "Erro ao gerar prévia do DANFE.";
            toast.error("Não foi possível gerar a prévia: " + msg);
        }
    } catch (err) {
        toast.error("Erro ao gerar prévia: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
    }
}

async function limparFormularioEmissaoCompleto() {
    if (AppState.emissaoItens && AppState.emissaoItens.length > 0) {
        const confirma = await showConfirmModal({
            title: "Limpar Formulário",
            message: "Deseja realmente limpar todos os dados do formulário e os produtos preenchidos?",
            confirmText: "Sim, limpar",
            cancelText: "Cancelar",
            danger: true,
            icon: "🗑️",
        });
        if (!confirma) {
            return;
        }
    }

    const form = document.getElementById("form-emissao-profissional");
    if (form) form.reset();

    AppState.emissaoItens = [];
    renderizarTabelaItensEmissao();

    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setVal("emissao-busca-cliente", "");
    setVal("emissao-busca-produto", "");
    setVal("emissao-chave-referenciada", "");
    setVal("item-add-codigo", "");
    setVal("item-add-descricao", "");
    setVal("item-add-qtd", "1");
    setVal("item-add-preco", "");
    setVal("item-add-desconto", "0.00");
    setVal("item-add-total-display", "R$ 0,00");

    const boxRef = document.getElementById("container-nfe-referenciada");
    if (boxRef) boxRef.style.display = "none";
    const boxTransp = document.getElementById("container-campos-transporte");
    if (boxTransp) boxTransp.style.display = "none";
    const boxPrazo = document.getElementById("container-parcelas-prazo");
    if (boxPrazo) boxPrazo.style.display = "none";
    const resDiv = document.getElementById("emissao-resultado-painel");
    if (resDiv) { resDiv.style.display = "none"; resDiv.innerHTML = ""; }

    atualizarProximoNumeroNfe();
    atualizarTotaisNfeEmissao();
}

async function handleEmitirNfeProfissional(e) {
    if (e) e.preventDefault();

    const descInput = document.getElementById("item-add-descricao");
    const precoInput = document.getElementById("item-add-preco");
    if ((!AppState.emissaoItens || AppState.emissaoItens.length === 0) && descInput && descInput.value.trim() && precoInput && parseFloat(precoInput.value) > 0) {
        adicionarItemNfeEmissao();
    }

    if (!AppState.emissaoItens || AppState.emissaoItens.length === 0) {
        if (descInput) {
            descInput.focus();
            descInput.classList.add("input-erro-destaque");
            setTimeout(() => descInput.classList.remove("input-erro-destaque"), 3000);
        }
        toast.warning("Por favor, adicione ao menos um produto à nota fiscal antes de transmitir.");
        return;
    }

    const payload = montarPayloadEmissao();
    const destDoc = payload.destinatario.cpf_cnpj;
    const destNome = payload.destinatario.razao_social;

    if (!destDoc || (destDoc.length !== 11 && destDoc.length !== 14)) {
        toast.error("CPF/CNPJ do destinatário inválido.");
        return;
    }
    if (!destNome) {
        toast.error("Nome/Razão Social do destinatário é obrigatório.");
        return;
    }

    // Abre o modal seguro de confirmação (Sim / Não)
    abrirModalConfirmacaoTransmissao(payload);
}

function abrirModalConfirmacaoTransmissao(payload) {
    if (!payload) payload = montarPayloadEmissao();
    AppState._payloadPendenteEmissao = payload;

    const modal = document.getElementById("modal-confirmar-transmissao-nfe");
    if (!modal) return;

    const emitCnpj = payload.emitente_cnpj || "";
    const cert = (AppState.certificados || []).find(c => c.cnpj === emitCnpj) || {};
    const fmtDoc = (doc) => (doc || '').replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5").replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");

    const emitEl = document.getElementById("confirm-trans-emitente");
    const destEl = document.getElementById("confirm-trans-destinatario");
    const numEl = document.getElementById("confirm-trans-numero-serie");
    const itensEl = document.getElementById("confirm-trans-itens");
    const valEl = document.getElementById("confirm-trans-valor");

    let totProdutos = 0;
    (payload.produtos || []).forEach(p => {
        totProdutos += (parseFloat(p.quantidade || 1) * parseFloat(p.valor_unitario || 0)) - parseFloat(p.desconto || 0);
    });
    const totNota = totProdutos + parseFloat(payload.valor_frete || 0) + parseFloat(payload.outras_despesas || 0);

    if (emitEl) emitEl.textContent = `${cert.razao_social || 'FILIAL'} (${fmtDoc(emitCnpj)})`;
    if (destEl) destEl.textContent = `${payload.destinatario?.razao_social || '—'} (${fmtDoc(payload.destinatario?.cpf_cnpj || '')})`;
    if (numEl) numEl.textContent = `Nº ${payload.numero || 'Auto'} / Série ${payload.serie || '1'}`;
    if (itensEl) itensEl.textContent = `${(payload.produtos || []).length} produto(s)`;
    if (valEl) valEl.textContent = `R$ ${totNota.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    modal.style.display = "flex";
}

function fecharModalConfirmacaoTransmissao() {
    const modal = document.getElementById("modal-confirmar-transmissao-nfe");
    if (modal) modal.style.display = "none";
}

async function executarTransmissaoSefazConfirmada() {
    const payload = AppState._payloadPendenteEmissao || montarPayloadEmissao();
    const btn = document.getElementById("btn-executar-transmissao-sefaz");
    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Transmitindo à SEFAZ..."; }

    const resDiv = document.getElementById("emissao-resultado-painel");
    if (resDiv) {
        resDiv.style.display = "block";
        resDiv.className = "result info";
        resDiv.innerHTML = `<p>Assinando o XML com Certificado Digital A1 e comunicando com os servidores da SEFAZ...</p>`;
    }

    try {
        const res = await apiPost("/api/emissao/nfe/emitir", payload);
        const d = (res && res.data && res.data.data) ? res.data.data : (res && res.data ? res.data : null);

        fecharModalConfirmacaoTransmissao();
        fecharModalPreviaNfe();

        if (res.success && d && d.chave) {
            // Abre o modal de retorno oficial com sucesso
            abrirModalRetornoSefaz({
                autorizada: true,
                c_stat: d.c_stat || "100",
                x_motivo: d.motivo || "Autorizado o uso da NF-e",
                chave: d.chave,
                numero: d.numero,
                serie: d.serie,
                modelo: "55",
                empresa_cnpj: d.emitente_cnpj || payload.emitente_cnpj,
                emitente_nome: d.emitente,
                destinatario_nome: d.destinatario,
                destinatario_cnpj: payload.destinatario?.cpf_cnpj,
                valor_total: d.valor_total,
                protocolo: d.protocolo,
                ambiente: d.ambiente,
                status_geral: "NF-e Autorizada com Sucesso na SEFAZ",
                explicacao_didatica: "A nota fiscal foi assinada com Certificado A1, validada e autorizada pelo Fisco com total validade jurídica.",
                solucao_recomendada: "Você já pode imprimir o DANFE, enviar o XML/PDF por e-mail ou WhatsApp para o cliente.",
                tipo_retorno: "sucesso"
            });

            // Limpa o carrinho de itens e avança o próximo número
            AppState.emissaoItens = [];
            renderizarTabelaItensEmissao();
            await atualizarProximoNumeroNfe();
            carregarSelectClientesEmissao();
            carregarNfeSaidas(1);
        } else {
            const errDetail = res.data?.detail || res.data?.error || "Rejeição SEFAZ";
            abrirModalRetornoSefaz({
                autorizada: false,
                c_stat: res.data?.c_stat || "225",
                x_motivo: errDetail,
                chave: res.data?.chave || "Pendente",
                numero: payload.numero || "Auto",
                serie: payload.serie || "1",
                empresa_cnpj: payload.emitente_cnpj,
                destinatario_nome: payload.destinatario?.razao_social,
                valor_total: 0,
                status_geral: "Rejeição / Erro de Transmissão SEFAZ",
                explicacao_didatica: `A SEFAZ retornou uma rejeição ao processar o lote: ${errDetail}`,
                solucao_recomendada: "Revise os dados destacados no formulário e corrija o campo apontado antes de transmitir novamente.",
                tipo_retorno: "erro"
            });
        }
    } catch (err) {
        fecharModalConfirmacaoTransmissao();
        fecharModalPreviaNfe();
        abrirModalRetornoSefaz({
            autorizada: false,
            c_stat: "ERR",
            x_motivo: err.message,
            chave: "—",
            status_geral: "Falha na Comunicação",
            explicacao_didatica: `Não foi possível transmitir a nota fiscal: ${err.message}`,
            solucao_recomendada: "Verifique os logs do servidor e a conexão com os servidores da SEFAZ.",
            tipo_retorno: "erro"
        });
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

// ====================================================================
// HISTÓRICO DE NF-e DE SAÍDAS (VENDAS / CLIENTES)
// ====================================================================

async function carregarNfeSaidas(page = 1) {
    currentSaidasPage = page;
    const tbody = document.getElementById("tbody-saidas-nfe");
    const pagDiv = document.getElementById("paginacao-saidas");
    if (!tbody) return;

    skeletonTable("tbody-saidas-nfe", 9, 8);

    const emp = document.getElementById("filtro-saidas-empresa")?.value || "";
    const busca = document.getElementById("filtro-saidas-busca")?.value || "";
    const sit = document.getElementById("filtro-saidas-situacao")?.value || "";
    const dtIni = document.getElementById("filtro-saidas-inicio")?.value || "";
    const dtFim = document.getElementById("filtro-saidas-fim")?.value || "";

    try {
        const url = `/api/emissao/saidas?page=${page}&limit=50&empresa_cnpj=${encodeURIComponent(emp)}&busca=${encodeURIComponent(busca)}&situacao=${encodeURIComponent(sit)}&data_inicio=${encodeURIComponent(dtIni)}&data_fim=${encodeURIComponent(dtFim)}`;
        const res = await apiGet(url);

        if (res.success) {
            const docs = res.data?.documentos || res.documentos || [];
            const total = res.data?.total !== undefined ? res.data.total : (res.total || docs.length);
            AppState.saidasNfe = docs;

            let volTotal = 0;
            docs.forEach(d => { volTotal += parseFloat(d.valor_total || 0); });
            const ticketMedio = docs.length ? (volTotal / docs.length) : 0;

            const kpiQtd = document.getElementById("kpi-saidas-qtd");
            const kpiVol = document.getElementById("kpi-saidas-volume");
            const kpiTic = document.getElementById("kpi-saidas-ticket");

            if (kpiQtd) kpiQtd.textContent = total;
            if (kpiVol) kpiVol.textContent = `R$ ${volTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            if (kpiTic) kpiTic.textContent = `R$ ${ticketMedio.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

            if (docs.length === 0) {
                renderEmptyState({
                    icon: '📭',
                    title: 'Nenhuma NF-e de saída/venda',
                    description: 'Nenhuma nota fiscal de saída encontrada com os filtros selecionados. Ajuste os filtros ou importe NF-es da SEFAZ.',
                    containerId: 'tbody-saidas-nfe',
                });
                if (pagDiv) pagDiv.innerHTML = "";
                return;
            }

            // ===================================================================
            // AGRUPAMENTO POR DIA: percorre docs (já vem DESC do backend) e
            // injeta cabeçalhos de grupo + linhas de subtotal ao final de cada
            // dia. Cada grupo mostra "📅 dd/mm/aaaa (dia-da-semana) — N notas"
            // e termina com "Subtotal: R$ X.XXX,XX".
            // ===================================================================
            let html = "";
            let grupoAtual = null;
            let subtotalGrupo = 0;
            let qtdGrupo = 0;

            const fecharGrupoAnterior = (diaChave) => {
                if (diaChave === null) return;
                const subFmt = subtotalGrupo.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                html += `<tr class="linhaSubtotal" style="font-weight:bold;">
                    <td colspan="5" style="padding:5px 10px;text-align:right;">Subtotal ${diaSemanaBR(diaChave)}:</td>
                    <td style="text-align:center;">${qtdGrupo}</td>
                    <td style="text-align:right;color:#10b981;font-weight:bold;">R$ ${subFmt}</td>
                    <td colspan="2"></td>
                </tr>`;
            };

            docs.forEach((d, i) => {
                const dia = chaveDiaBR(d.data_emissao);
                if (dia !== grupoAtual) {
                    // Fecha o grupo anterior (se houver)
                    fecharGrupoAnterior(grupoAtual);
                    // Abre novo grupo
                    grupoAtual = dia;
                    subtotalGrupo = 0;
                    qtdGrupo = 0;
                    html += `<tr class="linhaGrupoDia" style="font-weight:bold;">
                        <td colspan="9" style="padding:7px 14px;">📅 ${diaSemanaBR(dia)}</td>
                    </tr>`;
                }

                subtotalGrupo += parseFloat(d.valor_total || 0);
                qtdGrupo += 1;

                const numSerie = `${d.numero || "—"} / ${d.serie || "1"}`;
                const dataEmi = fmtDataBR(d.data_emissao);
                const vTot = parseFloat(d.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                const destFmt = `${escapeHtml(d.destinatario_nome || "—")}<br><small style="color:#64748b;">${d.destinatario_cnpj || ""}</small>`;
                const emitFmt = `${escapeHtml(d.emitente_nome || "—")}`;
                const isCancelada = (d.situacao || "").toLowerCase().includes("cancelad");
                const isPendenteOuRejeitada = (d.situacao || "").toLowerCase().includes("pendent") || (d.situacao || "").toLowerCase().includes("rejeit") || (d.situacao || "").toLowerCase().includes("erro");

                html += `
                    <tr class="linha" style="${isCancelada ? 'opacity:0.65;background:#fef2f2;' : ''};cursor:pointer;" onclick="toggleSaidasItens('${d.chave}', this)">
                        <td style="text-align:center;">${(page - 1) * 50 + (i + 1)}</td>
                        <td style="text-align:center;"><b>${numSerie}</b></td>
                        <td style="text-align:center;">${dataEmi}</td>
                        <td>${emitFmt}</td>
                        <td>${destFmt}</td>
                        <td style="text-align:center;"><span class="badge badge-info" id="badge-saidas-${d.chave}">${d.qtd_itens || "?"}</span></td>
                        <td style="text-align:right;font-weight:bold;color:#1b4f72;">R$ ${vTot}</td>
                        <td style="text-align:center;">
                            ${getSituacaoBadgeHtml(d.situacao || "Autorizada")}
                        </td>
                        <td style="text-align:center;">
                            <div class="actions-cell" style="justify-content:center;gap:4px;flex-wrap:wrap;">
                                <button type="button" class="btn-action btn-action-primary" onclick="event.stopPropagation();abrirDanfeDireto('${d.chave}');" title="Visualizar DANFE">👁️ DANFE</button>
                                <button type="button" class="btn-action" onclick="event.stopPropagation();reenviarNfeSefaz('${d.chave}');" title="Reenviar / Validar Retorno na SEFAZ" style="${isPendenteOuRejeitada ? 'background:#fef3c7;color:#92400e;border-color:#f59e0b;font-weight:bold;' : 'background:#f0fdf4;color:#166534;border-color:#bbf7d0;'}">🔄 Reenviar</button>
                                <a href="/api/danfe/pdf/${d.chave}" target="_blank" class="btn-action" style="text-decoration:none;" title="Baixar PDF">📥 PDF</a>
                                <button type="button" class="btn-action" onclick="event.stopPropagation();enviarWhatsappNfe('${d.chave}');" title="Enviar para o WhatsApp do Cliente" style="background:#25d366;color:#fff;border-color:#25d366;font-weight:bold;">💬 Zap</button>
                                <button type="button" class="btn-action" onclick="event.stopPropagation();abrirModalEmailNfe('${d.chave}', '${escapeHtml(d.destinatario_nome || '')}');" title="Enviar por E-mail com XML e PDF">📧 E-mail</button>
                                <button type="button" class="btn-action" onclick="event.stopPropagation();clonarNfeParaEmissao('${d.chave}');" title="Clonar dados para emitir nova nota">📋 Clonar</button>
                                <button type="button" class="btn-action" onclick="event.stopPropagation();abrirCartaCorrecaoModal('${d.chave}', '${d.empresa_cnpj || d.emitente_cnpj}');" title="Carta de Correção">✍️ CC-e</button>
                                ${!isCancelada ? `<button type="button" class="btn-action" onclick="event.stopPropagation();abrirModalCancelarNfe('${d.chave}', '${d.protocolo || ""}');" style="color:#c0392b;" title="Cancelar NF-e na SEFAZ">❌ Cancelar</button>` : ''}
                            </div>
                        </td>
                    </tr>
                    <tr id="row-saidas-itens-${d.chave}" style="display:none;">
                        <td colspan="9" style="padding:0;">
                            <div id="container-saidas-itens-${d.chave}" style="background:#f8fafc;padding:8px 12px;border-top:1px solid #e2e8f0;">
                                <span style="color:#64748b;font-size:11px;">Clique para carregar itens...</span>
                            </div>
                        </td>
                    </tr>
                `;
            });
            // Fecha o último grupo
            fecharGrupoAnterior(grupoAtual);
            tbody.innerHTML = html;

            if (pagDiv) {
                const totalPages = Math.ceil(res.data.total / res.data.limit) || 1;
                pagDiv.innerHTML = `
                    <span>Exibindo <b>${docs.length}</b> de <b>${res.data.total}</b> notas de saída</span>
                    <div style="display:flex;gap:6px;">
                        <button type="button" class="btn-action" ${page <= 1 ? "disabled" : ""} onclick="carregarNfeSaidas(${page - 1});">◀ Anterior</button>
                        <span style="padding:3px 8px;font-weight:bold;">Pág. ${page} de ${totalPages}</span>
                        <button type="button" class="btn-action" ${page >= totalPages ? "disabled" : ""} onclick="carregarNfeSaidas(${page + 1});">Próxima ▶</button>
                    </div>
                `;
            }
        }
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:20px;color:#c0392b;">Erro ao carregar saídas: ${escapeHtml(err.message)}</td></tr>`;
    }
}

function filtrarPorSituacaoRapida(sit) {
    const sel = document.getElementById("filtro-saidas-situacao");
    if (sel) sel.value = sit;
    sincronizarAbaSituacao(sit);
    carregarNfeSaidas(1);
}

const _saidasItensCache = {};
async function toggleSaidasItens(chave, rowEl) {
    const detailRow = document.getElementById(`row-saidas-itens-${chave}`);
    const container = document.getElementById(`container-saidas-itens-${chave}`);
    const badge = document.getElementById(`badge-saidas-${chave}`);
    if (!detailRow || !container) return;

    if (detailRow.style.display !== "none") {
        detailRow.style.display = "none";
        return;
    }

    detailRow.style.display = "";

    if (_saidasItensCache[chave]) {
        container.innerHTML = _saidasItensCache[chave];
        return;
    }

    container.innerHTML = `<span style="color:#64748b;font-size:11px;">⏳ Carregando itens...</span>`;

    try {
        const res = await apiGet(`/api/danfe/parse/${chave}`);
        const d = res.data || res;
        const produtos = d.produtos || [];

        if (badge) badge.textContent = `${produtos.length} itens`;

        if (produtos.length === 0) {
            container.innerHTML = `<span style="color:#94a3b8;font-size:11px;">Sem itens disponíveis (resumo SEFAZ ou XML não encontrado).</span>`;
            return;
        }

        const fmtM = (v) => (parseFloat(v) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        let html = `<table style="width:100%;font-size:10.5px;border-collapse:collapse;">
            <thead><tr style="border-bottom:1px solid #cbd5e1;">
                <th style="text-align:left;padding:3px 6px;">#</th>
                <th style="text-align:left;padding:3px 6px;">Produto</th>
                <th style="text-align:left;padding:3px 6px;">NCM</th>
                <th style="text-align:left;padding:3px 6px;">CFOP</th>
                <th style="text-align:right;padding:3px 6px;">Qtd</th>
                <th style="text-align:right;padding:3px 6px;">V.Unit</th>
                <th style="text-align:right;padding:3px 6px;">Total</th>
            </tr></thead><tbody>`;

        produtos.forEach(p => {
            html += `<tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:3px 6px;">${p.n_item || ''}</td>
                <td style="padding:3px 6px;font-weight:600;">${escapeHtml(p.descricao || '')}</td>
                <td style="padding:3px 6px;color:#64748b;">${escapeHtml(p.ncm || '')}</td>
                <td style="padding:3px 6px;color:#64748b;">${escapeHtml(p.cfop || '')}</td>
                <td style="padding:3px 6px;text-align:right;">${p.quantidade || 0}</td>
                <td style="padding:3px 6px;text-align:right;">R$ ${fmtM(p.valor_unitario)}</td>
                <td style="padding:3px 6px;text-align:right;font-weight:600;">R$ ${fmtM(p.valor_total)}</td>
            </tr>`;
        });

        html += `</tbody></table>`;
        _saidasItensCache[chave] = html;
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = `<span style="color:#c0392b;font-size:11px;">Erro ao carregar itens: ${escapeHtml(err.message)}</span>`;
    }
}


async function popularSelectEmpresasSaidas() {
    const sel = document.getElementById("importar-saida-empresa");
    if (!sel || sel.dataset.populated === "1") return;
    try {
        const res = await apiGet("/api/gestao/sync/status");
        if (res.success && res.data) {
            const certs = (res.data.empresas || []).filter(c => c.is_active);
            sel.innerHTML = '<option value="">— escolha a empresa emitente —</option>' +
                certs.map(c => {
                    const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                    return `<option value="${c.cnpj}">${escapeHtml(c.razao_social)} — ${cnpjFmt}</option>`;
                }).join("");
            sel.dataset.populated = "1";
        }
    } catch (err) {
        console.error("Erro ao carregar empresas:", err);
    }
}


async function importarSaidasExternas() {
    const sel = document.getElementById("importar-saida-empresa");
    const ta = document.getElementById("importar-saida-chaves");
    const fb = document.getElementById("importar-saida-feedback");
    if (!sel || !ta || !fb) return;

    const cnpj = (sel.value || "").replace(/\D/g, "");
    if (!cnpj) {
        fb.innerHTML = '<span style="color:#c0392b;">⚠ Selecione a empresa emitente.</span>';
        return;
    }
    // Aceita chaves separadas por quebra-linha, vírgula, ponto-e-vírgula ou espaço.
    const chaves = ta.value.split(/[\s,;]+/).map(s => s.replace(/\D/g, "")).filter(s => s.length === 44);
    if (chaves.length === 0) {
        fb.innerHTML = '<span style="color:#c0392b;">⚠ Informe ao menos uma chave de 44 dígitos. Chaves com tamanho diferente são ignoradas.</span>';
        return;
    }

    fb.innerHTML = `<span style="color:#2980b9;">⏳ Consultando <b>${chaves.length}</b> chave(s) na SEFAZ via consChNFe (aguarde, pode levar 5-30s por chave)...</span>`;

    try {
        const res = await apiPost("/api/gestao/saidas/importar-chaves", {
            chaves: chaves,
            empresa_cnpj: cnpj,
            homologacao: AppState.ambiente === "homologacao",
        });
        if (res.success) {
            const data = res.data || {};
            const ok = data.sucessos || 0;
            const fail = data.falhas || 0;
            const detalhes = (data.resultados || []).map(r => {
                const cor = r.success ? "#27ae60" : "#c0392b";
                const icone = r.success ? "✅" : "❌";
                return `<li style="color:${cor};margin-bottom:2px;">${icone} <code>${escapeHtml(r.chave)}</code> — ${escapeHtml(r.motivo || "Importada")}</li>`;
            }).join("");
            const totalCor = ok > 0 ? "#27ae60" : "#c0392b";
            const blocked = data.blocked_by_sefaz ? '<div style="margin-top:6px;color:#c0392b;">🔒 SEFAZ bloqueou a consulta (cStat 656). Aguarde o cooldown e tente novamente.</div>' : "";
            fb.innerHTML = `
                <div style="font-weight:bold;color:${totalCor};">
                    ${ok > 0 ? '✓' : '⚠'} <b>${ok}</b> importada(s), <b style="color:#c0392b;">${fail}</b> com erro, de <b>${data.total || chaves.length}</b> consultadas.
                </div>
                ${blocked}
                <ul style="margin-top:6px;margin-bottom:0;padding-left:20px;max-height:200px;overflow-y:auto;font-size:11px;">${detalhes}</ul>
            `;
            // Limpa textarea se houve pelo menos 1 sucesso
            if (ok > 0) {
                ta.value = "";
                carregarNfeSaidas(1);
            }
        } else {
            fb.innerHTML = `<span style="color:#c0392b;">⚠ ${escapeHtml(res.data?.detail || res.data?.error || "Falha na requisição")}</span>`;
        }
    } catch (err) {
        fb.innerHTML = `<span style="color:#c0392b;">⚠ Erro de comunicação: ${escapeHtml(err.message || "Falha")}</span>`;
    }
}

function sincronizarAbaSituacao(sit) {
    document.querySelectorAll(".btn-tab-situacao").forEach(b => b.classList.remove("active"));
    const idMap = {
        "": "tab-sit-todas",
        "autorizada": "tab-sit-autorizada",
        "pendente": "tab-sit-pendente",
        "cancelada": "tab-sit-cancelada",
        "rejeitada": "tab-sit-rejeitada"
    };
    const targetId = idMap[sit] || "tab-sit-todas";
    const btn = document.getElementById(targetId);
    if (btn) btn.classList.add("active");
}

function limparFiltrosSaidas() {
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    setVal("filtro-saidas-empresa", "");
    setVal("filtro-saidas-busca", "");
    setVal("filtro-saidas-situacao", "");
    setVal("filtro-saidas-inicio", "");
    setVal("filtro-saidas-fim", "");
    sincronizarAbaSituacao("");
    carregarNfeSaidas(1);
}

// ====================================================================
// CLONAGEM & CANCELAMENTO DE NF-e DE SAÍDA
// ====================================================================

async function reenviarNfeSefaz(chave) {
    if (!chave) return;

    // Notificação breve de carregamento
    const btn = event?.target;
    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Consultando..."; }

    try {
        const res = await apiPost(`/api/emissao/nfe/${chave}/reenviar`, {
            homologacao: AppState.ambiente === "homologacao"
        });
        const d = res.data?.data || res.data || {};
        if (res.success && (d.c_stat || d.autorizada !== undefined)) {
            abrirModalRetornoSefaz(d);
            // Atualiza a tabela se a situação foi alterada
            carregarNfeSaidas();
        } else {
            const errData = res.data?.data || res.data || {};
            abrirModalRetornoSefaz({
                chave: chave,
                c_stat: errData.c_stat || "999",
                x_motivo: errData.x_motivo || res.data?.detail || res.data?.error || "Erro de comunicação ou validação com a SEFAZ",
                status_geral: "Erro de Comunicação",
                explicacao_didatica: "Não foi possível obter resposta imediata dos servidores da SEFAZ ou os parâmetros da nota estão inconsistentes.",
                solucao_recomendada: "Verifique a conexão de internet, o status dos servidores da Fazenda ou os dados do certificado digital da filial.",
                tipo_retorno: "erro",
                autorizada: false
            });
        }
    } catch (err) {
        abrirModalRetornoSefaz({
            chave: chave,
            c_stat: "ERR",
            x_motivo: err.message,
            status_geral: "Falha na Requisição",
            explicacao_didatica: `Ocorreu uma falha ao tentar conectar com a SEFAZ: ${err.message}`,
            solucao_recomendada: "Verifique os logs do servidor e a validade do certificado digital A1.",
            tipo_retorno: "erro",
            autorizada: false
        });
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

function abrirModalRetornoSefaz(data) {
    const modal = document.getElementById("modal-retorno-sefaz");
    if (!modal || !data) return;

    const isSucesso = data.autorizada || data.c_stat === "100" || data.c_stat === "150";
    const isAlerta = data.c_stat === "101" || data.c_stat === "102" || data.c_stat === "135";
    const header = document.getElementById("retorno-sefaz-header");
    const icone = document.getElementById("retorno-sefaz-icone");
    const titulo = document.getElementById("retorno-sefaz-titulo");
    const boxStatus = document.getElementById("retorno-sefaz-box-status");
    const badgeCstat = document.getElementById("retorno-sefaz-badge-cstat");
    const dataHora = document.getElementById("retorno-sefaz-data-hora");
    const xMotivo = document.getElementById("retorno-sefaz-xmotivo");
    const explicacao = document.getElementById("retorno-sefaz-explicacao");
    const boxSolucao = document.getElementById("retorno-sefaz-box-solucao");
    const solucao = document.getElementById("retorno-sefaz-solucao");
    const numSerie = document.getElementById("retorno-sefaz-num-serie");
    const protocolo = document.getElementById("retorno-sefaz-protocolo");
    const emitente = document.getElementById("retorno-sefaz-emitente");
    const destinatario = document.getElementById("retorno-sefaz-destinatario");
    const valor = document.getElementById("retorno-sefaz-valor");
    const ambiente = document.getElementById("retorno-sefaz-ambiente");
    const chaveEl = document.getElementById("retorno-sefaz-chave");
    const botoesExtras = document.getElementById("retorno-sefaz-botoes-extras");

    // Cores e estilos do header
    if (header) {
        if (isSucesso) {
            header.style.background = "#15803d";
            if (icone) icone.textContent = "✅";
            if (titulo) titulo.textContent = "NF-e Autorizada com Sucesso na SEFAZ";
        } else if (isAlerta) {
            header.style.background = "#0369a1";
            if (icone) icone.textContent = "ℹ️";
            if (titulo) titulo.textContent = "Evento / Inutilização Homologada na SEFAZ";
        } else {
            header.style.background = "#b91c1c";
            if (icone) icone.textContent = "❌";
            if (titulo) titulo.textContent = "Rejeição / Erro de Validação SEFAZ";
        }
    }

    // Box status
    if (boxStatus) {
        if (isSucesso) {
            boxStatus.style.background = "#f0fdf4";
            boxStatus.style.borderLeftColor = "#22c55e";
        } else if (isAlerta) {
            boxStatus.style.background = "#f0f9ff";
            boxStatus.style.borderLeftColor = "#0284c7";
        } else {
            boxStatus.style.background = "#fef2f2";
            boxStatus.style.borderLeftColor = "#ef4444";
        }
    }

    if (badgeCstat) {
        badgeCstat.textContent = `cStat: ${data.c_stat || '—'}`;
        badgeCstat.style.background = isSucesso ? "#16a34a" : (isAlerta ? "#0284c7" : "#dc2626");
    }

    if (dataHora) dataHora.textContent = data.data_retorno || new Date().toLocaleString("pt-BR");
    if (xMotivo) xMotivo.textContent = data.x_motivo || data.status_geral || "Retorno SEFAZ";
    if (explicacao) explicacao.textContent = data.explicacao_didatica || data.x_motivo || "Sem detalhes adicionais.";

    if (boxSolucao) {
        if (data.solucao_recomendada) {
            boxSolucao.style.display = "block";
            if (solucao) solucao.textContent = data.solucao_recomendada;
        } else {
            boxSolucao.style.display = "none";
        }
    }

    if (numSerie) numSerie.textContent = `${data.numero || '—'} / Série ${data.serie || '1'}`;
    if (protocolo) protocolo.textContent = data.protocolo || (isSucesso ? "135260000..." : "Não gerado (Rejeitada)");
    const fmtDoc = (doc) => (doc || '').replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5").replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
    if (emitente) emitente.textContent = `${data.emitente_nome || '—'} (${fmtDoc(data.empresa_cnpj || '')})`;
    if (destinatario) destinatario.textContent = `${data.destinatario_nome || '—'} ${data.destinatario_cnpj ? '(' + fmtDoc(data.destinatario_cnpj) + ')' : ''}`;
    if (valor) valor.textContent = `R$ ${parseFloat(data.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (ambiente) ambiente.textContent = data.ambiente || "Homologação";
    if (chaveEl) {
        const ch = data.chave || "";
        const chFmt = ch.replace(/(\d{4})(?=\d)/g, "$1 ");
        chaveEl.innerHTML = `${chFmt} <button type="button" class="btn-action" onclick="navigator.clipboard.writeText('${ch}'); toast.success('Chave copiada!');" style="font-size:10px;padding:1px 6px;margin-left:6px;">📋 Copiar</button>`;
    }

    if (botoesExtras) {
        botoesExtras.innerHTML = "";
        if (isSucesso) {
            botoesExtras.innerHTML = `
                <button type="button" class="botao botao-primario" onclick="fecharModalRetornoSefaz(); abrirDanfeDireto('${data.chave}');" style="font-size:12px;padding:6px 12px;">
                    👁️ Visualizar DANFE
                </button>
                <a href="/api/danfe/pdf/${data.chave}" target="_blank" class="btn-action" style="font-size:12px;padding:6px 12px;text-decoration:none;">
                    📥 Baixar PDF
                </a>
            `;
        } else {
            botoesExtras.innerHTML = `
                <button type="button" class="botao botao-primario" onclick="fecharModalRetornoSefaz(); clonarNfeParaEmissao('${data.chave}');" style="font-size:12px;padding:6px 12px;">
                    ✏️ Clonar e Corrigir no Formulário
                </button>
            `;
        }
    }

    modal.style.display = "flex";
}

function fecharModalRetornoSefaz() {
    const modal = document.getElementById("modal-retorno-sefaz");
    if (modal) modal.style.display = "none";
}

async function clonarNfeParaEmissao(chave) {
    try {
        const res = await apiGet(`/api/emissao/nfe/${chave}/clonar`);
        if (res.success && res.documento) {
            const doc = res.documento;
            switchEmissaoTab("form");

            const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ""; };
            const dest = doc.destinatario || {};

            setVal("emissao-empresa-emit", doc.empresa_cnpj || doc.emitente_cnpj);
            setVal("emissao-dest-cpf-cnpj", dest.cnpj || dest.cpf || doc.destinatario_cnpj);
            setVal("emissao-dest-nome", dest.nome || doc.destinatario_nome);
            setVal("emissao-dest-ind-ie", dest.indicador_ie || 9);
            setVal("emissao-dest-ie", dest.ie || "");
            setVal("emissao-dest-cep", dest.endereco?.cep || "");
            setVal("emissao-dest-logradouro", dest.endereco?.logradouro || "");
            setVal("emissao-dest-numero", dest.endereco?.numero || "");
            setVal("emissao-dest-bairro", dest.endereco?.bairro || dest.bairro || "");
            setVal("emissao-dest-municipio", dest.endereco?.municipio || dest.municipio || "");
            setVal("emissao-dest-uf", dest.endereco?.uf || dest.uf || doc.destinatario_uf || "SP");
            setVal("emissao-dest-email", dest.email || doc.destinatario_email || "");
            setVal("emissao-dest-telefone", dest.telefone || dest.fone || doc.destinatario_telefone || "");

            if (doc.produtos && doc.produtos.length > 0) {
                AppState.emissaoItens = doc.produtos.map(p => ({
                    codigo: p.codigo || "PROD",
                    descricao: p.descricao || "",
                    imei: p.imei || "",
                    ncm: p.ncm || "85171300",
                    cfop: p.cfop || "5102",
                    unidade: p.unidade || "UN",
                    quantidade: parseFloat(p.quantidade || 1),
                    valor_unitario: parseFloat(p.valor_unitario || 0),
                    desconto: parseFloat(p.desconto || 0),
                    valor_total: parseFloat(p.valor_total || (p.quantidade * p.valor_unitario) || 0),
                }));
            }

            if (doc.numero) {
                setVal("emissao-numero", doc.numero);
                setVal("emissao-serie", doc.serie || "1");
            } else {
                await atualizarProximoNumeroNfe();
            }

            renderizarTabelaItensEmissao();
            atualizarCardEmitenteInfo();
            toast.success(`Dados da NF-e Nº ${doc.numero || ''} carregados no formulário de emissão! Você pode manter o mesmo número, corrigir os campos necessários e transmitir à SEFAZ.`, 8000);
        }
    } catch (err) {
        toast.error("Erro ao clonar NF-e: " + err.message);
    }
}

function abrirModalCancelarNfe(chave, protocolo) {
    const modal = document.getElementById("modal-cancelar-nfe");
    const inpChave = document.getElementById("modal-cancelar-chave");
    const inpDisp = document.getElementById("modal-cancelar-chave-display");
    const txtJust = document.getElementById("modal-cancelar-justificativa");

    if (inpChave) inpChave.value = chave;
    if (inpDisp) inpDisp.value = chave;
    if (txtJust) txtJust.value = "";
    if (modal) modal.style.display = "flex";
}

function fecharModalCancelarNfe() {
    const modal = document.getElementById("modal-cancelar-nfe");
    if (modal) modal.style.display = "none";
}

async function handleCancelarNfeModal(e) {
    e.preventDefault();
    const chave = document.getElementById("modal-cancelar-chave")?.value;
    const just = (document.getElementById("modal-cancelar-justificativa")?.value || "").trim();

    if (!chave || just.length < 15) {
        toast.error("A justificativa de cancelamento deve conter no mínimo 15 caracteres conforme exigência da SEFAZ.");
        return;
    }

    const confirma = await showConfirmModal({
        title: "CANCELAMENTO DEFINITIVO DE NF-e",
        message: `⚠️ ATENÇÃO - CANCELAMENTO DEFINITIVO DE NF-e NA SEFAZ\n\nTem certeza absoluta que deseja CANCELAR a nota fiscal:\nChave: ${chave}\n\nJustificativa:\n"${just}"\n\nEsta operação é IRREVERSÍVEL e anula totalmente o documento fiscal perante a Receita Federal.`,
        confirmText: "Sim, CANCELAR definitivamente",
        cancelText: "Voltar",
        danger: true,
        icon: "❌",
    });
    if (!confirma) {
        return;
    }

    try {
        const res = await apiPost("/api/emissao/nfe/cancelar", {
            chave: chave,
            justificativa: just,
            homologacao: AppState.ambiente === "homologacao",
        });

        fecharModalCancelarNfe();

        if (res.success) {
            await carregarNfeSaidas(1);
            abrirModalRetornoSefaz({
                autorizada: false,
                c_stat: res.data?.c_stat || "101",
                x_motivo: res.data?.motivo || "Cancelamento de NF-e homologado com sucesso",
                chave: chave,
                status_geral: "NF-e Cancelada Definitivamente na SEFAZ",
                explicacao_didatica: "O evento de cancelamento foi registrado nos servidores da SEFAZ. O documento fiscal não possui mais validade para circulação de mercadorias.",
                solucao_recomendada: "Nenhuma ação adicional é necessária. O status da nota foi atualizado para Cancelada no seu histórico.",
                tipo_retorno: "alerta"
            });
        } else {
            const errDetail = res.data?.detail || res.data?.error || "Rejeição no Cancelamento";
            abrirModalRetornoSefaz({
                autorizada: false,
                c_stat: res.data?.c_stat || "218",
                x_motivo: errDetail,
                chave: chave,
                status_geral: "Erro ao Cancelar NF-e na SEFAZ",
                explicacao_didatica: `A SEFAZ não homologou o cancelamento: ${errDetail}`,
                solucao_recomendada: "Verifique se o prazo limite legal de 24 horas da autorização já expirou ou se a nota possui manifestação de destinatário.",
                tipo_retorno: "erro"
            });
        }
    } catch (err) {
        fecharModalCancelarNfe();
        abrirModalRetornoSefaz({
            autorizada: false,
            c_stat: "ERR",
            x_motivo: err.message,
            chave: chave,
            status_geral: "Falha na Comunicação",
            explicacao_didatica: `Erro ao comunicar cancelamento com a SEFAZ: ${err.message}`,
            solucao_recomendada: "Verifique os logs e tente novamente.",
            tipo_retorno: "erro"
        });
    }
}

// ====================================================================
// CARTA DE CORREÇÃO ELETRÔNICA (CC-e)
// ====================================================================

function abrirCartaCorrecaoModal(chave, emitCnpj) {
    const modal = document.getElementById("modal-cce-nfe");
    const inpChave = document.getElementById("modal-cce-chave");
    const inpDisp = document.getElementById("modal-cce-chave-display");
    const txtCce = document.getElementById("modal-cce-texto");

    if (inpChave) inpChave.value = chave;
    if (inpDisp) inpDisp.value = chave;
    if (txtCce) txtCce.value = "";
    if (modal) modal.style.display = "flex";
}

function fecharModalCceNfe() {
    const modal = document.getElementById("modal-cce-nfe");
    if (modal) modal.style.display = "none";
}

async function handleCceModalSubmit(e) {
    e.preventDefault();
    const chave = document.getElementById("modal-cce-chave")?.value;
    const texto = (document.getElementById("modal-cce-texto")?.value || "").trim();

    if (!chave || texto.length < 15) {
        toast.error("O texto da Carta de Correção deve conter no mínimo 15 caracteres conforme exigência da SEFAZ.");
        return;
    }

    const confirma = await showConfirmModal({
        title: "Carta de Correção (CC-e)",
        message: `✍️ CONFIRMAÇÃO DE CARTA DE CORREÇÃO (CC-e)\n\nConfirma a transmissão desta CC-e para a SEFAZ?\n\nTexto a registrar:\n"${texto}"\n\nLembre-se: é expressamente proibido por lei alterar valores, alíquotas, dados que alterem emitente/destinatário ou datas.`,
        confirmText: "Sim, transmitir CC-e",
        cancelText: "Cancelar",
        icon: "✍️",
    });
    if (!confirma) {
        return;
    }

    const btn = document.getElementById("btn-transmitir-cce");
    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Transmitindo à SEFAZ..."; }

    try {
        const res = await apiPost("/api/emissao/nfe/cce", {
            chave: chave,
            correcao: texto,
            sequencia: 1
        });

        fecharModalCceNfe();

        if (res.success && res.data) {
            abrirModalRetornoSefaz({
                autorizada: true,
                c_stat: res.data.c_stat || "135",
                x_motivo: res.data.motivo || res.data.x_motivo || "Evento registrado e vinculado a NF-e",
                chave: chave,
                protocolo: res.data.protocolo,
                status_geral: "Carta de Correção (CC-e) Homologada na SEFAZ",
                explicacao_didatica: "A Carta de Correção foi transmitida, assinada digitalmente e homologada pelo Fisco com sucesso.",
                solucao_recomendada: "O evento foi vinculado à Chave de Acesso no banco de dados da Receita Federal.",
                tipo_retorno: "alerta"
            });
        } else {
            const errDetail = res.data?.detail || res.data?.error || "Rejeição na Carta de Correção";
            abrirModalRetornoSefaz({
                autorizada: false,
                c_stat: res.data?.c_stat || "494",
                x_motivo: errDetail,
                chave: chave,
                status_geral: "Erro na Carta de Correção SEFAZ",
                explicacao_didatica: `A SEFAZ não homologou o evento: ${errDetail}`,
                solucao_recomendada: "Verifique se o texto atende às regras e não tenta alterar campos não permitidos.",
                tipo_retorno: "erro"
            });
        }
    } catch (err) {
        fecharModalCceNfe();
        abrirModalRetornoSefaz({
            autorizada: false,
            c_stat: "ERR",
            x_motivo: err.message,
            chave: chave,
            status_geral: "Falha na Transmissão da CC-e",
            explicacao_didatica: `Erro de comunicação: ${err.message}`,
            solucao_recomendada: "Verifique os logs e tente novamente.",
            tipo_retorno: "erro"
        });
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

// ====================================================================
// ENVIO DE E-MAIL COM XML E DANFE PDF
// ====================================================================

function abrirModalEmailNfe(chave, destNome = "") {
    const modal = document.getElementById("modal-email-nfe");
    const inpChave = document.getElementById("modal-email-chave");
    const resDiv = document.getElementById("resultado-envio-email");
    const inpEmail = document.getElementById("modal-email-destinatario-email");

    if (inpChave) inpChave.value = chave;
    if (resDiv) { resDiv.style.display = "none"; resDiv.innerHTML = ""; }
    if (inpEmail) inpEmail.value = "";
    if (modal) modal.style.display = "flex";
}

function fecharModalEmailNfe() {
    const modal = document.getElementById("modal-email-nfe");
    if (modal) modal.style.display = "none";
}

async function handleEnviarEmailNfe(e) {
    e.preventDefault();
    const chave = document.getElementById("modal-email-chave")?.value;
    const email = (document.getElementById("modal-email-destinatario-email")?.value || "").trim();
    const assunto = document.getElementById("modal-email-assunto")?.value || "";
    const mensagem = document.getElementById("modal-email-mensagem")?.value || "";
    const resDiv = document.getElementById("resultado-envio-email");
    const btn = document.getElementById("btn-confirmar-envio-email");

    if (!chave || !email || !email.includes("@")) {
        toast.warning("Por favor, informe um endereço de e-mail válido.");
        return;
    }

    const confirma = await showConfirmModal({
        title: "Envio de E-mail",
        message: `📧 CONFIRMAÇÃO DE ENVIO POR E-MAIL\n\nDeseja realmente enviar o e-mail com os anexos XML e DANFE PDF para:\n${email}?`,
        confirmText: "Sim, enviar",
        cancelText: "Cancelar",
        icon: "📧",
    });
    if (!confirma) {
        return;
    }

    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Enviando e-mail com anexos..."; }

    try {
        const res = await apiPost("/api/emissao/enviar-email", {
            chave: chave,
            email: email,
            assunto: assunto,
            mensagem: mensagem
        });

        if (res.success) {
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#f0fdf4";
                resDiv.style.border = "1px solid #bbf7d0";
                resDiv.style.color = "#166534";
                resDiv.innerHTML = `<b>✓ Sucesso:</b> ${res.message || 'E-mail enviado com sucesso com XML e DANFE PDF anexados!'}`;
            }
            toast.success(`E-mail enviado com sucesso para ${email} com XML e DANFE PDF!`);
            setTimeout(() => {
                fecharModalEmailNfe();
            }, 1500);
        } else {
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#fef2f2";
                resDiv.style.border = "1px solid #fecaca";
                resDiv.style.color = "#991b1b";
                resDiv.innerHTML = `<b>❌ Erro no envio:</b> ${escapeHtml(res.detail || res.message || "Falha ao disparar e-mail.")}`;
            }
            toast.error(`Erro no envio do e-mail: ${res.detail || res.message || "Falha"}`);
        }
    } catch (err) {
        if (resDiv) {
            resDiv.style.display = "block";
            resDiv.style.background = "#fef2f2";
            resDiv.style.border = "1px solid #fecaca";
            resDiv.style.color = "#991b1b";
            resDiv.innerHTML = `<b>❌ Falha:</b> ${escapeHtml(err.message)}`;
        }
        toast.error(`Falha no envio: ${err.message}`);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

// ====================================================================
// INUTILIZAÇÃO OFICIAL DE FAIXA DE NUMERAÇÃO NA SEFAZ
// ====================================================================

function abrirModalInutilizarNfe() {
    const modal = document.getElementById("modal-inutilizar-nfe");
    const form = document.getElementById("form-modal-inutilizar-nfe");
    const selEmp = document.getElementById("modal-inut-empresa");
    const resDiv = document.getElementById("resultado-inutilizacao-nfe");

    if (form) form.reset();
    if (resDiv) { resDiv.style.display = "none"; resDiv.innerHTML = ""; }

    if (selEmp) {
        selEmp.innerHTML = "";
        const certs = AppState.certificados || [];
        if (certs.length === 0) {
            selEmp.innerHTML = `<option value="">Nenhuma empresa/certificado encontrado</option>`;
        } else {
            certs.forEach(c => {
                const opt = document.createElement("option");
                opt.value = c.cnpj;
                opt.textContent = `${c.razao_social || 'Filial'} (${formatarCpfCnpj(c.cnpj)})`;
                selEmp.appendChild(opt);
            });
            const empAtual = document.getElementById("filtro-saidas-empresa")?.value || document.getElementById("emissao-empresa-emit")?.value;
            if (empAtual) selEmp.value = empAtual;
        }
    }

    if (modal) modal.style.display = "flex";
}

function fecharModalInutilizarNfe() {
    const modal = document.getElementById("modal-inutilizar-nfe");
    if (modal) modal.style.display = "none";
}

async function handleInutilizarNfeModal(e) {
    e.preventDefault();
    const empCnpj = document.getElementById("modal-inut-empresa")?.value;
    const modelo = document.getElementById("modal-inut-modelo")?.value || "55";
    const serie = document.getElementById("modal-inut-serie")?.value || "1";
    const numIni = parseInt(document.getElementById("modal-inut-num-ini")?.value || 0);
    const numFim = parseInt(document.getElementById("modal-inut-num-fim")?.value || 0);
    const just = (document.getElementById("modal-inut-justificativa")?.value || "").trim();
    const resDiv = document.getElementById("resultado-inutilizacao-nfe");
    const btn = document.getElementById("btn-confirmar-inutilizacao");

    if (!empCnpj) {
        toast.warning("Selecione a empresa emitente.");
        return;
    }
    if (numIni <= 0 || numFim < numIni) {
        toast.error("Número inicial e final inválidos (o final não pode ser menor que o inicial).");
        return;
    }
    if (just.length < 15) {
        toast.error("A justificativa deve conter no mínimo 15 caracteres conforme exigência da SEFAZ.");
        return;
    }

    const confirma = await showConfirmModal({
        title: "Inutilizar Numeração",
        message: `Deseja realmente inutilizar a numeração ${numIni === numFim ? 'Nº ' + numIni : 'faixa ' + numIni + ' a ' + numFim} (Série ${serie}) perante a SEFAZ?`,
        confirmText: "Sim, inutilizar",
        cancelText: "Cancelar",
        danger: true,
        icon: "🚫",
    });
    if (!confirma) {
        return;
    }

    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Transmitindo à SEFAZ..."; }

    try {
        const payload = {
            empresa_cnpj: empCnpj,
            modelo: modelo,
            serie: serie,
            numero_inicial: numIni,
            numero_final: numFim,
            justificativa: just,
        };

        const res = await apiPost("/api/emissao/inutilizar", payload);

        if (res.success && res.data) {
            const d = res.data;
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#f0fdf4";
                resDiv.style.border = "1px solid #bbf7d0";
                resDiv.style.color = "#166534";
                resDiv.innerHTML = `
                    <div style="font-weight:bold;font-size:13px;margin-bottom:4px;">✓ Inutilização Homologada na SEFAZ (cStat: ${d.c_stat || '102'})</div>
                    <div><b>Protocolo SEFAZ:</b> <code>${d.protocolo || '—'}</code></div>
                    <div><b>Faixa Inutilizada:</b> Nº ${d.numero_inicial} a ${d.numero_final} (Série ${d.serie} - Mod ${d.modelo})</div>
                    <div><b>Data:</b> ${new Date(d.data_inutilizacao || Date.now()).toLocaleString('pt-BR')}</div>
                `;
            }
            toast.success(`Faixa Nº ${numIni} a ${numFim} inutilizada com sucesso! Protocolo SEFAZ: ${d.protocolo}`, 8000);
        } else {
            const msg = res.data?.detail || res.data?.error || "Rejeição na inutilização";
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#fef2f2";
                resDiv.style.border = "1px solid #fecaca";
                resDiv.style.color = "#991b1b";
                resDiv.innerHTML = `<p>Erro ao inutilizar: ${escapeHtml(msg)}</p>`;
            }
        }
    } catch (err) {
        if (resDiv) {
            resDiv.style.display = "block";
            resDiv.style.background = "#fef2f2";
            resDiv.style.border = "1px solid #fecaca";
            resDiv.style.color = "#991b1b";
            resDiv.innerHTML = `<p>Erro: ${escapeHtml(err.message)}</p>`;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}


// ====================================================================
// CONSULTA AUTOMÁTICA DE CNPJ NA RECEITA FEDERAL (ANTI-ERRO DE FUNCIONÁRIO)
// ====================================================================

async function consultarCnpjReceitaFederal(targetInputId) {
    const inputDoc = document.getElementById(targetInputId);
    if (!inputDoc) return;

    const rawVal = inputDoc.value || "";
    const cleanCnpj = rawVal.replace(/\D/g, "");

    if (cleanCnpj.length !== 14) {
        toast.warning("Por favor, digite um CNPJ válido com 14 dígitos para consultar na Receita Federal.");
        inputDoc.focus();
        return;
    }

    const btn = event?.target;
    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Buscando..."; }

    try {
        const res = await apiGet(`/api/emissao/consulta-cnpj/${cleanCnpj}`);
        const d = res.data?.data || res.data || {};
        if (res.success && d && d.razao_social) {
            // Se foi chamado a partir da tela de emissão de NF-e
            if (targetInputId.includes("dest") || targetInputId.includes("emissao")) {
                const setV = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
                setV("emissao-dest-nome", d.razao_social || d.nome_fantasia);
                setV("emissao-dest-cep", d.cep || "");
                setV("emissao-dest-logradouro", d.logradouro || "");
                setV("emissao-dest-numero", d.numero || "S/N");
                setV("emissao-dest-bairro", d.bairro || "");
                setV("emissao-dest-municipio", d.municipio || "");
                setV("emissao-dest-uf", d.uf || "SP");
                if (d.email) setV("emissao-dest-email", d.email);
                if (d.telefone) setV("emissao-dest-telefone", d.telefone);
                
                // Formata CNPJ no campo
                inputDoc.value = cleanCnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                
                toast.success(`Dados da empresa importados da Receita Federal! Razão Social: ${d.razao_social} | Endereço: ${d.logradouro}, ${d.numero} - ${d.municipio}/${d.uf} | Situação: ${d.situacao_cadastral || 'ATIVA'}`, 10000);
            } else if (targetInputId.includes("modal-cli") || targetInputId.includes("doc")) {
                // Se foi chamado no modal de cadastro de cliente
                const setV = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };
                setV("modal-cli-nome", d.razao_social);
                setV("modal-cli-fantasia", d.nome_fantasia || "");
                setV("modal-cli-cep", d.cep || "");
                setV("modal-cli-logr", d.logradouro || "");
                setV("modal-cli-num", d.numero || "S/N");
                setV("modal-cli-bairro", d.bairro || "");
                setV("modal-cli-mun", d.municipio || "");
                setV("modal-cli-uf", d.uf || "SP");
                if (d.email) setV("modal-cli-email", d.email);
                if (d.telefone) setV("modal-cli-fone", d.telefone);

                inputDoc.value = cleanCnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");

                toast.success(`Dados da empresa importados da Receita Federal! Razão Social: ${d.razao_social} | Localização: ${d.municipio}/${d.uf}`, 10000);
            }
        } else {
            toast.error(`Não foi possível obter os dados deste CNPJ: ${res.detail || "Erro na consulta"}`);
        }
    } catch (err) {
        toast.error(`Erro ao consultar CNPJ na Receita Federal: ${err.message}`);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

// ====================================================================
// FECHAMENTO CONTÁBIL MENSAL (EXPORTAÇÃO EM LOTE PARA CONTABILIDADE)
// ====================================================================

async function abrirModalFechamentoContabil() {
    const modal = document.getElementById("modal-fechamento-contabil");
    const selEmp = document.getElementById("fechamento-empresa-select");
    const resDiv = document.getElementById("resultado-fechamento-contabil");

    if (resDiv) { resDiv.style.display = "none"; resDiv.innerHTML = ""; }

    // Garante carregamento da lista de certificados digitais
    if (!AppState.certificados || AppState.certificados.length === 0) {
        try {
            const certRes = await apiGet("/api/certificado/list");
            if (certRes.success && Array.isArray(certRes.data)) {
                AppState.certificados = certRes.data;
            }
        } catch (e) {
            console.warn("Erro ao listar certificados:", e);
        }
    }

    if (selEmp) {
        selEmp.innerHTML = `<option value="">📦 TODAS AS 5 EMPRESAS / CERTIFICADOS (CONSOLIDADO)</option>`;
        const certs = AppState.certificados || [
            { cnpj: "34511185000110", razao_social: "JACKCELL CELULARES E IMPORTADOS LTDA", municipio: "Piracicaba" },
            { cnpj: "13787408000105", razao_social: "FERNANDES COMERCIO DE CELULARES E IMPORTACAO LTDA", municipio: "Piracicaba" },
            { cnpj: "44739622000101", razao_social: "FILIPE ALMEIDA GIL DE SOUZA LTDA", municipio: "Piracicaba" },
            { cnpj: "58186781000130", razao_social: "J DE A FERNANDES OPERACOES DE CREDITO", municipio: "Amparo" },
            { cnpj: "58495100000116", razao_social: "MI PLACE AMPARO LTDA", municipio: "Amparo" },
        ];

        certs.forEach((c, idx) => {
            const opt = document.createElement("option");
            opt.value = c.cnpj;
            const fmtDoc = (c.cnpj || '').replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
            opt.textContent = `🏢 ${idx + 1}. ${c.razao_social || 'Certificado'} (${fmtDoc}${c.municipio ? ' - ' + c.municipio : ''})`;
            selEmp.appendChild(opt);
        });
    }

    // Define mês atual por padrão
    const now = new Date();
    const curMonth = now.getMonth() + 1;
    const curYear = now.getFullYear();
    const selMes = document.getElementById("fechamento-mes-select");
    const selAno = document.getElementById("fechamento-ano-select");
    if (selMes) selMes.value = String(curMonth);
    if (selAno) selAno.value = String(curYear);

    if (modal) modal.style.display = "flex";

    // Calcula resumo instantâneo da competência
    atualizarResumoFechamentoContabil();
}

async function atualizarResumoFechamentoContabil() {
    const empCnpj = document.getElementById("fechamento-empresa-select")?.value || "";
    const mes = document.getElementById("fechamento-mes-select")?.value || "8";
    const ano = document.getElementById("fechamento-ano-select")?.value || "2026";
    const loadingBadge = document.getElementById("fechamento-badge-loading");
    const kpiAut = document.getElementById("fechamento-kpi-aut");
    const kpiCanc = document.getElementById("fechamento-kpi-canc");
    const kpiFat = document.getElementById("fechamento-kpi-fat");

    if (loadingBadge) loadingBadge.style.display = "inline";

    try {
        const url = `/api/emissao/fechamento-contabil/resumo?ano=${ano}&mes=${mes}${empCnpj ? '&empresa_cnpj=' + empCnpj : ''}`;
        const res = await apiGet(url);
        const stats = res.data?.data || res.data || {};

        if (kpiAut) kpiAut.textContent = stats.autorizadas || 0;
        if (kpiCanc) kpiCanc.textContent = stats.canceladas || 0;
        if (kpiFat) {
            const fat = parseFloat(stats.faturamento_total || 0);
            kpiFat.textContent = `R$ ${fat.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
    } catch (err) {
        console.warn("Erro ao calcular resumo do fechamento:", err);
    } finally {
        if (loadingBadge) loadingBadge.style.display = "none";
    }
}

function fecharModalFechamentoContabil() {
    const modal = document.getElementById("modal-fechamento-contabil");
    if (modal) modal.style.display = "none";
}

function baixarFechamentoContabilZip() {
    const empCnpj = document.getElementById("fechamento-empresa-select")?.value || "";
    const mes = document.getElementById("fechamento-mes-select")?.value || "8";
    const ano = document.getElementById("fechamento-ano-select")?.value || "2026";

    const url = `/api/emissao/fechamento-contabil/download?ano=${ano}&mes=${mes}${empCnpj ? '&empresa_cnpj=' + empCnpj : ''}`;
    const defaultName = `Fechamento_Fiscal_${ano}_${mes.padStart(2, '0')}.zip`;

    apiDownload(url, defaultName).then((res) => {
        const resDiv = document.getElementById("resultado-fechamento-contabil");
        if (res.ok) {
            const blobUrl = window.URL.createObjectURL(res.blob);
            const a = document.createElement("a");
            a.href = blobUrl;
            a.download = res.filename || defaultName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(blobUrl);

            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#f0fdf4";
                resDiv.style.border = "1px solid #bbf7d0";
                resDiv.style.color = "#166534";
                resDiv.innerHTML = `<b>✓ Download Iniciado com Sucesso:</b> O arquivo compactado ZIP contendo 100% dos XMLs do mês (organizados por certificado) e o Relatório CSV de Faturamento está sendo baixado.`;
            }
        } else {
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#fef2f2";
                resDiv.style.border = "1px solid #fecaca";
                resDiv.style.color = "#991b1b";
                resDiv.innerHTML = `<b>✗ Erro no download:</b> ${escapeHtml(res.error || "Falha desconhecida")}. Faça login novamente se a sessão expirou.`;
            }
        }
    });
}

async function enviarFechamentoContadorModal() {
    const empCnpj = document.getElementById("fechamento-empresa-select")?.value || "";
    const mes = document.getElementById("fechamento-mes-select")?.value || "8";
    const ano = document.getElementById("fechamento-ano-select")?.value || "2026";
    const email = (document.getElementById("fechamento-contador-email")?.value || "").trim();
    const resDiv = document.getElementById("resultado-fechamento-contabil");
    const btn = document.getElementById("btn-enviar-contador");

    if (!email || !email.includes("@")) {
        toast.warning("Por favor, preencha um e-mail válido para a contabilidade.");
        document.getElementById("fechamento-contador-email")?.focus();
        return;
    }

    const confirma = await showConfirmModal({
        title: "Enviar Fechamento Fiscal",
        message: `Deseja realmente enviar o pacote de Fechamento Fiscal (${mes.padStart(2, '0')}/${ano}) diretamente para o e-mail: ${email}?`,
        confirmText: "Sim, enviar",
        cancelText: "Cancelar",
        icon: "📧",
    });
    if (!confirma) {
        return;
    }

    const origText = btn ? btn.innerHTML : "";
    if (btn) { btn.disabled = true; btn.innerHTML = "⏳ Enviando..."; }

    try {
        const payload = {
            empresa_cnpj: empCnpj || null,
            ano: parseInt(ano),
            mes: parseInt(mes),
            email: email,
        };

        const res = await apiPost("/api/emissao/fechamento-contabil/enviar-contador", payload);
        if (res.success) {
            if (resDiv) {
                resDiv.style.display = "block";
                resDiv.style.background = "#f0fdf4";
                resDiv.style.border = "1px solid #bbf7d0";
                resDiv.style.color = "#166534";
                resDiv.innerHTML = `<b>✓ Sucesso:</b> ${escapeHtml(res.message || "Fechamento enviado com sucesso!")}`;
            }
            toast.success(`Fechamento Contábil despachado com sucesso para ${email}!`);
        } else {
            toast.error(`Falha no envio: ${res.detail || "Erro ao enviar ao contador"}`);
        }
    } catch (err) {
        toast.error(`Erro no envio: ${err.message}`);
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    }
}

// ====================================================================
// MONITOR DE STATUS DO WEB SERVICE SEFAZ EM TEMPO REAL (SEMÁFORO)
// ====================================================================

async function verificarStatusSefazRealtime(manual = false) {
    const badge = document.getElementById("badge-sefaz-status");
    const dot = document.getElementById("sefaz-status-dot");
    const label = document.getElementById("sefaz-status-label");

    if (label && manual) label.textContent = "Testando SEFAZ...";

    try {
        const res = await apiGet(`/api/emissao/sefaz-status?homologacao=${AppState.ambiente === "homologacao"}`);
        const d = res.data?.data || res.data || {};
        if (res.success && (d.online !== undefined || d.c_stat)) {
            if (d.online) {
                if (dot) dot.style.background = "#22c55e";
                if (label) label.textContent = `SEFAZ-SP: Online (${d.tempo_resposta_ms || 85}ms)`;
                if (badge) {
                    badge.style.background = "#f0fdf4";
                    badge.style.borderColor = "#bbf7d0";
                    badge.style.color = "#166534";
                }
                if (manual) {
                    toast.success(`SEFAZ-SP 100% Operacional! Código SEFAZ: cStat ${d.c_stat || '107'} (${d.x_motivo || 'Serviço em Operação'}) | Tempo de Resposta: ${d.tempo_resposta_ms || 85}ms | Ambiente: ${d.ambiente || 'Homologação'} | Data/Hora: ${d.data_hora || new Date().toLocaleString('pt-BR')}`, 10000);
                }
            } else {
                if (dot) dot.style.background = "#ef4444";
                if (label) label.textContent = `SEFAZ-SP: Instável (${d.c_stat || '999'})`;
                if (badge) {
                    badge.style.background = "#fef2f2";
                    badge.style.borderColor = "#fecaca";
                    badge.style.color = "#991b1b";
                }
                if (manual) {
                    toast.error(`Alerta de Indisponibilidade SEFAZ: Retorno: ${d.x_motivo || 'Instabilidade temporária'} (cStat ${d.c_stat || '999'}) | Verifique o certificado e o servidor da Fazenda.`, 10000);
                }
            }
        }
    } catch (err) {
        console.warn("Erro ao consultar status SEFAZ:", err);
        if (dot) dot.style.background = "#eab308";
        if (label) label.textContent = "SEFAZ-SP: Offline";
    }
}

// ====================================================================
// IMPORTAÇÃO EM MASSA DE XMLs / ZIPs DE SAÍDA
// ====================================================================

let arquivosImportacaoSelecionados = [];

function abrirModalImportarSaidas() {
    const modal = document.getElementById("modal-importar-saidas");
    const statusDiv = document.getElementById("status-import-saidas");
    const btn = document.getElementById("btn-iniciar-import-saidas");

    arquivosImportacaoSelecionados = [];
    if (statusDiv) { statusDiv.style.display = "none"; statusDiv.innerHTML = ""; }
    if (btn) btn.style.display = "none";
    if (modal) modal.style.display = "flex";
}

function fecharModalImportarSaidas() {
    const modal = document.getElementById("modal-importar-saidas");
    if (modal) modal.style.display = "none";
}

function handleSelecionarArquivosImport(files) {
    if (!files || files.length === 0) return;
    arquivosImportacaoSelecionados = Array.from(files);

    const statusDiv = document.getElementById("status-import-saidas");
    const btn = document.getElementById("btn-iniciar-import-saidas");

    if (statusDiv) {
        statusDiv.style.display = "block";
        statusDiv.style.background = "#eef2f6";
        statusDiv.style.color = "#1b4f72";
        statusDiv.innerHTML = `📁 <b>${files.length}</b> arquivo(s) selecionado(s) pronto(s) para importação.`;
    }
    if (btn) btn.style.display = "inline-block";
}

async function executarImportacaoSaidas() {
    if (!arquivosImportacaoSelecionados || arquivosImportacaoSelecionados.length === 0) {
        toast.warning("Selecione os arquivos XML ou ZIP primeiro.");
        return;
    }

    const statusDiv = document.getElementById("status-import-saidas");
    const btn = document.getElementById("btn-iniciar-import-saidas");
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Importando e Indexando..."; }

    if (statusDiv) {
        statusDiv.innerHTML = `⏳ Processando arquivos e indexando no banco de dados SQLite...`;
    }

    try {
        const formData = new FormData();
        arquivosImportacaoSelecionados.forEach(f => {
            formData.append("arquivos", f);
        });

        const res = await apiUploadForm("/api/emissao/importar-xmls", formData);
        const data = res.data || {};

        if (res.success && data.success) {
            if (statusDiv) {
                statusDiv.style.background = "#f0fdf4";
                statusDiv.style.color = "#166534";
                statusDiv.innerHTML = `
                    <div style="font-weight:bold;font-size:13px;">✓ Importação Concluída com Sucesso!</div>
                    <div style="margin-top:4px;"><b>Processados:</b> ${data.total_processados} | <b>Importados:</b> ${data.total_importados}</div>
                `;
            }
            await carregarNfeSaidas(1);
            if (btn) btn.style.display = "none";
        } else {
            if (statusDiv) {
                statusDiv.style.background = "#fef2f2";
                statusDiv.style.color = "#991b1b";
                statusDiv.innerHTML = `Erro na importação: ${data.detail || "Falha ao processar arquivos"}`;
            }
        }
    } catch (err) {
        if (statusDiv) {
            statusDiv.style.background = "#fef2f2";
            statusDiv.style.color = "#991b1b";
            statusDiv.innerHTML = `Erro: ${err.message}`;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "⚡ Iniciar Importação"; }
    }
}

// ====================================================================
// CADASTRO DE CLIENTES
// ====================================================================

async function carregarTabelaCadClientes() {
    const tbody = document.getElementById("tbody-cad-clientes");
    if (!tbody) return;

    try {
        const res = await apiGet("/api/emissao/clientes");
        const lista = res.data?.clientes || res.clientes || [];
        AppState.clientesCad = lista;
        renderizarListaClientes(lista);
    } catch (err) {
        console.warn("Erro ao carregar clientes:", err);
    }
}

function filtrarTabelaClientes(termo) {
    const t = (termo || "").trim().toLowerCase();
    if (!t) {
        renderizarListaClientes(AppState.clientesCad || []);
        return;
    }
    const filtrados = (AppState.clientesCad || []).filter(c =>
        (c.razao_social || "").toLowerCase().includes(t) ||
        (c.cpf_cnpj || "").includes(t) ||
        (c.email || "").toLowerCase().includes(t) ||
        (c.municipio || "").toLowerCase().includes(t)
    );
    renderizarListaClientes(filtrados);
}

function renderizarListaClientes(lista) {
    const tbody = document.getElementById("tbody-cad-clientes");
    if (!tbody) return;

    if (!lista || lista.length === 0) {
        renderEmptyState({
            icon: '👥',
            title: 'Nenhum cliente cadastrado',
            description: 'Comece adicionando seu primeiro cliente para usar nas emissões de NF-e.',
            actionHtml: '<button class="botao botao-primario" onclick="abrirModalNovoCliente()">➕ Cadastrar primeiro cliente</button>',
            containerId: 'tbody-cad-clientes',
        });
        return;
    }

    tbody.innerHTML = lista.map((c, i) => `
        <tr class="linha">
            <td style="text-align:center;">${i + 1}</td>
            <td style="text-align:center;"><code>${c.cpf_cnpj}</code></td>
            <td><b>${escapeHtml(c.razao_social)}</b> ${c.nome_fantasia ? `<br><small style="color:#64748b;">${escapeHtml(c.nome_fantasia)}</small>` : ""}</td>
            <td style="text-align:center;">${c.tipo_pessoa || (c.cpf_cnpj.length === 11 ? 'PF' : 'PJ')} ${c.ie ? `<br><small>IE: ${c.ie}</small>` : ""}</td>
            <td>${escapeHtml(c.municipio || "—")} / ${c.uf || "—"}</td>
            <td>${escapeHtml(c.telefone || "—")}</td>
            <td>${escapeHtml(c.email || "—")}</td>
            <td style="text-align:center;">
                <div class="actions-cell" style="justify-content:center;gap:4px;flex-wrap:wrap;">
                    <button type="button" class="btn-action" onclick="visualizarClienteCad(${c.id});" title="Visualizar todos os dados do cliente" style="background:#e0f2fe;color:#0369a1;border-color:#bae6fd;font-weight:600;padding:2px 7px;">👁️ Ver</button>
                    <button type="button" class="btn-action" onclick="abrirModalEditarCliente(${c.id});" title="Editar dados cadastrais do cliente" style="background:#fef3c7;color:#92400e;border-color:#fde68a;font-weight:600;padding:2px 7px;">✏️ Editar</button>
                    <button type="button" class="btn-action btn-action-primary" onclick="usarClienteNaEmissao('${c.cpf_cnpj}');" title="Usar este cliente na emissão de NF-e" style="padding:2px 7px;">📄 Usar</button>
                    <button type="button" class="btn-action" onclick="excluirClienteCad(${c.id});" style="color:#c0392b;padding:2px 7px;" title="Excluir cliente">🗑️</button>
                </div>
            </td>
        </tr>
    `).join("");
}

function abrirModalNovoCliente() {
    const modal = document.getElementById("modal-cad-cliente");
    const form = document.getElementById("form-modal-cliente");
    const tit = document.getElementById("modal-cliente-titulo");
    const btn = document.getElementById("btn-salvar-modal-cliente");
    const idInput = document.getElementById("modal-cli-id");

    if (form) form.reset();
    if (idInput) idInput.value = "";
    if (tit) tit.textContent = "👥 Cadastrar Novo Cliente / Destinatário";
    if (btn) btn.textContent = "💾 Salvar Cliente";

    const uf = document.getElementById("modal-cli-uf");
    if (uf) uf.value = "SP";
    const indIe = document.getElementById("modal-cli-ind-ie");
    if (indIe) indIe.value = "9";

    if (modal) modal.style.display = "flex";
}

function abrirModalEditarCliente(id) {
    const cliente = (AppState.clientesCad || []).find(c => c.id === id);
    if (!cliente) {
        toast.error("Cliente não encontrado.");
        return;
    }

    const modal = document.getElementById("modal-cad-cliente");
    const tit = document.getElementById("modal-cliente-titulo");
    const btn = document.getElementById("btn-salvar-modal-cliente");
    const idInput = document.getElementById("modal-cli-id");

    if (idInput) idInput.value = cliente.id || "";
    if (tit) tit.textContent = `✏️ Editar Cliente: ${cliente.razao_social}`;
    if (btn) btn.textContent = "💾 Salvar Alterações";

    const setVal = (fieldId, val) => {
        const el = document.getElementById(fieldId);
        if (el) el.value = val || "";
    };

    setVal("modal-cli-doc", cliente.cpf_cnpj);
    setVal("modal-cli-nome", cliente.razao_social);
    setVal("modal-cli-fantasia", cliente.nome_fantasia);
    setVal("modal-cli-ind-ie", cliente.indicador_ie !== undefined ? cliente.indicador_ie : 9);
    setVal("modal-cli-ie", cliente.ie);
    setVal("modal-cli-email", cliente.email);
    setVal("modal-cli-tel", cliente.telefone);
    setVal("modal-cli-cep", cliente.cep);
    setVal("modal-cli-logr", cliente.logradouro);
    setVal("modal-cli-num", cliente.numero);
    setVal("modal-cli-bairro", cliente.bairro);
    setVal("modal-cli-mun", cliente.municipio);
    setVal("modal-cli-uf", cliente.uf || "SP");

    if (modal) modal.style.display = "flex";
}

function fecharModalCliente() {
    const modal = document.getElementById("modal-cad-cliente");
    if (modal) modal.style.display = "none";
}

function visualizarClienteCad(id) {
    const c = (AppState.clientesCad || []).find(cli => cli.id === id);
    if (!c) {
        toast.error("Cliente não encontrado.");
        return;
    }

    const modal = document.getElementById("modal-visualizar-cliente");
    const container = document.getElementById("conteudo-modal-visualizar-cliente");
    if (!container || !modal) return;

    const tipoDesc = (c.tipo_pessoa === "PJ" || (c.cpf_cnpj && c.cpf_cnpj.length === 14)) ? "Pessoa Jurídica (PJ)" : "Pessoa Física (PF)";
    const indIeDesc = c.indicador_ie == 1 ? "1 - Contribuinte ICMS" : (c.indicador_ie == 2 ? "2 - Contribuinte Isento" : "9 - Não Contribuinte");

    container.innerHTML = `
        <!-- Identificação -->
        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;padding:14px;margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
                <div style="font-size:16px;font-weight:bold;color:#1e293b;">
                    ${escapeHtml(c.razao_social || "NOME NÃO INFORMADO")}
                </div>
                <span class="badge badge-info" style="font-size:12px;padding:4px 10px;">${tipoDesc}</span>
            </div>
            ${c.nome_fantasia ? `<div style="font-size:12.5px;color:#475569;margin-bottom:8px;"><b>Nome Fantasia:</b> ${escapeHtml(c.nome_fantasia)}</div>` : ""}
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:10px;font-size:12px;color:#334155;margin-top:8px;border-top:1px dashed #cbd5e1;padding-top:8px;">
                <div><b>CPF / CNPJ:</b> <code style="font-size:12.5px;">${c.cpf_cnpj || "—"}</code></div>
                <div><b>Inscrição Estadual (IE):</b> ${c.ie || "Isento / Não Informado"}</div>
                <div><b>Indicador de IE:</b> ${indIeDesc}</div>
            </div>
        </div>

        <div style="display:flex;gap:14px;flex-wrap:wrap;">
            <!-- Contato -->
            <div style="flex:1;min-width:260px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-weight:bold;font-size:13px;color:#1b4f72;margin-bottom:10px;border-bottom:1px solid #f1f5f9;padding-bottom:6px;">
                    📞 Contatos & Comunicação
                </div>
                <div style="font-size:12.5px;color:#334155;line-height:1.7;">
                    <div><b>Telefone / Celular:</b> ${c.telefone ? `<a href="tel:${c.telefone}" style="color:#0284c7;text-decoration:none;">${escapeHtml(c.telefone)}</a>` : "Não cadastrado"}</div>
                    <div><b>E-mail:</b> ${c.email ? `<a href="mailto:${escapeHtml(c.email)}" style="color:#0284c7;text-decoration:none;">${escapeHtml(c.email)}</a>` : "Não cadastrado"}</div>
                </div>
            </div>

            <!-- Endereço Fiscal -->
            <div style="flex:1.4;min-width:280px;background:#fff;border:1px solid #e2e8f0;border-radius:6px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-weight:bold;font-size:13px;color:#1b4f72;margin-bottom:10px;border-bottom:1px solid #f1f5f9;padding-bottom:6px;">
                    📍 Endereço Fiscal Completo
                </div>
                <div style="font-size:12.5px;color:#334155;line-height:1.7;">
                    <div><b>Logradouro:</b> ${escapeHtml(c.logradouro || "Não informado")}${c.numero ? `, Nº ${escapeHtml(c.numero)}` : ""}${c.complemento ? ` (${escapeHtml(c.complemento)})` : ""}</div>
                    <div><b>Bairro:</b> ${escapeHtml(c.bairro || "Não informado")}</div>
                    <div><b>Município / UF:</b> ${escapeHtml(c.municipio || "São Paulo")} / ${c.uf || "SP"}</div>
                    <div><b>CEP:</b> ${c.cep ? `${c.cep.slice(0, 5)}-${c.cep.slice(5)}` : "—"}</div>
                    <div style="font-size:11px;color:#64748b;margin-top:4px;"><b>Cód. IBGE Município:</b> ${c.cod_municipio || "3550308"}</div>
                </div>
            </div>
        </div>
    `;

    const btnUsar = document.getElementById("btn-vis-usar-emissao");
    if (btnUsar) {
        btnUsar.onclick = () => {
            fecharModalVisualizarCliente();
            usarClienteNaEmissao(c.cpf_cnpj);
        };
    }

    const btnEdit = document.getElementById("btn-vis-editar-cliente");
    if (btnEdit) {
        btnEdit.onclick = () => {
            fecharModalVisualizarCliente();
            abrirModalEditarCliente(c.id);
        };
    }

    modal.style.display = "flex";
}

function fecharModalVisualizarCliente() {
    const modal = document.getElementById("modal-visualizar-cliente");
    if (modal) modal.style.display = "none";
}

async function salvarClienteModal(e) {
    e.preventDefault();
    const cliId = document.getElementById("modal-cli-id")?.value;
    const doc = (document.getElementById("modal-cli-doc")?.value || "").replace(/\D/g, "");
    const nome = (document.getElementById("modal-cli-nome")?.value || "").trim().toUpperCase();
    const fantasia = (document.getElementById("modal-cli-fantasia")?.value || "").trim().toUpperCase();
    const indIe = parseInt(document.getElementById("modal-cli-ind-ie")?.value || 9);
    const ie = document.getElementById("modal-cli-ie")?.value || "";
    const email = document.getElementById("modal-cli-email")?.value || "";
    const tel = document.getElementById("modal-cli-tel")?.value || "";
    const cep = (document.getElementById("modal-cli-cep")?.value || "").replace(/\D/g, "");
    const logr = document.getElementById("modal-cli-logr")?.value || "";
    const num = document.getElementById("modal-cli-num")?.value || "";
    const bairro = document.getElementById("modal-cli-bairro")?.value || "";
    const mun = document.getElementById("modal-cli-mun")?.value || "";
    const uf = (document.getElementById("modal-cli-uf")?.value || "SP").toUpperCase();

    if (!doc || !nome) {
        toast.warning("CPF/CNPJ e Razão Social são obrigatórios.");
        return;
    }

    try {
        const payload = {
            cpf_cnpj: doc,
            razao_social: nome,
            nome_fantasia: fantasia,
            indicador_ie: indIe,
            ie: ie,
            email: email,
            telefone: tel,
            cep: cep,
            logradouro: logr,
            numero: num,
            bairro: bairro,
            municipio: mun,
            uf: uf,
        };
        if (cliId) {
            payload.id = parseInt(cliId);
        }

        const res = await apiPost("/api/emissao/clientes", payload);

        if (res.success && res.data?.success !== false) {
            fecharModalCliente();
            await carregarTabelaCadClientes();
            await carregarSelectClientesEmissao();
            toast.success("Cliente salvo com sucesso!");
        } else {
            const msg = res.data?.detail || res.data?.error || "Falha ao salvar cliente.";
            toast.error("Erro ao salvar cliente: " + msg);
        }
    } catch (err) {
        toast.error("Erro: " + err.message);
    }
}

function usarClienteNaEmissao(doc) {
    switchEmissaoTab("form");
    const sel = document.getElementById("emissao-select-cliente-rapido");
    if (sel) sel.value = doc;
    selecionarClientePreCadastrado(doc);
}

async function excluirClienteCad(id) {
    const confirma = await showConfirmModal({
        title: "Excluir Cliente",
        message: "Deseja realmente excluir este cliente do cadastro?",
        confirmText: "Sim, excluir",
        cancelText: "Cancelar",
        danger: true,
        icon: "🗑️",
    });
    if (!confirma) return;
    try {
        const res = await apiRequest(`/api/emissao/clientes/${id}`, { method: "DELETE" });
        if (res.success) {
            await carregarTabelaCadClientes();
            await carregarSelectClientesEmissao();
            toast.success("Cliente excluído com sucesso.");
        }
    } catch (err) {
        toast.error("Erro ao excluir cliente: " + err.message);
    }
}

// ====================================================================
// CATÁLOGO DE PRODUTOS
// ====================================================================

async function carregarTabelaCadProdutos() {
    const tbody = document.getElementById("tbody-cad-produtos");
    if (!tbody) return;

    try {
        const res = await apiGet("/api/emissao/produtos");
        const lista = res.data?.produtos || res.produtos || [];
        AppState.produtosCad = lista;
        renderizarListaProdutos(lista);
    } catch (err) {
        console.warn("Erro ao carregar produtos:", err);
    }
}

function filtrarTabelaProdutos(termo) {
    const t = (termo || "").trim().toLowerCase();
    if (!t) {
        renderizarListaProdutos(AppState.produtosCad || []);
        return;
    }
    const filtrados = (AppState.produtosCad || []).filter(p =>
        (p.descricao || "").toLowerCase().includes(t) ||
        (p.codigo || "").toLowerCase().includes(t) ||
        (p.ncm || "").includes(t) ||
        (p.gtin || "").includes(t)
    );
    renderizarListaProdutos(filtrados);
}

function renderizarListaProdutos(lista) {
    const tbody = document.getElementById("tbody-cad-produtos");
    if (!tbody) return;

    if (!lista || lista.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:25px;color:#888;">Nenhum produto cadastrado. Clique em <b>➕ Novo Produto</b>.</td></tr>`;
        return;
    }

    const origens = { 0: "Nacional", 1: "Imp. Direta", 2: "Imp. Interna" };

    tbody.innerHTML = lista.map((p, i) => `
        <tr class="linha">
            <td style="text-align:center;">${i + 1}</td>
            <td><code>${escapeHtml(p.codigo)}</code></td>
            <td><b>${escapeHtml(p.descricao)}</b> ${p.gtin ? `<br><small style="color:#64748b;">EAN: ${p.gtin}</small>` : ""} ${p.marca ? `<span class="badge badge-info" style="font-size:10px;margin-left:4px;">${escapeHtml(p.marca)}</span>` : ""}</td>
            <td style="text-align:center;"><code>${escapeHtml(p.ncm)}</code></td>
            <td style="text-align:center;">${escapeHtml(p.cfop_padrao || "5102")} / <small style="color:#64748b;">${escapeHtml(p.cfop_interestadual || "6102")}</small></td>
            <td style="text-align:center;">${escapeHtml(p.unidade || "UN")}</td>
            <td style="text-align:right;font-weight:bold;color:#27ae60;">R$ ${parseFloat(p.preco_venda || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td style="text-align:center;"><small>${origens[p.origem] || "Nacional"}</small></td>
            <td style="text-align:center;">
                <div class="actions-cell" style="justify-content:center;gap:4px;flex-wrap:wrap;">
                    <button type="button" class="btn-action" onclick="visualizarProdutoCad(${p.id});" title="Visualizar ficha fiscal e técnica" style="background:#e0f2fe;color:#0369a1;border-color:#bae6fd;font-weight:600;padding:2px 7px;">👁️ Ver</button>
                    <button type="button" class="btn-action" onclick="abrirModalEditarProduto(${p.id});" title="Editar dados cadastrais do produto" style="background:#fef3c7;color:#92400e;border-color:#fde68a;font-weight:600;padding:2px 7px;">✏️ Editar</button>
                    <button type="button" class="btn-action btn-action-primary" onclick="usarProdutoNaEmissao('${p.codigo}');" title="Adicionar à emissão de NF-e" style="padding:2px 7px;">➕ Usar</button>
                    <button type="button" class="btn-action" onclick="excluirProdutoCad(${p.id});" style="color:#c0392b;padding:2px 7px;" title="Excluir produto">🗑️</button>
                </div>
            </td>
        </tr>
    `).join("");
}

let timeoutSugestaoFiscal = null;
let ultimaSugestaoFiscal = null;

function handleDescricaoProdutoInput(valor) {
    clearTimeout(timeoutSugestaoFiscal);
    const box = document.getElementById("box-sugestao-fiscal");
    if (!valor || valor.trim().length < 3) {
        if (box) box.style.display = "none";
        return;
    }

    timeoutSugestaoFiscal = setTimeout(async () => {
        try {
            const res = await apiGet(`/api/emissao/produtos/sugerir-fiscal?termo=${encodeURIComponent(valor)}`);
            if (res.success && res.data) {
                ultimaSugestaoFiscal = res.data;
                const sug = res.data;
                const sugDetalhes = document.getElementById("sug-detalhes");
                if (sugDetalhes && box) {
                    sugDetalhes.innerHTML = `<b>NCM:</b> ${sug.ncm} | <b>CFOP:</b> ${sug.cfop_padrao} / ${sug.cfop_interestadual} | <b>UN:</b> ${sug.unidade} | <b>CSOSN:</b> ${sug.csosn_cst}${sug.cest ? ` | <b>CEST:</b> ${sug.cest}` : ""} <small style="color:#047857;font-weight:600;">(${sug.fonte})</small>`;
                    box.style.display = "flex";
                }
            }
        } catch (err) {
            console.warn("Erro ao buscar sugestão fiscal:", err);
        }
    }, 300);
}

function aplicarSugestaoFiscalProduto() {
    if (!ultimaSugestaoFiscal) return;
    const sug = ultimaSugestaoFiscal;

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el && val !== undefined && val !== null) el.value = val;
    };

    setVal("modal-prod-ncm", sug.ncm);
    if (sug.cest) setVal("modal-prod-cest", sug.cest);
    setVal("modal-prod-cfop", sug.cfop_padrao);
    setVal("modal-prod-cfop-inter", sug.cfop_interestadual);
    setVal("modal-prod-un", sug.unidade);
    setVal("modal-prod-csosn", sug.csosn_cst || "102");
    if (sug.origem !== undefined) setVal("modal-prod-origem", sug.origem);

    const precoEl = document.getElementById("modal-prod-preco");
    if (precoEl && (!precoEl.value || parseFloat(precoEl.value) === 0) && sug.preco_sugerido) {
        precoEl.value = sug.preco_sugerido.toFixed(2);
    }

    const box = document.getElementById("box-sugestao-fiscal");
    if (box) box.style.display = "none";
}

function abrirModalNovoProduto() {
    const modal = document.getElementById("modal-cad-produto");
    const form = document.getElementById("form-modal-produto");
    const tit = document.getElementById("modal-produto-titulo");
    const btn = document.getElementById("btn-salvar-modal-produto");
    const idInput = document.getElementById("modal-prod-id");
    const boxSug = document.getElementById("box-sugestao-fiscal");

    if (form) form.reset();
    if (idInput) idInput.value = "";
    if (tit) tit.textContent = "📦 Cadastrar Novo Produto / Item";
    if (btn) btn.textContent = "💾 Salvar Produto";
    if (boxSug) boxSug.style.display = "none";

    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    setVal("modal-prod-ncm", "85171300");
    setVal("modal-prod-cest", "21.053.00");
    setVal("modal-prod-cfop", "5102");
    setVal("modal-prod-cfop-inter", "6102");
    setVal("modal-prod-un", "UN");
    setVal("modal-prod-csosn", "102");
    setVal("modal-prod-origem", "0");
    setVal("modal-prod-estoque", "1");

    if (modal) modal.style.display = "flex";
}

function abrirModalEditarProduto(id) {
    const prod = (AppState.produtosCad || []).find(p => p.id === id);
    if (!prod) {
        toast.error("Produto não encontrado.");
        return;
    }

    const modal = document.getElementById("modal-cad-produto");
    const tit = document.getElementById("modal-produto-titulo");
    const btn = document.getElementById("btn-salvar-modal-produto");
    const idInput = document.getElementById("modal-prod-id");
    const boxSug = document.getElementById("box-sugestao-fiscal");

    if (idInput) idInput.value = prod.id || "";
    if (tit) tit.textContent = `✏️ Editar Produto: ${prod.descricao}`;
    if (btn) btn.textContent = "💾 Salvar Alterações";
    if (boxSug) boxSug.style.display = "none";

    const setVal = (fieldId, val) => {
        const el = document.getElementById(fieldId);
        if (el) el.value = (val !== undefined && val !== null) ? val : "";
    };

    setVal("modal-prod-cod", prod.codigo);
    setVal("modal-prod-desc", prod.descricao);
    setVal("modal-prod-ncm", prod.ncm || "85171300");
    setVal("modal-prod-cest", prod.cest || "");
    setVal("modal-prod-cfop", prod.cfop_padrao || "5102");
    setVal("modal-prod-cfop-inter", prod.cfop_interestadual || "6102");
    setVal("modal-prod-csosn", prod.csosn_cst || "102");
    setVal("modal-prod-origem", prod.origem !== undefined ? prod.origem : 0);
    setVal("modal-prod-un", prod.unidade || "UN");
    setVal("modal-prod-preco", prod.preco_venda || 0);
    setVal("modal-prod-custo", prod.preco_custo || 0);
    setVal("modal-prod-estoque", prod.estoque_atual || 0);
    setVal("modal-prod-gtin", prod.gtin || "");
    setVal("modal-prod-imei", prod.imei || "");
    setVal("modal-prod-marca", prod.marca || "");

    if (modal) modal.style.display = "flex";
}

function fecharModalProduto() {
    const modal = document.getElementById("modal-cad-produto");
    if (modal) modal.style.display = "none";
}

function visualizarProdutoCad(id) {
    const p = (AppState.produtosCad || []).find(prod => prod.id === id);
    if (!p) {
        toast.error("Produto não encontrado.");
        return;
    }

    const modal = document.getElementById("modal-visualizar-produto");
    const container = document.getElementById("conteudo-modal-visualizar-produto");
    if (!container || !modal) return;

    const origens = { 0: "0 - Nacional (exceto indicadas nos códigos 3 a 5)", 1: "1 - Estrangeira (Importação Direta)", 2: "2 - Estrangeira (Adquirida no Mercado Interno)" };
    const csosnMap = {
        "102": "102 - Tributada pelo Simples Nacional sem permissão de crédito",
        "500": "500 - ICMS cobrado anteriormente por ST",
        "101": "101 - Tributada pelo Simples Nacional com permissão de crédito",
        "400": "400 - Não tributada pelo Simples Nacional",
        "900": "900 - Outros"
    };

    container.innerHTML = `
        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;padding:14px;margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
                <div style="font-size:16px;font-weight:bold;color:#1e293b;">
                    ${escapeHtml(p.descricao || "PRODUTO")}
                </div>
                <span class="badge badge-info" style="font-size:12px;padding:4px 10px;">Cód: ${escapeHtml(p.codigo)}</span>
            </div>
            ${p.marca ? `<div style="font-size:12.5px;color:#475569;margin-bottom:6px;"><b>Marca / Fabricante:</b> ${escapeHtml(p.marca)}</div>` : ""}
            ${p.imei ? `<div style="font-size:12.5px;color:#0284c7;margin-bottom:6px;"><b>📱 IMEI / Nº Série:</b> ${escapeHtml(p.imei)}</div>` : ""}
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;font-size:12px;">
            <div style="background:#fff;border:1px solid #e2e8f0;padding:10px;border-radius:6px;">
                <b>⚖️ NCM:</b> <code>${escapeHtml(p.ncm || "85171300")}</code><br>
                <b>CEST:</b> <code>${escapeHtml(p.cest || "—")}</code><br>
                <b>EAN / GTIN:</b> <code>${escapeHtml(p.gtin || "SEM GTIN")}</code>
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;padding:10px;border-radius:6px;">
                <b>CFOP Estadual:</b> <code>${escapeHtml(p.cfop_padrao || "5102")}</code><br>
                <b>CFOP Interestadual:</b> <code>${escapeHtml(p.cfop_interestadual || "6102")}</code><br>
                <b>Unidade Comercial:</b> <b>${escapeHtml(p.unidade || "UN")}</b>
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;padding:10px;border-radius:6px;">
                <b>CSOSN (Simples):</b> ${escapeHtml(csosnMap[p.csosn_cst] || p.csosn_cst || "102")}<br>
                <b>Origem:</b> ${escapeHtml(origens[p.origem] || "Nacional")}
            </div>
            <div style="background:#fff;border:1px solid #e2e8f0;padding:10px;border-radius:6px;">
                <b>💰 Preço de Venda:</b> <span style="font-size:14px;font-weight:bold;color:#15803d;">R$ ${(p.preco_venda || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span><br>
                <b>Preço de Custo:</b> R$ ${(p.preco_custo || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}<br>
                <b>Estoque Atual:</b> <b>${p.estoque_atual || 0} ${escapeHtml(p.unidade || "UN")}</b>
            </div>
        </div>
    `;

    const btnUsar = document.getElementById("btn-vis-usar-emissao");
    if (btnUsar) {
        btnUsar.onclick = () => {
            fecharModalVisualizarProduto();
            usarProdutoNaEmissao(p.codigo);
        };
    }

    const btnEdit = document.getElementById("btn-vis-editar-produto");
    if (btnEdit) {
        btnEdit.onclick = () => {
            fecharModalVisualizarProduto();
            abrirModalEditarProduto(p.id);
        };
    }

    modal.style.display = "flex";
}

function fecharModalVisualizarProduto() {
    const modal = document.getElementById("modal-visualizar-produto");
    if (modal) modal.style.display = "none";
}

async function salvarProdutoModal(e) {
    e.preventDefault();
    const prodId = document.getElementById("modal-prod-id")?.value;
    const cod = (document.getElementById("modal-prod-cod")?.value || "").trim().toUpperCase();
    const desc = (document.getElementById("modal-prod-desc")?.value || "").trim().toUpperCase();
    const ncm = (document.getElementById("modal-prod-ncm")?.value || "").replace(/\D/g, "");
    const cest = (document.getElementById("modal-prod-cest")?.value || "").trim();
    const cfop = (document.getElementById("modal-prod-cfop")?.value || "5102").replace(/\D/g, "");
    const cfopInter = (document.getElementById("modal-prod-cfop-inter")?.value || "6102").replace(/\D/g, "");
    const csosn = (document.getElementById("modal-prod-csosn")?.value || "102").trim();
    const un = (document.getElementById("modal-prod-un")?.value || "UN").trim().toUpperCase();
    const preco = parseFloat(document.getElementById("modal-prod-preco")?.value || 0);
    const custo = parseFloat(document.getElementById("modal-prod-custo")?.value || 0);
    const estoque = parseFloat(document.getElementById("modal-prod-estoque")?.value || 1);
    const origem = parseInt(document.getElementById("modal-prod-origem")?.value || 0);
    const gtin = (document.getElementById("modal-prod-gtin")?.value || "").trim();
    const imei = (document.getElementById("modal-prod-imei")?.value || "").trim().toUpperCase();
    const marca = (document.getElementById("modal-prod-marca")?.value || "").trim().toUpperCase();

    if (!cod || !desc || !ncm) {
        toast.warning("Código, Descrição e NCM (8 dígitos) são obrigatórios.");
        return;
    }

    try {
        const payload = {
            codigo: cod,
            descricao: desc,
            ncm: ncm,
            cest: cest,
            cfop_padrao: cfop,
            cfop_interestadual: cfopInter,
            csosn_cst: csosn,
            unidade: un,
            preco_venda: preco,
            preco_custo: custo,
            estoque_atual: estoque,
            origem: origem,
            gtin: gtin,
            imei: imei,
            marca: marca,
        };
        if (prodId) {
            payload.id = parseInt(prodId);
        }

        const res = await apiPost("/api/emissao/produtos", payload);

        if (res.success && res.data?.success !== false) {
            fecharModalProduto();
            await carregarTabelaCadProdutos();
            await carregarSelectProdutosEmissao();
            toast.success("Produto salvo com sucesso no catálogo!");
        } else {
            const msg = res.data?.detail || res.data?.error || "Falha ao salvar produto.";
            toast.error("Erro ao salvar produto: " + msg);
        }
    } catch (err) {
        toast.error("Erro: " + err.message);
    }
}

function usarProdutoNaEmissao(codigo) {
    switchEmissaoTab("form");
    const sel = document.getElementById("emissao-select-prod-rapido");
    if (sel) sel.value = codigo;
    selecionarProdutoCatalogo(codigo);
}

async function excluirProdutoCad(id) {
    const confirma = await showConfirmModal({
        title: "Excluir Produto",
        message: "Deseja realmente excluir este produto do catálogo?",
        confirmText: "Sim, excluir",
        cancelText: "Cancelar",
        danger: true,
        icon: "🗑️",
    });
    if (!confirma) return;
    try {
        const res = await apiRequest(`/api/emissao/produtos/${id}`, { method: "DELETE" });
        if (res.success) {
            await carregarTabelaCadProdutos();
            await carregarSelectProdutosEmissao();
            toast.success("Produto excluído com sucesso.");
        }
    } catch (err) {
        toast.error("Erro ao excluir produto: " + err.message);
    }
}


// ====================================================================
// 6. BIPADOR DE CÓDIGO DE BARRAS / USB SCANNER
// ====================================================================

function abrirBipadorModal() {
    const modal = document.getElementById("modal-bipador");
    if (modal) {
        modal.style.display = "flex";
        setTimeout(() => {
            const input = document.getElementById("bipador-input-rapido");
            if (input) {
                input.value = "";
                input.focus();
            }
        }, 100);
    }
}

function fecharBipadorModal() {
    const modal = document.getElementById("modal-bipador");
    if (modal) modal.style.display = "none";
}

function handleBipadorKey(e) {
    if (e.key === "Enter") {
        e.preventDefault();
        processarBipChave();
    }
}

function processarBipChave() {
    const input = document.getElementById("bipador-input-rapido");
    const rawVal = input ? input.value : "";
    const chave = rawVal.replace(/\D/g, "");

    if (chave.length < 20) {
        toast.warning("Código de barras ou chave inválida.");
        return;
    }

    fecharBipadorModal();
    abrirConferenciaEstoque(chave);
}

// ====================================================================
// COMUNICAÇÃO COM O CLIENTE: WHATSAPP & E-MAIL
// ====================================================================

async function enviarWhatsappNfe(chave, telefone = "") {
    if (!chave) return;
    try {
        let tel = telefone;
        if (!tel) {
            tel = prompt("Digite o WhatsApp do cliente com DDD (ex: 11999998888) ou deixe em branco para escolher no app:");
        }
        const res = await apiPost("/api/emissao/whatsapp-link", { chave: chave, telefone: tel || "" });
        if (res.success && res.whatsapp_url) {
            window.open(res.whatsapp_url, "_blank");
        } else {
            toast.error("Não foi possível gerar o link de WhatsApp.");
        }
    } catch (err) {
        toast.error("Erro: " + err.message);
    }
}

// ====================================================================
// CHECK-IN AUTOMÁTICO DE ESTOQUE (ENTRADA DE COMPRAS)
// ====================================================================

async function executarCheckinEstoqueRapido(chave) {
    if (!chave) return;
    const confirma = await showConfirmModal({
        title: "Entrada de Estoque",
        message: "Deseja dar entrada no estoque para todos os produtos desta NF-e de compra? Produtos novos serão cadastrados automaticamente no catálogo.",
        confirmText: "Sim, dar entrada",
        cancelText: "Cancelar",
        icon: "📦",
    });
    if (!confirma) {
        return;
    }

    try {
        const res = await apiPost("/api/gestao/estoque/checkin-nfe", { chave: chave, markup_sugerido_pct: 40.0 });
        if (res.success) {
            toast.success(`${res.message} Novos produtos cadastrados: ${res.produtos_novos} | Itens atualizados: ${res.produtos_atualizados}`, 8000);
            if (typeof carregarCatalogoProdutos === "function") carregarCatalogoProdutos(1);
        } else {
            toast.error("Erro no check-in: " + (res.detail || "Falha"));
        }
    } catch (err) {
        toast.error("Erro ao executar check-in de estoque: " + err.message);
    }
}

// ====================================================================
// APURAÇÃO DO SIMPLES NACIONAL (LEI 123/2006)
// ====================================================================

async function carregarApuracaoSimplesNacional(ano, mes, empresa) {
    const container = document.getElementById("simples-nacional-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Calculando alíquotas do Simples Nacional...</div>`;

    try {
        const a = ano || (document.getElementById("fin-mes")?.value ? document.getElementById("fin-mes").value.split("-")[0] : "");
        const m = mes || (document.getElementById("fin-mes")?.value ? document.getElementById("fin-mes").value.split("-")[1] : "");
        const emp = empresa || document.getElementById("fin-empresa")?.value || "";
        let url = `/api/gestao/tributacao/simples-nacional?`;
        if (a) url += `ano=${encodeURIComponent(a)}&`;
        if (m) url += `mes=${encodeURIComponent(m)}&`;
        if (emp) url += `empresa_cnpj=${encodeURIComponent(emp)}&`;

        const res = await apiGet(url);
        if (res) {
            const fmtR = (v) => "R$ " + parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            container.innerHTML = `
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;margin-bottom:12px;">
                    <div style="background:#f8fafc;padding:12px;border:1px solid #cbd5e1;border-radius:4px;border-left:4px solid #3b82f6;">
                        <div style="font-size:11px;color:#64748b;font-weight:bold;">FATURAMENTO DO MÊS (${res.competencia})</div>
                        <div style="font-size:20px;font-weight:bold;color:#1e293b;margin-top:4px;">${fmtR(res.receita_mes)}</div>
                        <small style="color:#64748b;">${res.qtd_vendas_mes} vendas emitidas</small>
                    </div>
                    <div style="background:#f8fafc;padding:12px;border:1px solid #cbd5e1;border-radius:4px;border-left:4px solid #8b5cf6;">
                        <div style="font-size:11px;color:#64748b;font-weight:bold;">RBT12 (RECEITA BRUTA 12 MESES)</div>
                        <div style="font-size:20px;font-weight:bold;color:#1e293b;margin-top:4px;">${fmtR(res.rbt12)}</div>
                        <small style="color:#64748b;">${res.anexo} (Faixa ${res.faixa})</small>
                    </div>
                    <div style="background:#f8fafc;padding:12px;border:1px solid #cbd5e1;border-radius:4px;border-left:4px solid #f59e0b;">
                        <div style="font-size:11px;color:#64748b;font-weight:bold;">ALÍQUOTA EFETIVA</div>
                        <div style="font-size:20px;font-weight:bold;color:#b45309;margin-top:4px;">${res.aliquota_efetiva_pct}%</div>
                        <small style="color:#64748b;">Nominal: ${res.aliquota_nominal_pct}% | Ded: ${fmtR(res.parcela_deduzir)}</small>
                    </div>
                    <div style="background:#f0fdf4;padding:12px;border:1px solid #bbf7d0;border-radius:4px;border-left:4px solid #22c55e;">
                        <div style="font-size:11px;color:#166534;font-weight:bold;">ESTIMATIVA GUIA DAS</div>
                        <div style="font-size:20px;font-weight:bold;color:#15803d;margin-top:4px;">${fmtR(res.valor_das_estimado)}</div>
                        <small style="color:#166534;">Vencimento: ${res.data_vencimento}</small>
                    </div>
                </div>
            `;
        }
    } catch (err) {
        container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro ao calcular Simples Nacional: ${err.message}</div>`;
    }
}

// ====================================================================
// DRE DE MARGEM REAL POR PRODUTO
// ====================================================================

async function carregarDreMargens(empresa) {
    const container = document.getElementById("dre-margens-painel");
    if (!container) return;

    container.innerHTML = `<div style="padding:15px;text-align:center;color:#666;">Carregando análise de margem de produtos...</div>`;

    try {
        const emp = empresa || document.getElementById("fin-empresa")?.value || "";
        let url = `/api/gestao/dre/margens?limit=50`;
        if (emp) url += `&empresa_cnpj=${encodeURIComponent(emp)}`;
        const res = await apiGet(url);
        const produtos = res.produtos || [];

        if (produtos.length === 0) {
            container.innerHTML = `<div style="padding:15px;color:#888;text-align:center;">Nenhum produto cadastrado no catálogo.</div>`;
            return;
        }

        const fmtR = (v) => "R$ " + parseFloat(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const rows = produtos.map(p => {
            let badgeBg = "#22c55e";
            if (p.status_margem === "BAIXA") badgeBg = "#ef4444";
            else if (p.status_margem === "BOA") badgeBg = "#3b82f6";

            return `
                <tr>
                    <td><b>${escapeHtml(p.codigo || "")}</b></td>
                    <td><b>${escapeHtml(p.descricao || "")}</b><br><small style="color:#64748b;">NCM: ${escapeHtml(p.ncm || "—")}</small></td>
                    <td style="text-align:center;"><b>${p.estoque}</b></td>
                    <td style="text-align:right;color:#64748b;">${fmtR(p.preco_custo)}</td>
                    <td style="text-align:right;font-weight:bold;color:#1e293b;">${fmtR(p.preco_venda)}</td>
                    <td style="text-align:right;font-weight:bold;color:#166534;">${fmtR(p.lucro_unitario)}</td>
                    <td style="text-align:center;font-weight:bold;color:#1e293b;">${p.margem_lucro_pct}%</td>
                    <td style="text-align:center;"><span class="badge" style="background:${badgeBg};color:#fff;font-size:10px;padding:3px 8px;">${p.status_margem}</span></td>
                </tr>
            `;
        }).join("");

        container.innerHTML = `
            <div class="table-responsive">
                <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                    <thead>
                        <tr class="linhaTitulo">
                            <th style="padding:6px;">Código</th>
                            <th style="padding:6px;">Descrição do Produto</th>
                            <th style="padding:6px;text-align:center;">Estoque</th>
                            <th style="padding:6px;text-align:right;">Preço Custo</th>
                            <th style="padding:6px;text-align:right;">Preço Venda</th>
                            <th style="padding:6px;text-align:right;">Lucro Unitário</th>
                            <th style="padding:6px;text-align:center;">Margem (%)</th>
                            <th style="padding:6px;text-align:center;">Classificação</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div style="color:#c0392b;padding:10px;">Erro ao carregar DRE de produtos: ${err.message}</div>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const formContabil = document.getElementById("form-contabil-exportar");
    if (formContabil) {
        formContabil.addEventListener("submit", (e) => {
            e.preventDefault();
            const mes = document.getElementById("contabil-mes")?.value || "8";
            const ano = document.getElementById("contabil-ano")?.value || "2026";
            const empresa = document.getElementById("contabil-empresa")?.value || "";
            const chkPdf = document.getElementById("contabil-chk-pdf")?.checked ? "true" : "false";
            const url = `/api/gestao/contabil/pacote-mensal?ano=${ano}&mes=${mes}&empresa_cnpj=${encodeURIComponent(empresa)}&incluir_pdfs=${chkPdf}`;
            const defaultName = `Pacote_Contabil_${String(mes).padStart(2, '0')}_${ano}.zip`;
            apiDownload(url, defaultName).then((res) => {
                if (res.ok) {
                    const blobUrl = window.URL.createObjectURL(res.blob);
                    const a = document.createElement("a");
                    a.href = blobUrl;
                    a.download = res.filename || defaultName;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(blobUrl);
                    toast.success("Pacote contábil baixado com sucesso!");
                } else {
                    toast.error("Erro ao gerar pacote contábil: " + (res.error || "Falha no download"));
                }
            });
        });
    }
    preencherPeriodo();
    carregarEmpresas();
    document.getElementById("fin-mes")?.addEventListener("change", carregarFinanceiro);
    document.getElementById("fin-empresa")?.addEventListener("change", carregarFinanceiro);
});

// ====================================================================
// 1. TEMA ESCURO / CLARO (DARK MODE OLED & SLATE)
// ====================================================================
function initTheme() {
    const savedTheme = localStorage.getItem("nfe_theme") || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(savedTheme, false);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    setTheme(next, true);
}

function setTheme(theme, notify = true) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("nfe_theme", theme);
    const btn = document.getElementById("btn-theme-toggle");
    if (btn) {
        btn.textContent = theme === "dark" ? "☀️ Claro" : "🌙 Escuro";
        btn.title = `Alternar para tema ${theme === "dark" ? "claro" : "escuro"}`;
    }
    if (notify && typeof toast !== "undefined") {
        toast.info(`Tema ${theme === "dark" ? "escuro" : "claro"} ativado.`);
    }
}

// Inicializa tema imediatamente
initTheme();

// ====================================================================
// 2. COMMAND PALETTE (CTRL + K / SPOTLIGHT SEARCH)
// ====================================================================
const COMMANDS_BASE = [
    // Operações Principais
    { id: "emissao", icon: "📤", label: "Emitir Nova NF-e (Modelo 55)", category: "Ações", action: () => showSection("emissor-rapido") },
    { id: "minhas-nfe", icon: "📑", label: "Minhas NF-e (Gestão de Documentos)", category: "Ações", action: () => showSection("gestao-docs") },
    { id: "fechamento-zip", icon: "📦", label: "Fechamento Contábil Mensal (.ZIP)", category: "Contabilidade", action: () => showSection("gestao-contabil") },
    { id: "gaps", icon: "🔍", label: "Auditoria de Saltos de Numeração (Gaps)", category: "Auditoria", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-gaps"), 150); } },
    { id: "sync-robo", icon: "⚡", label: "Sincronizar Robô DF-e com a SEFAZ", category: "Serviços", action: () => showSection("gestao-sync") },
    { id: "financeiro", icon: "💳", label: "Financeiro, DRE & Contas a Pagar", category: "Financeiro", action: () => showSection("gestao-financeiro") },
    { id: "intercompany", icon: "🔄", label: "Transferências Entre Filiais", category: "Operações", action: () => showSection("gestao-intercompany") },
    { id: "limpeza", icon: "🧹", label: "Limpeza de NF-es de Teste & Homologação", category: "Manutenção", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-limpeza"), 150); } },
    { id: "orfaos", icon: "📁", label: "Limpeza de Arquivos XMLs Órfãos", category: "Manutenção", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-orfaos"), 150); } },
    { id: "auditoria-base", icon: "📊", label: "Auditoria Rápida da Base & Armazenamento", category: "Auditoria", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-auditoria"), 150); } },
    { id: "certificados", icon: "🏢", label: "Gerenciar Certificados Digitais A1", category: "Configurações", action: () => showSection("certificado") },
    { id: "toggle-theme", icon: "🌓", label: "Alternar Tema Claro / Escuro", category: "Aparência", action: () => toggleTheme() },
    { id: "test-audio", icon: "🔊", label: "Testar Som de Alerta Sonoro", category: "Configurações", action: () => testarSomAlertaWeb() },

    // Filiais do Grupo
    { id: "filial-jack", icon: "🏢", label: "Filial: JACKCELL CELULARES (34.511.185/0001-10)", category: "Filiais", action: () => filtrarNotasPorEmpresa("34511185000110") },
    { id: "filial-fernandes", icon: "🏢", label: "Filial: FERNANDES COMERCIO (13.787.408/0001-05)", category: "Filiais", action: () => filtrarNotasPorEmpresa("13787408000105") },
    { id: "filial-filipe", icon: "🏢", label: "Filial: FILIPE ALMEIDA GIL (44.739.622/0001-01)", category: "Filiais", action: () => filtrarNotasPorEmpresa("44739622000101") },
    { id: "filial-jdea", icon: "🏢", label: "Filial: J DE A FERNANDES (58.186.781/0001-30)", category: "Filiais", action: () => filtrarNotasPorEmpresa("58186781000130") },
    { id: "filial-miplace", icon: "🏢", label: "Filial: MI PLACE AMPARO (58.495.100/0001-16)", category: "Filiais", action: () => filtrarNotasPorEmpresa("58495100000116") },
];

let _cmdActiveIndex = 0;
let _cmdFilteredList = [];

function abrirCommandPalette() {
    const modal = document.getElementById("modal-command-palette");
    const input = document.getElementById("cmd-palette-input");
    if (!modal || !input) return;

    modal.style.display = "flex";
    input.value = "";
    filtrarCommandPalette("");
    setTimeout(() => input.focus(), 50);
}

function fecharCommandPalette() {
    const modal = document.getElementById("modal-command-palette");
    if (modal) modal.style.display = "none";
}

function filtrarCommandPalette(query) {
    const q = (query || "").trim().toLowerCase();
    const cleanDigits = q.replace(/\D/g, "");

    _cmdFilteredList = [];

    // Se o usuário digitou uma chave de 44 dígitos ou um número de nota
    if (cleanDigits.length === 44) {
        _cmdFilteredList.push({
            id: `danfe-${cleanDigits}`,
            icon: "👁️",
            label: `Abrir DANFE da Chave: ${cleanDigits}`,
            category: "Documento Fiscal",
            action: () => visualizarDanfeChave(cleanDigits),
        });
    } else if (cleanDigits.length > 0 && cleanDigits.length <= 9) {
        _cmdFilteredList.push({
            id: `busca-num-${cleanDigits}`,
            icon: "🔍",
            label: `Buscar NF-e com Nº ${cleanDigits}`,
            category: "Busca Rápida",
            action: () => {
                showSection("gestao-docs");
                const buscaInp = document.getElementById("gestao-busca");
                if (buscaInp) {
                    buscaInp.value = cleanDigits;
                    loadGestaoDocs(1);
                }
            },
        });
    }

    // Filtra lista padrão
    COMMANDS_BASE.forEach(cmd => {
        if (!q || cmd.label.toLowerCase().includes(q) || cmd.category.toLowerCase().includes(q)) {
            _cmdFilteredList.push(cmd);
        }
    });

    _cmdActiveIndex = 0;
    renderCommandList();
}

function renderCommandList() {
    const container = document.getElementById("cmd-palette-list");
    if (!container) return;

    if (_cmdFilteredList.length === 0) {
        container.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:12.5px;">Nenhum comando ou documento encontrado.</div>`;
        return;
    }

    let html = "";
    let currentCategory = "";

    _cmdFilteredList.forEach((cmd, idx) => {
        if (cmd.category !== currentCategory) {
            currentCategory = cmd.category;
            html += `<div class="cmd-group-label">${escapeHtml(currentCategory)}</div>`;
        }
        const isActive = idx === _cmdActiveIndex ? "active" : "";
        html += `
            <div class="cmd-item ${isActive}" onclick="executarComando(${idx});">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:15px;">${cmd.icon}</span>
                    <span>${escapeHtml(cmd.label)}</span>
                </div>
                <span class="cmd-shortcut-tag">↵</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

function handleCommandKeydown(e) {
    if (e.key === "Escape") {
        fecharCommandPalette();
    } else if (e.key === "ArrowDown") {
        e.preventDefault();
        _cmdActiveIndex = Math.min(_cmdActiveIndex + 1, _cmdFilteredList.length - 1);
        renderCommandList();
        scrollActiveCmdIntoView();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        _cmdActiveIndex = Math.max(_cmdActiveIndex - 1, 0);
        renderCommandList();
        scrollActiveCmdIntoView();
    } else if (e.key === "Enter") {
        e.preventDefault();
        executarComando(_cmdActiveIndex);
    }
}

function scrollActiveCmdIntoView() {
    const activeEl = document.querySelector(".cmd-item.active");
    if (activeEl) activeEl.scrollIntoView({ block: "nearest" });
}

function executarComando(index) {
    const cmd = _cmdFilteredList[index];
    if (cmd && typeof cmd.action === "function") {
        fecharCommandPalette();
        cmd.action();
    }
}

// Atalho global Ctrl+K / Cmd+K
document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        const modal = document.getElementById("modal-command-palette");
        if (modal && modal.style.display === "flex") {
            fecharCommandPalette();
        } else {
            abrirCommandPalette();
        }
    }
});

// ====================================================================
// 3. DRAWER LATERAL DESLIZANTE PARA DETALHES DE NF-E (SIDE SHEET)
// ====================================================================
async function abrirDrawerDetalhes(chave) {
    const drawer = document.getElementById("drawer-nfe-detalhes");
    const tit = document.getElementById("drawer-doc-titulo");
    const chv = document.getElementById("drawer-doc-chave");
    const sit = document.getElementById("drawer-doc-situacao");
    const corpo = document.getElementById("drawer-doc-corpo");
    const acoes = document.getElementById("drawer-doc-acoes");

    if (!drawer) return;
    drawer.style.display = "block";

    if (tit) tit.textContent = "Carregando detalhes...";
    if (chv) chv.textContent = chave;
    if (corpo) corpo.innerHTML = `<div style="text-align:center;padding:40px;"><span class="spinner"></span> Carregando dados da nota...</div>`;
    if (acoes) acoes.innerHTML = "";

    try {
        const res = await apiGet(`/api/danfe/parse/${chave}`);
        if (!res.success || !res.data) {
            if (corpo) corpo.innerHTML = `<div class="result error"><p>Erro ao carregar detalhes da NF-e.</p></div>`;
            return;
        }

        const d = res.data;
        const ide = d.identificacao || {};
        const emit = d.emitente || {};
        const dest = d.destinatario || {};
        const tot = d.totais || {};
        const produtos = d.produtos || [];
        const eventos = d.eventos || [];
        const isCancelada = String(d.situacao || "").toLowerCase().includes("cancelad");

        if (tit) tit.textContent = `NF-e Nº ${ide.numero || "—"} (Série ${ide.serie || "1"})`;
        if (sit) {
            sit.className = isCancelada ? "badge-teste-tag" : "badge-real-tag";
            sit.textContent = d.situacao || "Autorizada";
        }

        const zapText = encodeURIComponent(`📑 *NF-e Nº ${ide.numero}* - ${emit.nome}\nValor: R$ ${Number(tot.v_nf || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}\nChave: ${chave}`);

        let html = `
            <div style="background:var(--bg-surface-alt);border:1px solid var(--border-main);border-radius:var(--radius-md);padding:12px;margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="color:var(--text-muted);font-size:11px;">EMISSÃO</span>
                    <b style="font-size:11.5px;">${ide.data_emissao ? new Date(ide.data_emissao).toLocaleString('pt-BR') : '--'}</b>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="color:var(--text-muted);font-size:11px;">VALOR TOTAL</span>
                    <b style="font-size:15px;color:var(--text-main);">R$ ${Number(tot.v_nf || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b>
                </div>
                <div style="display:flex;justify-content:space-between;">
                    <span style="color:var(--text-muted);font-size:11px;">PROTOCOLO SEFAZ</span>
                    <code style="font-size:11px;">${d.protocolo || '--'}</code>
                </div>
            </div>

            <!-- Emitente & Destinatário -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;">
                <div style="background:var(--bg-surface);border:1px solid var(--border-main);border-radius:var(--radius-md);padding:10px;">
                    <div style="font-size:10.5px;font-weight:700;color:var(--text-muted);margin-bottom:4px;">EMITENTE</div>
                    <div style="font-weight:600;font-size:12px;" title="${escapeHtml(emit.nome || '')}">${escapeHtml(emit.nome || '—')}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">CNPJ: <code>${escapeHtml(emit.cnpj || '—')}</code></div>
                </div>
                <div style="background:var(--bg-surface);border:1px solid var(--border-main);border-radius:var(--radius-md);padding:10px;">
                    <div style="font-size:10.5px;font-weight:700;color:var(--text-muted);margin-bottom:4px;">DESTINATÁRIO</div>
                    <div style="font-weight:600;font-size:12px;" title="${escapeHtml(dest.nome || '')}">${escapeHtml(dest.nome || 'Consumidor')}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">CPF/CNPJ: <code>${escapeHtml(dest.cnpj || dest.cpf || '—')}</code></div>
                </div>
            </div>

            <!-- Produtos / Itens -->
            <div style="margin-bottom:14px;">
                <div style="font-weight:700;font-size:12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
                    <span>📦 Itens da Nota (${produtos.length})</span>
                </div>
                <div style="max-height:180px;overflow-y:auto;border:1px solid var(--border-main);border-radius:var(--radius-sm);">
                    <table class="tabelaGrupo" style="font-size:11px;margin:0;">
                        <thead>
                            <tr>
                                <th>Produto</th>
                                <th style="text-align:right;">Qtd</th>
                                <th style="text-align:right;">Total (R$)</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${produtos.length > 0 ? produtos.map(p => `
                                <tr>
                                    <td><b>${escapeHtml(p.descricao || 'Item')}</b> <small style="color:var(--text-muted);">(NCM: ${escapeHtml(p.ncm || '--')})</small></td>
                                    <td style="text-align:right;">${p.quantidade || 1}</td>
                                    <td style="text-align:right;font-weight:600;">${Number(p.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                </tr>
                            `).join('') : `<tr><td colspan="3" style="text-align:center;padding:10px;color:var(--text-muted);">Sem itens no resumo da SEFAZ.</td></tr>`}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Eventos / CC-e -->
            ${eventos.length > 0 ? `
                <div style="background:#f8fafc;border:1px solid #c7d2fe;border-radius:var(--radius-md);padding:10px;margin-bottom:14px;">
                    <div style="font-size:11px;font-weight:700;color:#3730a3;margin-bottom:6px;">📜 Cartas de Correção / Eventos Vinculados</div>
                    ${eventos.map(ev => `
                        <div style="font-size:11px;padding:4px 0;border-bottom:1px dashed #e2e8f0;">
                            <b>${escapeHtml(ev.desc_evento || 'Evento')}</b> - <small style="color:#64748b;">${escapeHtml(ev.dh_evento || '')}</small>
                            <div style="color:#1e293b;margin-top:2px;">${escapeHtml(ev.desc_evento || ev.xCorrecao || '')}</div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;

        if (corpo) corpo.innerHTML = html;

        if (acoes) {
            acoes.innerHTML = `
                <button type="button" class="botao botao-primario" onclick="fecharDrawerDetalhes(); visualizarDanfeChave('${chave}');" style="font-size:11.5px;padding:6px 12px;">
                    👁️ Ver DANFE Completo
                </button>
                <button type="button" class="botao" onclick="downloadDanfePdf('${chave}');" style="font-size:11.5px;padding:6px 10px;">
                    📥 Baixar PDF
                </button>
                <a href="https://api.whatsapp.com/send?phone=5519989354849&text=${zapText}" target="_blank" class="botao" style="font-size:11px;padding:6px 10px;background:#25d366;color:#fff;border-color:#25d366;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
                    💬 Whats 1
                </a>
                <a href="https://api.whatsapp.com/send?phone=5519990151809&text=${zapText}" target="_blank" class="botao" style="font-size:11px;padding:6px 10px;background:#25d366;color:#fff;border-color:#25d366;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
                    💬 Whats 2
                </a>
            `;
        }
    } catch (err) {
        if (corpo) corpo.innerHTML = `<div class="result error"><p>Erro na requisição: ${escapeHtml(err.message)}</p></div>`;
    }
}

function fecharDrawerDetalhes() {
    const drawer = document.getElementById("drawer-nfe-detalhes");
    if (drawer) drawer.style.display = "none";
}


// ==============================================================================
// ATUALIZAÇÃO DO SISTEMA VIA GITHUB (1-CLIQUE)
// ==============================================================================

async function verificarAtualizacoes(showFeedback = false) {
    const badgeHeader = document.getElementById("badge-update-available");
    const modalLoading = document.getElementById("modal-update-loading");
    const modalContent = document.getElementById("modal-update-content");

    if (showFeedback && modalLoading && modalContent) {
        modalLoading.style.display = "block";
        modalContent.style.display = "none";
    }

    try {
        let data = null;
        if (typeof apiGet === "function") {
            const resp = await apiGet("/api/gestao/sistema/atualizacao/status");
            if (!resp.success) {
                throw new Error(resp.data?.error || resp.data?.detail || `HTTP ${resp.status}`);
            }
            data = resp.data;
        } else {
            const token = (typeof AuthSession !== "undefined" && AuthSession?.token) || "";
            const headers = token ? { "X-Session-Token": token } : {};
            const resp = await fetch("/api/gestao/sistema/atualizacao/status", { headers });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            data = await resp.json();
        }

        if (!data) throw new Error("Resposta vazia do servidor.");

        // 1. Atualiza Badge no Header
        if (badgeHeader) {
            if (data.has_update) {
                badgeHeader.style.display = "inline-block";
                badgeHeader.textContent = `${data.commits_behind || 'NOVA'} NOVA(S)`;
            } else {
                badgeHeader.style.display = "none";
            }
        }

        // 2. Atualiza Modal
        if (modalContent) {
            const statusTitle = document.getElementById("modal-update-status-title");
            const statusBadge = document.getElementById("modal-update-badge");
            const localHash = document.getElementById("modal-update-local-hash");
            const localDate = document.getElementById("modal-update-local-date");
            const branchEl = document.getElementById("modal-update-branch");
            const repoEl = document.getElementById("modal-update-repo");
            const pendingBox = document.getElementById("modal-update-pending-box");
            const commitsList = document.getElementById("modal-update-commits");
            const btnUpdate = document.getElementById("btn-modal-executar-update");

            if (statusTitle) statusTitle.textContent = data.message || (data.has_update ? "Nova versão disponível no GitHub!" : "Sistema 100% atualizado!");
            if (statusBadge) {
                statusBadge.textContent = data.has_update ? "🚀 ATUALIZAÇÃO DISPONÍVEL" : "🟢 ATUALIZADO";
                statusBadge.style.background = data.has_update ? "#dcfce7" : "#f1f5f9";
                statusBadge.style.color = data.has_update ? "#166534" : "#475569";
            }

            if (localHash) localHash.textContent = data.local_commit || "--";
            if (localDate) localDate.textContent = data.local_date || "--";
            if (branchEl) branchEl.textContent = data.branch || "main";
            if (repoEl) repoEl.textContent = data.remote_url || "GitHub";

            if (pendingBox && commitsList) {
                if (data.has_update && data.pending_commits && data.pending_commits.length > 0) {
                    commitsList.innerHTML = data.pending_commits.map(c => `<li><code>${escapeHtml(c)}</code></li>`).join("");
                    pendingBox.style.display = "block";
                } else {
                    pendingBox.style.display = "none";
                }
            }

            if (btnUpdate) {
                btnUpdate.style.display = data.has_update ? "inline-block" : "none";
            }

            if (modalLoading) modalLoading.style.display = "none";
            modalContent.style.display = "block";
        }

        // 3. Atualiza Subaba em Configurações
        const cfgStatusText = document.getElementById("cfg-update-status-text");
        const cfgLocalCommit = document.getElementById("cfg-update-local-commit");
        const cfgLocalDate = document.getElementById("cfg-update-local-date");
        const cfgBranch = document.getElementById("cfg-update-branch");
        const cfgBtnUpdate = document.getElementById("btn-cfg-executar-update");
        const cfgPendingSec = document.getElementById("cfg-update-pending-section");
        const cfgCommitsList = document.getElementById("cfg-update-commits-list");

        if (cfgStatusText) {
            cfgStatusText.textContent = data.has_update ? "🚀 Nova versão disponível no repositório!" : "🟢 Sistema atualizado com a versão mais recente.";
            cfgStatusText.style.color = data.has_update ? "#16a34a" : "#0f172a";
        }
        if (cfgLocalCommit) cfgLocalCommit.textContent = data.local_commit || "--";
        if (cfgLocalDate) cfgLocalDate.textContent = data.local_date || "--";
        if (cfgBranch) cfgBranch.textContent = data.branch || "main";
        if (cfgBtnUpdate) cfgBtnUpdate.style.display = data.has_update ? "inline-block" : "none";

        if (cfgPendingSec && cfgCommitsList) {
            if (data.has_update && data.pending_commits && data.pending_commits.length > 0) {
                cfgCommitsList.innerHTML = data.pending_commits.map(c => `<li><code>${escapeHtml(c)}</code></li>`).join("");
                cfgPendingSec.style.display = "block";
            } else {
                cfgPendingSec.style.display = "none";
            }
        }

        if (showFeedback && typeof showToast === "function") {
            if (data.has_update) {
                showToast("🚀 Nova versão encontrada no GitHub!", "info");
            } else {
                showToast("✅ O sistema já está na versão mais recente.", "success");
            }
        }

    } catch (err) {
        console.warn("[Updater] Erro ao checar atualizações:", err);
        if (modalLoading && modalContent) {
            modalLoading.style.display = "none";
            modalContent.style.display = "block";
            const statusTitle = document.getElementById("modal-update-status-title");
            if (statusTitle) statusTitle.textContent = `Não foi possível verificar atualizações: ${err.message}`;
        }
    }
}

function abrirModalAtualizacao() {
    const modal = document.getElementById("modal-atualizacao-sistema");
    if (modal) {
        modal.style.display = "flex";
        const terminal = document.getElementById("modal-update-terminal");
        if (terminal) terminal.style.display = "none";
        const btnReload = document.getElementById("btn-modal-recarregar");
        if (btnReload) btnReload.style.display = "none";
        verificarAtualizacoes(true);
    }
}

function fecharModalAtualizacao() {
    const modal = document.getElementById("modal-atualizacao-sistema");
    if (modal) modal.style.display = "none";
}

async function executarAtualizacaoSistema() {
    const btnModal = document.getElementById("btn-modal-executar-update");
    const btnCfg = document.getElementById("btn-cfg-executar-update");
    const terminalModal = document.getElementById("modal-update-terminal");
    const terminalCfg = document.getElementById("cfg-update-log-terminal");
    const btnReload = document.getElementById("btn-modal-recarregar");

    if (btnModal) { btnModal.disabled = true; btnModal.innerHTML = "⏳ Atualizando..."; }
    if (btnCfg) { btnCfg.disabled = true; btnCfg.innerHTML = "⏳ Atualizando..."; }

    if (terminalModal) {
        terminalModal.style.display = "block";
        terminalModal.textContent = "⏳ Conectando ao GitHub e baixando novidades...\n";
    }
    if (terminalCfg) {
        terminalCfg.style.display = "block";
        terminalCfg.textContent = "⏳ Conectando ao GitHub e baixando novidades...\n";
    }

    try {
        let data = null;
        if (typeof apiPost === "function") {
            const resp = await apiPost("/api/gestao/sistema/atualizacao/executar", {});
            data = resp.data || {};
            if (!resp.success && !data.message) {
                data.message = data.error || data.detail || `HTTP ${resp.status}`;
            }
        } else {
            const token = (typeof AuthSession !== "undefined" && AuthSession?.token) || "";
            const headers = { "Content-Type": "application/json" };
            if (token) headers["X-Session-Token"] = token;
            const resp = await fetch("/api/gestao/sistema/atualizacao/executar", {
                method: "POST",
                headers,
                body: JSON.stringify({})
            });
            data = await resp.json();
        }

        if (terminalModal) terminalModal.textContent = data.logs || (data.success ? "Atualização concluída!" : `Erro: ${data.message}`);
        if (terminalCfg) terminalCfg.textContent = data.logs || (data.success ? "Atualização concluída!" : `Erro: ${data.message}`);

        if (data.success) {
            if (typeof showToast === "function") showToast("🎉 Sistema atualizado com sucesso!", "success");
            if (btnModal) btnModal.style.display = "none";
            if (btnCfg) btnCfg.style.display = "none";
            if (btnReload) btnReload.style.display = "inline-block";

            // Atualiza status após sucesso
            setTimeout(() => {
                verificarAtualizacoes(false);
            }, 1000);
        } else {
            if (typeof showToast === "function") showToast(`❌ ${data.message || "Erro na atualização"}`, "error");
            if (btnModal) { btnModal.disabled = false; btnModal.innerHTML = "🚀 Tentar Novamente"; }
            if (btnCfg) { btnCfg.disabled = false; btnCfg.innerHTML = "🚀 Tentar Novamente"; }
        }
    } catch (err) {
        const errTxt = `❌ Erro de conexão durante a atualização: ${err.message}`;
        if (terminalModal) terminalModal.textContent += `\n${errTxt}`;
        if (terminalCfg) terminalCfg.textContent += `\n${errTxt}`;
        if (btnModal) { btnModal.disabled = false; btnModal.innerHTML = "🚀 Tentar Novamente"; }
        if (btnCfg) { btnCfg.disabled = false; btnCfg.innerHTML = "🚀 Tentar Novamente"; }
    }
}


