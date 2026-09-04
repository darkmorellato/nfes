// ====================================================================
// EMISSOR — Emissor Rápido de NF-e Modelo 55 & Tributação
// ====================================================================

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
