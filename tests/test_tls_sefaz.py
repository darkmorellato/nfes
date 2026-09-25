"""
Verificação TLS dos webservices da SEFAZ.

O PyNFe chama ``requests.post(..., verify=False)`` sem possibilidade de
configuração — sem o patch, um atacante na mesma rede podia devolver um
``cStat 100`` falso e o sistema gravaria a nota como autorizada.
"""
import os
import ssl

import pytest

from backend.services import tls_sefaz


def test_bundle_de_cas_icp_brasil_esta_versionado():
    caminho = tls_sefaz.BUNDLE_PADRAO
    assert os.path.isfile(caminho), f"bundle ausente: {caminho}"

    from cryptography import x509
    cert = x509.load_pem_x509_certificate(open(caminho, "rb").read())
    sujeito = cert.subject.rfc4514_string()
    assert "AC SOLUTI SSL EV G4" in sujeito, sujeito
    assert "ICP-Brasil" in sujeito, sujeito
    # a cadeia precisa seguir válida por uns anos
    assert cert.not_valid_after_utc.year >= 2030


def test_host_governo_identifica_sefaz_e_ignora_o_resto():
    for url in (
        "https://nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        "https://www.nfe.fazenda.gov.br/ws/nfeconsultaprotocolo4",
        "https://www1.nfe.fazenda.gov.br/consulta",
    ):
        assert tls_sefaz.host_governo(url), f"deveria ser governo: {url}"

    for url in (
        "https://firestore.googleapis.com/v1/projects/x",
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        "https://cdn.jsdelivr.net/npm/chart.js",
        "http://192.168.3.97:8000/api/gestao/rede/exportar-dados",
        "not-a-url",
        "",
    ):
        assert not tls_sefaz.host_governo(url), f"não é governo: {url}"


def test_patch_forca_verify_bundle_nas_urls_de_governo(monkeypatch):
    """O wrapper deve sobrescrever o verify=False do PyNFe apenas em *.gov.br."""
    capturado = {}

    def original(self, method, url, *args, **kwargs):
        capturado["verify"] = kwargs.get("verify")
        capturado["url"] = url
        return None

    monkeypatch.setattr(tls_sefaz, "_original_request", original)
    monkeypatch.setattr(tls_sefaz, "_aplicado", False)
    monkeypatch.setattr("backend.config.settings.SEFAZ_VERIFY_TLS", True)
    monkeypatch.setattr(
        "backend.config.settings.SEFAZ_CA_BUNDLE", tls_sefaz.BUNDLE_PADRAO
    )

    assert tls_sefaz.aplicar_verificacao_tls() is True

    class _Sessao:
        pass

    from requests import Session
    sessao = Session.__new__(Session)

    # URL de governo → verify passa a ser o bundle fixado
    Session.request(sessao, "POST", "https://nfe.fazenda.sp.gov.br/ws/x.asmx", verify=False)
    assert capturado["verify"] == tls_sefaz.BUNDLE_PADRAO, (
        "o verify=False do PyNFe não foi sobrescrito"
    )

    # URL externa → mantém o valor original (não quebra o resto do sistema)
    Session.request(sessao, "POST", "https://api.example.com/x", verify=False)
    assert capturado["verify"] is False


def test_desativacao_e_explicita_e_registrada(monkeypatch, caplog):
    monkeypatch.setattr(tls_sefaz, "_aplicado", False)
    monkeypatch.setattr("backend.config.settings.SEFAZ_VERIFY_TLS", False)

    with caplog.at_level("WARNING", logger="nfe.tls"):
        assert tls_sefaz.aplicar_verificacao_tls() is False

    assert any("DESATIVADA" in r.message for r in caplog.records), (
        "desativar a verificação TLS precisa gerar aviso em log"
    )


def test_mensagem_erro_tls_e_acionavel():
    causa = ssl.SSLCertVerificationError("certificate verify failed: unable to get local issuer")
    envolucro = RuntimeError("falha ao transmitir")
    envolucro.__cause__ = causa

    msg = tls_sefaz.mensagem_erro_tls(envolucro)
    assert msg is not None
    assert "SEFAZ_VERIFY_TLS" in msg, "a mensagem precisa dizer como contornar"
    assert "sefaz_ca.pem" in msg, "a mensagem precisa dizer como corrigir"


def test_mensagem_erro_tls_ausente_para_erro_comum():
    assert tls_sefaz.mensagem_erro_tls(ValueError("qualquer coisa")) is None


def test_bundle_padrao_e_lido_por_settings():
    from backend.config import settings
    # o default do settings vem do ambiente; o arquivo versionado é o fallback
    assert settings.SEFAZ_VERIFY_TLS in (True, False)
    assert isinstance(settings.SEFAZ_CA_BUNDLE, str)


def test_health_expoe_status_do_tls():
    """/health atesta ao operador que a verificação TLS está de fato ativa."""
    from fastapi.testclient import TestClient
    from backend.main import app

    corpo = TestClient(app).get("/health").json()
    tls = corpo.get("sefaz_tls")
    assert isinstance(tls, dict), "o /health precisa expor sefaz_tls"
    assert set(tls) >= {"verificacao_ativa", "configurado", "bundle"}
    # no ambiente de teste o bundle versionado existe e a conftest aplica o patch
    assert tls["bundle"] == "sefaz_ca.pem"
    assert tls["verificacao_ativa"] is True, (
        "a verificação TLS deveria estar ativa com o bundle versionado presente"
    )
