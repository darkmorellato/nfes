APP_NAME=nfe-manager
APP_DIR=$(pwd)
VENV_DIR=$APP_DIR/venv
USER_SERVICE_DIR=$HOME/.config/systemd/user

echo "=== Configurando servico systemd para NFE Manager ==="

mkdir -p "$VENV_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/backend/requirements.txt"

mkdir -p "$USER_SERVICE_DIR"

cat > "$USER_SERVICE_DIR/nfe-manager.service" << EOF
[Unit]
Description=NFE Manager - Interface PyNFe
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
Restart=always
RestartSec=10
Environment="PATH=$VENV_DIR/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable nfe-manager.service
systemctl --user start nfe-manager.service

echo ""
echo "Servico instalado!"
echo "  Iniciar:  systemctl --user start nfe-manager"
echo "  Parar:    systemctl --user stop nfe-manager"
echo "  Status:   systemctl --user status nfe-manager"
echo "  Logs:     journalctl --user -u nfe-manager -f"
echo ""
echo "Acesse: http://localhost:8000"
