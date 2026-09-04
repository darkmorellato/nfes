// ====================================================================
// CONTABIL — Fechamento Contábil Mensal, Exportação ZIP/Excel & Relatórios
// ====================================================================

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
