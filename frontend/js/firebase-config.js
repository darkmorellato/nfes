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
        } else {
            console.warn("SDK do Firebase não foi carregado via CDN.");
            updateFirestoreStatusUI(false, "SDK não carregado");
        }
    } catch (err) {
        console.error("Erro ao inicializar Firebase:", err);
        isFirestoreAvailable = false;
        updateFirestoreStatusUI(false, err.message);
    }
}

function updateFirestoreStatusUI(connected, errorMsg = "") {
    const badge = document.getElementById("badgeStatusFirestore");
    if (!badge) return;

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
 * Sincroniza todas as notas locais com o Firestore
 */
async function syncAllToFirestore() {
    if (!isFirestoreAvailable || !firestoreDb) {
        alert("Firestore não está conectado no momento. Verifique sua conexão de internet.");
        return;
    }

    const btn = document.getElementById("btn-sync-firestore-all");
    const originalText = btn ? btn.textContent : "☁️ Nuvem Firestore";
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Enviando para Firestore..."; }

    try {
        const res = await apiGet("/api/gestao/documentos?page=1&limit=1000");
        if (!res || !res.success || !res.data) {
            const detail = res && res.detail ? res.detail : "Erro ao carregar documentos locais.";
            throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }

        const docs = res.data.documentos || [];
        if (docs.length === 0) {
            alert("Nenhuma nota fiscal encontrada no banco local para enviar ao Firestore.");
            return;
        }

        let sucessos = 0;
        let erros = 0;

        for (let i = 0; i < docs.length; i++) {
            const d = docs[i];
            if (btn) btn.textContent = `⏳ Enviando (${i + 1}/${docs.length})...`;
            
            try {
                const detailRes = await apiGet(`/api/gestao/documento/${d.chave}`);
                const fullDoc = (detailRes.success && detailRes.data) ? detailRes.data : d;
                const ok = await saveDocToFirestore(fullDoc);
                if (ok) sucessos++;
                else erros++;
            } catch (docErr) {
                console.warn(`Erro ao sincronizar nota ${d.chave}:`, docErr);
                erros++;
            }
        }

        alert(`✓ Sincronização com Cloud Firestore concluída com sucesso!\n\n• Notas enviadas: ${sucessos} de ${docs.length}\n• Status: Atualizado no Firestore.`);
    } catch (err) {
        console.error("Erro na sincronização Firestore:", err);
        alert("Erro na sincronização com o Firestore: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = originalText; }
    }
}

// Inicializa quando o DOM estiver pronto
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const resp = await fetch("/api/firebase-config");
        if (resp.ok) {
            const cfg = await resp.json();
            if (cfg.apiKey) {
                Object.assign(firebaseConfig, cfg);
                initFirebase();
            } else {
                const msg = "Config do Firebase não disponível no backend. Sincronização com nuvem desativada.";
                console.warn(msg);
                updateFirestoreStatusUI(false, msg);
            }
        } else {
            const msg = `Backend retornou status ${resp.status} ao carregar config do Firebase.`;
            console.warn(msg);
            updateFirestoreStatusUI(false, msg);
        }
    } catch (e) {
        const msg = "Falha ao conectar ao backend para carregar config do Firebase. Sincronização com nuvem desativada.";
        console.warn(msg, e);
        updateFirestoreStatusUI(false, msg);
    }
});
