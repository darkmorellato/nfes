import os
import io
import zipfile
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from lxml import etree

from pynfe.entidades.cliente import Cliente
from pynfe.entidades.emitente import Emitente
from pynfe.entidades.notafiscal import (
    NotaFiscal,
    NotaFiscalTransporteVolume,
    NotaFiscalCobrancaDuplicata,
)
from pynfe.entidades.fonte_dados import _fonte_dados
from pynfe.utils.flags import CODIGO_BRASIL
from pynfe.processamento.serializacao import SerializacaoXML
from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.processamento.comunicacao import ComunicacaoSefaz

from backend.database import (
    get_db_connection,
    get_certificate_record,
    list_certificates_db,
    save_nfe_doc,
    save_nfe_event,
    save_cliente,
    get_next_nfe_number,
    reservar_proximo_numero,
    garante_numero_livre,
    cancelar_nfe_doc,
    get_nfe_detail,
    save_inutilizacao,
    XML_STORAGE_DIR,
)
from backend.database.nfe_docs import (
    _ler_retorno_do_xml,
    CSTAT_AUTORIZADO,
    CSTAT_DENEGADO,
    situacao_e_terminal,
)
from backend.services.danfe_service import parse_nfe_xml, generate_danfe_pdf
from backend.services.xsd_validator import validar_xml
from backend.utils import decode_xml
from backend.config import settings

logger = logging.getLogger(__name__)

# Timeout (segundos) para qualquer chamada ao webservice da SEFAZ.
# Sem timeout a chamada bloqueante dentro de ``async def`` congela a API inteira.
SEFAZ_TIMEOUT = float(os.environ.get("SEFAZ_TIMEOUT", "30"))

# cStat de lote (nível retEnviNFe) e de nota (nível infProt)
CSTAT_LOTE_PROCESSADO = "104"
CSTAT_LOTE_RECEBIDO = "103"
CSTAT_LOTE_EM_PROCESSAMENTO = "105"

# ====================================================================
# Contingência (tpEmis)
# ====================================================================
# Tabela oficial do MOC NF-e (tag tpEmis do grupo B01).
TPEMIS_NORMAL = "1"
TPEMIS_CONTINGENCIA = {"2", "4", "5", "6", "7", "9"}

# O PyNFe decide a URL de contingência pela UF e ignora o código que escrevemos
# (``ComunicacaoSefaz._get_url(contingencia=True)``). Emitir com tpEmis 2/4/5
# mandaria o XML para a SEFAZ Virtual errada e a SEFAZ rejeitaria.
# Por isso só são aceitos os códigos de SVC coerentes com essa rota — e eles
# são derivados da UF automaticamente.
_SVC_SVAN = ("AC", "AL", "AP", "DF", "ES", "MG", "PA", "PB", "PI", "RJ",
             "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO")
_SVC_SVRS = ("AM", "BA", "CE", "GO", "MA", "MS", "MT", "PE", "PR")

_ROTULO_TPEMIS = {
    "1": "Emissão normal",
    "2": "Contingência FS-IA (formulário de segurança)",
    "4": "Contingência DPEC",
    "5": "Contingência FS-DA (formulário de segurança)",
    "6": "Contingência SVC-AN (SEFAZ Virtual do Ambiente Nacional)",
    "7": "Contingência SVC-RS (SEFAZ Virtual do RS)",
    "9": "Contingência offline da NFC-e",
}


def tp_emis_svc_da_uf(uf: str) -> str:
    """
    Código tpEmis do SVC que atende esta UF, seguindo a mesma rota do PyNFe.

    * lista ``contingencia_svan`` → **6** (SVC-AN)
    * lista ``contingencia_svrs`` → **7** (SVC-RS)
    * vazio quando a UF não tem SVC mapeada nessa biblioteca
    """
    uf = (uf or "").upper()
    if uf in _SVC_SVAN:
        return "6"
    if uf in _SVC_SVRS:
        return "7"
    return ""


def resolver_tp_emis(payload: Dict[str, Any], uf_emitente: str) -> Tuple[str, Optional[str]]:
    """
    Resolve e valida o ``tpEmis`` da emissão.

    Dois formatos são aceitos:

    * ``contingencia: true`` → código derivado automaticamente da UF;
    * ``tp_emis: 6|7`` → código explícito, conferido contra a UF.

    Retorna ``(tp_emis, justificativa_de_contingencia)``; a justificativa é
    ``None`` quando a emissão é normal. Qualquer incoerência levanta
    ``ValueError`` **antes** de a numeração ser reservada e **antes** de
    qualquer chamada à SEFAZ.
    """
    tp_informado = payload.get("tp_emis")
    flag_contingencia = bool(payload.get("contingencia"))

    if tp_informado in (None, ""):
        if not flag_contingencia:
            return TPEMIS_NORMAL, None
        # Pediu contingência sem informar o código: deriva da UF.
        tp_emis = tp_emis_svc_da_uf(uf_emitente)
        if not tp_emis:
            raise ValueError(
                f"A UF {uf_emitente.upper()} não tem contingência SVC mapeada pelo "
                "motor de emissão. Informe tp_emis explicitamente ou emita em modo normal."
            )
    else:
        tp_emis = str(tp_informado).strip()
        if tp_emis == TPEMIS_NORMAL:
            if flag_contingencia:
                raise ValueError(
                    "Contingência contraditória: tp_emis=1 (emissão normal) junto "
                    "com contingencia=true. Remova um dos dois."
                )
            return TPEMIS_NORMAL, None

        if tp_emis not in TPEMIS_CONTINGENCIA:
            raise ValueError(
                f"tp_emis '{tp_emis}' não consta na tabela oficial da NF-e "
                f"({', '.join(sorted(TPEMIS_CONTINGENCIA))})."
            )
        if tp_emis not in ("6", "7"):
            raise ValueError(
                f"tp_emis {tp_emis} ({_ROTULO_TPEMIS.get(tp_emis, '?')}) não é suportado: "
                "o motor roteia a contingência para a SEFAZ Virtual, então somente "
                "6 (SVC-AN) e 7 (SVC-RS) são coerentes com o endpoint utilizado."
            )
        esperado = tp_emis_svc_da_uf(uf_emitente)
        if esperado and tp_emis != esperado:
            raise ValueError(
                f"A UF {uf_emitente.upper()} é atendida por "
                f"{_ROTULO_TPEMIS[esperado]} — use tp_emis={esperado} "
                f"(o {tp_emis} enviaria o XML para a SEFAZ Virtual errada)."
            )

    justificativa = remover_acentos_sefaz(str(payload.get("contingencia_justificativa") or "").strip())
    if len(justificativa) < 15:
        raise ValueError(
            "A contingência exige justificativa de no mínimo 15 caracteres "
            "(campo contingencia_justificativa) — exigido pela SEFAZ em <xJust>."
        )
    if len(justificativa) > 255:
        raise ValueError("A justificativa de contingência aceita no máximo 255 caracteres.")

    return tp_emis, justificativa


def _situacao_de_cstat(c_stat: str, protocolo: str = "") -> str:
    """Máquina de estados fiscal a partir do cStat real devolvido pela SEFAZ."""
    if c_stat in CSTAT_AUTORIZADO:
        return "Autorizada"
    if c_stat in CSTAT_DENEGADO:
        return "Denegada"
    if c_stat in (CSTAT_LOTE_RECEBIDO, CSTAT_LOTE_EM_PROCESSAMENTO):
        return "Em Processamento"
    if c_stat:
        return f"Rejeitada ({c_stat})"
    return "Pendente"


def _extrair_icms_tot(xml: str) -> Dict[str, str]:
    """Lê os totais do grupo ``ICMSTot`` direto do XML assinado da NF-e."""
    resultado = {
        "vBC": "0.00", "vICMS": "0.00", "vProd": "0.00", "vFrete": "0.00",
        "vSeg": "0.00", "vDesc": "0.00", "vIPI": "0.00", "vPIS": "0.00",
        "vCOFINS": "0.00", "vOutro": "0.00", "vNF": "0.00",
    }
    if not xml:
        return resultado
    bloco = re.search(r"<ICMSTot>(.*?)</ICMSTot>", xml, re.S)
    if not bloco:
        return resultado
    for chave in resultado:
        m = re.search(rf"<{chave}>([^<]+)</{chave}>", bloco.group(1))
        if m and m.group(1).strip():
            resultado[chave] = m.group(1).strip()
    return resultado


def _serializar_prot_nfe(proc_elem) -> str:
    """
    Serializa o ``<protNFe>`` devolvido pela SEFAZ com namespace padrão canônico.

    O PyNFe monta o ``nfeProc`` usando ``xmlns`` como atributo literal, o que faz
    o lxml prefixar o grupo recebido da SEFAZ como ``<ns0:protNFe>``. Reconstruir
    apenas esse grupo devolve o formato usual de ``procNFe`` — o ``<NFe>`` assinado
    não é re-serializado, então a assinatura permanece intacta.
    """
    from pynfe.utils.flags import NAMESPACE_NFE

    nos = proc_elem.xpath(".//*[local-name()='protNFe']")
    if not nos:
        return ""
    prot = nos[0]
    novo = etree.Element("protNFe", nsmap={None: NAMESPACE_NFE}, versao=prot.get("versao") or "4.00")
    for filho in list(prot):
        novo.append(filho)
    return etree.tostring(novo, encoding="unicode")


def _montar_nfe_proc(xml_nfe_assinado: str, prot_xml: str) -> str:
    """Envolve o ``<NFe>`` assinado (bytes originais) no ``nfeProc`` com o protocolo."""
    from pynfe.utils.flags import NAMESPACE_NFE

    corpo_nfe = re.sub(r"<\?xml[^?]*\?>", "", xml_nfe_assinado or "").strip()
    if not corpo_nfe or not prot_xml:
        return ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<nfeProc xmlns="{NAMESPACE_NFE}" versao="4.00">\n'
        f"{corpo_nfe}\n{prot_xml}\n</nfeProc>"
    )


def _parse_retorno_autorizacao(resposta, xml_assinado_str: str = "") -> Dict[str, str]:
    """
    Converte o retorno de ``ComunicacaoSefaz.autorizacao()`` em dados estruturados.

    O PyNFe devolve **sempre uma tupla**:
      * ``(0, nfeProc)``  → autorizado (cStat 100/150), com o ``protNFe`` real da SEFAZ;
      * ``(1, response, nota)`` → qualquer outra situação (rejeição, lote, erro HTTP).

    Nunca inventamos protocolo, digVal ou verAplic: tudo vem do XML de resposta.
    """
    resultado: Dict[str, str] = {
        "c_stat": "",
        "motivo": "",
        "protocolo": "",
        "dh_recbto": "",
        "dig_val": "",
        "ver_aplic": "",
        "c_msg": "",
        "x_msg": "",
        "xml_proc": "",
        "erro": None,
    }

    try:
        codigo, primeiro, *demais = resposta
    except Exception:
        resultado["erro"] = "Formato de retorno inesperado do PyNFe (esperada uma tupla)."
        return resultado

    if codigo == 0 and primeiro is not None:
        # Autorizado: `primeiro` é o <nfeProc> montado com o protNFe real.
        proc_elem = primeiro
        retorno = _ler_retorno_do_xml(etree.tostring(proc_elem, encoding="unicode"))
        resultado.update({
            "c_stat": retorno.get("c_stat", ""),
            "motivo": retorno.get("x_motivo", ""),
            "protocolo": retorno.get("protocolo", ""),
            "dh_recbto": retorno.get("dh_recbto", ""),
            "dig_val": retorno.get("dig_val", ""),
            "ver_aplic": retorno.get("ver_aplic", ""),
        })
        if not resultado["c_stat"]:
            resultado["erro"] = "Resposta da SEFAZ sem infProt mesmo com status 0."
            return resultado
        # O <NFe> assinado é envolvido por concatenação de string: a assinatura
        # cobre apenas <infNFe>, então nenhum byte assinado é re-serializado.
        resultado["xml_proc"] = _montar_nfe_proc(xml_assinado_str, _serializar_prot_nfe(proc_elem))
        return resultado

    # Falha / rejeição: `primeiro` é o objeto Response do SOAP.
    response = primeiro
    corpo = getattr(response, "text", None) or getattr(response, "content", None) or ""
    if isinstance(corpo, bytes):
        corpo = corpo.decode("utf-8", errors="replace")
    status_http = getattr(response, "status_code", None)
    if status_http not in (None, 200):
        resultado["erro"] = f"HTTP {status_http} no webservice da SEFAZ"
        resultado["motivo"] = f"Falha de comunicação com a SEFAZ (HTTP {status_http})."
        return resultado

    try:
        raiz = etree.fromstring(corpo.encode("utf-8"))
    except Exception as exc:
        resultado["erro"] = f"Não foi possível interpretar a resposta da SEFAZ: {exc}"
        resultado["motivo"] = "Resposta da SEFAZ ilegível."
        return resultado

    def _acha(tag: str) -> str:
        nos = raiz.xpath(f"//*[local-name()='{tag}']")
        return (nos[0].text or "").strip() if nos else ""

    # 1) Nível de item: infProt (quando o lote foi processado)
    inf_prot = raiz.xpath("//*[local-name()='infProt']")
    if inf_prot:
        bloco = inf_prot[0]
        def _dentro(nome: str) -> str:
            nos = bloco.xpath(f".//*[local-name()='{nome}']")
            return (nos[0].text or "").strip() if nos else ""
        resultado["c_stat"] = _dentro("cStat")
        resultado["motivo"] = _dentro("xMotivo")
        resultado["protocolo"] = _dentro("nProt")
        resultado["dh_recbto"] = _dentro("dhRecbto")
        resultado["dig_val"] = _dentro("digVal")
        resultado["ver_aplic"] = _dentro("verAplic")

    # 2) Nível de lote: retEnviNFe (usado quando não há infProt ou cStat vazio)
    lote_cstat = _acha("cStat") if not resultado["c_stat"] else ""
    if not resultado["c_stat"] and lote_cstat:
        resultado["c_stat"] = lote_cstat
        resultado["motivo"] = _acha("xMotivo") or "Sem descrição retornada pela SEFAZ."
    resultado["c_msg"] = _acha("cMsg")
    resultado["x_msg"] = _acha("xMsg")

    # 3) Mensagem de erro SOAP (falha de transporte, certificado, etc.)
    fault = _acha("faultstring") or _acha("Message")
    if fault and not resultado["c_stat"]:
        resultado["erro"] = fault
        resultado["motivo"] = f"Erro de comunicação com a SEFAZ: {fault}"

    return resultado

# Meses em pt-BR (por extenso e abreviado) para rótulos de fechamento contábil.
_MESES_PT_BR = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
_MESES_PT_BR_ABREV = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


def _fmt_competencia_label(mes: int, ano: int, abrev: bool = False) -> str:
    """Formata a competência do fechamento contábil em pt-BR.

    Exemplo: _fmt_competencia_label(8, 2026)  → "Agosto/2026"
             _fmt_competencia_label(8, 2026, True) → "ago/2026"
    """
    if not (1 <= int(mes) <= 12):
        return f"{int(mes):02d}/{int(ano)}"
    nome = _MESES_PT_BR_ABREV[int(mes) - 1] if abrev else _MESES_PT_BR[int(mes) - 1]
    return f"{nome}/{int(ano)}"


import unicodedata
import re

# Tabela estimativa IBPT (Lei 12.741/2012) por prefixo de NCM
IBPT_ALIQUOTAS = {
    "8517": {"fed": Decimal("0.1345"), "est": Decimal("0.1800")}, # Smartphones e telecom
    "8504": {"fed": Decimal("0.1150"), "est": Decimal("0.1800")}, # Carregadores e fontes
    "8544": {"fed": Decimal("0.1080"), "est": Decimal("0.1800")}, # Cabos e condutores
    "8518": {"fed": Decimal("0.1250"), "est": Decimal("0.1800")}, # Fones e autofalantes
    "3926": {"fed": Decimal("0.1420"), "est": Decimal("0.1800")}, # Películas e capas plásticas
    "4202": {"fed": Decimal("0.1300"), "est": Decimal("0.1800")}, # Bolsas e estojos
}


def remover_acentos_sefaz(texto: str) -> str:
    """
    Remove acentos, quebras de linha e caracteres especiais proibidos pela SEFAZ / MOC 7.0,
    garantindo que o XML seja 100% válido contra os esquemas XSD da Receita Federal.
    """
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    sem_acento = sem_acento.replace("&", "E").replace("<", " ").replace(">", " ").replace('"', ' ').replace("'", " ")
    limpo = re.sub(r"[^\w\s\-\.\,\/\:\;\(\)\#\%\*\+\=\@]", " ", sem_acento)
    return re.sub(r"\s+", " ", limpo).strip().upper()


def validar_cpf(cpf: str) -> bool:
    """Valida o dígito verificador do CPF pelo algoritmo oficial da Receita Federal."""
    cpf = re.sub(r"\D", "", str(cpf))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    if int(cpf[9]) != d1:
        return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return int(cpf[10]) == d2


def validar_cnpj(cnpj: str) -> bool:
    """Valida o dígito verificador do CNPJ pelo algoritmo oficial da Receita Federal."""
    cnpj = re.sub(r"\D", "", str(cnpj))
    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    d1 = 0 if resto1 < 2 else 11 - resto1
    if int(cnpj[12]) != d1:
        return False
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto2 = soma2 % 11
    d2 = 0 if resto2 < 2 else 11 - resto2
    return int(cnpj[13]) == d2


def calcular_ibpt_ncm(ncm: str, valor: Decimal) -> Tuple[Decimal, Decimal]:
    """Calcula a estimativa de tributos Federais e Estaduais conforme a Lei 12.741/2012 (IBPT)."""
    prefix = str(ncm)[:4]
    aliq = IBPT_ALIQUOTAS.get(prefix, {"fed": Decimal("0.1200"), "est": Decimal("0.1800")})
    v_fed = (valor * aliq["fed"]).quantize(Decimal("0.01"))
    v_est = (valor * aliq["est"]).quantize(Decimal("0.01"))
    return v_fed, v_est


def emitir_nfe_profissional(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constrói, valida conforme a legislação brasileira, assina digitalmente com Certificado A1
    e transmite uma Nota Fiscal Eletrônica (Modelo 55 - Saída / Venda / Devolução) para a SEFAZ.
    """
    logger.info(f"[NFE EMISSAO] Iniciando emissão para CNPJ {payload.get('emitente_cnpj')} | destino={payload.get('destinatario', {}).get('razao_social')}")

    emit_cnpj_clean = "".join(c for c in str(payload.get("emitente_cnpj", "")) if c.isdigit())
    if not emit_cnpj_clean:
        raise ValueError("CNPJ da empresa emitente é obrigatório.")

    cert_rec = get_certificate_record(emit_cnpj_clean)
    if not cert_rec:
        certs = list_certificates_db()
        cert_rec = next((c for c in certs if c["cnpj"] == emit_cnpj_clean), None)

    if not cert_rec:
        raise ValueError(f"Certificado Digital A1 não encontrado para a empresa CNPJ {emit_cnpj_clean}.")

    # 1. Dados do Emitente
    emit_uf = (payload.get("emitente_uf") or cert_rec.get("uf") or "SP").upper()
    emit_municipio = (payload.get("emitente_municipio") or cert_rec.get("municipio") or "Piracicaba").strip()
    emit_cod_mun = str(payload.get("emitente_cod_municipio") or cert_rec.get("cod_municipio") or ("3538709" if "PIRACICABA" in emit_municipio.upper() else "3501905" if "AMPARO" in emit_municipio.upper() else "3550308")).strip()
    emit_ie = "".join(c for c in str(payload.get("emitente_ie") or cert_rec.get("ie") or "") if c.isdigit())
    if not emit_ie:
        raise ValueError(f"Inscrição Estadual (IE) da empresa emitente {cert_rec.get('razao_social')} não encontrada. Configure a IE no cadastro do certificado.")
    emit_logr = (payload.get("emitente_logradouro") or cert_rec.get("logradouro") or "Rua Principal").strip()
    emit_num = str(payload.get("emitente_numero") or cert_rec.get("numero") or "S/N").strip()
    emit_bairro = (payload.get("emitente_bairro") or cert_rec.get("bairro") or "Centro").strip()
    emit_cep = "".join(c for c in str(payload.get("emitente_cep") or cert_rec.get("cep") or "01001000") if c.isdigit())
    emit_crt = int(payload.get("regime_tributario") or cert_rec.get("crt") or 1)

    # ATENÇÃO: os atributos corretos do PyNFe são `cnpj` e
    # `codigo_de_regime_tributario`. Usar `numero_documento`/`regime_tributario`
    # criava atributos órfãos que o serializador ignora — resultando em XML sem
    # <CNPJ> em <emit> e com <CRT/> vazio (Rejeição 225) e em chave de acesso
    # com CNPJ zerado.
    pynfe_emitente = Emitente(
        razao_social=cert_rec["razao_social"],
        nome_fantasia=cert_rec.get("nome_fantasia") or cert_rec["razao_social"].split()[0],
        cnpj=emit_cnpj_clean,
        inscricao_estadual=emit_ie,
        codigo_de_regime_tributario=str(emit_crt), # 1=Simples Nacional, 2=Simples excesso, 3=Regime normal
        endereco_logradouro=emit_logr,
        endereco_numero=emit_num,
        endereco_bairro=emit_bairro,
        endereco_municipio=emit_municipio,
        endereco_cod_municipio=emit_cod_mun,
        endereco_uf=emit_uf,
        endereco_cep=emit_cep,
    )

    # 2. Dados do Destinatário (Cliente)
    dest_data = payload.get("destinatario", {})
    dest_doc_clean = "".join(c for c in str(dest_data.get("cpf_cnpj", "")) if c.isdigit())
    dest_nome = str(dest_data.get("razao_social", "")).strip()

    if not dest_doc_clean or not dest_nome:
        raise ValueError("CPF/CNPJ e Nome/Razão Social do Cliente destinatário são obrigatórios.")

    dest_tipo_doc = "CPF" if len(dest_doc_clean) == 11 else "CNPJ"
    if dest_tipo_doc == "CPF" and not validar_cpf(dest_doc_clean):
        raise ValueError(f"O CPF '{dest_doc_clean}' informado para o destinatário é inválido perante o algoritmo da Receita Federal.")
    elif dest_tipo_doc == "CNPJ" and not validar_cnpj(dest_doc_clean):
        raise ValueError(f"O CNPJ '{dest_doc_clean}' informado para o destinatário é inválido perante o algoritmo da Receita Federal.")

    dest_uf = (dest_data.get("uf") or emit_uf).upper()
    dest_municipio = dest_data.get("municipio") or "SAO PAULO"
    dest_cod_mun = dest_data.get("cod_municipio") or ("3550308" if dest_uf == "SP" else "3304557")
    dest_ind_ie = int(dest_data.get("indicador_ie", 9 if dest_tipo_doc == "CPF" else 1))

    dest_nome_limpo = remover_acentos_sefaz(dest_nome)
    dest_logr_limpo = remover_acentos_sefaz(dest_data.get("logradouro") or "Rua Principal")
    dest_bairro_limpo = remover_acentos_sefaz(dest_data.get("bairro") or "Centro")
    dest_mun_limpo = remover_acentos_sefaz(dest_municipio)

    pynfe_cliente = Cliente(
        razao_social=dest_nome_limpo,
        tipo_documento=dest_tipo_doc,
        numero_documento=dest_doc_clean,
        indicador_ie=dest_ind_ie,
        inscricao_estadual=dest_data.get("ie") if dest_ind_ie == 1 else "",
        email=dest_data.get("email", ""),
        endereco_telefone=dest_data.get("telefone", ""),
        endereco_logradouro=dest_logr_limpo,
        endereco_numero=dest_data.get("numero") or "1",
        endereco_complemento=remover_acentos_sefaz(dest_data.get("complemento", "")),
        endereco_bairro=dest_bairro_limpo,
        endereco_municipio=dest_mun_limpo,
        endereco_cod_municipio=dest_cod_mun,
        endereco_uf=dest_uf,
        endereco_cep=str(dest_data.get("cep", "01001000")).replace("-", ""),
        # O padrão da classe é "" e o serializador emite <cPais/> vazio →
        # viola o padrão [0-9]{1,4} e a SEFAZ responde cStat 225.
        endereco_pais=CODIGO_BRASIL,
    )

    # Salva cliente no banco para cadastros futuros se solicitado
    if payload.get("salvar_cliente", True):
        try:
            save_cliente({
                "cpf_cnpj": dest_doc_clean,
                "razao_social": dest_nome_limpo,
                "nome_fantasia": dest_data.get("nome_fantasia", ""),
                "ie": dest_data.get("ie", ""),
                "indicador_ie": dest_ind_ie,
                "email": dest_data.get("email", ""),
                "telefone": dest_data.get("telefone", ""),
                "cep": dest_data.get("cep", "01001000"),
                "logradouro": dest_logr_limpo,
                "numero": dest_data.get("numero", "1"),
                "complemento": dest_data.get("complemento", ""),
                "bairro": dest_bairro_limpo,
                "municipio": dest_mun_limpo,
                "cod_municipio": dest_cod_mun,
                "uf": dest_uf,
            })
        except Exception as e:
            print(f"Aviso ao auto-salvar cliente: {e}")

    # Contingência: validada ANTES de reservar numeração e ANTES de qualquer
    # chamada à SEFAZ — um tpEmis incoerente com a UF geraria XML que a SEFAZ
    # rejeita e ainda queimaria um número de nota.
    tp_emis, contingencia_just = resolver_tp_emis(payload, emit_uf)

    # 3. Número, Série e Identificação
    # Valida os itens ANTES de reservar numeração: um payload inválido não pode
    # queimar números da sequência fiscal da empresa.
    produtos_payload = payload.get("produtos") or []
    if not produtos_payload:
        raise ValueError("A NF-e deve conter ao menos 1 produto ou serviço.")
    for idx_item, item_bruto in enumerate(produtos_payload, start=1):
        try:
            q_item = Decimal(str(item_bruto.get("quantidade", 1)))
            vu_item = Decimal(str(item_bruto.get("valor_unitario", 0)))
        except Exception:
            raise ValueError(f"Item {idx_item}: quantidade ou valor unitário inválido.")
        if q_item <= 0:
            raise ValueError(f"Item {idx_item}: a quantidade deve ser maior que zero.")
        if vu_item < 0:
            raise ValueError(f"Item {idx_item}: o valor unitário não pode ser negativo.")

    serie = str(payload.get("serie", "1"))
    modelo_doc = str(payload.get("modelo", "55"))
    numero_informado = payload.get("numero")
    if numero_informado:
        # Número escolhido manualmente pelo operador: precisa estar livre e
        # reservar a sequência até ele, para que a próxima emissão não o reutilize.
        numero = int(numero_informado)
        garante_numero_livre(emit_cnpj_clean, serie, modelo_doc, numero)
    else:
        # Reserva atômica (BEGIN IMMEDIATE): emissões simultâneas nunca recebem
        # o mesmo número — previne a Rejeição 204 da SEFAZ.
        numero = reservar_proximo_numero(emit_cnpj_clean, serie, modelo_doc)

    natureza_op = remover_acentos_sefaz(str(payload.get("natureza_operacao") or "VENDA DE MERCADORIA"))
    is_interestadual = emit_uf != dest_uf
    ind_destino = 2 if is_interestadual else 1
    finalidade = int(payload.get("finalidade", 1)) # 1=Normal, 4=Devolução

    now = datetime.now()
    data_saida_val = now
    if payload.get("data_saida"):
        try:
            raw_dt = str(payload.get("data_saida")).strip()
            if len(raw_dt) == 10:
                data_saida_val = datetime.strptime(raw_dt, "%Y-%m-%d")
            elif len(raw_dt) == 16:
                data_saida_val = datetime.strptime(raw_dt, "%Y-%m-%dT%H:%M")
            else:
                data_saida_val = datetime.fromisoformat(raw_dt.replace("Z", "+00:00").split("+")[0])
        except Exception:
            data_saida_val = now

    # Informações Complementares e Lei da Transparência (IBPT)
    inf_cpl_base = payload.get("informacoes_complementares", "Documento emitido por ME ou EPP optante pelo Simples Nacional. Nao gera direito a credito fiscal de IPI.")

    # 4. Instanciação da Nota Fiscal
    # O PyNFe mantém um repositório global de entidades. Se uma emissão anterior
    # falhou após criar o NotaFiscal, ele fica residente e a próxima serialização
    # geraria <NFe> com DOIS <infNFe> (XML inválido) assinando a nota errada.
    _fonte_dados.limpar_dados()

    nota_fiscal = NotaFiscal(
        emitente=pynfe_emitente,
        cliente=pynfe_cliente,
        destinatario_remetente=pynfe_cliente,
        natureza_operacao=natureza_op,
        tipo_documento=1, # 1=Saída
        finalidade_emissao=finalidade,
        cliente_final=1 if dest_tipo_doc == "CPF" or dest_ind_ie == 9 else 0,
        indicador_destino=ind_destino,
        indicador_presencial=int(payload.get("indicador_presencial", 1)),
        numero_nf=str(numero),
        serie=str(serie),
        # tpEmis entra na chave de acesso (posição 34), por isso precisa estar
        # definido antes de qualquer serialização.
        forma_emissao=tp_emis,
        modelo="55",
        uf=emit_uf,
        municipio=emit_cod_mun,
        data_emissao=now,
        data_saida_entrada=data_saida_val,
        informacoes_complementares_interesse_contribuinte=remover_acentos_sefaz(inf_cpl_base),
    )
    nota_fiscal.cliente = pynfe_cliente

    # Adiciona NF-e Referenciada se informada (ex: Devoluções / Retornos / Garantias)
    chave_ref = "".join(c for c in str(payload.get("chave_referenciada") or payload.get("nfe_referenciada") or "") if c.isdigit())
    if chave_ref and len(chave_ref) == 44:
        try:
            nota_fiscal.adicionar_nota_fiscal_referenciada(chave_acesso=chave_ref)
        except Exception as e:
            print(f"Aviso ao referenciar NF-e: {e}")
    elif finalidade == 4:
        raise ValueError("A NF-e de Devolução (Finalidade 4) exige a Chave de 44 dígitos da NF-e de Origem Referenciada conforme a SEFAZ (Rejeição 321).")

    # 5. Adição dos Produtos e Cálculo dos Tributos (IBPT)
    tot_produtos = Decimal("0.00")
    tot_desconto = Decimal("0.00")
    tot_trib_fed = Decimal("0.00")
    tot_trib_est = Decimal("0.00")
    tot_trib_aprox = Decimal("0.00")   # soma exata dos vTotTrib dos itens
    itens_para_rateio: List[Tuple[Any, Decimal]] = []  # (objeto_do_item, valor_bruto)

    # CSOSN (Simples Nacional) e CST (Regime Normal) são mutuamente exclusivos.
    # Misturar os dois gera <ICMSSN102><CSOSN>000</CSOSN> → Rejeição 215/225.
    CSOSN_VALIDOS = {"101", "102", "103", "201", "202", "203", "300", "400", "500", "900"}
    CST_VALIDOS = {"00", "02", "10", "15", "20", "30", "40", "41", "50", "51", "60", "70", "90"}

    def _resolver_classificacao(valor_informado: str, idx: int) -> str:
        bruto = str(valor_informado or "").strip()
        if emit_crt == 1:
            if bruto in CSOSN_VALIDOS:
                return bruto
            if bruto:
                logger.warning(
                    "[NFE EMISSAO] Item %s: CSOSN '%s' inválido para o Simples Nacional — usando 102.",
                    idx, bruto,
                )
            return "102"
        # Regime Normal (CRT 2/3)
        cand = bruto[-2:] if (len(bruto) == 3 and bruto.startswith("0")) else bruto
        if cand in CST_VALIDOS:
            return cand
        if not bruto:
            raise ValueError(
                f"Item {idx}: a empresa não é optante pelo Simples Nacional (CRT {emit_crt}), "
                "portanto é obrigatório informar o CST de ICMS (2 dígitos) do item."
            )
        raise ValueError(
            f"Item {idx}: CST/CSOSN informado ('{bruto}') incompatível com o regime tributário "
            f"da empresa (CRT {emit_crt}). Informe um CST válido ({', '.join(sorted(CST_VALIDOS))})."
        )

    for idx, prod_raw in enumerate(produtos_payload, start=1):
        cod_prod = remover_acentos_sefaz(str(prod_raw.get("codigo") or f"PROD{idx}"))
        desc_prod = remover_acentos_sefaz(str(prod_raw.get("descricao") or "PRODUTO COMERCIAL").strip())
        ncm_prod = "".join(c for c in str(prod_raw.get("ncm") or "85171300") if c.isdigit())
        if len(ncm_prod) < 8:
            ncm_prod = ncm_prod.ljust(8, "0")
        elif len(ncm_prod) > 8:
            ncm_prod = ncm_prod[:8]

        unidade = remover_acentos_sefaz(str(prod_raw.get("unidade") or "UN"))
        qtd = Decimal(str(prod_raw.get("quantidade", 1)))
        v_unit = Decimal(str(prod_raw.get("valor_unitario", 0.0)))
        v_desc = Decimal(str(prod_raw.get("desconto", 0.0)))
        # vProd SEMPRE bruto (qCom × vUnCom); o desconto vai em <vDesc> à parte.
        # Embutir o desconto em vProd quebra a regra vProd = qCom × vUnCom − vDesc
        # e faz o <vDesc> total ficar sempre 0,00 no ICMSTot.
        v_bruto = qtd * v_unit
        if v_desc < 0:
            raise ValueError(f"Item {idx}: o desconto não pode ser negativo.")
        if v_desc > v_bruto:
            raise ValueError(
                f"Item {idx}: o desconto (R$ {v_desc:.2f}) é maior que o valor do item (R$ {v_bruto:.2f})."
            )
        v_tot = v_bruto - v_desc

        cfop_sugerido = "6102" if is_interestadual else "5102"
        if "DEVOLUCAO" in natureza_op or finalidade == 4:
            cfop_sugerido = "6202" if is_interestadual else "5202"

        cfop_inf = str(prod_raw.get("cfop") or cfop_sugerido).strip()
        # Validação cruzada CFOP x Destino Interestadual para prevenir Rejeição 525 da SEFAZ
        if is_interestadual and cfop_inf.startswith("5"):
            cfop = "6" + cfop_inf[1:]
        elif not is_interestadual and cfop_inf.startswith("6"):
            cfop = "5" + cfop_inf[1:]
        else:
            cfop = cfop_inf

        classificacao = _resolver_classificacao(prod_raw.get("csosn_cst") or "", idx)
        origem = int(prod_raw.get("origem", 0))

        # IBPT
        item_fed, item_est = calcular_ibpt_ncm(ncm_prod, v_tot)
        tot_trib_fed += item_fed
        tot_trib_est += item_est
        item_trib_tot = item_fed + item_est

        imei_prod = str(prod_raw.get("imei") or "").strip()
        if imei_prod:
            desc_prod = f"{desc_prod} [IMEI: {remover_acentos_sefaz(imei_prod)}]"

        kwargs_icms = (
            {"icms_csosn": classificacao, "icms_modalidade": classificacao}
            if emit_crt == 1
            else {"icms_csosn": "", "icms_modalidade": classificacao}
        )

        p_obj = nota_fiscal.adicionar_produto_servico(
            codigo=cod_prod,
            descricao=desc_prod,
            ncm=ncm_prod,
            cfop=cfop,
            unidade_comercial=unidade,
            quantidade_comercial=qtd,
            valor_unitario_comercial=v_unit,
            valor_total_bruto=v_bruto,
            desconto=v_desc,
            unidade_tributavel=unidade,
            quantidade_tributavel=qtd,
            valor_unitario_tributavel=v_unit,
            icms_origem=origem,
            **kwargs_icms,
        )
        p_obj.ind_total = 1
        p_obj.ean = "SEM GTIN"
        p_obj.ean_tributavel = "SEM GTIN"
        # Decimal (não float): o PyNFe grava com str(), e str(30.0) == "30.0"
        # violaria o padrão XSD de 2 casas decimais (Rejeição 225).
        p_obj.valor_tributos_aprox = item_trib_tot
        p_obj.pis_modalidade = "49"
        p_obj.cofins_modalidade = "49"
        p_obj.ipi_codigo_enquadramento = "999"
        p_obj.ipi_classe_enquadramento = "999"
        if imei_prod:
            p_obj.informacoes_adicionais = f"IMEI/Serial: {remover_acentos_sefaz(imei_prod)}"

        itens_para_rateio.append((p_obj, v_bruto))
        tot_produtos += v_bruto
        tot_desconto += v_desc
        tot_trib_aprox += item_trib_tot

    tot_frete = Decimal(str(payload.get("valor_frete", "0.00")))
    tot_seguro = Decimal(str(payload.get("valor_seguro", "0.00")))
    tot_outras = Decimal(str(payload.get("outras_despesas", "0.00")))
    for nome, valor in (("valor_frete", tot_frete), ("valor_seguro", tot_seguro), ("outras_despesas", tot_outras)):
        if valor < 0:
            raise ValueError(f"O campo {nome} não pode ser negativo.")
    tot_nota = tot_produtos - tot_desconto + tot_frete + tot_seguro + tot_outras
    if tot_nota <= 0:
        raise ValueError("O valor total da NF-e deve ser maior que zero.")

    # Rateia frete/seguro/outras despesas entre os itens (grupo infProd/vFrete, vSeg, vOutro).
    # O ICMSTot é a SOMA dos itens: sem isso vFrete/vSeg/vOutro ficam 0,00 e
    # vPag (que usa tot_nota) passa a divergir de vNF → Rejeições 865/866.
    def _ratear(valor_total: Decimal, rotulo: str) -> None:
        if valor_total == 0 or not itens_para_rateio:
            return
        base_total = sum((bruto for _, bruto in itens_para_rateio), Decimal("0.00"))
        if base_total <= 0:
            itens_para_rateio[0][0].__setattr__(rotulo, valor_total)
            return
        atribuido = Decimal("0.00")
        for pos, (obj, bruto) in enumerate(itens_para_rateio):
            if pos == len(itens_para_rateio) - 1:
                parte = valor_total - atribuido
            else:
                parte = (valor_total * bruto / base_total).quantize(Decimal("0.01"))
                if parte < 0:
                    parte = Decimal("0.00")
                atribuido += parte
            setattr(obj, rotulo, parte)

    _ratear(tot_frete, "total_frete")
    _ratear(tot_seguro, "total_seguro")
    _ratear(tot_outras, "outras_despesas_acessorias")

    # O PyNFe soma os totais no momento em que o item é INSERIDO; o rateio de
    # frete/seguro/outras acontece depois, portanto reaplicamos os acumuladores
    # no nível da nota. Sem isso o ICMSTot sairia com vFrete/vSeg/vOutro zerados
    # enquanto vPag usava o total cheio → Rejeições 865/866.
    nota_fiscal.totais_icms_total_produtos_e_servicos = tot_produtos
    nota_fiscal.totais_icms_total_desconto = tot_desconto
    nota_fiscal.totais_icms_total_frete = tot_frete
    nota_fiscal.totais_icms_total_seguro = tot_seguro
    nota_fiscal.totais_icms_outras_despesas_acessorias = tot_outras
    # Mesma fórmula usada pelo serializador do PyNFe para <vNF>
    nota_fiscal.totais_icms_total_nota = (
        nota_fiscal.totais_icms_total_produtos_e_servicos
        + nota_fiscal.totais_icms_st_total
        + nota_fiscal.totais_fcp_st
        + nota_fiscal.totais_icms_total_frete
        + nota_fiscal.totais_icms_total_seguro
        + nota_fiscal.totais_icms_outras_despesas_acessorias
        + nota_fiscal.totais_icms_total_ii
        + nota_fiscal.totais_icms_total_ipi
        + nota_fiscal.totais_icms_total_ipi_dev
        - nota_fiscal.totais_icms_total_desconto
        - nota_fiscal.totais_icms_desonerado
    )

    # Conferência cruzada: o vNF do XML tem de fechar exatamente com tot_nota,
    # que é o valor usado em vPag e nas duplicatas.
    v_nf_xml = (
        nota_fiscal.totais_icms_total_produtos_e_servicos
        + nota_fiscal.totais_icms_total_frete
        + nota_fiscal.totais_icms_total_seguro
        + nota_fiscal.totais_icms_outras_despesas_acessorias
        - nota_fiscal.totais_icms_total_desconto
        + nota_fiscal.totais_icms_st_total
        + nota_fiscal.totais_icms_total_ipi
        + nota_fiscal.totais_icms_total_ipi_dev
        - nota_fiscal.totais_icms_desonerado
    )
    if Decimal(f"{v_nf_xml:.2f}") != tot_nota:
        raise ValueError(
            f"Inconsistência de totais: vNF do XML (R$ {v_nf_xml:.2f}) difere do total "
            f"calculado (R$ {tot_nota:.2f}). Transmissão cancelada para evitar rejeição."
        )

    # vTotTrib (Lei 12.741/2012) do grupo ICMSTot: precisa ser exatamente a soma
    # dos vTotTrib dos itens — divergência gera Rejeição 685. Mantido como Decimal
    # porque o serializador usa "{:.2f}" / str() e float perderia as casas.
    nota_fiscal.totais_tributos_aproximado = tot_trib_aprox

    # Adiciona resumo IBPT no rodapé
    ibpt_texto = f" | Trib aprox R$: {tot_trib_fed:.2f} Federal e R$: {tot_trib_est:.2f} Estadual. Fonte: IBPT."
    nota_fiscal.informacoes_complementares_interesse_contribuinte = inf_cpl_base + ibpt_texto

    # 6. Transporte & Volumes (Grupo X)
    transp_data = payload.get("transporte", {})
    mod_frete = str(transp_data.get("modalidade_frete", payload.get("modalidade_frete", "9"))) # 9 = Sem Ocorrência
    nota_fiscal.transporte_modalidade_frete = mod_frete

    if mod_frete != "9":
        transp_nome = transp_data.get("transportadora_nome")
        transp_doc = "".join(c for c in str(transp_data.get("transportadora_cnpj_cpf", "")) if c.isdigit())
        if transp_nome and transp_doc:
            # O PyNFe serializa `transporte_transportadora` (grupo transp/transporta).
            # `transportadora` não é lido por nenhum serializador e seria descartado.
            nota_fiscal.transporte_transportadora = Cliente(
                razao_social=transp_nome,
                tipo_documento="CNPJ" if len(transp_doc) == 14 else "CPF",
                numero_documento=transp_doc,
                inscricao_estadual=transp_data.get("transportadora_ie", ""),
                endereco_logradouro=transp_data.get("transportadora_endereco", ""),
                endereco_municipio=transp_data.get("transportadora_municipio", ""),
                endereco_uf=transp_data.get("transportadora_uf", "SP"),
                endereco_pais=CODIGO_BRASIL,
            )

        if transp_data.get("placa_veiculo"):
            nota_fiscal.transporte_veiculo_placa = str(transp_data["placa_veiculo"]).replace("-", "").upper()
            nota_fiscal.transporte_veiculo_uf = (transp_data.get("uf_veiculo") or "SP").upper()

    # Volumes e pesos (grupo vol) são independentes da modalidade de frete:
    # sempre que houver volume informado, precisa ir para o XML.
    qtd_vol = int(transp_data.get("volumes_qtd") or 0)
    if qtd_vol > 0:
        vol_obj = NotaFiscalTransporteVolume(
            quantidade=qtd_vol,
            especie=str(transp_data.get("volumes_especie") or "VOLUMES").upper(),
            marca=str(transp_data.get("volumes_marca") or "").upper(),
            numeracao=str(transp_data.get("volumes_numeracao") or ""),
            peso_liquido=float(transp_data.get("peso_liquido") or 0.0),
            peso_bruto=float(transp_data.get("peso_bruto") or 0.0),
        )
        nota_fiscal.transporte_volumes = [vol_obj]

    # 7. Cobrança e Faturamento a Prazo (Grupo Y - Fatura & Duplicatas)
    cond_pag = payload.get("condicao_pagamento", "a_vista")
    parcelas_raw = payload.get("parcelas", [])

    if cond_pag == "a_prazo" and parcelas_raw:
        nota_fiscal.fatura_numero = str(numero)
        nota_fiscal.fatura_valor_original = float(tot_nota)
        nota_fiscal.fatura_valor_desconto = float(tot_desconto)
        nota_fiscal.fatura_valor_liquido = float(tot_nota)

        dups = []
        valores_declarados = []
        for p in parcelas_raw:
            dt_venc = p.get("vencimento")
            if isinstance(dt_venc, str):
                try:
                    dt_venc_obj = datetime.strptime(dt_venc.split()[0], "%Y-%m-%d")
                except Exception:
                    dt_venc_obj = now + timedelta(days=30)
            elif isinstance(dt_venc, (datetime, date)):
                dt_venc_obj = dt_venc
            else:
                dt_venc_obj = now + timedelta(days=30)

            valor_informado = p.get("valor")
            valores_declarados.append(
                None if valor_informado in (None, "") else Decimal(str(valor_informado))
            )
            dups.append(NotaFiscalCobrancaDuplicata(
                numero=str(p.get("numero", f"00{len(dups)+1}")),
                data_vencimento=dt_venc_obj,
                valor=0.0,  # recalculado abaixo para fechar com o vNF
            ))

        # A soma das duplicatas tem de fechar exatamente com vNF (Rejeição 866).
        # Valores não informados são distribuídos; a última parcela absorve
        # a diferença de arredondamento.
        declarados_validos = [v for v in valores_declarados if v is not None]
        if len(declarados_validos) == len(valores_declarados) and declarados_validos:
            soma_declarada = sum(declarados_validos, Decimal("0.00"))
            if soma_declarada != tot_nota:
                logger.warning(
                    "[NFE EMISSAO] Soma das parcelas (R$ %.2f) divergia de vNF (R$ %.2f) — "
                    "última parcela ajustada para fechar o total.",
                    soma_declarada, tot_nota,
                )
            valores_declarados[-1] += tot_nota - soma_declarada
            if valores_declarados[-1] <= 0:
                raise ValueError(
                    f"As parcelas informadas somam R$ {soma_declarada:.2f}, mas o total da NF-e "
                    f"é R$ {tot_nota:.2f}. Corrija as duplicatas antes de transmitir."
                )
        else:
            n = len(dups)
            fatia = (tot_nota / n).quantize(Decimal("0.01"))
            for i in range(n):
                valores_declarados[i] = fatia
            valores_declarados[-1] = tot_nota - fatia * (n - 1)

        for dup, valor in zip(dups, valores_declarados):
            dup.valor = float(valor)
        nota_fiscal.duplicatas = dups

    # 8. Formas de Pagamento (Grupo YA)
    tipo_pag = str(payload.get("forma_pagamento", "17")).strip()
    tipo_pag = tipo_pag.zfill(2) if tipo_pag.isdigit() else tipo_pag  # "3" → "03"
    cartao = payload.get("cartao") or {}
    tp_integra = str(cartao.get("tp_integra") or payload.get("tp_integra") or "").strip()

    pagamento_kwargs: Dict[str, Any] = {
        "t_pag": tipo_pag,
        "v_pag": float(tot_nota),
        "ind_pag": "1" if cond_pag == "a_prazo" else "0",
    }

    # Regra 391_YA04-10 (MOC / NT 2023.004): para tPag 03 (crédito), 04 (débito)
    # e 17 (PIX) o grupo <card> é obrigatório. Sem TEF integrado usa-se
    # tpIntegra=2 (POS não integrado), que dispensa CNPJ da credenciadora,
    # bandeira e código de autorização (regra 392 só aplica a tpIntegra=1).
    if tipo_pag in ("03", "04", "17"):
        if not tp_integra:
            tp_integra = "2"

        if tp_integra == "1":
            faltantes = [
                rotulo for campo, rotulo in (
                    ("cnpj", "CNPJ da credenciadora"),
                    ("bandeira", "bandeira do cartão (tBand)"),
                    ("aut", "código de autorização (cAut)"),
                )
                if not str(cartao.get(campo) or "").strip()
            ]
            if faltantes:
                raise ValueError(
                    f"Pagamento com integração de TEF (tpIntegra=1) exige: {', '.join(faltantes)}. "
                    "Preencha os dados da transação ou use tpIntegra=2 (POS não integrado)."
                )

        bandeira = str(cartao.get("bandeira") or "").strip()
        if bandeira.isdigit() and len(bandeira) == 1:
            bandeira = bandeira.zfill(2)

        pagamento_kwargs.update({
            "tp_integra": tp_integra,
            "cnpj": str(cartao.get("cnpj") or "").strip(),
            "t_band": bandeira,
            "c_aut": str(cartao.get("aut") or "").strip(),
        })

    nota_fiscal.adicionar_pagamento(**pagamento_kwargs)

    # 9. Serialização & Assinatura Digital A1
    homolog = bool(payload.get("homologacao", settings.HOMOLOGACAO))
    # `contingencia=` injeta <dhCont> e <xJust> no <ide> (exigidos quando tpEmis != 1)
    serializador = SerializacaoXML(
        _fonte_dados, homologacao=homolog, contingencia=contingencia_just
    )
    xml_tree = serializador.exportar(nota_fiscal)

    assinador = AssinaturaA1(cert_rec["path"], cert_rec["password"])
    xml_assinado_element = assinador.assinar(xml_tree)
    xml_assinado_str = etree.tostring(xml_assinado_element, encoding="utf-8").decode("utf-8")

    chave_acesso = nota_fiscal.identificador_unico.replace("NFe", "")
    if not chave_acesso or len(chave_acesso) != 44:
        raise ValueError(f"Chave de acesso inválida gerada pelo PyNFe: {chave_acesso!r}")

    # 9.5. Validação do leiaute XSD oficial ANTES de transmitir.
    # Erro local é gratuito; a mesma falha na SEFAZ custa cStat 215/225 e
    # desgasta a cota do certificado (rejeição 656 - consumo indevido).
    violacoes = validar_xml(xml_assinado_str, esperado="NFe")
    if violacoes:
        detalhes = "\n".join(f"  • {e}" for e in violacoes[:8])
        logger.error("[NFE EMISSAO] XML fora do leiaute XSD. Chave %s:\n%s", chave_acesso, detalhes)
        raise ValueError(
            "O XML da NF-e não corresponde ao leiaute oficial (validação XSD local). "
            "Nada foi transmitido à SEFAZ.\n" + detalhes
        )

    # 10. Transmissão para a SEFAZ
    # NADA é fabricado localmente: protocolo, digVal, verAplic, cStat e data de
    # recebimento vêm exclusivamente do webservice. Sem resposta da SEFAZ não
    # existe autorização — a nota nasce como "Pendente".
    status_sefaz = "Pendente"
    protocolo = ""
    motivo = "NF-e ainda não transmitida."
    c_stat = ""
    dh_recbto = ""
    dig_val = ""
    xml_proc_completo = ""       # só é preenchido quando a SEFAZ autoriza
    sefaz_error = None

    try:
        con = ComunicacaoSefaz(emit_uf, cert_rec["path"], cert_rec["password"], homologacao=homolog)
        # ATENÇÃO: o PyNFe devolve UMA TUPLA (código, resultado), nunca um
        # objeto HTTP. Tratar como Response fazia o retorno ser descartado e a
        # nota era gravada como "Autorizada" mesmo em rejeição.
        envio_resp = con.autorizacao(
            modelo="nfe",
            nota_fiscal=xml_assinado_element,
            id_lote=1,
            ind_sinc=1,
            timeout=SEFAZ_TIMEOUT,
            # Em contingência o endpoint muda (SVAN/SVRS) — o PyNFe decide pela UF.
            contingencia=tp_emis != TPEMIS_NORMAL,
        )
        retorno = _parse_retorno_autorizacao(envio_resp, xml_assinado_str)
        c_stat = retorno["c_stat"]
        motivo = retorno["motivo"] or "Sem descrição retornada pela SEFAZ."
        protocolo = retorno["protocolo"]
        dh_recbto = retorno["dh_recbto"]
        dig_val = retorno["dig_val"]
        sefaz_error = retorno["erro"]
        xml_proc_completo = retorno["xml_proc"]
        status_sefaz = _situacao_de_cstat(c_stat, protocolo)
    except Exception as sefaz_err:
        logger.exception("[NFE EMISSAO] Falha de transmissão SEFAZ para a chave %s", chave_acesso)
        from backend.services.tls_sefaz import mensagem_erro_tls
        erro_tls = mensagem_erro_tls(sefaz_err)
        sefaz_error = erro_tls or str(sefaz_err)
        motivo = erro_tls or f"Erro na transmissão SEFAZ: {sefaz_err}"
        c_stat = ""
        status_sefaz = "Pendente"
        xml_proc_completo = ""

    # Defesa em profundidade: só há autorização se a SEFAZ devolveu um nfeProc.
    autorizada = status_sefaz == "Autorizada" and bool(xml_proc_completo)
    if status_sefaz == "Autorizada" and not autorizada:
        status_sefaz = "Pendente"
        motivo = "Resposta interpretada como autorizada sem XML de protocolo — transmissão não confirmada."

    # 11. NÃO montamos nfeProc manualmente. Persiste-se byte a byte o retorno da
    # SEFAZ quando autorizada; caso contrário, guarda-se apenas o <NFe> assinado
    # (coluna xml_assinado) para retransmissão idempotente.
    if not xml_proc_completo:
        status_sefaz = "Pendente" if status_sefaz == "Autorizada" else status_sefaz
    elif not xml_proc_completo.lstrip().startswith("<?xml"):
        xml_proc_completo = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_proc_completo.lstrip()

    dh_emissao = now.isoformat()
    m_dhemi = re.search(r"<dhEmi>([^<]+)</dhEmi>", xml_assinado_str)
    if m_dhemi and m_dhemi.group(1).strip():
        dh_emissao = m_dhemi.group(1).strip()

    # Totais lidos do próprio XML (ICMSTot) — nunca chumbados como 0,00
    totais_do_xml = _extrair_icms_tot(xml_assinado_str)

    # 12. Gravação no banco (upsert). O XML oficial só vai para data/xmls/ quando
    # há protocolo real — save_nfe_doc escreve em disco apenas se xml_raw vier.
    doc_dict = {
        "chave": chave_acesso,
        "empresa_cnpj": emit_cnpj_clean,
        "numero": str(numero),
        "serie": serie,
        "modelo": "55",
        "tipo_doc": 1, # 1=Saída para Cliente
        "data_emissao": dh_emissao,
        "data_autorizacao": dh_recbto or "",
        "emitente": {
            "nome": cert_rec["razao_social"],
            "cnpj": emit_cnpj_clean,
            "uf": emit_uf,
            "municipio": emit_municipio,
            "endereco": {"uf": emit_uf, "municipio": emit_municipio},
        },
        "emitente_uf": emit_uf,
        "destinatario": {
            "nome": dest_nome,
            "cnpj": dest_doc_clean if dest_tipo_doc == "CNPJ" else "",
            "cpf": dest_doc_clean if dest_tipo_doc == "CPF" else "",
            "uf": dest_uf,
            "municipio": dest_municipio,
            "endereco": {"uf": dest_uf, "municipio": dest_municipio},
        },
        "destinatario_uf": dest_uf,
        "totais": {
            "v_nf": f"{tot_nota:.2f}",
            "v_icms": totais_do_xml.get("vICMS", "0.00"),
            "v_pis": totais_do_xml.get("vPIS", "0.00"),
            "v_cofins": totais_do_xml.get("vCOFINS", "0.00"),
            "v_ipi": totais_do_xml.get("vIPI", "0.00"),
        },
        "situacao": status_sefaz,
        "protocolo": protocolo,
        "c_stat": c_stat,
        "x_motivo": motivo,
        "tp_amb": 2 if homolog else 1,
        "tp_emis": int(tp_emis),
        "dh_recbto": dh_recbto,
        "xml_assinado": "" if xml_proc_completo else xml_assinado_str,
        "produtos": [
            {
                "n_item": i,
                "codigo": p.codigo,
                "descricao": p.descricao,
                "ncm": p.ncm,
                "cfop": p.cfop,
                "unidade": p.unidade_comercial,
                "quantidade": float(p.quantidade_comercial),
                "valor_unitario": float(p.valor_unitario_comercial),
                "valor_total": float(p.valor_total_bruto),
                "cst": getattr(p, "icms_modalidade", "") or "",
                "v_icms": float(getattr(p, "icms_valor", 0) or 0),
            } for i, p in enumerate(nota_fiscal.produtos_e_servicos, start=1)
        ]
    }

    try:
        saved = save_nfe_doc(doc_dict, xml_raw=xml_proc_completo or None, empresa_cnpj=emit_cnpj_clean)
    except Exception:
        logger.exception(
            "[NFE EMISSAO] EXCEÇÃO AO SALVAR no banco: chave=%s (número %s da série %s do CNPJ %s "
            "foi consumido — confira a numeração e a situação na SEFAZ)",
            chave_acesso, numero, serie, emit_cnpj_clean,
        )
        raise
    if not saved:
        logger.error(f"[NFE EMISSAO] FALHA AO SALVAR no banco: chave={chave_acesso} emit_cnpj={emit_cnpj_clean}")
        raise RuntimeError(f"Falha ao salvar NF-e no banco local (chave={chave_acesso}). Verifique os logs.")
    logger.info(
        "[NFE EMISSAO] Salvo: chave=%s nº=%s série=%s situação=%s cStat=%s protocolo=%s valor=%.2f",
        chave_acesso, numero, serie, status_sefaz, c_stat, protocolo or "-", float(tot_nota),
    )

    if sefaz_error:
        logger.error(f"[NFE EMISSAO] ERRO SEFAZ para chave {chave_acesso}: {sefaz_error} | cStat={c_stat} | motivo={motivo}")
    else:
        logger.info(f"[NFE EMISSAO] Retorno: chave={chave_acesso} | cStat={c_stat or '-'} | protocolo={protocolo or '-'} | {status_sefaz}")

    # 13. DANFE em disco somente para nota COM protocolo real da SEFAZ.
    # Emitir DANFE de nota não autorizada produziria documento sem validade fiscal.
    pdf_gerado = False
    if autorizada:
        try:
            pdf_io = generate_danfe_pdf(xml_proc_completo.encode("utf-8"))
            if pdf_io:
                pdf_dir = os.path.join(settings.DATA_DIR, "danfe_pdfs")
                os.makedirs(pdf_dir, exist_ok=True)
                with open(os.path.join(pdf_dir, f"{chave_acesso}.pdf"), "wb") as f_pdf:
                    f_pdf.write(pdf_io.getvalue())
                pdf_gerado = True
        except Exception:
            logger.exception("[NFE EMISSAO] Falha ao gerar DANFE PDF da chave %s", chave_acesso)

    return {
        # `success` só é verdadeiro com autorização real da SEFAZ.
        "success": autorizada,
        "autorizada": autorizada,
        "denegada": status_sefaz == "Denegada",
        "situacao": status_sefaz,
        "chave": chave_acesso,
        "numero": numero,
        "serie": serie,
        "protocolo": protocolo,
        "c_stat": c_stat,
        "motivo": motivo,
        "x_motivo": motivo,
        "detail": motivo,          # lido pelo front na tela de rejeição
        "error": motivo if not autorizada else None,
        "dh_recbto": dh_recbto,
        "dig_val": dig_val,
        "emitente": cert_rec["razao_social"],
        "emitente_cnpj": emit_cnpj_clean,
        "destinatario": dest_nome,
        "destinatario_doc": dest_doc_clean,
        "valor_total": float(tot_nota),
        "data_emissao": dh_emissao,
        "ambiente": "Homologação" if homolog else "Produção",
        "xml_gerado": bool(xml_proc_completo),
        "has_xml": 1 if xml_proc_completo else 0,
        "pdf_gerado": pdf_gerado,
        "tp_emis": int(tp_emis),
        "contingencia": tp_emis != TPEMIS_NORMAL,
        "sefaz_error": sefaz_error,
    }


# ====================================================================
# EVENTOS FISCAIS (cancelamento 110111, CC-e 110110) e Inutilização 404/405
# Tudo é TRANSMITIDO à SEFAZ. Nenhum protocolo é fabricado localmente.
# ====================================================================

def _extrair_retorno_consulta(xml_texto) -> Dict[str, str]:
    """Lê o retorno de ``consulta_nota`` (``retConsSitNFe``).

    ``cStat``/``xMotivo`` ficam no nível raiz da resposta; o protocolo vem em
    ``protNFe/infProt/nProt`` (só existe quando a nota está na base da SEFAZ).
    """
    out = {"c_stat": "", "motivo": "", "protocolo": "", "erro": ""}
    if not xml_texto:
        out["erro"] = "Resposta vazia do webservice da SEFAZ."
        return out
    try:
        bruto = xml_texto if not isinstance(xml_texto, str) else xml_texto.encode("utf-8")
        raiz = etree.fromstring(bruto)
    except Exception as exc:
        out["erro"] = f"Resposta da SEFAZ ilegível: {exc}"
        return out

    # cStat de nível de serviço (fora de infProt/infEvento)
    candidatos = raiz.xpath(
        "//*[local-name()='retConsSitNFe' or local-name()='retConsStatServ']"
        "/*[local-name()='cStat']"
    )
    if not candidatos:
        candidatos = raiz.xpath("//*[local-name()='cStat']")
    if candidatos:
        out["c_stat"] = (candidatos[0].text or "").strip()

    motivos = raiz.xpath(
        "//*[local-name()='retConsSitNFe' or local-name()='retConsStatServ']"
        "/*[local-name()='xMotivo']"
    )
    if motivos:
        out["motivo"] = (motivos[0].text or "").strip()

    prots = raiz.xpath("//*[local-name()='protNFe']//*[local-name()='nProt']")
    if prots:
        out["protocolo"] = (prots[0].text or "").strip()

    if not out["c_stat"]:
        fault = raiz.xpath("//*[local-name()='faultstring']/text()")
        out["erro"] = fault[0].strip() if fault else "Retorno da SEFAZ sem cStat."
    return out


def _extrair_infret(xml_texto) -> Dict[str, str]:
    """Lê ``cStat``/``xMotivo``/``nProt`` do retorno de eventos e inutilização.

    Aceita ``<retEnviEvento><retEvento><infEvento>`` e ``<retInutNFe><infInut>``.
    """
    out = {"c_stat": "", "motivo": "", "protocolo": "", "dh_reg": "", "erro": ""}
    if not xml_texto:
        out["erro"] = "Resposta vazia do webservice da SEFAZ."
        return out
    try:
        bruto = xml_texto if not isinstance(xml_texto, str) else xml_texto.encode("utf-8")
        raiz = etree.fromstring(bruto)
    except Exception as exc:
        out["erro"] = f"Resposta da SEFAZ ilegível: {exc}"
        return out

    nos = raiz.xpath("//*[local-name()='infEvento' or local-name()='infInut']")
    if not nos:
        fault = raiz.xpath("//*[local-name()='faultstring']/text()")
        out["erro"] = fault[0].strip() if fault else "Resposta sem infEvento/infInut."
        return out

    bloco = nos[0]

    def _g(nome: str) -> str:
        achou = bloco.xpath(f".//*[local-name()='{nome}']")
        return (achou[0].text or "").strip() if achou else ""

    out["c_stat"] = _g("cStat")
    out["motivo"] = _g("xMotivo")
    out["protocolo"] = _g("nProt")
    out["dh_reg"] = _g("dhRegEvento") or _g("dhRecbto")
    if not out["c_stat"]:
        # Sem cStat não há como decidir — trate como falha de comunicação.
        out["erro"] = "Retorno da SEFAZ sem cStat."
    return out


def _montar_evento(
    tp_evento: str,
    chave: str,
    cnpj: str,
    uf: str,
    homolog: bool,
    det_campos: Dict[str, str],
    n_seq: int = 1,
    desc_evento: str = "",
    x_cond_uso: Optional[str] = None,
):
    """Monta e assina um evento NF-e (cancelamento, CC-e, manifestação)."""
    from pynfe.utils.flags import CODIGOS_ESTADOS, NAMESPACE_NFE

    clean_chave = "".join(c for c in chave if c.isdigit())
    clean_cnpj = "".join(c for c in cnpj if c.isdigit())
    cod_uf = CODIGOS_ESTADOS.get(str(uf).upper(), "35")

    evento = etree.Element("evento", versao="1.00", xmlns=NAMESPACE_NFE)
    inf_evento = etree.SubElement(
        evento, "infEvento", Id=f"ID{tp_evento}{clean_chave}{int(n_seq):02d}"
    )
    etree.SubElement(inf_evento, "cOrgao").text = str(cod_uf)
    etree.SubElement(inf_evento, "tpAmb").text = "2" if homolog else "1"
    if len(clean_cnpj) == 11:
        etree.SubElement(inf_evento, "CPF").text = clean_cnpj
    else:
        etree.SubElement(inf_evento, "CNPJ").text = clean_cnpj
    etree.SubElement(inf_evento, "chNFe").text = clean_chave
    etree.SubElement(inf_evento, "dhEvento").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
    etree.SubElement(inf_evento, "tpEvento").text = str(tp_evento)
    etree.SubElement(inf_evento, "nSeqEvento").text = str(int(n_seq))
    etree.SubElement(inf_evento, "verEvento").text = "1.00"

    det_evento = etree.SubElement(inf_evento, "detEvento", versao="1.00")
    etree.SubElement(det_evento, "descEvento").text = desc_evento
    if x_cond_uso:
        etree.SubElement(det_evento, "xCondUso").text = x_cond_uso
    for tag, valor in det_campos.items():
        if valor not in (None, ""):
            etree.SubElement(det_evento, tag).text = str(valor)

    return evento


def _transmitir_evento(cert_rec: Dict[str, Any], uf: str, homolog: bool, evento_assinado, modelo: str = "nfe") -> Dict[str, str]:
    con = ComunicacaoSefaz(uf, cert_rec["path"], cert_rec["password"], homologacao=homolog)
    resp = con.evento(modelo, evento_assinado, id_lote=1)
    corpo = getattr(resp, "text", "") or ""
    status_http = getattr(resp, "status_code", None)
    if status_http not in (None, 200):
        return {"c_stat": "", "motivo": "", "protocolo": "", "dh_reg": "",
                "erro": f"HTTP {status_http} no webservice de eventos da SEFAZ."}
    return _extrair_infret(corpo)


def cancelar_nfe_profissional(chave: str, justificativa: str, protocolo: Optional[str] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    """
    Cancela uma NF-e de saída perante a SEFAZ (Evento 110111) e atualiza o banco.

    A justificativa deve conter de 15 a 255 caracteres (MOC 7.0).
    O banco só é alterado quando a SEFAZ confirma com cStat 135.
    """
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    if len(chave_clean) != 44:
        raise ValueError("Chave de acesso inválida (deve conter 44 dígitos).")

    just_limpa = remover_acentos_sefaz(str(justificativa).strip())
    if len(just_limpa) < 15:
        raise ValueError("A justificativa de cancelamento deve conter no mínimo 15 caracteres.")
    if len(just_limpa) > 255:
        raise ValueError("A justificativa de cancelamento deve conter no máximo 255 caracteres.")

    doc = get_nfe_detail(chave_clean)
    if not doc:
        raise ValueError(f"NF-e com chave {chave_clean} não encontrada no banco de dados.")

    situacao_atual = str(doc.get("situacao") or "")
    if situacao_atual.startswith("Cancelada"):
        return {
            "success": False, "ja_executado": True, "chave": chave_clean,
            "c_stat": "", "motivo": f"NF-e já consta como cancelada ({situacao_atual}).",
            "detail": f"NF-e já consta como cancelada ({situacao_atual}).",
            "situacao": situacao_atual,
        }
    if not situacao_atual.startswith("Autorizada"):
        msg = (
            f"Somente NF-e AUTORIZADA pode ser cancelada. Esta nota está como "
            f"'{situacao_atual or 'desconhecida'}'."
        )
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": msg,
                "detail": msg, "situacao": situacao_atual}

    emit_cnpj = doc.get("emitente_cnpj") or chave_clean[6:20]
    cert_rec = get_certificate_record(emit_cnpj)
    if not cert_rec:
        raise ValueError(f"Certificado A1 não encontrado para o CNPJ {emit_cnpj}.")

    prot_aut = str(protocolo or doc.get("protocolo") or "")
    if not prot_aut:
        msg = (
            "A NF-e não possui protocolo de autorização registrado localmente. "
            "Consulte a situação na SEFAZ antes de cancelar."
        )
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": msg,
                "detail": msg, "situacao": situacao_atual}

    homolog = homologacao if homologacao is not None else _homolog_do_documento(doc)
    uf = _uf_do_documento(doc, chave_clean)

    evento = _montar_evento(
        tp_evento="110111",
        chave=chave_clean,
        cnpj=emit_cnpj,
        uf=uf,
        homolog=homolog,
        det_campos={"nProt": prot_aut, "xJust": just_limpa},
        n_seq=1,
        desc_evento="Cancelamento",
    )

    from pynfe.processamento.assinatura import AssinaturaA1
    try:
        evento_assinado = AssinaturaA1(cert_rec["path"], cert_rec["password"]).assinar(evento)
    except Exception:
        logger.exception("[CANCELAMENTO] Falha ao assinar o evento da chave %s", chave_clean)
        raise ValueError("Falha ao assinar o evento de cancelamento com o certificado A1.")

    try:
        retorno = _transmitir_evento(cert_rec, uf, homolog, evento_assinado)
    except Exception as exc:
        logger.exception("[CANCELAMENTO] Falha de comunicação SEFAZ para a chave %s", chave_clean)
        msg = f"Falha de comunicação com a SEFAZ: {exc}"
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": msg,
                "detail": msg, "situacao": situacao_atual}

    c_stat = retorno["c_stat"]
    motivo = retorno["motivo"] or retorno["erro"] or "Sem retorno da SEFAZ."
    homologado = c_stat in ("135", "136")   # 135=evento registrado, 136=evento registrado com advertência

    if retorno["erro"] and not c_stat:
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": retorno["erro"],
                "detail": retorno["erro"], "situacao": situacao_atual}

    if not homologado:
        msg = f"cStat {c_stat}: {motivo}"
        logger.warning("[CANCELAMENTO] Rejeitado para a chave %s — %s", chave_clean, msg)
        return {"success": False, "chave": chave_clean, "c_stat": c_stat, "motivo": msg,
                "detail": msg, "situacao": situacao_atual, "protocolo_evento": retorno["protocolo"]}

    # Só aqui o banco é alterado — o cancelamento foi aceito pela SEFAZ.
    cancelar_nfe_doc(chave_clean, retorno["protocolo"], just_limpa)
    save_nfe_event({
        "chave": chave_clean,
        "tipo_evento": "110111",
        "desc_evento": "Cancelamento de NF-e",
        "n_seq": 1,
        "dh_evento": retorno["dh_reg"] or datetime.now().isoformat(),
        "protocolo": retorno["protocolo"],
        "c_stat": c_stat,
        "x_motivo": motivo,
    })

    return {
        "success": True,
        "chave": chave_clean,
        "protocolo": retorno["protocolo"],
        "protocolo_autorizacao": prot_aut,
        "c_stat": c_stat,
        "motivo": motivo,
        "x_motivo": motivo,
        "detail": motivo,
        "justificativa": just_limpa,
        "data_cancelamento": retorno["dh_reg"] or datetime.now().isoformat(),
        "situacao": "Cancelada",
    }


def emitir_carta_correcao_nfe(chave: str, texto_correcao: str, seq_evento: Optional[int] = None, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    """
    Emite uma Carta de Correção Eletrônica (CC-e - Evento 110110) perante a SEFAZ.

    Conforme o MOC / NT 2011.003:
    - Mínimo de 15 caracteres e máximo de 1000 caracteres.
    - É proibido corrigir: valores/impostos, dados cadastrais que alterem
      emitente/destinatário, data de emissão/saída.
    - ``nSeqEvento`` é sequencial por chave (máximo 20 eventos).
    """
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    if len(chave_clean) != 44:
        raise ValueError("Chave de acesso inválida (deve conter 44 dígitos).")

    texto_limpo = remover_acentos_sefaz(str(texto_correcao).strip())
    if len(texto_limpo) < 15:
        raise ValueError("O texto da Carta de Correção deve conter no mínimo 15 caracteres.")
    if len(texto_limpo) > 1000:
        raise ValueError("O texto da Carta de Correção deve conter no máximo 1000 caracteres.")

    doc = get_nfe_detail(chave_clean)
    if not doc:
        raise ValueError(f"NF-e com chave {chave_clean} não encontrada no banco de dados.")

    situacao_atual = str(doc.get("situacao") or "")
    if situacao_atual.startswith("Cancelada"):
        msg = "NF-e cancelada não pode receber Carta de Correção."
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": msg,
                "detail": msg, "situacao": situacao_atual}

    emit_cnpj = doc.get("emitente_cnpj") or chave_clean[6:20]
    cert_rec = get_certificate_record(emit_cnpj)
    if not cert_rec:
        raise ValueError(f"Certificado A1 não encontrado para o CNPJ {emit_cnpj}.")

    # Sequência do evento: explícita > próxima livre local > 1
    seq = int(seq_evento) if seq_evento else _proxima_sequencia_evento(chave_clean, "110110")
    if not (1 <= seq <= 20):
        raise ValueError("A sequência da Carta de Correção deve estar entre 1 e 20.")

    homolog = homologacao if homologacao is not None else _homolog_do_documento(doc)
    uf = _uf_do_documento(doc, chave_clean)

    evento = _montar_evento(
        tp_evento="110110",
        chave=chave_clean,
        cnpj=emit_cnpj,
        uf=uf,
        homolog=homolog,
        det_campos={"xCorrecao": texto_limpo, "xCondUso": (
            "A Carta de Correcao e disciplinada pelo paragrafo 1o-A do art. 7o do Convenio S/N, "
            "de 15 de dezembro de 1970 e pode ser utilizada para regularizacao de erro ocorrido "
            "na emissao de documento fiscal, desde que o erro nao esteja relacionado com: I - as "
            "variaveis que determinam o valor do imposto tais como: base de calculo, aliquota, "
            "diferenca de preco, quantidade, valor da operacao ou da prestacao; II - a correcao de "
            "dados cadastrais que implique mudanca do remetente ou do destinatario; III - a data de "
            "emissao ou de saida."
        )},
        n_seq=seq,
        desc_evento="Carta de Correcao",
    )

    from pynfe.processamento.assinatura import AssinaturaA1
    try:
        evento_assinado = AssinaturaA1(cert_rec["path"], cert_rec["password"]).assinar(evento)
    except Exception:
        logger.exception("[CC-e] Falha ao assinar o evento da chave %s", chave_clean)
        raise ValueError("Falha ao assinar a Carta de Correção com o certificado A1.")

    try:
        retorno = _transmitir_evento(cert_rec, uf, homolog, evento_assinado)
    except Exception as exc:
        logger.exception("[CC-e] Falha de comunicação SEFAZ para a chave %s", chave_clean)
        msg = f"Falha de comunicação com a SEFAZ: {exc}"
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": msg,
                "detail": msg, "sequencia_evento": seq}

    c_stat = retorno["c_stat"]
    motivo = retorno["motivo"] or retorno["erro"] or "Sem retorno da SEFAZ."

    if retorno["erro"] and not c_stat:
        return {"success": False, "chave": chave_clean, "c_stat": "", "motivo": retorno["erro"],
                "detail": retorno["erro"], "sequencia_evento": seq}

    if c_stat not in ("135", "136"):
        msg = f"cStat {c_stat}: {motivo}"
        logger.warning("[CC-e] Rejeitada para a chave %s — %s", chave_clean, msg)
        return {"success": False, "chave": chave_clean, "c_stat": c_stat, "motivo": msg,
                "detail": msg, "sequencia_evento": seq, "correcao": texto_limpo}

    # Persiste o evento para que o DACCE possa ser gerado (cce_service exige a linha).
    save_nfe_event({
        "chave": chave_clean,
        "tipo_evento": "110110",
        "desc_evento": "Carta de Correcao Eletronica",
        "n_seq": seq,
        "dh_evento": retorno["dh_reg"] or datetime.now().isoformat(),
        "protocolo": retorno["protocolo"],
        "c_stat": c_stat,
        "x_motivo": motivo,
    })

    return {
        "success": True,
        "chave": chave_clean,
        "sequencia_evento": seq,
        "protocolo": retorno["protocolo"],
        "c_stat": c_stat,
        "motivo": motivo,
        "x_motivo": motivo,
        "detail": motivo,
        "correcao": texto_limpo,
        "data_evento": retorno["dh_reg"] or datetime.now().isoformat(),
    }


_UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}


def _uf_de_cod_uf(codigo: str) -> str:
    """Converte o código IBGE de UF (2 dígitos da chave) na sigla."""
    return _UF_POR_CODIGO.get(str(codigo), "")


def _uf_do_documento(doc: Dict[str, Any], chave: str) -> str:
    """Resolve a UF do emitente: cadastro local → código IBGE da chave → default."""
    uf = str(doc.get("emitente_uf") or "").strip().upper()
    if uf and len(uf) == 2 and uf.isalpha():
        return uf
    return _uf_de_cod_uf(chave[:2]) or settings.DEFAULT_UF


def _homolog_do_documento(doc: Dict[str, Any]) -> bool:
    """
    Ambiente do evento = ambiente em que a NF-e foi emitida.

    Cancelar/CC-e uma nota de homologação contra o webservice de produção (ou
    vice-versa) devolve cStat 217/502. Só cai no ``settings.HOMOLOGACAO`` quando
    o registro não guarda o ``tp_amb``.
    """
    tp_amb = doc.get("tp_amb")
    if str(tp_amb) in ("1", "2"):
        return str(tp_amb) == "2"
    return bool(settings.HOMOLOGACAO)


def _proxima_sequencia_evento(chave: str, tipo_evento: str) -> int:
    """Próxima sequência livre de um evento para a chave (limitada a 20)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(n_seq) FROM nfe_events WHERE chave = ? AND tipo_evento = ?",
                (chave, tipo_evento),
            )
            row = cursor.fetchone()
            atual = int(row[0] or 0)
        proxima = atual + 1
        if proxima > 20:
            raise ValueError(
                "A NF-e atingiu o limite de 20 Cartas de Correção para a mesma chave."
            )
        return proxima
    except ValueError:
        raise
    except Exception:
        return 1


# Dicionário de Diagnóstico Didático para Retornos e Rejeições da SEFAZ
SEFAZ_EXPLICATIVO_CSTAT = {
    "100": {
        "status_geral": "Autorizada com Sucesso",
        "explicacao": "A NF-e foi recebida, validada contra o Schema XML da Receita Federal e autorizada com sucesso pela SEFAZ. O documento possui total validade fiscal e jurídica.",
        "solucao": "Nenhuma ação necessária. Você já pode emitir ou imprimir o DANFE e enviar ao destinatário.",
        "tipo": "sucesso"
    },
    "101": {
        "status_geral": "Cancelamento Homologado",
        "explicacao": "O pedido de cancelamento da NF-e foi homologado com sucesso pela SEFAZ (Evento 110111).",
        "solucao": "A nota fiscal está formalmente cancelada perante o Fisco. Nenhuma mercadoria pode circular com este documento.",
        "tipo": "alerta"
    },
    "102": {
        "status_geral": "Inutilização Homologada",
        "explicacao": "A faixa de numeração informada foi inutilizada com sucesso perante a SEFAZ.",
        "solucao": "A quebra de sequência numérica está formalmente justificada perante o Fisco.",
        "tipo": "alerta"
    },
    "135": {
        "status_geral": "Evento Vinculado com Sucesso",
        "explicacao": "O evento fiscal (Carta de Correção, Cancelamento ou Manifestação) foi registrado e vinculado à NF-e.",
        "solucao": "O evento encontra-se registrado na base de dados nacional da SEFAZ.",
        "tipo": "sucesso"
    },
    "204": {
        "status_geral": "Rejeição: Duplicidade de NF-e",
        "explicacao": "A SEFAZ identificou que já existe uma NF-e autorizada com o mesmo CNPJ Emitente, Modelo (55), Série e Número.",
        "solucao": "1. Verifique se esta nota já foi emitida e autorizada anteriormente no histórico de saídas.\n2. Se deseja emitir uma nova venda, utilize o próximo número livre disponível.",
        "tipo": "erro"
    },
    "205": {
        "status_geral": "Rejeição: NF-e Denegada",
        "explicacao": "A NF-e foi denegada pelo Fisco devido à situação cadastral irregular do emitente ou do destinatário perante a Secretaria da Fazenda.",
        "solucao": "Consulte a situação da Inscrição Estadual da empresa ou do cliente no SINTEGRA / CCC (Cadastro Centralizado de Contribuintes). Uma nota denegada não pode ser reaproveitada.",
        "tipo": "erro"
    },
    "215": {
        "status_geral": "Rejeição: Falha no Schema XML",
        "explicacao": "O arquivo XML da NF-e não atende à validação dos esquemas XSD da Receita Federal (campos obrigatórios ausentes, tipos de dados incompatíveis ou caracteres inválidos).",
        "solucao": "Revise o preenchimento dos campos obrigatórios (marcados com borda vermelha) e certifique-se de que os dados fiscais estão completos.",
        "tipo": "erro"
    },
    "217": {
        "status_geral": "Rejeição: NF-e não consta na base da SEFAZ",
        "explicacao": "A SEFAZ não localizou esta Chave de Acesso em sua base de dados (a nota não foi transmitida anteriormente para a Fazenda ou foi gerada localmente/em ambiente de homologação).",
        "solucao": "Caso deseje oficializar a venda, utilize a opção '📋 Clonar e Emitir' para carregar os dados no formulário e realizar a transmissão oficial à SEFAZ.",
        "tipo": "alerta"
    },
    "656": {
        "status_geral": "Rejeição: Consumo Indevido pela SEFAZ",
        "explicacao": "A SEFAZ bloqueou temporariamente as requisições por excesso de consultas repetidas para a mesma chave em um curto intervalo de tempo (limite de tráfego do Web Service).",
        "solucao": "Aguarde de 3 a 5 minutos antes de realizar uma nova tentativa de consulta ou reenvio.",
        "tipo": "alerta"
    },
    "209": {
        "status_geral": "Rejeição: IE do Emitente Inválida",
        "explicacao": "A Inscrição Estadual informada para a filial emitente não possui dígitos verificadores válidos segundo o algoritmo do Estado.",
        "solucao": "Confira o número da Inscrição Estadual da filial nas configurações e certifique-se de que os dígitos estão corretos.",
        "tipo": "erro"
    },
    "225": {
        "status_geral": "Rejeição: Falha no Schema XML da NF-e",
        "explicacao": "A estrutura do XML não atende aos padrões técnicos exigidos pelo Manual de Orientação do Contribuinte da SEFAZ (campo obrigatório ausente ou formato incorreto).",
        "solucao": "Verifique se todos os campos destacados em vermelho foram preenchidos corretamente (ex: NCM com 8 dígitos, CPF/CNPJ válido, UF correta).",
        "tipo": "erro"
    },
    "229": {
        "status_geral": "Rejeição: IE do Emitente não informada",
        "explicacao": "A tag <IE> do emitente está vazia ou ausente no XML. Para notas Modelo 55, a IE da empresa emitente é estritamente obrigatória.",
        "solucao": "Acesse a seleção da empresa emitente e confirme o preenchimento da Inscrição Estadual da filial.",
        "tipo": "erro"
    },
    "230": {
        "status_geral": "Rejeição: IE do Emitente não cadastrada",
        "explicacao": "A Inscrição Estadual informada não foi localizada na base de contribuintes da SEFAZ do respectivo Estado.",
        "solucao": "Verifique se o credenciamento da empresa como emissora de NF-e está ativo na SEFAZ do Estado emissor.",
        "tipo": "erro"
    },
    "231": {
        "status_geral": "Rejeição: IE do Emitente não vinculada ao CNPJ",
        "explicacao": "A Inscrição Estadual informada pertence a outra empresa ou filial e não corresponde ao CNPJ do certificado digital.",
        "solucao": "Certifique-se de que a IE informada é exatamente a que pertence ao CNPJ da filial selecionada.",
        "tipo": "erro"
    },
    "232": {
        "status_geral": "Rejeição: IE do Destinatário não informada",
        "explicacao": "O cliente foi cadastrado com o Indicador de IE = 1 (Contribuinte de ICMS), mas a Inscrição Estadual não foi preenchida.",
        "solucao": "Se o cliente é pessoa física ou empresa sem IE, altere o Indicador de IE para '9 - Não Contribuinte'. Caso possua IE, preencha o campo de Inscrição Estadual.",
        "tipo": "erro"
    },
    "233": {
        "status_geral": "Rejeição: IE do Destinatário não cadastrada na SEFAZ",
        "explicacao": "A Inscrição Estadual do cliente não consta no cadastro da SEFAZ da UF de destino.",
        "solucao": "Altere o Indicador de IE do destinatário para '9 - Não Contribuinte' ou confira a numeração no SINTEGRA.",
        "tipo": "erro"
    },
    "234": {
        "status_geral": "Rejeição: IE do Destinatário não vinculada ao CNPJ",
        "explicacao": "A Inscrição Estadual informada para o cliente não corresponde ao CNPJ informado.",
        "solucao": "Consulte o CNPJ no portal CCC / SINTEGRA para confirmar a Inscrição Estadual correta vinculada ao CNPJ.",
        "tipo": "erro"
    },
    "539": {
        "status_geral": "Rejeição: Duplicidade de NF-e com diferença na Chave",
        "explicacao": "Já existe na SEFAZ uma NF-e autorizada para esta série e número, porém gerada com uma Chave de Acesso diferente.",
        "solucao": "1. Não utilize este número de NF-e para uma nova venda.\n2. Verifique o número da última nota emitida e avance a numeração.",
        "tipo": "erro"
    },
    "600": {
        "status_geral": "Rejeição: Chave da NF-e Referenciada Inválida",
        "explicacao": "A chave de acesso informada no campo 'NF-e Referenciada' possui dígitos verificadores inválidos ou não contém exatamente 44 números.",
        "solucao": "Confira a chave de 44 dígitos da nota fiscal de origem (fornecedor ou devolução) no DANFE original.",
        "tipo": "erro"
    },
    "610": {
        "status_geral": "Rejeição: Total da NF-e difere do somatório dos itens",
        "explicacao": "O valor total da nota fiscal informado no cabeçalho não coincide com a soma exata dos valores dos produtos menos descontos e mais frete.",
        "solucao": "O sistema recalcula automaticamente os totais para garantir a paridade centavo a centavo.",
        "tipo": "erro"
    },
    "778": {
        "status_geral": "Rejeição: Informado NCM Inexistente",
        "explicacao": "Um ou mais produtos da nota utilizam um código NCM de 8 dígitos que foi extinto ou não existe na tabela oficial da Receita Federal.",
        "solucao": "Corrija o código NCM do produto para uma classificação fiscal ativa na Tabela TIPI da Receita Federal.",
        "tipo": "erro"
    }
}


def reenviar_nfe_sefaz(chave: str, homologacao: Optional[bool] = None) -> Dict[str, Any]:
    """
    Consulta a situação oficial da NF-e na SEFAZ e, se a nota estiver **Pendente
    de transmissão** e não existir na base delas, retransmite o XML assinado.

    Fluxo:
      1. ``consulta_nota`` → se a SEFAZ já conhece a chave, adota o estado real
         (autorizada / denegada / rejeitada) sem reenviar nada;
      2. caso responda 217 (não consta) e tenhamos o ``<NFe> assinado`` local,
         retransmite — aí sim é um reenvio de fato.

    Nunca fabrica cStat nem protocolo: sem resposta da SEFAZ o estado continua
    o que já estava registrado localmente.
    """
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    if len(chave_clean) != 44:
        raise ValueError("Chave de acesso inválida (deve conter 44 dígitos).")

    doc = get_nfe_detail(chave_clean)
    if not doc:
        raise ValueError(f"NF-e com chave {chave_clean} não encontrada no banco de dados.")

    emit_cnpj = doc.get("empresa_cnpj") or doc.get("emitente_cnpj") or chave_clean[6:20]
    cert_rec = get_certificate_record(emit_cnpj)
    if not cert_rec:
        certs = list_certificates_db()
        cert_rec = next((c for c in certs if c["cnpj"] == emit_cnpj), None)

    situacao_local = str(doc.get("situacao") or "Pendente")
    if situacao_local.startswith("Cancelada"):
        # Cancelamento é estado final e prevalece sobre qualquer consulta.
        return {
            "success": True, "autorizada": False, "ja_executado": True,
            "chave": chave_clean, "c_stat": doc.get("c_stat") or "",
            "x_motivo": "NF-e cancelada — a consulta não altera o estado final.",
            "situacao": situacao_local, "protocolo": doc.get("protocolo"),
            "status_geral": "NF-e Cancelada",
            "explicacao_didatica": "O cancelamento registrado localmente é estado final e não é revertido por consulta.",
            "solucao_recomendada": "Nenhuma ação necessária.",
            "tipo_retorno": "alerta",
        }

    # O ambiente vem do próprio registro: consultar homologação por uma nota
    # de produção (ou vice-versa) devolve cStat 217 e rebaixaria a situação.
    tp_amb_local = doc.get("tp_amb")
    homolog = homologacao if homologacao is not None else (
        bool(int(tp_amb_local)) if str(tp_amb_local) in ("1", "2") else settings.HOMOLOGACAO
    )
    now = datetime.now()
    emit_uf = (doc.get("emitente_uf") or (cert_rec.get("uf") if cert_rec else None) or settings.DEFAULT_UF).upper()

    c_stat = str(doc.get("c_stat") or "")
    x_motivo = str(doc.get("x_motivo") or "")
    protocolo = str(doc.get("protocolo") or "")
    erro_comunicacao = None
    retransmitido = False

    if not cert_rec or not os.path.exists(cert_rec.get("path", "")):
        erro_comunicacao = (
            f"Certificado A1 do CNPJ {emit_cnpj} não encontrado ou arquivo inexistente — "
            "a consulta à SEFAZ não foi realizada."
        )
    else:
        try:
            con = ComunicacaoSefaz(emit_uf, cert_rec["path"], cert_rec["password"], homologacao=homolog)

            # 1) Consulta primeiro — nunca retransmite às cegas.
            # Nota emitida em contingência é consultada no endpoint da SEFAZ
            # Virtual, senão a SEFAZ responde 217 (não consta).
            tp_emis_doc = str(doc.get("tp_emis") or "1")
            resp_cons = con.consulta_nota(
                modelo="nfe", chave=chave_clean, contingencia=tp_emis_doc != "1"
            )
            consulta = _extrair_retorno_consulta(getattr(resp_cons, "text", ""))
            c_cons = consulta["c_stat"]

            if c_cons in ("100", "150"):
                c_stat, x_motivo = c_cons, consulta["motivo"] or "Autorizado o uso da NF-e"
                protocolo = consulta["protocolo"] or protocolo
            elif c_cons in CSTAT_DENEGADO:
                c_stat, x_motivo = c_cons, consulta["motivo"] or "Uso denegado"
                protocolo = consulta["protocolo"] or protocolo
            elif c_cons == "217":
                # A nota não consta na SEFAZ: só retransmite se formos nós que
                # a emitimos e ela ficou pendente (falha de rede, lote, etc).
                xml_assinado_local = str(doc.get("xml_assinado") or "")
                if xml_assinado_local:
                    elem = etree.fromstring(xml_assinado_local.encode("utf-8"))
                    resp_envio = con.autorizacao(
                        modelo="nfe", nota_fiscal=elem, id_lote=1,
                        ind_sinc=1, timeout=SEFAZ_TIMEOUT,
                    )
                    envio = _parse_retorno_autorizacao(resp_envio)
                    if envio["erro"] and not envio["c_stat"]:
                        erro_comunicacao = envio["erro"]
                    else:
                        c_stat = envio["c_stat"]
                        x_motivo = envio["motivo"] or "Sem descrição da SEFAZ."
                        protocolo = envio["protocolo"]
                        retransmitido = True
                        if envio["xml_proc"]:
                            try:
                                with get_db_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "UPDATE nfe_docs SET xml_raw = ? WHERE chave = ?",
                                        (envio["xml_proc"], chave_clean),
                                    )
                                    conn.commit()
                            except Exception:
                                logger.exception(
                                    "[REENVIO] Falha ao gravar nfeProc autorizado da chave %s", chave_clean
                                )
                else:
                    c_stat, x_motivo = c_cons, consulta["motivo"] or "NF-e não consta na SEFAZ."
            else:
                # 108/110 serviço parado, 217 sem consulta possível, HTTP != 200...
                if c_cons:
                    c_stat, x_motivo = c_cons, consulta["motivo"] or consulta["erro"] or ""
                else:
                    erro_comunicacao = consulta["erro"] or "Sem retorno interpretável da SEFAZ."
        except Exception as sefaz_err:
            logger.exception("[REENVIO] Falha de comunicação SEFAZ para a chave %s", chave_clean)
            erro_comunicacao = f"Falha de comunicação com a SEFAZ: {sefaz_err}"

    autorizada = c_stat in CSTAT_AUTORIZADO
    denegada = c_stat in CSTAT_DENEGADO
    situacao_nova = _situacao_de_cstat(c_stat, protocolo) if c_stat else situacao_local

    # Nunca rebaixa estados terminais.
    if situacao_e_terminal(situacao_local):
        situacao_nova = situacao_local

    if c_stat:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE nfe_docs
                SET situacao = ?, c_stat = ?, x_motivo = ?, protocolo = COALESCE(NULLIF(?, ''), protocolo),
                    data_autorizacao = CASE WHEN ? AND (data_autorizacao IS NULL OR data_autorizacao = '')
                                            THEN ? ELSE data_autorizacao END,
                    updated_at = ?
                WHERE chave = ?
                """,
                (situacao_nova, c_stat, x_motivo, protocolo, str(autorizada),
                 now.isoformat(), now.isoformat(), chave_clean),
            )
            conn.commit()

    info_explicativa = SEFAZ_EXPLICATIVO_CSTAT.get(c_stat, {
        "status_geral": f"Código SEFAZ {c_stat}" if c_stat else "Consulta não realizada",
        "explicacao": x_motivo or (erro_comunicacao or "Sem descrição disponível."),
        "solucao": "Verifique os dados cadastrais da empresa e do cliente conforme a mensagem oficial da SEFAZ.",
        "tipo": "sucesso" if autorizada else "erro",
    })

    return {
        "success": erro_comunicacao is None,
        "autorizada": autorizada,
        "denegada": denegada,
        "retransmitido": retransmitido,
        "erro": erro_comunicacao,
        "chave": chave_clean,
        "numero": doc.get("numero", "1"),
        "serie": doc.get("serie", "1"),
        "modelo": doc.get("modelo", "55"),
        "empresa_cnpj": emit_cnpj,
        "emitente_nome": doc.get("emitente_nome", cert_rec.get("razao_social") if cert_rec else "EMPRESA EMITENTE"),
        "destinatario_nome": doc.get("destinatario_nome", "CLIENTE DESTINATÁRIO"),
        "destinatario_cnpj": doc.get("destinatario_cnpj", ""),
        "valor_total": float(doc.get("valor_total", 0.0)),
        "c_stat": c_stat,
        "x_motivo": x_motivo or erro_comunicacao or "",
        "detail": x_motivo or erro_comunicacao or "",
        "situacao": situacao_nova,
        "protocolo": protocolo if autorizada else (protocolo or None),
        "ambiente": "Homologação" if homolog else "Produção",
        "data_retorno": now.strftime("%d/%m/%Y %H:%M:%S"),
        "status_geral": info_explicativa.get("status_geral"),
        "explicacao_didatica": info_explicativa.get("explicacao"),
        "solucao_recomendada": info_explicativa.get("solucao"),
        "tipo_retorno": info_explicativa.get("tipo"),
    }


def inutilizar_numeracao_nfe(empresa_cnpj: str, serie: str, numero_inicial: int, numero_final: int, justificativa: str, modelo: str = "55", homologacao: Optional[bool] = None) -> Dict[str, Any]:
    """
    Inutiliza uma faixa de numeração de NF-e/NFC-e perante a SEFAZ (serviço 404/405).

    - Justificativa de 15 a 255 caracteres.
    - modelo: 55 (NF-e) ou 65 (NFC-e).
    - O registro só entra no banco depois que a SEFAZ confirma cStat 102
      (ou 404, quando a faixa já constava como inutilizada — idempotente).
    """
    cnpj_clean = "".join(c for c in str(empresa_cnpj) if c.isdigit())
    if len(cnpj_clean) not in (11, 14):
        raise ValueError("CNPJ/CPF do emitente é inválido.")

    just_limpa = remover_acentos_sefaz(str(justificativa).strip())
    if len(just_limpa) < 15:
        raise ValueError("A justificativa de inutilização deve conter no mínimo 15 caracteres.")
    if len(just_limpa) > 255:
        raise ValueError("A justificativa de inutilização deve conter no máximo 255 caracteres.")

    numero_inicial = int(numero_inicial)
    numero_final = int(numero_final)
    if numero_final < numero_inicial:
        raise ValueError("O número final não pode ser menor que o número inicial.")
    if (numero_final - numero_inicial) > 9999:
        raise ValueError("A faixa de inutilização não pode exceder 10.000 numerações por vez.")
    if numero_inicial < 1:
        raise ValueError("O número inicial da faixa deve ser maior que zero.")

    modelo = str(modelo or "55")
    if modelo not in ("55", "65"):
        raise ValueError("Modelo inválido: use 55 (NF-e) ou 65 (NFC-e).")

    # Guarda local: não inutiliza faixa que contém nota já emitida.
    com_ocupados = _numeros_ocupados_na_faixa(cnpj_clean, serie, modelo, numero_inicial, numero_final)
    if com_ocupados:
        raise ValueError(
            "A faixa informada contém números já utilizados: "
            + ", ".join(str(n) for n in com_ocupados[:10])
            + ". Reduza a faixa antes de inutilizar."
        )

    homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO
    uf = settings.DEFAULT_UF
    cert_rec = get_certificate_record(cnpj_clean)
    if not cert_rec:
        raise ValueError(f"Certificado A1 não encontrado para o CNPJ {cnpj_clean}.")
    uf = str(cert_rec.get("uf") or uf).upper()

    try:
        con = ComunicacaoSefaz(uf, cert_rec["path"], cert_rec["password"], homologacao=homolog)
        response = con.inutilizacao(
            "nfe" if modelo == "55" else "nfce",
            cnpj_clean,
            numero_inicial,
            numero_final,
            justificativa=just_limpa,
            ano=datetime.now().year,
            serie=str(serie or "1"),
        )
    except Exception as exc:
        logger.exception("[INUTILIZACAO] Falha de comunicação SEFAZ (%s/%s)", numero_inicial, numero_final)
        return {
            "success": False, "empresa_cnpj": cnpj_clean, "modelo": modelo, "serie": str(serie),
            "numero_inicial": numero_inicial, "numero_final": numero_final,
            "c_stat": "", "motivo": f"Falha de comunicação com a SEFAZ: {exc}",
            "detail": f"Falha de comunicação com a SEFAZ: {exc}",
        }

    corpo = getattr(response, "text", "") or ""
    status_http = getattr(response, "status_code", None)
    if status_http not in (None, 200):
        msg = f"HTTP {status_http} no webservice de inutilização da SEFAZ."
        return {"success": False, "empresa_cnpj": cnpj_clean, "modelo": modelo, "serie": str(serie),
                "numero_inicial": numero_inicial, "numero_final": numero_final,
                "c_stat": "", "motivo": msg, "detail": msg}

    retorno = _extrair_infret(corpo)
    c_stat = retorno["c_stat"]
    motivo = retorno["motivo"] or retorno["erro"] or "Sem retorno da SEFAZ."

    # 102 = inutilização homologada; 404 = faixa já inutilizada (idempotente).
    aceito = c_stat in ("102", "404")
    if not aceito:
        msg = f"cStat {c_stat}: {motivo}"
        logger.warning("[INUTILIZACAO] Rejeitada (%s..%s) — %s", numero_inicial, numero_final, msg)
        return {
            "success": False, "empresa_cnpj": cnpj_clean, "modelo": modelo, "serie": str(serie),
            "numero_inicial": numero_inicial, "numero_final": numero_final,
            "c_stat": c_stat, "motivo": msg, "detail": msg,
        }

    now = datetime.now()
    prot_inut = retorno["protocolo"] or ""
    if c_stat == "404":
        motivo = motivo or "Faixa de numeração já inutilizada na SEFAZ."

    try:
        save_inutilizacao({
            "empresa_cnpj": cnpj_clean,
            "ano": now.year,
            "modelo": modelo,
            "serie": serie,
            "numero_inicial": numero_inicial,
            "numero_final": numero_final,
            "protocolo": prot_inut,
            "justificativa": just_limpa,
            "data_homologacao": retorno["dh_reg"] or now.isoformat(),
            "c_stat": c_stat,
            "x_motivo": motivo,
        })
    except Exception:
        logger.exception("[INUTILIZACAO] Falha ao registrar no banco local.")

    return {
        "success": True,
        "empresa_cnpj": cnpj_clean,
        "modelo": modelo,
        "serie": str(serie),
        "numero_inicial": numero_inicial,
        "numero_final": numero_final,
        "protocolo": prot_inut,
        "c_stat": c_stat,
        "motivo": motivo,
        "x_motivo": motivo,
        "detail": motivo,
        "justificativa": just_limpa,
        "data_inutilizacao": retorno["dh_reg"] or now.isoformat(),
        "ambiente": "Homologação" if homolog else "Produção",
    }


def _numeros_ocupados_na_faixa(cnpj: str, serie: str, modelo: str, ini: int, fim: int) -> List[int]:
    """Retorna números da faixa que já existem em nfe_docs (evita Rejeição 405)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT CAST(numero AS INTEGER) AS n
                FROM nfe_docs
                WHERE emitente_cnpj = ? AND serie = ?
                  AND (modelo = ? OR modelo IS NULL OR modelo = '')
                  AND CAST(numero AS INTEGER) BETWEEN ? AND ?
                  AND numero IS NOT NULL AND numero != ''
                ORDER BY n
                """,
                (cnpj, str(serie or "1"), modelo, ini, fim),
            )
            return [int(r[0]) for r in cursor.fetchall()]
    except Exception:
        return []


def importar_lote_xmls_saida(arquivos: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    """
    Importa em massa múltiplos arquivos XMLs ou arquivos ZIP contendo XMLs de notas fiscais de saída.
    Processa cada XML, grava em disco, indexa no SQLite e gera o PDF DANFE oficial.
    """
    total_processados = 0
    total_importados = 0
    total_atualizados = 0
    erros = []

    xml_items: List[Tuple[str, bytes]] = []

    for fname, content in arquivos:
        if not content:
            continue
        if fname.lower().endswith(".zip") or content[:4] == b"PK\x03\x04":
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    for zname in z.namelist():
                        if zname.lower().endswith(".xml") and not zname.startswith("__MACOSX"):
                            xml_items.append((zname, z.read(zname)))
            except Exception as zip_err:
                erros.append(f"Erro ao descompactar {fname}: {zip_err}")
        elif fname.lower().endswith(".xml") or b"<nfeProc" in content or b"<NFe" in content:
            xml_items.append((fname, content))

    for fname, xml_bytes in xml_items:
        total_processados += 1
        try:
            xml_str = decode_xml(xml_bytes)
            parsed = parse_nfe_xml(xml_bytes)
            if not parsed or "error" in parsed:
                continue

            chave = parsed.get("chave") or "".join(c for c in fname if c.isdigit())
            if len(chave) != 44:
                continue

            emit_cnpj = "".join(c for c in str(parsed.get("emitente", {}).get("cnpj", "")) if c.isdigit())
            dest_cnpj = "".join(c for c in str(parsed.get("destinatario", {}).get("cnpj", "") or parsed.get("destinatario", {}).get("cpf", "")) if c.isdigit())

            # Se o emitente é uma das empresas do grupo, marca como saída (tipo_doc = 1)
            emit_is_grupo = bool(get_certificate_record(emit_cnpj))
            dest_is_grupo = bool(get_certificate_record(dest_cnpj))

            tipo_doc = 1 if emit_is_grupo and not dest_is_grupo else 0

            doc_dict = {
                "chave": chave,
                "empresa_cnpj": emit_cnpj if emit_is_grupo else dest_cnpj,
                "numero": str(parsed.get("numero", "")),
                "serie": str(parsed.get("serie", "1")),
                "modelo": str(parsed.get("modelo", "55")),
                "tipo_doc": tipo_doc,
                "data_emissao": parsed.get("data_emissao", ""),
                "data_autorizacao": parsed.get("data_autorizacao", ""),
                "emitente": parsed.get("emitente", {}),
                "destinatario": parsed.get("destinatario", {}),
                "totais": parsed.get("totais", {}),
                "situacao": parsed.get("situacao", "Autorizada"),
                "protocolo": parsed.get("protocolo", ""),
                "produtos": parsed.get("produtos", []),
            }

            saved = save_nfe_doc(doc_dict, xml_raw=xml_str)
            if saved:
                total_importados += 1

                # Gera DANFE PDF
                try:
                    pdf_io = generate_danfe_pdf(xml_bytes)
                    if pdf_io:
                        pdf_path = os.path.join(settings.DATA_DIR, "danfe_pdfs", f"{chave}.pdf")
                        with open(pdf_path, "wb") as f_pdf:
                            f_pdf.write(pdf_io.getvalue())
                except Exception:
                    pass

        except Exception as e:
            erros.append(f"Erro em {fname}: {str(e)}")

    return {
        "success": True,
        "total_processados": total_processados,
        "total_importados": total_importados,
        "erros": erros[:10],
    }


def gerar_previa_nfe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gera a prévia completa do DANFE em formato estruturado a partir dos dados do formulário,
    permitindo que o usuário visualize e imprima antes de assinar e transmitir à SEFAZ.
    """
    emit_cnpj_clean = "".join(c for c in str(payload.get("emitente_cnpj", "")) if c.isdigit())
    cert_rec = get_certificate_record(emit_cnpj_clean) if emit_cnpj_clean else None
    if not cert_rec:
        certs = list_certificates_db()
        cert_rec = next((c for c in certs if c["cnpj"] == emit_cnpj_clean), None) if emit_cnpj_clean else None

    razao_emit = cert_rec["razao_social"] if cert_rec else "EMPRESA EMITENTE EXEMPLO LTDA"
    emit_uf = (payload.get("emitente_uf") or (cert_rec.get("uf") if cert_rec else "SP") or "SP").upper()

    dest_data = payload.get("destinatario", {})
    dest_doc_clean = "".join(c for c in str(dest_data.get("cpf_cnpj", "")) if c.isdigit())
    dest_nome = str(dest_data.get("razao_social", "")).strip().upper() or "CONSUMIDOR FINAL"
    dest_tipo_doc = "CPF" if len(dest_doc_clean) == 11 else "CNPJ"
    dest_uf = (dest_data.get("uf") or emit_uf).upper()
    dest_municipio = dest_data.get("municipio") or "SAO PAULO"

    produtos_payload = payload.get("produtos", [])
    if not produtos_payload:
        raise ValueError("Adicione ao menos 1 produto para visualizar a prévia da NF-e.")

    serie = str(payload.get("serie", "1"))
    numero = int(payload.get("numero") or (get_next_nfe_number(emit_cnpj_clean, serie) if emit_cnpj_clean else 1))
    natureza_op = str(payload.get("natureza_operacao") or "VENDA DE MERCADORIA").upper()

    now = datetime.now()
    chave_simulada = f"35{now.strftime('%y%m')}{emit_cnpj_clean.zfill(14)}55{serie.zfill(3)}{str(numero).zfill(9)}100000001"
    if len(chave_simulada) < 44:
        chave_simulada = chave_simulada.ljust(44, "0")
    elif len(chave_simulada) > 44:
        chave_simulada = chave_simulada[:44]

    tot_produtos = Decimal("0.00")
    tot_desconto = Decimal("0.00")
    tot_trib_fed = Decimal("0.00")
    tot_trib_est = Decimal("0.00")

    is_interestadual = emit_uf != dest_uf
    itens_formatados = []
    for idx, prod_raw in enumerate(produtos_payload, start=1):
        cod_prod = remover_acentos_sefaz(str(prod_raw.get("codigo") or f"PROD{idx}"))
        desc_prod = remover_acentos_sefaz(str(prod_raw.get("descricao") or "PRODUTO COMERCIAL").strip())
        ncm_prod = "".join(c for c in str(prod_raw.get("ncm") or "85171300") if c.isdigit())
        if len(ncm_prod) < 8:
            ncm_prod = ncm_prod.ljust(8, "0")
        elif len(ncm_prod) > 8:
            ncm_prod = ncm_prod[:8]

        unidade = remover_acentos_sefaz(str(prod_raw.get("unidade") or "UN"))
        qtd = Decimal(str(prod_raw.get("quantidade", 1)))
        v_unit = Decimal(str(prod_raw.get("valor_unitario", 0.0)))
        v_desc = Decimal(str(prod_raw.get("desconto", 0.0)))
        v_tot = (qtd * v_unit) - v_desc

        cfop_sugerido = "6102" if is_interestadual else "5102"
        cfop_inf = str(prod_raw.get("cfop") or cfop_sugerido).strip()
        if is_interestadual and cfop_inf.startswith("5"):
            cfop = "6" + cfop_inf[1:]
        elif not is_interestadual and cfop_inf.startswith("6"):
            cfop = "5" + cfop_inf[1:]
        else:
            cfop = cfop_inf

        tot_produtos += (qtd * v_unit)
        tot_desconto += v_desc

        item_fed, item_est = calcular_ibpt_ncm(ncm_prod, v_tot)
        tot_trib_fed += item_fed
        tot_trib_est += item_est
        itens_formatados.append({
            "numero_item": idx,
            "codigo": cod_prod,
            "descricao": desc_prod,
            "imei": str(prod_raw.get("imei") or "").strip(),
            "ncm": ncm_prod,
            "cfop": cfop,
            "unidade": unidade,
            "quantidade": float(qtd),
            "valor_unitario": float(v_unit),
            "valor_total": float(v_tot),
            "desconto": float(v_desc),
            "valor_icms": 0.0,
            "aliquota_icms": 0.0,
        })

    tot_frete = Decimal(str(payload.get("valor_frete", "0.00")))
    tot_seguro = Decimal(str(payload.get("valor_seguro", "0.00")))
    tot_outras = Decimal(str(payload.get("outras_despesas", "0.00")))
    tot_nota = tot_produtos - tot_desconto + tot_frete + tot_seguro + tot_outras

    transp_data = payload.get("transporte", {})

    def _fmt_cnpj_cpf(val):
        d = "".join(c for c in str(val or "") if c.isdigit())
        if len(d) == 14:
            return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
        elif len(d) == 11:
            return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
        return val or ""

    def _fmt_cep_str(val):
        d = "".join(c for c in str(val or "") if c.isdigit())
        if len(d) == 8:
            return f"{d[:5]}-{d[5:]}"
        return val or ""

    is_homologacao = payload.get("homologacao", True)

    danfe_dict = {
        "chave": chave_simulada,
        "natureza_operacao": natureza_op,
        "numero": str(numero),
        "serie": str(serie),
        "data_emissao": now.strftime("%d/%m/%Y %H:%M:%S"),
        "data_saida": (payload.get("data_saida") or now.strftime("%d/%m/%Y %H:%M:%S")),
        "ambiente": "Homologação" if is_homologacao else "Produção",
        "emitente": {
            "razao_social": razao_emit,
            "cnpj": _fmt_cnpj_cpf(emit_cnpj_clean),
            "cnpj_formatado": _fmt_cnpj_cpf(emit_cnpj_clean),
            "ie": payload.get("emitente_ie") or (cert_rec.get("ie") if cert_rec else None) or "ISENTO",
            "logradouro": payload.get("emitente_logradouro") or (cert_rec.get("logradouro") if cert_rec else None) or "Rua Principal",
            "numero": payload.get("emitente_numero") or (cert_rec.get("numero") if cert_rec else None) or "S/N",
            "bairro": payload.get("emitente_bairro") or (cert_rec.get("bairro") if cert_rec else None) or "Centro",
            "municipio": payload.get("emitente_municipio") or (cert_rec.get("municipio") if cert_rec else None) or "Piracicaba",
            "uf": emit_uf,
            "cep": payload.get("emitente_cep") or (cert_rec.get("cep") if cert_rec else None) or "13400-000",
        },
        "destinatario": {
            "razao_social": dest_nome,
            "cnpj_cpf": _fmt_cnpj_cpf(dest_doc_clean),
            "tipo_documento": dest_tipo_doc,
            "ie": dest_data.get("ie") or "ISENTO",
            "logradouro": dest_data.get("logradouro") or "Rua do Cliente",
            "numero": dest_data.get("numero") or "S/N",
            "bairro": dest_data.get("bairro") or "Bairro",
            "municipio": dest_municipio,
            "uf": dest_uf,
            "cep": dest_data.get("cep") or "",
        },
        "totais": {
            "base_calculo_icms": 0.0,
            "valor_icms": 0.0,
            "base_calculo_icms_st": 0.0,
            "valor_icms_st": 0.0,
            "valor_produtos": float(tot_produtos),
            "valor_frete": float(tot_frete),
            "valor_seguro": float(tot_seguro),
            "desconto": float(tot_desconto),
            "outras_despesas": float(tot_outras),
            "valor_ipi": 0.0,
            "valor_pis": 0.0,
            "valor_cofins": 0.0,
            "valor_total": float(tot_nota),
            "valor_tributos": float(tot_trib_fed + tot_trib_est),
        },
        "transporte": {
            "modalidade_frete": str(transp_data.get("modalidade_frete", "9")),
            "transportadora_nome": transp_data.get("transportadora_nome") or "",
            "transportadora_cnpj_cpf": transp_data.get("transportadora_cnpj_cpf") or "",
            "placa_veiculo": transp_data.get("placa_veiculo") or "",
            "uf_veiculo": transp_data.get("uf_veiculo") or "",
            "volumes_qtd": int(transp_data.get("volumes_qtd") or 0),
            "volumes_especie": transp_data.get("volumes_especie") or "",
            "peso_liquido": float(transp_data.get("peso_liquido") or 0.0),
            "peso_bruto": float(transp_data.get("peso_bruto") or 0.0),
        },
        "itens": itens_formatados,
        "duplicatas": payload.get("parcelas", []),
        "informacoes_complementares": (payload.get("informacoes_complementares", "") or "Documento emitido por ME ou EPP optante pelo Simples Nacional.") + f" | Trib aprox R$: {tot_trib_fed:.2f} Fed e R$: {tot_trib_est:.2f} Est. Fonte: IBPT.",
        "chave_referenciada": payload.get("chave_referenciada") or payload.get("nfe_referenciada") or "",
    }
    return danfe_dict


# ====================================================================
# CONSULTA AUTOMÁTICA DE CNPJ NA RECEITA FEDERAL (BRASILAPI / RECEITAWS)
# ====================================================================

def consultar_dados_cnpj(cnpj: str) -> Dict[str, Any]:
    """
    Consulta a base de dados pública da Receita Federal via API pública e retorna os dados cadastrais completos.
    """
    import requests
    clean_cnpj = "".join(c for c in str(cnpj or "") if c.isdigit())
    if len(clean_cnpj) != 14:
        raise ValueError("CNPJ inválido (deve conter 14 dígitos numéricos).")

    headers = {"User-Agent": "NFe-Emissor/2.0"}

    # 1. Tenta BrasilAPI
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{clean_cnpj}", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            cep_raw = str(d.get("cep") or "").replace(".", "").replace("-", "")
            cep_fmt = f"{cep_raw[:5]}-{cep_raw[5:]}" if len(cep_raw) == 8 else cep_raw

            return {
                "cnpj": clean_cnpj,
                "razao_social": d.get("razao_social", ""),
                "nome_fantasia": d.get("nome_fantasia", "") or d.get("razao_social", ""),
                "situacao_cadastral": d.get("descricao_situacao_cadastral", "ATIVA"),
                "data_situacao_cadastral": d.get("data_situacao_cadastral", ""),
                "logradouro": d.get("logradouro", ""),
                "numero": d.get("numero", ""),
                "complemento": d.get("complemento", ""),
                "bairro": d.get("bairro", ""),
                "municipio": d.get("municipio", ""),
                "uf": d.get("uf", "SP"),
                "cep": cep_fmt,
                "telefone": d.get("ddd_telefone_1", "") or d.get("ddd_telefone_2", ""),
                "email": d.get("email", ""),
                "cnae_fiscal": str(d.get("cnae_fiscal", "")),
                "cnae_fiscal_descricao": d.get("cnae_fiscal_descricao", ""),
                "natureza_juridica": d.get("natureza_juridica", ""),
                "opcao_pelo_simples": bool(d.get("opcao_pelo_simples", True)),
                "indicador_ie": 9, # Por padrão, consumidor / não contribuinte até informar IE
            }
    except Exception as e:
        print(f"Aviso: BrasilAPI falhou ({e}), tentando ReceitaWS...")

    # 2. Fallback: ReceitaWS
    try:
        r = requests.get(f"https://receitaws.com.br/v1/cnpj/{clean_cnpj}", headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "ERROR":
                raise ValueError(d.get("message", "CNPJ não localizado na Receita Federal."))

            cep_raw = str(d.get("cep") or "").replace(".", "").replace("-", "")
            cep_fmt = f"{cep_raw[:5]}-{cep_raw[5:]}" if len(cep_raw) == 8 else cep_raw

            return {
                "cnpj": clean_cnpj,
                "razao_social": d.get("nome", ""),
                "nome_fantasia": d.get("fantasia", "") or d.get("nome", ""),
                "situacao_cadastral": d.get("situacao", "ATIVA"),
                "data_situacao_cadastral": d.get("data_situacao", ""),
                "logradouro": d.get("logradouro", ""),
                "numero": d.get("numero", ""),
                "complemento": d.get("complemento", ""),
                "bairro": d.get("bairro", ""),
                "municipio": d.get("municipio", ""),
                "uf": d.get("uf", "SP"),
                "cep": cep_fmt,
                "telefone": d.get("telefone", ""),
                "email": d.get("email", ""),
                "cnae_fiscal": d.get("atividade_principal", [{}])[0].get("code", ""),
                "cnae_fiscal_descricao": d.get("atividade_principal", [{}])[0].get("text", ""),
                "natureza_juridica": d.get("natureza_juridica", ""),
                "opcao_pelo_simples": bool(d.get("simples", {}).get("optante", True)),
                "indicador_ie": 9,
            }
    except Exception as e:
        raise ValueError(f"Não foi possível consultar o CNPJ na Receita Federal: {e}")

    raise ValueError("CNPJ não encontrado na base pública da Receita Federal.")


# ====================================================================
# FECHAMENTO CONTÁBIL MENSAL (EXPORTAÇÃO EM LOTE PARA CONTABILIDADE)
# ====================================================================

def gerar_pacote_fechamento_contabil(
    empresa_cnpj: Optional[str] = None,
    ano: int = 2026,
    mes: int = 8
) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Gera um arquivo .ZIP organizado por Certificado / Empresa contendo todos os XMLs de notas fiscais
    emitidas no mês (Autorizadas, Canceladas) e um Relatório CSV de Faturamento para o escritório de contabilidade.
    Garante que 100% das notas tenham seus XMLs incluídos.
    """
    import csv
    from backend.services.danfe_service import build_synthetic_nfe_xml

    competencia = f"{ano:04d}-{mes:02d}"
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    # Mapeamento oficial de certificados / filiais
    EMPRESAS_MAP = {
        "34511185000110": "JACKCELL CELULARES E IMPORTADOS LTDA",
        "13787408000105": "FERNANDES COMERCIO DE CELULARES E IMPORTACAO LTDA",
        "44739622000101": "FILIPE ALMEIDA GIL DE SOUZA LTDA",
        "58186781000130": "J DE A FERNANDES OPERACOES DE CREDITO",
        "58495100000116": "MI PLACE AMPARO LTDA",
    }

    query = """
        SELECT chave, empresa_cnpj, emitente_cnpj, numero, serie, modelo, data_emissao, emitente_nome,
               destinatario_nome, destinatario_cnpj, valor_total, situacao, xml_raw
        FROM nfe_docs
        WHERE data_emissao LIKE ?
    """
    params = [f"{competencia}%"]

    if clean_cnpj:
        query += " AND (empresa_cnpj = ? OR emitente_cnpj = ?)"
        params.extend([clean_cnpj, clean_cnpj])
    else:
        # Pega todas as notas emitidas por qualquer um dos nossos 5 certificados
        query += " AND (tipo_doc = 1 OR emitente_cnpj IN ({cnpjs}))".format(
            cnpjs=",".join(f"'{c}'" for c in EMPRESAS_MAP.keys())
        )

    query += " ORDER BY emitente_cnpj ASC, CAST(numero AS INTEGER) ASC"

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

    zip_buffer = io.BytesIO()
    total_autorizadas = 0
    total_canceladas = 0
    faturamento_total = Decimal("0.00")
    por_empresa = {}

    csv_rows = [
        ["Data Emissao", "Chave de Acesso", "Numero", "Serie", "Modelo", "CNPJ Emitente", "Empresa Emitente", "Destinatario", "CPF/CNPJ Destinatario", "Valor Total (R$)", "Situacao"]
    ]

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            chave = r["chave"]
            situacao = r["situacao"] or "Autorizada"
            is_cancelada = "cancelad" in situacao.lower()
            val_tot = Decimal(str(r["valor_total"] or 0))
            emit_cnpj = r.get("emitente_cnpj") or r.get("empresa_cnpj") or "34511185000110"
            nome_empresa = r.get("emitente_nome") or EMPRESAS_MAP.get(emit_cnpj, "EMPRESA")

            if emit_cnpj not in por_empresa:
                por_empresa[emit_cnpj] = {"nome": nome_empresa, "qtd": 0, "valor": Decimal("0.00")}
            por_empresa[emit_cnpj]["qtd"] += 1
            por_empresa[emit_cnpj]["valor"] += val_tot

            if not is_cancelada:
                total_autorizadas += 1
                faturamento_total += val_tot
                sub_status = "NFes_Autorizadas"
            else:
                total_canceladas += 1
                sub_status = "NFes_Canceladas"

            # Estrutura de pastas no ZIP
            if clean_cnpj:
                folder_path = sub_status
            else:
                prefix_emp = f"{emit_cnpj}_{nome_empresa.replace(' ', '_')[:25]}"
                folder_path = f"{prefix_emp}/{sub_status}"

            csv_rows.append([
                r["data_emissao"] or "",
                chave,
                r["numero"] or "",
                r["serie"] or "1",
                r["modelo"] or "55",
                emit_cnpj,
                nome_empresa,
                r["destinatario_nome"] or "",
                r["destinatario_cnpj"] or "",
                f"{val_tot:.2f}",
                situacao
            ])

            # 1. Procura o arquivo XML em disco ou no xml_raw
            xml_bytes = None
            if r.get("xml_raw"):
                xml_bytes = r["xml_raw"].encode("utf-8")
            else:
                fallback_path = os.path.join(XML_STORAGE_DIR, f"{chave}.xml")
                if os.path.exists(fallback_path):
                    with open(fallback_path, "rb") as f:
                        xml_bytes = f.read()

            # 2. Se não tiver XML em disco, sintetiza o XML oficial completo com dados dos produtos
            if not xml_bytes:
                try:
                    doc_detail = get_nfe_detail(chave)
                    if doc_detail:
                        xml_bytes = build_synthetic_nfe_xml(doc_detail)
                except Exception as ex:
                    print(f"Erro ao sintetizar XML para {chave}: {ex}")

            if xml_bytes:
                z.writestr(f"{folder_path}/{chave}.xml", xml_bytes)

        # Adiciona Relatório CSV Consolidado
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter=";", lineterminator="\n")
        writer.writerows(csv_rows)
        csv_filename = f"Relatorio_Faturamento_{competencia.replace('-', '_')}_{clean_cnpj or 'Consolidado'}.csv"
        z.writestr(csv_filename, csv_buffer.getvalue().encode("utf-8-sig"))

        # Adiciona Relatórios CSV Individuais por Empresa / Certificado
        if not clean_cnpj:
            for c_cnpj, emp_info in por_empresa.items():
                emp_rows = [csv_rows[0]] + [r for r in csv_rows[1:] if r[5] == c_cnpj]
                emp_csv_buf = io.StringIO()
                emp_writer = csv.writer(emp_csv_buf, delimiter=";", lineterminator="\n")
                emp_writer.writerows(emp_rows)
                prefix_emp = f"{c_cnpj}_{emp_info['nome'].replace(' ', '_')[:25]}"
                z.writestr(f"{prefix_emp}/Relatorio_Faturamento_{c_cnpj}_{competencia.replace('-', '_')}.csv", emp_csv_buf.getvalue().encode("utf-8-sig"))

        # Adiciona Resumo Executivo em TXT para a Contabilidade
        txt_resumo = "===========================================================\n"
        txt_resumo += f"FECHAMENTO FISCAL & CONTÁBIL MENSAL - COMPETÊNCIA {mes:02d}/{ano}\n"
        txt_resumo += "===========================================================\n\n"
        txt_resumo += f"Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        txt_resumo += f"Total de NF-e Emitidas no Período: {len(rows)}\n"
        txt_resumo += f"  • Autorizadas: {total_autorizadas}\n"
        txt_resumo += f"  • Canceladas: {total_canceladas}\n"
        txt_resumo += f"Faturamento Total Consolidado: R$ {faturamento_total:,.2f}\n\n"
        txt_resumo += "DETALHAMENTO POR CERTIFICADO / EMPRESA:\n"
        txt_resumo += "-----------------------------------------------------------\n"
        for c_cnpj, emp_info in por_empresa.items():
            txt_resumo += f"• CNPJ: {c_cnpj} - {emp_info['nome']}\n"
            txt_resumo += f"  Qtd Notas: {emp_info['qtd']} | Faturamento: R$ {emp_info['valor']:,.2f}\n\n"
        txt_resumo += "-----------------------------------------------------------\n"
        txt_resumo += "Pacote gerado automaticamente pelo Sistema de Gestão Fiscal NF-e."

        z.writestr(f"RESUMO_EXECUTIVO_FECHAMENTO_{competencia.replace('-', '_')}.txt", txt_resumo.encode("utf-8-sig"))

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    cnpj_suffix = f"_{clean_cnpj}" if clean_cnpj else "_Todas_Filiais"
    filename = f"Fechamento_Fiscal_{competencia.replace('-', '_')}{cnpj_suffix}.zip"

    stats = {
        "competencia": f"{mes:02d}/{ano}",
        "competencia_label": _fmt_competencia_label(mes, ano),
        "total_notas": len(rows),
        "autorizadas": total_autorizadas,
        "canceladas": total_canceladas,
        "faturamento_total": float(faturamento_total),
        "arquivo": filename,
        "tamanho_bytes": len(zip_bytes),
        "por_empresa": {k: {"nome": v["nome"], "qtd": v["qtd"], "valor": float(v["valor"])} for k, v in por_empresa.items()}
    }

    return zip_bytes, filename, stats


# ====================================================================
# MONITOR DE STATUS DO SERVIÇO SEFAZ EM TEMPO REAL (SEMÁFORO)
# ====================================================================

def consultar_status_servico_sefaz(
    empresa_cnpj: Optional[str] = None,
    homologacao: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Consulta oficial do ``NFeStatusServico4`` e mede o tempo de resposta (ms).

    O semáforo só acende verde com **cStat 107 real**. Qualquer falha de
    comunicação devolve ``online=False`` — nunca simula operação.
    """
    import time

    is_homolog = homologacao if homologacao is not None else getattr(settings, "HOMOLOGACAO", True)

    # Seleciona certificado (o WS de status exige certificado cliente)
    cert_rec = None
    if empresa_cnpj:
        clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit())
        cert_rec = get_certificate_record(clean_cnpj)

    if not cert_rec:
        certs = list_certificates_db()
        cert_rec = certs[0] if certs else None

    if not cert_rec:
        return {
            "online": False,
            "c_stat": "999",
            "x_motivo": "Nenhum certificado A1 configurado no sistema.",
            "tempo_resposta_ms": 0,
            "ambiente": "Homologação" if is_homolog else "Produção",
            "uf": settings.DEFAULT_UF,
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

    if not cert_rec.get("path") or not os.path.exists(cert_rec["path"]):
        return {
            "online": False,
            "c_stat": "999",
            "x_motivo": f"Arquivo do certificado A1 não encontrado para o CNPJ {cert_rec.get('cnpj')}.",
            "tempo_resposta_ms": 0,
            "ambiente": "Homologação" if is_homolog else "Produção",
            "uf": str(cert_rec.get("uf") or settings.DEFAULT_UF).upper(),
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

    uf = str(cert_rec.get("uf") or settings.DEFAULT_UF).upper()
    start_time = time.time()
    try:
        # ComunicacaoSefaz(uf, certificado, certificado_senha, homologacao=...)
        con = ComunicacaoSefaz(uf, cert_rec["path"], cert_rec["password"], homologacao=is_homolog)
        resp = con.status_servico("nfe", timeout=SEFAZ_TIMEOUT)
        elapsed_ms = int((time.time() - start_time) * 1000)

        corpo = getattr(resp, "text", "") or ""
        status_http = getattr(resp, "status_code", None)
        if status_http not in (None, 200):
            return {
                "online": False,
                "c_stat": str(status_http),
                "x_motivo": f"HTTP {status_http} no webservice de status da SEFAZ.",
                "tempo_resposta_ms": elapsed_ms,
                "ambiente": "Homologação" if is_homolog else "Produção",
                "uf": uf,
                "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            }

        retorno = _extrair_retorno_consulta(corpo)
        c_stat = retorno["c_stat"] or "999"
        x_motivo = retorno["motivo"] or retorno["erro"] or "Sem descrição retornada pela SEFAZ."

        return {
            "online": c_stat == "107",
            "c_stat": c_stat,
            "x_motivo": x_motivo,
            "tempo_resposta_ms": elapsed_ms,
            "ambiente": "Homologação" if is_homolog else "Produção",
            "uf": uf,
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning("[SEFAZ STATUS] Falha ao consultar status (%s): %s", uf, exc)
        return {
            "online": False,
            "c_stat": "999",
            "x_motivo": f"Falha de comunicação com a SEFAZ-{uf}: {exc}",
            "tempo_resposta_ms": elapsed_ms,
            "ambiente": "Homologação" if is_homolog else "Produção",
            "uf": uf,
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
