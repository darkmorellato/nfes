"""Entrypoint do AppImage/executável: sobe o servidor FastAPI e abre a UI.

- Sobe o uvicorn EM PROCESSO (funciona congelado e em dev; evita re-exec do
  próprio binário via `python -m uvicorn`, que não existe no bundle).
- Abre a janela Chromium embutida (NFE_CHROME_BIN) em modo --app; fallback para
  o navegador do SO.
- Instância única: se a porta já estiver em uso, apenas abre a UI e sai.
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
