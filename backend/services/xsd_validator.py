"""
Validação de schema XSD dos leiautes oficiais da NF-e (PL_009 / versão 4.00).

Por quê: transmitir XML fora do leiaute consome a cota do certificado A1
(rejeição 656 "consumo indevido") e devolve cStat 215/225 sem dizer exatamente
o que está errado. Validar localmente antes do envio dá erro legível, imediato
e sem custo perante a SEFAZ.

Os XSDs versionados neste diretório são os publicados no leiaute final da NF-e
4.00 (PL_009 V4) — mesmos arquivos usados pelas SEFAZ.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from lxml import etree

XSD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "xsd", "nfe")

# Elemento-raiz → arquivo XSD que o define
SCHEMAS = {
    "NFe": "nfe_v4.00.xsd",
    "nfeProc": "procNFe_v4.00.xsd",
    "enviNFe": "enviNFe_v4.00.xsd",
    "retEnviNFe": "retEnviNFe_v4.00.xsd",
    "consSitNFe": "consSitNFe_v4.00.xsd",
    "consStatServ": "consStatServ_v4.00.xsd",
    "envEvento": "envEvento_v1.00.xsd",
    "evento": "leiauteEvento_v1.00.xsd",
    "inutNFe": "inutNFe_v4.00.xsd",
}


class XSDIndisponivel(Exception):
    """Os arquivos XSD não estão presentes no diretório ``backend/xsd/nfe``."""


@lru_cache(maxsize=len(SCHEMAS))
def _carregar_schema(nome_arquivo: str):
    caminho = os.path.join(XSD_DIR, nome_arquivo)
    if not os.path.exists(caminho):
        raise XSDIndisponivel(f"XSD não encontrado: {caminho}")
    # Resolver entidades apenas do disco local — nunca via rede.
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    with open(caminho, "rb") as f:
        schema_doc = etree.parse(f, parser)
    return etree.XMLSchema(schema_doc)


def _raiz(xml) -> str:
    if hasattr(xml, "tag"):
        tag = xml.tag
    else:
        texto = xml.decode("utf-8", errors="replace") if isinstance(xml, bytes) else str(xml)
        bruto = etree.fromstring(texto.encode("utf-8"))
        tag = bruto.tag
    if not isinstance(tag, str):        # comentário / PI
        return ""
    return etree.QName(tag).localname if tag.startswith("{") else str(tag)


def validar_xml(xml, esperado: str | None = None) -> List[str]:
    """
    Valida ``xml`` contra o XSD oficial correspondente.

    Retorna a lista de violações (vazia = válido). Se os XSDs não estiverem
    disponíveis, devolve uma lista com um único aviso — nunca quebra o fluxo
    por indisponibilidade do leiaute.
    """
    try:
        raiz_nome = esperado or _raiz(xml)
        nome_arquivo = SCHEMAS.get(raiz_nome)
        if not nome_arquivo:
            return [f"Sem XSD registrado para a raiz <{raiz_nome}> — validação ignorada."]
        schema = _carregar_schema(nome_arquivo)
    except XSDIndisponivel as exc:
        return [f"Leiaute XSD indisponível: {exc}"]
    except Exception as exc:                      # pragma: no cover - defensivo
        return [f"Falha ao carregar o XSD: {exc}"]

    try:
        if isinstance(xml, (str, bytes)):
            texto = xml.decode("utf-8", errors="replace") if isinstance(xml, bytes) else xml
            doc = etree.fromstring(texto.encode("utf-8"))
        else:
            doc = xml
    except Exception as exc:
        return [f"XML malformado: {exc}"]

    if schema.validate(doc):
        return []

    erros: List[str] = []
    for err in schema.error_log:
        caminho = f"{err.filename or ''}:{err.line}"
        erros.append(f"{caminho} {err.message}".strip())
    return erros or ["Violação de schema XSD não detalhada."]


def xml_valido(xml, esperado: str | None = None) -> bool:
    """True quando não há violações de leiaute (ou quando o XSD está ausente)."""
    erros = validar_xml(xml, esperado)
    return not erros or erros[0].startswith(("Sem XSD", "Leiaute XSD indisponível"))
