// ====================================================================
// SKELETON LOADERS — feedback visual enquanto dados carregam
// ====================================================================

(function () {
    'use strict';

    /**
     * Preenche um <tbody> com linhas skeleton.
     * @param {string} tbodyId - id do <tbody> a ser preenchido
     * @param {number} colspan - número de colunas da tabela
     * @param {number} numRows - quantas linhas skeleton renderizar
     */
    function skeletonTable(tbodyId, colspan = 8, numRows = 8) {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        const cells = Array(colspan).fill(0).map(() =>
            `<td><div class="skeleton skeleton-line"></div></td>`
        ).join('');
        tbody.innerHTML = Array(numRows).fill(0).map(() =>
            `<tr class="skeleton-row">${cells}</tr>`
        ).join('');
    }

    /**
     * Preenche um container com cards skeleton (KPIs, dashboards).
     * @param {string} containerId - id do container
     * @param {number} numCards - quantos cards skeleton renderizar
     */
    function skeletonCards(containerId, numCards = 4) {
        const c = document.getElementById(containerId);
        if (!c) return;
        c.innerHTML = Array(numCards).fill(0).map(() => `
            <div class="skeleton-card">
                <div class="skeleton skeleton-line" style="width:60%;height:14px;margin-bottom:8px;"></div>
                <div class="skeleton skeleton-line" style="width:40%;height:24px;margin-bottom:6px;"></div>
                <div class="skeleton skeleton-line" style="width:80%;height:11px;"></div>
            </div>
        `).join('');
    }

    /**
     * Skeleton inline para um elemento específico (substitui "Carregando...").
     * @param {string} elId - id do elemento
     * @param {string} text - texto a mostrar (default "Carregando...")
     */
    function skeletonText(elId, text = 'Carregando…') {
        const el = document.getElementById(elId);
        if (!el) return;
        el.innerHTML = `<span class="skeleton-inline">${text}</span>`;
    }

    window.skeletonTable = skeletonTable;
    window.skeletonCards = skeletonCards;
    window.skeletonText = skeletonText;
})();
