from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection
from backend.database.certificates import list_certificates_db

def get_analytics_dashboard(mes: Optional[int] = None, ano: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Retorna dados analíticos de compras (entradas), vendas (saídas) e impostos para o Dashboard filtrados por período e restritos exclusivamente às 5 empresas que possuem certificado digital."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    # Recupera a lista oficial dos CNPJs das empresas que possuem certificado ativo
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cnpj, razao_social FROM certificates WHERE is_active = 1")
        certs = cursor.fetchall()
        nossos_cnpjs = [r["cnpj"] for r in certs]

    if not nossos_cnpjs:
        nossos_cnpjs = ["34511185000110", "13787408000105", "44739622000101", "58186781000130", "58495100000116"]

    emp_digits = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    
    # Se uma empresa específica for selecionada (e ela for uma das nossas 5), filtra apenas por ela; senão usa todas as 5
    cnpjs_alvo = [emp_digits] if (emp_digits and emp_digits in nossos_cnpjs) else nossos_cnpjs
    placeholders = ",".join("?" for _ in cnpjs_alvo)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. TOTAIS DE ENTRADA (COMPRAS / FORNECEDORES - tipo_doc = 0)
        # Notas onde uma das nossas 5 empresas é a destinatária
        cursor.execute(f"""
            SELECT COUNT(*) as total_notas_entrada,
                   COALESCE(SUM(valor_total), 0.0) as total_compras,
                   COALESCE(SUM(valor_icms), 0.0) as total_icms,
                   COALESCE(SUM(valor_pis), 0.0) as total_pis,
                   COALESCE(SUM(valor_cofins), 0.0) as total_cofins,
                   COALESCE(SUM(valor_ipi), 0.0) as total_ipi
            FROM nfe_docs
            WHERE data_emissao LIKE ? 
              AND tipo_doc = 0 
              AND situacao != 'Cancelada' 
              AND (empresa_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders}))
        """, [f"{mes_str}%"] + cnpjs_alvo + cnpjs_alvo)
        totais_entrada = dict(cursor.fetchone())

        # 2. TOTAIS DE SAÍDA (VENDAS / CLIENTES - tipo_doc = 1)
        # Notas onde uma das nossas 5 empresas é a emitente
        cursor.execute(f"""
            SELECT COUNT(*) as total_notas_saida,
                   COALESCE(SUM(valor_total), 0.0) as total_vendas,
                   COALESCE(SUM(valor_icms), 0.0) as total_icms_vendas,
                   COALESCE(SUM(valor_pis), 0.0) as total_pis_vendas,
                   COALESCE(SUM(valor_cofins), 0.0) as total_cofins_vendas,
                   COALESCE(SUM(valor_ipi), 0.0) as total_ipi_vendas
            FROM nfe_docs
            WHERE data_emissao LIKE ? 
              AND tipo_doc = 1 
              AND situacao != 'Cancelada' 
              AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders}))
        """, [f"{mes_str}%"] + cnpjs_alvo + cnpjs_alvo)
        totais_saida = dict(cursor.fetchone())

        vendas_tot = float(totais_saida.get("total_vendas", 0.0))
        compras_tot = float(totais_entrada.get("total_compras", 0.0))
        qtd_vendas = int(totais_saida.get("total_notas_saida", 0))
        qtd_compras = int(totais_entrada.get("total_notas_entrada", 0))

        ticket_medio_vendas = (vendas_tot / qtd_vendas) if qtd_vendas > 0 else 0.0
        ticket_medio_compras = (compras_tot / qtd_compras) if qtd_compras > 0 else 0.0
        saldo_operacional = vendas_tot - compras_tot
        margem_bruta_pct = ((vendas_tot - compras_tot) / vendas_tot * 100) if vendas_tot > 0 else 0.0

        # 3. TOP 5 FORNECEDORES DO MÊS (ENTRADAS)
        cursor.execute(f"""
            SELECT emitente_nome, emitente_cnpj, COUNT(*) as qtd_notas, SUM(valor_total) as valor_total
            FROM nfe_docs
            WHERE data_emissao LIKE ? 
              AND tipo_doc = 0 
              AND situacao != 'Cancelada' 
              AND emitente_nome != '' 
              AND (empresa_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders}))
            GROUP BY emitente_cnpj, emitente_nome
            ORDER BY valor_total DESC
            LIMIT 5
        """, [f"{mes_str}%"] + cnpjs_alvo + cnpjs_alvo)
        top_fornecedores = [dict(r) for r in cursor.fetchall()]

        # 4. TOP 5 CLIENTES DO MÊS (SAÍDAS)
        cursor.execute(f"""
            SELECT destinatario_nome, destinatario_cnpj, COUNT(*) as qtd_notas, SUM(valor_total) as valor_total
            FROM nfe_docs
            WHERE data_emissao LIKE ? 
              AND tipo_doc = 1 
              AND situacao != 'Cancelada' 
              AND destinatario_nome != '' 
              AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders}))
            GROUP BY destinatario_cnpj, destinatario_nome
            ORDER BY valor_total DESC
            LIMIT 5
        """, [f"{mes_str}%"] + cnpjs_alvo + cnpjs_alvo)
        top_clientes = [dict(r) for r in cursor.fetchall()]

        # 5. EVOLUÇÃO COMPARATIVA MENSAL (ENTRADAS vs SAÍDAS - ÚLTIMOS 12 MESES)
        params_evol = (
            cnpjs_alvo + cnpjs_alvo +  # CASE 1 COUNT
            cnpjs_alvo + cnpjs_alvo +  # CASE 1 SUM
            cnpjs_alvo + cnpjs_alvo +  # CASE 2 COUNT
            cnpjs_alvo + cnpjs_alvo +  # CASE 2 SUM
            cnpjs_alvo + cnpjs_alvo + cnpjs_alvo  # WHERE
        )
        cursor.execute(f"""
            SELECT SUBSTR(data_emissao, 1, 7) as mes_ano,
                   COUNT(CASE WHEN tipo_doc = 0 AND (empresa_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders})) THEN 1 END) as qtd_entradas,
                   COALESCE(SUM(CASE WHEN tipo_doc = 0 AND (empresa_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders})) THEN valor_total ELSE 0 END), 0.0) as valor_entradas,
                   COUNT(CASE WHEN tipo_doc = 1 AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders})) THEN 1 END) as qtd_saidas,
                   COALESCE(SUM(CASE WHEN tipo_doc = 1 AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders})) THEN valor_total ELSE 0 END), 0.0) as valor_saidas
            FROM nfe_docs
            WHERE data_emissao != '' AND situacao != 'Cancelada'
              AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders}))
            GROUP BY mes_ano
            ORDER BY mes_ano DESC
            LIMIT 12
        """, params_evol)
        evolucao_mensal = [dict(r) for r in cursor.fetchall()][::-1]

        # 6. DISTRIBUIÇÃO POR EMPRESA FILIAL
        cursor.execute(f"""
            SELECT empresa_cnpj,
                   COALESCE(SUM(CASE WHEN tipo_doc = 0 THEN valor_total ELSE 0 END), 0.0) as compras,
                   COALESCE(SUM(CASE WHEN tipo_doc = 1 THEN valor_total ELSE 0 END), 0.0) as vendas,
                   COUNT(CASE WHEN tipo_doc = 0 THEN 1 END) as qtd_compras,
                   COUNT(CASE WHEN tipo_doc = 1 THEN 1 END) as qtd_vendas
            FROM nfe_docs
            WHERE data_emissao LIKE ? AND situacao != 'Cancelada' AND empresa_cnpj IN ({placeholders})
            GROUP BY empresa_cnpj
            ORDER BY vendas DESC
        """, [f"{mes_str}%"] + cnpjs_alvo)
        desempenho_empresas = [dict(r) for r in cursor.fetchall()]

        # Totais gerais do banco
        cursor.execute(f"""
            SELECT COUNT(*) as total_geral,
                   COALESCE(SUM(valor_total), 0.0) as valor_geral,
                   COUNT(CASE WHEN tipo_doc = 0 THEN 1 END) as total_entradas,
                   COALESCE(SUM(CASE WHEN tipo_doc = 0 THEN valor_total ELSE 0 END), 0.0) as valor_entradas_geral,
                   COUNT(CASE WHEN tipo_doc = 1 THEN 1 END) as total_saidas,
                   COALESCE(SUM(CASE WHEN tipo_doc = 1 THEN valor_total ELSE 0 END), 0.0) as valor_saidas_geral
            FROM nfe_docs WHERE situacao != 'Cancelada' AND (empresa_cnpj IN ({placeholders}) OR emitente_cnpj IN ({placeholders}) OR destinatario_cnpj IN ({placeholders}))
        """, cnpjs_alvo + cnpjs_alvo + cnpjs_alvo)
        total_banco = dict(cursor.fetchone())

    return {
        "mes": mes,
        "ano": ano,
        "empresa_cnpj": empresa_cnpj,
        "empresas_certificados": nossos_cnpjs,
        "totais_entrada": totais_entrada,
        "totais_saida": totais_saida,
        "totais_mes": totais_entrada, # compatibilidade
        "kpis_executivos": {
            "vendas_tot": vendas_tot,
            "compras_tot": compras_tot,
            "saldo_operacional": saldo_operacional,
            "margem_bruta_pct": margem_bruta_pct,
            "ticket_medio_vendas": ticket_medio_vendas,
            "ticket_medio_compras": ticket_medio_compras,
            "qtd_vendas": qtd_vendas,
            "qtd_compras": qtd_compras,
        },
        "top_fornecedores": top_fornecedores,
        "top_clientes": top_clientes,
        "evolucao_mensal": evolucao_mensal,
        "desempenho_empresas": desempenho_empresas,
        "total_banco": total_banco,
    }

def get_price_history(termo: str, empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consulta o histórico de preços pagos por um determinado produto/NCM."""
    if not termo:
        return []
    termo_like = f"%{termo.strip()}%"

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT i.descricao, i.codigo, i.ncm, i.unidade, i.quantidade, i.valor_unitario, i.valor_total,
                   d.chave, d.numero, d.data_emissao, d.emitente_nome, d.emitente_cnpj
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE (i.descricao LIKE ? OR i.ncm LIKE ? OR i.codigo LIKE ?) {emp_cond}
            ORDER BY d.data_emissao DESC
            LIMIT 50
        """, [termo_like, termo_like, termo_like] + emp_params)
        return [dict(r) for r in cursor.fetchall()]

def get_abc_curve(mes: Optional[int] = None, ano: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calcula a Curva ABC de produtos comprados no período exclusivamente para as 5 empresas com certificado."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    # Recupera a lista oficial dos CNPJs das empresas que possuem certificado ativo
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cnpj FROM certificates WHERE is_active = 1")
        certs = cursor.fetchall()
        nossos_cnpjs = [r["cnpj"] for r in certs]

    if not nossos_cnpjs:
        nossos_cnpjs = ["34511185000110", "13787408000105", "44739622000101", "58186781000130", "58495100000116"]

    emp_digits = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    cnpjs_alvo = [emp_digits] if (emp_digits and emp_digits in nossos_cnpjs) else nossos_cnpjs
    placeholders = ",".join("?" for _ in cnpjs_alvo)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT i.descricao, i.ncm, SUM(i.quantidade) as qtd_total, SUM(i.valor_total) as valor_total
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE d.data_emissao LIKE ? 
              AND d.tipo_doc = 0 
              AND d.situacao != 'Cancelada'
              AND (d.empresa_cnpj IN ({placeholders}) OR d.destinatario_cnpj IN ({placeholders}))
            GROUP BY i.descricao, i.ncm
            ORDER BY valor_total DESC
            LIMIT 30
        """, [f"{mes_str}%"] + cnpjs_alvo + cnpjs_alvo)
        rows = [dict(r) for r in cursor.fetchall()]

    total_geral = sum(r["valor_total"] for r in rows) or 1.0
    acumulado = 0.0
    for r in rows:
        pct = (r["valor_total"] / total_geral) * 100
        acumulado += pct
        r["percentual"] = round(pct, 2)
        r["acumulado"] = round(acumulado, 2)
        if acumulado <= 80:
            r["classe"] = "A"
        elif acumulado <= 95:
            r["classe"] = "B"
        else:
            r["classe"] = "C"

    return rows


# ====================================================================
# NOTIFICAÇÕES EM TEMPO REAL & ALERTAS
# ====================================================================

def get_price_divergences(empresa_cnpj: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Audita todas as compras e detecta variações de preços de um mesmo produto."""
    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Busca produtos com múltiplas compras
        cursor.execute(f"""
            SELECT i.descricao, i.codigo, i.ncm, i.valor_unitario, i.quantidade,
                   d.chave, d.numero, d.data_emissao, d.emitente_nome, d.empresa_cnpj, d.destinatario_nome
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE i.valor_unitario > 0 {emp_cond}
            ORDER BY i.descricao ASC, d.data_emissao DESC
        """, emp_params)
        all_items = [dict(r) for r in cursor.fetchall()]

    divergencias = []
    from collections import defaultdict
    grouped = defaultdict(list)
    for it in all_items:
        key = (it.get("codigo") or it.get("descricao") or "").strip().upper()
        if key:
            grouped[key].append(it)

    for key, items in grouped.items():
        if len(items) >= 2:
            latest = items[0]
            previous = items[1]
            p_lat = float(latest["valor_unitario"] or 0)
            p_prev = float(previous["valor_unitario"] or 0)

            if p_lat > 0 and p_prev > 0 and abs(p_lat - p_prev) > 0.01:
                diff = p_lat - p_prev
                pct = round((diff / p_prev) * 100, 2)
                divergencias.append({
                    "descricao": latest["descricao"],
                    "codigo": latest["codigo"],
                    "ncm": latest["ncm"],
                    "preco_atual": p_lat,
                    "preco_anterior": p_prev,
                    "diferenca_reais": round(diff, 2),
                    "variacao_pct": pct,
                    "tipo": "AUMENTO" if pct > 0 else "QUEDA",
                    "chave_atual": latest["chave"],
                    "data_atual": latest["data_emissao"],
                    "fornecedor_atual": latest["emitente_nome"],
                    "chave_anterior": previous["chave"],
                    "data_anterior": previous["data_emissao"],
                    "fornecedor_anterior": previous["emitente_nome"],
                    "empresa_destinatario": latest.get("destinatario_nome") or latest.get("empresa_cnpj"),
                })

    divergencias.sort(key=lambda x: abs(x["variacao_pct"]), reverse=True)
    return divergencias[:limit]


# ====================================================================
# CONCILIAÇÃO DE OPERAÇÕES INTERCOMPANY (ENTRE NOSSAS EMPRESAS)
# ====================================================================

def get_intercompany_operations() -> Dict[str, Any]:
    """Cruza as notas fiscais emitidas por uma de nossas empresas com destino a outra empresa nossa."""
    certs = list_certificates_db()
    cnpjs_nossos = [c["cnpj"] for c in certs if c.get("cnpj")]

    if not cnpjs_nossos:
        return {"operacoes": [], "resumo_transferencias": [], "total_volume": 0.0, "total_notas": 0}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chave, numero, serie, emitente_cnpj, emitente_nome,
                   destinatario_cnpj, destinatario_nome, data_emissao, valor_total, situacao
            FROM nfe_docs
            ORDER BY data_emissao DESC
        """)
        all_docs = [dict(r) for r in cursor.fetchall()]

    intercompany_docs = []
    total_volume = 0.0

    def clean_cnpj(c):
        return "".join(ch for ch in str(c) if ch.isdigit())

    for d in all_docs:
        e_cnpj = clean_cnpj(d.get("emitente_cnpj", ""))
        dest_cnpj = clean_cnpj(d.get("destinatario_cnpj", ""))

        if e_cnpj in cnpjs_nossos and dest_cnpj in cnpjs_nossos:
            intercompany_docs.append(d)
            total_volume += float(d.get("valor_total") or 0.0)

    # Matriz de transferências
    from collections import defaultdict
    transfer_matrix = defaultdict(lambda: {"qtd": 0, "total": 0.0, "origem": "", "destino": ""})
    for d in intercompany_docs:
        orig = d.get("emitente_nome") or d.get("emitente_cnpj")
        dest = d.get("destinatario_nome") or d.get("destinatario_cnpj")
        k = (orig, dest)
        transfer_matrix[k]["origem"] = orig
        transfer_matrix[k]["destino"] = dest
        transfer_matrix[k]["qtd"] += 1
        transfer_matrix[k]["total"] += float(d.get("valor_total") or 0.0)

    return {
        "operacoes": intercompany_docs,
        "resumo_transferencias": list(transfer_matrix.values()),
        "total_volume": total_volume,
        "total_notas": len(intercompany_docs),
    }


# ====================================================================
# GESTÃO FINANCEIRA & CONTAS A PAGAR (DUPLICATAS DE NF-e)
# ====================================================================

# Manifestações do destinatário que caracterizam rejeição/desconhecimento da NF-e
# (a nota não gera compromisso financeiro reconhecido): Desconhecimento (210220)
# e Operação Não Realizada (210240).
EVENTOS_REJEICAO = ("210220", "210240")

def get_inadimplencia(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Relatório de inadimplência: agrupa contas a receber por cliente."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (r.empresa_cnpj = ? OR r.cliente_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj]

    now_str = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT r.cliente_nome, r.cliente_cnpj,
                   SUM(r.v_dup) as total,
                   SUM(CASE WHEN r.recebido=0 AND (r.d_venc < ? OR r.d_venc = ?) THEN r.v_dup ELSE 0 END) as vencido,
                   SUM(CASE WHEN r.recebido=0 AND r.d_venc >= ? THEN r.v_dup ELSE 0 END) as aberto
            FROM nfe_contas_receber r
            JOIN nfe_docs doc ON r.chave = doc.chave
            WHERE doc.tipo_doc = 1 {emp_filter}
            GROUP BY r.cliente_nome, r.cliente_cnpj
            ORDER BY vencido DESC
        """, [now_str, now_str, now_str] + emp_params)
        rows = [dict(r) for r in cursor.fetchall()]

    for row in rows:
        total = float(row["total"] or 0.0)
        vencido = float(row["vencido"] or 0.0)
        row["pct_vencido"] = round((vencido / total) * 100, 2) if total > 0 else 0.0
        row["status"] = "INADIMPLENTE" if row["pct_vencido"] >= 50 else ("ATENÇÃO" if row["pct_vencido"] >= 20 else "EM DIA")

    return {"inadimplentes": rows, "total_clientes": len(rows)}


# ====================================================================
# CONFERÊNCIA CEGA DE ESTOQUE (CHECK-IN DE MERCADORIAS)
# ====================================================================

def get_auditoria_fornecedores(empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Audita os fornecedores cadastrados nas notas fiscais para apontar riscos fiscais."""
    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " WHERE (empresa_cnpj = ? OR destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT emitente_cnpj, emitente_nome, emitente_uf,
                   COUNT(*) as qtd_notas, SUM(valor_total) as volume_total,
                   MIN(data_emissao) as primeira_compra, MAX(data_emissao) as ultima_compra
            FROM nfe_docs
            {emp_cond}
            GROUP BY emitente_cnpj, emitente_nome, emitente_uf
            ORDER BY volume_total DESC
        """, emp_params)
        rows = [dict(r) for r in cursor.fetchall()]

    auditoria = []
    for r in rows:
        cnpj = "".join(c for c in str(r["emitente_cnpj"] or "") if c.isdigit())
        score = 100
        alertas = []

        # Validação matemática de dígitos verificadores do CNPJ
        if len(cnpj) != 14:
            score -= 50
            alertas.append("CNPJ com tamanho inválido")
        else:
            # Algoritmo de verificação de CNPJ
            def validar_cnpj(c):
                pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                d1 = sum(int(c[i]) * pesos1[i] for i in range(12)) % 11
                d1 = 0 if d1 < 2 else 11 - d1
                d2 = sum(int(c[i]) * pesos2[i] for i in range(13)) % 11
                d2 = 0 if d2 < 2 else 11 - d2
                return c[-2:] == f"{d1}{d2}"

            if not validar_cnpj(cnpj):
                score -= 60
                alertas.append("Dígito verificador do CNPJ inválido")

        if not r["emitente_uf"]:
            score -= 10
            alertas.append("UF do fornecedor não identificada")

        if r["qtd_notas"] >= 3:
            score = min(100, score + 10)

        cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj

        auditoria.append({
            "cnpj": cnpj_fmt,
            "razao_social": r["emitente_nome"],
            "uf": r["emitente_uf"] or "—",
            "qtd_notas": r["qtd_notas"],
            "volume_total": float(r["volume_total"] or 0.0),
            "primeira_compra": r["primeira_compra"],
            "ultima_compra": r["ultima_compra"],
            "score_conformidade": max(0, score),
            "nivel_risco": "BAIXO" if score >= 80 else ("MÉDIO" if score >= 50 else "ALTO"),
            "alertas": alertas,
            "status_sefaz": "HABILITADO / REGULAR",
        })

    return auditoria


# ====================================================================
# EMISSÃO DE NF-e: CLIENTES, PRODUTOS, PRÓXIMO NÚMERO & HISTÓRICO DE SAÍDAS
# ====================================================================
