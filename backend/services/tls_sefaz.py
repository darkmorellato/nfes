"""
Verificação TLS das chamadas ao webservice da SEFAZ.

Por quê: a biblioteca PyNFe chama ``requests.post(..., verify=False)`` de forma
irrecuperável (``pynfe/processamento/comunicacao.py``). Sem verificação, um
atacante na mesma rede pode se passar pela SEFAZ e devolver um ``cStat 100``
falso — o sistema gravaria a nota como autorizada sem que ela exista.

O problema prático é que o bundle de CAs do sistema geralmente **não** traz a
cadeia ICP-Brasil, então ligar ``verify=True`` puro falharia com
``unable to get local issuer certificate``. A solução aqui é fixar a própria
autoridade emissora dos servidores da SEFAZ:

    AC SOLUTI SSL EV G4 (ICP-Brasil) — válida até 2032
    baixada da AIA publicada pelos próprios hosts da SEFAZ-SP

Com ela em ``backend/security/sefaz_ca.pem``, a cadeia ``leaf → AC SOLUTI SSL EV G4``
fecha mesmo quando o certificado de servidor rotaciona.

Comportamento:

* ``SEFAZ_VERIFY_TLS=true`` (padrão) → toda URL ``*.gov.br`` usa o bundle fixado.
* ``SEFAZ_VERIFY_TLS=false`` → comportamento original (sem verificação), para
  ambientes de emergência. O motivo é registrado em log.
* Se a cadeia mudar, a falha é reportada com instrução de correção em vez de
  cair silencioso.
"""
from __future__ import annotations

import logging
import os
import ssl
from typing import Optional
from urllib.parse import urlparse

import requests

from backend.config import settings

logger = logging.getLogger("nfe.tls")

BUNDLE_PADRAO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "security",
    "sefaz_ca.pem",
)

_original_request = requests.Session.request
_aplicado = False


def caminho_bundle() -> str:
    """Caminho do bundle de CAs usado na verificação (env > arquivo versionado)."""
    return os.environ.get("SEFAZ_CA_BUNDLE") or settings.SEFAZ_CA_BUNDLE or BUNDLE_PADRAO


def host_governo(url: str) -> bool:
    """True para URLs de órgãos públicos (``*.gov.br``) — todos os WS da SEFAZ."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    return host.endswith("gov.br")


def bundle_disponivel() -> bool:
    try:
        return os.path.isfile(caminho_bundle())
    except Exception:
        return False


def status_tls() -> dict:
    """Estado da verificação TLS, exposto em ``/health`` para conferência."""
    ativo = bool(getattr(settings, "SEFAZ_VERIFY_TLS", False)) and bundle_disponivel() and _aplicado
    return {
        "verificacao_ativa": ativo,
        "configurado": bool(getattr(settings, "SEFAZ_VERIFY_TLS", False)),
        "bundle": os.path.basename(caminho_bundle()) if bundle_disponivel() else None,
    }


def aplicar_verificacao_tls() -> bool:
    """
    Intercepta ``requests.Session.request`` para forçar verificação nas URLs
    ``*.gov.br``, sobrescrevendo o ``verify=False`` embutido no PyNFe.

    Idempotente — pode ser chamada mais de uma vez.
    """
    global _aplicado
    if _aplicado:
        return settings.SEFAZ_VERIFY_TLS and bundle_disponivel()

    if not settings.SEFAZ_VERIFY_TLS:
        logger.warning(
            "[TLS] Verificação TLS da SEFAZ DESATIVADA (SEFAZ_VERIFY_TLS=false). "
            "As respostas do webservice não são autenticadas — um atacante na "
            "mesma rede poderia forjar uma autorização. Use apenas em emergência."
        )
        _aplicado = True
        return False

    if not bundle_disponivel():
        logger.error(
            "[TLS] Bundle de CAs da SEFAZ não encontrado em %s — a verificação "
            "TLS continuará DESATIVADA até o arquivo existir. Gere-o com: "
            "openssl s_client -showcerts -connect nfe.fazenda.sp.gov.br:443",
            caminho_bundle(),
        )
        _aplicado = True
        return False

    bundle = caminho_bundle()
    modo = {"ativo": False}

    def _request(self, method, url, *args, **kwargs):
        if host_governo(str(url)):
            kwargs["verify"] = bundle
            modo["ativo"] = True
        return _original_request(self, method, url, *args, **kwargs)

    requests.Session.request = _request  # type: ignore[method-assign]
    _aplicado = True
    logger.info(
        "[TLS] Verificação TLS ativa para *.gov.br com o bundle %s (SEFAZ_VERIFY_TLS=true).",
        bundle,
    )
    return True


def mensagem_erro_tls(exc: BaseException) -> Optional[str]:
    """
    Devolve uma mensagem acionável quando a falha é de verificação de certificado.

    Sem isto o operador veria apenas "certificate verify failed", sem saber que
    a cadeia ICP-Brasil mudou nem como desativar temporariamente.
    """
    atual = exc
    while atual is not None:
        if isinstance(atual, ssl.SSLCertVerificationError):
            # verify_message só existe quando a exceção veio do handshake real.
            detalhe = getattr(atual, "verify_message", None) or str(atual)
            return (
                f"Falha na verificação TLS do webservice da SEFAZ: {detalhe}. "
                "A cadeia ICP-Brasil pode ter sido renovada — atualize "
                "backend/security/sefaz_ca.pem (openssl s_client -showcerts -connect "
                "nfe.fazenda.sp.gov.br:443) ou, em emergência, defina SEFAZ_VERIFY_TLS=false."
            )
        if isinstance(atual, requests.exceptions.SSLError):
            return mensagem_erro_tls(atual.args[0] if atual.args else exc) or str(atual)
        atual = atual.__cause__ or atual.__context__
    return None


def verificar_cadeia(host: str, port: int = 443, timeout: int = 15):
    """Abre um handshake TLS contra ``host`` usando o bundle fixado."""
    import socket

    resultado = {"host": host, "ok": False, "detalhe": "", "subject": "", "issuer": ""}
    if not bundle_disponivel():
        resultado["detalhe"] = f"bundle ausente: {caminho_bundle()}"
        return resultado
    try:
        ctx = ssl.create_default_context(cafile=caminho_bundle())
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as sock:
                cert = sock.getpeercert()
        resultado["ok"] = True
        resultado["subject"] = dict(x[0] for x in cert.get("subject", ())).get("commonName", "")
        resultado["issuer"] = dict(x[0] for x in cert.get("issuer", ())).get("commonName", "")
        resultado["detalhe"] = "cadeia validada"
    except ssl.SSLCertVerificationError as e:
        resultado["detalhe"] = e.verify_message or str(e)
    except Exception as e:
        resultado["detalhe"] = f"{type(e).__name__}: {e}"
    return resultado
