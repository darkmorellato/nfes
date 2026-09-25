"""
Contingência de emissão (tpEmis) — NF-e em modo SEFAZ Virtual.

Regras cobertas aqui:

* ``tpEmis`` entra na chave de acesso (posição 34) e precisa estar certo
  **antes** da serialização;
* ``dhCont`` e ``xJust`` só existem quando há contingência, e a justificativa
  tem de ter 15–255 caracteres;
* o código 6/7 precisa coincidir com a SEFAZ Virtual que o PyNFe realmente
  usa para a UF (ele decide a URL pela UF e ignora o código que escrevemos);
* validação barra **antes** de reservar número e **antes** de chamar a SEFAZ.
"""
import os
import re

import pytest
from lxml import etree

from backend.database import get_db_connection, get_nfe_detail, get_next_nfe_number
from backend.services import nfe_emissao_service as svc
from backend.services.xsd_validator import validar_xml
from tests.test_integridade_fiscal import (  # fixtures: certificado real + payload
    CERT,
    CNPJ_EMIT,
    _limpar,
    _payload,
    pytestmark,  # noqa: F401  (skip se não houver .pfx)
)


# ====================================================================
# 1. Resolução/validação do tpEmis (sem rede, sem numeração)
# ====================================================================

def test_emissao_normal_nao_tem_justificativa():
    tp, just = svc.resolver_tp_emis({"tp_emis": 1}, "SP")
    assert tp == "1"
    assert just is None


def test_sem_contingencia_retorna_normal():
    tp, just = svc.resolver_tp_emis({}, "SP")
    assert (tp, just) == ("1", None)


def test_contingencia_sem_codigo_deriva_da_uf():
    """Pedir 'contingência' sem código deve resolver pelo estado do emitente."""
    tp, just = svc.resolver_tp_emis(
        {"contingencia": True, "contingencia_justificativa": "Falha no servidor da SEFAZ"},
        "SP",
    )
    assert tp == "6", "SP é atendida por SVC-AN (tpEmis 6)"
    # remover_acentos_sefaz normaliza para caixa alta (exigência do leiaute)
    assert just.upper().startswith("FALHA NO SERVIDOR")


def test_deriva_correta_por_uf():
    assert svc.tp_emis_svc_da_uf("SP") == "6"   # SVAN
    assert svc.tp_emis_svc_da_uf("MG") == "6"   # SVAN
    assert svc.tp_emis_svc_da_uf("AM") == "7"   # SVRS
    assert svc.tp_emis_svc_da_uf("PR") == "7"   # SVRS
    assert svc.tp_emis_svc_da_uf("XX") == ""


def test_tp_emis_errado_para_a_uf_e_rejeitado():
    with pytest.raises(ValueError, match="SEFAZ Virtual errada"):
        svc.resolver_tp_emis(
            {"tp_emis": 7, "contingencia_justificativa": "Falha no servidor da SEFAZ"},
            "SP",
        )


def test_tp_emis_nao_svc_e_rejeitado():
    """2/4/5 mudariam só o código, mas o PyNFe enviaria para a SEFAZ Virtual."""
    for codigo in ("2", "4", "5", "9"):
        with pytest.raises(ValueError, match="somente"):
            svc.resolver_tp_emis(
                {"tp_emis": codigo, "contingencia_justificativa": "Falha no servidor da SEFAZ"},
                "SP",
            )


def test_codigo_fora_da_tabela_e_rejeitado():
    with pytest.raises(ValueError, match="tabela oficial"):
        svc.resolver_tp_emis(
            {"tp_emis": 42, "contingencia_justificativa": "Falha no servidor da SEFAZ"},
            "SP",
        )


def test_justificativa_ausente_e_rejeitada():
    with pytest.raises(ValueError, match="15 caracteres"):
        svc.resolver_tp_emis({"contingencia": True}, "SP")


def test_justificativa_curta_e_rejeitada():
    with pytest.raises(ValueError, match="15 caracteres"):
        svc.resolver_tp_emis(
            {"contingencia": True, "contingencia_justificativa": "curta demais"},
            "SP",
        )


def test_justificativa_longa_e_rejeitada():
    with pytest.raises(ValueError, match="255"):
        svc.resolver_tp_emis(
            {"contingencia": True, "contingencia_justificativa": "x" * 300},
            "SP",
        )


def test_contingencia_invalida_nao_reserva_numero():
    """A validação tem de vir ANTES de consumir numeração fiscal."""
    antes = get_next_nfe_number(CNPJ_EMIT, serie="77", modelo="55")
    with pytest.raises(ValueError):
        svc.emitir_nfe_profissional(_payload(
            serie="77",
            contingencia=True,   # sem justificativa
        ))
    depois = get_next_nfe_number(CNPJ_EMIT, serie="77", modelo="55")
    assert depois == antes, "número foi reservado mesmo com payload inválido"


# ====================================================================
# 2. Emissão real em contingência (SEFAZ mockada)
# ====================================================================

def _mock_autorizacao(monkeypatch, capturado):
    def duplo(self, modelo, nota_fiscal, **kwargs):
        capturado["kwargs"] = kwargs
        capturado["xml"] = etree.tostring(nota_fiscal, encoding="unicode")
        proc = etree.Element("nfeProc", nsmap={None: "http://www.portalfiscal.inf.br/nfe"}, versao="4.00")
        proc.append(nota_fiscal)
        inf = etree.SubElement(etree.SubElement(proc, "protNFe", versao="4.00"), "infProt")
        for tag, valor in (
            ("tpAmb", "2"), ("verAplic", "SP_PL_009"),
            ("chNFe", nota_fiscal[0].get("Id", "").replace("NFe", "")),
            ("dhRecbto", "2026-01-01T10:00:00-03:00"),
            ("nProt", "135260000000099"), ("digVal", "AAAAAAAAAAAAAAAAAAAAAAAAAAA="),
            ("cStat", "100"), ("xMotivo", "Autorizado o uso da NF-e"),
        ):
            etree.SubElement(inf, tag).text = valor
        return (0, proc)

    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", duplo)


def _payload_contingencia(**sobre):
    base = _payload(
        serie="78",
        contingencia=True,
        contingencia_justificativa="SEFAZ indisponivel para a regiao de Piracicaba em 01/01/2026",
    )
    base.update(sobre)
    return base


def test_emissao_em_contingencia_usa_endpoint_sv(monkeypatch):
    capturado = {}
    _mock_autorizacao(monkeypatch, capturado)

    res = svc.emitir_nfe_profissional(_payload_contingencia())

    assert capturado["kwargs"].get("contingencia") is True, (
        "a chamada deve ir para o endpoint da SEFAZ Virtual"
    )
    assert res["contingencia"] is True
    assert res["tp_emis"] == 6
    assert res["autorizada"] is True
    _limpar(res["chave"])


def test_xml_de_contingencia_tem_tpmemis_dhcont_e_xjust(monkeypatch):
    capturado = {}
    _mock_autorizacao(monkeypatch, capturado)

    res = svc.emitir_nfe_profissional(_payload_contingencia())
    xml = capturado["xml"]

    assert "<tpEmis>6</tpEmis>" in xml, "tpEmis de contingência ausente"
    assert "<dhCont>" in xml, "dhCont obrigatório quando tpEmis != 1"
    assert "<xJust>SEFAZ INDISPONIVEL PARA A REGIAO DE PIRACICABA EM 01/01/2026</xJust>" in xml

    # tpEmis é a posição 34 da chave (índice 34), entre nNF(9) e cNF(8)
    assert res["chave"][34] == "6", f"chave sem tpEmis=6: {res['chave']}"

    erros = validar_xml(xml, esperado="NFe")
    assert erros == [], f"XML de contingência fora do leiaute: {erros}"
    _limpar(res["chave"])


def test_emissao_normal_nao_tem_dhcont(monkeypatch):
    capturado = {}
    _mock_autorizacao(monkeypatch, capturado)

    res = svc.emitir_nfe_profissional(_payload(serie="79"))
    xml = capturado["xml"]

    assert capturado["kwargs"].get("contingencia") is False
    assert "<tpEmis>1</tpEmis>" in xml
    assert "<dhCont>" not in xml
    assert "<xJust>" not in xml
    assert res["chave"][34] == "1"
    _limpar(res["chave"])


def test_tp_emis_e_persistido_no_banco(monkeypatch):
    capturado = {}
    _mock_autorizacao(monkeypatch, capturado)

    res = svc.emitir_nfe_profissional(_payload_contingencia())
    doc = get_nfe_detail(res["chave"])
    assert doc["tp_emis"] == 6, "tp_emis precisa ficar no banco para a consulta posterior"
    _limpar(res["chave"])


def test_consulta_de_nota_de_contingencia_usa_sv(monkeypatch):
    """reenviar/consulta deve ir para a SEFAZ Virtual da nota."""
    capturado = {}
    _mock_autorizacao(monkeypatch, capturado)
    res = svc.emitir_nfe_profissional(_payload_contingencia())
    chave = res["chave"]

    chamadas = {}
    origem = svc.ComunicacaoSefaz.consulta_nota

    def espia_consulta(self, modelo, chave=None, contingencia=False, **kw):
        chamadas["contingencia"] = contingencia

        class _R:
            status_code = 200
            text = (
                '<retConsSitNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
                "<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
                "<protNFe><infProt><nProt>135260000000099</nProt></infProt></protNFe>"
                "</retConsSitNFe>"
            )
        return _R()

    monkeypatch.setattr(svc.ComunicacaoSefaz, "consulta_nota", espia_consulta)
    out = svc.reenviar_nfe_sefaz(chave, homologacao=True)

    assert chamadas.get("contingencia") is True, (
        "nota de contingência consultada no endpoint normal"
    )
    assert out["c_stat"] == "100"
    _limpar(chave)
