// ====================================================================
// NAVIGATION — Roteamento de Seções, Abas, Tema & Command Palette
// ====================================================================

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
    } else if (tabId === "tab-cfg-backups") {
        carregarListaBackups();
    } else if (tabId === "tab-cfg-audit-trail") {
        carregarTrilhaAuditoria(1);
    }
}


// Temas e Command Palette
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
    { id: "backups-fiscais", icon: "📦", label: "Backups Fiscais & Snapshots do BD", category: "Configurações", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-backups"), 150); } },
    { id: "trilha-auditoria", icon: "📜", label: "Trilha de Auditoria Imutável (Compliance)", category: "Auditoria", action: () => { showSection("config"); setTimeout(() => switchTab("tab-cfg-audit-trail"), 150); } },
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
