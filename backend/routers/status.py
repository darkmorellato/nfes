from fastapi import APIRouter
from pynfe.processamento.comunicacao import ComunicacaoSefaz
from backend.config import settings
from backend.services.cert_service import get_cert_path, get_cert_password
from backend.services.pynfe_service import uf_from_chave
from typing import Optional

router = APIRouter()


@router.get("/status/{tipo}")
async def status_servico(tipo: str, uf: Optional[str] = None, homologacao: Optional[bool] = None):
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO

    try:
        cert_path = get_cert_path()
        cert_password = get_cert_password()
        con = ComunicacaoSefaz(uf, cert_path, cert_password, homologacao=homologacao)
        response = con.status_servico(tipo)
        return {"status_code": response.status_code, "body": response.text}
    except Exception as e:
        return {"error": str(e)}


@router.get("/consulta/chave")
async def consulta_chave(
    chave: str,
    modelo: str = "nfe",
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None
):
    uf = (uf or uf_from_chave(chave) or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO

    try:
        cert_path = get_cert_path()
        cert_password = get_cert_password()
        con = ComunicacaoSefaz(uf, cert_path, cert_password, homologacao=homologacao)
        response = con.consulta_nota(modelo, chave)
        return {"status_code": response.status_code, "body": response.text}
    except Exception as e:
        return {"error": str(e)}


@router.get("/consulta/cadastro")
async def consulta_cadastro(
    documento: str,
    tipo: str = "CNPJ",
    modelo: str = "nfe",
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None
):
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO

    try:
        cert_path = get_cert_path()
        cert_password = get_cert_password()
        con = ComunicacaoSefaz(uf, cert_path, cert_password, homologacao=homologacao)
        response = con.consulta_cadastro(modelo, documento, tipo=tipo, uf=uf)
        return {"status_code": response.status_code, "body": response.text}
    except Exception as e:
        return {"error": str(e)}


def _parse_distribuicao_xml(xml_text: str) -> dict:
    import base64
    import gzip
    from lxml import etree

    out = {
        "c_stat": "",
        "motivo": "",
        "ult_nsu": "0",
        "max_nsu": "0",
        "documentos": [],
    }
    if not xml_text:
        return out

    try:
        root = etree.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

        out["c_stat"] = root.findtext(".//nfe:cStat", default="", namespaces=ns)
        out["motivo"] = root.findtext(".//nfe:xMotivo", default="", namespaces=ns)
        out["ult_nsu"] = root.findtext(".//nfe:ultNSU", default="0", namespaces=ns)
        out["max_nsu"] = root.findtext(".//nfe:maxNSU", default="0", namespaces=ns)

        doc_zips = root.findall(".//nfe:docZip", ns)
        for dz in doc_zips:
            nsu = dz.attrib.get("NSU", "")
            schema = dz.attrib.get("schema", "")
            b64_content = (dz.text or "").strip()
            if not b64_content:
                continue

            try:
                xml_bytes = gzip.decompress(base64.b64decode(b64_content))
                inner_root = etree.fromstring(xml_bytes)
                tag_name = etree.QName(inner_root.tag).localname

                doc_info = {
                    "nsu": nsu,
                    "schema": schema,
                    "tag": tag_name,
                    "xml_raw": xml_bytes.decode("utf-8", errors="ignore"),
                    "chave": "",
                    "cnpj_emitente": "",
                    "nome_emitente": "",
                    "valor_total": "0.00",
                    "data_emissao": "",
                    "situacao": "",
                    "tipo": "NF-e",
                    "tipo_evento": "",
                    "desc_evento": "",
                }

                if tag_name == "resNFe":
                    doc_info["chave"] = inner_root.findtext(".//nfe:chNFe", default="", namespaces=ns) or inner_root.findtext(".//chNFe", default="")
                    doc_info["cnpj_emitente"] = inner_root.findtext(".//nfe:CNPJ", default="", namespaces=ns) or inner_root.findtext(".//CNPJ", default="")
                    doc_info["nome_emitente"] = inner_root.findtext(".//nfe:xNome", default="", namespaces=ns) or inner_root.findtext(".//xNome", default="")
                    doc_info["valor_total"] = inner_root.findtext(".//nfe:vNF", default="0.00", namespaces=ns) or inner_root.findtext(".//vNF", default="0.00")
                    doc_info["data_emissao"] = inner_root.findtext(".//nfe:dhEmi", default="", namespaces=ns) or inner_root.findtext(".//dhEmi", default="")
                    doc_info["situacao"] = inner_root.findtext(".//nfe:cSitNFe", default="", namespaces=ns) or inner_root.findtext(".//cSitNFe", default="")
                elif tag_name == "resEvento":
                    doc_info["chave"] = inner_root.findtext(".//nfe:chNFe", default="", namespaces=ns) or inner_root.findtext(".//chNFe", default="")
                    doc_info["cnpj_emitente"] = inner_root.findtext(".//nfe:CNPJ", default="", namespaces=ns) or inner_root.findtext(".//CNPJ", default="")
                    doc_info["tipo_evento"] = inner_root.findtext(".//nfe:tpEvento", default="", namespaces=ns) or inner_root.findtext(".//tpEvento", default="")
                    doc_info["desc_evento"] = inner_root.findtext(".//nfe:xEvento", default="", namespaces=ns) or inner_root.findtext(".//xEvento", default="")
                    doc_info["data_emissao"] = inner_root.findtext(".//nfe:dhEvento", default="", namespaces=ns) or inner_root.findtext(".//dhEvento", default="")
                    doc_info["tipo"] = f"Evento ({doc_info['tipo_evento']})"
                    doc_info["situacao"] = doc_info["desc_evento"]
                elif tag_name in ("nfeProc", "NFe"):
                    doc_info["chave"] = inner_root.findtext(".//nfe:chNFe", default="", namespaces=ns) or inner_root.findtext(".//nfe:infNFe", default="", namespaces=ns) or inner_root.findtext(".//chNFe", default="")
                    if not doc_info["chave"]:
                        inf_nfe = inner_root.find(".//nfe:infNFe", ns)
                        if inf_nfe is not None:
                            doc_info["chave"] = inf_nfe.attrib.get("Id", "").replace("NFe", "")
                    doc_info["cnpj_emitente"] = inner_root.findtext(".//nfe:emit/nfe:CNPJ", default="", namespaces=ns)
                    doc_info["nome_emitente"] = inner_root.findtext(".//nfe:emit/nfe:xNome", default="", namespaces=ns)
                    doc_info["valor_total"] = inner_root.findtext(".//nfe:total/nfe:ICMSTot/nfe:vNF", default="0.00", namespaces=ns)
                    doc_info["data_emissao"] = inner_root.findtext(".//nfe:ide/nfe:dhEmi", default="", namespaces=ns)
                    doc_info["situacao"] = "Autorizada (XML Completo)"
                elif tag_name in ("procEventoNFe", "evento"):
                    doc_info["chave"] = inner_root.findtext(".//nfe:chNFe", default="", namespaces=ns) or inner_root.findtext(".//chNFe", default="")
                    doc_info["tipo_evento"] = inner_root.findtext(".//nfe:tpEvento", default="", namespaces=ns) or inner_root.findtext(".//tpEvento", default="")
                    doc_info["desc_evento"] = inner_root.findtext(".//nfe:descEvento", default="", namespaces=ns) or inner_root.findtext(".//nfe:xEvento", default="", namespaces=ns)
                    doc_info["data_emissao"] = inner_root.findtext(".//nfe:dhEvento", default="", namespaces=ns)
                    doc_info["tipo"] = f"Evento ({doc_info['tipo_evento']})"
                    doc_info["situacao"] = doc_info["desc_evento"]

                out["documentos"].append(doc_info)
            except Exception:
                out["documentos"].append({
                    "nsu": nsu,
                    "schema": schema,
                    "tag": "docZip",
                    "chave": "",
                    "tipo": "Lote Compactado",
                    "situacao": "Disponível para download",
                })
    except Exception:
        pass

    return out


@router.get("/consulta/distribuicao")
async def consulta_distribuicao(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    chave: Optional[str] = None,
    nsu: int = 0,
    consulta_nsu_especifico: bool = False,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None
):
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO

    try:
        cert_path = get_cert_path()
        cert_password = get_cert_password()
        con = ComunicacaoSefaz(uf, cert_path, cert_password, homologacao=homologacao)
        response = con.consulta_distribuicao(
            cnpj=cnpj, cpf=cpf, chave=chave, nsu=nsu, consulta_nsu_especifico=consulta_nsu_especifico
        )
        parsed = _parse_distribuicao_xml(response.text)
        return {
            "status_code": response.status_code,
            "body": response.text,
            "parsed": parsed,
        }
    except Exception as e:
        return {"error": str(e)}
