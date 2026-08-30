#!/usr/bin/env bash
# Build do AppImage NFE Manager (FastAPI + Chromium embutido).
# Rodar num container Ubuntu 22.04 (glibc 2.35), Python 3.11.
set -e

PY="${PY:-python3.11}"
"${PY}" -m venv venv && source venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt pyinstaller playwright

# 1) Freeze do backend (gera dist/NFE-Manager).
pyinstaller backend.spec --noconfirm --clean

# 2) Baixa e empacota o Chromium (Playwright).
playwright install chromium
PLAYWRIGHT_CACHE="${PLAYWRIGHT_CACHE:-$HOME/.cache/ms-playwright}"
CHROMIUM_SRC="$(ls -d ${PLAYWRIGHT_CACHE}/chromium-* 2>/dev/null | head -1)"
if [ -z "${CHROMIUM_SRC}" ]; then
    echo "Chromium não encontrado em ${PLAYWRIGHT_CACHE}."; exit 1
fi

# 3) Monta o AppDir.
APPDIR="AppDir"
# Preserva os arquivos-template do AppDir (AppRun, .desktop, ícone); só
# reconstrói a árvore gerada (usr/bin/NFE-Manager e usr/lib/playwright).
mkdir -p "${APPDIR}"
rm -rf "${APPDIR}/usr"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/lib/playwright"
cp "dist/NFE-Manager" "${APPDIR}/usr/bin/NFE-Manager"
cp -r "${CHROMIUM_SRC}" "${APPDIR}/usr/lib/playwright/$(basename "${CHROMIUM_SRC}")"
# AppRun, .desktop e ícone já estão em AppDir (preservados acima); nada a copiar.
chmod +x "${APPDIR}/AppRun" "${APPDIR}/usr/bin/NFE-Manager"

# 4) Gera o .AppImage.
if [ ! -x appimagetool-x86_64.AppImage ]; then
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi
./appimagetool-x86_64.AppImage "${APPDIR}" "NFE-Manager-x86_64.AppImage"

echo "Pronto: NFE-Manager-x86_64.AppImage"
