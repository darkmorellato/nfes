// ====================================================================
// UPDATER — Atualizador Automático do Sistema via GitHub
// ====================================================================

async function verificarAtualizacoes(showFeedback = false) {
    const badgeHeader = document.getElementById("badge-update-available");
    const modalLoading = document.getElementById("modal-update-loading");
    const modalContent = document.getElementById("modal-update-content");

    if (showFeedback && modalLoading && modalContent) {
        modalLoading.style.display = "block";
        modalContent.style.display = "none";
    }

    try {
        let data = null;
        if (typeof apiGet === "function") {
            const resp = await apiGet("/api/gestao/sistema/atualizacao/status");
            if (!resp.success) {
                throw new Error(resp.data?.error || resp.data?.detail || `HTTP ${resp.status}`);
            }
            data = resp.data;
        } else {
            const token = (typeof AuthSession !== "undefined" && AuthSession?.token) || "";
            const headers = token ? { "X-Session-Token": token } : {};
            const resp = await fetch("/api/gestao/sistema/atualizacao/status", { headers });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            data = await resp.json();
        }

        if (!data) throw new Error("Resposta vazia do servidor.");

        // 1. Atualiza Badge no Header
        if (badgeHeader) {
            if (data.has_update) {
                badgeHeader.style.display = "inline-block";
                badgeHeader.textContent = `${data.commits_behind || 'NOVA'} NOVA(S)`;
            } else {
                badgeHeader.style.display = "none";
            }
        }

        // 2. Atualiza Modal
        if (modalContent) {
            const statusTitle = document.getElementById("modal-update-status-title");
            const statusBadge = document.getElementById("modal-update-badge");
            const localHash = document.getElementById("modal-update-local-hash");
            const localDate = document.getElementById("modal-update-local-date");
            const branchEl = document.getElementById("modal-update-branch");
            const repoEl = document.getElementById("modal-update-repo");
            const pendingBox = document.getElementById("modal-update-pending-box");
            const commitsList = document.getElementById("modal-update-commits");
            const btnUpdate = document.getElementById("btn-modal-executar-update");

            if (statusTitle) statusTitle.textContent = data.message || (data.has_update ? "Nova versão disponível no GitHub!" : "Sistema 100% atualizado!");
            if (statusBadge) {
                statusBadge.textContent = data.has_update ? "🚀 ATUALIZAÇÃO DISPONÍVEL" : "🟢 ATUALIZADO";
                statusBadge.style.background = data.has_update ? "#dcfce7" : "#f1f5f9";
                statusBadge.style.color = data.has_update ? "#166534" : "#475569";
            }

            if (localHash) localHash.textContent = data.local_commit || "--";
            if (localDate) localDate.textContent = data.local_date || "--";
            if (branchEl) branchEl.textContent = data.branch || "main";
            if (repoEl) repoEl.textContent = data.remote_url || "GitHub";

            if (pendingBox && commitsList) {
                if (data.has_update && data.pending_commits && data.pending_commits.length > 0) {
                    commitsList.innerHTML = data.pending_commits.map(c => `<li><code>${escapeHtml(c)}</code></li>`).join("");
                    pendingBox.style.display = "block";
                } else {
                    pendingBox.style.display = "none";
                }
            }

            if (btnUpdate) {
                btnUpdate.style.display = data.has_update ? "inline-block" : "none";
            }

            if (modalLoading) modalLoading.style.display = "none";
            modalContent.style.display = "block";
        }

        // 3. Atualiza Subaba em Configurações
        const cfgStatusText = document.getElementById("cfg-update-status-text");
        const cfgLocalCommit = document.getElementById("cfg-update-local-commit");
        const cfgLocalDate = document.getElementById("cfg-update-local-date");
        const cfgBranch = document.getElementById("cfg-update-branch");
        const cfgBtnUpdate = document.getElementById("btn-cfg-executar-update");
        const cfgPendingSec = document.getElementById("cfg-update-pending-section");
        const cfgCommitsList = document.getElementById("cfg-update-commits-list");

        if (cfgStatusText) {
            cfgStatusText.textContent = data.has_update ? "🚀 Nova versão disponível no repositório!" : "🟢 Sistema atualizado com a versão mais recente.";
            cfgStatusText.style.color = data.has_update ? "#16a34a" : "#0f172a";
        }
        if (cfgLocalCommit) cfgLocalCommit.textContent = data.local_commit || "--";
        if (cfgLocalDate) cfgLocalDate.textContent = data.local_date || "--";
        if (cfgBranch) cfgBranch.textContent = data.branch || "main";
        if (cfgBtnUpdate) cfgBtnUpdate.style.display = data.has_update ? "inline-block" : "none";

        if (cfgPendingSec && cfgCommitsList) {
            if (data.has_update && data.pending_commits && data.pending_commits.length > 0) {
                cfgCommitsList.innerHTML = data.pending_commits.map(c => `<li><code>${escapeHtml(c)}</code></li>`).join("");
                cfgPendingSec.style.display = "block";
            } else {
                cfgPendingSec.style.display = "none";
            }
        }

        if (showFeedback && typeof showToast === "function") {
            if (data.has_update) {
                showToast("🚀 Nova versão encontrada no GitHub!", "info");
            } else {
                showToast("✅ O sistema já está na versão mais recente.", "success");
            }
        }

    } catch (err) {
        console.warn("[Updater] Erro ao checar atualizações:", err);
        if (modalLoading && modalContent) {
            modalLoading.style.display = "none";
            modalContent.style.display = "block";
            const statusTitle = document.getElementById("modal-update-status-title");
            if (statusTitle) statusTitle.textContent = `Não foi possível verificar atualizações: ${err.message}`;
        }
    }
}

function abrirModalAtualizacao() {
    const modal = document.getElementById("modal-atualizacao-sistema");
    if (modal) {
        modal.style.display = "flex";
        const terminal = document.getElementById("modal-update-terminal");
        if (terminal) terminal.style.display = "none";
        const btnReload = document.getElementById("btn-modal-recarregar");
        if (btnReload) btnReload.style.display = "none";
        verificarAtualizacoes(true);
    }
}

function fecharModalAtualizacao() {
    const modal = document.getElementById("modal-atualizacao-sistema");
    if (modal) modal.style.display = "none";
}

async function executarAtualizacaoSistema() {
    const btnModal = document.getElementById("btn-modal-executar-update");
    const btnCfg = document.getElementById("btn-cfg-executar-update");
    const terminalModal = document.getElementById("modal-update-terminal");
    const terminalCfg = document.getElementById("cfg-update-log-terminal");
    const btnReload = document.getElementById("btn-modal-recarregar");

    if (btnModal) { btnModal.disabled = true; btnModal.innerHTML = "⏳ Atualizando..."; }
    if (btnCfg) { btnCfg.disabled = true; btnCfg.innerHTML = "⏳ Atualizando..."; }

    if (terminalModal) {
        terminalModal.style.display = "block";
        terminalModal.textContent = "⏳ Conectando ao GitHub e baixando novidades...\n";
    }
    if (terminalCfg) {
        terminalCfg.style.display = "block";
        terminalCfg.textContent = "⏳ Conectando ao GitHub e baixando novidades...\n";
    }

    try {
        let data = null;
        if (typeof apiPost === "function") {
            const resp = await apiPost("/api/gestao/sistema/atualizacao/executar", {});
            data = resp.data || {};
            if (!resp.success && !data.message) {
                data.message = data.error || data.detail || `HTTP ${resp.status}`;
            }
        } else {
            const token = (typeof AuthSession !== "undefined" && AuthSession?.token) || "";
            const headers = { "Content-Type": "application/json" };
            if (token) headers["X-Session-Token"] = token;
            const resp = await fetch("/api/gestao/sistema/atualizacao/executar", {
                method: "POST",
                headers,
                body: JSON.stringify({})
            });
            data = await resp.json();
        }

        if (terminalModal) terminalModal.textContent = data.logs || (data.success ? "Atualização concluída!" : `Erro: ${data.message}`);
        if (terminalCfg) terminalCfg.textContent = data.logs || (data.success ? "Atualização concluída!" : `Erro: ${data.message}`);

        if (data.success) {
            if (typeof showToast === "function") showToast("🎉 Sistema atualizado com sucesso!", "success");
            if (btnModal) btnModal.style.display = "none";
            if (btnCfg) btnCfg.style.display = "none";
            if (btnReload) btnReload.style.display = "inline-block";

            // Atualiza status após sucesso
            setTimeout(() => {
                verificarAtualizacoes(false);
            }, 1000);
        } else {
            if (typeof showToast === "function") showToast(`❌ ${data.message || "Erro na atualização"}`, "error");
            if (btnModal) { btnModal.disabled = false; btnModal.innerHTML = "🚀 Tentar Novamente"; }
            if (btnCfg) { btnCfg.disabled = false; btnCfg.innerHTML = "🚀 Tentar Novamente"; }
        }
    } catch (err) {
        const errTxt = `❌ Erro de conexão durante a atualização: ${err.message}`;
        if (terminalModal) terminalModal.textContent += `\n${errTxt}`;
        if (terminalCfg) terminalCfg.textContent += `\n${errTxt}`;
        if (btnModal) { btnModal.disabled = false; btnModal.innerHTML = "🚀 Tentar Novamente"; }
        if (btnCfg) { btnCfg.disabled = false; btnCfg.innerHTML = "🚀 Tentar Novamente"; }
    }
}
