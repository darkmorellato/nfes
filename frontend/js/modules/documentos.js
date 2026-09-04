// ====================================================================
// DOCUMENTOS — Gestão de NF-e, Filtros, Busca, Tabela e Drawer Lateral
// ====================================================================

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
                        <button type="button" class="btn-action" onclick="abrirManifestacaoChave('${d.chave}', '${d.destinatario_cnpj || d.empresa_cnpj || ''}');" title="Manifestar Nota">✍️ Manifestar</button>
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
