// ====================================================================
// ATALHOS DE TECLADO — Ctrl+K busca global, Esc fecha modal, / foca busca
// ====================================================================

(function () {
    'use strict';

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function isTypingTarget(el) {
        if (!el) return false;
        const tag = el.tagName?.toLowerCase();
        return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
    }

    document.addEventListener('keydown', (e) => {
        // Ctrl+K / Cmd+K — busca global
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openGlobalSearch();
            return;
        }
        // "/" foca busca global (só se não estiver digitando)
        if (e.key === '/' && !isTypingTarget(e.target) && !e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            openGlobalSearch();
            return;
        }
        // Esc — fecha modal aberto (se não estiver em input)
        if (e.key === 'Escape') {
            const m = document.querySelector('.modal-backdrop:not(.modal-hide):not([style*="display: none"])');
            if (m) {
                const cancelBtn = m.querySelector('#confirm-cancel, [data-dismiss="modal"]');
                if (cancelBtn) cancelBtn.click();
                else m.click(); // fecha via backdrop
            }
        }
    });

    function openGlobalSearch() {
        // Se já existe, foca o input
        const old = document.getElementById('global-search-modal');
        if (old) {
            const inp = document.getElementById('global-search-input');
            if (inp) inp.focus();
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'global-search-modal';
        modal.className = 'modal-backdrop';
        modal.innerHTML = `
            <div class="modal-content global-search-box" role="dialog" aria-modal="true">
                <div class="global-search-input-wrap">
                    <input type="text" id="global-search-input"
                           placeholder="🔍 Buscar NF-e, cliente, produto…"
                           autocomplete="off">
                </div>
                <div id="global-search-results" class="global-search-results">
                    <div class="global-search-empty">
                        ⌨️ Digite para buscar<br>
                        <small style="font-size:11px;opacity:0.7;">NF-e por chave • Clientes por nome/CPF • Produtos por código</small>
                    </div>
                </div>
                <div class="global-search-footer">
                    <kbd>Esc</kbd> fechar &nbsp;•&nbsp; <kbd>Enter</kbd> abrir &nbsp;•&nbsp; <kbd>↑↓</kbd> navegar
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        setTimeout(() => document.getElementById('global-search-input').focus(), 50);

        let timeout = null;
        modal.querySelector('#global-search-input').addEventListener('input', (e) => {
            clearTimeout(timeout);
            const term = e.target.value.trim();
            const results = document.getElementById('global-search-results');
            if (!term) {
                results.innerHTML = `
                    <div class="global-search-empty">
                        ⌨️ Digite para buscar<br>
                        <small style="font-size:11px;opacity:0.7;">NF-e por chave • Clientes por nome/CPF • Produtos por código</small>
                    </div>
                `;
                return;
            }
            timeout = setTimeout(() => performGlobalSearch(term), 250);
        });

        // Fechar ao clicar fora (no backdrop, não no conteúdo)
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }

    async function performGlobalSearch(term) {
        const results = document.getElementById('global-search-results');
        if (!results) return;
        results.innerHTML = `<div class="global-search-empty">Buscando…</div>`;
        try {
            // Chama 3 endpoints em paralelo (não falha se um der erro)
            const [nfe, cli, prod] = await Promise.allSettled([
                fetch(`/api/emissao/saidas?busca=${encodeURIComponent(term)}&limit=5`, { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : { data: { documentos: [] } })
                    .catch(() => ({ data: { documentos: [] } })),
                fetch(`/api/emissao/clientes?busca=${encodeURIComponent(term)}&limit=5`, { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : { data: { clientes: [] } })
                    .catch(() => ({ data: { clientes: [] } })),
                fetch(`/api/emissao/produtos?busca=${encodeURIComponent(term)}&limit=5`, { credentials: 'same-origin' })
                    .then(r => r.ok ? r.json() : { data: { produtos: [] } })
                    .catch(() => ({ data: { produtos: [] } })),
            ]);
            renderResults(results, term, nfe, cli, prod);
        } catch (err) {
            results.innerHTML = `<div class="global-search-empty" style="color:#c0392b;">Erro: ${escapeHtml(err.message)}</div>`;
        }
    }

    function renderResults(container, term, nfe, cli, prod) {
        const nfeDocs = nfe.status === 'fulfilled' ? (nfe.value?.data?.documentos || nfe.value?.documentos || []) : [];
        const cliList = cli.status === 'fulfilled' ? (cli.value?.data?.clientes || cli.value?.clientes || []) : [];
        const prodList = prod.status === 'fulfilled' ? (prod.value?.data?.produtos || prod.value?.produtos || []) : [];

        if (nfeDocs.length === 0 && cliList.length === 0 && prodList.length === 0) {
            container.innerHTML = `<div class="global-search-empty">Nenhum resultado para "${escapeHtml(term)}"</div>`;
            return;
        }

        let html = '';
        if (nfeDocs.length) {
            html += `<div class="global-search-group">📄 NF-e (${nfeDocs.length})</div>`;
            nfeDocs.slice(0, 5).forEach(d => {
                const nome = d.destinatario_nome || d.emitente_nome || d.destinatario?.nome || d.emitente?.nome || '(sem nome)';
                const data = (d.data_emissao || '').substring(0, 10);
                const num = d.numero || d.chave?.slice(-6) || '?';
                html += `<a href="#" class="global-search-item" onclick="fecharBuscaGlobalEAbrirNfe('${escapeHtml(d.chave || '')}');return false;">
                    <b>NF-e ${escapeHtml(String(num))}</b> — ${escapeHtml(nome)} <small>${escapeHtml(data)}</small>
                </a>`;
            });
        }
        if (cliList.length) {
            html += `<div class="global-search-group">👥 Clientes (${cliList.length})</div>`;
            cliList.slice(0, 5).forEach(c => {
                const doc = c.cpf_cnpj || c.cnpj_cpf || c.documento || '';
                html += `<a href="#" class="global-search-item" onclick="fecharBuscaGlobalEAbrirCliente('${escapeHtml(String(c.id || ''))}');return false;">
                    <b>${escapeHtml(c.razao_social || c.nome || '(sem nome)')}</b> <small>${escapeHtml(doc)}</small>
                </a>`;
            });
        }
        if (prodList.length) {
            html += `<div class="global-search-group">📦 Produtos (${prodList.length})</div>`;
            prodList.slice(0, 5).forEach(p => {
                html += `<a href="#" class="global-search-item" onclick="fecharBuscaGlobalEAbrirProduto('${escapeHtml(String(p.id || ''))}');return false;">
                    <b>${escapeHtml(p.codigo || '')}</b> — ${escapeHtml(p.descricao || '')}
                </a>`;
            });
        }
        container.innerHTML = html;
    }

    window.openGlobalSearch = openGlobalSearch;

    // Helpers de navegação ao clicar num resultado
    window.fecharBuscaGlobalEAbrirNfe = (chave) => {
        const modal = document.getElementById('global-search-modal');
        if (modal) modal.remove();
        if (typeof showSection === 'function') showSection('emissao');
        if (chave && typeof carregarDetalhesNfe === 'function') {
            carregarDetalhesNfe(chave);
        }
    };
    window.fecharBuscaGlobalEAbrirCliente = (id) => {
        const modal = document.getElementById('global-search-modal');
        if (modal) modal.remove();
        if (typeof showSection === 'function') showSection('cadastros');
        if (id && typeof abrirModalEditarCliente === 'function') {
            abrirModalEditarCliente(id);
        }
    };
    window.fecharBuscaGlobalEAbrirProduto = (id) => {
        const modal = document.getElementById('global-search-modal');
        if (modal) modal.remove();
        if (typeof showSection === 'function') showSection('cadastros');
        if (id && typeof abrirModalEditarProduto === 'function') {
            abrirModalEditarProduto(id);
        }
    };
})();
