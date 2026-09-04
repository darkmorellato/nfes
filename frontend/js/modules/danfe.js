// ====================================================================
// DANFE — Visualização, Impressão, Consultas SEFAZ e Upload XML
// ====================================================================

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
