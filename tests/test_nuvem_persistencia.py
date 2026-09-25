"""
Durabilidade dos documentos fiscais no Cloud Firestore.

Objetivo declarado: o Firestore é o guarda para não perder dados. Fazê-lo de
verdade exige que o **XML** (o documento com valor jurídico) suba junto — não
apenas os metadados. Antes desta correção, a nuvem tinha só a capa: se o disco
local morresse, os XMLs de compra/venda não existiriam em lugar nenhum.

Também se garante o caminho de volta (pull), que restaura o arquivo em
``data/xmls/`` numa instalação nova.
"""
import os

import pytest

from backend.database import get_db_connection, save_nfe_doc

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHAVE_TESTE = "35260113787408000105550010000007711000000555"
XML_NFEPROC = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    "<NFe><infNFe Id=\"NFe" + CHAVE_TESTE + "\" versao=\"4.00\">"
    "<ide><cUF>35</cUF><mod>55</mod><serie>1</serie><nNF>771</nNF></ide>"
    "</infNFe></NFe>"
    "<protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
    "<nProt>135260000000077</nProt><tpAmb>2</tpAmb></infProt></protNFe>"
    "</nfeProc>"
)


def _limpar():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM nfe_docs WHERE chave = ?", (CHAVE_TESTE,))
        conn.commit()


@pytest.fixture
def captura_sync(monkeypatch):
    """Grava o payload que sairia para o Firestore (a conftest o neutraliza)."""
    enviado = {}
    from backend.services import firestore_service as fs

    def gravar(payload):
        enviado["payload"] = payload

    monkeypatch.setattr(fs, "sync_single_nfe_async", gravar)
    return enviado


def test_xml_sobe_para_o_firestore(captura_sync):
    _limpar()
    doc = {
        "chave": CHAVE_TESTE,
        "empresa_cnpj": "13787408000105",
        "numero": "771",
        "serie": "1",
        "modelo": "55",
        "tipo_doc": 1,
        "emitente": {"nome": "EMITENTE", "cnpj": "13787408000105", "uf": "SP"},
        "destinatario": {"nome": "DEST", "cnpj": "12345678909", "uf": "SP"},
        "totais": {"v_nf": "100.00"},
        "situacao": "Autorizada",
    }
    try:
        assert save_nfe_doc(doc, xml_raw=XML_NFEPROC, empresa_cnpj="13787408000105")
        payload = captura_sync.get("payload")
        assert payload, "nada foi enviado ao Firestore"
        assert payload.get("xml_raw") == XML_NFEPROC, (
            "o XML não subiu para a nuvem — a perda do disco local perderia o documento"
        )
        assert payload["has_xml"] is True
    finally:
        _limpar()


def test_sem_xml_nao_inventa_campo(captura_sync):
    """Nota sem XML autorizado não pode mandar lixo para a nuvem."""
    _limpar()
    doc = {
        "chave": CHAVE_TESTE,
        "empresa_cnpj": "13787408000105",
        "numero": "772",
        "serie": "1",
        "modelo": "55",
        "tipo_doc": 1,
        "emitente": {"nome": "EMITENTE", "cnpj": "13787408000105", "uf": "SP"},
        "destinatario": {"nome": "DEST", "cnpj": "12345678909", "uf": "SP"},
        "situacao": "Pendente",
    }
    try:
        assert save_nfe_doc(doc, empresa_cnpj="13787408000105")
        payload = captura_sync.get("payload")
        assert payload is not None
        assert payload.get("xml_raw") in (None, ""), (
            "nota sem XML não deveria carregar xml_raw"
        )
    finally:
        _limpar()


def test_pull_repassa_o_xml_ao_salvar(monkeypatch):
    """O pull precisa passar o xml_raw recebido de volta ao save_nfe_doc."""
    from backend.services import firestore_service as fs

    capturado = {}

    monkeypatch.setattr(
        fs, "list_all_nfe_docs_from_firestore",
        lambda page_size=300: [{
            "chave": CHAVE_TESTE,
            "empresa_cnpj": "13787408000105",
            "numero": "773",
            "serie": "1",
            "tipo_doc": 1,
            "situacao": "Autorizada",
            "xml_raw": XML_NFEPROC,
        }],
    )
    monkeypatch.setattr(fs, "_list_itens_subcollection", lambda chave: [])

    import backend.database.nfe_docs as nfe_docs
    monkeypatch.setattr(nfe_docs, "save_nfe_doc", lambda d, xml_raw=None, empresa_cnpj=None, sync_remote=True: (
        capturado.update({"xml_raw": xml_raw, "chave": d.get("chave")}) or True
    ))

    res = fs.pull_from_firestore()

    assert res["imported"] == 1, res
    assert capturado.get("xml_raw") == XML_NFEPROC, (
        "o pull descartou o xml_raw vindo da nuvem — instalação nova ficaria sem XML"
    )


def test_pull_nao_reenvia_para_a_nuvem(monkeypatch):
    """
    O pull precisa salvar com ``sync_remote=False``.

    Sem isso ele baixava da nuvem e reenviava tudo em seguida: a cada startup
    eram ~1900 escritas repetidas, o plano Spark respondia ``429`` e a tela de
    login travava em "Verificando credenciais...".
    """
    from backend.services import firestore_service as fs

    chamadas = {}

    monkeypatch.setattr(
        fs, "list_all_nfe_docs_from_firestore",
        lambda page_size=300: [{
            "chave": CHAVE_TESTE, "empresa_cnpj": "13787408000105",
            "numero": "774", "serie": "1", "tipo_doc": 1,
            "situacao": "Autorizada", "xml_raw": XML_NFEPROC,
        }],
    )
    monkeypatch.setattr(fs, "_list_itens_subcollection", lambda chave: [])

    import backend.database.nfe_docs as nfe_docs
    monkeypatch.setattr(
        nfe_docs, "save_nfe_doc",
        lambda d, xml_raw=None, empresa_cnpj=None, sync_remote=True: (
            chamadas.update({"sync_remote": sync_remote}) or True
        ),
    )

    fs.pull_from_firestore()

    assert chamadas.get("sync_remote") is False, (
        "o pull reenviou dados para a nuvem — loop de escritas / cota Spark"
    )


def test_gravacao_local_pode_pular_a_nuvem(captura_sync):
    """sync_remote=False grava no SQLite mas não dispara Firestore."""
    _limpar()
    doc = {
        "chave": CHAVE_TESTE,
        "empresa_cnpj": "13787408000105",
        "numero": "775", "serie": "1", "modelo": "55", "tipo_doc": 1,
        "emitente": {"nome": "E", "cnpj": "13787408000105", "uf": "SP"},
        "destinatario": {"nome": "D", "cnpj": "12345678909", "uf": "SP"},
        "situacao": "Autorizada",
    }
    try:
        assert save_nfe_doc(doc, empresa_cnpj="13787408000105", sync_remote=False)
        assert "payload" not in captura_sync, "sync_remote=False ainda foi para a nuvem"
        # o registro local existe
        with get_db_connection() as conn:
            assert conn.execute(
                "SELECT 1 FROM nfe_docs WHERE chave = ?", (CHAVE_TESTE,)
            ).fetchone()
    finally:
        _limpar()


def test_login_nao_depende_da_auditoria_da_nuvem():
    """
    A tela de login não pode esperar o Firestore.

    O `await` da auditoria era feito ANTES de `setLoginLoading(false)`: com a
    cota do plano Spark estourada (HTTP 429) a promessa ficava pendurada e o
    usuário travava em "Verificando credenciais..." até recarregar o navegador.
    """
    src = open(os.path.join(RAIZ, "frontend", "js", "auth.js"), encoding="utf-8").read()

    assert "await firestoreDb" not in src, (
        "auth.js voltou a aguardar escrita do Firestore no caminho de login"
    )
    assert "registrarAcessoNoFirestore" in src

    # Analisa SÓ o bloco de sucesso, a partir do ponto em que o token já veio.
    inicio = src.index("AuthSession.senha_padrao = data.senha_padrao")
    bloco = src[inicio:src.index("} catch (err)", inicio)]

    ordem = [
        bloco.index("setLoginLoading(false);"),
        bloco.index("hideLoginOverlay();"),
        bloco.index("registrarAcessoNoFirestore();"),
    ]
    assert ordem == sorted(ordem), (
        "no bloco de sucesso a UI precisa ser liberada ANTES da auditoria: "
        "setLoginLoading(false) → hideLoginOverlay() → registrarAcessoNoFirestore()"
    )

    # a auditoria em si precisa de teto de tempo próprio
    decl = src.index("function registrarAcessoNoFirestore")
    corpo = src[decl:src.index("\n}", decl)]
    assert "Promise.race" in corpo and "setTimeout" in corpo, (
        "registrarAcessoNoFirestore precisa de teto (Promise.race + timeout)"
    )


def test_csp_permite_websocket_do_googleapis():
    """O SDK do Firestore usa transporte tempo real; sem wss:// o listener pendura."""
    from backend.main import _CSP
    connect = [p for p in _CSP.split(";") if p.strip().startswith("connect-src")][0]
    assert "wss://*.googleapis.com" in connect
    assert "https://*.googleapis.com" in connect
