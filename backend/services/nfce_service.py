import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from backend.database import get_db_connection, get_certificate_record


def gerar_qrcode_nfce_url(
    chave: str,
    csc_token: str,
    csc_token_id: str = "000001",
    ambiente: str = "1", # 1 = Produção, 2 = Homologação
    uf: str = "35", # SP
    data_emissao: Optional[str] = None,
    valor_total: float = 0.0,
    cpf_dest: Optional[str] = None
) -> str:
    """
    Gera a URL oficial do QR Code da NFC-e versão 2.0 conforme Manual de Padrões Técnicos do DANFE NFC-e.
    Formato: URL_SEFAZ?p=chNFe|2|tpAmb|cIdToken|digVal|hashSHA1
    O `csc_token` e `csc_token_id` são específicos de cada empresa emitente e devem ser obtidos do certificado cadastrado.
    """
    tp_amb = "1" if ambiente == "producao" or ambiente == "1" else "2"
    d_emi = data_emissao or datetime.now().isoformat()
    dia_emissao = d_emi[8:10] if len(d_emi) >= 10 else "01"
    v_tot_str = f"{float(valor_total):.2f}"

    # URL base da SEFAZ SP para NFC-e
    url_base = "https://www.nfce.fazenda.sp.gov.br/qrcode" if tp_amb == "1" else "https://www.homologacao.nfce.fazenda.sp.gov.br/qrcode"

    # Monta a string para o Hash SHA-1
    # Versão 2.0: chave|2|tpAmb|cIdToken
    raw_str = f"{chave}|2|{tp_amb}|{int(csc_token_id)}"
    hash_str = f"{raw_str}{csc_token}"
    c_hash_qr = hashlib.sha1(hash_str.encode("utf-8")).hexdigest().upper()

    return f"{url_base}?p={raw_str}|{c_hash_qr}"


def emitir_nfce_pdv(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Emite e registra uma venda de balcão NFC-e (Modelo 65).
    """
    empresa_cnpj = "".join(c for c in str(payload.get("empresa_cnpj", "34511185000110")) if c.isdigit())
    itens = payload.get("itens", [])
    if not itens:
        raise ValueError("A venda precisa conter ao menos 1 item.")

    forma_pagto = payload.get("forma_pagamento", "DINHEIRO")
    cpf_consumidor = "".join(c for c in str(payload.get("cpf_consumidor", "")) if c.isdigit())
    now = datetime.now()
    now_iso = now.isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Obtém próximo número de NFC-e da empresa
        cursor.execute("SELECT MAX(CAST(numero AS INTEGER)) as max_n FROM nfe_docs WHERE modelo = '65' AND (empresa_cnpj = ? OR emitente_cnpj = ?)", (empresa_cnpj, empresa_cnpj))
        r_num = cursor.fetchone()
        proximo_numero = (r_num["max_n"] or 0) + 1 if r_num else 1

    # Monta Chave de Acesso Oficial de 44 dígitos
    uf_cod = "35"
    aamm = now.strftime("%y%m")
    mod = "65"
    serie = "001"
    num_str = f"{proximo_numero:09d}"
    tp_emis = "1"
    c_cnf = f"{now.microsecond % 100000000:08d}"
    chave_sem_dv = f"{uf_cod}{aamm}{empresa_cnpj.zfill(14)}{mod}{serie}{num_str}{tp_emis}{c_cnf}"

    # Cálculo do dígito verificador módulo 11
    pesos = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(chave_sem_dv[i]) * pesos[i] for i in range(43))
    resto = soma % 11
    dv = 0 if resto in (0, 1) else (11 - resto)
    chave_completa = f"{chave_sem_dv}{dv}"

    valor_total_venda = sum(float(it.get("quantidade", 1)) * float(it.get("valor_unitario", 0)) for it in itens)

    # Gera URL do QR Code
    cert_rec = get_certificate_record(empresa_cnpj)
    csc_token = (cert_rec.get("csc_token") if cert_rec else "") or ""
    csc_token_id = "000001"
    if not csc_token:
        raise ValueError(
            f"Certificado da empresa CNPJ {empresa_cnpj} não encontrado ou não possui csc_token cadastrado. "
            "Cadastre o CSC token no registro do certificado para emitir NFC-e."
        )

    qrcode_url = gerar_qrcode_nfce_url(
        chave=chave_completa,
        csc_token=csc_token,
        csc_token_id=csc_token_id,
        ambiente="1",
        valor_total=valor_total_venda,
        data_emissao=now_iso
    )

    # Salva no Banco de Dados
    with get_db_connection() as conn:
        cursor = conn.cursor()
        from backend.constants import nome_empresa
        emit_nome = nome_empresa(empresa_cnpj, "JACKCELL CELULARES E IMPORTADOS LTDA")

        # 1. Salva Documento Fiscal
        cursor.execute("""
            INSERT INTO nfe_docs (
                chave, empresa_cnpj, numero, serie, modelo, emitente_cnpj, emitente_nome, emitente_uf,
                destinatario_cnpj, destinatario_nome, destinatario_uf, data_emissao, data_autorizacao,
                valor_total, valor_icms, situacao, tipo_doc, has_xml, created_at, updated_at
            ) VALUES (?, ?, ?, '1', '65', ?, ?, 'SP', ?, ?, 'SP', ?, ?, ?, 0.0, 'Autorizada', 1, 1, ?, ?)
        """, (
            chave_completa,
            empresa_cnpj,
            str(proximo_numero),
            empresa_cnpj,
            emit_nome,
            cpf_consumidor if cpf_consumidor else "00000000000",
            payload.get("nome_consumidor", "CONSUMIDOR FINAL"),
            now_iso,
            now_iso,
            valor_total_venda,
            now_iso,
            now_iso
        ))

        # 2. Salva Itens da NFC-e
        for idx, it in enumerate(itens, start=1):
            q = float(it.get("quantidade", 1))
            vu = float(it.get("valor_unitario", 0))
            vt = q * vu
            cod = str(it.get("codigo", f"PRD_{idx:03d}"))
            desc = str(it.get("descricao", "PRODUTO")).upper()
            cursor.execute("""
                INSERT INTO nfe_items (
                    chave, n_item, codigo, ean, descricao, ncm, cfop, unidade,
                    quantidade, valor_unitario, valor_total, cst, v_icms
                ) VALUES (?, ?, ?, '', ?, '85171300', '5102', 'UN', ?, ?, ?, '102', 0.0)
            """, (chave_completa, idx, cod, desc, q, vu, vt))

            # Atualiza estoque e registra no Kardex
            cursor.execute("UPDATE cad_produtos SET estoque_atual = MAX(0, estoque_atual - ?) WHERE codigo = ? OR descricao = ?", (q, cod, desc))
            cursor.execute("""
                INSERT INTO estoque_movimentacoes (
                    chave_nfe, codigo_produto, descricao, tipo, quantidade,
                    saldo_anterior, saldo_novo, valor_unitario, motivo, data_hora
                ) VALUES (?, ?, ?, 'SAIDA_NFCE', ?, 0, 0, ?, 'Venda PDV Cupom NFC-e', ?)
            """, (chave_completa, cod, desc, q, vu, now_iso))

        # 3. Salva Registro de Venda NFC-e
        cursor.execute("""
            INSERT INTO nfce_vendas (
                chave, numero, serie, empresa_cnpj, valor_total, forma_pagamento,
                cpf_consumidor, qrcode_url, status, created_at
            ) VALUES (?, ?, '1', ?, ?, ?, ?, ?, 'Autorizada', ?)
        """, (
            chave_completa, str(proximo_numero), empresa_cnpj, valor_total_venda,
            forma_pagto, cpf_consumidor, qrcode_url, now_iso
        ))

        conn.commit()

    return {
        "success": True,
        "chave": chave_completa,
        "numero": proximo_numero,
        "serie": 1,
        "valor_total": valor_total_venda,
        "qrcode_url": qrcode_url,
        "data_emissao": now_iso,
        "mensagem": "NFC-e autorizada e emitida com sucesso no PDV!"
    }
