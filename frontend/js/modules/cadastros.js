// ====================================================================
// CADASTROS — Clientes, Produtos, Consulta CNPJ RF, Bipador & WhatsApp
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
