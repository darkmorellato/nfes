// ====================================================================
// OPERAÇÕES NF-e — Saídas, Clonagem, Cancelamento, CC-e & Inutilização
// ====================================================================

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
