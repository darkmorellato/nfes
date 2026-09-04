// ====================================================================
// SYNC — Robô DF-e, Sincronização em Background, Status SEFAZ & Alertas
// ====================================================================

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

        // Renderiza tabela multi-empresa e banner global de cooldown
        const globalBanner = document.getElementById("global-sefaz-cooldown-banner");
        const blockedCerts = certs.filter(c => c.blocked_by_sefaz);
        if (globalBanner) {
            if (blockedCerts.length > 0) {
                globalBanner.style.display = "block";
                globalBanner.innerHTML = `
                    <div style="padding:10px 14px;background:#fef6e7;border:1px solid #f9d89c;border-left:4px solid #e67e22;border-radius:4px;color:#8f4b0e;font-size:12px;display:flex;align-items:center;justify-content:space-between;gap:10px;">
                        <div>
                            <b>⏱️ SEFAZ em Intervalo Regulatório (cStat 656):</b>
                            ${blockedCerts.map(c => {
                                const retryTime = c.retry_at ? new Date(c.retry_at).toLocaleTimeString("pt-BR", { hour: '2-digit', minute: '2-digit' }) : "—";
                                return `<span style="margin-left:6px;"><b>${escapeHtml(c.razao_social || c.cnpj)}</b> aguardando até <b>${escapeHtml(retryTime)}</b> (${c.cooldown_minutes} min).</span>`;
                            }).join(" ")}
                            <span style="font-size:11px;color:#a06126;display:block;margin-top:2px;">O robô aguarda o término da janela oficial para evitar bloqueios maiores da SEFAZ.</span>
                        </div>
                        <button type="button" onclick="document.getElementById('global-sefaz-cooldown-banner').style.display='none'" style="background:none;border:none;cursor:pointer;font-size:14px;color:#8f4b0e;">✕</button>
                    </div>
                `;
            } else {
                globalBanner.style.display = "none";
            }
        }

        const containerTabela = document.getElementById("sync-tabela-empresas");
        if (containerTabela) {
            if (certs.length === 0) {
                containerTabela.innerHTML = `<div style="padding:15px;color:#666;">Nenhuma empresa cadastrada.</div>`;
            } else {
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
