from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection

def get_empresas() -> List[Dict[str, Any]]:
    """Retorna as empresas cadastradas com certificados digitais ativos (CNPJ + Razão Social oficial)."""
    from backend.constants import EMPRESAS_OFICIAIS

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cnpj, razao_social as nome
            FROM certificates
            WHERE is_active = 1
            ORDER BY razao_social ASC
        """)
        empresas = [dict(r) for r in cursor.fetchall()]

    # Fallback se a tabela de certificados estiver vazia
    if not empresas:
        empresas = [{"cnpj": cnpj, "nome": nome} for cnpj, nome in EMPRESAS_OFICIAIS.items()]

    return empresas


# ====================================================================
# INADIMPLÊNCIA POR CLIENTE/FORNECEDOR
# ====================================================================

def save_cliente(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cadastra ou atualiza um cliente destinatário."""
    doc_clean = "".join(c for c in str(data.get("cpf_cnpj", "")) if c.isdigit())
    if not doc_clean or not data.get("razao_social"):
        raise ValueError("CPF/CNPJ e Razão Social são obrigatórios.")

    tipo_pessoa = "PF" if len(doc_clean) == 11 else "PJ"
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cli_id = data.get("id")
        if cli_id:
            cursor.execute("SELECT id FROM cad_clientes WHERE id = ?", (cli_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT id FROM cad_clientes WHERE cpf_cnpj = ?", (doc_clean,))
            row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE cad_clientes
                SET tipo_pessoa = ?, cpf_cnpj = ?, razao_social = ?, nome_fantasia = ?, ie = ?, indicador_ie = ?,
                    email = ?, telefone = ?, cep = ?, logradouro = ?, numero = ?, complemento = ?,
                    bairro = ?, municipio = ?, cod_municipio = ?, uf = ?, updated_at = ?
                WHERE id = ?
            """, (
                tipo_pessoa,
                doc_clean,
                data.get("razao_social", "").strip().upper(),
                data.get("nome_fantasia", "").strip().upper(),
                data.get("ie", "").strip(),
                int(data.get("indicador_ie", 9)),
                data.get("email", "").strip().lower(),
                data.get("telefone", "").strip(),
                data.get("cep", "").replace("-", "").strip(),
                data.get("logradouro", "").strip(),
                data.get("numero", "").strip(),
                data.get("complemento", "").strip(),
                data.get("bairro", "").strip(),
                data.get("municipio", "").strip(),
                data.get("cod_municipio", "3550308").strip(),
                data.get("uf", "SP").strip().upper(),
                now_iso,
                row["id"]
            ))
            cliente_id = row["id"]
        else:
            cursor.execute("""
                INSERT INTO cad_clientes (
                    tipo_pessoa, cpf_cnpj, razao_social, nome_fantasia, ie, indicador_ie,
                    email, telefone, cep, logradouro, numero, complemento,
                    bairro, municipio, cod_municipio, uf, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tipo_pessoa,
                doc_clean,
                data.get("razao_social", "").strip().upper(),
                data.get("nome_fantasia", "").strip().upper(),
                data.get("ie", "").strip(),
                int(data.get("indicador_ie", 9)),
                data.get("email", "").strip().lower(),
                data.get("telefone", "").strip(),
                data.get("cep", "").replace("-", "").strip(),
                data.get("logradouro", "").strip(),
                data.get("numero", "").strip(),
                data.get("complemento", "").strip(),
                data.get("bairro", "").strip(),
                data.get("municipio", "").strip(),
                data.get("cod_municipio", "3550308").strip(),
                data.get("uf", "SP").strip().upper(),
                now_iso,
                now_iso
            ))
            cliente_id = cursor.lastrowid
        conn.commit()

    return {"success": True, "id": cliente_id, "cpf_cnpj": doc_clean}

def list_clientes(busca: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos os clientes com suporte a busca rápida por nome, CPF/CNPJ, e-mail e telefone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if busca and busca.strip():
            b_clean = busca.strip()
            digits = "".join(c for c in b_clean if c.isdigit())
            b_like = f"%{b_clean}%"
            conds = [
                "razao_social LIKE ?",
                "nome_fantasia LIKE ?",
                "email LIKE ?",
                "telefone LIKE ?",
                "cpf_cnpj LIKE ?",
            ]
            params = [b_like, b_like, b_like, b_like, b_like]
            if len(digits) >= 2:
                conds.append("REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
                conds.append("REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '') LIKE ?")
                params.extend([f"%{digits}%", f"%{digits}%"])
            cursor.execute(f"SELECT * FROM cad_clientes WHERE {' OR '.join(conds)} ORDER BY razao_social ASC LIMIT 100", params)
        else:
            cursor.execute("SELECT * FROM cad_clientes ORDER BY razao_social ASC LIMIT 2000")
        return [dict(r) for r in cursor.fetchall()]

def delete_cliente(cliente_id: int) -> bool:
    """Exclui um cliente do cadastro."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cad_clientes WHERE id = ?", (cliente_id,))
        conn.commit()
        return cursor.rowcount > 0

def save_produto(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cadastra ou atualiza um item no catálogo de produtos com parâmetros fiscais completos."""
    codigo = str(data.get("codigo", "")).strip().upper()
    descricao = str(data.get("descricao", "")).strip().upper()
    ncm = "".join(c for c in str(data.get("ncm", "")) if c.isdigit())
    if not codigo or not descricao or not ncm:
        raise ValueError("Código, Descrição e NCM (8 dígitos) são obrigatórios.")

    now_iso = datetime.now().isoformat()
    preco = float(data.get("preco_venda", 0.0))
    preco_custo = float(data.get("preco_custo", 0.0))
    estoque_atual = float(data.get("estoque_atual", 0.0))
    estoque_min = float(data.get("estoque_minimo", 0.0))
    cfop = str(data.get("cfop_padrao", "5102")).strip()
    cfop_inter = str(data.get("cfop_interestadual", "6102")).strip()
    cest = str(data.get("cest", "")).strip()
    unidade = str(data.get("unidade", "UN")).strip().upper()
    origem = int(data.get("origem", 0))
    csosn = str(data.get("csosn_cst", "102")).strip()
    aliq_icms = float(data.get("aliquota_icms", 0.0))
    gtin = str(data.get("gtin", "")).strip()
    imei = str(data.get("imei", "")).strip().upper()
    marca = str(data.get("marca", "")).strip().upper()
    prod_id_input = data.get("id")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if prod_id_input:
            cursor.execute("SELECT id FROM cad_produtos WHERE id = ?", (prod_id_input,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT id FROM cad_produtos WHERE codigo = ?", (codigo,))
            row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE cad_produtos
                SET codigo = ?, descricao = ?, ncm = ?, cest = ?, cfop_padrao = ?, cfop_interestadual = ?,
                    unidade = ?, preco_venda = ?, preco_custo = ?, estoque_atual = ?, estoque_minimo = ?,
                    origem = ?, csosn_cst = ?, aliquota_icms = ?, gtin = ?, imei = ?, marca = ?, updated_at = ?
                WHERE id = ?
            """, (
                codigo, descricao, ncm, cest, cfop, cfop_inter,
                unidade, preco, preco_custo, estoque_atual, estoque_min,
                origem, csosn, aliq_icms, gtin, imei, marca, now_iso, row["id"]
            ))
            prod_id = row["id"]
        else:
            cursor.execute("""
                INSERT INTO cad_produtos (
                    codigo, descricao, ncm, cest, cfop_padrao, cfop_interestadual, unidade, preco_venda,
                    preco_custo, estoque_atual, estoque_minimo, origem, csosn_cst, aliquota_icms, gtin, imei, marca, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                codigo, descricao, ncm, cest, cfop, cfop_inter, unidade, preco,
                preco_custo, estoque_atual, estoque_min, origem, csosn, aliq_icms, gtin, imei, marca, now_iso, now_iso
            ))
            prod_id = cursor.lastrowid
        conn.commit()

    return {"success": True, "id": prod_id, "codigo": codigo, "descricao": descricao}

def get_produto_detail(prod_id: int) -> Optional[Dict[str, Any]]:
    """Retorna os dados completos de um produto específico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cad_produtos WHERE id = ?", (prod_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def sugerir_dados_fiscais_produto(termo: str) -> Dict[str, Any]:
    """
    Analisa a descrição digitada pelo usuário e consulta o histórico real de NF-e emitidas
    e a base de regras tributárias para sugerir automaticamente NCM, CEST, CFOP e Unidade.
    """
    termo_clean = (termo or "").strip().lower()
    if not termo_clean:
        return {
            "ncm": "85171300",
            "cest": "21.053.00",
            "cfop_padrao": "5102",
            "cfop_interestadual": "6102",
            "unidade": "UN",
            "origem": 0,
            "csosn_cst": "102",
            "fonte": "PADRAO"
        }

    # 1. Consulta no histórico de NF-e
    with get_db_connection() as conn:
        cursor = conn.cursor()
        t = f"%{termo_clean}%"
        cursor.execute("""
            SELECT ncm, cfop, unidade, AVG(valor_unitario) as preco_medio, COUNT(*) as cnt
            FROM nfe_items
            WHERE LOWER(descricao) LIKE ? AND ncm IS NOT NULL AND ncm != ''
            GROUP BY ncm, cfop, unidade
            ORDER BY cnt DESC
            LIMIT 1
        """, (t,))
        r = cursor.fetchone()
        if r and r["ncm"]:
            ncm_hist = str(r["ncm"]).replace(".", "").strip()
            cfop_hist = str(r["cfop"] or "5102").replace(".", "").strip()
            cfop_inter = "6102" if cfop_hist == "5102" else ("6403" if cfop_hist == "5405" else "6102")
            csosn_hist = "500" if cfop_hist == "5405" else "102"
            return {
                "ncm": ncm_hist,
                "cest": "21.053.00" if ncm_hist == "85171300" else "",
                "cfop_padrao": cfop_hist,
                "cfop_interestadual": cfop_inter,
                "unidade": str(r["unidade"] or "UN").upper(),
                "preco_sugerido": round(float(r["preco_medio"] or 0.0), 2),
                "origem": 0,
                "csosn_cst": csosn_hist,
                "fonte": f"HISTÓRICO NF-e ({r['cnt']} notas)",
                "ocorrencias": r["cnt"]
            }

    # 2. Base de conhecimento fiscal por categoria
    regras = [
        (["galaxy", "iphone", "celular", "smartphone", "xiaomi", "redmi", "motorola", "poco", "sansung", "samsung", "moto"], {
            "ncm": "85171300", "cest": "21.053.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Smartphones e Celulares"
        }),
        (["capa", "case", "capinha"], {
            "ncm": "85176262", "cest": "21.066.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Capas Protetoras"
        }),
        (["pelicula", "vidro", "ceramica", "hidrogel", "3d", "privacidade"], {
            "ncm": "39204900", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Películas de Proteção"
        }),
        (["carregador", "fonte", "adaptador", "turbo", "tomada"], {
            "ncm": "85044010", "cest": "21.001.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Carregadores e Fontes"
        }),
        (["fone", "headphone", "earphone", "airpod", "buds", "headset"], {
            "ncm": "85183000", "cest": "21.058.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Fones e Áudio"
        }),
        (["cabo", "lightning", "usb", "tipo c", "type c"], {
            "ncm": "85444200", "cest": "21.066.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Cabos e Conectores"
        }),
        (["tablet", "ipad", "pad"], {
            "ncm": "84713012", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Tablets"
        }),
        (["smartwatch", "relogio", "watch", "band", "pulseira"], {
            "ncm": "85176277", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Relógios Inteligentes"
        }),
        (["caixa de som", "speaker", "soundbar", "alexa", "echo"], {
            "ncm": "85182200", "cest": "21.057.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Caixas de Som"
        })
    ]

    for palavras, dados in regras:
        if any(p in termo_clean for p in palavras):
            return {**dados, "fonte": f"CATEGORIA: {dados.get('categoria', 'Geral')}"}

    return {
        "ncm": "85171300",
        "cest": "21.053.00",
        "cfop_padrao": "5102",
        "cfop_interestadual": "6102",
        "unidade": "UN",
        "origem": 0,
        "csosn_cst": "102",
        "fonte": "SUGESTÃO AUTOMÁTICA"
    }

def list_produtos(busca: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista catálogo de produtos com busca rápida."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if busca and busca.strip():
            b = f"%{busca.strip()}%"
            cursor.execute("""
                SELECT * FROM cad_produtos
                WHERE descricao LIKE ? OR codigo LIKE ? OR ncm LIKE ? OR gtin LIKE ?
                ORDER BY descricao ASC
            """, (b, b, b, b))
        else:
            cursor.execute("SELECT * FROM cad_produtos ORDER BY descricao ASC")
        return [dict(r) for r in cursor.fetchall()]

def delete_produto(prod_id: int) -> bool:
    """Exclui um produto do catálogo."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cad_produtos WHERE id = ?", (prod_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_next_nfe_number(empresa_cnpj: str, serie: str = "1", modelo: str = "55") -> int:
    """Calcula o próximo número sequencial de NF-e (Mod 55) ou NFC-e (Mod 65) para a empresa emitente e série informadas."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit())
    clean_serie = str(serie or "1").strip()
    clean_modelo = str(modelo or "55").strip()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Verifica notas emitidas por essa empresa (Saídas - tipo_doc = 1)
        if clean_modelo == "65":
            cursor.execute("""
                SELECT MAX(CAST(numero AS INTEGER)) as max_num
                FROM nfe_docs
                WHERE emitente_cnpj = ? AND serie = ? AND tipo_doc = 1 AND modelo = '65'
            """, (clean_cnpj, clean_serie))
        else:
            cursor.execute("""
                SELECT MAX(CAST(numero AS INTEGER)) as max_num
                FROM nfe_docs
                WHERE emitente_cnpj = ? AND serie = ? AND tipo_doc = 1 AND (modelo = '55' OR modelo IS NULL)
            """, (clean_cnpj, clean_serie))
        row = cursor.fetchone()
        max_doc = int(row["max_num"]) if row and row["max_num"] else 0

        # 2. Verifica se houve inutilizações de numeração cadastradas
        try:
            cursor.execute("""
                SELECT MAX(numero_final) as max_inu
                FROM nfe_inutilizacoes
                WHERE empresa_cnpj = ? AND serie = ? AND modelo = ?
            """, (clean_cnpj, clean_serie, clean_modelo))
            row_inu = cursor.fetchone()
            max_inu = int(row_inu["max_inu"]) if row_inu and row_inu["max_inu"] else 0
        except Exception:
            max_inu = 0

        max_final = max(max_doc, max_inu)
        return max_final + 1
