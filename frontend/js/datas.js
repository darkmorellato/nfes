// =====================================================================
// Helpers de data — formato brasileiro (dd/mm/aaaa)
//
// Backend armazena datas em ISO 8601 ("2026-08-25T12:13:54-03:00").
// Este módulo converte para o formato brasileiro em qualquer ponto
// da UI, sem precisar criar wrappers a cada chamada.
//
// Vantagem de NÃO usar `new Date(iso).toLocaleDateString("pt-BR")`:
//   Datas com fuso-horário podem virar o dia anterior em fusos
//   negativos. Aqui pegamos a parte textual da data (substring)
//   que é determinística.
//
// Uso:
//   fmtDataBR("2026-08-25T12:13:54-03:00")    → "25/08/2026"
//   fmtDataHoraBR("2026-08-25T12:13:54-03:00")→ "25/08/2026 12:13"
//   fmtMesBR("2026-08")                       → "ago/2026"
//   diaSemanaBR("2026-08-29")                 → "29/08/2026 (sábado)"
// =====================================================================

/**
 * Converte uma string ISO ou "YYYY-MM-DD" para o formato brasileiro "dd/mm/aaaa".
 * @param {string|null|undefined} iso Data em ISO 8601 (ou só a parte da data).
 * @return {string} "dd/mm/aaaa" ou "—" se vazio.
 */
function fmtDataBR(iso) {
    if (!iso) return "—";
    // Pega só a parte da data (antes do 'T')
    const data = String(iso).substring(0, 10);
    if (data.length !== 10 || data[4] !== "-" || data[7] !== "-") return data || "—";
    return `${data.substring(8, 10)}/${data.substring(5, 7)}/${data.substring(0, 4)}`;
}

/**
 * Converte uma string ISO para "dd/mm/aaaa HH:MM" (sem segundos).
 * @param {string|null|undefined} iso Data em ISO 8601.
 * @return {string} "dd/mm/aaaa HH:MM" ou "—" se vazio.
 */
function fmtDataHoraBR(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return String(iso);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Converte uma string ISO para "dd/mm/aaaa HH:MM:SS" (com segundos).
 * @param {string|null|undefined} iso Data em ISO 8601.
 * @return {string} "dd/mm/aaaa HH:MM:SS" ou "—" se vazio.
 */
function fmtDataHoraSegBR(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return String(iso);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR");
}

/**
 * Converte uma string ISO, "YYYY-MM" ou "YYYY-MM-DD" para "mmm/aaaa".
 * Usado em gráficos (eixo X) para exibir "ago/2026" em vez de "08/2026".
 * @param {string|null|undefined} isoOuYYYYMM
 * @return {string} "mmm/aaaa" ou "—" se vazio.
 */
function fmtMesBR(isoOuYYYYMM) {
    if (!isoOuYYYYMM) return "—";
    const s = String(isoOuYYYYMM);
    let y, m;
    if (s.length >= 7 && s[4] === "-") {
        y = s.substring(0, 4);
        m = s.substring(5, 7);
    } else {
        return s;
    }
    const meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
    return `${meses[parseInt(m, 10) - 1]}/${y}`;
}

/**
 * Extrai a chave de agrupamento "YYYY-MM-DD" de uma data ISO.
 * Usada para agrupar linhas de tabela por dia.
 * @param {string|null|undefined} iso
 * @return {string} "YYYY-MM-DD" ou "" se vazio.
 */
function chaveDiaBR(iso) {
    if (!iso) return "";
    return String(iso).substring(0, 10);
}

/**
 * Converte "YYYY-MM-DD" para "dd/mm/aaaa (dia-da-semana)".
 * Exemplo: diaSemanaBR("2026-08-29") → "29/08/2026 (sábado)".
 * @param {string} isoYYYYMMDD
 * @return {string} Texto formatado ou "" se vazio.
 */
function diaSemanaBR(isoYYYYMMDD) {
    if (!isoYYYYMMDD) return "";
    const partes = String(isoYYYYMMDD).split("-");
    if (partes.length !== 3) return "";
    const y = parseInt(partes[0], 10);
    const m = parseInt(partes[1], 10);
    const d = parseInt(partes[2], 10);
    if (isNaN(y) || isNaN(m) || isNaN(d)) return "";
    const dt = new Date(y, m - 1, d);
    const dias = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
    return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${y} (${dias[dt.getDay()]})`;
}
