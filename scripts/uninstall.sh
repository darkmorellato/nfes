#!/usr/bin/env bash
# Remove a instalação do menu feita por scripts/install.sh.
set -e

APP="NFE-Manager"
rm -f "$HOME/.local/share/applications/${APP}.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/nfe-manager.png"
rm -rf "$HOME/.local/opt/${APP}"
echo "Removido."
