# 🏛️ NFE Manager — Portal NF-e & Gestão Fiscal SEFAZ

> Sistema completo e autônomo para **gestão, consulta, manifestação, download de XMLs e emissão de Notas Fiscais Eletrônicas (NF-e/NFC-e)** diretamente na SEFAZ — 100% Web, sem Java e sem instalações complicadas.

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](#-instalação-rápida-em-1-clique)
[![License](https://img.shields.io/badge/Licença-Proprietária-red)](#)
[![Status](https://img.shields.io/badge/SEFAZ-MOC%207.0%20%7C%20NT%202020.001-green)](https://www.nfe.fazenda.gov.br/)

---

## 🚀 Instalação Rápida em 1-Clique

Você não precisa de conhecimentos avançados de programação para instalar o NFE Manager. Siga os passos simples para o seu sistema:

### 🪟 No Windows (Qualquer versão)

1. **Instale o Python:** Caso ainda não tenha, baixe no site oficial **[python.org/downloads](https://www.python.org/downloads/)** *(lembre-se de marcar a opção **"Add Python to PATH"** na primeira tela da instalação)*.
2. **Baixe o projeto:** Clique no botão verde **`Code` ➡️ `Download ZIP`** no topo da página e extraia os arquivos.
3. **Inicie o sistema:** Na pasta extraída, dê **dois cliques** no arquivo:
   ```bat
   iniciar_windows.bat
   ```
   *(O sistema cria o ambiente, instala tudo automaticamente e abre o seu navegador em `http://127.0.0.1:8000`)*.

---

### 🐧 No Linux (Ubuntu, Debian, Mint, Arch, Fedora, Zorin)

Abra o terminal na pasta do projeto e execute:
```bash
chmod +x iniciar_linux.sh instalar.sh
./iniciar_linux.sh
```

---

> 📖 **Guia Completo para Leigos:** Se você quer ver instruções detalhadas com imagens e passo a passo explicativo, acesse o **[Guia de Instalação para Iniciantes (docs/GUIA_INSTALACAO_LEIGOS.md)](docs/GUIA_INSTALACAO_LEIGOS.md)**.

---

## 🔄 Como Atualizar o Sistema (Novas Versões do GitHub)

O NFE Manager conta com **atualizador integrado de 1-Clique**:

1. **Pela Interface Web (Mais Fácil):**
   - Na barra superior do sistema, clique no botão **`🔄 Atualizar`**.
   - Se houver novidades no repositório GitHub, você verá a lista de melhorias e bastará clicar em **`🚀 Atualizar Agora (1-Clique)`**.
2. **Automático na Inicialização:**
   - Ao abrir pelo `iniciar_windows.bat` ou `iniciar_linux.sh`, o sistema verifica automaticamente novas atualizações.
3. **Pelo Terminal / Prompt:**
   ```bash
   git pull origin main
   ```

---

## 🔑 Primeiro Acesso

1. Acesse **`http://127.0.0.1:8000`** no seu navegador de internet.
2. **E-mail:** `contasgeraljack@gmail.com`
3. **Senha Temporária:** A senha inicial é exibida no terminal na primeira inicialização.
4. **Troca Obrigatória:** Por segurança, cadastre sua senha pessoal no primeiro login.

---

## ✨ Recursos e Funcionalidades

- ⚡ **Robô DF-e Automático:** Consulta a SEFAZ em segundo plano e baixa automaticamente os XMLs completos (`nfeProc`) de todas as notas fiscais emitidas para suas empresas.
- 👁️ **Visualizador de DANFE Oficial:** Renderiza o DANFE idêntico ao modelo oficial da SEFAZ, com visualização em tela, código de barras, impressão e download direto de PDF.
- 📤 **Emissor de NF-e e NFC-e:** Emissão profissional modelo 55 e 65 com assinatura digital A1, cálculo tributário automático e transmissão instantânea.
- ✍️ **Manifestação do Destinatário:** Registro de Ciência da Emissão (210210), Confirmação da Operação (210200) e Desconhecimento com 1 clique.
- 📝 **Eventos Fiscais & CC-e:** Cancelamento oficial e emissão de Carta de Correção Eletrônica.
- 📊 **Fechamento Contábil Mensal:** Gera pacote `.zip` organizado com XMLs de Entradas/Saídas, DANFEs em PDF e planilha Excel para envio ao contador.
- 🔍 **Auditoria de Numeração (Gaps):** Localiza notas faltantes ou puladas na sequência de emissão e permite inutilização imediata na SEFAZ.
- 💳 **Financeiro & DRE:** Gestão de contas a pagar/receber vinculadas às notas fiscais e DRE gerencial.
- 🏢 **Multi-Empresa:** Suporte para múltiplos certificados digitais A1 e gerenciamento centralizado de filiais.
- ☁️ **Sincronização Nuvem (Firestore):** Backup opcional e sincronização multi-dispositivo gratuita.
- 🎨 **Interface Moderna:** Design profissional com modos Claro (Emerald) e Escuro (Quartz).

---

## 🏢 Configurando seus Certificados Digitais A1

1. Acesse o menu **`🏢 Certificados A1`**.
2. Clique em **`Adicionar Certificado`**.
3. Selecione o arquivo do seu certificado (extensão `.pfx` ou `.p12`) e informe a senha.
4. O sistema valida os dados (CNPJ, Razão Social e Validade) e ativa o robô de sincronização automaticamente.

---

## 🛠️ Comandos para Desenvolvedores

```bash
# Executar todos os testes automatizados:
./venv/bin/python -m unittest tests/test_all.py

# Iniciar servidor em modo desenvolvimento com auto-reload:
./venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 📞 Suporte e Ajuda

- **Guia Detalhado para Iniciantes:** [docs/GUIA_INSTALACAO_LEIGOS.md](docs/GUIA_INSTALACAO_LEIGOS.md)
- **Central de Dúvidas / Issues:** [https://github.com/darkmorellato/nfes/issues](https://github.com/darkmorellato/nfes/issues)
