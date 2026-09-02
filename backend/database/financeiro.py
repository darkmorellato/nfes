import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection, XML_STORAGE_DIR

EVENTOS_REJEICAO = ("210220", "210240")

def sync_duplicatas_from_xmls():
    """Varre todos os XMLs e notas fiscais para garantir que as duplicatas estejam cadastradas.

    Apenas documentos de ENTRADA (tipo_doc=0 / Compra/Fornecedor) geram contas a pagar.
    """
    import glob
    from lxml import etree
    from datetime import timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Migração de segurança: remove contas a pagar órfãs geradas por saídas (bug antigo)
        cursor.execute(
            "DELETE FROM nfe_duplicatas WHERE chave IN (SELECT chave FROM nfe_docs WHERE tipo_doc = 1)"
        )

        # Remove contas a pagar de NF-e com manifestação de rejeição/desconhecimento
        rej_params = list(EVENTOS_REJEICAO)
        rej_placeholders = ",".join("?" for _ in rej_params)
        cursor.execute(
            f"DELETE FROM nfe_duplicatas WHERE chave IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))",
            rej_params,
        )

        # Conjunto de chaves rejeitadas para não recriar as duplicatas
        cursor.execute(f"SELECT DISTINCT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders})", rej_params)
        chaves_rejeitadas = {r["chave"] for r in cursor.fetchall()}

        cursor.execute(
            "SELECT chave, empresa_cnpj, emitente_nome, data_emissao, valor_total FROM nfe_docs WHERE tipo_doc = 0"
        )
        all_docs = [dict(r) for r in cursor.fetchall()]

        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        for doc in all_docs:
            ch = doc["chave"]
            if ch in chaves_rejeitadas:
                continue
            cursor.execute("SELECT COUNT(*) as count FROM nfe_duplicatas WHERE chave = ?", (ch,))
            if cursor.fetchone()["count"] > 0:
                continue

            xml_path = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
            inserted = False
            if os.path.exists(xml_path):
                try:
                    with open(xml_path, "rb") as f:
                        root = etree.fromstring(f.read())
                    dups = root.findall(".//nfe:dup", ns)
                    for idx, d in enumerate(dups, start=1):
                        n_dup = d.findtext("nfe:nDup", default=str(idx), namespaces=ns)
                        d_venc = d.findtext("nfe:dVenc", default="", namespaces=ns)
                        v_dup = float(d.findtext("nfe:vDup", default="0.0", namespaces=ns) or 0.0)
                        if not d_venc and doc.get("data_emissao"):
                            try:
                                d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                            except Exception:
                                d_venc = doc["data_emissao"][:10]

                        cursor.execute("""
                            INSERT INTO nfe_duplicatas (chave, n_dup, d_venc, v_dup, forma_pagamento, status, pago, empresa_cnpj, emitente_nome, created_at)
                            VALUES (?, ?, ?, ?, 'Boleto/Duplicata', 'A_VENCER', 0, ?, ?, ?)
                        """, (ch, n_dup, d_venc, v_dup, doc["empresa_cnpj"], doc["emitente_nome"], datetime.now().isoformat()))
                        inserted = True
                except Exception:
                    pass

            if not inserted and float(doc.get("valor_total") or 0.0) > 0:
                d_venc = ""
                if doc.get("data_emissao"):
                    try:
                        d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                    except Exception:
                        d_venc = doc["data_emissao"][:10]
                cursor.execute("""
                    INSERT INTO nfe_duplicatas (chave, n_dup, d_venc, v_dup, forma_pagamento, status, pago, empresa_cnpj, emitente_nome, created_at)
                    VALUES (?, '001', ?, ?, 'Fatura / Boleto', 'A_VENCER', 0, ?, ?, ?)
                """, (ch, d_venc, float(doc["valor_total"]), doc["empresa_cnpj"], doc["emitente_nome"], datetime.now().isoformat()))

        conn.commit()

def list_contas_a_pagar(empresa_cnpj: Optional[str] = None, filtro_status: Optional[str] = None, mes: Optional[str] = None) -> Dict[str, Any]:
    """Retorna contas a pagar e vencimentos extraídos das NF-e das empresas."""
    sync_duplicatas_from_xmls()
    now_str = datetime.now().strftime("%Y-%m-%d")

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    rej_params = list(EVENTOS_REJEICAO)
    rej_placeholders = ",".join("?" for _ in rej_params)

    mes_cond = ""
    mes_params = []
    if mes:
        mes_cond = " AND substr(doc.data_emissao, 1, 7) = ?"
        mes_params.append(mes)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT dup.id, dup.chave, dup.n_dup, dup.d_venc, dup.v_dup, dup.forma_pagamento,
                   dup.pago, dup.data_pagamento, dup.empresa_cnpj, dup.emitente_nome,
                    doc.numero as nfe_numero, doc.destinatario_nome
            FROM nfe_duplicatas dup
            JOIN nfe_docs doc ON dup.chave = doc.chave
            WHERE doc.tipo_doc = 0
              AND doc.chave NOT IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))
              {emp_cond}{mes_cond}
            ORDER BY dup.d_venc ASC
        """, rej_params + emp_params + mes_params)
        all_dups = [dict(r) for r in cursor.fetchall()]

    total_aberto = 0.0
    total_vencido = 0.0
    total_pago = 0.0
    vencendo_hoje = 0.0

    for d in all_dups:
        venc = d.get("d_venc", "")
        val = float(d.get("v_dup") or 0.0)
        pago = bool(d.get("pago"))

        if pago:
            d["status_calc"] = "PAGO"
            total_pago += val
        elif venc and venc < now_str:
            d["status_calc"] = "VENCIDO"
            total_vencido += val
            total_aberto += val
        elif venc == now_str:
            d["status_calc"] = "VENCE_HOJE"
            vencendo_hoje += val
            total_aberto += val
        else:
            d["status_calc"] = "A_VENCER"
            total_aberto += val

    if filtro_status == "aberto":
        filtered = [d for d in all_dups if d["status_calc"] != "PAGO"]
    elif filtro_status == "vencido":
        filtered = [d for d in all_dups if d["status_calc"] == "VENCIDO"]
    elif filtro_status == "pago":
        filtered = [d for d in all_dups if d["status_calc"] == "PAGO"]
    else:
        filtered = all_dups

    return {
        "duplicatas": filtered,
        "total_contas": len(filtered),
        "total_aberto": total_aberto,
        "total_vencido": total_vencido,
        "total_pago": total_pago,
        "vencendo_hoje": vencendo_hoje,
    }

def pagar_duplicata(dup_id: int) -> bool:
    """Marca uma duplicata como paga ou desmarca."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pago FROM nfe_duplicatas WHERE id = ?", (dup_id,))
        row = cursor.fetchone()
        if not row:
            return False
        novo_pago = 0 if row["pago"] == 1 else 1
        dt_pag = now if novo_pago == 1 else None
        cursor.execute("UPDATE nfe_duplicatas SET pago = ?, data_pagamento = ? WHERE id = ?", (novo_pago, dt_pag, dup_id))
        conn.commit()
        return True


# ====================================================================
# CONTAS A RECEBER (SAÍDAS / VENDAS / CLIENTES)
# ====================================================================

def sync_contas_receber_from_xmls():
    """Varre todos os XMLs e notas fiscais de SAÍDA (tipo_doc=1) para garantir
    que as parcelas a receber (contas a receber) estejam cadastradas."""
    import glob
    from lxml import etree
    from datetime import timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Migração de segurança: remove contas a receber órfãs geradas por entradas (bug antigo)
        cursor.execute(
            "DELETE FROM nfe_contas_receber WHERE chave IN (SELECT chave FROM nfe_docs WHERE tipo_doc = 0)"
        )

        # As notas de saída são emitidas à vista (já recebemos), então o padrão é RECEBIDO.
        # Migração única: marca como recebidas as parcelas criadas antes deste comportamento.
        flag_row = cursor.execute(
            "SELECT value FROM sync_state WHERE key = 'contas_receber_recebido_default'"
        ).fetchone()
        if not (flag_row and flag_row["value"] == "1"):
            cursor.execute(
                "UPDATE nfe_contas_receber SET recebido = 1, status = 'RECEBIDO', "
                "data_recebimento = created_at WHERE recebido = 0"
            )
            _now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO sync_state (key, value, updated_at) VALUES ('contas_receber_recebido_default', '1', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = '1', updated_at = ?",
                (_now, _now),
            )

        cursor.execute(
            "SELECT chave, empresa_cnpj, destinatario_nome, destinatario_cnpj, data_emissao, valor_total "
            "FROM nfe_docs WHERE tipo_doc = 1"
        )
        all_docs = [dict(r) for r in cursor.fetchall()]

        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        for doc in all_docs:
            ch = doc["chave"]
            cursor.execute("SELECT COUNT(*) as count FROM nfe_contas_receber WHERE chave = ?", (ch,))
            if cursor.fetchone()["count"] > 0:
                continue

            xml_path = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
            inserted = False
            if os.path.exists(xml_path):
                try:
                    with open(xml_path, "rb") as f:
                        root = etree.fromstring(f.read())
                    dups = root.findall(".//nfe:dup", ns)
                    for idx, d in enumerate(dups, start=1):
                        n_dup = d.findtext("nfe:nDup", default=str(idx), namespaces=ns)
                        d_venc = d.findtext("nfe:dVenc", default="", namespaces=ns)
                        v_dup = float(d.findtext("nfe:vDup", default="0.0", namespaces=ns) or 0.0)
                        if not d_venc and doc.get("data_emissao"):
                            try:
                                d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                            except Exception:
                                d_venc = doc["data_emissao"][:10]

                        now_iso = datetime.now().isoformat()
                        cursor.execute("""
                            INSERT INTO nfe_contas_receber (chave, n_dup, d_venc, v_dup, forma_pagamento, status, recebido, data_recebimento, empresa_cnpj, cliente_nome, cliente_cnpj, created_at)
                            VALUES (?, ?, ?, ?, 'Boleto/Duplicata', 'RECEBIDO', 1, ?, ?, ?, ?, ?)
                        """, (ch, n_dup, d_venc, v_dup, now_iso, doc["empresa_cnpj"], doc["destinatario_nome"], doc["destinatario_cnpj"], now_iso))
                        inserted = True
                except Exception:
                    pass

            if not inserted and float(doc.get("valor_total") or 0.0) > 0:
                d_venc = ""
                if doc.get("data_emissao"):
                    try:
                        d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                    except Exception:
                        d_venc = doc["data_emissao"][:10]
                now_iso = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO nfe_contas_receber (chave, n_dup, d_venc, v_dup, forma_pagamento, status, recebido, data_recebimento, empresa_cnpj, cliente_nome, cliente_cnpj, created_at)
                    VALUES (?, '001', ?, ?, 'Fatura / Boleto', 'RECEBIDO', 1, ?, ?, ?, ?, ?)
                """, (ch, d_venc, float(doc["valor_total"]), now_iso, doc["empresa_cnpj"], doc["destinatario_nome"], doc["destinatario_cnpj"], now_iso))

        conn.commit()

def list_contas_a_receber(empresa_cnpj: Optional[str] = None, filtro_status: Optional[str] = None, mes: Optional[str] = None) -> Dict[str, Any]:
    """Retorna contas a receber (saídas/vendas) e vencimentos extraídos das NF-e das empresas."""
    sync_contas_receber_from_xmls()
    now_str = datetime.now().strftime("%Y-%m-%d")

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (r.empresa_cnpj = ? OR r.cliente_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    mes_cond = ""
    mes_params = []
    if mes:
        mes_cond = " AND substr(doc.data_emissao, 1, 7) = ?"
        mes_params.append(mes)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT r.id, r.chave, r.n_dup, r.d_venc, r.v_dup, r.forma_pagamento,
                   r.recebido, r.data_recebimento, r.empresa_cnpj, r.cliente_nome,
                    doc.numero as nfe_numero, doc.emitente_nome
            FROM nfe_contas_receber r
            JOIN nfe_docs doc ON r.chave = doc.chave
            WHERE doc.tipo_doc = 1 {emp_cond}{mes_cond}
            ORDER BY r.d_venc ASC
        """, emp_params + mes_params)
        all_rec = [dict(r) for r in cursor.fetchall()]

    total_aberto = 0.0
    total_vencido = 0.0
    total_recebido = 0.0
    vencendo_hoje = 0.0

    for d in all_rec:
        venc = d.get("d_venc", "")
        val = float(d.get("v_dup") or 0.0)
        rec = bool(d.get("recebido"))

        if rec:
            d["status_calc"] = "RECEBIDO"
            total_recebido += val
        elif venc and venc < now_str:
            d["status_calc"] = "VENCIDO"
            total_vencido += val
            total_aberto += val
        elif venc == now_str:
            d["status_calc"] = "VENCE_HOJE"
            vencendo_hoje += val
            total_aberto += val
        else:
            d["status_calc"] = "A_RECEBER"
            total_aberto += val

    if filtro_status == "aberto":
        filtered = [d for d in all_rec if d["status_calc"] != "RECEBIDO"]
    elif filtro_status == "vencido":
        filtered = [d for d in all_rec if d["status_calc"] == "VENCIDO"]
    elif filtro_status == "recebido":
        filtered = [d for d in all_rec if d["status_calc"] == "RECEBIDO"]
    else:
        filtered = all_rec

    return {
        "contas": filtered,
        "total_contas": len(filtered),
        "total_aberto": total_aberto,
        "total_vencido": total_vencido,
        "total_recebido": total_recebido,
        "vencendo_hoje": vencendo_hoje,
    }

def receber_duplicata(dup_id: int) -> bool:
    """Marca uma conta a receber como recebida ou desmarca."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT recebido FROM nfe_contas_receber WHERE id = ?", (dup_id,))
        row = cursor.fetchone()
        if not row:
            return False
        novo_recebido = 0 if row["recebido"] == 1 else 1
        dt_rec = now if novo_recebido == 1 else None
        cursor.execute("UPDATE nfe_contas_receber SET recebido = ?, data_recebimento = ? WHERE id = ?", (novo_recebido, dt_rec, dup_id))
        conn.commit()
        return True


# ====================================================================
# DRE CONSOLIDADO (RESULTADO DO EXERCÍCIO)
# ====================================================================

def get_dre_consolidado(ano: Optional[int] = None, mes: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Calcula o DRE consolidado do período: Receita Bruta - Impostos - CPV = Lucro Bruto - DAS = Lucro Líquido."""
    now = datetime.now()
    cur_ano = ano or now.year
    cur_mes = mes or now.month
    data_mes_prefix = f"{cur_ano}-{cur_mes:02d}"
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (empresa_cnpj = ? OR emitente_cnpj = ? OR destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj, clean_cnpj]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Receita Bruta (Saídas, não canceladas)
        cursor.execute(
            f"SELECT SUM(valor_total) as v, COUNT(*) as q FROM nfe_docs "
            f"WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_rec = dict(cursor.fetchone())
        receita_bruta = float(r_rec["v"] or 0.0)
        qtd_vendas = int(r_rec["q"] or 0)

        # Impostos s/ Venda (ICMS + PIS + COFINS + IPI das saídas do período)
        cursor.execute(
            f"SELECT COALESCE(SUM(valor_icms),0) as icms, COALESCE(SUM(valor_pis),0) as pis, "
            f"COALESCE(SUM(valor_cofins),0) as cofins, COALESCE(SUM(valor_ipi),0) as ipi "
            f"FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_imp = dict(cursor.fetchone())
        impostos_venda = round(float(r_imp["icms"]) + float(r_imp["pis"]) + float(r_imp["cofins"]) + float(r_imp["ipi"]), 2)

        # CPV (Custo das Mercadorias Vendidas) = Entradas do período (não canceladas)
        cursor.execute(
            f"SELECT SUM(valor_total) as v FROM nfe_docs "
            f"WHERE tipo_doc = 0 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_cpv = cursor.fetchone()
        cpv = float(r_cpv["v"] or 0.0)

    receita_liquida = round(receita_bruta - impostos_venda, 2)
    lucro_bruto = round(receita_liquida - cpv, 2)

    # Imposto Simples (DAS) estimado do período
    simples = get_simples_nacional_apuracao(ano=cur_ano, mes=cur_mes, empresa_cnpj=empresa_cnpj)
    das_estimado = round(float(simples.get("valor_das_estimado") or 0.0), 2)

    lucro_liquido = round(lucro_bruto - das_estimado, 2)

    def pct(parte: float, total: float) -> float:
        return round((parte / total) * 100, 2) if total > 0 else 0.0

    return {
        "ano": cur_ano,
        "mes": cur_mes,
        "competencia": f"{cur_mes:02d}/{cur_ano}",
        "qtd_vendas": qtd_vendas,
        "receita_bruta": receita_bruta,
        "impostos_venda": impostos_venda,
        "receita_liquida": receita_liquida,
        "cpv": cpv,
        "lucro_bruto": lucro_bruto,
        "das_simples_estimado": das_estimado,
        "lucro_liquido": lucro_liquido,
        "margem_bruta_pct": pct(lucro_bruto, receita_liquida),
        "margem_liquida_pct": pct(lucro_liquido, receita_liquida),
        "simples": simples,
    }


# ====================================================================
# IMPOSTOS INTERESTADUAIS A RECOLHER (DIFAL - ICMS)
# ====================================================================

# Alíquotas internas do ICMS por UF (estimativa gerencial / valores praticados)
_ALIQUOTAS_INTERNAS_UF = {
    "AC": 17.0, "AL": 17.0, "AP": 17.0, "AM": 18.0, "BA": 19.0, "CE": 17.0,
    "DF": 18.0, "ES": 17.0, "GO": 17.0, "MA": 18.0, "MT": 17.0, "MS": 17.0,
    "MG": 18.0, "PA": 17.0, "PB": 18.0, "PR": 19.0, "PE": 18.0, "PI": 18.0,
    "RJ": 20.0, "RN": 18.0, "RS": 17.0, "RO": 17.5, "RR": 17.0, "SC": 17.0,
    "SP": 18.0, "SE": 18.0, "TO": 18.0,
}

def _aliquota_interestadual(aliq_interna_destino: float) -> float:
    """Alíquota interestadual conforme EC 87/2015 (4% / 7% / 12%) pela alíquota interna de destino."""
    if aliq_interna_destino <= 12.0:
        return 4.0
    if aliq_interna_destino <= 17.0:
        return 7.0
    if aliq_interna_destino <= 20.0:
        return 12.0
    return 4.0

def get_impostos_interestaduais(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Estima o DIFAL (ICMS a recolher sobre operações interestaduais de ENTRADA).

    Para cada NF-e de entrada (tipo_doc=0) cujo emitente está em UF diferente da
    UF da empresa (destinatário), calcula a diferença entre a alíquota interna de
    destino e a alíquota efetivamente aplicada (ou a interestadual) sobre o valor
    da nota. É uma PREVISÃO gerencial do imposto a recolher "fora do estado".
    """
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    rej_params = list(EVENTOS_REJEICAO)
    rej_placeholders = ",".join("?" for _ in rej_params)

    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, f"%{clean_cnpj}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT d.chave, d.numero, d.data_emissao, d.emitente_nome, d.emitente_uf,
                   d.destinatario_uf, d.empresa_cnpj, d.valor_total, d.valor_icms
            FROM nfe_docs d
            WHERE d.tipo_doc = 0
              AND d.situacao != 'Cancelada'
              AND d.emitente_uf IS NOT NULL AND d.destinatario_uf IS NOT NULL
              AND d.emitente_uf != d.destinatario_uf
              AND d.chave NOT IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))
              {emp_filter}
            ORDER BY d.data_emissao DESC
        """, rej_params + emp_params)
        docs = [dict(r) for r in cursor.fetchall()]

    itens = []
    total_difal = 0.0
    total_base = 0.0
    total_icms_proprio = 0.0

    for d in docs:
        uf_dest = (d.get("destinatario_uf") or "").strip().upper()
        uf_orig = (d.get("emitente_uf") or "").strip().upper()
        base = float(d.get("valor_total") or 0.0)
        icms_proprio = float(d.get("valor_icms") or 0.0)

        aliq_interna = _ALIQUOTAS_INTERNAS_UF.get(uf_dest, 18.0)
        # Alíquota efetivamente aplicada na origem (se houver ICMS registrado)
        if base > 0 and icms_proprio > 0:
            aliq_aplicada = (icms_proprio / base) * 100.0
        else:
            aliq_aplicada = _aliquota_interestadual(aliq_interna)

        difal = round(base * max(0.0, (aliq_interna - aliq_aplicada)) / 100.0, 2)

        if difal <= 0:
            continue

        total_difal += difal
        total_base += base
        total_icms_proprio += icms_proprio

        itens.append({
            "chave": d.get("chave"),
            "numero": d.get("numero"),
            "data_emissao": d.get("data_emissao"),
            "emitente_nome": d.get("emitente_nome"),
            "uf_origem": uf_orig,
            "uf_destino": uf_dest,
            "empresa_cnpj": d.get("empresa_cnpj"),
            "valor_total": base,
            "icms_proprio": round(icms_proprio, 2),
            "aliquota_interna_destino": aliq_interna,
            "aliquota_aplicada": round(aliq_aplicada, 2),
            "difal_estimado": difal,
        })

    return {
        "itens": itens,
        "total_notas": len(itens),
        "total_base": round(total_base, 2),
        "total_icms_proprio": round(total_icms_proprio, 2),
        "total_difal_estimado": round(total_difal, 2),
        "observacao": "Estimativa gerencial de DIFAL sobre o valor total da NF-e. Base real de cálculo pode incluir IPI/frete conforme legislação vigente.",
    }


# ====================================================================
# TENDÊNCIA MENSAL DO DRE (ÚLTIMOS 12 MESES)
# ====================================================================

def get_dre_tendencia(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Retorna a série histórica mensal do DRE (últimos 12 meses)."""
    now = datetime.now()
    cur_ano = now.year
    cur_mes = now.month

    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (empresa_cnpj = ? OR emitente_cnpj = ? OR destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj, clean_cnpj]

    meses = []
    for i in range(11, -1, -1):
        m = cur_mes - i
        a = cur_ano
        if m <= 0:
            m += 12
            a -= 1
        meses.append({"ano": a, "mes": m, "prefixo": f"{a}-{m:02d}"})

    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = []
        for mm in meses:
            p = mm["prefixo"]
            params = [p] + emp_params
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_total),0) as receita FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            receita = float(cursor.fetchone()["receita"])
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_icms),0)+COALESCE(SUM(valor_pis),0)+COALESCE(SUM(valor_cofins),0)+COALESCE(SUM(valor_ipi),0) as impostos FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            impostos = float(cursor.fetchone()["impostos"])
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_total),0) as cpv FROM nfe_docs WHERE tipo_doc=0 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            cpv = float(cursor.fetchone()["cpv"])
            cursor.execute(
                f"SELECT SUM(valor_total) as r FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            receita_mes = float(cursor.fetchone()["r"])
            cursor.execute(
                "SELECT SUM(valor_total) as r FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?",
                [p],
            )
            rbt12_local = float(cursor.fetchone()["r"] or 0.0)
            aliq_efetiva = max(0.04, ((rbt12_local * 0.04) / rbt12_local) if rbt12_local > 0 else 0.04)
            das = round(receita_mes * aliq_efetiva, 2) if receita_mes > 0 else 0.0
            receita_liquida = round(receita - impostos, 2)
            lucro_bruto = round(receita_liquida - cpv, 2)
            lucro_liquido = round(lucro_bruto - das, 2)
            rows.append({
                "ano": a, "mes": m, "competencia": f"{m:02d}/{a}",
                "receita_bruta": round(receita, 2), "impostos_venda": round(impostos, 2),
                "receita_liquida": receita_liquida, "cpv": round(cpv, 2),
                "lucro_bruto": lucro_bruto, "das_simples_estimado": das,
                "lucro_liquido": lucro_liquido,
            })

        # Contas a pagar/receber por mês (tendência de caixa)
        cursor.execute(
            f"SELECT substr(d_venc,1,7) as mes, SUM(v_dup) as total, SUM(CASE WHEN pago=1 THEN v_dup ELSE 0 END) as pago FROM nfe_duplicatas d JOIN nfe_docs doc ON d.chave=doc.chave WHERE doc.tipo_doc=0 AND substr(d_venc,1,7) IN ({','.join('?' for _ in meses)}) GROUP BY substr(d_venc,1,7)",
            [mm["prefixo"] for mm in meses],
        )
        ap_rows = {r["mes"]: r for r in cursor.fetchall()}
        cursor.execute(
            f"SELECT substr(d_venc,1,7) as mes, SUM(v_dup) as total, SUM(CASE WHEN recebido=1 THEN v_dup ELSE 0 END) as recebido FROM nfe_contas_receber r JOIN nfe_docs doc ON r.chave=doc.chave WHERE doc.tipo_doc=1 AND substr(d_venc,1,7) IN ({','.join('?' for _ in meses)}) GROUP BY substr(d_venc,1,7)",
            [mm["prefixo"] for mm in meses],
        )
        ar_rows = {r["mes"]: r for r in cursor.fetchall()}

    for row in rows:
        m = f"{row['ano']}-{row['mes']:02d}"
        ap = ap_rows.get(m, {"total": 0, "pago": 0})
        ar = ar_rows.get(m, {"total": 0, "recebido": 0})
        row["ap_total"] = round(float(ap["total"]), 2)
        row["ap_pago"] = round(float(ap["pago"]), 2)
        row["ar_total"] = round(float(ar["total"]), 2)
        row["ar_recebido"] = round(float(ar["recebido"]), 2)

    return {"tendencia": rows, "total_meses": len(rows)}


# ====================================================================
# EMPRESAS CADASTRADAS (DROPDOWN)
# ====================================================================

def get_simples_nacional_apuracao(ano: Optional[int] = None, mes: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """
    Calcula a estimativa de imposto do Simples Nacional (Anexo I - Comércio)
    com base no Faturamento dos últimos 12 meses (RBT12) e receita do mês corrente.
    """
    now = datetime.now()
    cur_ano = ano or now.year
    cur_mes = mes or now.month

    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    # Tabela Anexo I - Comércio (LC 123/2006)
    # Faixas: (Limite Superior, Alíquota Nominal %, Parcela a Deduzir R$)
    FAIXAS_ANEXO_I = [
        (180000.00, 0.0400, 0.00),         # 1ª Faixa: até 180k -> 4.00%
        (360000.00, 0.0730, 5940.00),      # 2ª Faixa: 180k a 360k -> 7.30%
        (720000.00, 0.0950, 13860.00),     # 3ª Faixa: 360k a 720k -> 9.50%
        (1800000.00, 0.1070, 22500.00),    # 4ª Faixa: 720k a 1.8M -> 10.70%
        (3600000.00, 0.1430, 87300.00),    # 5ª Faixa: 1.8M a 3.6M -> 14.30%
        (4800000.00, 0.1900, 378000.00),   # 6ª Faixa: 3.6M a 4.8M -> 19.00%
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Faturamento do Mês Corrente (Saídas / Vendas com tipo_doc=1)
        data_mes_prefix = f"{cur_ano}-{cur_mes:02d}"
        query_mes = "SELECT SUM(valor_total) as rpa, COUNT(*) as qtd FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?"
        params_mes = [data_mes_prefix]
        if clean_cnpj:
            query_mes += " AND (empresa_cnpj = ? OR emitente_cnpj = ?)"
            params_mes.extend([clean_cnpj, clean_cnpj])

        cursor.execute(query_mes, params_mes)
        r_mes = cursor.fetchone()
        receita_mes = float(r_mes["rpa"] or 0.0)
        qtd_vendas = int(r_mes["qtd"] or 0)

        # 2. Faturamento Total Acumulado (RBT12)
        query_rbt = "SELECT SUM(valor_total) as rbt12 FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada'"
        params_rbt = []
        if clean_cnpj:
            query_rbt += " AND (empresa_cnpj = ? OR emitente_cnpj = ?)"
            params_rbt.extend([clean_cnpj, clean_cnpj])

        cursor.execute(query_rbt, params_rbt)
        r_rbt = cursor.fetchone()
        rbt12 = float(r_rbt["rbt12"] or receita_mes)

    # Identifica faixa
    faixa_idx = 1
    aliq_nominal = 0.0400
    parcela_deduzir = 0.00

    for idx, (limite, aliq, ded) in enumerate(FAIXAS_ANEXO_I, start=1):
        if rbt12 <= limite or idx == len(FAIXAS_ANEXO_I):
            faixa_idx = idx
            aliq_nominal = aliq
            parcela_deduzir = ded
            break

    # Alíquota Efetiva = ((RBT12 * AliqNominal) - ParcelaDeduzir) / RBT12
    if rbt12 > 0:
        aliq_efetiva = max(0.0400, ((rbt12 * aliq_nominal) - parcela_deduzir) / rbt12)
    else:
        aliq_efetiva = 0.0400

    valor_das_estimado = round(receita_mes * aliq_efetiva, 2)

    return {
        "ano": cur_ano,
        "mes": cur_mes,
        "competencia": f"{cur_mes:02d}/{cur_ano}",
        "receita_mes": receita_mes,
        "qtd_vendas_mes": qtd_vendas,
        "rbt12": rbt12,
        "anexo": "Anexo I - Comércio",
        "faixa": faixa_idx,
        "aliquota_nominal_pct": round(aliq_nominal * 100, 2),
        "aliquota_efetiva_pct": round(aliq_efetiva * 100, 2),
        "parcela_deduzir": parcela_deduzir,
        "valor_das_estimado": valor_das_estimado,
        "data_vencimento": f"20/{cur_mes + 1 if cur_mes < 12 else 1:02d}/{cur_ano if cur_mes < 12 else cur_ano + 1}",
    }


# ====================================================================
# DRE DE MARGEM REAL POR PRODUTO (COMPRA VS. VENDA)
# ====================================================================

def get_dre_produtos_margem(empresa_cnpj: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Calcula o Lucro Bruto e a Margem Real (%) comparando preço de compra vs preço de venda de cada produto."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Busca preço médio de venda (Saídas)
        cursor.execute("""
            SELECT p.codigo, p.descricao, p.ncm, p.unidade,
                   p.preco_venda as preco_venda_catalogo,
                   p.preco_custo as preco_custo_catalogo,
                   p.estoque_atual,
                   (SELECT AVG(valor_unitario) FROM nfe_items WHERE (codigo = p.codigo OR descricao = p.descricao) AND valor_unitario > 0) as preco_medio_praticado,
                   (SELECT SUM(quantidade) FROM nfe_items WHERE (codigo = p.codigo OR descricao = p.descricao)) as total_vendido
            FROM cad_produtos p
            ORDER BY p.preco_venda DESC
            LIMIT ?
        """, (limit,))
        produtos = [dict(r) for r in cursor.fetchall()]

    dre_list = []
    for p in produtos:
        pv = float(p.get("preco_medio_praticado") or p.get("preco_venda_catalogo") or 0.0)
        pc = float(p.get("preco_custo_catalogo") or (pv * 0.65)) # Estimativa se custo não registrado
        lucro_unitario = pv - pc
        margem_pct = round((lucro_unitario / pv) * 100, 2) if pv > 0 else 0.0

        dre_list.append({
            "codigo": p.get("codigo"),
            "descricao": p.get("descricao"),
            "ncm": p.get("ncm"),
            "estoque": float(p.get("estoque_atual") or 0.0),
            "preco_custo": round(pc, 2),
            "preco_venda": round(pv, 2),
            "lucro_unitario": round(lucro_unitario, 2),
            "margem_lucro_pct": margem_pct,
            "status_margem": "EXCELENTE" if margem_pct >= 40 else ("BOA" if margem_pct >= 20 else "BAIXA")
        })

    return dre_list
