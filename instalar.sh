#!/usr/bin/env bash
# ============================================================================
# NFE Manager — Script de Instalação Unificado
# Detecta automaticamente a distribuição Linux e instala todas as dependências.
# Uso: chmod +x instalar.sh && ./instalar.sh
# ============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${REPO_DIR}/venv"
REQ_FILE="${REPO_DIR}/backend/requirements.txt"
ENV_EXAMPLE="${REPO_DIR}/.env.example"
ENV_FILE="${REPO_DIR}/.env"
PYTHON_MIN="3.9"

# ── Cores ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $*"; }
err()   { echo -e "${RED}[ERRO]${NC} $*" >&2; }

# ── Detectar SO ────────────────────────────────────────────────────────────────
detect_os() {
    local os
    os="$(uname -s)"
    case "$os" in
        Linux*)  OS="linux" ;;
        MINGW*|MSYS*|CYGWIN*)  OS="windows" ;;
        *)  err "SO não suportado: $os"; exit 1 ;;
    esac
}

# ── Detectar distribuição Linux ────────────────────────────────────────────────
detect_distro() {
    DISTROFamily=""
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        local id_like="${ID_LIKE:-$ID}"
        case "$id_like" in
            *debian*|*ubuntu*)  DISTROFamily="debian" ;;
            *arch*)             DISTROFamily="arch" ;;
            *fedora*|*rhel*)    DISTROFamily="fedora" ;;
            *suse*)             DISTROFamily="suse" ;;
            *)
                case "${ID:-}" in
                    debian|ubuntu|linuxmint|zorin|pop)  DISTROFamily="debian" ;;
                    arch|manjaro|cachyos|endeavouros)    DISTROFamily="arch" ;;
                    fedora|rhel|centos|rocky|alma)       DISTROFamily="fedora" ;;
                    opensuse*|sles)                       DISTROFamily="suse" ;;
                    *)  DISTROFamily="unknown" ;;
                esac
                ;;
        esac
    else
        DISTROFamily="unknown"
    fi
}

# ── Verificar versão do Python ────────────────────────────────────────────────
check_python_version() {
    local py_cmd="$1"
    local version
    version="$("$py_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)" || return 1
    local major minor
    major="$(echo "$version" | cut -d. -f1)"
    minor="$(echo "$version" | cut -d. -f2)"
    local req_major req_minor
    req_major="$(echo "$PYTHON_MIN" | cut -d. -f1)"
    req_minor="$(echo "$PYTHON_MIN" | cut -d. -f2)"
    [ "$major" -gt "$req_major" ] || { [ "$major" -eq "$req_major" ] && [ "$minor" -ge "$req_minor" ]; }
}

# ── Encontrar Python 3 ────────────────────────────────────────────────────────
find_python() {
    local candidates=("python3" "python" "python3.12" "python3.11" "python3.10" "python3.9")
    for cmd in "${candidates[@]}"; do
        if command -v "$cmd" &>/dev/null && check_python_version "$cmd"; then
            PYTHON_CMD="$cmd"
            return 0
        fi
    done
    return 1
}

# ── Instalar dependências do sistema (Debian/Ubuntu) ──────────────────────────
install_deps_debian() {
    info "Detectado: Debian/Ubuntu/Zorin/Mint"
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3 python3-venv python3-pip \
        openssl libxml2 libxslt1-dev \
        build-essential libssl-dev libffi-dev \
        git
}

# ── Instalar dependências do sistema (Arch) ───────────────────────────────────
install_deps_arch() {
    info "Detectado: Arch/Manjaro/CachyOS/EndeavourOS"
    sudo pacman -Syu --needed --noconfirm \
        python python-pip openssl libxml2 libxslt xmlsec \
        base-devel git
}

# ── Instalar dependências do sistema (Fedora) ────────────────────────────────
install_deps_fedora() {
    info "Detectado: Fedora/RHEL/CentOS"
    sudo dnf install -y \
        python3 python3-pip python3-devel \
        openssl openssl-devel libxml2-devel libxslt-devel \
        gcc gcc-c++ make git
}

# ── Instalar dependências do sistema (openSUSE) ──────────────────────────────
install_deps_suse() {
    info "Detectado: openSUSE/SLES"
    sudo zypper install -y \
        python3 python3-pip python3-devel \
        openssl libxml2-devel libxslt-devel \
        gcc gcc-c++ make git
}

# ── Instalar dependências do sistema ──────────────────────────────────────────
install_system_deps() {
    case "$DISTROFamily" in
        debian)  install_deps_debian ;;
        arch)    install_deps_arch ;;
        fedora)  install_deps_fedora ;;
        suse)    install_deps_suse ;;
        unknown)
            warn "Distribuição não identificada. Instale manualmente:"
            warn "  Python 3.9+, pip, venv, openssl, libxml2, libxslt-dev, gcc"
            echo ""
            read -rp "Pressione Enter para continuar após instalar as dependências..."
            ;;
    esac
}

# ── Criar ambiente virtual ────────────────────────────────────────────────────
setup_venv() {
    if [ -d "$VENV_DIR" ]; then
        info "Ambiente virtual já existe em $VENV_DIR"
    else
        info "Criando ambiente virtual..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        ok "Ambiente virtual criado."
    fi

    info "Instalando dependências Python..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$REQ_FILE" -q
    ok "Dependências Python instaladas."
}

# ── Configurar .env ───────────────────────────────────────────────────────────
setup_env() {
    if [ -f "$ENV_FILE" ]; then
        info "Arquivo .env já existe."
    elif [ -f "$ENV_EXAMPLE" ]; then
        info "Criando .env a partir do .env.example..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        # Gerar SECRET_KEY aleatória
        local secret_key
        secret_key=$("$VENV_DIR/bin/python" -c "import secrets; print(secrets.token_urlsafe(48))")
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=${secret_key}/" "$ENV_FILE"
        else
            sed -i "s/SECRET_KEY=.*/SECRET_KEY=${secret_key}/" "$ENV_FILE"
        fi
        ok ".env criado com SECRET_KEY gerado."
        warn "Edite o .env para configurar Firebase (opcional)."
    fi
}

# ── Executar migrações do banco (Alembic) ───────────────────────────────────
run_database_migrations() {
    info "Aplicando migrações estruturais do banco de dados..."
    if [ -f "${VENV_DIR}/bin/alembic" ] && [ -f "${REPO_DIR}/alembic.ini" ]; then
        "${VENV_DIR}/bin/alembic" -c "${REPO_DIR}/alembic.ini" upgrade head
        ok "Banco de dados atualizado na última versão estrutural (Alembic)."
    else
        "$VENV_DIR/bin/python" -c "from backend.database import init_db; init_db()"
        ok "Banco de dados inicializado."
    fi
}

# ── Instalar atalho .desktop (Linux) ─────────────────────────────────────────
install_desktop_entry() {
    if [ "$OS" = "linux" ] && [ -f "${REPO_DIR}/scripts/install.sh" ]; then
        info "Instalando atalho no menu e ícone..."
        bash "${REPO_DIR}/scripts/install.sh"
    fi
}

# ── Mensagem final ────────────────────────────────────────────────────────────
print_success() {
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  NFE Manager instalado com sucesso!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Para iniciar o sistema:"
    echo -e "    ${CYAN}./iniciar_linux.sh${NC}"
    echo ""
    echo -e "  Ou manualmente:"
    echo -e "    ${CYAN}source venv/bin/activate${NC}"
    echo -e "    ${CYAN}python app_launcher.py${NC}"
    echo ""
    echo -e "  Acesse: ${CYAN}http://127.0.0.1:8000${NC}"
    echo ""
    if [ -f "$ENV_FILE" ]; then
        if grep -q "FIREBASE_API_KEY=" "$ENV_FILE" && ! grep -q "FIREBASE_API_KEY=.\\+" "$ENV_FILE"; then
            warn "Firebase não configurado. Edite o .env para sincronização na nuvem."
        fi
    fi
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       NFE Manager — Instalador Unificado               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    detect_os
    if [ "$OS" = "linux" ]; then
        detect_distro
    fi

    # 1. Dependências do sistema
    install_system_deps

    # 2. Encontrar Python
    if ! find_python; then
        err "Python ${PYTHON_MIN}+ não encontrado. Instale-o primeiro."
        exit 1
    fi
    info "Usando: $($PYTHON_CMD --version 2>&1)"

    # 3. Ambiente virtual + dependências Python
    setup_venv

    # 4. Arquivo .env
    setup_env

    # 5. Migrações do banco de dados (Alembic)
    run_database_migrations

    # 6. Atalho .desktop com Ícone (Linux)
    install_desktop_entry

    # 7. Sucesso
    print_success
}

main "$@"
