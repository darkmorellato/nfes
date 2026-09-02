// ====================================================================
// TOUR GUIADO — primeira visita mostra 5 passos curtos
// Persiste em localStorage para não aparecer novamente
// ====================================================================

(function () {
    'use strict';

    const STORAGE_KEY = 'nfe_tour_done';
    const STEPS = [
        { selector: '#menuWrapper', title: 'Menu principal', description: 'Aqui você acessa Emissão, Cadastros, Relatórios, Gestão e Sync com Firestore.' },
        { selector: '#cabecalho', title: 'Cabeçalho', description: 'Notificações, certificados, configurações e alternador de tema claro/escuro.' },
        { selector: '[data-section-link="emissao"]', title: 'Emissão de NF-e', description: 'Emita notas fiscais com certificado digital A1. Suporta venda, devolução e transferência.' },
        { selector: '[data-section-link="gestao"]', title: 'Gestão & BI', description: 'KPIs, relatórios, fechamento contábil e sincronização 24h com Cloud Firestore.' },
        { selector: '#divCentral', title: 'Atalhos úteis', description: 'Ctrl+K abre a busca global. Esc fecha modais. O botão ↑ no canto volta ao topo. Boa navegação!', center: true },
    ];

    let currentStep = 0;
    let overlay, tooltip;

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function shouldShow() {
        try { return localStorage.getItem(STORAGE_KEY) !== '1'; }
        catch (_) { return true; }
    }

    function start() {
        if (!shouldShow()) return;
        currentStep = 0;
        createOverlay();
        showStep(0);
    }

    function createOverlay() {
        overlay = document.createElement('div');
        overlay.id = 'tour-overlay';
        overlay.innerHTML = `<div class="tour-spotlight"></div>`;
        document.body.appendChild(overlay);

        tooltip = document.createElement('div');
        tooltip.id = 'tour-tooltip';
        document.body.appendChild(tooltip);
    }

    function showStep(i) {
        if (i >= STEPS.length) return end();
        const step = STEPS[i];
        const target = step.center ? null : document.querySelector(step.selector);
        if (!step.center && !target) { showStep(i + 1); return; }

        const spot = overlay.querySelector('.tour-spotlight');
        if (step.center) {
            spot.style.top = '50%';
            spot.style.left = '50%';
            spot.style.transform = 'translate(-50%, -50%)';
            spot.style.width = '90vw';
            spot.style.height = '80vh';
        } else {
            const rect = target.getBoundingClientRect();
            spot.style.transform = 'none';
            spot.style.top = (rect.top - 6) + 'px';
            spot.style.left = (rect.left - 6) + 'px';
            spot.style.width = (rect.width + 12) + 'px';
            spot.style.height = (rect.height + 12) + 'px';
        }

        if (step.center) {
            tooltip.style.top = '50%';
            tooltip.style.left = '50%';
            tooltip.style.transform = 'translate(-50%, -50%)';
        } else {
            const rect = target.getBoundingClientRect();
            const isBelow = rect.top < window.innerHeight / 2;
            tooltip.style.transform = 'none';
            tooltip.style.top = isBelow ? (rect.bottom + 14) + 'px' : (rect.top - 130) + 'px';
            tooltip.style.left = Math.max(10, Math.min(window.innerWidth - 360, rect.left)) + 'px';
        }
        tooltip.innerHTML = `
            <div class="tour-step">${i + 1}/${STEPS.length}</div>
            <h3>${escapeHtml(step.title)}</h3>
            <p>${escapeHtml(step.description)}</p>
            <div class="tour-actions">
                <button type="button" class="botao botao-secundario" id="tour-skip">Pular</button>
                <button type="button" class="botao botao-primario" id="tour-next">${i === STEPS.length - 1 ? 'Concluir' : 'Próximo →'}</button>
            </div>
        `;
        tooltip.querySelector('#tour-skip').onclick = end;
        tooltip.querySelector('#tour-next').onclick = () => showStep(i + 1);
    }

    function end() {
        try { localStorage.setItem(STORAGE_KEY, '1'); } catch (_) {}
        if (overlay) { overlay.remove(); overlay = null; }
        if (tooltip) { tooltip.remove(); tooltip = null; }
    }

    window.startTour = start;
    window.resetTour = () => {
        try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
        start();
    };

    // Auto-start após login (1.5s) — só se o usuário ainda não viu
    if (shouldShow()) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => setTimeout(start, 1500));
        } else {
            setTimeout(start, 1500);
        }
    }
})();
