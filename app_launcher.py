"""Entrypoint do AppImage/executável: sobe o servidor FastAPI e abre a UI.

- Sobe o uvicorn EM PROCESSO (funciona congelado e em dev; evita re-exec do
  próprio binário via `python -m uvicorn`, que não existe no bundle).
- Abre a janela Chromium embutida (NFE_CHROME_BIN) em modo --app; fallback para
  o navegador do SO.
- Instância única: se a porta já estiver em uso, apenas abre a UI e sai.
- Auto-update: verifica atualizações via git pull ao iniciar (se for repo git).
- Cleanup ao fechar (uvicorn.run bloqueia até Ctrl+C).
"""
import os
import sys
import time
import socket
import threading
import subprocess
import urllib.request
import webbrowser
import logging

logger = logging.getLogger("nfe.launcher")


def _auto_update(repo_dir: str) -> None:
    """Verifica e aplica atualizações via git pull (se o diretório for um repo git)."""
    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.isdir(git_dir):
        return

    # Verificar se --no-auto-update foi passado
    if "--no-auto-update" in sys.argv:
        logger.info("[AutoUpdate] Desativado via --no-auto-update")
        return

    logger.info("[AutoUpdate] Verificando atualizações...")
    try:
        result = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("[AutoUpdate] git fetch falhou: %s", result.stderr.strip())
            return

        # Verificar se há mudanças
        status = subprocess.run(
            ["git", "status", "-uno", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Comparar HEAD com origin/main
        diff = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        remote_head = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if diff.returncode != 0 or remote_head.returncode != 0:
            return

        local_commit = diff.stdout.strip()
        remote_commit = remote_head.stdout.strip()

        if local_commit == remote_commit:
            logger.info("[AutoUpdate] Já está atualizado.")
            return

        logger.info("[AutoUpdate] Nova versão disponível. Atualizando...")
        pull_result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if pull_result.returncode == 0:
            logger.info("[AutoUpdate] Atualizado com sucesso: %s", pull_result.stdout.strip())
            # Instalar novas dependências se requirements.txt mudou
            pip_install = subprocess.run(
                [os.path.join(repo_dir, "venv", "bin", "pip"), "install", "-r",
                 os.path.join(repo_dir, "backend", "requirements.txt"), "-q"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if pip_install.returncode == 0:
                logger.info("[AutoUpdate] Dependências atualizadas.")
        else:
            logger.warning("[AutoUpdate] git pull falhou: %s", pull_result.stderr.strip())

    except subprocess.TimeoutExpired:
        logger.warning("[AutoUpdate] Timeout ao verificar atualizações.")
    except Exception as e:
        logger.warning("[AutoUpdate] Erro inesperado: %s", e)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def _open_ui(url: str, chrome: str | None) -> None:
    # Aguarda o servidor subir antes de abrir a janela.
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{url}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    try:
        if chrome and os.path.exists(chrome):
            cmd = [
                chrome,
                "--no-sandbox",
                "--ozone-platform-hint=auto",
                f"--app={url}",
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
    except Exception as e:
        print(f"AVISO: falha ao abrir o Chromium embutido ({e}); usando o navegador do sistema.")
    # Fallback: navegador padrão do SO (funciona mesmo sem o Chromium do bundle).
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"AVISO: não foi possível abrir a UI automaticamente: {e}")


def main() -> int:
    host = os.environ.get("NFE_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("NFE_PORT", "8000"))
    except ValueError:
        port = 8000
    url = f"http://{host}:{port}"

    # Auto-update antes de subir o servidor
    _auto_update(os.path.dirname(os.path.abspath(__file__)))

    if _port_in_use(host, port):
        # Já há um servidor rodando: apenas abre a UI.
        _open_ui(url, os.environ.get("NFE_CHROME_BIN"))
        return 0

    threading.Thread(target=_open_ui, args=(url, os.environ.get("NFE_CHROME_BIN")), daemon=True).start()

    import uvicorn
    from backend.main import app

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
