#!/usr/bin/env bash
# Instala o .AppImage no menu do usuário (modo "instalado", além do portátil).
set -e

APP="NFE-Manager"
APPIMAGE="$(ls ./NFE-Manager*.AppImage 2>/dev/null | head -1)"
if [ -z "${APPIMAGE}" ]; then
    echo "Coloque o NFE-Manager-x86_64.AppImage nesta pasta e rode ./scripts/install.sh"
    exit 1
fi

DEST="$HOME/.local/opt/${APP}"
mkdir -p "${DEST}"
cp "${APPIMAGE}" "${DEST}/${APP}.AppImage"
chmod +x "${DEST}/${APP}.AppImage"

APPDIR="${DEST}/${APP}.AppImage"
# Extrai ícone/desktop se o AppImage os expuser; senão usa os do repo.
"${APPDIR}" --appimage-extract-and-run true >/dev/null 2>&1 || true

mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
cat > "$HOME/.local/share/applications/${APP}.desktop" <<EOF
[Desktop Entry]
Name=NFE Manager
Comment=Portal NF-e local (SEFAZ) sem Java
Exec=${DEST}/${APP}.AppImage
Icon=nfe-manager
Type=Application
Categories=Office;Finance;
Terminal=false
EOF

# Sem FUSE: usa extração em tempo de execução.
if ! command -v fusermount >/dev/null 2>&1 && ! command -v fusermount3 >/dev/null 2>&1; then
    sed -i "s|^Exec=.*|Exec=${DEST}/${APP}.AppImage --appimage-extract-and-run|" \
        "$HOME/.local/share/applications/${APP}.desktop"
    echo "FUSE ausente: o atalho usará --appimage-extract-and-run."
fi

# Ícone (opcional).
if [ -f "AppDir/nfe-manager.png" ]; then
    cp "AppDir/nfe-manager.png" "$HOME/.local/share/icons/hicolor/256x256/apps/nfe-manager.png"
fi

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
echo "Instalado. Atalho: $HOME/.local/share/applications/${APP}.desktop"
