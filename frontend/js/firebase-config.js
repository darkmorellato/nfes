/**
 * Integração Google Firebase & Cloud Firestore
 * Projeto: nfes-dd7ab
 *
 * A configuração é carregada dinamicamente do backend via /api/firebase-config.
 * Não há credenciais hardcoded — se o backend não responder, o Firebase não inicializa.
 */

const firebaseConfig = {};

let firebaseApp = null;
let firestoreDb = null;
let firebaseAnalytics = null;
let isFirestoreAvailable = false;

// Promise que resolve quando o Firebase terminar de inicializar.
// auth.js aguarda esta promise antes de tentar o login, evitando
// a race condition entre carregamento assíncrono do Firebase e o login.
let _firebaseReadyResolve = null;
let _firebaseReadyReject = null;
const firebaseReadyPromise = new Promise((resolve, reject) => {
    _firebaseReadyResolve = resolve;
    _firebaseReadyReject = reject;
});

function initFirebase() {
    try {
        if (typeof firebase !== "undefined") {
            if (!firebase.apps.length) {
                firebaseApp = firebase.initializeApp(firebaseConfig);
            } else {
                firebaseApp = firebase.app();
            }

            firestoreDb = firebase.firestore();

            if (typeof firebase.analytics === "function") {
                try {
                    firebaseAnalytics = firebase.analytics();
                } catch (e) {
                    console.log("Firebase Analytics inicializado localmente.");
                }
            }

            isFirestoreAvailable = true;
            console.log("✓ Firebase & Cloud Firestore inicializados com sucesso!");
            updateFirestoreStatusUI(true);
            // Notifica todos que aguardam o Firebase
            if (_firebaseReadyResolve) _firebaseReadyResolve(true);
        } else {
            const msg = "SDK do Firebase não foi carregado via CDN.";
            console.warn(msg);
            isFirestoreAvailable = false;
            updateFirestoreStatusUI(false, msg);
            if (_firebaseReadyReject) _firebaseReadyReject(new Error(msg));
        }
    } catch (err) {
        console.error("Erro ao inicializar Firebase:", err);
        isFirestoreAvailable = false;
        updateFirestoreStatusUI(false, err.message);
        if (_firebaseReadyReject) _firebaseReadyReject(err);
    }
}

function updateFirestoreStatusUI(connected, errorMsg = "") {
    const badge = document.getElementById("badgeStatusFirestore");
    if (badge) {
        if (connected) {
            badge.textContent = "☁️ Firestore OK";
            badge.className = "badge-firestore badge-firestore-ok";
            badge.title = "Conectado ao Cloud Firestore";
            badge.style.display = "inline-flex";
        } else {
            badge.textContent = "☁️ Firestore Offline";
            badge.className = "badge-firestore badge-firestore-off";
            badge.title = errorMsg || "Cloud Firestore Offline";
            badge.style.display = "inline-flex";
        }
    }
    // Atualiza o indicador na tela de login (se disponível)
    if (typeof updateLoginFirestoreStatus === "function") {
        updateLoginFirestoreStatus(connected, errorMsg);
    }
}

/**
 * Salva ou atualiza um documento NF-e no Cloud Firestore
 */
async function saveDocToFirestore(doc) {
    if (!isFirestoreAvailable || !firestoreDb) return false;
    const chave = (doc.chave || "").replace(/\D/g, "");
    if (!chave || chave.length !== 44) return false;

    const dataEmi = doc.data_emissao || (doc.identificacao && doc.identificacao.data_emissao) || "";
    const competencia = dataEmi.length >= 7 ? dataEmi.substring(0, 7) : "";
    const empresaCnpj = doc.empresa_cnpj || doc.destinatario_cnpj || (doc.destinatario && doc.destinatario.cnpj) || "";
    const cleanEmpresa = empresaCnpj.replace(/\D/g, "");

    try {
        const payload = {
            chave: chave,
            empresa_cnpj: cleanEmpresa,
            competencia: competencia, // Ex: "2026-01", "2026-08" para arquivamento mês a mês
            numero: doc.numero || "",
            serie: doc.serie || "",
            modelo: doc.modelo || "55",
            emitente_cnpj: doc.emitente_cnpj || (doc.emitente && doc.emitente.cnpj) || "",
            emitente_nome: doc.emitente_nome || (doc.emitente && doc.emitente.nome) || "",
            destinatario_cnpj: doc.destinatario_cnpj || (doc.destinatario && (doc.destinatario.cnpj || doc.destinatario.cpf)) || "",
            destinatario_nome: doc.destinatario_nome || (doc.destinatario && doc.destinatario.nome) || "",
            data_emissao: dataEmi,
            data_autorizacao: doc.data_autorizacao || "",
            valor_total: parseFloat(doc.valor_total || (doc.totais && doc.totais.v_nf) || 0.0),
            valor_icms: parseFloat(doc.valor_icms || (doc.totais && doc.totais.v_icms) || 0.0),
            valor_pis: parseFloat(doc.valor_pis || (doc.totais && doc.totais.v_pis) || 0.0),
            valor_cofins: parseFloat(doc.valor_cofins || (doc.totais && doc.totais.v_cofins) || 0.0),
            valor_ipi: parseFloat(doc.valor_ipi || (doc.totais && doc.totais.v_ipi) || 0.0),
            situacao: doc.situacao || "Autorizada",
            nsu: doc.nsu || "0",
            produtos: doc.produtos || [],
            updated_at: firebase.firestore.FieldValue.serverTimestamp(),
        };

        // Salva na coleção global nfe_docs
        await firestoreDb.collection("nfe_docs").doc(chave).set(payload, { merge: true });

        // Se tiver CNPJ da empresa, salva também na subcoleção estruturada da empresa
        if (cleanEmpresa) {
            await firestoreDb.collection("empresas").doc(cleanEmpresa).collection("nfe_docs").doc(chave).set(payload, { merge: true });
        }

        console.log(`✓ NF-e ${chave} sincronizada no Firestore (Empresa: ${cleanEmpresa} | Mês: ${competencia}).`);
        return true;
    } catch (err) {
        console.warn(`Aviso: sincronização Firestore para NF-e ${chave}:`, err.message);
        return false;
    }
}

/**
 * Salva um evento (Manifestação / Cancelamento) no Firestore
 */
async function saveEventToFirestore(event) {
    if (!isFirestoreAvailable || !firestoreDb) return false;
    const chave = (event.chave || "").replace(/\D/g, "");
    if (!chave) return false;

    try {
        const docRef = firestoreDb.collection("nfe_events").doc();
        await docRef.set({
            ...event,
            created_at: firebase.firestore.FieldValue.serverTimestamp(),
        });
        return true;
    } catch (err) {
        console.warn("Aviso ao salvar evento no Firestore:", err.message);
        return false;
    }
}

/**
 * Sincroniza todas as notas locais com o Firestore em lote ultrarrápido
 */
async function syncAllToFirestore() {
    const btn = document.getElementById("btn-sync-firestore-all");
    const originalText = btn ? btn.textContent : "☁️ Nuvem Firestore";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Sincronizando com Firestore..."; }

    try {
        // Tenta sincronização em lote de alta performance via backend
        const res = await fetch("/api/gestao/firestore/sync-all", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                toast.success(
                    `Sincronização 24h Cloud Firestore Concluída!\n\n` +
                    `• Notas sincronizadas na nuvem: ${data.synced} de ${data.total}\n` +
                    `• Projeto: ${data.project_id}\n` +
                    `• Status: Atualizado e disponível 24h.`,
                    8000
                );
                updateFirestoreStatusUI(true);
                return;
            }
        }
        throw new Error("Falha no endpoint de sincronização em lote.");
    } catch (err) {
        console.warn("[Firestore] Tentando sincronização direta pelo cliente...", err);
        if (!isFirestoreAvailable || !firestoreDb) {
            toast.error("Erro ao sincronizar com o Firestore: " + err.message);
            return;
        }

        try {
            const res = await apiGet("/api/gestao/documentos?page=1&limit=1000");
            const docs = (res && res.data && res.data.documentos) || [];
            let sucessos = 0;
            for (let i = 0; i < docs.length; i++) {
                if (btn) btn.textContent = `⏳ Enviando (${i + 1}/${docs.length})...`;
                const ok = await saveDocToFirestore(docs[i]);
                if (ok) sucessos++;
            }
            toast.success(`Sincronização concluída: ${sucessos} notas enviadas para a nuvem.`, 6000);
        } catch (clientErr) {
            toast.error("Erro na sincronização: " + clientErr.message);
        }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = originalText; }
    }
}

/**
 * Baixa todas as NF-es do Cloud Firestore para o banco local (SQLite).
 * Idempotente — pode rodar várias vezes sem duplicar (chave é PRIMARY KEY).
 */
async function pullFromFirestore() {
    const btn = document.getElementById("btn-firestore-pull");
    const originalText = btn ? btn.textContent : "⬇️ Baixar do Firestore";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Baixando do Firestore..."; }

    try {
        const res = await fetch("/api/gestao/firestore/pull-all", { method: "POST" });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
        }
        const data = await res.json();
        if (data.success) {
            const recarregar = await showConfirmModal({
                title: "Pull do Cloud Firestore Concluído",
                message:
                    `Total na nuvem: ${data.total_cloud}\n` +
                    `Importadas: ${data.imported}\n` +
                    `Falhas: ${data.failed}\n` +
                    `Ignoradas (chave inválida): ${data.skipped}\n\n` +
                    `Deseja recarregar a página agora para ver todas as NF-es?`,
                confirmText: "Sim, recarregar",
                cancelText: "Agora não",
                icon: "☁️",
            });
            if (recarregar) {
                window.location.reload();
            } else if (typeof carregarNfeSaidas === "function") {
                carregarNfeSaidas(1);
            }
            toast.success(
                `Pull concluído: ${data.imported} de ${data.total_cloud} NF-es importadas.`,
                5000
            );
        } else {
            throw new Error(data.error || data.detail || "Falha desconhecida");
        }
    } catch (err) {
        toast.error("Erro ao baixar do Firestore: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = originalText; }
    }
}

/**
 * Consolida todos os clientes (emitentes + destinatários) das NF-es
 * no Firestore (coleção 'clientes'). Idempotente.
 */
async function consolidarClientesFirestore() {
    const ok = await showConfirmModal({
        title: "Consolidar Clientes",
        message: "Consolidar todos os clientes (emitentes + destinatários) das NF-es no Firestore?\n\nIsso pode levar 1-2 minutos para ~1.700 clientes.",
        confirmText: "Consolidar",
        cancelText: "Cancelar",
        icon: "👥",
    });
    if (!ok) return;
    const btn = document.getElementById("btn-firestore-consolidar-clientes");
    const original = btn ? btn.textContent : "👥 Consolidar Clientes";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Consolidando clientes..."; }
    try {
        const res = await fetch("/api/gestao/firestore/consolidar-clientes", { method: "POST" });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
        }
        const data = await res.json();
        if (data.success) {
            toast.success(
                `Consolidação de clientes concluída!\n\n` +
                `• Únicos: ${data.total_unicos}\n` +
                `• Importados: ${data.imported}\n` +
                `• Falhas: ${data.failed}\n\n` +
                `Coleção 'clientes' do Firestore atualizada.`,
                6000
            );
        } else {
            throw new Error(data.error || data.detail || "Falha desconhecida");
        }
    } catch (err) {
        toast.error("Erro ao consolidar clientes: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = original; }
    }
}

/**
 * Consolida todos os produtos (das NF-es com XML) no Firestore
 * (coleção 'produtos'). Idempotente.
 */
async function consolidarProdutosFirestore() {
    const ok = await showConfirmModal({
        title: "Consolidar Produtos",
        message: "Consolidar todos os produtos (das NF-es com XML) no Firestore?\n\nApenas NF-es com XML/itens cadastrados (62 NF-es).",
        confirmText: "Consolidar",
        cancelText: "Cancelar",
        icon: "📦",
    });
    if (!ok) return;
    const btn = document.getElementById("btn-firestore-consolidar-produtos");
    const original = btn ? btn.textContent : "📦 Consolidar Produtos";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Consolidando produtos..."; }
    try {
        const res = await fetch("/api/gestao/firestore/consolidar-produtos", { method: "POST" });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
        }
        const data = await res.json();
        if (data.success) {
            toast.success(
                `Consolidação de produtos concluída!\n\n` +
                `• Únicos: ${data.total_unicos}\n` +
                `• Importados: ${data.imported}\n` +
                `• Falhas: ${data.failed}\n\n` +
                `Coleção 'produtos' do Firestore atualizada.`,
                6000
            );
        } else {
            throw new Error(data.error || data.detail || "Falha desconhecida");
        }
    } catch (err) {
        toast.error("Erro ao consolidar produtos: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = original; }
    }
}

/**
 * Copia a coleção 'clientes' do Firestore para a tabela cad_clientes do SQLite.
 * Necessário para que a aba "Cadastro de Clientes" do app mostre os dados.
 */
async function sincronizarClientesLocal() {
    const ok = await showConfirmModal({
        title: "Copiar Clientes do Firestore → Local",
        message: "Copiar todos os clientes do Firestore para o banco local?\n\nA aba 'Cadastro de Clientes' mostrará os dados após a cópia.",
        confirmText: "Copiar agora",
        cancelText: "Cancelar",
        icon: "📥",
    });
    if (!ok) return;
    const btn = document.getElementById("btn-firestore-sync-clientes-local");
    const original = btn ? btn.textContent : "📥 Copiar Clientes → Local";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Copiando clientes..."; }
    try {
        const res = await fetch("/api/gestao/firestore/sincronizar-clientes-local", { method: "POST" });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
        }
        const data = await res.json();
        if (data.success) {
            toast.success(
                `Clientes copiados para o banco local!\n\n` +
                `• Na nuvem: ${data.total_nuvem}\n` +
                `• Importados: ${data.imported}\n` +
                `• Falhas: ${data.failed}\n` +
                `• Ignorados (CNPJ inválido): ${data.skipped || 0}\n\n` +
                `A aba 'Cadastro de Clientes' agora mostrará os dados.`,
                6000
            );
            if (typeof carregarClientes === "function") {
                carregarClientes(1);
            }
        } else {
            throw new Error(data.error || data.detail || "Falha desconhecida");
        }
    } catch (err) {
        toast.error("Erro ao copiar clientes: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = original; }
    }
}

/**
 * Copia a coleção 'produtos' do Firestore para a tabela cad_produtos do SQLite.
 */
async function sincronizarProdutosLocal() {
    const ok = await showConfirmModal({
        title: "Copiar Produtos do Firestore → Local",
        message: "Copiar todos os produtos do Firestore para o banco local?\n\nA aba 'Catálogo de Produtos' mostrará os dados após a cópia.",
        confirmText: "Copiar agora",
        cancelText: "Cancelar",
        icon: "📥",
    });
    if (!ok) return;
    const btn = document.getElementById("btn-firestore-sync-produtos-local");
    const original = btn ? btn.textContent : "📥 Copiar Produtos → Local";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Copiando produtos..."; }
    try {
        const res = await fetch("/api/gestao/firestore/sincronizar-produtos-local", { method: "POST" });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
        }
        const data = await res.json();
        if (data.success) {
            toast.success(
                `Produtos copiados para o banco local!\n\n` +
                `• Na nuvem: ${data.total_nuvem}\n` +
                `• Importados: ${data.imported}\n` +
                `• Falhas: ${data.failed}\n` +
                `• Ignorados: ${data.skipped || 0}`,
                6000
            );
            if (typeof carregarProdutos === "function") {
                carregarProdutos(1);
            }
        } else {
            throw new Error(data.error || data.detail || "Falha desconhecida");
        }
    } catch (err) {
        toast.error("Erro ao copiar produtos: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = original; }
    }
}

// Inicializa de forma robusta independente do momento do carregamento do script
async function bootstrapFirebase() {
    try {
        const resp = await fetch("/api/firebase-config");
        if (resp.ok) {
            const cfg = await resp.json();
            if (cfg.apiKey) {
                Object.assign(firebaseConfig, cfg);
                initFirebase(); // resolve ou rejeita firebaseReadyPromise internamente
            } else {
                const msg = "Config do Firebase não disponível no backend. Sincronização com nuvem desativada.";
                console.warn(msg);
                updateFirestoreStatusUI(false, msg);
                if (_firebaseReadyReject) _firebaseReadyReject(new Error(msg));
            }
        } else {
            const msg = `Backend retornou status ${resp.status} ao carregar config do Firebase.`;
            console.warn(msg);
            updateFirestoreStatusUI(false, msg);
            if (_firebaseReadyReject) _firebaseReadyReject(new Error(msg));
        }
    } catch (e) {
        const msg = "Falha ao conectar ao backend para carregar config do Firebase. Sincronização com nuvem desativada.";
        console.warn(msg, e);
        updateFirestoreStatusUI(false, msg);
        if (_firebaseReadyReject) _firebaseReadyReject(new Error(msg));
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapFirebase);
} else {
    bootstrapFirebase();
}
