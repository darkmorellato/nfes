// ====================================================================
// MANUTENÇÃO — Limpeza de Testes, XMLs Órfãos, Backups & Auditoria
// ====================================================================

async function executarBackupFiscalNuvem() {
    const msgEl = document.getElementById("backup-fiscal-status-msg");
    if (msgEl) msgEl.textContent = "Gerando snapshot fiscal...";

    try {
        const res = await apiPost("/api/gestao/cloud/backup", {});
        if (res.success && res.data) {
            const b = res.data.backup || {};
            if (msgEl) msgEl.textContent = `✓ Backup concluído em ${b.data_formatada} (${b.total_notas} notas protegidas até ${b.validade_retencao_legal}).`;
            toast.success(`Backup Fiscal Concluído com Sucesso! ${b.total_notas} notas fiscais protegidas com carimbo de retenção legal de 5 anos.`, 8000);
        } else {
            if (msgEl) msgEl.textContent = "Falha no backup.";
        }
    } catch (err) {
        if (msgEl) msgEl.textContent = "Erro: " + err.message;
    }
}

async function carregarConfigNotificacoes() {
    try {
        const res = await apiGet("/api/gestao/notificacoes/config");
        if (res.success && res.data) {
            const d = res.data;
            if (document.getElementById("notif-cfg-webhook")) document.getElementById("notif-cfg-webhook").value = d.webhook_url || "";
            if (document.getElementById("notif-cfg-tg-token")) document.getElementById("notif-cfg-tg-token").value = d.telegram_bot_token || "";
            if (document.getElementById("notif-cfg-tg-chat")) document.getElementById("notif-cfg-tg-chat").value = d.telegram_chat_id || "";
            if (document.getElementById("notif-cfg-whatsapp")) document.getElementById("notif-cfg-whatsapp").value = d.whatsapp_alert_numbers || "+5519989354849, +5519990151809";
        }
        const audioCheckbox = document.getElementById("cfg-audio-alert-enabled");
        if (audioCheckbox) {
            audioCheckbox.checked = localStorage.getItem("nfe_audio_alert_enabled") !== "false";
        }
    } catch (err) {
        console.warn("Erro ao carregar config de notificações:", err);
    }
}

async function handleSalvarConfigNotificacoes(e) {
    e.preventDefault();
    const webhook = document.getElementById("notif-cfg-webhook")?.value || "";
    const tgToken = document.getElementById("notif-cfg-tg-token")?.value || "";
    const tgChat = document.getElementById("notif-cfg-tg-chat")?.value || "";
    const whatsapp = document.getElementById("notif-cfg-whatsapp")?.value || "";

    const res = await apiPost("/api/gestao/notificacoes/config", {
        webhook_url: webhook,
        telegram_bot_token: tgToken,
        telegram_chat_id: tgChat,
        whatsapp_alert_numbers: whatsapp,
    });

    const resDiv = document.getElementById("result-config-notif");
    if (resDiv) {
        resDiv.style.display = "block";
        if (res.success) {
            resDiv.className = "result success";
            resDiv.innerHTML = `<p>✓ Canais de notificação (WhatsApp, Telegram e Webhooks) salvos com sucesso e teste disparado!</p>`;
        } else {
            resDiv.className = "result error";
            resDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha")}</p>`;
        }
    }
}



// Inicia polling de notificações a cada 30 segundos
if (!notifIntervalId) {
    notifIntervalId = setInterval(carregarNotificacoes, 30000);
}
setTimeout(carregarNotificacoes, 1500);

// Auto-refresh das listagens de NF-e (documentos e saídas) a cada 30 segundos
if (!window._gestaoDocsIntervalId) {
    window._gestaoDocsIntervalId = setInterval(() => {
        const container = document.getElementById("gestao-lista-resultado");
        if (container) loadGestaoDocs(currentGestaoPage);
    }, 30000);
}
if (!window._saidasIntervalId) {
    window._saidasIntervalId = setInterval(() => {
        const tbody = document.getElementById("tbody-saidas-nfe");
        if (tbody) carregarNfeSaidas(currentSaidasPage);
    }, 30000);
}

// Listener do form de notificações na aba de configurações
document.addEventListener("DOMContentLoaded", () => {
    const formNotif = document.getElementById("form-config-notificacoes");
    if (formNotif) formNotif.addEventListener("submit", handleSalvarConfigNotificacoes);
});


// ====================================================================
// LIMPEZA DE DADOS DE TESTE, XMLS ÓRFÃOS E AUDITORIA DA BASE
// ====================================================================

window._currentLimpezaTipo = "homologacao";

function aplicarPresetLimpeza(tipo) {
    document.querySelectorAll(".btn-preset").forEach(b => b.classList.remove("active"));
    const btn = document.getElementById(`preset-btn-${tipo}`);
    if (btn) btn.classList.add("active");

    window._currentLimpezaTipo = tipo;
    const empEl = document.getElementById("limpeza-empresa");
    const termoEl = document.getElementById("limpeza-termo");
    const cnpjEl = document.getElementById("limpeza-cnpj");
    const dtIniEl = document.getElementById("limpeza-dt-ini");
    const dtFimEl = document.getElementById("limpeza-dt-fim");
    const sitEl = document.getElementById("limpeza-situacao");

    if (tipo === "homologacao") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
        if (sitEl) sitEl.value = "todas";
    } else if (tipo === "zeradas") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
    } else if (tipo === "sem_itens") {
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
    } else if (tipo === "limpar") {
        if (empEl) empEl.value = "";
        if (termoEl) termoEl.value = "";
        if (cnpjEl) cnpjEl.value = "";
        if (dtIniEl) dtIniEl.value = "";
        if (dtFimEl) dtFimEl.value = "";
        if (sitEl) sitEl.value = "todas";
        window._currentLimpezaTipo = "custom";
    }

    carregarLimpezaPreview(window._currentLimpezaTipo);
}

async function carregarLimpezaPreview(tipoTeste) {
    if (tipoTeste) {
        window._currentLimpezaTipo = tipoTeste;
    } else {
        tipoTeste = window._currentLimpezaTipo || "homologacao";
    }

    const empresa = document.getElementById("limpeza-empresa")?.value || "";
    const termo = document.getElementById("limpeza-termo")?.value || "";
    const cnpj = document.getElementById("limpeza-cnpj")?.value || "";
    const dtIni = document.getElementById("limpeza-dt-ini")?.value || "";
    const dtFim = document.getElementById("limpeza-dt-fim")?.value || "";
    const situacao = document.getElementById("limpeza-situacao")?.value || "todas";

    const statusMsg = document.getElementById("limpeza-status-msg");
    if (statusMsg) statusMsg.textContent = "🔍 Localizando NF-es...";

    const container = document.getElementById("limpeza-resultado-container");
    const tbody = document.getElementById("tbody-limpeza-preview");
    const btnExec = document.getElementById("btn-limpeza-executar");

    try {
        const query = new URLSearchParams({
            empresa_cnpj: empresa.trim(),
            termo: termo.trim(),
            cnpj: cnpj.trim(),
            data_inicio: dtIni,
            data_fim: dtFim,
            situacao: situacao,
            tipo_teste: tipoTeste,
            limit: "200",
        });

        const res = await apiGet(`/api/gestao/limpeza/preview?${query.toString()}`);
        if (res.success && res.data) {
            const d = res.data;
            if (container) container.style.display = "block";

            const elTotal = document.getElementById("limpeza-total-encontradas");
            if (elTotal) elTotal.textContent = d.total_encontradas || 0;

            const elValor = document.getElementById("limpeza-valor-total");
            if (elValor) elValor.textContent = `R$ ${Number(d.valor_total_somado || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

            if (tbody) {
                if (!d.itens || d.itens.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:24px;color:var(--text-muted);">Nenhuma NF-e localizada para os filtros especificados.</td></tr>`;
                    if (btnExec) btnExec.style.display = "none";
                    if (statusMsg) statusMsg.textContent = "Nenhuma NF-e encontrada.";
                    return;
                }

                tbody.innerHTML = d.itens.map(item => {
                    const ch = item.chave || "";
                    const chCurta = ch ? `${ch.slice(0, 6)}...${ch.slice(-6)}` : "--";
                    const isTestLikely = (item.emitente_nome && /homolog|teste|sem valor|treinamento/i.test(item.emitente_nome)) ||
                                         (item.destinatario_nome && /homolog|teste|sem valor/i.test(item.destinatario_nome)) ||
                                         item.valor_total <= 0;

                    return `
                        <tr>
                            <td style="text-align:center;">
                                <input type="checkbox" class="chk-limpeza-item" value="${ch}" checked onchange="atualizarBadgeSelecaoLimpeza()">
                            </td>
                            <td><strong>${escapeHtml(item.numero || "--")}</strong> <span style="font-size:11px;color:var(--text-muted);">(série ${escapeHtml(item.serie || "1")})</span></td>
                            <td>
                                <div>${escapeHtml(item.emitente_nome || "(Sem Nome)")}</div>
                                <small style="color:var(--text-muted);">${escapeHtml(item.emitente_cnpj || "")}</small>
                                ${isTestLikely ? '<span class="badge-teste-tag" style="margin-left:4px;">🧪 Teste</span>' : ""}
                            </td>
                            <td>
                                <div>${escapeHtml(item.destinatario_nome || "(Sem Nome)")}</div>
                                <small style="color:var(--text-muted);">${escapeHtml(item.destinatario_cnpj || "")}</small>
                            </td>
                            <td>${escapeHtml(item.data_emissao ? item.data_emissao.slice(0, 10) : "--")}</td>
                            <td style="text-align:right;font-weight:600;">R$ ${Number(item.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td><span class="tag-pill">${escapeHtml(item.situacao || "Autorizada")}</span></td>
                            <td style="text-align:center;">
                                ${item.xml_exists_on_disk ? '<span class="badge-real-tag">✓ Sim</span>' : '<span class="badge-teste-tag">✗ Não</span>'}
                            </td>
                            <td>
                                <code style="font-size:11px;" title="${ch}">${chCurta}</code>
                            </td>
                            <td style="text-align:center;white-space:nowrap;">
                                <button type="button" class="btn-action btn-action-primary" onclick="visualizarDanfeChave('${ch}');" title="Visualizar DANFE / Detalhes da Nota" style="padding:4px 8px;font-size:11px;display:inline-flex;align-items:center;gap:4px;">
                                    👁️ Ver DANFE
                                </button>
                            </td>
                        </tr>
                    `;
                }).join("");

                atualizarBadgeSelecaoLimpeza();
                if (statusMsg) statusMsg.textContent = `Pronto (${d.total_encontradas} encontradas)`;
            }
        } else {
            if (statusMsg) statusMsg.textContent = "Erro ao buscar prévia: " + (res.data?.detail || "Falha na conexão");
        }
    } catch (err) {
        if (statusMsg) statusMsg.textContent = "Erro: " + err.message;
    }
}

function atualizarBadgeSelecaoLimpeza() {
    const checkboxes = document.querySelectorAll(".chk-limpeza-item");
    const checked = document.querySelectorAll(".chk-limpeza-item:checked");
    const count = checked.length;

    const badge = document.getElementById("limpeza-count-badge");
    if (badge) badge.textContent = count;

    const btnExec = document.getElementById("btn-limpeza-executar");
    if (btnExec) {
        btnExec.style.display = count > 0 ? "inline-flex" : "none";
    }

    const master = document.getElementById("chk-limpeza-master");
    if (master && checkboxes.length > 0) {
        master.checked = count === checkboxes.length;
        master.indeterminate = count > 0 && count < checkboxes.length;
    }
}

function toggleMasterLimpeza(master) {
    document.querySelectorAll(".chk-limpeza-item").forEach(chk => {
        chk.checked = master.checked;
    });
    atualizarBadgeSelecaoLimpeza();
}

function marcarTodasLimpeza(marcar) {
    document.querySelectorAll(".chk-limpeza-item").forEach(chk => {
        chk.checked = marcar;
    });
    const master = document.getElementById("chk-limpeza-master");
    if (master) master.checked = marcar;
    atualizarBadgeSelecaoLimpeza();
}

async function executarLimpezaNfesConfirmada() {
    const checkboxes = document.querySelectorAll(".chk-limpeza-item:checked");
    const chaves = Array.from(checkboxes).map(c => c.value);

    if (!chaves || chaves.length === 0) {
        alert("Por favor, selecione ao menos uma NF-e para excluir.");
        return;
    }

    const confirmMsg = `⚠️ ATENÇÃO: CONFIRMAÇÃO DE EXCLUSÃO DEFINITIVA\n\n` +
        `Você está prestes a excluir ${chaves.length} nota(s) fiscal(is) do sistema:\n\n` +
        `✓ Registros no SQLite: serão removidos (incluindo produtos, duplicatas e eventos).\n` +
        `✓ Arquivos XML no Disco: serão apagados fisicamente de data/xmls/.\n` +
        `✓ Espelho no Firestore: registros serão excluídos na nuvem.\n\n` +
        `Essa operação NÃO pode ser desfeita. Deseja continuar?`;

    if (!confirm(confirmMsg)) return;

    const btnExec = document.getElementById("btn-limpeza-executar");
    if (btnExec) {
        btnExec.disabled = true;
        btnExec.textContent = "⏳ Excluindo NF-es...";
    }

    const apagarXml = document.getElementById("limpeza-chk-xml")?.checked ?? true;
    const apagarFs = document.getElementById("limpeza-chk-firestore")?.checked ?? true;

    try {
        const res = await apiPost("/api/gestao/limpeza/executar", {
            chaves_selecionadas: chaves,
            apagar_xml_disco: apagarXml,
            apagar_firestore: apagarFs,
        });

        const alertDiv = document.getElementById("limpeza-feedback-alert");
        if (alertDiv) {
            alertDiv.style.display = "block";
            if (res.success) {
                alertDiv.className = "result success";
                alertDiv.innerHTML = `<p>✓ ${escapeHtml(res.data?.message || "NF-es excluídas com sucesso!")}</p>`;
            } else {
                alertDiv.className = "result error";
                alertDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha na exclusão")}</p>`;
            }
        }

        // Recarrega a prévia e a auditoria da base
        carregarLimpezaPreview();
        carregarAuditoriaBase();
    } catch (err) {
        alert("Erro na requisição: " + err.message);
    } finally {
        if (btnExec) {
            btnExec.disabled = false;
            btnExec.textContent = "🗑️ Excluir Selecionadas";
        }
    }
}

async function carregarAuditoriaXmlsOrfaos() {
    const statusMsg = document.getElementById("orfaos-status-msg");
    if (statusMsg) statusMsg.textContent = "🔍 Analisando arquivos...";

    const btnApagar = document.getElementById("btn-apagar-orfaos");
    const container = document.getElementById("orfaos-resultado-container");
    const tbody = document.getElementById("tbody-orfaos-preview");

    try {
        const res = await apiGet("/api/gestao/limpeza/xmls-orfaos");
        if (res.success && res.data) {
            const d = res.data;
            const elDisco = document.getElementById("kpi-orfaos-disco");
            if (elDisco) elDisco.textContent = d.total_xmls_disco || 0;

            const elBanco = document.getElementById("kpi-orfaos-banco");
            if (elBanco) elBanco.textContent = d.total_docs_banco || 0;

            const elTotal = document.getElementById("kpi-orfaos-total");
            if (elTotal) elTotal.textContent = d.total_orfaos || 0;

            const elTam = document.getElementById("kpi-orfaos-tamanho");
            if (elTam) elTam.textContent = `${d.tamanho_orfaos_formatado || "0 B"} em disco`;

            if (container) container.style.display = "block";

            if (tbody) {
                if (!d.amostra_orfaos || d.amostra_orfaos.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--pastel-green-text);font-weight:600;">✓ Nenhum arquivo XML órfão encontrado! A pasta de armazenamento está 100% íntegra.</td></tr>`;
                    if (btnApagar) btnApagar.style.display = "none";
                    if (statusMsg) statusMsg.textContent = "Nenhum arquivo órfão.";
                    return;
                }

                tbody.innerHTML = d.amostra_orfaos.map(item => `
                    <tr>
                        <td><code>${escapeHtml(item.filename)}</code></td>
                        <td><small style="color:var(--text-muted);">${escapeHtml(item.chave || "(Sem Chave Válida)")}</small></td>
                        <td>${escapeHtml(item.size_formatted || "0 B")}</td>
                        <td>${escapeHtml(item.modified_at || "--")}</td>
                        <td>
                            ${item.is_corrupt_or_empty ? '<span class="badge-teste-tag">Vazio / Corrompido</span>' : '<span class="badge-teste-tag">Órfão (Sem Banco)</span>'}
                        </td>
                    </tr>
                `).join("");

                if (btnApagar) {
                    btnApagar.style.display = "inline-flex";
                    btnApagar.textContent = `🧹 Apagar ${d.total_orfaos} XMLs Órfãos (${d.tamanho_orfaos_formatado})`;
                }
                if (statusMsg) statusMsg.textContent = `Identificados ${d.total_orfaos} arquivos órfãos.`;
            }
        } else {
            if (statusMsg) statusMsg.textContent = "Erro ao auditar XMLs: " + (res.data?.detail || "Falha");
        }
    } catch (err) {
        if (statusMsg) statusMsg.textContent = "Erro: " + err.message;
    }
}

async function apagarXmlsOrfaosConfirmado() {
    const confirmMsg = `Deseja realmente apagar todos os arquivos XML órfãos do disco?\n\n` +
        `Eles não estão vinculados a nenhuma NF-e no banco de dados e serão excluídos definitivamente de data/xmls/ para recuperar espaço.`;

    if (!confirm(confirmMsg)) return;

    const btnApagar = document.getElementById("btn-apagar-orfaos");
    if (btnApagar) {
        btnApagar.disabled = true;
        btnApagar.textContent = "⏳ Apagando XMLs...";
    }

    try {
        const res = await apiPost("/api/gestao/limpeza/apagar-xmls-orfaos", {});
        const alertDiv = document.getElementById("orfaos-feedback-alert");
        if (alertDiv) {
            alertDiv.style.display = "block";
            if (res.success) {
                alertDiv.className = "result success";
                alertDiv.innerHTML = `<p>✓ ${escapeHtml(res.data?.message || "XMLs órfãos excluídos!")}</p>`;
            } else {
                alertDiv.className = "result error";
                alertDiv.innerHTML = `<p>Erro: ${escapeHtml(res.data?.detail || "Falha na exclusão")}</p>`;
            }
        }

        carregarAuditoriaXmlsOrfaos();
        carregarAuditoriaBase();
    } catch (err) {
        alert("Erro na requisição: " + err.message);
    } finally {
        if (btnApagar) {
            btnApagar.disabled = false;
            btnApagar.textContent = "🧹 Apagar XMLs Órfãos do Disco";
        }
    }
}

async function carregarAuditoriaBase() {
    try {
        const res = await apiGet("/api/gestao/limpeza/auditoria-base");
        if (res.success && res.data) {
            const d = res.data;
            const rn = d.resumo_notas || {};
            const arm = d.armazenamento || {};
            const fs = d.firestore || {};

            const elHora = document.getElementById("auditoria-data-hora");
            if (elHora) elHora.textContent = `Última checagem: ${new Date().toLocaleTimeString("pt-BR")}`;

            const elTot = document.getElementById("audit-kpi-total-docs");
            if (elTot) elTot.textContent = Number(rn.total_docs || 0).toLocaleString("pt-BR");

            const elEnt = document.getElementById("audit-kpi-entradas");
            if (elEnt) elEnt.textContent = `${Number(rn.total_entradas || 0).toLocaleString("pt-BR")}`;

            const elSai = document.getElementById("audit-kpi-saidas");
            if (elSai) elSai.textContent = `${Number(rn.total_saidas || 0).toLocaleString("pt-BR")}`;

            const elCXml = document.getElementById("audit-kpi-com-xml");
            if (elCXml) elCXml.textContent = Number(rn.total_com_xml || 0).toLocaleString("pt-BR");

            const elSXml = document.getElementById("audit-kpi-sem-xml");
            if (elSXml) elSXml.textContent = `${Number(rn.total_sem_xml || 0).toLocaleString("pt-BR")}`;

            const elTst = document.getElementById("audit-kpi-testes");
            if (elTst) elTst.textContent = Number(rn.total_testes_identificados || 0).toLocaleString("pt-BR");

            const elTstVal = document.getElementById("audit-kpi-testes-valor");
            if (elTstVal) elTstVal.textContent = `R$ ${Number(rn.valor_testes_somado || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} somado`;

            const elDb = document.getElementById("audit-kpi-db-size");
            if (elDb) elDb.textContent = `SQLite: ${arm.db_size_formatado || "--"}`;

            const elXmlDir = document.getElementById("audit-kpi-xmls-size");
            if (elXmlDir) elXmlDir.textContent = `${arm.xmls_dir_size_formatado || "--"} (${arm.xmls_count_disco || 0} arquivos)`;

            const elFs = document.getElementById("audit-kpi-firestore");
            if (elFs) elFs.textContent = fs.configurado ? "✓ Conectado" : "Desconectado";

            const elFsP = document.getElementById("audit-kpi-firestore-proj");
            if (elFsP) elFsP.textContent = fs.project_id || "Não configurado";

            // Empresas
            const tbodyEmp = document.getElementById("tbody-audit-empresas");
            if (tbodyEmp) {
                if (!d.empresas || d.empresas.length === 0) {
                    tbodyEmp.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">Nenhum certificado cadastrado.</td></tr>`;
                } else {
                    tbodyEmp.innerHTML = d.empresas.map(emp => `
                        <tr>
                            <td><strong>${escapeHtml(emp.razao_social || "--")}</strong></td>
                            <td><code>${escapeHtml(emp.cnpj || "--")}</code></td>
                            <td>${escapeHtml(emp.valid_to || "--")} <small style="color:var(--text-muted);">(${emp.days_remaining || 0} dias)</small></td>
                            <td><code>${escapeHtml(emp.last_nsu || "0")}</code></td>
                            <td><code>${escapeHtml(emp.max_nsu || "0")}</code></td>
                            <td>${escapeHtml(emp.last_sync_time || "Nunca")}</td>
                            <td><span class="tag-pill">${escapeHtml(emp.last_sync_status || "Pendente")}</span></td>
                        </tr>
                    `).join("");
                }
            }

            // Top Emitentes
            const tbodyEmit = document.getElementById("tbody-audit-emitentes");
            if (tbodyEmit) {
                if (!d.top_emitentes || d.top_emitentes.length === 0) {
                    tbodyEmit.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">Nenhum emitente registrado.</td></tr>`;
                } else {
                    tbodyEmit.innerHTML = d.top_emitentes.map(e => `
                        <tr>
                            <td>
                                <strong>${escapeHtml(e.nome || "--")}</strong>
                                ${e.is_teste_suspeito ? '<span class="badge-teste-tag" style="margin-left:4px;">🧪 Teste / Homol</span>' : ""}
                            </td>
                            <td><code>${escapeHtml(e.cnpj || "--")}</code></td>
                            <td>${escapeHtml(e.uf || "--")}</td>
                            <td style="text-align:right;font-weight:600;">${Number(e.total_notas || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align:right;font-weight:600;">R$ ${Number(e.valor_total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            <td>${escapeHtml(e.ultima_emissao ? e.ultima_emissao.slice(0, 10) : "--")}</td>
                            <td>
                                ${e.is_teste_suspeito ? '<span class="badge-teste-tag">Teste / Homol</span>' : '<span class="badge-real-tag">✓ Normal</span>'}
                            </td>
                        </tr>
                    `).join("");
                }
            }
        }
    } catch (err) {
        console.warn("Erro ao carregar auditoria da base:", err);
    }
}


async function carregarAuditoriaGaps() {
    const container = document.getElementById("resultado-auditoria-gaps");
    const empCnpj = document.getElementById("gaps-filtro-empresa")?.value || "";
    const serie = document.getElementById("gaps-filtro-serie")?.value || "";

    if (container) {
        container.innerHTML = `<div style="text-align:center;padding:30px;"><span class="spinner"></span> Analisando sequência numérica de todas as filiais...</div>`;
    }

    try {
        let url = "/api/gestao/auditoria/gaps-numeracao";
        const params = [];
        if (empCnpj) params.push(`empresa_cnpj=${encodeURIComponent(empCnpj)}`);
        if (serie) params.push(`serie=${encodeURIComponent(serie)}`);
        if (params.length > 0) url += `?${params.join("&")}`;

        const res = await apiGet(url);
        if (!res.success || !res.data) {
            if (container) container.innerHTML = `<div class="result error"><p>Erro ao auditar saltos de numeração: ${escapeHtml(res.data?.detail || "Falha")}</p></div>`;
            return;
        }

        const d = res.data;
        const kpiEmp = document.getElementById("gap-kpi-empresas");
        const kpiGaps = document.getElementById("gap-kpi-gaps");
        const kpiFalt = document.getElementById("gap-kpi-faltando");
        const kpiInut = document.getElementById("gap-kpi-inutilizados");

        if (kpiEmp) kpiEmp.textContent = d.total_empresas_auditadas || 0;
        if (kpiGaps) kpiGaps.textContent = d.total_gaps_encontrados || 0;
        if (kpiFalt) kpiFalt.textContent = Number(d.total_numeros_faltando || 0).toLocaleString("pt-BR");
        if (kpiInut) kpiInut.textContent = Number(d.total_numeros_inutilizados || 0).toLocaleString("pt-BR");

        if (!d.empresas || d.empresas.length === 0) {
            if (container) {
                container.innerHTML = `<div class="result success"><p>✓ Nenhuma nota de saída registrada ou nenhum gap encontrado para os filtros selecionados.</p></div>`;
            }
            return;
        }

        let html = "";
        d.empresas.forEach(emp => {
            emp.series.forEach(s => {
                html += `
                    <div class="painelSessao" style="margin-bottom:16px;">
                        <div class="painelSessaoTitulo" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                            <div>
                                🏢 <b>${escapeHtml(emp.razao_social || emp.cnpj)}</b>
                                <small style="color:var(--text-muted);margin-left:6px;">(CNPJ: ${escapeHtml(emp.cnpj)} | Série: ${escapeHtml(s.serie)})</small>
                            </div>
                            <div>
                                <span class="tag-pill" style="font-size:11px;">Faixa Emitida: Nº ${s.menor_numero} a Nº ${s.maior_numero}</span>
                                <span class="tag-pill" style="font-size:11px;background:#f0fdf4;color:#166534;border-color:#bbf7d0;">Presentes: ${s.total_presente}</span>
                                ${s.total_faltando > 0 ? `<span class="tag-pill" style="font-size:11px;background:#fef2f2;color:#991b1b;border-color:#fecaca;">🚨 ${s.total_faltando} Faltando</span>` : `<span class="tag-pill" style="font-size:11px;background:#f0fdf4;color:#166534;border-color:#bbf7d0;">✓ 100% Contínua</span>`}
                            </div>
                        </div>

                        ${s.gaps && s.gaps.length > 0 ? `
                            <div class="table-responsive" style="margin-top:10px;">
                                <table class="tabelaGrupo">
                                    <thead>
                                        <tr>
                                            <th style="width:20%;">Faixa do Salto (Gap)</th>
                                            <th style="width:12%;text-align:center;">Qtd Números</th>
                                            <th style="width:20%;">Status</th>
                                            <th style="width:30%;">Diagnóstico / Detalhes</th>
                                            <th style="width:18%;text-align:center;">Ações Fiscais</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${s.gaps.map(g => `
                                            <tr>
                                                <td><b style="font-family:monospace;font-size:12px;">${escapeHtml(g.faixa_formatada)}</b></td>
                                                <td style="text-align:center;">${g.quantidade}</td>
                                                <td><span class="${g.badge_class}">${escapeHtml(g.status)}</span></td>
                                                <td style="font-size:11px;color:var(--text-muted);">${escapeHtml(g.detalhes)}</td>
                                                <td style="text-align:center;">
                                                    ${!g.inutilizado ? `
                                                        <button type="button" class="btn-action" onclick="abrirModalInutilizarComDados('${emp.cnpj}', '${s.serie}', ${g.numero_inicio}, ${g.numero_fim});" style="background:#dc2626;color:#fff;border-color:#dc2626;font-size:11px;padding:3px 8px;" title="Transmitir pedido oficial de inutilização à SEFAZ">
                                                            🚫 Inutilizar Faixa
                                                        </button>
                                                    ` : `
                                                        <span style="color:#16a34a;font-size:11px;font-weight:bold;">✓ Regularizada</span>
                                                    `}
                                                </td>
                                            </tr>
                                        `).join("")}
                                    </tbody>
                                </table>
                            </div>
                        ` : `
                            <div style="padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;color:#166534;font-size:12px;margin-top:8px;">
                                ✓ <b>Excelente!</b> Sequência 100% contínua. Não há quebras ou saltos de numeração nesta série.
                            </div>
                        `}
                    </div>
                `;
            });
        });

        if (container) container.innerHTML = html;
    } catch (e) {
        if (container) container.innerHTML = `<div class="result error"><p>Erro ao executar auditoria: ${escapeHtml(e.message)}</p></div>`;
    }
}

function abrirModalInutilizarComDados(cnpj, serie, numIni, numFim) {
    if (typeof abrirModalInutilizarNfe === "function") {
        abrirModalInutilizarNfe();
    } else {
        const modal = document.getElementById("modal-inutilizar-nfe");
        if (modal) modal.style.display = "flex";
    }
    const empSelect = document.getElementById("inutilizar-empresa");
    const serieInp = document.getElementById("inutilizar-serie");
    const numIniInp = document.getElementById("inutilizar-num-ini");
    const numFimInp = document.getElementById("inutilizar-num-fim");
    const justInp = document.getElementById("inutilizar-justificativa");

    if (empSelect) empSelect.value = cnpj;
    if (serieInp) serieInp.value = serie;
    if (numIniInp) numIniInp.value = numIni;
    if (numFimInp) numFimInp.value = numFim;
    if (justInp) justInp.value = `Salto de numeração identificado em auditoria contábil. Numeração não utilizada na emissão.`;
}



// ====================================================================
// GESTÃO DE BACKUPS FISCAIS & TRILHA DE AUDITORIA IMUTÁVEL
// ====================================================================

async function carregarListaBackups() {
    const tbody = document.getElementById("tbody-backups-fiscais");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);"><span class="spinner"></span> Carregando backups fiscais...</td></tr>`;

    try {
        const res = await apiGet("/api/gestao/backups");
        if (res.success && res.data && Array.isArray(res.data.backups)) {
            const backups = res.data.backups;
            if (backups.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Nenhum backup fiscal encontrado. Clique em "Criar Backup Agora" para gerar o primeiro snapshot.</td></tr>`;
                return;
            }

            tbody.innerHTML = backups.map(b => {
                const fn = escapeHtml(b.filename);
                const dataDisplay = escapeHtml(b.created_at_br || b.created_at || "--");
                const tamanhoDisplay = b.size_mb !== undefined ? `${b.size_mb} MB` : escapeHtml(b.size_formatted || "--");
                const sha = escapeHtml(b.sha256 || "");
                const shaShort = sha ? `${sha.slice(0, 8)}...${sha.slice(-8)}` : "--";
                return `
                    <tr>
                        <td style="font-weight:600;">📦 ${fn}</td>
                        <td style="font-size:12px;color:var(--text-muted);">${dataDisplay}</td>
                        <td style="text-align:right;font-weight:600;">${tamanhoDisplay}</td>
                        <td>
                            <code style="font-size:11px;background:rgba(0,0,0,0.04);padding:2px 6px;border-radius:4px;" title="${sha}">${shaShort}</code>
                            ${sha ? `<button type="button" class="botao botao-secundario" style="padding:1px 6px;font-size:10px;margin-left:4px;" onclick="navigator.clipboard.writeText('${sha}');showToast('Hash SHA-256 copiado!','info',2000);">Copiar</button>` : ''}
                        </td>
                        <td style="text-align:center;">
                            <button type="button" class="botao botao-secundario" style="padding:3px 8px;font-size:11px;" onclick="baixarBackupFiscal('${fn}')">
                                ⬇ Download .ZIP
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        } else {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#dc2626;padding:16px;">Falha ao carregar lista: ${escapeHtml(res.data?.error || res.data?.detail || "Erro desconhecido")}</td></tr>`;
        }
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#dc2626;padding:16px;">Erro ao carregar lista de backups: ${escapeHtml(err.message)}</td></tr>`;
    }
}

async function baixarBackupFiscal(filename) {
    if (!filename) return;
    showToast(`Iniciando download do backup ${filename}...`, "info", 2500);
    try {
        const url = `/api/gestao/backups/${encodeURIComponent(filename)}/download`;
        const res = await apiDownload(url, filename);
        if (res.ok) {
            const blobUrl = window.URL.createObjectURL(res.blob);
            const a = document.createElement("a");
            a.href = blobUrl;
            a.download = res.filename || filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(blobUrl);
            showToast(`Download de ${filename} concluído!`, "success");
        } else {
            showToast(`Erro ao baixar backup: ${res.error || "Falha"}`, "error");
        }
    } catch (err) {
        showToast(`Erro no download: ${err.message}`, "error");
    }
}

async function executarBackupFiscalManual() {
    const btn = document.getElementById("btn-gerar-backup-manual");
    const statusArea = document.getElementById("backup-status-area");

    if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ Gerando Snapshot...";
    }
    if (statusArea) {
        statusArea.style.display = "block";
        statusArea.innerHTML = `<div style="padding:10px 14px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;color:#1e40af;font-size:12px;">
            Executando snapshot a quente do banco de dados SQLite e empacotando XMLs fiscais...
        </div>`;
    }

    try {
        const res = await apiPost("/api/gestao/cloud/backup", {});
        if (res.success && res.data && res.data.details) {
            const det = res.data.details;
            showToast("✅ Backup fiscal concluído com sucesso!", "success");
            if (statusArea) {
                statusArea.innerHTML = `<div style="padding:10px 14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;color:#166534;font-size:12px;">
                    ✓ <b>Backup gerado com sucesso:</b> <code>${escapeHtml(det.filename)}</code> (${det.size_formatted}, ${det.xml_count} XMLs inclusos). Hash: <code style="font-size:10px;">${escapeHtml(det.sha256)}</code>
                </div>`;
            }
            await carregarListaBackups();
        } else {
            const errMsg = res.data?.detail || res.data?.message || "Falha ao gerar backup";
            showToast(`❌ Erro: ${errMsg}`, "error", 6000, res.requestId);
            if (statusArea) {
                statusArea.innerHTML = `<div style="padding:10px 14px;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;color:#991b1b;font-size:12px;">
                    ❌ Erro ao criar backup: ${escapeHtml(errMsg)}
                </div>`;
            }
        }
    } catch (err) {
        showToast(`Erro ao criar backup: ${err.message}`, "error");
        if (statusArea) {
            statusArea.innerHTML = `<div style="padding:10px 14px;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;color:#991b1b;font-size:12px;">
                ❌ Erro na requisição: ${escapeHtml(err.message)}
            </div>`;
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "⚡ Criar Backup Agora";
        }
    }
}

let _auditCurrentPage = 1;

async function carregarTrilhaAuditoria(page = 1) {
    _auditCurrentPage = page;
    const tbody = document.getElementById("tbody-trilha-auditoria");
    const paginacao = document.getElementById("audit-paginacao");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);"><span class="spinner"></span> Carregando registros de auditoria...</td></tr>`;

    const acaoFiltro = document.getElementById("filtro-audit-acao")?.value || "";
    const userFiltro = document.getElementById("filtro-audit-usuario")?.value || "";

    const params = [`page=${page}`, `limit=20`];
    if (acaoFiltro) params.push(`acao=${encodeURIComponent(acaoFiltro)}`);
    if (userFiltro) params.push(`usuario_email=${encodeURIComponent(userFiltro)}`);

    try {
        const res = await apiGet(`/api/gestao/auditoria?${params.join("&")}`);
        if (res.success && res.data) {
            const logs = res.data.logs || res.data.items || [];
            const total = res.data.total || 0;
            const limit = res.data.limit || 20;
            const pages = Math.max(1, Math.ceil(total / limit));

            if (logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted);">Nenhum registro de auditoria encontrado com os filtros selecionados.</td></tr>`;
                if (paginacao) paginacao.innerHTML = "";
                return;
            }

            const getBadgeForAction = (act) => {
                switch (act) {
                    case "LOGIN":
                        return '<span style="background:#dcfce7;color:#166534;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">🔑 LOGIN</span>';
                    case "LOGOUT":
                        return '<span style="background:#f1f5f9;color:#475569;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">🚪 LOGOUT</span>';
                    case "MANIFESTACAO":
                        return '<span style="background:#e0e7ff;color:#3730a3;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">📑 MANIFESTAÇÃO</span>';
                    case "EXCLUSAO":
                        return '<span style="background:#fee2e2;color:#991b1b;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">🗑️ EXCLUSÃO</span>';
                    case "BACKUP_CRIADO":
                        return '<span style="background:#f3e8ff;color:#6b21a8;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">📦 BACKUP CRIADO</span>';
                    default:
                        return `<span style="background:#f3f4f6;color:#374151;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">${escapeHtml(act)}</span>`;
                }
            };

            tbody.innerHTML = logs.map(it => {
                const dataFormatada = it.timestamp ? it.timestamp.replace("T", " ").slice(0, 19) : "--";
                const userDisplay = it.usuario_nome ? `${escapeHtml(it.usuario_nome)} <span style="font-size:11px;color:var(--text-muted);">(${escapeHtml(it.usuario_email || "")})</span>` : escapeHtml(it.usuario_email || "Sistema");
                const entidadeInfo = it.entidade ? `<span style="font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;">[${escapeHtml(it.entidade)}${it.entidade_id ? ' #' + escapeHtml(it.entidade_id) : ''}]</span> ` : '';
                const detalheTexto = escapeHtml(it.detalhe || "--");

                return `
                    <tr>
                        <td style="font-size:12px;white-space:nowrap;">${dataFormatada}</td>
                        <td style="font-size:12px;">${userDisplay}</td>
                        <td>${getBadgeForAction(it.acao)}</td>
                        <td style="font-size:12px;font-family:monospace;">${escapeHtml(it.ip || "--")}</td>
                        <td style="font-size:12px;max-width:350px;word-break:break-word;">${entidadeInfo}${detalheTexto}</td>
                    </tr>
                `;
            }).join("");

            if (paginacao) {
                paginacao.innerHTML = `
                    <div>Total de <b>${total}</b> eventos registrados (Página <b>${page}</b> de <b>${pages}</b>)</div>
                    <div style="display:flex;gap:6px;">
                        <button type="button" class="botao botao-secundario" style="padding:3px 10px;font-size:12px;"
                            ${page <= 1 ? 'disabled' : ''} onclick="carregarTrilhaAuditoria(${page - 1})">
                            ◀ Anterior
                        </button>
                        <button type="button" class="botao botao-secundario" style="padding:3px 10px;font-size:12px;"
                            ${page >= pages ? 'disabled' : ''} onclick="carregarTrilhaAuditoria(${page + 1})">
                            Próxima ▶
                        </button>
                    </div>
                `;
            }
        } else {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#dc2626;padding:16px;">Falha ao carregar trilha de auditoria: ${escapeHtml(res.data?.detail || "Erro")}</td></tr>`;
        }
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#dc2626;padding:16px;">Erro ao carregar trilha: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// ====================================================================
// 1. GESTÃO FINANCEIRA & CONTAS A PAGAR (DUPLICATAS DE NF-e)
// ====================================================================

let filtroStatusContasAtual = "";
