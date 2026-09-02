#!/bin/bash
# Aguarda cooldown da SEFAZ e roda download dos XMLs
sleep 2700
cd /home/dark/Codes/nfes-main
./venv/bin/python scripts/download_missing_xmls.py >> /tmp/download_xmls.log 2>&1
echo "$(date): Download finalizado" >> /tmp/download_xmls.log
