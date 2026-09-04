// ====================================================================
// SISTEMA DE FEEDBACK VISUAL — TOAST + MODAL DE CONFIRMAÇÃO
// Reutilizável. Substitui alert()/confirm() nativos do browser.
// ====================================================================

(function () {
    'use strict';

    // ---------- HELPERS ----------
    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ====================================================================
    // TOAST — notificações flutuantes canto inferior direito
    // ====================================================================

    function ensureContainer() {
        let c = document.getElementById('toast-container');
        if (!c) {
            c = document.createElement('div');
            c.id = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    const TOAST_ICONS = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

    function showToast(message, type = 'info', duration = 4000, requestId = null) {
        const container = ensureContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
        toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        const reqHtml = requestId ? `<div style="font-size:10.5px;opacity:0.85;margin-top:4px;font-family:monospace;user-select:all;">ID: ${escapeHtml(requestId)}</div>` : '';
        toast.innerHTML = `
            <span class="toast-icon" aria-hidden="true">${TOAST_ICONS[type] || 'ℹ'}</span>
            <div style="display:flex;flex-direction:column;flex:1;">
                <span class="toast-msg">${escapeHtml(String(message))}</span>
                ${reqHtml}
            </div>
            <button type="button" class="toast-close" aria-label="Fechar notificação">×</button>
        `;
        container.appendChild(toast);

        // anima entrada
        requestAnimationFrame(() => toast.classList.add('toast-show'));

        const dismiss = () => {
            if (toast.classList.contains('toast-hide')) return;
            toast.classList.remove('toast-show');
            toast.classList.add('toast-hide');
            setTimeout(() => toast.remove(), 300);
        };
        toast.querySelector('.toast-close').addEventListener('click', dismiss);
        if (duration > 0) setTimeout(dismiss, duration);
        return dismiss;
    }

    // Atalhos
    const toast = {
        success: (m, d, r) => showToast(m, 'success', d, r),
        error:   (m, d, r) => showToast(m, 'error',   d ?? 6000, r),
        warning: (m, d, r) => showToast(m, 'warning', d ?? 5000, r),
        info:    (m, d, r) => showToast(m, 'info',    d, r),
    };

    // ====================================================================
    // MODAL DE CONFIRMAÇÃO — substitui window.confirm()
    // ====================================================================

    function showConfirmModal({
        title = 'Confirmar',
        message = '',
        confirmText = 'Confirmar',
        cancelText = 'Cancelar',
        danger = false,
        icon = '⚠',
    } = {}) {
        return new Promise((resolve) => {
            // Remove modal anterior se houver (evita empilhar)
            const old = document.getElementById('confirm-modal');
            if (old) old.remove();

            const modal = document.createElement('div');
            modal.id = 'confirm-modal';
            modal.className = 'modal-backdrop';
            modal.innerHTML = `
                <div class="modal-content modal-confirm" role="dialog" aria-modal="true"
                     aria-labelledby="confirm-title" style="max-width:440px;">
                    <div class="modal-confirm-icon modal-confirm-icon-${danger ? 'danger' : 'warn'}"
                         aria-hidden="true">${escapeHtml(icon)}</div>
                    <h3 id="confirm-title" class="modal-confirm-title">${escapeHtml(title)}</h3>
                    <p class="modal-confirm-msg">${escapeHtml(message)}</p>
                    <div class="modal-confirm-actions">
                        <button type="button" class="botao botao-secundario" id="confirm-cancel">
                            ${escapeHtml(cancelText)}
                        </button>
                        <button type="button" class="botao ${danger ? 'botao-perigo' : 'botao-primario'}"
                                id="confirm-ok" autofocus>
                            ${escapeHtml(confirmText)}
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            const previousOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';

            let done = false;
            const cleanup = (result) => {
                if (done) return;
                done = true;
                modal.classList.add('modal-hide');
                document.removeEventListener('keydown', onKey);
                setTimeout(() => {
                    modal.remove();
                    document.body.style.overflow = previousOverflow;
                    resolve(result);
                }, 150);
            };

            modal.querySelector('#confirm-cancel').addEventListener('click', () => cleanup(false));
            modal.querySelector('#confirm-ok').addEventListener('click', () => cleanup(true));
            modal.addEventListener('click', (e) => {
                if (e.target === modal) cleanup(false); // clique no backdrop
            });
            function onKey(e) {
                if (e.key === 'Escape') cleanup(false);
                else if (e.key === 'Enter') cleanup(true);
            }
            document.addEventListener('keydown', onKey);

            // Foco inicial no botão OK
            setTimeout(() => modal.querySelector('#confirm-ok').focus(), 50);
        });
    }

    // Expor globalmente
    window.toast = toast;
    window.showConfirmModal = showConfirmModal;
    window.showToast = showToast;

    // ====================================================================
    // EMPTY STATE — placeholder visual quando lista está vazia
    // ====================================================================

    function renderEmptyState({ icon = '📭', title = 'Nada por aqui', description = '',
                                actionHtml = '', containerId = '' }) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">${escapeHtml(icon)}</div>
                <div class="empty-state-title">${escapeHtml(title)}</div>
                ${description ? `<div class="empty-state-desc">${escapeHtml(description)}</div>` : ''}
                ${actionHtml ? `<div class="empty-state-action">${actionHtml}</div>` : ''}
            </div>
        `;
    }
    window.renderEmptyState = renderEmptyState;

    // ====================================================================
    // TEMA — alterna entre claro/escuro, persiste em localStorage
    // ====================================================================

    function getTheme() {
        return localStorage.getItem('nfe_theme')
            || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        const btn = document.getElementById('btn-theme-toggle');
        if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
        try { localStorage.setItem('nfe_theme', theme); } catch (_) {}
    }

    function toggleTheme() {
        applyTheme(getTheme() === 'dark' ? 'light' : 'dark');
    }

    window.toggleTheme = toggleTheme;
    window.getTheme = getTheme;
    window.applyTheme = applyTheme;

    // Aplica imediatamente para evitar flash
    applyTheme(getTheme());

    // Ativa botão "voltar ao topo" quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupBackToTop);
    } else {
        setupBackToTop();
    }

    // ====================================================================
    // VOLTAR AO TOPO — floating button canto inferior esquerdo
    // ====================================================================

    function setupBackToTop() {
        // Não duplica se já existe
        if (document.getElementById('btn-back-to-top')) return;
        const btn = document.createElement('button');
        btn.id = 'btn-back-to-top';
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Voltar ao topo');
        btn.innerHTML = '↑';
        btn.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
        document.body.appendChild(btn);

        const toggle = () => {
            if (window.scrollY > 300) btn.classList.add('show');
            else btn.classList.remove('show');
        };
        window.addEventListener('scroll', toggle, { passive: true });
        toggle();
    }
    window.setupBackToTop = setupBackToTop;
})();
