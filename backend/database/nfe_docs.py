import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from lxml import etree

from backend.database import get_db_connection, XML_STORAGE_DIR
from backend.database.certificates import get_certificate_record


# ====================================================================
# Mapeamento de situação fiscal a partir do retorno real da SEFAZ
# ====================================================================

CSTAT_AUTORIZADO = ("100", "150")
CSTAT_DENEGADO = ("110", "301", "302")

# Manifestação do destinatário (evento sobre a nota de terceiros).
# Fica em `nfe_docs.manifestacao`, separada da `situacao` fiscal.
_ROTULOS_MANIFESTACAO = {
    "210200": "Confirmada (210200)",
    "210210": "Ciência da Emissão (210210)",
    "210220": "Desconhecimento (210220)",
    "210240": "Operação não Realizada (210240)",
}


def _ler_retorno_do_xml(xml_raw: Optional[str]) -> Dict[str, str]:
    """
    Extrai o ``infProt`` (protocolo SEFAZ) de um ``<nfeProc>``.

    Usa XPath por ``local-name()``: o PyNFe serializa o retorno com prefixos
    gerados (``ns0:infProt``) e um parser por regex literal perderia o protocolo
    — a nota autorizada ficaria gravada como pendente.

    Retorna dicionário vazio quando não há protocolo: nesse caso a nota **não**
    foi autorizada e não pode ser tratada como tal.
    """
    if not xml_raw:
        return {}

    try:
        bruto = xml_raw if not isinstance(xml_raw, str) else xml_raw.encode("utf-8")
        raiz = etree.fromstring(bruto)
    except Exception:
        return {}

    nos = raiz.xpath("//*[local-name()='infProt']")
    if not nos:
        return {}
    bloco = nos[0]

    def _dentro(nome: str) -> str:
        achou = bloco.xpath(f".//*[local-name()='{nome}']")
        return (achou[0].text or "").strip() if achou else ""

    return {
        "c_stat": _dentro("cStat"),
        "x_motivo": _dentro("xMotivo"),
        "protocolo": _dentro("nProt"),
        "dh_recbto": _dentro("dhRecbto"),
        "tp_amb": _dentro("tpAmb"),
        "dig_val": _dentro("digVal"),
        "ver_aplic": _dentro("verAplic"),
    }


def _situacao_padrao(c_stat: str, protocolo: str = "") -> str:
    """Deriva a situação fiscal exclusivamente a partir do retorno da SEFAZ."""
    if c_stat in CSTAT_AUTORIZADO:
        return "Autorizada"
    if c_stat in CSTAT_DENEGADO:
        return "Denegada"
    if c_stat in ("103", "105"):
        return "Em Processamento"
    if c_stat:
        return f"Rejeitada ({c_stat})"
    return "Pendente"


def situacao_e_terminal(situacao_atual: Optional[str]) -> bool:
    """Cancelada e Denegada são estados finais — não podem ser rebaixados."""
    if not situacao_atual:
        return False
    return situacao_atual.startswith("Cancelada") or situacao_atual.startswith("Denegada")


def save_nfe_doc(doc: Dict[str, Any], xml_raw: Optional[str] = None,
                 empresa_cnpj: Optional[str] = None, sync_remote: bool = True) -> bool:
    """
    Salva ou atualiza um documento NF-e e seus produtos no banco de dados SQLite.

    ``sync_remote=False`` grava só localmente — usado pelo pull do Firestore,
    senão o sistema baixaria da nuvem e em seguida reenviaria tudo, queimando a
    cota de escrita do plano Spark (``HTTP 429``) e travando o login.
    """
    chave = "".join(c for c in str(doc.get("chave", "")) if c.isdigit())
    if len(chave) != 44:
        return False

    now = datetime.now().isoformat()
    emit = doc.get("emitente", {}) if isinstance(doc.get("emitente"), dict) else {}
    dest = doc.get("destinatario", {}) if isinstance(doc.get("destinatario"), dict) else {}
    totais = doc.get("totais", {}) if isinstance(doc.get("totais"), dict) else {}
    ident = doc.get("identificacao", {}) if isinstance(doc.get("identificacao"), dict) else {}

    emit_nome = emit.get("nome") or doc.get("nome_emitente") or doc.get("emitente_nome") or ""
    emit_cnpj = emit.get("cnpj") or doc.get("cnpj_emitente") or doc.get("emitente_cnpj") or ""
    emit_uf = emit.get("endereco", {}).get("uf") if isinstance(emit.get("endereco"), dict) else doc.get("emitente_uf", "")

    dest_nome = dest.get("nome") or doc.get("destinatario_nome") or ""
    dest_cnpj = dest.get("cnpj") or dest.get("cpf") or doc.get("destinatario_cnpj") or ""
    dest_uf = dest.get("endereco", {}).get("uf") if isinstance(dest.get("endereco"), dict) else doc.get("destinatario_uf", "")

    # Determina a empresa dona do documento
    dest_digits = "".join(c for c in str(dest_cnpj) if c.isdigit())
    emit_digits = "".join(c for c in str(emit_cnpj) if c.isdigit())
    empresa_digits = "".join(c for c in str(empresa_cnpj or doc.get("empresa_cnpj") or "") if c.isdigit())

    # Se não temos um CNPJ válido de empresa dona, tenta localizar pelos certificados (por CNPJ ou Razão Social)
    cert_record = get_certificate_record(empresa_digits) or get_certificate_record(dest_digits) or get_certificate_record(emit_digits)
    if not cert_record:
        from backend.database.certificates import list_certificates_db
        certs = list_certificates_db()
        emit_upper = (emit_nome or "").strip().upper()
        dest_upper = (dest_nome or "").strip().upper()
        for c in certs:
            c_razao = (c.get("razao_social") or "").strip().upper()
            c_fantasia = (c.get("nome_fantasia") or "").strip().upper()
            if c_razao and (c_razao in emit_upper or emit_upper in c_razao or (c_fantasia and c_fantasia in emit_upper)):
                cert_record = c
                if not emit_digits or emit_digits == "00000000000000":
                    emit_cnpj = c["cnpj"]
                    emit_digits = c["cnpj"]
                break
            if c_razao and (c_razao in dest_upper or dest_upper in c_razao or (c_fantasia and c_fantasia in dest_upper)):
                cert_record = c
                if not dest_digits or dest_digits == "00000000000000":
                    dest_cnpj = c["cnpj"]
                    dest_digits = c["cnpj"]
                break

    if cert_record:
        empresa_cnpj = cert_record["cnpj"]
        empresa_digits = cert_record["cnpj"]
    elif not empresa_cnpj:
        empresa_cnpj = dest_digits or emit_digits
        empresa_digits = "".join(c for c in str(empresa_cnpj) if c.isdigit())

    # Determina o tipo de documento (0 = Entrada / Fornecedor, 1 = Saída / Venda)
    # Critério oficial: tipo_doc é definido pelo PAPEL da empresa_cnpj (a empresa dona
    # do registro), não pelo emitente/destinatário do XML.
    tipo_doc = doc.get("tipo_doc")
    if tipo_doc is None:
        if empresa_digits and emit_digits == empresa_digits:
            # A empresa dona do registro é a EMITENTE → SAÍDA
            tipo_doc = 1
        elif empresa_digits and dest_digits == empresa_digits:
            # A empresa dona do registro é a DESTINATÁRIA → ENTRADA
            tipo_doc = 0
        else:
            # Fallback (empresa_cnpj ausente ou não bate com emit/dest):
            # usa o critério legado — emitente cadastrado e destinatário não → saída
            emit_is_empresa = bool(get_certificate_record(emit_digits))
            dest_is_empresa = bool(get_certificate_record(dest_digits))
            if emit_is_empresa and not dest_is_empresa:
                tipo_doc = 1
            elif dest_is_empresa and not emit_is_empresa:
                tipo_doc = 0
            else:
                # Conservador: padrão como entrada (não relacionado a mim)
                tipo_doc = 0
    else:
        tipo_doc = int(tipo_doc)

    numero = ident.get("numero") or doc.get("numero") or ""
    serie = ident.get("serie") or doc.get("serie") or ""
    modelo = ident.get("modelo") or doc.get("modelo") or ("65" if chave[20:22] == "65" else "55")
    dt_emi = ident.get("data_emissao") or doc.get("data_emissao") or doc.get("dhEmi") or ""
    dt_aut = doc.get("data_autorizacao") or ""
    nsu = str(doc.get("nsu") or "0")

    # --- Retorno real da SEFAZ (nunca fabricado localmente) ---
    # Campos informados explicitamente têm prioridade; caso contrário são
    # extraídos do próprio <nfeProc> (fluxo de download/sincronização).
    retorno_xml = _ler_retorno_do_xml(xml_raw)
    protocolo = str(doc.get("protocolo") or retorno_xml.get("protocolo") or "")
    c_stat = str(doc.get("c_stat") or retorno_xml.get("c_stat") or "")
    x_motivo = str(doc.get("x_motivo") or retorno_xml.get("x_motivo") or "")
    dh_recbto = str(doc.get("dh_recbto") or retorno_xml.get("dh_recbto") or "")
    tp_amb = doc.get("tp_amb", retorno_xml.get("tp_amb"))
    tp_amb = int(tp_amb) if tp_amb in (1, 2, "1", "2") else None
    tp_emis = doc.get("tp_emis")
    try:
        tp_emis = int(tp_emis) if tp_emis is not None else None
    except (TypeError, ValueError):
        tp_emis = None
    xml_assinado = doc.get("xml_assinado") or ""

    situacao = doc.get("situacao") or ""
    if not situacao:
        # Sem informação explícita: só autoriza se o XML carregar protocolo SEFAZ.
        situacao = _situacao_padrao(c_stat, protocolo)

    # Estados terminais: nunca são rebaixados por uma regravção posterior.
    SITUACOES_TERMINAIS = ("Cancelada", "Denegada")

    # Extração inteligente a partir da chave de 44 dígitos se faltarem dados (como em resNFe)
    if not numero and len(chave) == 44:
        try:
            numero = str(int(chave[25:34]))
        except Exception:
            pass
    if not serie and len(chave) == 44:
        try:
            serie = str(int(chave[22:25]))
        except Exception:
            pass
    if (not emit_cnpj or emit_cnpj == "00000000000000") and tipo_doc == 1 and empresa_cnpj:
        emit_cnpj = empresa_cnpj
    elif not emit_cnpj and len(chave) == 44:
        emit_cnpj = chave[6:20]

    # Em nota de Entrada (tipo_doc == 0), se destinatário estiver vazio,
    # o titular da nota é a própria empresa receptora (empresa_cnpj)
    if tipo_doc == 0 and not dest_cnpj and empresa_digits:
        dest_cnpj = empresa_digits
        dest_rec = get_certificate_record(empresa_digits)
        if dest_rec and not dest_nome:
            dest_nome = dest_rec.get("razao_social", "")

    def _to_float(v):
        if not v:
            return 0.0
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    v_total = _to_float(totais.get("v_nf") or totais.get("valor_total") or doc.get("valor_total"))
    v_icms = _to_float(totais.get("v_icms") or doc.get("valor_icms"))
    v_pis = _to_float(totais.get("v_pis") or doc.get("valor_pis"))
    v_cofins = _to_float(totais.get("v_cofins") or doc.get("valor_cofins"))
    v_ipi = _to_float(totais.get("v_ipi") or doc.get("valor_ipi"))

    has_xml = 1 if (xml_raw and len(xml_raw) > 50) else 0

    if has_xml:
        xml_file_path = os.path.join(XML_STORAGE_DIR, f"{chave}.xml")
        try:
            with open(xml_file_path, "w", encoding="utf-8") as f:
                f.write(xml_raw)
        except Exception:
            pass

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nfe_docs (
                chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emitente_cnpj, emitente_nome, emitente_uf,
                destinatario_cnpj, destinatario_nome, destinatario_uf, data_emissao, data_autorizacao,
                valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi, situacao, nsu,
                has_xml, xml_raw, created_at, updated_at,
                protocolo, c_stat, x_motivo, tp_amb, dh_recbto, xml_assinado, tp_emis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                empresa_cnpj = COALESCE(NULLIF(excluded.empresa_cnpj, ''), nfe_docs.empresa_cnpj),
                numero = COALESCE(NULLIF(excluded.numero, ''), nfe_docs.numero),
                serie = COALESCE(NULLIF(excluded.serie, ''), nfe_docs.serie),
                tipo_doc = CASE WHEN excluded.tipo_doc = 1 THEN 1 ELSE nfe_docs.tipo_doc END,
                emitente_cnpj = COALESCE(NULLIF(excluded.emitente_cnpj, ''), nfe_docs.emitente_cnpj),
                emitente_nome = COALESCE(NULLIF(excluded.emitente_nome, ''), nfe_docs.emitente_nome),
                destinatario_cnpj = COALESCE(NULLIF(excluded.destinatario_cnpj, ''), nfe_docs.destinatario_cnpj),
                destinatario_nome = COALESCE(NULLIF(excluded.destinatario_nome, ''), nfe_docs.destinatario_nome),
                data_emissao = COALESCE(NULLIF(excluded.data_emissao, ''), nfe_docs.data_emissao),
                data_autorizacao = COALESCE(NULLIF(excluded.data_autorizacao, ''), nfe_docs.data_autorizacao),
                valor_total = CASE WHEN excluded.valor_total > 0 THEN excluded.valor_total ELSE nfe_docs.valor_total END,
                situacao = CASE
                    WHEN nfe_docs.situacao IS NOT NULL
                         AND nfe_docs.situacao != ''
                         AND (nfe_docs.situacao LIKE 'Cancelada%' OR nfe_docs.situacao LIKE 'Denegada%')
                    THEN nfe_docs.situacao
                    ELSE COALESCE(NULLIF(excluded.situacao, ''), nfe_docs.situacao)
                END,
                nsu = CASE WHEN excluded.nsu != '0' THEN excluded.nsu ELSE nfe_docs.nsu END,
                has_xml = CASE WHEN excluded.has_xml = 1 THEN 1 ELSE nfe_docs.has_xml END,
                protocolo = COALESCE(NULLIF(excluded.protocolo, ''), nfe_docs.protocolo),
                c_stat = COALESCE(NULLIF(excluded.c_stat, ''), nfe_docs.c_stat),
                x_motivo = COALESCE(NULLIF(excluded.x_motivo, ''), nfe_docs.x_motivo),
                tp_amb = COALESCE(excluded.tp_amb, nfe_docs.tp_amb),
                tp_emis = COALESCE(excluded.tp_emis, nfe_docs.tp_emis),
                dh_recbto = COALESCE(NULLIF(excluded.dh_recbto, ''), nfe_docs.dh_recbto),
                xml_assinado = COALESCE(NULLIF(excluded.xml_assinado, ''), nfe_docs.xml_assinado),
                xml_raw = CASE
                    WHEN excluded.xml_raw LIKE '%<nfeProc%' OR excluded.xml_raw LIKE '%<NFe%' THEN excluded.xml_raw
                    WHEN nfe_docs.xml_raw LIKE '%<nfeProc%' OR nfe_docs.xml_raw LIKE '%<NFe%' THEN nfe_docs.xml_raw
                    ELSE COALESCE(NULLIF(excluded.xml_raw, ''), nfe_docs.xml_raw)
                END,
                updated_at = excluded.updated_at
        """, (
            chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emit_cnpj, emit_nome, emit_uf,
            dest_cnpj, dest_nome, dest_uf, dt_emi, dt_aut,
            v_total, v_icms, v_pis, v_cofins, v_ipi, situacao, nsu,
            has_xml, xml_raw or "", now, now,
            protocolo, c_stat, x_motivo, tp_amb, dh_recbto, xml_assinado,
            tp_emis,
        ))

        produtos = doc.get("produtos", [])
        if produtos:
            cursor.execute("DELETE FROM nfe_items WHERE chave = ?", (chave,))
            for p in produtos:
                cursor.execute("""
                    INSERT INTO nfe_items (
                        chave, n_item, codigo, ean, descricao, ncm, cfop, unidade,
                        quantidade, valor_unitario, valor_total, cst, v_icms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chave,
                    int(p.get("n_item") or 1),
                    p.get("codigo") or "",
                    p.get("ean") or "",
                    p.get("descricao") or "",
                    p.get("ncm") or "",
                    p.get("cfop") or "",
                    p.get("unidade") or "",
                    _to_float(p.get("quantidade")),
                    _to_float(p.get("valor_unitario")),
                    _to_float(p.get("valor_total")),
                    p.get("cst") or "",
                    _to_float(p.get("v_icms")),
                ))

        conn.commit()

    # Espelhamento automático em tempo real no Cloud Firestore (não-bloqueante).
    # Pulado quando a origem É o próprio Firestore: reenviar o que acabou de ser
    # baixado gera um loop de escritas que estoura a cota do plano Spark.
    if not sync_remote:
        return True

    try:
        from backend.services.firestore_service import sync_single_nfe_async, sync_nfe_items_to_firestore_async
        doc_payload = {
            "chave": chave,
            "empresa_cnpj": empresa_cnpj,
            "numero": numero,
            "serie": serie,
            "modelo": modelo,
            "tipo_doc": tipo_doc,
            "emitente_cnpj": emit_cnpj,
            "emitente_nome": emit_nome,
            "emitente_uf": emit_uf,
            "destinatario_cnpj": dest_cnpj,
            "destinatario_nome": dest_nome,
            "destinatario_uf": dest_uf,
            "data_emissao": dt_emi,
            "data_autorizacao": dt_aut,
            "valor_total": v_total,
            "valor_icms": v_icms,
            "valor_pis": v_pis,
            "valor_cofins": v_cofins,
            "valor_ipi": v_ipi,
            "situacao": situacao,
            "nsu": nsu,
            "has_xml": bool(has_xml),
            # O XML fiscal é o documento de valor jurídico: mandá-lo para a nuvem
            # garante que a perda da máquina local não perca o arquivo (e o pull
            # consegue restaurar data/xmls/ numa instalação nova).
            # Média de 8,4 KB → 1 GiB do plano Spark comporta ~124 mil XMLs.
            "xml_raw": xml_raw if has_xml else None,
        }
        sync_single_nfe_async(doc_payload)
        if produtos:
            sync_nfe_items_to_firestore_async(chave, produtos)
    except Exception:
        pass

    return True

def _garantir_documento_pai(cursor, chave: str) -> None:
    """
    Garante que a NF-e exista em ``nfe_docs`` antes de gravar um evento.

    Com ``foreign_keys=ON``, manifestar ou sincronizar uma nota que ainda não
    foi baixada localmente violaria a FK. A nota é registrada com o mínimo
    fiável: a chave (que carrega UF, CNPJ, modelo, série e número) e o papel
    derivado de quem é o emitente.
    """
    cursor.execute("SELECT 1 FROM nfe_docs WHERE chave = ?", (chave,))
    if cursor.fetchone():
        return

    emitente_cnpj = chave[6:20] if len(chave) == 44 else ""
    try:
        from backend.database.certificates import get_certificate_record
        emitente_e_minha = bool(get_certificate_record(emitente_cnpj))
    except Exception:
        emitente_e_minha = False

    tipo_doc = 1 if emitente_e_minha else 0
    now_iso = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT OR IGNORE INTO nfe_docs (
            chave, empresa_cnpj, numero, serie, modelo, tipo_doc,
            emitente_cnpj, situacao, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Recebida', ?, ?)
        """,
        (
            chave,
            emitente_cnpj if emitente_e_minha else "",
            chave[25:34] if len(chave) == 44 else "",
            str(int(chave[22:25])) if len(chave) == 44 else "0",
            chave[20:22] if len(chave) == 44 else "55",
            tipo_doc,
            emitente_cnpj,
            now_iso,
            now_iso,
        ),
    )


def save_nfe_event(event: Dict[str, Any]) -> bool:
    """Salva um evento fiscal (Manifestação, Cancelamento, CC-e) no banco."""
    chave = "".join(c for c in str(event.get("chave", "")) if c.isdigit())
    if len(chave) != 44:
        return False

    now = datetime.now().isoformat()
    tipo = str(event.get("tipo_evento") or "")
    desc = str(event.get("desc_evento") or event.get("xEvento") or "")
    n_seq = int(event.get("n_seq") or event.get("nSeqEvento") or 1)
    dh_ev = str(event.get("dh_evento") or event.get("dhRegEvento") or now)
    prot = str(event.get("protocolo") or event.get("nProt") or "")
    cstat = str(event.get("c_stat") or event.get("cStat") or "")
    motivo = str(event.get("x_motivo") or event.get("xMotivo") or "")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        _garantir_documento_pai(cursor, chave)
        cursor.execute("""
            INSERT INTO nfe_events (
                chave, tipo_evento, desc_evento, n_seq, dh_evento, protocolo, c_stat, x_motivo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (chave, tipo, desc, n_seq, dh_ev, prot, cstat, motivo, now))

        if tipo == "110111":
            # Cancelamento é estado final e a única manifestação que altera
            # a situação fiscal. As demais (210200/210210/210220/210240) são
            # registradas APENAS em nfe_events: sobrescrever `situacao` com elas
            # fazia uma nota autorizada sumir do filtro "Autorizadas"
            # (LIKE '%autorizad%') logo após a confirmação da operação.
            cursor.execute(
                "UPDATE nfe_docs SET situacao = 'Cancelada', updated_at = ? WHERE chave = ?",
                (now, chave),
            )
        elif tipo in _ROTULOS_MANIFESTACAO:
            cursor.execute(
                "UPDATE nfe_docs SET manifestacao = ?, updated_at = ? WHERE chave = ?",
                (_ROTULOS_MANIFESTACAO[tipo], now, chave),
            )

        conn.commit()

    try:
        from backend.services.firestore_service import sync_event_to_firestore_async
        sync_event_to_firestore_async(event)
    except Exception:
        pass

    return True

def list_nfe_docs(
    busca: Optional[str] = None,
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    situacao: Optional[str] = None,
    tipo_doc: Optional[Any] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Lista as NF-e armazenadas com filtros por empresa, tipo (Entrada/Saída), data, situação e busca por termo."""
    offset = max(0, (page - 1) * limit)
    conditions = []
    params: List[Any] = []

    if tipo_doc is not None and str(tipo_doc).strip() != "":
        conditions.append("nfe_docs.tipo_doc = ?")
        params.append(int(tipo_doc))

    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            conditions.append("(nfe_docs.empresa_cnpj = ? OR nfe_docs.destinatario_cnpj LIKE ? OR nfe_docs.emitente_cnpj LIKE ?)")
            params.extend([emp_digits, f"%{emp_digits}%", f"%{emp_digits}%"])

    if busca:
        busca_clean = busca.strip()
        digits = "".join(c for c in busca_clean if c.isdigit())
        p_like = f"%{busca_clean}%"

        sub_conds = [
            "nfe_docs.chave LIKE ?",
            "nfe_docs.numero LIKE ?",
            "nfe_docs.emitente_nome LIKE ?",
            "nfe_docs.emitente_cnpj LIKE ?",
            "nfe_docs.destinatario_nome LIKE ?",
            "nfe_docs.destinatario_cnpj LIKE ?",
            "EXISTS (SELECT 1 FROM nfe_items WHERE nfe_items.chave = nfe_docs.chave AND (nfe_items.descricao LIKE ? OR nfe_items.codigo LIKE ? OR nfe_items.ncm LIKE ? OR nfe_items.ean LIKE ?))",
        ]
        params.extend([p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like])

        if len(digits) >= 8:
            sub_conds.append("REPLACE(REPLACE(REPLACE(REPLACE(nfe_docs.emitente_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
            sub_conds.append("REPLACE(REPLACE(REPLACE(REPLACE(nfe_docs.destinatario_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
            p_digits = f"%{digits}%"
            params.extend([p_digits, p_digits])

        conditions.append("(" + " OR ".join(sub_conds) + ")")

    if data_inicio:
        conditions.append("nfe_docs.data_emissao >= ?")
        params.append(data_inicio)

    if data_fim:
        conditions.append("nfe_docs.data_emissao <= ?")
        params.append(data_fim + "T23:59:59")

    if situacao:
        conditions.append("nfe_docs.situacao LIKE ?")
        params.append(f"%{situacao}%")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) as total, SUM(valor_total) as total_valor FROM nfe_docs {where_clause}", params)
        row_count = cursor.fetchone()
        total = row_count["total"] if row_count else 0
        total_valor = row_count["total_valor"] if (row_count and row_count["total_valor"]) else 0.0

        query = f"""
            SELECT chave, empresa_cnpj, tipo_doc, numero, serie, modelo, emitente_cnpj, emitente_nome, emitente_uf,
                   destinatario_cnpj, destinatario_nome, data_emissao, data_autorizacao,
                   valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi,
                   situacao, nsu, has_xml, created_at
            FROM nfe_docs
            {where_clause}
            ORDER BY data_emissao DESC, created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        rows = [dict(r) for r in cursor.fetchall()]

    return {
        "documentos": rows,
        "total": total,
        "total_valor": total_valor,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }

def get_nfe_detail(chave: str) -> Optional[Dict[str, Any]]:
    """Retorna detalhes completos de uma NF-e incluindo produtos e eventos."""
    chave = "".join(c for c in chave if c.isdigit())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfe_docs WHERE chave = ?", (chave,))
        doc_row = cursor.fetchone()
        if not doc_row:
            return None

        doc = dict(doc_row)
        cursor.execute("SELECT * FROM nfe_items WHERE chave = ? ORDER BY n_item ASC", (chave,))
        doc["produtos"] = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM nfe_events WHERE chave = ? ORDER BY dh_evento DESC", (chave,))
        doc["eventos"] = [dict(r) for r in cursor.fetchall()]

        return doc

def list_nfe_saidas(
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    busca: Optional[str] = None,
    situacao: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Lista todas as notas fiscais emitidas (Saídas para Clientes / Devoluções / Transferências)."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    # Identifica todas as nossas empresas cadastradas
    nossos_cnpjs = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cnpj FROM certificates WHERE is_active = 1")
        nossos_cnpjs = [r["cnpj"] for r in cursor.fetchall()]

    where_conditions = ["(d.tipo_doc = 1 OR d.emitente_cnpj IN ({cnpjs}))".format(
        cnpjs=",".join(f"'{c}'" for c in nossos_cnpjs) if nossos_cnpjs else "'00000000000000'"
    )]
    params: List[Any] = []

    if clean_cnpj:
        where_conditions.append("(d.empresa_cnpj = ? OR d.emitente_cnpj = ?)")
        params.extend([clean_cnpj, clean_cnpj])

    if data_inicio:
        where_conditions.append("substr(d.data_emissao, 1, 10) >= ?")
        params.append(data_inicio)

    if data_fim:
        where_conditions.append("substr(d.data_emissao, 1, 10) <= ?")
        params.append(data_fim)

    if situacao and situacao.strip():
        sit_norm = situacao.strip().lower()
        if sit_norm == "autorizada" or sit_norm == "autorizadas":
            where_conditions.append("(d.situacao LIKE '%autorizad%' OR d.situacao IS NULL OR d.situacao = '' OR d.situacao = '100')")
        elif sit_norm == "pendente" or sit_norm == "pendentes":
            where_conditions.append("(d.situacao LIKE '%pendent%' OR d.situacao LIKE '%processamento%' OR d.situacao LIKE '%contingencia%')")
        elif sit_norm == "cancelada" or sit_norm == "canceladas":
            where_conditions.append("(d.situacao LIKE '%cancelad%' OR d.situacao = '101')")
        elif sit_norm == "rejeitada" or sit_norm == "rejeitadas":
            where_conditions.append("(d.situacao LIKE '%rejeit%' OR d.situacao LIKE '%erro%' OR d.situacao LIKE '%denegad%')")
        else:
            where_conditions.append("d.situacao LIKE ?")
            params.append(f"%{situacao.strip()}%")

    if busca and busca.strip():
        b = f"%{busca.strip()}%"
        where_conditions.append("(d.chave LIKE ? OR d.numero LIKE ? OR d.destinatario_nome LIKE ? OR d.destinatario_cnpj LIKE ?)")
        params.extend([b, b, b, b])

    where_str = "WHERE " + " AND ".join(where_conditions)

    count_query = f"SELECT COUNT(*) FROM nfe_docs d {where_str}"
    data_query = f"""
        SELECT d.chave, d.empresa_cnpj, d.numero, d.serie, d.modelo,
               d.emitente_cnpj, d.emitente_nome, d.emitente_uf,
               d.destinatario_cnpj, d.destinatario_nome, d.destinatario_uf,
               d.data_emissao, d.data_autorizacao, d.valor_total,
               d.valor_icms, d.valor_pis, d.valor_cofins, d.valor_ipi,
               d.situacao, d.manifestacao, d.tipo_doc, d.has_xml, d.created_at,
               (SELECT COUNT(*) FROM nfe_items WHERE chave = d.chave) as qtd_itens
        FROM nfe_docs d
        {where_str}
        ORDER BY d.data_emissao DESC, d.numero DESC
        LIMIT ? OFFSET ?
    """

    offset = max(0, (page - 1) * limit)
    paged_params = list(params) + [limit, offset]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        cursor.execute(data_query, paged_params)
        docs = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "page": page,
        "limit": limit,
        "documentos": docs,
    }


def cancelar_nfe_doc(chave: str, protocolo: str, justificativa: str) -> bool:
    """Registra o cancelamento de uma NF-e no banco e cria o evento fiscal 110111."""
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE nfe_docs
            SET situacao = 'Cancelada', updated_at = ?
            WHERE chave = ?
        """, (now_iso, chave_clean))

        cursor.execute("""
            INSERT INTO nfe_events (
                chave, tipo_evento, desc_evento, n_seq, protocolo, c_stat, x_motivo, dh_evento, created_at
            ) VALUES (?, '110111', 'Cancelamento de NF-e homologado', 1, ?, '135', ?, ?, ?)
        """, (chave_clean, protocolo, justificativa, now_iso, now_iso))
        conn.commit()

    try:
        from backend.services.firestore_service import sync_event_to_firestore_async, sync_single_nfe_async
        sync_event_to_firestore_async({
            "chave": chave_clean,
            "tipo_evento": "110111",
            "desc_evento": "Cancelamento de NF-e homologado",
            "n_seq": 1,
            "protocolo": protocolo,
            "x_motivo": justificativa,
        })
        sync_single_nfe_async({"chave": chave_clean, "situacao": "Cancelada"})
    except Exception:
        pass

    return True


# ====================================================================
# INUTILIZAÇÃO DE NUMERAÇÃO DE NF-e / NFC-e
# ====================================================================

def save_inutilizacao(data: Dict[str, Any]) -> Dict[str, Any]:
    """Registra a inutilização de numeração homologada na SEFAZ."""
    empresa_cnpj = "".join(c for c in str(data.get("empresa_cnpj", "")) if c.isdigit())
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nfe_inutilizacoes (
                empresa_cnpj, ano, modelo, serie, numero_inicial, numero_final,
                protocolo, justificativa, data_homologacao, c_stat, x_motivo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            empresa_cnpj,
            int(data.get("ano", datetime.now().year)),
            str(data.get("modelo", "55")),
            int(data.get("serie", 1)),
            int(data.get("numero_inicial", 1)),
            int(data.get("numero_final", 1)),
            str(data.get("protocolo", "")),
            str(data.get("justificativa", "")),
            str(data.get("data_homologacao", now_iso)),
            str(data.get("c_stat", "102")),
            str(data.get("x_motivo", "Inutilização de número homologada")),
            now_iso
        ))
        conn.commit()
        return {"id": cursor.lastrowid, **data}

def list_inutilizacoes(empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista as faixas de numeração inutilizadas na SEFAZ."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if empresa_cnpj:
            clean_cnpj = "".join(c for c in empresa_cnpj if c.isdigit())
            cursor.execute("SELECT * FROM nfe_inutilizacoes WHERE empresa_cnpj = ? ORDER BY id DESC", (clean_cnpj,))
        else:
            cursor.execute("SELECT * FROM nfe_inutilizacoes ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]


# ====================================================================
# CHECK-IN AUTOMÁTICO DE ESTOQUE (A PARTIR DE NF-e DE COMPRA/ENTRADA)
# ====================================================================
