#!/usr/bin/env bash
# Spike de viabilidade (Fase 0): prova o freeze mínimo + Chromium no AppImage.
set -e
WORK="$(mktemp -d)"; echo "WORK=${WORK}"; cd "${WORK}"

sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip \
    libssl-dev libffi-dev libxml2-dev libxslt1-dev build-essential \
    fuse3 wget squashfs-tools

python3.11 -m venv venv && source venv/bin/activate
pip install -U pip
pip install pyinstaller "pynfe>=0.6.5" lxml cryptography \
    "fastapi>=0.115.6" "uvicorn[standard]>=0.34.0" python-multipart playwright

# Copia os fontes do repo (ajuste o caminho).
REPO="${REPO:-/home/dark/Desktop/codes/NFE}"
cp "${REPO}/scripts/spike_entry.py" .
cp "${REPO}/scripts/backend_min.spec" .

pyinstaller backend_min.spec --noconfirm

# Valida o binário congelado (sem Chromium ainda).
./dist/nfe_spike & SPIKE_PID=$!
sleep 3
curl -s http://127.0.0.1:8000/health && echo " FREEZE_OK" || echo " FREEZE_FAIL"
kill "${SPIKE_PID}" 2>/dev/null || true

# Baixa Chromium e empacota num AppImage de teste.
playwright install chromium
CHROME="$(find "$HOME/.cache/ms-playwright" -name chrome -path '*chrome-linux*' | head -1)"
mkdir -p AppDir/usr/bin
cp "${CHROME}" AppDir/usr/bin/chromium-spike
cat > AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
"$HERE/usr/bin/chromium-spike" --no-sandbox --app=https://example.com
EOF
chmod +x AppDir/AppRun AppDir/usr/bin/chromium-spike
wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
./appimagetool-x86_64.AppImage AppDir NFE-Spike-x86_64.AppImage
echo "SPIKE_APPIMAGE_PRONTO: ${WORK}/NFE-Spike-x86_64.AppImage"
