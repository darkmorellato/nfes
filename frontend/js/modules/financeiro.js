// ====================================================================
// FINANCEIRO — Contas a Pagar/Receber, Conferência de Carga, Aging & DRE
// ====================================================================

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
