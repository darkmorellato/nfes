"""
Serviço de atualização automática e sob demanda do sistema NFE Manager via Git.
Permite checar novas versões no repositório GitHub e aplicar atualizações com 1 clique.
"""
import os
import sys
import subprocess
import logging
from typing import Dict, Any, List

logger = logging.getLogger("nfe.updater")


def _get_repo_dir() -> str:
    """Retorna o diretório raiz do repositório."""
    # backend/services/updater_service.py -> ../../
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _get_pip_executable(repo_dir: str) -> str:
    """Detecta o executável do pip dentro do venv (Linux/Mac ou Windows)."""
    if sys.platform == "win32":
        pip_path = os.path.join(repo_dir, "venv", "Scripts", "pip.exe")
        if os.path.isfile(pip_path):
            return pip_path
    else:
        pip_path = os.path.join(repo_dir, "venv", "bin", "pip")
        if os.path.isfile(pip_path):
            return pip_path
    return sys.executable + " -m pip"


def check_update_status() -> Dict[str, Any]:
    """Verifica se há novas atualizações disponíveis no repositório remoto Git."""
    repo_dir = _get_repo_dir()
    git_dir = os.path.join(repo_dir, ".git")

    if not os.path.isdir(git_dir):
        return {
            "is_git": False,
            "has_update": False,
            "message": "A instalação atual não foi feita via Git (.git ausente).",
            "local_commit": "N/A",
            "branch": "main",
        }

    try:
        # 1. Identifica branch atual
        branch_proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = branch_proc.stdout.strip() or "main"

        # 2. Informações do commit local atual
        local_log = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cd|%s", "--date=short"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        local_commit, local_date, local_msg = ("desconhecido", "", "")
        if local_log.returncode == 0 and local_log.stdout.strip():
            parts = local_log.stdout.strip().split("|", 2)
            if len(parts) == 3:
                local_commit, local_date, local_msg = parts

        # 3. URL do repositório remoto
        remote_url_proc = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        remote_url = remote_url_proc.stdout.strip()

        # 4. Faz git fetch para consultar o remoto (timeout 15s)
        fetch_proc = subprocess.run(
            ["git", "fetch", "origin", branch],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )

        if fetch_proc.returncode != 0:
            # Tenta fetch genérico caso a branch tenha outro nome no origin
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=15,
            )

        # 5. Compara commits
        local_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()

        remote_target = f"origin/{branch}"
        remote_head_proc = subprocess.run(
            ["git", "rev-parse", remote_target],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        
        if remote_head_proc.returncode != 0 and branch != "main":
            remote_target = "origin/main"
            remote_head_proc = subprocess.run(
                ["git", "rev-parse", remote_target],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

        remote_head = remote_head_proc.stdout.strip()
        has_update = bool(local_head and remote_head and local_head != remote_head)

        commits_behind = 0
        pending_commits: List[str] = []
        if has_update:
            count_proc = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..{remote_target}"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if count_proc.returncode == 0 and count_proc.stdout.strip().isdigit():
                commits_behind = int(count_proc.stdout.strip())

            list_proc = subprocess.run(
                ["git", "log", f"HEAD..{remote_target}", "--oneline", "-n", "10"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if list_proc.returncode == 0:
                pending_commits = [c.strip() for c in list_proc.stdout.strip().split("\n") if c.strip()]

        return {
            "is_git": True,
            "has_update": has_update,
            "branch": branch,
            "local_commit": local_commit,
            "local_date": local_date,
            "local_message": local_msg,
            "remote_commit": remote_head[:7] if remote_head else "",
            "commits_behind": commits_behind,
            "pending_commits": pending_commits,
            "remote_url": remote_url,
            "message": "Nova versão disponível no GitHub!" if has_update else "Seu sistema está atualizado com a versão mais recente.",
        }

    except subprocess.TimeoutExpired:
        return {
            "is_git": True,
            "has_update": False,
            "error": "Tempo limite esgotado ao conectar ao GitHub. Verifique sua conexão com a internet.",
            "local_commit": "N/A",
            "branch": "main",
        }
    except Exception as e:
        logger.error(f"Erro ao verificar atualizações: {e}")
        return {
            "is_git": True,
            "has_update": False,
            "error": str(e),
            "local_commit": "N/A",
            "branch": "main",
        }


def execute_update() -> Dict[str, Any]:
    """Executa o git pull e a atualização das dependências."""
    repo_dir = _get_repo_dir()
    git_dir = os.path.join(repo_dir, ".git")

    if not os.path.isdir(git_dir):
        return {
            "success": False,
            "message": "Não é possível atualizar: diretório .git não encontrado.",
        }

    logs: List[str] = []
    try:
        # 1. Identifica branch
        branch_proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = branch_proc.stdout.strip() or "main"
        logs.append(f"📦 Branch ativa: {branch}")

        # 2. Executa git pull
        logs.append("⬇️ Baixando atualizações do repositório GitHub...")
        pull_proc = subprocess.run(
            ["git", "pull", "origin", branch],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if pull_proc.returncode != 0:
            # Fallback para git pull padrão
            pull_proc = subprocess.run(
                ["git", "pull"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

        if pull_proc.returncode != 0:
            err_msg = pull_proc.stderr.strip() or pull_proc.stdout.strip()
            logs.append(f"❌ Erro no git pull: {err_msg}")
            return {
                "success": False,
                "message": f"Falha ao sincronizar com GitHub: {err_msg}",
                "logs": "\n".join(logs),
            }

        logs.append(f"✅ Arquivos atualizados:\n{pull_proc.stdout.strip()}")

        # 3. Atualiza dependências pip
        req_file = os.path.join(repo_dir, "backend", "requirements.txt")
        if os.path.isfile(req_file):
            pip_cmd = _get_pip_executable(repo_dir)
            logs.append("⚙️ Verificando e instalando dependências Python...")
            
            if isinstance(pip_cmd, list):
                cmd_args = pip_cmd + ["install", "-r", req_file, "-q"]
            else:
                cmd_args = [pip_cmd, "install", "-r", req_file, "-q"]

            pip_proc = subprocess.run(
                cmd_args,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if pip_proc.returncode == 0:
                logs.append("✅ Dependências verificadas com sucesso.")
            else:
                logs.append(f"⚠️ Aviso ao instalar dependências: {pip_proc.stderr.strip()}")

        # 4. Executa migrações / inicializações do banco SQLite
        try:
            from backend.database import init_db
            init_db()
            logs.append("✅ Banco de dados e tabelas verificados.")
        except Exception as db_err:
            logs.append(f"⚠️ Aviso ao verificar banco: {db_err}")

        # 5. Obtém novo commit hash
        new_commit_proc = subprocess.run(
            ["git", "log", "-1", "--format=%h — %s (%cd)", "--date=short"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        new_version = new_commit_proc.stdout.strip() if new_commit_proc.returncode == 0 else "OK"
        logs.append(f"🎉 Sistema atualizado para: {new_version}")

        return {
            "success": True,
            "message": "Sistema atualizado com sucesso!",
            "new_version": new_version,
            "logs": "\n".join(logs),
            "restart_recommended": True,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Tempo limite esgotado durante o processo de atualização.",
            "logs": "\n".join(logs),
        }
    except Exception as e:
        logger.exception("Erro durante atualização")
        return {
            "success": False,
            "message": f"Erro inesperado durante a atualização: {str(e)}",
            "logs": "\n".join(logs) + f"\n❌ {str(e)}",
        }
