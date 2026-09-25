"""
A tela "Minhas NF-e" precisa renderizar de verdade.

O bug que motivou este teste: um identificador solto dentro do
``JSON.stringify`` (``$event`` sem aspas) lançava ``ReferenceError`` no meio do
render, a promessa caía sem tratamento e a lista ficava **vazia** — com a API
respondendo 200 e 1899 notas. Sem erro visível para o usuário.

Estes testes renderizam a tabela com dados REAIS da API e ainda provam que o
teste tem poder de detecção (controle negativo).
"""
import json
import os
import secrets
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
node = shutil.which("node")

pytestmark = pytest.mark.skipif(node is None, reason="Node.js indisponível")

MODULO = os.path.join(RAIZ, "frontend", "js", "modules", "documentos.js")
HARNESS = os.path.join(RAIZ, "tests", "fixtures", "render_lista_check.js")


def _payload_documentos(limit=50):
    """Busca a resposta real de /api/gestao/documentos (usa a base isolada)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.routers.auth import save_session

    token = secrets.token_hex(16)
    save_session(token, {"email": "render@teste", "nome": "R", "perfil": "admin"})
    resp = TestClient(app).get(
        f"/api/gestao/documentos?page=1&limit={limit}",
        headers={"X-Session-Token": token},
    )
    assert resp.status_code == 200, f"API de documentos devolveu {resp.status_code}"
    return resp.json()


def _rodar(modulo, payload_path):
    return subprocess.run(
        [node, HARNESS, modulo, payload_path],
        capture_output=True, text=True, timeout=90, cwd=RAIZ,
    )


def test_tabela_minhas_nfe_renderiza(tmp_path):
    dados = _payload_documentos()
    documentos = dados.get("documentos", [])
    assert len(documentos) > 0, (
        "a base de teste não tem notas — o teste perderia o sentido"
    )

    arquivo = tmp_path / "documentos.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")

    proc = _rodar(MODULO, str(arquivo))
    assert proc.returncode == 0, (
        f"Minhas NF-e não renderizou:\n{proc.stdout}\n{proc.stderr}"
    )
    assert f"{len(documentos)} notas reais" in proc.stdout


def test_controle_negativo_detecta_marcador_solto(tmp_path):
    """Prova que o teste acima teria pegado o bug reportado."""
    origem = open(MODULO, encoding="utf-8").read()
    corrompido = origem.replace('"args": ["$event", d.chave]', '"args": [$event, d.chave]', 1)
    assert corrompido != origem, "o padrão do bug não foi encontrado para o controle"

    modulo_ruim = tmp_path / "documentos_bug.js"
    modulo_ruim.write_text(corrompido, encoding="utf-8")

    dados = _payload_documentos(limit=10)
    arquivo = tmp_path / "documentos.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")

    proc = _rodar(str(modulo_ruim), str(arquivo))
    assert proc.returncode != 0, (
        "o controle negativo passou: o teste de render não está detectando "
        "identificador solto dentro do JSON.stringify"
    )
    assert "$event is not defined" in (proc.stdout + proc.stderr)


def test_nenhum_marcador_delegacao_solto():
    """`$event`/`$this` só existem como STRING dentro do array de argumentos.

    Fora de aspas eles viram uma variável JS inexistente no momento do render.
    """
    import re
    from glob import glob

    solto = re.compile(r'(?<!["\'\\])\$(event|this)\b')
    problemas = []
    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True):
        for num, linha in enumerate(open(caminho, encoding="utf-8"), start=1):
            strip = linha.lstrip()
            if strip.startswith(("*", "//", "/*")):
                continue
            m = solto.search(linha)
            if m:
                problemas.append(f"{os.path.relpath(caminho, RAIZ)}:{num} → {m.group(0)}")

    assert not problemas, (
        "marcador de delegação sem aspas (ReferenceError no render):\n  "
        + "\n  ".join(problemas)
    )
