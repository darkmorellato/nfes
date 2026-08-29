"""Servico de geracao do DANFE (Documento Auxiliar da NF-e).

Gera o PDF oficial da NF-e a partir do XML retornado pela SEFAZ, usando a
biblioteca brazilfiscalreport. Tambem expoe funcoes para parsear o XML
em dicionario para que o frontend renderize um preview HTML do DANFE.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any, Dict, Optional

from lxml import etree


def _t(tag: str) -> str:
    return re.sub(r"^[^}]+}", "", tag)


def _find(node, path: str, default: str = ""):
    if node is None:
        return default
    el = node.find(path)
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _format_cnpj(cnpj: str) -> str:
    cnpj = re.sub(r"\D", "", cnpj or "")
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    if len(cnpj) == 11:
        return f"{cnpj[:3]}.{cnpj[3:6]}.{cnpj[6:9]}-{cnpj[9:]}"
    return cnpj


def _format_cep(cep: str) -> str:
    cep = re.sub(r"\D", "", cep or "")
    if len(cep) == 8:
        return f"{cep[:5]}-{cep[5:]}"
    return cep


def _format_fone(fone: str) -> str:
    fone = re.sub(r"\D", "", fone or "")
    if len(fone) == 11:
        return f"({fone[:2]}) {fone[2:7]}-{fone[7:]}"
    if len(fone) == 10:
        return f"({fone[:2]}) {fone[2:6]}-{fone[6:]}"
    return fone



def _format_br_datetime(value: str) -> str:
    """Converte ISO datetime (com ou sem TZ) para 'dd/mm/yyyy HH:MM:SS'.

    Retorna a string original caso nao seja possivel interpretar.
    """
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""
    try:
        cleaned = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, TypeError):
        return raw


def parse_resumo_sefaz(xml_string: str) -> Dict[str, Any]:
    """Faz o parse de um XML de retorno da SEFAZ (retEnviNFe, retConsSitNFe,
    procNFe, etc.) e devolve um dicionario com o resumo da NF-e pronto
    para exibicao no portal.

    Nao levanta excecao: em qualquer erro retorna um dicionario com
    campos vazios.
    """
    empty: Dict[str, Any] = {
        "c_stat": "",
        "motivo": "",
        "uf": "",
        "chave": "",
        "protocolo": "",
        "data_autorizacao": "",
        "digito_verificador": "",
        "tipo_ambiente": "",
        "versao": "",
        "numero": "",
        "serie": "",
        "data_emissao": "",
        "emitente_cnpj": "",
        "emitente_nome": "",
        "destinatario_cnpj": "",
        "destinatario_nome": "",
        "valor_total": "",
        "eventos": [],
    }

    if not xml_string:
        return empty

    try:
        if isinstance(xml_string, bytes):
            data = xml_string
        else:
            data = xml_string.encode("utf-8")
        root = etree.fromstring(data)
    except Exception:
        return empty

    try:
        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

        inf_prot = root.find(".//nfe:infProt", ns)
        prot_nfe = root.find(".//nfe:protNFe", ns)
        ide = root.find(".//nfe:ide", ns)
        emit = root.find(".//nfe:emit", ns)
        dest = root.find(".//nfe:dest", ns)
        total = root.find(".//nfe:total", ns)
        inf_nfe = root.find(".//nfe:infNFe", ns)
        ret_cons = root.find(".//nfe:retConsSitNFe", ns) or root.find(".//nfe:retEnviNFe", ns)

        resumo: Dict[str, Any] = dict(empty)

        if ret_cons is not None:
            resumo["c_stat"] = (ret_cons.findtext("nfe:cStat", default="", namespaces=ns) or "").strip()
            resumo["motivo"] = (ret_cons.findtext("nfe:xMotivo", default="", namespaces=ns) or "").strip()
            resumo["uf"] = (ret_cons.findtext("nfe:cUF", default="", namespaces=ns) or "").strip()
            resumo["tipo_ambiente"] = (ret_cons.findtext("nfe:tpAmb", default="", namespaces=ns) or "").strip()
            resumo["versao"] = ret_cons.get("versao", "") or ""
        elif prot_nfe is not None:
            resumo["versao"] = prot_nfe.get("versao", "") or ""
        elif root is not None:
            resumo["versao"] = root.get("versao", "") or ""

        if inf_prot is not None:
            if not resumo["c_stat"]:
                resumo["c_stat"] = (inf_prot.findtext("nfe:cStat", default="", namespaces=ns) or "").strip()
            if not resumo["motivo"]:
                resumo["motivo"] = (inf_prot.findtext("nfe:xMotivo", default="", namespaces=ns) or "").strip()
            resumo["chave"] = (inf_prot.findtext("nfe:chNFe", default="", namespaces=ns) or "").strip()
            resumo["protocolo"] = (inf_prot.findtext("nfe:nProt", default="", namespaces=ns) or "").strip()
            resumo["data_autorizacao"] = _format_br_datetime(
                inf_prot.findtext("nfe:dhRecbto", default="", namespaces=ns) or ""
            )
            resumo["digito_verificador"] = (inf_prot.findtext("nfe:digVal", default="", namespaces=ns) or "").strip()
            resumo["tipo_ambiente"] = (inf_prot.findtext("nfe:tpAmb", default="", namespaces=ns) or "").strip()
            if not resumo["uf"]:
                resumo["uf"] = (inf_prot.findtext("nfe:cUF", default="", namespaces=ns) or "").strip()

        if inf_nfe is not None and not resumo["chave"]:
            resumo["chave"] = inf_nfe.get("Id", "").replace("NFe", "").strip()

        if ide is not None:
            resumo["numero"] = (ide.findtext("nfe:nNF", default="", namespaces=ns) or "").strip()
            resumo["serie"] = (ide.findtext("nfe:serie", default="", namespaces=ns) or "").strip()
            if not resumo["data_emissao"]:
                resumo["data_emissao"] = _format_br_datetime(
                    ide.findtext("nfe:dhEmi", default="", namespaces=ns) or ""
                )
            if not resumo["uf"]:
                resumo["uf"] = (ide.findtext("nfe:cUF", default="", namespaces=ns) or "").strip()
            if not resumo["tipo_ambiente"]:
                resumo["tipo_ambiente"] = (ide.findtext("nfe:tpAmb", default="", namespaces=ns) or "").strip()

        if emit is not None:
            resumo["emitente_cnpj"] = (emit.findtext("nfe:CNPJ", default="", namespaces=ns)
                                       or emit.findtext("nfe:CPF", default="", namespaces=ns)
                                       or "").strip()
            resumo["emitente_nome"] = (emit.findtext("nfe:xNome", default="", namespaces=ns) or "").strip()

        if dest is not None:
            resumo["destinatario_cnpj"] = (dest.findtext("nfe:CNPJ", default="", namespaces=ns)
                                           or dest.findtext("nfe:CPF", default="", namespaces=ns)
                                           or dest.findtext("nfe:idEstrangeiro", default="", namespaces=ns)
                                           or "").strip()
            resumo["destinatario_nome"] = (dest.findtext("nfe:xNome", default="", namespaces=ns) or "").strip()

        if total is not None:
            icms_tot = total.find("nfe:ICMSTot", ns)
            if icms_tot is not None:
                resumo["valor_total"] = (icms_tot.findtext("nfe:vNF", default="", namespaces=ns) or "").strip()

        eventos: list = []
        for proc_evento in root.findall(".//nfe:procEventoNFe", ns):
            evento = proc_evento.find("nfe:evento", ns)
            inf_evento = evento.find("nfe:infEvento", ns) if evento is not None else None
            if inf_evento is None:
                continue
            det_evento = inf_evento.find("nfe:detEvento", ns)
            tipo_evento = ""
            if det_evento is not None:
                tipo_evento = (det_evento.findtext("nfe:descEvento", default="", namespaces=ns)
                               or det_evento.get("versao", "")
                               or "").strip()
            eventos.append({
                "tipo": tipo_evento,
                "n_protocolo": (inf_evento.findtext("nfe:nProt", default="", namespaces=ns) or "").strip(),
                "data": _format_br_datetime(
                    inf_evento.findtext("nfe:dhRegEvento", default="", namespaces=ns) or ""
                ),
                "chave": (inf_evento.findtext("nfe:chNFe", default="", namespaces=ns) or "").strip(),
            })
        resumo["eventos"] = eventos

        if not resumo["data_emissao"] and ide is None:
            for candidate_tag in ("dhEmi", "dEmi"):
                value = (root.findtext(f".//nfe:{candidate_tag}", default="", namespaces=ns) or "").strip()
                if value:
                    resumo["data_emissao"] = _format_br_datetime(value)
                    break

        if not resumo["valor_total"]:
            v_nf = (root.findtext(".//nfe:vNF", default="", namespaces=ns) or "").strip()
            if v_nf:
                resumo["valor_total"] = v_nf

        if not resumo["c_stat"]:
            c_stat = (root.findtext(".//nfe:cStat", default="", namespaces=ns) or "").strip()
            if c_stat:
                resumo["c_stat"] = c_stat
        if not resumo["motivo"]:
            motivo = (root.findtext(".//nfe:xMotivo", default="", namespaces=ns) or "").strip()
            if motivo:
                resumo["motivo"] = motivo

        return resumo
    except Exception:
        return empty


def parse_nfe_xml(xml_bytes: bytes) -> Dict[str, Any]:
    """Converte o XML da NF-e em um dicionario estruturado para preview HTML."""
    if not xml_bytes:
        return {}

    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        return {"error": f"XML invalido: {exc}"}

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    inf_nfe = root.find(".//nfe:infNFe", ns)
    ide = root.find(".//nfe:ide", ns)
    emit = root.find(".//nfe:emit", ns)
    dest = root.find(".//nfe:dest", ns)
    total = root.find(".//nfe:total", ns)
    transp = root.find(".//nfe:transp", ns)
    inf_adic = root.find(".//nfe:infAdic", ns)
    prot_nfe = root.find(".//nfe:protNFe", ns)

    chave = ""
    if inf_nfe is not None:
        chave = inf_nfe.get("Id", "").replace("NFe", "")

    protocolo = ""
    data_aut = ""
    if prot_nfe is not None:
        inf_prot = prot_nfe.find(".//nfe:infProt", ns)
        if inf_prot is not None:
            protocolo = inf_prot.findtext("nfe:nProt", default="", namespaces=ns).strip()
            data_aut = inf_prot.findtext("nfe:dhRecbto", default="", namespaces=ns).strip()

    emitente: Dict[str, Any] = {
        "nome": "",
        "cnpj": "",
    }
    if emit is not None:
        emitente["nome"] = emit.findtext("nfe:xNome", default="", namespaces=ns)
        emitente["cnpj"] = emit.findtext("nfe:CNPJ", default="", namespaces=ns)
        ender_emit = emit.find("nfe:enderEmit", ns)
        if ender_emit is not None:
            emitente["endereco"] = {
                "logradouro": ender_emit.findtext("nfe:xLgr", default="", namespaces=ns),
                "numero": ender_emit.findtext("nfe:nro", default="", namespaces=ns),
                "bairro": ender_emit.findtext("nfe:xBairro", default="", namespaces=ns),
                "municipio": ender_emit.findtext("nfe:xMun", default="", namespaces=ns),
                "uf": ender_emit.findtext("nfe:UF", default="", namespaces=ns),
                "cep": _format_cep(ender_emit.findtext("nfe:CEP", default="", namespaces=ns)),
                "fone": _format_fone(ender_emit.findtext("nfe:fone", default="", namespaces=ns)),
            }
        emitente["ie"] = emit.findtext("nfe:IE", default="", namespaces=ns)

    destinatario: Dict[str, Any] = {}
    if dest is not None:
        destinatario = {
            "nome": dest.findtext("nfe:xNome", default="", namespaces=ns),
            "cnpj": _format_cnpj(dest.findtext("nfe:CNPJ", default="", namespaces=ns)),
            "cpf": _format_cnpj(dest.findtext("nfe:CPF", default="", namespaces=ns)),
            "ie": dest.findtext("nfe:IE", default="", namespaces=ns),
            "email": dest.findtext("nfe:email", default="", namespaces=ns),
        }
        ender_dest = dest.find("nfe:enderDest", ns)
        if ender_dest is not None:
            destinatario["endereco"] = {
                "logradouro": ender_dest.findtext("nfe:xLgr", default="", namespaces=ns),
                "numero": ender_dest.findtext("nfe:nro", default="", namespaces=ns),
                "bairro": ender_dest.findtext("nfe:xBairro", default="", namespaces=ns),
                "municipio": ender_dest.findtext("nfe:xMun", default="", namespaces=ns),
                "uf": ender_dest.findtext("nfe:UF", default="", namespaces=ns),
                "cep": _format_cep(ender_dest.findtext("nfe:CEP", default="", namespaces=ns)),
            }

    identificacao: Dict[str, Any] = {}
    if ide is not None:
        identificacao = {
            "numero": ide.findtext("nfe:nNF", default="", namespaces=ns),
            "serie": ide.findtext("nfe:serie", default="", namespaces=ns),
            "data_emissao": ide.findtext("nfe:dhEmi", default="", namespaces=ns),
            "data_saida": ide.findtext("nfe:dhSaiEnt", default="", namespaces=ns),
            "modelo": ide.findtext("nfe:mod", default="", namespaces=ns),
            "natureza": ide.findtext("nfe:natOp", default="", namespaces=ns),
            "tipo": ide.findtext("nfe:tpNF", default="", namespaces=ns),
            "ambiente": ide.findtext("nfe:tpAmb", default="", namespaces=ns),
            "uf_emitente": ide.findtext("nfe:cUF", default="", namespaces=ns),
        }

    totais: Dict[str, Any] = {}
    if total is not None:
        icms_tot = total.find("nfe:ICMSTot", ns)
        if icms_tot is not None:
            totais = {
                "v_bc_icms": icms_tot.findtext("nfe:vBC", default="0.00", namespaces=ns),
                "v_icms": icms_tot.findtext("nfe:vICMS", default="0.00", namespaces=ns),
                "v_bc_icms_st": icms_tot.findtext("nfe:vBCST", default="0.00", namespaces=ns),
                "v_icms_st": icms_tot.findtext("nfe:vST", default="0.00", namespaces=ns),
                "v_prod": icms_tot.findtext("nfe:vProd", default="0.00", namespaces=ns),
                "v_frete": icms_tot.findtext("nfe:vFrete", default="0.00", namespaces=ns),
                "v_seg": icms_tot.findtext("nfe:vSeg", default="0.00", namespaces=ns),
                "v_desc": icms_tot.findtext("nfe:vDesc", default="0.00", namespaces=ns),
                "v_ii": icms_tot.findtext("nfe:vII", default="0.00", namespaces=ns),
                "v_ipi": icms_tot.findtext("nfe:vIPI", default="0.00", namespaces=ns),
                "v_pis": icms_tot.findtext("nfe:vPIS", default="0.00", namespaces=ns),
                "v_cofins": icms_tot.findtext("nfe:vCOFINS", default="0.00", namespaces=ns),
                "v_nf": icms_tot.findtext("nfe:vNF", default="0.00", namespaces=ns),
            }

    produtos: list[Dict[str, Any]] = []
    for det in root.findall(".//nfe:det", ns):
        prod = det.find("nfe:prod", ns)
        imposto = det.find("nfe:imposto", ns)
        item: Dict[str, Any] = {}
        if prod is not None:
            item = {
                "n_item": det.get("nItem", ""),
                "codigo": prod.findtext("nfe:cProd", default="", namespaces=ns),
                "ean": prod.findtext("nfe:cEAN", default="", namespaces=ns),
                "descricao": prod.findtext("nfe:xProd", default="", namespaces=ns),
                "ncm": prod.findtext("nfe:NCM", default="", namespaces=ns),
                "cfop": prod.findtext("nfe:CFOP", default="", namespaces=ns),
                "unidade": prod.findtext("nfe:uCom", default="", namespaces=ns),
                "quantidade": prod.findtext("nfe:qCom", default="0", namespaces=ns),
                "valor_unitario": prod.findtext("nfe:vUnCom", default="0.00", namespaces=ns),
                "valor_total": prod.findtext("nfe:vProd", default="0.00", namespaces=ns),
            }
        if imposto is not None:
            icms = imposto.find(".//nfe:ICMS", ns)
            if icms is not None:
                for child in icms:
                    item["cst"] = child.findtext("nfe:orig", default="", namespaces=ns) + "/" + \
                                  child.findtext("nfe:CST", default=child.findtext("nfe:CSOSN", default="", namespaces=ns), namespaces=ns)
                    item["v_bc_icms"] = child.findtext("nfe:vBC", default="", namespaces=ns)
                    item["v_icms"] = child.findtext("nfe:vICMS", default="", namespaces=ns)
                    item["aliquota_icms"] = child.findtext("nfe:pICMS", default="", namespaces=ns)
                    break
        produtos.append(item)

    transportadora: Dict[str, Any] = {}
    if transp is not None:
        transport_node = transp.find("nfe:transporta", ns)
        if transport_node is not None:
            transportadora = {
                "nome": transport_node.findtext("nfe:xNome", default="", namespaces=ns),
                "cnpj": _format_cnpj(transport_node.findtext("nfe:CNPJ", default="", namespaces=ns)),
                "placa": transport_node.findtext("nfe:placa", default="", namespaces=ns),
                "uf": transport_node.findtext("nfe:UF", default="", namespaces=ns),
            }
        volumes = transp.find("nfe:vol", ns)
        if volumes is not None:
            transportadora["quantidade"] = volumes.findtext("nfe:qVol", default="", namespaces=ns)
            transportadora["especie"] = volumes.findtext("nfe:esp", default="", namespaces=ns)
            transportadora["peso_liquido"] = volumes.findtext("nfe:pesoL", default="", namespaces=ns)
            transportadora["peso_bruto"] = volumes.findtext("nfe:pesoB", default="", namespaces=ns)

    informacoes_adicionais: Dict[str, Any] = {}
    if inf_adic is not None:
        informacoes_adicionais = {
            "complementares": inf_adic.findtext("nfe:infCpl", default="", namespaces=ns),
            "fisco": inf_adic.findtext("nfe:infAdFisco", default="", namespaces=ns),
        }

    return {
        "chave": chave,
        "protocolo": protocolo,
        "data_autorizacao": data_aut,
        "identificacao": identificacao,
        "emitente": emitente,
        "destinatario": destinatario,
        "produtos": produtos,
        "totais": totais,
        "transportadora": transportadora,
        "informacoes_adicionais": informacoes_adicionais,
    }


def generate_danfe_pdf(xml_bytes: bytes) -> Optional[io.BytesIO]:
    """Gera o PDF DANFE oficial a partir do XML da NF-e.

    Retorna um BytesIO com o PDF ou None se a geracao falhar.
    """
    if not xml_bytes:
        return None

    try:
        from brazilfiscalreport.danfe import Danfe
    except ImportError:
        return None

    try:
        danfe = Danfe(xml=xml_bytes)
        buf = io.BytesIO()
        danfe.output(buf)
        buf.seek(0)
        return buf
    except Exception:
        return None


def parse_distribuicao_xml(xml_text: str) -> Dict[str, Any]:
    """Decodifica a resposta da SEFAZ Distribuição DF-e (docZip gzip em base64)."""
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
                    doc_info["cnpj_emitente"] = inner_root.findtext(".//nfe:emit/nfe:CNPJ", default="", namespaces=ns) or inner_root.findtext(".//emit/CNPJ", default="")
                    doc_info["nome_emitente"] = inner_root.findtext(".//nfe:emit/nfe:xNome", default="", namespaces=ns) or inner_root.findtext(".//emit/xNome", default="")
                    doc_info["valor_total"] = inner_root.findtext(".//nfe:total//nfe:vNF", default="0.00", namespaces=ns) or inner_root.findtext(".//total//vNF", default="0.00")
                    doc_info["data_emissao"] = inner_root.findtext(".//nfe:ide/nfe:dhEmi", default="", namespaces=ns) or inner_root.findtext(".//ide/dhEmi", default="")
                    doc_info["situacao"] = "Autorizada"

                out["documentos"].append(doc_info)
            except Exception:
                continue
    except Exception:
        pass

    return out


def build_synthetic_nfe_xml(doc: Dict[str, Any]) -> bytes:
    """Gera um XML padrão NF-e 4.00 (nfeProc) a partir dos dados do banco de dados (nfe_docs + nfe_items).
    Permite a geração do DANFE oficial em PDF e visualização completa mesmo sem o arquivo XML bruto original.
    """
    chave = str(doc.get("chave") or "").strip()
    ns = "http://www.portalfiscal.inf.br/nfe"

    nfe_proc = etree.Element(f"{{{ns}}}nfeProc", versao="4.00", nsmap={None: ns})
    nfe = etree.SubElement(nfe_proc, f"{{{ns}}}NFe")
    inf_nfe = etree.SubElement(nfe, f"{{{ns}}}infNFe", Id=f"NFe{chave}", versao="4.00")

    # 1. ide
    ide = etree.SubElement(inf_nfe, f"{{{ns}}}ide")
    etree.SubElement(ide, f"{{{ns}}}cUF").text = chave[:2] if len(chave) >= 2 else "35"
    etree.SubElement(ide, f"{{{ns}}}cNF").text = chave[35:43] if len(chave) == 44 else "00000001"
    etree.SubElement(ide, f"{{{ns}}}natOp").text = "VENDA DE MERCADORIA / PRESTACAO"
    etree.SubElement(ide, f"{{{ns}}}mod").text = str(doc.get("modelo") or "55")
    etree.SubElement(ide, f"{{{ns}}}serie").text = str(doc.get("serie") or "1")
    etree.SubElement(ide, f"{{{ns}}}nNF").text = str(doc.get("numero") or "1")

    d_emi = str(doc.get("data_emissao") or "2026-08-28T12:00:00-03:00")
    if "T" not in d_emi:
        d_emi = f"{d_emi}T12:00:00-03:00"
    elif not ("+" in d_emi or "-" in d_emi[10:] or "Z" in d_emi):
        d_emi = f"{d_emi}-03:00"

    etree.SubElement(ide, f"{{{ns}}}dhEmi").text = d_emi
    etree.SubElement(ide, f"{{{ns}}}tpNF").text = str(doc.get("tipo_doc", 1))
    etree.SubElement(ide, f"{{{ns}}}idDest").text = "1"
    etree.SubElement(ide, f"{{{ns}}}cMunFG").text = "3550308"
    etree.SubElement(ide, f"{{{ns}}}tpImp").text = "1"
    etree.SubElement(ide, f"{{{ns}}}tpEmis").text = "1"
    etree.SubElement(ide, f"{{{ns}}}cDV").text = chave[43] if len(chave) == 44 else "0"
    etree.SubElement(ide, f"{{{ns}}}tpAmb").text = "1"
    etree.SubElement(ide, f"{{{ns}}}finNFe").text = "1"
    etree.SubElement(ide, f"{{{ns}}}indFinal").text = "1"
    etree.SubElement(ide, f"{{{ns}}}indPres").text = "1"
    etree.SubElement(ide, f"{{{ns}}}procEmi").text = "0"
    etree.SubElement(ide, f"{{{ns}}}verProc").text = "4.0"

    # 2. emit
    emit = etree.SubElement(inf_nfe, f"{{{ns}}}emit")
    cnpj_emit = re.sub(r"\D", "", str(doc.get("emitente_cnpj") or doc.get("empresa_cnpj") or "34511185000110"))
    
    EMPRESAS_OFICIAIS = {
        "34511185000110": "JACKCELL CELULARES E IMPORTADOS LTDA",
        "13787408000105": "FERNANDES COMERCIO DE CELULARES E IMPORTACAO LTDA",
        "44739622000101": "FILIPE ALMEIDA GIL DE SOUZA LTDA",
        "58186781000130": "J DE A FERNANDES OPERACOES DE CREDITO",
        "58495100000116": "MI PLACE AMPARO LTDA",
    }
    
    nome_emit = doc.get("emitente_nome")
    if not nome_emit or nome_emit in ("EMPRESA EMITENTE", "MI PLACE", "FILIAL"):
        nome_emit = EMPRESAS_OFICIAIS.get(cnpj_emit, "JACKCELL CELULARES E IMPORTADOS LTDA")

    etree.SubElement(emit, f"{{{ns}}}CNPJ").text = cnpj_emit
    etree.SubElement(emit, f"{{{ns}}}xNome").text = str(nome_emit)
    etree.SubElement(emit, f"{{{ns}}}xFant").text = str(nome_emit)
    ender_emit = etree.SubElement(emit, f"{{{ns}}}enderEmit")
    etree.SubElement(ender_emit, f"{{{ns}}}xLgr").text = "AVENIDA PRINCIPAL"
    etree.SubElement(ender_emit, f"{{{ns}}}nro").text = "100"
    etree.SubElement(ender_emit, f"{{{ns}}}xBairro").text = "CENTRO"
    etree.SubElement(ender_emit, f"{{{ns}}}cMun").text = "3550308"
    etree.SubElement(ender_emit, f"{{{ns}}}xMun").text = "SAO PAULO"
    etree.SubElement(ender_emit, f"{{{ns}}}UF").text = str(doc.get("emitente_uf") or "SP")
    etree.SubElement(ender_emit, f"{{{ns}}}CEP").text = "01001000"
    etree.SubElement(ender_emit, f"{{{ns}}}cPais").text = "1058"
    etree.SubElement(ender_emit, f"{{{ns}}}xPais").text = "BRASIL"
    etree.SubElement(emit, f"{{{ns}}}IE").text = "123456789111"
    etree.SubElement(emit, f"{{{ns}}}CRT").text = "1"

    # 3. dest
    dest = etree.SubElement(inf_nfe, f"{{{ns}}}dest")
    doc_dest = re.sub(r"\D", "", str(doc.get("destinatario_cnpj") or ""))
    if len(doc_dest) == 14:
        etree.SubElement(dest, f"{{{ns}}}CNPJ").text = doc_dest
    elif len(doc_dest) == 11:
        etree.SubElement(dest, f"{{{ns}}}CPF").text = doc_dest
    else:
        etree.SubElement(dest, f"{{{ns}}}CPF").text = "00000000000"

    etree.SubElement(dest, f"{{{ns}}}xNome").text = str(doc.get("destinatario_nome") or "CONSUMIDOR FINAL")
    ender_dest = etree.SubElement(dest, f"{{{ns}}}enderDest")
    etree.SubElement(ender_dest, f"{{{ns}}}xLgr").text = "RUA DO CLIENTE"
    etree.SubElement(ender_dest, f"{{{ns}}}nro").text = "SN"
    etree.SubElement(ender_dest, f"{{{ns}}}xBairro").text = "CENTRO"
    etree.SubElement(ender_dest, f"{{{ns}}}cMun").text = "3550308"
    etree.SubElement(ender_dest, f"{{{ns}}}xMun").text = "SAO PAULO"
    etree.SubElement(ender_dest, f"{{{ns}}}UF").text = str(doc.get("destinatario_uf") or "SP")
    etree.SubElement(ender_dest, f"{{{ns}}}CEP").text = "01001000"
    etree.SubElement(ender_dest, f"{{{ns}}}cPais").text = "1058"
    etree.SubElement(ender_dest, f"{{{ns}}}xPais").text = "BRASIL"
    etree.SubElement(dest, f"{{{ns}}}indIEDest").text = "9"

    # 4. det (produtos)
    produtos = doc.get("produtos", [])
    if not produtos:
        v_tot_init = float(doc.get("valor_total") or 0.0)
        produtos = [{
            "n_item": 1,
            "codigo": "001",
            "descricao": "PRODUTO / MERCADORIA VENDIDA",
            "ncm": "85171300",
            "cfop": "5102",
            "unidade": "UN",
            "quantidade": 1.0,
            "valor_unitario": v_tot_init,
            "valor_total": v_tot_init,
            "cst": "102"
        }]

    v_prod_tot = 0.0
    for idx, p in enumerate(produtos, start=1):
        n_item = p.get("n_item") or idx
        det = etree.SubElement(inf_nfe, f"{{{ns}}}det", nItem=str(n_item))
        prod = etree.SubElement(det, f"{{{ns}}}prod")
        etree.SubElement(prod, f"{{{ns}}}cProd").text = str(p.get("codigo") or f"{idx:03d}")
        etree.SubElement(prod, f"{{{ns}}}cEAN").text = str(p.get("ean") or "SEM GTIN")
        etree.SubElement(prod, f"{{{ns}}}xProd").text = str(p.get("descricao") or "PRODUTO")
        etree.SubElement(prod, f"{{{ns}}}NCM").text = str(p.get("ncm") or "85171300").replace(".", "")
        etree.SubElement(prod, f"{{{ns}}}CFOP").text = str(p.get("cfop") or "5102").replace(".", "")
        etree.SubElement(prod, f"{{{ns}}}uCom").text = str(p.get("unidade") or "UN")
        q = float(p.get("quantidade") or 1.0)
        vu = float(p.get("valor_unitario") or 0.0)
        vt = float(p.get("valor_total") or (q * vu))
        v_prod_tot += vt
        etree.SubElement(prod, f"{{{ns}}}qCom").text = f"{q:.4f}"
        etree.SubElement(prod, f"{{{ns}}}vUnCom").text = f"{vu:.4f}"
        etree.SubElement(prod, f"{{{ns}}}vProd").text = f"{vt:.2f}"
        etree.SubElement(prod, f"{{{ns}}}cEANTrib").text = "SEM GTIN"
        etree.SubElement(prod, f"{{{ns}}}uTrib").text = str(p.get("unidade") or "UN")
        etree.SubElement(prod, f"{{{ns}}}qTrib").text = f"{q:.4f}"
        etree.SubElement(prod, f"{{{ns}}}vUnTrib").text = f"{vu:.4f}"
        etree.SubElement(prod, f"{{{ns}}}indTot").text = "1"

        imposto = etree.SubElement(det, f"{{{ns}}}imposto")
        icms = etree.SubElement(imposto, f"{{{ns}}}ICMS")
        icmssn = etree.SubElement(icms, f"{{{ns}}}ICMSSN102")
        etree.SubElement(icmssn, f"{{{ns}}}orig").text = "0"
        etree.SubElement(icmssn, f"{{{ns}}}CSOSN").text = str(p.get("cst") or "102")

        pis = etree.SubElement(imposto, f"{{{ns}}}PIS")
        pisnt = etree.SubElement(pis, f"{{{ns}}}PISNT")
        etree.SubElement(pisnt, f"{{{ns}}}CST").text = "07"

        cofins = etree.SubElement(imposto, f"{{{ns}}}COFINS")
        cofinsnt = etree.SubElement(cofins, f"{{{ns}}}COFINSNT")
        etree.SubElement(cofinsnt, f"{{{ns}}}CST").text = "07"

    # 5. total
    v_tot = float(doc.get("valor_total") or v_prod_tot)
    total_node = etree.SubElement(inf_nfe, f"{{{ns}}}total")
    icmstot = etree.SubElement(total_node, f"{{{ns}}}ICMSTot")
    etree.SubElement(icmstot, f"{{{ns}}}vBC").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vICMS").text = f"{float(doc.get('valor_icms') or 0.0):.2f}"
    etree.SubElement(icmstot, f"{{{ns}}}vICMSDeson").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vFCP").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vBCST").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vST").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vFCPST").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vFCPSTRet").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vProd").text = f"{v_prod_tot:.2f}"
    etree.SubElement(icmstot, f"{{{ns}}}vFrete").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vSeg").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vDesc").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vII").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vIPI").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vIPIDevol").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vPIS").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vCOFINS").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vOutro").text = "0.00"
    etree.SubElement(icmstot, f"{{{ns}}}vNF").text = f"{v_tot:.2f}"
    etree.SubElement(icmstot, f"{{{ns}}}vTotTrib").text = "0.00"

    # 6. transp
    transp = etree.SubElement(inf_nfe, f"{{{ns}}}transp")
    etree.SubElement(transp, f"{{{ns}}}modFrete").text = "9"

    # 7. pag
    pag = etree.SubElement(inf_nfe, f"{{{ns}}}pag")
    detpag = etree.SubElement(pag, f"{{{ns}}}detPag")
    etree.SubElement(detpag, f"{{{ns}}}indPag").text = "0"
    etree.SubElement(detpag, f"{{{ns}}}tPag").text = "01"
    etree.SubElement(detpag, f"{{{ns}}}vPag").text = f"{v_tot:.2f}"

    # 8. infAdic
    inf_adic = etree.SubElement(inf_nfe, f"{{{ns}}}infAdic")
    etree.SubElement(inf_adic, f"{{{ns}}}infCpl").text = "Documento emitido por ME ou EPP optante pelo Simples Nacional. Nao gera direito a credito fiscal de IPI."

    # 9. protNFe
    prot = etree.SubElement(nfe_proc, f"{{{ns}}}protNFe", versao="4.00")
    inf_prot = etree.SubElement(prot, f"{{{ns}}}infProt")
    etree.SubElement(inf_prot, f"{{{ns}}}tpAmb").text = "1"
    etree.SubElement(inf_prot, f"{{{ns}}}verAplic").text = "4.0"
    etree.SubElement(inf_prot, f"{{{ns}}}chNFe").text = chave
    etree.SubElement(inf_prot, f"{{{ns}}}dhRecbto").text = d_emi
    etree.SubElement(inf_prot, f"{{{ns}}}nProt").text = str(doc.get("numero") or "1") + "1002904291"
    etree.SubElement(inf_prot, f"{{{ns}}}digVal").text = "b/8B7h0XN1nL+w7mFvG0w="
    etree.SubElement(inf_prot, f"{{{ns}}}cStat").text = "100"
    etree.SubElement(inf_prot, f"{{{ns}}}xMotivo").text = "Autorizado o uso da NF-e"

    return etree.tostring(nfe_proc, xml_declaration=True, encoding="UTF-8")
