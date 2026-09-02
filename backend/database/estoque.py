from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection
from backend.database.nfe_docs import get_nfe_detail

def get_conferencia(chave: str) -> Dict[str, Any]:
    """Retorna o status da conferência de estoque de uma NF-e e a lista de itens."""
    doc = get_nfe_detail(chave)
    if not doc:
        return {}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfe_conferencia WHERE chave = ?", (chave,))
        conf = cursor.fetchone()

        conf_data = dict(conf) if conf else {
            "chave": chave,
            "empresa_cnpj": doc.get("empresa_cnpj", ""),
            "status": "PENDENTE",
            "conferido_por": "",
            "data_conferencia": "",
            "divergencias_count": 0,
            "observacoes": "",
        }

        cursor.execute("SELECT * FROM nfe_conferencia_items WHERE chave = ?", (chave,))
        saved_items = {r["codigo"] or r["descricao"]: dict(r) for r in cursor.fetchall()}

    items_list = []
    for it in doc.get("produtos", []):
        k = it.get("codigo") or it.get("descricao")
        saved = saved_items.get(k, {})
        qtd_nota = float(it.get("quantidade") or 0.0)
        qtd_conf = float(saved.get("qtd_conferida") or 0.0)
        diverg = qtd_conf != qtd_nota and conf_data.get("status") == "CONFERIDO"

        items_list.append({
            "codigo": it.get("codigo", ""),
            "ean": it.get("ean", ""),
            "descricao": it.get("descricao", ""),
            "ncm": it.get("ncm", ""),
            "unidade": it.get("unidade", "UN"),
            "qtd_nota": qtd_nota,
            "qtd_conferida": qtd_conf,
            "divergencia": diverg,
            "seriais": saved.get("seriais", ""),
            "status": "OK" if qtd_conf == qtd_nota and qtd_nota > 0 else ("DIVERGENTE" if qtd_conf > 0 else "PENDENTE"),
        })

    return {
        "conferencia": conf_data,
        "nfe": {
            "chave": doc["chave"],
            "numero": doc.get("numero", ""),
            "serie": doc.get("serie", "1"),
            "emitente_nome": doc.get("emitente_nome", ""),
            "destinatario_nome": doc.get("destinatario_nome", ""),
            "data_emissao": doc.get("data_emissao", ""),
            "valor_total": doc.get("valor_total", 0.0),
        },
        "itens": items_list,
    }

def salvar_conferencia(chave: str, conferido_por: str, itens: List[Dict[str, Any]], observacoes: str = "") -> Dict[str, Any]:
    """Salva a conferência física dos produtos da NF-e e detecta divergências."""
    now = datetime.now().isoformat()
    divergencias = 0

    for it in itens:
        if float(it.get("qtd_conferida", 0)) != float(it.get("qtd_nota", 0)):
            divergencias += 1

    status = "CONFERIDO_DIVERGENCIA" if divergencias > 0 else "CONFERIDO_OK"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT empresa_cnpj FROM nfe_docs WHERE chave = ?", (chave,))
        r = cursor.fetchone()
        emp_cnpj = r["empresa_cnpj"] if r else ""

        cursor.execute("""
            INSERT INTO nfe_conferencia (chave, empresa_cnpj, status, conferido_por, data_conferencia, divergencias_count, observacoes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                status = excluded.status,
                conferido_por = excluded.conferido_por,
                data_conferencia = excluded.data_conferencia,
                divergencias_count = excluded.divergencias_count,
                observacoes = excluded.observacoes
        """, (chave, emp_cnpj, status, conferido_por, now, divergencias, observacoes, now))
        conf_id = cursor.lastrowid

        cursor.execute("DELETE FROM nfe_conferencia_items WHERE chave = ?", (chave,))
        for it in itens:
            q_nota = float(it.get("qtd_nota", 0))
            q_conf = float(it.get("qtd_conferida", 0))
            st_it = "OK" if q_nota == q_conf else "DIVERGENTE"
            cursor.execute("""
                INSERT INTO nfe_conferencia_items (conferencia_id, chave, codigo, descricao, qtd_nota, qtd_conferida, seriais, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (conf_id, chave, it.get("codigo", ""), it.get("descricao", ""), q_nota, q_conf, it.get("seriais", ""), st_it))

        conn.commit()

    return {
        "success": True,
        "status": status,
        "divergencias_count": divergencias,
        "data_conferencia": now,
    }


# ====================================================================
# AUDITORIA DE RISCO & IDONEIDADE FISCAL DOS FORNECEDORES
# ====================================================================

def checkin_nfe_estoque(chave: str, markup_sugerido_pct: float = 40.0) -> Dict[str, Any]:
    """
    Processa os itens de uma NF-e de Entrada recebida de fornecedor:
    1. Cadastra automaticamente os produtos novos no catálogo (cad_produtos).
    2. Atualiza o estoque_atual somando as quantidades compradas.
    3. Registra a movimentação no histórico de estoque (Kardex).
    """
    chave_clean = "".join(c for c in chave if c.isdigit())
    now_iso = datetime.now().isoformat()

    doc = get_nfe_detail(chave_clean)
    if not doc:
        raise ValueError("NF-e não localizada no banco de dados local.")

    items = doc.get("produtos", [])
    if not items:
        raise ValueError("Esta NF-e não possui itens de produtos cadastrados.")

    produtos_cadastrados = 0
    produtos_atualizados = 0
    total_itens_processados = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for it in items:
            cod_item = str(it.get("codigo") or f"PRD_{it.get('id', 1):04d}").strip()
            desc_item = str(it.get("descricao") or "PRODUTO RECEBIDO").strip().upper()
            ncm_item = str(it.get("ncm") or "85171300").replace(".", "").strip()
            cfop_item = str(it.get("cfop") or "5102").replace(".", "").strip()
            qtd_item = float(it.get("quantidade") or 1.0)
            v_unit = float(it.get("valor_unitario") or 0.0)
            v_venda_sugerido = round(v_unit * (1.0 + (markup_sugerido_pct / 100.0)), 2)

            # Verifica se produto já existe no catálogo
            cursor.execute("SELECT id, codigo, estoque_atual, preco_venda FROM cad_produtos WHERE codigo = ? OR descricao = ?", (cod_item, desc_item))
            p_row = cursor.fetchone()

            saldo_anterior = 0.0
            if p_row:
                p_id = p_row["id"]
                saldo_anterior = float(p_row["estoque_atual"] or 0.0)
                saldo_novo = saldo_anterior + qtd_item
                # Atualiza estoque e preço de venda se estiver zerado
                cursor.execute("""
                    UPDATE cad_produtos
                    SET estoque_atual = ?, preco_custo = ?, updated_at = ?
                    WHERE id = ?
                """, (saldo_novo, v_unit, now_iso, p_id))
                produtos_atualizados += 1
            else:
                saldo_novo = qtd_item
                cursor.execute("""
                    INSERT OR IGNORE INTO cad_produtos (
                        codigo, descricao, ncm, cfop_padrao, unidade, preco_venda, preco_custo,
                        origem, csosn_cst, aliquota_icms, gtin, estoque_atual, ativo, created_at, updated_at
                    ) VALUES (?, ?, ?, '5102', 'UN', ?, ?, 0, '102', 0.0, '', ?, 1, ?, ?)
                """, (cod_item, desc_item, ncm_item, v_venda_sugerido if v_venda_sugerido > 0 else v_unit, v_unit, saldo_novo, now_iso, now_iso))
                produtos_cadastrados += 1

            # Registra no Kardex
            cursor.execute("""
                INSERT INTO estoque_movimentacoes (
                    chave_nfe, codigo_produto, descricao, tipo, quantidade,
                    saldo_anterior, saldo_novo, valor_unitario, motivo, data_hora
                ) VALUES (?, ?, ?, 'ENTRADA_NFE', ?, ?, ?, ?, ?, ?)
            """, (
                chave_clean, cod_item, desc_item, qtd_item,
                saldo_anterior, saldo_novo, v_unit,
                f"Check-in NF-e {doc.get('numero', '')} de {doc.get('emitente_nome', 'Fornecedor')}",
                now_iso
            ))
            total_itens_processados += 1

        conn.commit()

    return {
        "success": True,
        "chave": chave_clean,
        "total_itens": total_itens_processados,
        "produtos_novos": produtos_cadastrados,
        "produtos_atualizados": produtos_atualizados,
        "message": f"Check-in concluído! {total_itens_processados} itens adicionados ao estoque com sucesso."
    }

def get_historico_estoque(codigo_produto: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna o extrato de movimentações de estoque (Kardex)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if codigo_produto:
            cursor.execute("SELECT * FROM estoque_movimentacoes WHERE codigo_produto = ? ORDER BY id DESC LIMIT ?", (codigo_produto, limit))
        else:
            cursor.execute("SELECT * FROM estoque_movimentacoes ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]


# ====================================================================
# APURAÇÃO DO SIMPLES NACIONAL (LEI COMPLEMENTAR 123/2006)
# ====================================================================
