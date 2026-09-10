// ====================================================================
// CERTIFICADOS — Gestão de Certificados Digitais A1 & Perfil de Conta
// ====================================================================

async function handleCertUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById("cert-file");
    const password = document.getElementById("cert-password").value;
    const file = fileInput.files[0];

    if (!file) {
        showResult("result-cert-upload", { error: "Selecione um arquivo de certificado." }, "error");
        return;
    }
    if (!password) {
        showResult("result-cert-upload", { error: "Informe a senha do certificado." }, "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("password", password);

    showLoading("result-cert-upload");
    const result = await apiUploadForm("/api/certificado/upload", formData);

    if (result.success && result.data.loaded) {
        AppState.certLoaded = true;
        showResult("result-cert-upload", {
            success: `Certificado cadastrado com sucesso! Empresa: ${result.data.subject || ''} | Validade: ${result.data.valid_to || ''}`
        }, "success");
        fileInput.value = "";
        document.getElementById("cert-password").value = "";
        checkCertStatus();
        loadCertificatesUI();
    } else {
        showResult("result-cert-upload", result.data || { error: "Erro ao carregar certificado." }, "error");
    }
}


async function loadCertificatesUI() {
    try {
        const res = await apiGet("/api/certificado/list");
        if (!res.success || !res.data) return;
        const certs = res.data || [];
        AppState.certificados = certs;

        // 1. Renderiza Cards na Tela Inicial (#inicio-cards-certificados)
        const cardsContainer = document.getElementById("inicio-cards-certificados");
        if (cardsContainer) {
            if (certs.length === 0) {
                renderEmptyState({
                    icon: '🏢',
                    title: 'Nenhum certificado cadastrado',
                    description: 'Você ainda não cadastrou um certificado digital A1.',
                    actionHtml: '<button class="botao botao-primario" onclick="showSection(\'certificado\')">➕ Adicionar certificado</button>',
                    containerId: 'inicio-cards-certificados',
                });
            } else {
                cardsContainer.innerHTML = certs.map(c => {
                    const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                    const days = c.days_remaining || 0;
                    let badgeClass = "badge-ambiente";
                    let badgeStyle = "background:var(--pastel-green-bg);color:var(--pastel-green-text);border:1px solid var(--pastel-green-border);";
                    let badgeText = `🟢 ${days} dias restantes`;
                    if (c.status_validade === "VENCIDO" || days === 0) {
                        badgeStyle = "background:var(--pastel-rose-bg);color:var(--pastel-rose-text);border:1px solid var(--pastel-rose-border);";
                        badgeText = "🔴 Vencido";
                    } else if (c.status_validade === "EXPIRANDO" || days <= 30) {
                        badgeStyle = "background:var(--pastel-amber-bg);color:var(--pastel-amber-text);border:1px solid var(--pastel-amber-border);";
                        badgeText = `🟡 Atenção: ${days} dias`;
                    }
                    const ieResumo = c.ie ? `IE: <b>${escapeHtml(c.ie)}</b>` : `<span style="color:#ef4444;font-size:10.5px;">IE pendente</span>`;

                    return `
                        <div class="card-kpi" style="border-top:3px solid var(--primary);">
                            <div>
                                <div style="font-size:12.5px;font-weight:600;color:var(--text-main);margin-bottom:4px;line-height:1.3;" title="${escapeHtml(c.razao_social)}">${escapeHtml(c.razao_social)}</div>
                                <div style="font-size:11px;font-family:monospace;color:var(--text-muted);margin-bottom:4px;">CNPJ: <b>${escapeHtml(cnpjFmt)}</b></div>
                                <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px;">${ieResumo}</div>
                                <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Validade: <b>${escapeHtml(c.valid_from || '—')}</b> até <b>${escapeHtml(c.valid_to || '—')}</b></div>
                                <div style="margin-bottom:10px;"><span style="${badgeStyle}font-size:10.5px;padding:3px 8px;border-radius:9999px;font-weight:600;">${escapeHtml(badgeText)}</span></div>
                            </div>
                            <div style="display:flex;gap:5px;border-top:1px solid var(--border-subtle);padding-top:10px;margin-top:6px;flex-wrap:wrap;">
                                <button type="button" class="btn-action" onclick="abrirModalEditarDadosFiscaisCert('${c.cnpj}');" style="flex:1;justify-content:center;padding:4px 6px;font-size:10.5px;" title="Editar IE e Endereço desta empresa">✏️ Fiscal</button>
                                <button type="button" class="btn-action btn-action-primary" onclick="filtrarNotasPorEmpresa('${c.cnpj}');" style="flex:1;justify-content:center;padding:4px 6px;font-size:10.5px;">🗄️ Notas</button>
                                <button type="button" class="btn-action btn-action-success" onclick="sincronizarEmpresaEspecifica('${c.cnpj}');" style="flex:1;justify-content:center;padding:4px 6px;font-size:10.5px;">⚡ Sync</button>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }

        // 2. Renderiza Tabela na aba Certificados (#cert-lista-tabela)
        const certTabela = document.getElementById("cert-lista-tabela");
        if (certTabela) {
            if (certs.length === 0) {
                renderEmptyState({
                    icon: '🏢',
                    title: 'Nenhum certificado cadastrado',
                    description: 'Você ainda não possui certificados digitais cadastrados no banco local.',
                    actionHtml: '<button class="botao botao-primario" onclick="abrirModalCadCert()">➕ Adicionar certificado A1</button>',
                    containerId: 'cert-lista-tabela',
                });
            } else {
                certTabela.innerHTML = `
                    <table class="tabelaGrupo" style="width:100%;font-size:11px;">
                        <tr class="linhaTitulo">
                            <th style="text-align:left;padding:6px;">Razão Social / Nome Fantasia</th>
                            <th>CNPJ</th>
                            <th>Inscrição Estadual</th>
                            <th>Endereço Fiscal</th>
                            <th>Validade Final</th>
                            <th>Dias</th>
                            <th>Status</th>
                            <th>Ações</th>
                        </tr>
                        ${certs.map(c => {
                            const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                            const days = c.days_remaining || 0;
                            let badgeColor = days > 30 ? "#27ae60" : days > 0 ? "#e67e22" : "#b00020";
                            const ieClean = (c.ie || "").replace(/\D/g, "");
                            let ieFmt = ieClean ? (ieClean.length === 12 ? ieClean.replace(/^(\d{3})(\d{3})(\d{3})(\d{3})$/, "$1.$2.$3.$4") : ieClean) : `<span style="color:#ef4444;font-style:italic;">Não configurada</span>`;
                            const endFmt = c.logradouro
                                ? `${escapeHtml(c.logradouro)}, ${escapeHtml(c.numero || 'S/N')} - ${escapeHtml(c.municipio || '')}/${escapeHtml(c.uf || 'SP')}`
                                : `<span style="color:#ef4444;font-style:italic;">Não configurado</span>`;

                            return `
                                <tr>
                                    <td style="text-align:left;padding:6px;">
                                        <b>${escapeHtml(c.razao_social)}</b>
                                        ${c.nome_fantasia ? `<br><small style="color:var(--text-muted);">${escapeHtml(c.nome_fantasia)}</small>` : ""}
                                    </td>
                                    <td style="font-family:monospace;">${escapeHtml(cnpjFmt)}</td>
                                    <td style="font-family:monospace;font-weight:bold;color:var(--primary);">${ieFmt}</td>
                                    <td style="font-size:10.5px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(c.logradouro || '')}">${endFmt}</td>
                                    <td><b>${escapeHtml(c.valid_to || "—")}</b></td>
                                    <td><b>${days} dias</b></td>
                                    <td><span class="badge-ambiente" style="background:${badgeColor};font-size:10px;">${escapeHtml(c.status_validade || "ATIVO")}</span></td>
                                    <td style="white-space:nowrap;display:flex;gap:4px;justify-content:center;padding:6px 4px;">
                                        <button type="button" class="botao" onclick="abrirModalEditarDadosFiscaisCert('${c.cnpj}');" style="font-size:10px;padding:3px 7px;color:#0284c7;border-color:#0284c7;" title="Configurar Inscrição Estadual e Endereço Fiscal">✏️ Fiscal</button>
                                        <button type="button" class="botao" onclick="sincronizarEmpresaEspecifica('${c.cnpj}');" style="font-size:10px;padding:3px 7px;">⚡ Sync</button>
                                        <button type="button" class="botao" onclick="excluirCertificado('${c.cnpj}', '${escapeHtml(c.razao_social)}');" style="font-size:10px;padding:3px 7px;color:#b00020;border-color:#b00020;">🗑️</button>
                                    </td>
                                </tr>
                            `;
                        }).join("")}
                    </table>
                `;
            }
        }

        // 3. Atualiza Select Dropdowns de Empresas em todas as abas
        const selectIds = [
            { id: "gestao-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
            { id: "contabil-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
            { id: "emissao-empresa-emit", placeholder: "Selecione a empresa emitente..." },
            { id: "filtro-saidas-empresa", placeholder: "🏢 Todas as 5 Empresas Emitentes" },
            { id: "filtro-empresa-saidas", placeholder: "🏢 Todas as 5 Empresas Emitentes" },
            { id: "intercompany-empresa-origem", placeholder: "Empresa de Origem..." },
            { id: "intercompany-empresa-destino", placeholder: "Empresa de Destino..." },
            { id: "limpeza-empresa", placeholder: "🏢 Todas as Empresas / Certificados" },
            { id: "gaps-filtro-empresa", placeholder: "🏢 Todas as 5 Filiais do Grupo" },
        ];

        selectIds.forEach(({ id, placeholder }) => {
            const sel = document.getElementById(id);
            if (sel) {
                const valAtual = sel.value;
                const optDefault = placeholder ? `<option value="">${placeholder}</option>` : "";
                sel.innerHTML = optDefault + certs.map(c => {
                    const cnpjFmt = (c.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
                    return `<option value="${c.cnpj}">${escapeHtml(cnpjFmt)} - ${escapeHtml(c.razao_social)}</option>`;
                }).join("");
                if (valAtual && [...sel.options].some(o => o.value === valAtual)) {
                    sel.value = valAtual;
                }
            }
        });
        atualizarCardEmitenteInfo();
    } catch (err) {
        console.error("Erro ao carregar certificados UI:", err);
    }
}


async function excluirCertificado(cnpj, razaoSocial) {
    const confirma = await showConfirmModal({
        title: "Excluir Certificado",
        message: `Deseja realmente excluir o certificado da empresa:\n${razaoSocial} (${cnpj})?`,
        confirmText: "Sim, excluir",
        cancelText: "Cancelar",
        danger: true,
        icon: "🗑️",
    });
    if (!confirma) {
        return;
    }
    try {
        const res = await apiDelete(`/api/certificado/${cnpj}`);
        if (res.success) {
            toast.success(`Certificado ${cnpj} excluído com sucesso.`);
            loadCertificatesUI();
            checkCertStatus();
        } else {
            toast.error("Erro ao excluir certificado: " + (res.data?.detail || "Falha"));
        }
    } catch (err) {
        toast.error("Erro na requisição: " + err.message);
    }
}


function filtrarNotasPorEmpresa(cnpj) {
    showSection("gestao-docs");
    const selectEmp = document.getElementById("gestao-empresa");
    if (selectEmp) selectEmp.value = cnpj;
    loadGestaoDocs(1);
}


async function sincronizarEmpresaEspecifica(cnpj) {
    const feedback = document.getElementById("sync-execucao-resultado");
    if (feedback) {
        feedback.style.display = "block";
        feedback.className = "result info";
        feedback.innerHTML = `<p>⚡ Sincronizando empresa <b>${cnpj}</b> com a SEFAZ Nacional a partir do último NSU, aguarde...</p>`;
    }
    showSection("gestao-sync");

    try {
        const res = await apiPost("/api/gestao/sync/run", { cnpj: cnpj, homologacao: AppState.ambiente === "homologacao" });
        if (res.success) {
            const data = res.data || {};
            // Caso a empresa esteja em cooldown por 656 (ou o sync recém tenha caído em 656),
            // o backend retorna blocked_by_sefaz=true. Mostra aviso amigável em vez do "✓ sucesso".
            const empresas = data.empresas || [];
            const empresaInfo = empresas.find(e => e.cnpj === cnpj) || data;
            if (empresaInfo && empresaInfo.blocked_by_sefaz) {
                const retryAt = empresaInfo.retry_at
                    ? new Date(empresaInfo.retry_at).toLocaleString("pt-BR", { dateStyle: 'short', timeStyle: 'short' })
                    : "—";
                if (feedback) {
                    feedback.className = "result info";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#c0392b;">🔒 SEFAZ bloqueou esta empresa (cStat 656 — Consumo Indevido).</div>
                        <div style="font-size:12px;margin-top:4px;">
                            Tentativa ${empresaInfo.tentativa_656 || 1} do backoff exponencial.<br>
                            <b>Próxima retentativa:</b> ${escapeHtml(retryAt)} (em ${empresaInfo.cooldown_minutes || 0} min).<br>
                            Tentar antes do cooldown só agrava o bloqueio. O sync automático respeitará a janela.
                        </div>
                    `;
                }
            } else if (data.skipped && data.blocked_by_sefaz) {
                const retryAt = data.retry_at
                    ? new Date(data.retry_at).toLocaleString("pt-BR", { dateStyle: 'short', timeStyle: 'short' })
                    : "—";
                if (feedback) {
                    feedback.className = "result info";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#c0392b;">🔒 Sync pulado — SEFAZ ainda bloqueia esta empresa.</div>
                        <div style="font-size:12px;margin-top:4px;">
                            <b>Próxima retentativa:</b> ${escapeHtml(retryAt)} (em ${data.cooldown_minutes || 0} min).
                        </div>
                    `;
                }
            } else {
                if (feedback) {
                    feedback.className = "result success";
                    feedback.innerHTML = `
                        <div style="font-weight:bold;color:#27ae60;">✓ Sincronização concluída com sucesso!</div>
                        <div style="font-size:12px;margin-top:4px;">
                            <b>${data.total_docs_saved || 0}</b> novas notas fiscais baixadas e arquivadas no banco.<br>
                            <b>${data.total_events_saved || 0}</b> eventos registrados.
                        </div>
                    `;
                }
            }
            loadSyncStatus();
            loadCertificatesUI();
        } else {
            if (feedback) {
                feedback.className = "result error";
                feedback.innerHTML = `<p>Erro na sincronização: ${escapeHtml(res.data?.detail || "Falha")}</p>`;
            }
        }
    } catch (err) {
        if (feedback) {
            feedback.className = "result error";
            feedback.innerHTML = `<p>Erro de comunicação: ${escapeHtml(err.message)}</p>`;
        }
    }
}


async function showCertInfo() {
    showLoading("result-cert-info");
    const result = await apiGet("/api/certificado/info");

    if (result.success && result.data.loaded) {
        AppState.certLoaded = true;
        showResult("result-cert-info", result.data, "success");
        checkCertStatus();
    } else {
        AppState.certLoaded = false;
        showResult("result-cert-info", result.data, "error");
        checkCertStatus();
    }
}


// ── Handlers: Conta (Alterar Senha / E-mail) ──────────────────────────────────

async function handleAlterarSenha(e) {
    e.preventDefault();
    const resultDiv = document.getElementById("result-alterar-senha");
    const senhaAtual = document.getElementById("senha-atual").value;
    const senhaNova = document.getElementById("senha-nova").value;
    const senhaNovaConfirm = document.getElementById("senha-nova-confirm").value;

    if (!senhaAtual || !senhaNova || !senhaNovaConfirm) {
        showResult("result-alterar-senha", { error: "Preencha todos os campos." }, "error");
        return;
    }
    if (senhaNova.length < 6) {
        showResult("result-alterar-senha", { error: "A nova senha deve ter ao menos 6 caracteres." }, "error");
        return;
    }
    if (senhaNova !== senhaNovaConfirm) {
        showResult("result-alterar-senha", { error: "As senhas não conferem." }, "error");
        return;
    }

    try {
        const res = await apiPost("/api/auth/alterar-senha", {
            senha_atual: senhaAtual,
            senha_nova: senhaNova,
        });
        if (res.success) {
            showResult("result-alterar-senha", { message: "Senha alterada com sucesso!" }, "success");
            document.getElementById("form-alterar-senha").reset();
            // Se era senha padrão, desbloquear o sistema
            if (AppState.senha_padrao) {
                AppState.senha_padrao = false;
                const alertDiv = document.getElementById("senha-padrao-alert");
                if (alertDiv) alertDiv.style.display = "none";
                // Marcar no backend que a senha padrão foi alterada
                await apiPost("/api/auth/marcar-senha-alterada", {});
            }
        } else {
            showResult("result-alterar-senha", { error: res.detail || "Erro ao alterar senha." }, "error");
        }
    } catch (err) {
        showResult("result-alterar-senha", { error: err.message || "Erro de conexão." }, "error");
    }
}

async function handleAlterarEmail(e) {
    e.preventDefault();
    const senhaAtual = document.getElementById("email-senha-atual").value;
    const emailNovo = document.getElementById("email-novo").value;
    const emailNovoConfirm = document.getElementById("email-novo-confirm").value;

    if (!senhaAtual || !emailNovo || !emailNovoConfirm) {
        showResult("result-alterar-email", { error: "Preencha todos os campos." }, "error");
        return;
    }
    if (emailNovo !== emailNovoConfirm) {
        showResult("result-alterar-email", { error: "Os e-mails não conferem." }, "error");
        return;
    }

    try {
        const res = await apiFetch("/api/auth/alterar-email", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                senha_atual: senhaAtual,
                email_novo: emailNovo,
                email_novo_confirm: emailNovoConfirm,
            }),
        });
        const data = await res.json();
        if (res.ok && data.success) {
            showResult("result-alterar-email", { message: "E-mail alterado com sucesso!" }, "success");
            document.getElementById("form-alterar-email").reset();
            AppState.email = data.email;
            document.getElementById("conta-email-atual").textContent = data.email;
        } else {
            showResult("result-alterar-email", { error: data.detail || "Erro ao alterar e-mail." }, "error");
        }
    } catch (err) {
        showResult("result-alterar-email", { error: err.message || "Erro de conexão." }, "error");
    }
}

function loadContaInfo() {
    // Preencher informações da conta na aba
    const emailEl = document.getElementById("conta-email-atual");
    const nomeEl = document.getElementById("conta-nome-atual");
    const perfilEl = document.getElementById("conta-perfil-atual");
    if (emailEl) emailEl.textContent = AppState.email || "—";
    if (nomeEl) nomeEl.textContent = AppState.nome || "—";
    if (perfilEl) perfilEl.textContent = AppState.perfil || "—";
}


async function handleConfigAmbiente(e) {
    e.preventDefault();
    const radio = document.querySelector('input[name="ambiente"]:checked');
    if (radio) {
        AppState.ambiente = radio.value;
        saveSettings();
        updateBadges();
        toast.success("Ambiente atualizado com sucesso.");
    }
}


async function handleConfigUF(e) {
    e.preventDefault();
    AppState.uf = document.getElementById("config-uf-select").value;
    saveSettings();
    updateBadges();
    toast.success("UF atualizada com sucesso.");
}



async function checkCertStatus() {
    try {
        const result = await apiGet("/api/certificado/info");
        AppState.certLoaded = !!(result.success && result.data && result.data.loaded);
    } catch {
        AppState.certLoaded = false;
    }
}

// ── Modal Edição de Dados Fiscais do Certificado ─────────────────────────────

function abrirModalEditarDadosFiscaisCert(cnpj) {
    if (!cnpj) return;
    const cleanCnpj = String(cnpj).replace(/\D/g, "");
    const cert = (AppState.certificados || []).find(c => String(c.cnpj || "").replace(/\D/g, "") === cleanCnpj);
    if (!cert) {
        toast.error("Certificado não encontrado.");
        return;
    }

    const modal = document.getElementById("modal-editar-dados-fiscais-cert");
    if (!modal) return;

    const cnpjFmt = (cert.cnpj || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");

    document.getElementById("modal-cert-fiscal-cnpj").value = cert.cnpj || "";
    document.getElementById("modal-cert-fiscal-razao").value = cert.razao_social || "";
    document.getElementById("modal-cert-fiscal-cnpj-display").textContent = cnpjFmt;
    document.getElementById("modal-cert-fiscal-razao-display").textContent = cert.razao_social || "";
    document.getElementById("modal-cert-fiscal-fantasia").value = cert.nome_fantasia || "";
    document.getElementById("modal-cert-fiscal-ie").value = cert.ie || "";
    document.getElementById("modal-cert-fiscal-crt").value = String(cert.crt || 1);
    document.getElementById("modal-cert-fiscal-cep").value = cert.cep || "";
    document.getElementById("modal-cert-fiscal-logradouro").value = cert.logradouro || "";
    document.getElementById("modal-cert-fiscal-numero").value = cert.numero || "";
    document.getElementById("modal-cert-fiscal-complemento").value = cert.complemento || "";
    document.getElementById("modal-cert-fiscal-bairro").value = cert.bairro || "";
    document.getElementById("modal-cert-fiscal-municipio").value = cert.municipio || "";
    document.getElementById("modal-cert-fiscal-cod-mun").value = cert.cod_municipio || "";
    document.getElementById("modal-cert-fiscal-uf").value = cert.uf || "SP";

    modal.style.display = "flex";
}

function fecharModalEditarDadosFiscaisCert() {
    const modal = document.getElementById("modal-editar-dados-fiscais-cert");
    if (modal) modal.style.display = "none";
}

async function buscarCepCertViaCep(cep) {
    const clean = String(cep || "").replace(/\D/g, "");
    if (clean.length !== 8) return;
    try {
        const resp = await fetch(`https://viacep.com.br/ws/${clean}/json/`);
        const data = await resp.json();
        if (data.erro) {
            toast.error("CEP não encontrado.");
            return;
        }
        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val) el.value = val;
        };
        setVal("modal-cert-fiscal-logradouro", data.logradouro);
        setVal("modal-cert-fiscal-bairro", data.bairro);
        setVal("modal-cert-fiscal-municipio", data.localidade);
        setVal("modal-cert-fiscal-uf", data.uf);
        setVal("modal-cert-fiscal-cod-mun", data.ibge);
        const numEl = document.getElementById("modal-cert-fiscal-numero");
        if (numEl) numEl.focus();
    } catch (err) {
        console.warn("Erro ao buscar CEP:", err);
    }
}

async function salvarDadosFiscaisCertModal(e) {
    e.preventDefault();
    const cnpj = document.getElementById("modal-cert-fiscal-cnpj").value;
    if (!cnpj) return;

    const cleanCnpj = String(cnpj).replace(/\D/g, "");
    const payload = {
        ie: (document.getElementById("modal-cert-fiscal-ie")?.value || "").replace(/\D/g, ""),
        nome_fantasia: document.getElementById("modal-cert-fiscal-fantasia")?.value?.trim() || "",
        crt: parseInt(document.getElementById("modal-cert-fiscal-crt")?.value || 1),
        cep: (document.getElementById("modal-cert-fiscal-cep")?.value || "").replace(/\D/g, ""),
        logradouro: document.getElementById("modal-cert-fiscal-logradouro")?.value?.trim() || "",
        numero: document.getElementById("modal-cert-fiscal-numero")?.value?.trim() || "",
        complemento: document.getElementById("modal-cert-fiscal-complemento")?.value?.trim() || "",
        bairro: document.getElementById("modal-cert-fiscal-bairro")?.value?.trim() || "",
        municipio: document.getElementById("modal-cert-fiscal-municipio")?.value?.trim() || "",
        cod_municipio: (document.getElementById("modal-cert-fiscal-cod-mun")?.value || "").replace(/\D/g, ""),
        uf: (document.getElementById("modal-cert-fiscal-uf")?.value || "SP").trim().toUpperCase(),
    };

    if (!payload.ie) {
        toast.error("A Inscrição Estadual (IE) é obrigatória para emissão de NF-e.");
        return;
    }
    if (!payload.logradouro || !payload.numero || !payload.bairro || !payload.municipio) {
        toast.error("Preencha todos os campos obrigatórios do endereço fiscal.");
        return;
    }

    try {
        const res = await apiPut(`/api/certificado/${cleanCnpj}/dados-fiscais`, payload);
        if (res.success) {
            toast.success("Dados fiscais atualizados com sucesso!");
            fecharModalEditarDadosFiscaisCert();
            await loadCertificatesUI();
            if (typeof carregarEmpresasEmitentesSelect === "function") {
                await carregarEmpresasEmitentesSelect();
            }
            if (typeof atualizarCardEmitenteInfo === "function") {
                atualizarCardEmitenteInfo();
            }
        } else {
            toast.error(res.data?.detail || res.detail || "Erro ao salvar dados fiscais.");
        }
    } catch (err) {
        toast.error("Erro de comunicação: " + err.message);
    }
}

