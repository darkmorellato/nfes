# NFE Manager

> Portal NF-e & Gestao Fiscal — sem Java, sem .jnlp

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## Quick Start

### Linux (Ubuntu / Arch / Zorin / Fedora)

```bash
git clone https://github.com/darkmorellato/nfes.git
cd nfes
./instalar.sh
./iniciar_linux.sh
```

### Windows

```bat
git clone https://github.com/darkmorellato/nfes.git
cd nfes
iniciar_windows.bat
```

Acesse: **http://127.0.0.1:8000**

---

## Funcionalidades

- **Robot DF-e Automatico** — Consulta e baixa automaticamente da SEFAZ todas as notas fiscais emitidas contra o seu CNPJ.
- **Visualizador DANFE** — Gera DANFE oficial na tela com visualizacao A4, impressao e download de PDF com codigo de barras.
- **Emissor Autonomo** — NF-e (Modelo 55) e NFC-e (Modelo 65) com assinatura digital A1 e transmissao a SEFAZ (MOC 7.0).
- **Eventos Fiscais** — Cancelamento, Manifestacao do Destinatario e Cartas de Correcao Eletronica (CC-e).
- **Fechamento Contabil Mensal** — Gera pacote .zip com XMLs de Entradas/Saidas, DANFEs em PDF e relatorio Excel para o contador.
- **Auditoria de Gaps** — Identifica buracos na numeracao de notas e permite inutilizacao imediata na SEFAZ.
- **Sincronizacao Firestore** — Backup e acesso multi-maquina via Google Cloud Firestore (plano gratuito).
- **Design System Profissional** — Temas Claro (Emerald Enterprise) e Escuro (Quartz Accounting).

---

## Primeiro Acesso

1. Abra **http://127.0.0.1:8000** no navegador
2. Usuario: `contasgeraljack@gmail.com`
3. Senha: consulte o log do servidor na primeira execucao (senha temporaria gerada automaticamente)
4. **O sistema obrigara a alteracao da senha no primeiro login** por seguranca

---

## Atualizacao Automatica

O sistema verifica atualizacoes automaticamente via `git pull` ao iniciar. Para desativar:

```bash
python app_launcher.py --no-auto-update
```

---

## Seguranca

- **Senhas:** bcrypt (rounds=12) com migracao automatica de hashes legados
- **Certificados:** Criptografia Fernet (AES-128-CBC + HMAC-SHA256)
- **Sessoes:** Tokens criptograficos com expiracao de 8 horas
- **Dados sensivel:** `.env`, `certs/`, `data/*.db` nunca sao commitados no Git

---

## Comandos para Desenvolvedores

```bash
# Executar testes:
PYTHONPATH=. ./venv/bin/pytest tests/

# Validar sintaxe do JavaScript:
node --check frontend/js/app.js
```

---

## Suporte

- **Documentacao:** `docs/SETUP.md`
- **Issues:** https://github.com/darkmorellato/nfes/issues
