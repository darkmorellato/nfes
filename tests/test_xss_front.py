"""
Prova executável de que os handlers inline do front não permitem XSS.

O cenário real é: valor hostil → atributo HTML → parser decodifica entidades →
JavaScript avalia o handler. `escapeHtml` produz `&#39;`, que é decodificado de
volta para `'` ANTES do JS rodar — por isso era insuficiente aqui.

O teste roda o harness em Node (pulado quando `node` não está disponível).
"""
import os
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(RAIZ, "tests", "fixtures", "xss_check.js")
UTILS = os.path.join(RAIZ, "frontend", "js", "utils.js")

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="Node.js indisponível para o teste de XSS")


def test_handlers_inline_nao_permitem_xss():
    proc = subprocess.run(
        [node, HARNESS, UTILS],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=RAIZ,
    )
    assert proc.returncode == 0, f"XSS no handler inline:\n{proc.stdout}\n{proc.stderr}"


def test_escape_for_inline_handler_existe_no_utils():
    src = open(UTILS, encoding="utf-8").read()
    assert "function escapeForInlineHandler" in src
    # a ordem importa: & antes de qualquer outra substituição
    idx_amp = src.index("function escapeForInlineHandler")
    corpo = src[idx_amp:src.index("function cleanDigits")]
    assert corpo.index(".replace(/&/g") < corpo.index(".replace(/'/g"), (
        "o '&' precisa ser escapado primeiro, senão &#39; vindo do dado seria "
        "decodificado pelo HTML e reabriria a string JS"
    )


def test_nenhum_escape_html_dentro_de_onclick():
    """Nenhum handler inline pode usar escapeHtml (que é insuficiente)."""
    from glob import glob

    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "modules", "*.js")):
        for num, linha in enumerate(open(caminho, encoding="utf-8"), start=1):
            if "onclick=" in linha and "escapeHtml(" in linha:
                raise AssertionError(
                    f"{os.path.relpath(caminho, RAIZ)}:{num} usa escapeHtml dentro de onclick "
                    f"— use escapeForInlineHandler"
                )


# Valores vindos do servidor (mensagem da SEFAZ, detail do erro, etc.)
TOKENS_ARRISCADOS = (
    "data.detail", "res.message", "err.message", "res.data?.detail",
    "data.error", "${err}", "JSON.stringify",
)


def test_innerhtml_sem_escape_em_dados_do_servidor():
    """innerHTML com retorno da API/SEFAZ sem escape é XSS armazenado."""
    from glob import glob

    problemas = []
    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True):
        for num, linha in enumerate(open(caminho, encoding="utf-8"), start=1):
            if "innerHTML" not in linha or "${" not in linha:
                continue
            if "escapeHtml(" in linha or "escapeForInlineHandler(" in linha or "escapeInlineExpr(" in linha:
                continue
            # JSON.stringify + escapeAttrJson é o caminho seguro dos data-on*:
            # serializa os dados e só então escapa para o atributo HTML.
            if "escapeAttrJson(JSON.stringify(" in linha:
                continue
            if any(token in linha for token in TOKENS_ARRISCADOS):
                problemas.append(f"{os.path.relpath(caminho, RAIZ)}:{num}")

    assert not problemas, (
        "innerHTML com dado do servidor sem escapeHtml:\n  " + "\n  ".join(problemas)
    )


def test_funcoes_auxiliares_de_escapamento_existem():
    src = open(os.path.join(RAIZ, "frontend", "js", "utils.js"), encoding="utf-8").read()
    for nome in ("escapeHtml", "escapeForInlineHandler", "escapeInlineExpr", "formatCpfCnpj"):
        assert f"function {nome}" in src, f"{nome} ausente em utils.js"


def test_nenhuma_chamada_a_funcao_inexistente():
    """`formatarCpfCnpj` nunca existiu e o ReferenceError fechava o modal de
    inutilização. Vale para qualquer função auxiliar do front."""
    from glob import glob
    import re

    proibidas = re.compile(r"(?<![\w.])(formatarCpfCnpj)\s*\(")
    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True):
        for num, linha in enumerate(open(caminho, encoding="utf-8"), start=1):
            limpa = linha.split("//", 1)[0]
            if proibidas.search(limpa):
                raise AssertionError(
                    f"{os.path.relpath(caminho, RAIZ)}:{num} chama função inexistente "
                    f"formatarCpfCnpj() — use formatCpfCnpj() de utils.js"
                )


def test_respostas_da_api_sao_lidas_em_data():
    """apiGet/apiPost devolvem { success, data } — ler `res.X` direto quebra
    silenciosamente (clonar NF-e, DRE de produtos, próximo número)."""
    nfe_ops = open(os.path.join(RAIZ, "frontend", "js", "modules", "nfe-ops.js"), encoding="utf-8").read()
    financeiro = open(os.path.join(RAIZ, "frontend", "js", "modules", "financeiro.js"), encoding="utf-8").read()

    assert "res.data?.documento || res.documento" in nfe_ops, (
        "clonarNfeParaEmissao voltou a ler res.documento (o payload está em res.data)"
    )
    assert "res.data?.produtos || res.produtos" in financeiro, (
        "DRE de produtos voltou a ler res.produtos (o payload está em res.data)"
    )


# ====================================================================
# CSP sem 'unsafe-inline' (Fase 4)
# ====================================================================

# Objetos globais do navegador: não têm `function`/`=` no nosso código.
GLOBAIS_NAVEGADOR = {
    "window", "document", "navigator", "location", "console", "Math", "JSON",
    "Date", "setTimeout", "setInterval", "fetch", "alert", "confirm", "Event",
}

def _fontes_js():
    from glob import glob
    return (
        [os.path.join(RAIZ, "frontend", "index.html")]
        + glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True)
    )


def test_csp_nao_permite_script_inline():
    """O objetivo final da migração: script-src sem 'unsafe-inline'."""
    from backend.main import _CSP

    script_src = [p for p in _CSP.split(";") if p.strip().startswith("script-src")][0]
    assert "'unsafe-inline'" not in script_src, (
        f"script-src ainda permite inline: {script_src}"
    )
    assert "'self'" in script_src
    # estilos continuam inline (o index.html tem milhares de style="...")
    assert "style-src 'self' 'unsafe-inline'" in _CSP


def test_nenhum_handler_inline_no_frontend():
    """Nenhum on*= pode sobrar: o navegador bloquearia todos eles."""
    import re

    padrao = re.compile(r"(?<![\w-])on(?:click|change|submit|input|blur|focus|dblclick|keydown|keyup)=")
    problemas = []
    for caminho in _fontes_js():
        for num, linha in enumerate(open(caminho, encoding="utf-8"), start=1):
            strip = linha.lstrip()
            if strip.startswith(("*", "//", "/*")):
                continue
            if padrao.search(linha):
                problemas.append(f"{os.path.relpath(caminho, RAIZ)}:{num}")
    assert not problemas, "handlers inline sobraram:\n  " + "\n  ".join(problemas)


def test_runtime_de_delegacao_esta_carregada_no_index():
    html = open(os.path.join(RAIZ, "frontend", "index.html"), encoding="utf-8").read()
    assert "/static/js/inline-actions.js" in html, (
        "a runtime de delegação precisa ser carregada antes dos módulos"
    )
    # e precisa vir depois de utils.js (não depende, mas a ordem dos scripts importa)
    assert html.index("/static/js/utils.js") < html.index("/static/js/inline-actions.js")


def test_toda_funcao_de_data_on_existe():
    """Todo `fn` referenciado em data-on* precisa existir como função global."""
    import json
    import html as html_mod
    import re
    from glob import glob

    fns = set()

    def registrar(spec):
        if not isinstance(spec, dict):
            return
        if "seq" in spec:
            for f in spec["seq"]:
                fns.add(f["fn"])
        elif "fn" in spec:
            fns.add(spec["fn"])

    html = open(os.path.join(RAIZ, "frontend", "index.html"), encoding="utf-8").read()
    for m in re.finditer(r'\bdata-on[a-z]+="(.*?)"(?=[\s>])', html, re.S):
        registrar(json.loads(html_mod.unescape(m.group(1))))

    padrao_js = re.compile(
        r'data-on[a-z]+="\$\{escapeAttrJson\(JSON\.stringify\((\{.*?\})\)\)\}"', re.S
    )
    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True):
        src = open(caminho, encoding="utf-8").read()
        for m in padrao_js.finditer(src):
            nomes = re.findall(r'"fn":\s*"([^"]+)"', m.group(1))
            if len(nomes) == 1:
                registrar({"fn": nomes[0]})
            elif nomes:
                registrar({"seq": [{"fn": n} for n in nomes]})

    assert fns, "nenhum handler encontrado — a checagem perdeu o sentido"

    codigo = ""
    for caminho in glob(os.path.join(RAIZ, "frontend", "js", "**", "*.js"), recursive=True):
        codigo += open(caminho, encoding="utf-8").read() + "\n"
    codigo += html

    def existe(fn):
        # Caminho pontilhado (`toast.success`) → checa só a raiz.
        alvo = fn.split(".")[0]
        if alvo in GLOBAIS_NAVEGADOR:
            return True
        p = re.escape(alvo)
        return bool(
            re.search(r"(?<![\w$])function\s+" + p + r"\s*\(", codigo, re.M)
            or re.search(r"(?<![\w$])" + p + r"\s*=(?!=)", codigo)
            or re.search(r"(?<![\w$])(?:const|let|var)\s+" + p + r"\b", codigo)
        )

    faltando = sorted(f for f in fns if not existe(f))
    assert not faltando, "funções referenciadas mas inexistentes: " + ", ".join(faltando)


def test_delegacao_reproduz_semantica_inline():
    """O harness Node prova argumentos, $event/$this, seq, stopPropagation e
    isolamento de erros — tudo o que os handlers inline faziam."""
    if node is None:
        pytest.skip("Node.js indisponível")
    harness = os.path.join(RAIZ, "tests", "fixtures", "inline_actions_check.js")
    alvo = os.path.join(RAIZ, "frontend", "js", "inline-actions.js")
    proc = subprocess.run([node, harness, alvo], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"delegação falhou:\n{proc.stdout}\n{proc.stderr}"
