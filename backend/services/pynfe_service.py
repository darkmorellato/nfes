from typing import Dict, Any, Optional
from datetime import datetime
from backend.config import settings


def _get_con(uf: Optional[str] = None, homologacao: Optional[bool] = None):
    from pynfe.processamento.comunicacao import ComunicacaoSefaz
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    return ComunicacaoSefaz(uf, cert_path, cert_password, homologacao=homologacao)


UF_CODIGO_PARA_NOME = {
    "11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO",
    "21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA",
    "31":"MG","32":"ES","33":"RJ","35":"SP",
    "41":"PR","42":"SC","43":"RS",
    "50":"MS","51":"MT","52":"GO","53":"DF",
}


def uf_from_chave(chave: str) -> Optional[str]:
    """Extrai a UF dos 2 primeiros digitos da chave de acesso (codigo IBGE)."""
    if not chave:
        return None
    digits = "".join(c for c in chave if c.isdigit())
    if len(digits) < 2:
        return None
    return UF_CODIGO_PARA_NOME.get(digits[:2])


def _get_cert_path() -> str:
    from backend.services.cert_service import get_cert_path
    return get_cert_path()


def _get_cert_password() -> str:
    from backend.services.cert_service import get_cert_password
    return get_cert_password()


def status_servico(tipo: str = "nfe", uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.status_servico(tipo)
    return {"status_code": response.status_code, "body": response.text}


def consultar_nota(chave: str, modelo: str = "nfe", uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.consulta_nota(modelo, chave)
    return {"status_code": response.status_code, "body": response.text}


def consultar_recibo(numero: str, modelo: str = "nfe", uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.consulta_recibo(modelo, numero)
    return {"status_code": response.status_code, "body": response.text}


def consultar_distribuicao(
    cnpj: Optional[str] = None,
    cpf: Optional[str] = None,
    chave: Optional[str] = None,
    nsu: int = 0,
    consulta_nsu_especifico: bool = False,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.consulta_distribuicao(
        cnpj=cnpj, cpf=cpf, chave=chave, nsu=nsu, consulta_nsu_especifico=consulta_nsu_especifico
    )
    return {"status_code": response.status_code, "body": response.text}


def consultar_cadastro(documento: str, tipo: str = "CNPJ", modelo: str = "nfe", uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.consulta_cadastro(modelo, documento, tipo=tipo, uf=uf)
    return {"status_code": response.status_code, "body": response.text}


def autorizar_nfe(
    xml: str,
    id_lote: int = 1,
    ind_sinc: int = 1,
    contingencia: bool = False,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    con = _get_con(uf=uf, homologacao=homologacao)
    nota = etree.fromstring(xml.encode("utf-8"))
    status, result, *_ = con.autorizacao("nfe", nota, id_lote=id_lote, ind_sinc=ind_sinc, contingencia=contingencia)

    if status == 0:
        xml_result = etree.tostring(result, encoding="unicode")
        return {"status": "success", "status_code": 0, "xml": xml_result}
    else:
        return {"status": "error", "status_code": getattr(result, 'status_code', 500), "body": getattr(result, 'text', str(result)), "nota": xml}


def cancelar_nota(
    xml_evento: Optional[str] = None,
    id_lote: int = 1,
    modelo: str = "nfe",
    chave: Optional[str] = None,
    cnpj: Optional[str] = None,
    n_prot: Optional[str] = None,
    justificativa: str = "",
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    from pynfe.utils.flags import NAMESPACE_NFE, CODIGOS_ESTADOS
    from pynfe.processamento.assinatura import AssinaturaA1

    uf_resolved = (uf or (uf_from_chave(chave) if chave else None) or settings.DEFAULT_UF).upper()
    con = _get_con(uf=uf_resolved, homologacao=homologacao)
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    is_homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    if xml_evento:
        root = etree.fromstring(xml_evento.encode("utf-8"))
        evento_node = root.find(".//{http://www.portalfiscal.inf.br/nfe}evento") if "envEvento" in root.tag else root
        if evento_node.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is None:
            assinador = AssinaturaA1(cert_path, cert_password)
            evento_node = assinador.assinar(evento_node)
    else:
        if not chave or not cnpj:
            raise ValueError("Chave de acesso e CNPJ são obrigatórios para cancelamento.")
        cod_uf = CODIGOS_ESTADOS.get(uf_resolved, "35")
        clean_cnpj = "".join(c for c in cnpj if c.isdigit())
        clean_chave = "".join(c for c in chave if c.isdigit())

        evento_node = etree.Element("evento", versao="1.00", xmlns=NAMESPACE_NFE)
        inf_evento = etree.SubElement(evento_node, "infEvento", Id=f"ID110111{clean_chave}01")
        etree.SubElement(inf_evento, "cOrgao").text = str(cod_uf)
        etree.SubElement(inf_evento, "tpAmb").text = "2" if is_homolog else "1"
        if len(clean_cnpj) == 11:
            etree.SubElement(inf_evento, "CPF").text = clean_cnpj
        else:
            etree.SubElement(inf_evento, "CNPJ").text = clean_cnpj
        etree.SubElement(inf_evento, "chNFe").text = clean_chave
        etree.SubElement(inf_evento, "dhEvento").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
        etree.SubElement(inf_evento, "tpEvento").text = "110111"
        etree.SubElement(inf_evento, "nSeqEvento").text = "1"
        etree.SubElement(inf_evento, "verEvento").text = "1.00"
        det_evento = etree.SubElement(inf_evento, "detEvento", versao="1.00")
        etree.SubElement(det_evento, "descEvento").text = "Cancelamento"
        if n_prot:
            etree.SubElement(det_evento, "nProt").text = str(n_prot).strip()
        etree.SubElement(det_evento, "xJust").text = justificativa or "Cancelamento de NF-e solicitado pelo emitente"

        assinador = AssinaturaA1(cert_path, cert_password)
        evento_node = assinador.assinar(evento_node)

    response = con.evento(modelo, evento_node, id_lote=id_lote)
    return {"status_code": response.status_code, "body": response.text}


def carta_correcao(
    xml_evento: Optional[str] = None,
    id_lote: int = 1,
    modelo: str = "nfe",
    chave: Optional[str] = None,
    cnpj: Optional[str] = None,
    texto: Optional[str] = None,
    n_seq_evento: int = 1,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    from pynfe.utils.flags import NAMESPACE_NFE, CODIGOS_ESTADOS
    from pynfe.processamento.assinatura import AssinaturaA1

    uf_resolved = (uf or (uf_from_chave(chave) if chave else None) or settings.DEFAULT_UF).upper()
    con = _get_con(uf=uf_resolved, homologacao=homologacao)
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    is_homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    if xml_evento:
        root = etree.fromstring(xml_evento.encode("utf-8"))
        evento_node = root.find(".//{http://www.portalfiscal.inf.br/nfe}evento") if "envEvento" in root.tag else root
        if evento_node.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is None:
            assinador = AssinaturaA1(cert_path, cert_password)
            evento_node = assinador.assinar(evento_node)
    else:
        if not chave or not cnpj or not texto:
            raise ValueError("Chave de acesso, CNPJ e texto de correção são obrigatórios.")
        cod_uf = CODIGOS_ESTADOS.get(uf_resolved, "35")
        clean_cnpj = "".join(c for c in cnpj if c.isdigit())
        clean_chave = "".join(c for c in chave if c.isdigit())
        seq_str = str(n_seq_evento).zfill(2)

        evento_node = etree.Element("evento", versao="1.00", xmlns=NAMESPACE_NFE)
        inf_evento = etree.SubElement(evento_node, "infEvento", Id=f"ID110110{clean_chave}{seq_str}")
        etree.SubElement(inf_evento, "cOrgao").text = str(cod_uf)
        etree.SubElement(inf_evento, "tpAmb").text = "2" if is_homolog else "1"
        if len(clean_cnpj) == 11:
            etree.SubElement(inf_evento, "CPF").text = clean_cnpj
        else:
            etree.SubElement(inf_evento, "CNPJ").text = clean_cnpj
        etree.SubElement(inf_evento, "chNFe").text = clean_chave
        etree.SubElement(inf_evento, "dhEvento").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
        etree.SubElement(inf_evento, "tpEvento").text = "110110"
        etree.SubElement(inf_evento, "nSeqEvento").text = str(n_seq_evento)
        etree.SubElement(inf_evento, "verEvento").text = "1.00"
        det_evento = etree.SubElement(inf_evento, "detEvento", versao="1.00")
        etree.SubElement(det_evento, "descEvento").text = "Carta de Correcao"
        etree.SubElement(det_evento, "xCorrecao").text = texto
        etree.SubElement(det_evento, "xCondUso").text = (
            "A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, de 15 de dezembro de 1970 "
            "e pode ser utilizada para regularizacao de erro ocorrido na emissao de documento fiscal, desde que o erro nao "
            "esteja relacionado com: I - as variaveis que determinam o valor do imposto tais como: base de calculo, aliquota, "
            "diferenca de preco, quantidade, valor da operacao ou da prestacao; II - a correcao de dados cadastrais que "
            "implique mudanca do remetente ou do destinatario; III - a data de emissao ou de saida."
        )

        assinador = AssinaturaA1(cert_path, cert_password)
        evento_node = assinador.assinar(evento_node)

    response = con.evento(modelo, evento_node, id_lote=id_lote)
    return {"status_code": response.status_code, "body": response.text}


def inutilizar_numeracao(
    cnpj: str,
    numero_inicial: int,
    numero_final: int,
    justificativa: str = "",
    serie: str = "1",
    ano: Optional[int] = None,
    modelo: str = "nfe",
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    con = _get_con(uf=uf, homologacao=homologacao)
    response = con.inutilizacao(
        modelo, cnpj, numero_inicial, numero_final,
        justificativa=justificativa, ano=ano, serie=serie
    )
    return {"status_code": response.status_code, "body": response.text}


def manifestacao_destinatario(
    chave: str,
    cnpj: str,
    tipo_manifestacao: str,
    justificativa: str = "",
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    from pynfe.utils.flags import NAMESPACE_NFE
    from pynfe.processamento.assinatura import AssinaturaA1

    uf_resolved = (uf or uf_from_chave(chave) or settings.DEFAULT_UF).upper()
    con = _get_con(uf=uf_resolved, homologacao=homologacao)
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    is_homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    clean_cnpj = "".join(c for c in cnpj if c.isdigit())
    clean_chave = "".join(c for c in chave if c.isdigit())

    desc_map = {
        "210200": "Confirmacao da Operacao",
        "210210": "Ciencia da Emissao",
        "210220": "Desconhecimento da Operacao",
        "210240": "Operacao nao Realizada",
    }
    desc_evento = desc_map.get(tipo_manifestacao, "Operacao nao Realizada")

    evento = etree.Element("evento", versao="1.00", xmlns=NAMESPACE_NFE)
    inf_evento = etree.SubElement(evento, "infEvento", Id=f"ID{tipo_manifestacao}{clean_chave}01")
    etree.SubElement(inf_evento, "cOrgao").text = "91"
    etree.SubElement(inf_evento, "tpAmb").text = "2" if is_homolog else "1"
    if len(clean_cnpj) == 11:
        etree.SubElement(inf_evento, "CPF").text = clean_cnpj
    else:
        etree.SubElement(inf_evento, "CNPJ").text = clean_cnpj
    etree.SubElement(inf_evento, "chNFe").text = clean_chave
    etree.SubElement(inf_evento, "dhEvento").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
    etree.SubElement(inf_evento, "tpEvento").text = tipo_manifestacao
    etree.SubElement(inf_evento, "nSeqEvento").text = "1"
    etree.SubElement(inf_evento, "verEvento").text = "1.00"
    det_evento = etree.SubElement(inf_evento, "detEvento", versao="1.00")
    etree.SubElement(det_evento, "descEvento").text = desc_evento
    if tipo_manifestacao == "210240":
        etree.SubElement(det_evento, "xJust").text = justificativa or "Operacao comercial nao realizada pelo destinatario"

    assinador = AssinaturaA1(cert_path, cert_password)
    evento_assinado = assinador.assinar(evento)

    response = con.evento("nfe", evento_assinado, id_lote=1)
    return {"status_code": response.status_code, "body": response.text}


def autorizar_nfce(
    xml: str,
    id_lote: int = 1,
    ind_sinc: int = 1,
    contingencia: bool = False,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    con = _get_con(uf=uf, homologacao=homologacao)
    nota = etree.fromstring(xml.encode("utf-8"))
    status, result, *_ = con.autorizacao("nfce", nota, id_lote=id_lote, ind_sinc=ind_sinc, contingencia=contingencia)

    if status == 0:
        xml_result = etree.tostring(result, encoding="unicode")
        return {"status": "success", "status_code": 0, "xml": xml_result}
    else:
        return {"status": "error", "status_code": getattr(result, 'status_code', 500), "body": getattr(result, 'text', str(result)), "nota": xml}


def consultar_nota_nfce(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return consultar_nota(chave=chave, modelo="nfce", uf=uf, homologacao=homologacao)


def cancelar_nota_nfce(xml_evento: str, id_lote: int = 1, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return cancelar_nota(xml_evento=xml_evento, id_lote=id_lote, modelo="nfce", uf=uf, homologacao=homologacao)


def status_mdfe(uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    from pynfe.processamento.comunicacao import ComunicacaoMDFe
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    con = ComunicacaoMDFe(uf, cert_path, cert_password, homologacao=homologacao)
    response = con.status_servico()
    return {"status_code": response.status_code, "body": response.text}


def consultar_mdfe(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    from pynfe.processamento.comunicacao import ComunicacaoMDFe
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    con = ComunicacaoMDFe(uf, cert_path, cert_password, homologacao=homologacao)
    response = con.consulta(chave)
    return {"status_code": response.status_code, "body": response.text}


def autorizar_mdfe(
    xml: str,
    id_lote: int = 1,
    ind_sinc: int = 1,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    from lxml import etree
    from pynfe.processamento.comunicacao import ComunicacaoMDFe
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    con = ComunicacaoMDFe(uf, cert_path, cert_password, homologacao=homologacao)
    manifesto = etree.fromstring(xml.encode("utf-8"))
    status, result, *_ = con.autorizacao(manifesto, id_lote=id_lote, ind_sinc=ind_sinc)
    if status == 0:
        xml_result = etree.tostring(result, encoding="unicode")
        return {"status": "success", "status_code": 0, "xml": xml_result}
    else:
        return {"status": "error", "status_code": getattr(result, 'status_code', 500), "body": getattr(result, 'text', str(result))}


def cancelar_mdfe(xml_evento: str, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    from lxml import etree
    from pynfe.processamento.comunicacao import ComunicacaoMDFe
    uf = (uf or settings.DEFAULT_UF).upper()
    homologacao = homologacao if homologacao is not None else settings.HOMOLOGACAO
    cert_path = _get_cert_path()
    cert_password = _get_cert_password()
    con = ComunicacaoMDFe(uf, cert_path, cert_password, homologacao=homologacao)
    evento = etree.fromstring(xml_evento.encode("utf-8"))
    response = con.evento(evento)
    return {"status_code": response.status_code, "body": response.text}


def encerrar_mdfe(xml_evento: str, uf: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return cancelar_mdfe(xml_evento=xml_evento, uf=uf, homologacao=homologacao)


def status_nfse(autorizador: str = "GINFES", homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return {"info": f"Status NFS-e para {autorizador}"}


def consultar_nfse_numero(numero: str, autorizador: str = "GINFES", homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return {"info": f"Consulta NFS-e numero {numero} via {autorizador}"}


def consultar_nfse_rps(rps_numero: str, autorizador: str = "GINFES", homologacao: Optional[bool] = None) -> Dict[str, Any]:
    return {"info": f"Consulta NFS-e por RPS {rps_numero} via {autorizador}"}
