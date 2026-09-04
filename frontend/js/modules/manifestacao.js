// ====================================================================
// MANIFESTAÇÃO — Eventos do Destinatário SEFAZ & Distribuição DF-e
// ====================================================================

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



function abrirManifestacaoChave(chave, cnpj) {
    const inputChave = document.getElementById("manifestacao-chave");
    const inputCnpj = document.getElementById("manifestacao-cnpj");
    if (inputChave) inputChave.value = chave;
    const finalCnpj = cnpj || AppState.empresaSelecionada || (AppState.empresas && AppState.empresas[0]?.cnpj) || "";
    if (inputCnpj) inputCnpj.value = finalCnpj.replace(/\D/g, "");
    showSection("manifestacao");
}

/* ================================================================
   ROBÔ DE SINCRONIZAÇÃO EM BACKGROUND (MULTI-EMPRESA)
================================================================ */


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
