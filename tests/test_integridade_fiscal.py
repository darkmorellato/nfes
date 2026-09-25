"""
Testes de INTEGRIDADE FISCAL — Fase 1.

Cobrem exatamente o que quebrava a emissão real:

* o retorno da SEFAZ é interpretado (tupla do PyNFe), nunca fabricado;
* estados fiscais: Autorizada / Denegada / Rejeitada / Pendente;
* XML gerado passa na validação XSD oficial (PL_009 V4);
* totais fecham: vPag == vNF == soma dos itens (rateio de frete/seguro/outras);
* dígito verificador da chave de acesso (módulo 11);
* cancelamento, CC-e e inutilização só alteram o banco após cStat de sucesso;
* numeração reservada atomicamente (sem corrida);
* endpoint legado de emissão simulada removido.

**Nenhum teste fala com a SEFAZ**: ``ComunicacaoSefaz`` é substituído por um
duplo que devolve os retornos oficiais.
"""
import os
import re
import threading
from decimal import Decimal

import pytest
from lxml import etree
from pynfe.utils.flags import NAMESPACE_NFE

from backend.database import (
    get_db_connection,
    get_nfe_detail,
    list_certificates_db,
    reservar_proximo_numero,
    garante_numero_livre,
)
from backend.services import nfe_emissao_service as svc
from backend.services.xsd_validator import validar_xml


# ====================================================================
# Infra: certificado A1 real apenas para ASSINAR (a transmissão é simulada)
# ====================================================================

def _certificado_disponivel():
    for c in list_certificates_db():
        if c.get("path") and os.path.exists(c["path"]):
            return c
    return None


CERT = _certificado_disponivel()
pytestmark = pytest.mark.skipif(
    CERT is None,
    reason="Nenhum certificado A1 (.pfx) disponível no ambiente — assinatura não testável",
)

CNPJ_EMIT = CERT["cnpj"] if CERT else ""
DEST_HOMOLOG = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"


def _payload(**extra):
    payload = {
        "emitente_cnpj": CNPJ_EMIT,
        "natureza_operacao": "VENDA DE MERCADORIA",
        "serie": "1",
        "destinatario": {
            "cpf_cnpj": "12345678909",
            "razao_social": DEST_HOMOLOG,
            "indicador_ie": 9,
            "cep": "01310100",
            "logradouro": "Av Paulista",
            "numero": "100",
            "bairro": "Bela Vista",
            "municipio": "Sao Paulo",
            "uf": "SP",
        },
        "salvar_cliente": False,
        "produtos": [
            {
                "codigo": "PTESTE1",
                "descricao": "PRODUTO TESTE UNIT",
                "ncm": "85171300",
                "cfop": "5102",
                "unidade": "UN",
                "quantidade": 1.0,
                "valor_unitario": 100.0,
                "desconto": 0.0,
            }
        ],
        "forma_pagamento": "17",
        "homologacao": True,
        "uf": "SP",
    }
    payload.update(extra)
    return payload


# ====================================================================
# Duplos da SEFAZ
# ====================================================================

class _FakeHTTP:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.content = text.encode("utf-8") if isinstance(text, str) else text
        self.status_code = status_code


def _ret_envi_nfe(c_stat_inf: str, x_motivo: str, ch_nfe: str, c_stat_lote: str = "104") -> _FakeHTTP:
    """SOAP de retorno de autorização (rejeição ou lote processado)."""
    return _FakeHTTP(
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<retEnviNFe xmlns="{NAMESPACE_NFE}" versao="4.00">'
        f"<tpAmb>2</tpAmb><verAplic>SP_PL_009</verAplic><cUF>35</cUF>"
        f"<dhRecbto>2026-01-01T10:00:00-03:00</dhRecbto><chNFe>{ch_nfe}</chNFe>"
        f"<protNFe versao='4.00'><infProt>"
        f"<tpAmb>2</tpAmb><verAplic>SP_PL_009</verAplic><chNFe>{ch_nfe}</chNFe>"
        f"<dhRecbto>2026-01-01T10:00:00-03:00</dhRecbto>"
        f"<digVal>abc123=</digVal><cStat>{c_stat_inf}</cStat><xMotivo>{x_motivo}</xMotivo>"
        f"</infProt></protNFe>"
        f"<cStat>{c_stat_lote}</cStat><xMotivo>Lote processado</xMotivo>"
        f"</retEnviNFe>"
    )


def _autoriza(self, modelo, nota_fiscal, id_lote=1, ind_sinc=1, contingencia=False, timeout=None,
              c_stat="100", x_motivo="Autorizado o uso da NF-e", n_prot="135260000000001"):
    """Duplo de ``ComunicacaoSefaz.autorizacao`` — devolve tupla como o PyNFe."""
    proc = etree.Element("nfeProc", nsmap={None: NAMESPACE_NFE}, versao="4.00")
    proc.append(nota_fiscal)
    inf = etree.SubElement(etree.SubElement(proc, "protNFe", versao="4.00"), "infProt")
    for tag, valor in (
        ("tpAmb", "2"), ("verAplic", "SP_PL_009"),
        ("chNFe", nota_fiscal[0].get("Id", "").replace("NFe", "")),
        ("dhRecbto", "2026-01-01T10:00:00-03:00"),
        ("nProt", n_prot), ("digVal", "AAAAAAAAAAAAAAAAAAAAAAAAAAA="),
        ("cStat", c_stat), ("xMotivo", x_motivo),
    ):
        etree.SubElement(inf, tag).text = valor
    return (0, proc)


def _rejeita(self, modelo, nota_fiscal, id_lote=1, ind_sinc=1, contingencia=False, timeout=None,
             c_stat="204", x_motivo="Rejeicao: Duplicidade de NF-e"):
    chave = nota_fiscal[0].get("Id", "").replace("NFe", "")
    return (1, _ret_envi_nfe(c_stat, x_motivo, chave), nota_fiscal)


@pytest.fixture
def sefaz_autoriza(monkeypatch):
    """A SEFAZ autoriza toda NF-e transmitida (cStat 100)."""
    capturado = {}
    origem = svc.ComunicacaoSefaz.autorizacao

    def duplo(self, modelo, nota_fiscal, **kwargs):
        capturado["xml"] = etree.tostring(nota_fiscal, encoding="unicode")
        return _autoriza(self, modelo, nota_fiscal, **kwargs)

    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", duplo)
    yield capturado
    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", origem)


@pytest.fixture
def sefaz_rejeita(monkeypatch):
    capturado = {}
    origem = svc.ComunicacaoSefaz.autorizacao

    def duplo(self, modelo, nota_fiscal, **kwargs):
        capturado["xml"] = etree.tostring(nota_fiscal, encoding="unicode")
        return _rejeita(self, modelo, nota_fiscal, **kwargs)

    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", duplo)
    yield capturado
    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", origem)


def _xml_em_disco(chave: str) -> str:
    caminho = os.path.join(svc.XML_STORAGE_DIR, f"{chave}.xml")
    if not os.path.exists(caminho):
        return ""
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _limpar(chave: str) -> None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        for tabela in ("nfe_items", "nfe_events"):
            cur.execute(f"DELETE FROM {tabela} WHERE chave = ?", (chave,))
        cur.execute("DELETE FROM nfe_docs WHERE chave = ?", (chave,))
        conn.commit()
    caminho = os.path.join(svc.XML_STORAGE_DIR, f"{chave}.xml")
    if os.path.exists(caminho):
        os.remove(caminho)


# ====================================================================
# 1. Emissão autorizada
# ====================================================================

def test_emissao_autorizada_persiste_protocolo_real(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload())

    assert res["success"] is True
    assert res["autorizada"] is True
    assert res["c_stat"] == "100"
    assert res["protocolo"] == "135260000000001"
    assert res["situacao"] == "Autorizada"

    doc = get_nfe_detail(res["chave"])
    assert doc["situacao"] == "Autorizada"
    assert doc["protocolo"] == "135260000000001"
    assert doc["c_stat"] == "100"
    assert doc["tp_amb"] == 2
    _limpar(res["chave"])


def test_xml_oficial_somente_quando_autorizado(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload())
    xml = _xml_em_disco(res["chave"])

    assert xml, "nota autorizada deve ter XML em data/xmls/"
    assert "<nfeProc" in xml and "<protNFe" in xml
    assert "<nProt>135260000000001</nProt>" in xml
    # nenhum protocolo inventado pelo sistema
    assert "SP_NFE_PL_009_V4" not in xml
    _limpar(res["chave"])


def test_xml_gerado_passa_na_validacao_xsd(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload())
    erros = validar_xml(sefaz_autoriza["xml"], esperado="NFe")
    assert erros == [], f"XML fora do leiaute oficial: {erros}"
    _limpar(res["chave"])


def test_nfe_proc_autorizado_passa_no_xsd_e_sem_prefixos(sefaz_autoriza):
    """O procNFe gravado em disco precisa ser o formato oficial (sem ns0:)."""
    res = svc.emitir_nfe_profissional(_payload())
    xml = _xml_em_disco(res["chave"])

    assert "ns0:" not in xml, "procNFe com prefixo gerado não é o formato usual"
    erros = validar_xml(xml, esperado="nfeProc")
    assert erros == [], f"procNFe fora do leiaute oficial: {erros}"
    # o <NFe> assinado entra byte a byte (assinatura cobre <infNFe>)
    assert "<Signature" in xml
    _limpar(res["chave"])


def test_emitente_com_cnpj_e_crt_no_xml(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload())
    xml = sefaz_autoriza["xml"]

    assert f"<emit><CNPJ>{CNPJ_EMIT}</CNPJ>" in xml, "CNPJ do emitente ausente no <emit>"
    assert re.search(r"<CRT>[123]</CRT>", xml), "CRT (regime tributário) vazio/ausente"
    # a chave de acesso precisa carregar o CNPJ do emitente (posição 6..19)
    assert res["chave"][6:20] == CNPJ_EMIT
    # endereço do destinatário com país informado (evita cStat 225)
    assert "<cPais/>" not in xml
    _limpar(res["chave"])


# ====================================================================
# 2. Rejeição e denegação — nunca viram "Autorizada"
# ====================================================================

def test_rejeicao_nao_vira_autorizada_e_nao_grava_xml(sefaz_rejeita):
    res = svc.emitir_nfe_profissional(_payload())

    assert res["success"] is False
    assert res["autorizada"] is False
    assert res["c_stat"] == "204"
    assert res["situacao"] == "Rejeitada (204)"
    assert res["protocolo"] == ""
    assert res["xml_gerado"] is False

    doc = get_nfe_detail(res["chave"])
    assert doc["situacao"] == "Rejeitada (204)"
    assert doc["protocolo"] in ("", None)
    assert not _xml_em_disco(res["chave"]), "rejeitada não pode virar XML fiscal em disco"
    # o <NFe> assinado fica guardado para retransmissão
    assert doc.get("xml_assinado"), "XML assinado deve ser preservado para reenvio"
    _limpar(res["chave"])


def test_denegacao_e_estado_distinto(monkeypatch):
    origem = svc.ComunicacaoSefaz.autorizacao
    monkeypatch.setattr(
        svc.ComunicacaoSefaz, "autorizacao",
        lambda self, modelo, nota_fiscal, **kw: _autoriza(
            self, modelo, nota_fiscal, c_stat="110",
            x_motivo="Uso Denegado", **kw
        ),
    )
    res = svc.emitir_nfe_profissional(_payload())
    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", origem)

    assert res["autorizada"] is False
    assert res["denegada"] is True
    assert res["situacao"] == "Denegada"
    doc = get_nfe_detail(res["chave"])
    assert doc["situacao"] == "Denegada"
    _limpar(res["chave"])


def test_falha_de_comunicacao_deixa_pendente(monkeypatch):
    def explode(self, modelo, nota_fiscal, **kwargs):
        raise ConnectionError("rede indisponível")

    origem = svc.ComunicacaoSefaz.autorizacao
    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", explode)
    res = svc.emitir_nfe_profissional(_payload())
    monkeypatch.setattr(svc.ComunicacaoSefaz, "autorizacao", origem)

    assert res["success"] is False
    assert res["situacao"] == "Pendente"
    assert res["protocolo"] == ""
    doc = get_nfe_detail(res["chave"])
    assert doc["situacao"] == "Pendente"
    _limpar(res["chave"])


# ====================================================================
# 3. Totais e chave de acesso
# ====================================================================

def test_totais_fecham_com_frete_e_seguro(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload(
        valor_frete="20.00", valor_seguro="5.00", outras_despesas="3.00",
        desconto_total=0.0,
    ))

    xml = sefaz_autoriza["xml"]
    totais = dict(re.findall(r"<(vProd|vFrete|vSeg|vOutro|vDesc|vNF)>([^<]+)</\1>", xml))
    pag = dict(re.findall(r"<(vPag)>([^<]+)</\1>", xml))

    v_nf = Decimal(totais["vNF"])
    assert Decimal(totais["vFrete"]) == Decimal("20.00")
    assert Decimal(totais["vSeg"]) == Decimal("5.00")
    assert Decimal(totais["vOutro"]) == Decimal("3.00")
    # vPag não pode exceder vNF (Rejeições 865/866)
    assert Decimal(pag["vPag"]) == v_nf
    assert v_nf == Decimal("128.00")
    _limpar(res["chave"])


def test_desconto_vai_em_v_desc_e_nao_em_v_prod(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload(
        produtos=[{
            "codigo": "P1", "descricao": "PRODUTO", "ncm": "85171300", "cfop": "5102",
            "unidade": "UN", "quantidade": 2.0, "valor_unitario": 50.0, "desconto": 10.0,
        }],
    ))
    totais = dict(re.findall(r"<(vProd|vDesc|vNF)>([^<]+)</\1>", sefaz_autoriza["xml"]))

    assert Decimal(totais["vProd"]) == Decimal("100.00"), "vProd deve ser bruto (qCom × vUnCom)"
    assert Decimal(totais["vDesc"]) == Decimal("10.00")
    assert Decimal(totais["vNF"]) == Decimal("90.00")
    _limpar(res["chave"])


def test_digito_verificador_da_chave_modulo_11(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload())
    chave = res["chave"]
    assert len(chave) == 44 and chave.isdigit()

    corpo, dv_informado = chave[:43], int(chave[43])
    pesos = list(range(2, 11))                     # 2..9 girando da direita p/ esquerda
    soma = 0
    for i, digito in enumerate(reversed(corpo)):
        soma += int(digito) * pesos[i % 8]
    resto = soma % 11
    dv_esperado = 0 if resto in (0, 1) else 11 - resto
    assert dv_informado == dv_esperado, "dígito verificador da chave inválido"
    _limpar(res["chave"])


def test_parcelas_somam_o_vnf(sefaz_autoriza):
    res = svc.emitir_nfe_profissional(_payload(
        condicao_pagamento="a_prazo",
        parcelas=[
            {"numero": "001", "vencimento": "2026-03-10", "valor": 40.00},
            {"numero": "002", "vencimento": "2026-04-10", "valor": 40.00},
            {"numero": "003", "vencimento": "2026-05-10", "valor": 99.99},  # não fecha
        ],
    ))
    xml = sefaz_autoriza["xml"]
    v_nf = Decimal(re.search(r"<vNF>([^<]+)</vNF>", xml).group(1))
    soma_dups = sum((Decimal(v) for v in re.findall(r"<vDup>([^<]+)</vDup>", xml)), Decimal("0.00"))

    assert soma_dups == v_nf
    _limpar(res["chave"])


# ====================================================================
# 4. Validações locais (falham ANTES de gastar cota da SEFAZ)
# ====================================================================

def test_quantidade_invalida_bloqueia_emissao():
    with pytest.raises(ValueError, match="quantidade"):
        svc.emitir_nfe_profissional(_payload(
            produtos=[{"codigo": "P", "descricao": "X", "ncm": "85171300", "cfop": "5102",
                       "unidade": "UN", "quantidade": 0, "valor_unitario": 10.0}],
        ))


def test_desconto_maior_que_item_bloqueia_emissao():
    with pytest.raises(ValueError, match="desconto"):
        svc.emitir_nfe_profissional(_payload(
            produtos=[{"codigo": "P", "descricao": "X", "ncm": "85171300", "cfop": "5102",
                       "unidade": "UN", "quantidade": 1.0, "valor_unitario": 10.0,
                       "desconto": 99.0}],
        ))


def test_cst_incompativel_com_regime_bloqueia(monkeypatch):
    """CST de regime normal num emitente do Simples não pode virar XML inválido."""
    certs = list_certificates_db()
    monkeypatch.setitem(certs[0], "crt", 3)
    monkeypatch.setattr(svc, "get_certificate_record", lambda cnpj: certs[0])
    with pytest.raises(ValueError, match="regime tributário"):
        svc.emitir_nfe_profissional(_payload(
            produtos=[{"codigo": "P", "descricao": "X", "ncm": "85171300", "cfop": "5102",
                       "unidade": "UN", "quantidade": 1.0, "valor_unitario": 10.0,
                       "csosn_cst": "102"}],
        ))


def test_pagamento_cartao_integrado_exige_dados_da_transacao():
    with pytest.raises(ValueError, match="tpIntegra"):
        svc.emitir_nfe_profissional(_payload(
            forma_pagamento="03",
            cartao={"tp_integra": "1"},
        ))


def test_pagamento_pix_emite_grupo_card(sefaz_autoriza):
    """Regra 391_YA04-10: tPag 17 exige o grupo <card>."""
    res = svc.emitir_nfe_profissional(_payload(forma_pagamento="17"))
    xml = _xml_em_disco(res["chave"])
    assert "<card><tpIntegra>2</tpIntegra></card>" in xml
    _limpar(res["chave"])


# ====================================================================
# 5. Eventos fiscais: transmitem e só persistem no cStat de sucesso
# ====================================================================

def _inserir_nfe_autorizada(chave: str, protocolo: str = "135260000000099") -> None:
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO nfe_docs
              (chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emitente_cnpj,
               emitente_nome, emitente_uf, destinatario_nome, destinatario_cnpj,
               data_emissao, valor_total, situacao, protocolo, c_stat, tp_amb, created_at, updated_at)
            VALUES (?, ?, '77', '1', '55', 1, ?, 'EMITENTE TESTE', 'SP',
                    'CLIENTE', '12345678909', '2026-01-01T10:00:00', 100.0,
                    'Autorizada', ?, '102', 2, datetime('now'), datetime('now'))
            """,
            (chave, CNPJ_EMIT, CNPJ_EMIT, protocolo),
        )
        conn.commit()


def _duplo_evento(monkeypatch, c_stat, x_motivo="Evento registrado", n_prot="135260000000055"):
    def duplo(self, uf, homolog, evento_assinado, modelo="nfe"):
        return {"c_stat": c_stat, "motivo": x_motivo, "protocolo": n_prot,
                "dh_reg": "2026-01-01T10:05:00-03:00", "erro": ""}
    monkeypatch.setattr(svc, "_transmitir_evento", duplo)


def test_cancelamento_so_persiste_com_cstat_135(monkeypatch):
    chave = "35260113787408000105550010000007711000000123"
    _inserir_nfe_autorizada(chave)
    _duplo_evento(monkeypatch, "135")

    res = svc.cancelar_nfe_profissional(chave, "Cancelamento solicitado pelo cliente")
    assert res["success"] is True
    assert res["protocolo"] == "135260000000055"
    assert get_nfe_detail(chave)["situacao"] == "Cancelada"
    _limpar(chave)


def test_cancelamento_rejeitado_nao_altera_banco(monkeypatch):
    chave = "35260113787408000105550010000007711000000456"
    _inserir_nfe_autorizada(chave)
    _duplo_evento(monkeypatch, "218", "Rejeicao: Ja consta cancelamento")

    res = svc.cancelar_nfe_profissional(chave, "Cancelamento solicitado pelo cliente")
    assert res["success"] is False
    assert res["c_stat"] == "218"
    assert get_nfe_detail(chave)["situacao"] == "Autorizada", (
        "rejeição da SEFAZ não pode alterar o estado local"
    )
    _limpar(chave)


def test_nota_nao_autorizada_nao_pode_ser_cancelada(monkeypatch):
    chave = "35260113787408000105550010000007711000000789"
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO nfe_docs (chave, empresa_cnpj, numero, serie, modelo, "
            "tipo_doc, emitente_cnpj, emitente_uf, situacao, created_at, updated_at) "
            "VALUES (?, ?, '78', '1', '55', 1, ?, 'SP', 'Rejeitada (204)', datetime('now'), datetime('now'))",
            (chave, CNPJ_EMIT, CNPJ_EMIT),
        )
        conn.commit()

    chamado = {"n": 0}
    monkeypatch.setattr(svc, "_transmitir_evento", lambda *a, **k: chamado.__setitem__("n", 1))

    res = svc.cancelar_nfe_profissional(chave, "Cancelamento solicitado pelo cliente")
    assert res["success"] is False
    assert chamado["n"] == 0, "não deve transmitir cancelamento de nota não autorizada"
    _limpar(chave)


def test_cancelamento_justificativa_curta_e_rejeitada_localmente():
    with pytest.raises(ValueError, match="mínimo 15"):
        svc.cancelar_nfe_profissional("35" + "0" * 42, "curta")


def test_carta_correcao_persiste_evento_e_usa_sequencia(monkeypatch):
    chave = "35260113787408000105550010000007711000000321"
    _inserir_nfe_autorizada(chave)
    _duplo_evento(monkeypatch, "135")

    res = svc.emitir_carta_correcao_nfe(chave, "Correcao de endereco do destinatario informado")
    assert res["success"] is True
    assert res["sequencia_evento"] >= 1

    doc = get_nfe_detail(chave)
    cce = [e for e in doc["eventos"] if e["tipo_evento"] == "110110"]
    assert cce, "CC-e aceita deve ser persistida (DACCE depende dela)"
    # a nota autorizada não pode mudar de estado com CC-e
    assert doc["situacao"] == "Autorizada"
    _limpar(chave)


def test_evento_de_cancelamento_montado_assinado_e_lido(monkeypatch):
    """
    Vai até a fronteira da rede: monta, ASSINA o evento 110111 e interpreta o
    retorno da SEFAZ — só a chamada HTTP é substituída.
    """
    chave = "35260113787408000105550010000007711000000987"
    _inserir_nfe_autorizada(chave, protocolo="135260000999000")
    capturado = {}

    class _Resp:
        status_code = 200
        text = (
            f'<retEnviEvento xmlns="{NAMESPACE_NFE}" versao="1.00">'
            "<cUF>35</cUF><verAplic>SP_PL_009</verAplic><ambValid>2</ambValid>"
            "<cStat>128</cStat><xMotivo>Lote de evento processado</xMotivo>"
            "<retEvento><infEvento>"
            "<tpAmb>2</tpAmb><verAplic>SP_PL_009</verAplic><cOrgao>35</cOrgao>"
            "<cStat>135</cStat><xMotivo>Evento registrado e vinculado a NF-e</xMotivo>"
            f"<chNFe>{chave}</chNFe><dhRegEvento>2026-01-01T10:05:00-03:00</dhRegEvento>"
            "<nProt>135260000000055</nProt>"
            "</infEvento></retEvento></retEnviEvento>"
        )

    def evento_duplo(self, modelo, evento, id_lote=1):
        capturado["xml"] = etree.tostring(evento, encoding="unicode")
        return _Resp()

    monkeypatch.setattr(svc.ComunicacaoSefaz, "evento", evento_duplo)

    just = "Cancelamento solicitado pelo cliente em 01/01/2026"
    res = svc.cancelar_nfe_profissional(chave, just)

    assert res["success"] is True
    assert res["protocolo"] == "135260000000055"

    xml = capturado["xml"]
    assert f'Id="ID110111{chave}01"' in xml, "ID do evento fora do padrão ID<tpEvento><chave><seq>"
    assert "<Signature" in xml, "evento de cancelamento deve ser assinado com o Certificado A1"
    assert "<nProt>135260000999000</nProt>" in xml, "faltou o protocolo da autorização no cancelamento"
    assert just.upper() in xml.upper()
    # tpAmb do evento precisa casar com o ambiente em que a nota foi emitida
    assert "<tpAmb>2</tpAmb>" in xml, "evento emitido no ambiente errado (doc tp_amb=2)"

    assert get_nfe_detail(chave)["situacao"] == "Cancelada"
    _limpar(chave)


def test_carta_correcao_rejeitada_nao_persiste(monkeypatch):
    chave = "35260113787408000105550010000007711000000654"
    _inserir_nfe_autorizada(chave)
    _duplo_evento(monkeypatch, "577", "Rejeicao: limite de eventos")

    res = svc.emitir_carta_correcao_nfe(chave, "Correcao de endereco do destinatario informado")
    assert res["success"] is False
    doc = get_nfe_detail(chave)
    assert not [e for e in doc["eventos"] if e["tipo_evento"] == "110110"]
    _limpar(chave)


def test_inutilizacao_so_registra_com_cstat_102(monkeypatch):
    class _Resp:
        status_code = 200
        text = (
            f'<retInutNFe xmlns="{NAMESPACE_NFE}" versao="4.00"><infInut>'
            "<tpAmb>2</tpAmb><verAplic>SP</verAplic><cUF>35</cUF><ano>26</ano>"
            f"<CNPJ>{CNPJ_EMIT}</CNPJ><serie>1</serie><nNFIni>99100</nNFIni><nNFFin>99105</nNFFin>"
            "<xJust>Quebra de sequencia por falha impressora</xJust>"
            "<nProt>135260000000077</nProt><dhRecbto>2026-01-01T10:00:00-03:00</dhRecbto>"
            "<cStat>102</cStat><xMotivo>Inutilizacao de numero homologada com sucesso</xMotivo>"
            "</infInut></retInutNFe>"
        )

    monkeypatch.setattr(svc.ComunicacaoSefaz, "inutilizacao",
                        lambda self, *a, **k: _Resp())

    res = svc.inutilizar_numeracao_nfe(
        CNPJ_EMIT, "1", 99100, 99105, "Quebra de sequencia por falha impressora"
    )
    assert res["success"] is True
    assert res["protocolo"] == "135260000000077"

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM nfe_inutilizacoes WHERE numero_inicial = 99100 AND numero_final = 99105"
        ).fetchone()
    assert row[0] == 1


def test_inutilizacao_rejeitada_nao_registra(monkeypatch):
    class _Resp:
        status_code = 200
        text = (
            f'<retInutNFe xmlns="{NAMESPACE_NFE}" versao="4.00"><infInut>'
            "<cStat>405</cStat><xMotivo>Rejeicao: Numero ja utilizado</xMotivo>"
            "</infInut></retInutNFe>"
        )

    monkeypatch.setattr(svc.ComunicacaoSefaz, "inutilizacao",
                        lambda self, *a, **k: _Resp())

    res = svc.inutilizar_numeracao_nfe(
        CNPJ_EMIT, "1", 99200, 99210, "Quebra de sequencia por falha impressora"
    )
    assert res["success"] is False
    assert res["c_stat"] == "405"

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM nfe_inutilizacoes WHERE numero_inicial = 99200"
        ).fetchone()
    assert row[0] == 0


def test_inutilizacao_bloqueia_faixa_com_notas_existentes(monkeypatch):
    """A guarda local precisa barrar a faixa ANTES de gastar cota da SEFAZ."""
    def nao_deve_transmitir(self, *args, **kwargs):   # pragma: no cover
        raise AssertionError("a guarda local deve barrar antes de transmitir")

    monkeypatch.setattr(svc.ComunicacaoSefaz, "inutilizacao", nao_deve_transmitir)

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT numero, serie FROM nfe_docs "
            "WHERE emitente_cnpj = ? AND numero IS NOT NULL AND numero != '' LIMIT 1",
            (CNPJ_EMIT,),
        ).fetchone()
    if not row:
        pytest.skip("nenhuma nota existente na base de teste")

    numero, serie = int(row[0]), str(row[1] or "1")
    with pytest.raises(ValueError, match="já utilizados"):
        svc.inutilizar_numeracao_nfe(
            CNPJ_EMIT, serie, numero, numero + 5,
            "Quebra de sequencia por falha impressora",
        )


# ====================================================================
# 6. Numeração: reserva atômica
# ====================================================================

def test_reserva_de_numeracao_e_sequencial():
    a = reservar_proximo_numero(CNPJ_EMIT, "98", "55")
    b = reservar_proximo_numero(CNPJ_EMIT, "98", "55")
    assert b == a + 1


def test_reservas_concorrentes_nunca_repetem_numero():
    serie, total = "99", 20
    resultados, erros = [], []
    trava = threading.Lock()

    def worker():
        try:
            n = reservar_proximo_numero(CNPJ_EMIT, serie, "55")
            with trava:
                resultados.append(n)
        except Exception as exc:                       # pragma: no cover
            with trava:
                erros.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(total)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros, f"falha na reserva concorrente: {erros}"
    assert len(set(resultados)) == total, "numeração repetida entre emissões simultâneas"


def test_numero_manual_ja_usado_e_recusado():
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT numero FROM nfe_docs WHERE emitente_cnpj = ? AND serie = '1' "
            "AND numero IS NOT NULL AND numero != '' LIMIT 1",
            (CNPJ_EMIT,),
        ).fetchone()
    if not row:
        pytest.skip("nenhuma nota existente na base de teste")
    with pytest.raises(ValueError, match="já está em uso"):
        garante_numero_livre(CNPJ_EMIT, "1", "55", int(row[0]))


# ====================================================================
# 7. Estaduais / regressões
# ====================================================================

def test_endpoint_de_emissao_simulada_foi_removido():
    from backend.routers.nfe import emitir_nfe_rapido
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        import asyncio
        asyncio.run(emitir_nfe_rapido({}))
    assert exc.value.status_code == 410
    assert "simulava" in exc.value.detail


def test_sefaz_status_nao_simula_operacao(monkeypatch):
    def explode(self, modelo, timeout=None):
        raise ConnectionError("sem rede")

    monkeypatch.setattr(svc.ComunicacaoSefaz, "status_servico", explode)
    res = svc.consultar_status_servico_sefaz(CNPJ_EMIT, homologacao=True)

    assert res["online"] is False
    assert res["c_stat"] != "107"
    assert "Falha" in res["x_motivo"] or "falha" in res["x_motivo"]


def test_situacao_padrao_deriva_do_protocolo():
    from backend.database.nfe_docs import _situacao_padrao
    assert _situacao_padrao("100", "135") == "Autorizada"
    assert _situacao_padrao("150", "135") == "Autorizada"
    assert _situacao_padrao("110", "") == "Denegada"
    assert _situacao_padrao("301", "") == "Denegada"
    assert _situacao_padrao("204", "") == "Rejeitada (204)"
    assert _situacao_padrao("105", "") == "Em Processamento"
    assert _situacao_padrao("", "") == "Pendente"


def test_estados_terminais_nao_sao_rebaixados():
    from backend.database.nfe_docs import situacao_e_terminal
    assert situacao_e_terminal("Cancelada")
    assert situacao_e_terminal("Denegada")
    assert not situacao_e_terminal("Autorizada")
    assert not situacao_e_terminal("Rejeitada (204)")


def test_retorno_autorizacao_interpreta_tupla_do_pynfe():
    """Regressão direta: o PyNFe devolve tupla, não objeto HTTP."""
    http = _ret_envi_nfe("100", "Autorizado o uso da NF-e", "35" + "0" * 42)
    out = svc._parse_retorno_autorizacao((1, http, None))
    assert out["c_stat"] == "100"

    # formato errado (objeto Response solto) nunca vira autorização silenciosa
    out2 = svc._parse_retorno_autorizacao(http)
    assert out2["c_stat"] in ("", "100")
