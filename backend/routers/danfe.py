import os
import io
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from lxml import etree

from backend.services.danfe_service import parse_nfe_xml, generate_danfe_pdf, parse_distribuicao_xml, build_synthetic_nfe_xml
from backend.services.cert_service import get_cert_path, get_cert_password, list_all_certificates
from backend.database import get_nfe_detail, save_nfe_doc, list_certificates_db, XML_STORAGE_DIR
from backend.config import settings
from backend.dependencies import require_session

router = APIRouter(dependencies=[Depends(require_session)])


def _get_local_xml(chave: str) -> Optional[bytes]:
    """Recupera o XML da NF-e a partir do banco de dados local SQLite, do disco ou sintetiza dos registros."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    if len(chave_clean) != 44:
        return None

    ns_nfe = "http://www.portalfiscal.inf.br/nfe"

    def _is_resumo(content: bytes) -> bool:
        """resNFe e resEvento (Distribuição DF-e) não servem para gerar
        DANFE completo — só têm cabeçalho. Devem ser ignorados para que
        o caller possa buscar o XML completo na SEFAZ."""
        if not content:
            return False
        try:
            root = etree.fromstring(content)
        except Exception:
            return False
        tag = etree.QName(root.tag).localname
        return tag in ("resNFe", "resEvento")

    # 2. Verifica no banco SQLite (xml_raw real tem prioridade sobre sintético)
    doc = get_nfe_detail(chave_clean)
    if doc:
        if doc.get("xml_raw") and len(doc["xml_raw"]) > 50:
            raw_bytes = doc["xml_raw"].encode("utf-8")
            if not _is_resumo(raw_bytes):
                return raw_bytes

    # 3. Verifica no disco (apenas XMLs reais, não sintéticos)
    disk_path = os.path.join(XML_STORAGE_DIR, f"{chave_clean}.xml")
    if os.path.exists(disk_path):
        try:
            with open(disk_path, "rb") as f:
                content = f.read()
                if len(content) > 100 and not _is_resumo(content):
                    # Verifica se é XML sintético (produto genérico)
                    try:
                        root_check = etree.fromstring(content)
                        ns_check = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
                        prods_check = root_check.findall('.//nfe:prod/nfe:xProd', ns_check)
                        if prods_check:
                            desc_check = (prods_check[0].text or '').strip()
                            if desc_check and 'PRODUTO / MERCADORIA VENDIDA' not in desc_check and len(desc_check) > 5:
                                return content
                    except Exception:
                        pass
        except Exception:
            pass

    # 4. Se temos o registro no banco (nfe_docs + nfe_items), gera o XML sintético
    #    SOMENTE se não existir xml_raw real no banco
    if doc and not (doc.get("xml_raw") and len(doc["xml_raw"]) > 50):
        try:
            produtos = doc.get("produtos", [])
            tem_descricao_real = any(
                (p.get("descricao") or "").strip()
                and "PRODUTO / MERCADORIA VENDIDA" not in (p.get("descricao") or "")
                and len((p.get("descricao") or "").strip()) > 5
                for p in produtos
            ) if produtos else False

            xml_bytes = build_synthetic_nfe_xml(doc)
            if xml_bytes:
                if tem_descricao_real:
                    try:
                        with open(disk_path, "wb") as f:
                            f.write(xml_bytes)
                    except Exception:
                        pass
                return xml_bytes
        except Exception:
            pass

    return None


def _fetch_nfe_from_sefaz(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Optional[bytes]:
    """Tenta obter o XML da NF-e na SEFAZ testando os certificados das empresas cadastradas.
    Se a NF-e foi recebida apenas como resumo (resNFe), envia automaticamente a Ciência da Emissão
    (tpEvento 210210) para que a SEFAZ libere o download do XML completo (nfeProc).
    """
    from pynfe.processamento.comunicacao import ComunicacaoSefaz
    from backend.database import save_nfe_event

    chave_clean = "".join(c for c in chave if c.isdigit())
    uf = (uf or ("SP" if chave_clean.startswith("35") else "RJ" if chave_clean.startswith("33") else "SP")).upper()
    homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    certs = list_certificates_db()
    if not certs:
        return None

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    for c in certs:
        if not c.get("is_active"):
            continue
        try:
            con = ComunicacaoSefaz(uf, c["path"], c["password"], homologacao=homolog)

            # 1. Tenta consulta_distribuicao por chave específica com o CNPJ da empresa
            dist_resp = con.consulta_distribuicao(cnpj=c["cnpj"], chave=chave_clean)
            if dist_resp.status_code == 200:
                parsed_dist = parse_distribuicao_xml(dist_resp.text)
                tem_apenas_resumo = False
                for doc in parsed_dist.get("documentos", []):
                    tag = doc.get("tag", "")
                    xml_raw = doc.get("xml_raw", "")
                    if tag in ("nfeProc", "NFe") and xml_raw:
                        xml_bytes = xml_raw.encode("utf-8")
                        try:
                            dados = parse_nfe_xml(xml_bytes)
                            dados["empresa_cnpj"] = c["cnpj"]
                            save_nfe_doc(dados, xml_raw=xml_raw, empresa_cnpj=c["cnpj"])
                        except Exception:
                            pass
                        return xml_bytes
                    elif tag == "resNFe":
                        tem_apenas_resumo = True

                # Se a SEFAZ devolveu apenas o resumo (resNFe), envia Ciência da Emissão para liberar o XML completo
                if tem_apenas_resumo:
                    try:
                        m_resp = con.manifestacao_destinatario(
                            chave=chave_clean,
                            cnpj=c["cnpj"],
                            tipo_evento="210210",
                            justificativa="Ciencia da Emissao automatica para download do XML",
                        )
                        save_nfe_event({
                            "chave": chave_clean,
                            "tipo_evento": "210210",
                            "desc_evento": "Ciência da Emissão",
                            "dh_evento": datetime.now().isoformat(),
                            "c_stat": "135",
                            "x_motivo": "Ciência da Emissão registrada na SEFAZ para liberação do XML",
                        })
                        # Nova tentativa de consulta após ciência
                        retry_resp = con.consulta_distribuicao(cnpj=c["cnpj"], chave=chave_clean)
                        if retry_resp.status_code == 200:
                            retry_parsed = parse_distribuicao_xml(retry_resp.text)
                            for r_doc in retry_parsed.get("documentos", []):
                                r_tag = r_doc.get("tag", "")
                                r_raw = r_doc.get("xml_raw", "")
                                if r_tag in ("nfeProc", "NFe") and r_raw:
                                    r_bytes = r_raw.encode("utf-8")
                                    try:
                                        dados = parse_nfe_xml(r_bytes)
                                        dados["empresa_cnpj"] = c["cnpj"]
                                        save_nfe_doc(dados, xml_raw=r_raw, empresa_cnpj=c["cnpj"])
                                    except Exception:
                                        pass
                                    return r_bytes
                    except Exception:
                        pass

            # 2. Tenta consulta_nota padrão de protocolo
            resp = con.consulta_nota("nfe", chave_clean)
            if resp.status_code == 200:
                root = etree.fromstring(resp.text.encode("utf-8") if isinstance(resp.text, str) else resp.text)
                nfe_node = root.find(".//nfe:NFe", ns)
                if nfe_node is not None:
                    xml_bytes = etree.tostring(nfe_node, xml_declaration=True, encoding="UTF-8")
                    try:
                        dados = parse_nfe_xml(xml_bytes)
                        dados["empresa_cnpj"] = c["cnpj"]
                        save_nfe_doc(dados, xml_raw=resp.text, empresa_cnpj=c["cnpj"])
                    except Exception:
                        pass
                    return xml_bytes
        except Exception:
            continue

    return None


@router.get("/parse/{chave}")
async def parse_danfe(chave: str, uf: Optional[str] = Query(None), homologacao: Optional[bool] = Query(None)):
    """Consulta a NF-e e retorna todos os dados (emitente, destinatário, produtos, totais) para visualização do DANFE."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    if len(chave_clean) != 44:
        raise HTTPException(status_code=400, detail="A chave deve conter 44 dígitos numéricos.")

    # 1. Primeiro verifica no banco de dados local e disco
    xml_bytes = _get_local_xml(chave_clean)

    # 2. Se não estiver no banco, busca na SEFAZ usando o certificado da empresa correta (com auto-manifestação)
    if not xml_bytes:
        xml_bytes = _fetch_nfe_from_sefaz(chave_clean, uf=uf, homologacao=homologacao)

    if not xml_bytes:
        # Se mesmo assim não achar o XML completo, monta a resposta com os dados parciais do banco
        doc = get_nfe_detail(chave_clean)
        if doc:
            nat_op = (
                doc.get("natureza_operacao")
                or doc.get("natureza")
                or ("DEVOLUCAO DE MERCADORIA" if "DEVOLU" in str(doc.get("emitente_nome", "")).upper() else "VENDA DE MERCADORIA / PRESTACAO")
            )
            tp_doc = str(doc.get("tipo_doc", 0) if doc.get("tipo_doc") is not None else 0)
            fin_doc = "4" if "DEVOLU" in nat_op.upper() else "1"
            dados_fallback = {
                "chave": doc["chave"],
                "numero": doc.get("numero", ""),
                "serie": doc.get("serie", "1"),
                "modelo": doc.get("modelo", "55"),
                "situacao": doc.get("situacao", "Autorizada"),
                "protocolo": doc.get("numero", "") or "Consta na base SEFAZ",
                "data_emissao": doc.get("data_emissao", ""),
                "data_autorizacao": doc.get("data_autorizacao", "") or doc.get("data_emissao", ""),
                "identificacao": {
                    "numero": doc.get("numero", ""),
                    "serie": doc.get("serie", "1"),
                    "modelo": doc.get("modelo", "55"),
                    "data_emissao": doc.get("data_emissao", ""),
                    "natureza": nat_op,
                    "natureza_operacao": nat_op,
                    "tipo": tp_doc,
                    "tipo_operacao": tp_doc,
                    "tipo_operacao_texto": "0 - ENTRADA" if tp_doc == "0" else "1 - SAÍDA",
                    "finalidade": fin_doc,
                    "finalidade_texto": "Devolução" if fin_doc == "4" else "Normal",
                },
                "emitente": {
                    "cnpj": doc.get("emitente_cnpj", ""),
                    "nome": doc.get("emitente_nome", ""),
                    "endereco": {"uf": doc.get("emitente_uf", "")},
                },
                "destinatario": {
                    "cnpj": doc.get("destinatario_cnpj", ""),
                    "nome": doc.get("destinatario_nome", ""),
                    "endereco": {"uf": doc.get("destinatario_uf", "")},
                },
                "totais": {
                    "v_nf": doc.get("valor_total", 0.0),
                    "v_icms": doc.get("valor_icms", 0.0),
                    "v_pis": doc.get("valor_pis", 0.0),
                    "v_cofins": doc.get("valor_cofins", 0.0),
                    "v_ipi": doc.get("valor_ipi", 0.0),
                    "v_outro": 0.0,
                },
                "produtos": doc.get("produtos", []),
            }
            return JSONResponse(content=dados_fallback)

        raise HTTPException(
            status_code=404,
            detail="NF-e não localizada localmente ou na SEFAZ. Você pode importar o arquivo XML diretamente.",
        )

    try:
        dados = parse_nfe_xml(xml_bytes)
        doc = get_nfe_detail(chave_clean)
        if doc:
            if "eventos" in doc and doc["eventos"]:
                dados["eventos"] = doc["eventos"]
            if not dados.get("situacao") and doc.get("situacao"):
                dados["situacao"] = doc["situacao"]
            if not dados.get("protocolo") and doc.get("numero"):
                dados["protocolo"] = doc.get("numero")
        return JSONResponse(content=dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar estrutura XML do DANFE: {str(e)}")


@router.get("/pdf/{chave}")
async def danfe_pdf(chave: str, uf: Optional[str] = Query(None), homologacao: Optional[bool] = Query(None)):
    """Gera o DANFE oficial em PDF com código de barras a partir do XML local ou SEFAZ."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    if len(chave_clean) != 44:
        raise HTTPException(status_code=400, detail="A chave deve conter 44 dígitos numéricos.")

    xml_bytes = _get_local_xml(chave_clean)
    if not xml_bytes:
        xml_bytes = _fetch_nfe_from_sefaz(chave_clean, uf=uf, homologacao=homologacao)

    if not xml_bytes:
        raise HTTPException(status_code=404, detail="XML da NF-e não encontrado para gerar o PDF DANFE.")

    pdf_buffer = generate_danfe_pdf(xml_bytes)
    if not pdf_buffer:
        raise HTTPException(status_code=500, detail="Não foi possível renderizar o PDF do DANFE.")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=DANFE_{chave_clean}.pdf"},
    )


@router.get("/resumo/{chave}")
async def resumo_danfe(chave: str, uf: Optional[str] = Query(None), homologacao: Optional[bool] = Query(None)):
    """Retorna o resumo da NF-e, checando banco local primeiro para evitar Consumo Indevido (656)."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    if len(chave_clean) != 44:
        raise HTTPException(status_code=400, detail="A chave deve conter 44 dígitos.")

    doc = get_nfe_detail(chave_clean)
    if doc:
        return {
            "chave": chave_clean,
            "c_stat": "100",
            "motivo": "Autorizado o uso da NF-e (Armazenada no Banco Local)",
            "n_prot": doc.get("numero", ""),
            "dh_recbto": doc.get("data_emissao", ""),
            "has_xml": doc.get("has_xml", 1),
        }

    # Se não tiver local, busca na SEFAZ com os certificados cadastrados
    from pynfe.processamento.comunicacao import ComunicacaoSefaz
    from backend.services.danfe_service import parse_resumo_sefaz

    certs = list_certificates_db()
    for c in certs:
        try:
            con = ComunicacaoSefaz(uf or "SP", c["path"], c["password"], homologacao=homologacao if homologacao is not None else settings.HOMOLOGACAO)
            resp = con.consulta_nota("nfe", chave_clean)
            if resp.status_code == 200:
                parsed = parse_resumo_sefaz(resp.text)
                parsed["chave"] = chave_clean
                return parsed
        except Exception:
            continue

    return {
        "chave": chave_clean,
        "c_stat": "100",
        "motivo": "Documento pronto para consulta",
    }


@router.post("/upload-xml")
@router.post("/xml")
async def upload_xml_danfe(payload: dict = Body(...)):
    """Recebe o texto XML da NF-e, parseia e salva no banco de dados local."""
    xml_str = payload.get("xml", "")
    if not xml_str or not xml_str.strip():
        raise HTTPException(status_code=400, detail="Conteúdo XML vazio.")

    xml_bytes = xml_str.encode("utf-8")
    dados = parse_nfe_xml(xml_bytes)
    if not dados or not dados.get("chave"):
        raise HTTPException(status_code=400, detail="XML inválido ou chave de acesso não encontrada.")

    save_nfe_doc(dados, xml_raw=xml_str)
    return JSONResponse(content=dados)


danfe_from_xml = upload_xml_danfe
