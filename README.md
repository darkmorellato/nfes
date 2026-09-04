# 🏛️ NFE Manager — Portal NF-e & Gestão Fiscal SEFAZ (Enterprise Edition)

> Plataforma completa, autônoma e de padrão corporativo para **recepção automática (Robô DF-e), manifestação, download de XMLs completos, emissão modelo 55/65, gestão de múltiplos certificados digitais A1, conferência de estoque, fechamento contábil e auditoria fiscal imutável** diretamente na SEFAZ — 100% Web, sem Java e com instalação descomplicada.

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20WAL%20%2B%20Alembic-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Code Quality](https://img.shields.io/badge/Linter-Ruff%20Clean-success)](https://astral.sh/ruff)
[![SEFAZ](https://img.shields.io/badge/SEFAZ-MOC%207.0%20%7C%20NT%202020.001-green)](https://www.nfe.fazenda.gov.br/)

---

## 📋 Índice
1. [Instalação Rápida em Nova Máquina](#-instalação-rápida-em-nova-máquina)
   - [Instalação no Linux (Com Atalho Desktop e Ícone)](#-no-linux-ubuntudebianarchfedoramintcachyos)
   - [Instalação no Windows](#-no-windows-10--11)
   - [Instalação via Docker / Servidor](#-via-docker--docker-compose-servidores)
2. [Atualizações Futuras em 1-Clique](#-atualizações-futuras-em-1-clique)
3. [Primeiro Acesso & Configuração](#-primeiro-acesso--configuração-inicial)
4. [Recursos Principais](#-recursos-principais)
5. [Backups Fiscais & Trilha de Auditoria](#-backups-fiscais--trilha-de-auditoria)
6. [Arquitetura & Módulos](#-arquitetura-do-projeto)
7. [Comandos para Desenvolvedores](#-comandos-úteis-para-desenvolvedores)

---

## 🚀 Instalação Rápida em Nova Máquina

O processo foi automatizado para que qualquer pessoa consiga subir o sistema em uma máquina recém-formatada ou novo computador de trabalho.

---

### 🐧 No Linux (Ubuntu, Debian, Arch, Fedora, Mint, CachyOS, etc.)

O instalador unificado detecta sua distribuição, instala os pacotes de sistema necessários (Python, OpenSSL, bibliotecas XML), cria o ambiente virtual isolado, gera a chave criptográfica, aplica as migrações do banco de dados e **cria o atalho `.desktop` no menu de aplicativos e na Área de Trabalho com o ícone oficial do sistema**.

#### Passo a Passo:

1. **Abra o terminal e clone o repositório:**
   ```bash
   git clone https://github.com/darkmorellato/nfes.git
   cd nfes
   ```

2. **Execute o instalador inteligente:**
   ```bash
   chmod +x instalar.sh
   ./instalar.sh
   ```

3. **O que o instalador faz automaticamente por você:**
   - 📦 Instala dependências nativas (`openssl`, `libxml2`, `libxslt`, `gcc`, `git`).
   - 🐍 Cria o ambiente virtual Python (`venv/`) e instala todos os pacotes.
   - 🔐 Gera o arquivo de configuração seguro `.env` com chave de sessão única.
   - 🗄️ Executa as migrações do banco de dados via **Alembic** (`upgrade head`).
   - 🖥️ Instala o atalho executável **`NFE Manager`** no seu Menu de Aplicativos e na Área de Trabalho com o ícone em alta definição (`256x256`).

4. **Como abrir o sistema:**
   - **Pelo Menu/Área de Trabalho:** Dê um clique duplo no ícone **NFE Manager**.
   - **Pelo Terminal:** Execute `./iniciar_linux.sh`
   - **Ou configure como serviço de inicialização automática (opcional):**
     ```bash
     systemctl --user enable --now nfe-manager.service
     ```

---

### 🪟 No Windows (10 / 11)

1. **Instale o Python:** Caso ainda não possua, baixe em **[python.org](https://www.python.org/downloads/)** *(marque obrigatoriamente a caixa **"Add Python to PATH"** na primeira tela)*.
2. **Baixe ou clone a pasta do projeto.**
3. **Execute o inicializador:**
   Dê **dois cliques** no arquivo:
   ```bat
   iniciar_windows.bat
   ```
   *(O script criará o ambiente virtual, instalará as dependências e abrirá o navegador em `http://127.0.0.1:8000` automaticamente).*

---

### 🐳 Via Docker / Docker Compose (Servidores)

Ideal para servidores dedicados ou ambientes corporativos na nuvem:

```bash
# 1. Copie as variáveis de ambiente
cp .env.example .env

# 2. Inicialize o container em segundo plano
docker compose up -d

# 3. Verifique a saúde do serviço
docker compose ps
```
Acesse em: `http://localhost:8000`.

---

## 🔄 Atualizações Futuras em 1-Clique

Para quem já tem o sistema instalado, **não é necessário digitar nenhum comando no terminal** para receber novas funções, melhorias e correções fiscais:

```
┌────────────────────────────────────────────────────────────────────────┐
│  Barra Superior ➜ Clique em "🔄 Atualizar" ➜ "🚀 Atualizar Agora"      │
└────────────────────────────────────────────────────────────────────────┘
```

### O que o botão de 1-Clique executa automaticamente:
1. **Sincronização com o GitHub:** Baixa a versão mais recente via `git pull`.
2. **Atualização de Bibliotecas:** Atualiza eventuais dependências do Python no ambiente virtual.
3. **Migrações Automáticas:** Aplica as novas tabelas e colunas no SQLite via **Alembic** sem risco de perda de dados.
4. **Hot-Reload:** Atualiza a interface e exibe o registro detalhado de melhorias aplicadas.

> 💻 *Se preferir atualizar manualmente via terminal, basta rodar:*
> ```bash
> git pull origin main
> ./venv/bin/alembic upgrade head
> ```

---

## 🔑 Primeiro Acesso & Configuração Inicial

1. Abra seu navegador em: **`http://127.0.0.1:8000`**
2. **Usuário Padrão:** `contasgeraljack@gmail.com`
3. **Senha Temporária:** Informada na tela do terminal na primeira inicialização (troca solicitada no primeiro login).
4. **Configurando Certificados Digitais A1:**
   - Acesse o menu lateral **`🏢 Certificados A1`**.
   - Clique em **`Adicionar Certificado`**, selecione seu arquivo `.pfx` ou `.p12` e insira a senha.
   - O sistema valida a Razão Social, CNPJ e data de validade, ativando automaticamente o **Robô DF-e de busca de notas na SEFAZ**.

---

## ✨ Recursos Principais

- ⚡ **Robô DF-e Autônomo:** Consulta a SEFAZ em background utilizando o NSU e efetua o download automático dos XMLs completos de todas as notas fiscais emitidas para seus CNPJs.
- 👁️ **Visualizador de DANFE Oficial:** Exibição em tela com código de barras Code-128 em SVG, geração instantânea de PDF e download do XML assinado.
- ✍️ **Manifestação do Destinatário:** Confirmação da Operação, Ciência da Emissão e Desconhecimento da Operação com 1 clique (individual ou em lote).
- 📤 **Emissor Rápido NF-e (Modelo 55):** Emissão profissional com catálogo de produtos, cálculo automático de impostos (ICMS, PIS, COFINS, IPI) e transmissão direta.
- 📝 **Eventos Fiscais:** Emissão de Carta de Correção Eletrônica (CC-e) e Cancelamento oficial de notas homologadas.
- 📊 **Fechamento Contábil Mensal:** Gera pacote `.zip` completo contendo todos os XMLs de Entradas/Saídas organizados por pasta e planilha Excel analítica para envio ao contador.
- 💳 **Módulo Financeiro & Contas a Pagar:** Gestão de duplicatas vinculadas às notas fiscais, conferência física de carga no recebimento e DRE gerencial.
- 🔍 **Auditoria de Saltos (Gaps):** Localiza notas fiscais puladas na numeração e permite inutilização imediata na SEFAZ.
- 🌓 **Design Moderno:** Interface com suporte a modo Claro (Emerald) e Escuro (Quartz), além de navegação rápida via Command Palette (**`Ctrl+K`**).

---

## 📦 Backups Fiscais & Trilha de Auditoria

O sistema foi blindado para auditorias fiscais e conformidade jurídica (LGPD):

- **Snapshot a Quente (Zero-Lock):** Utiliza a API nativa do SQLite para gerar cópias consistentes da base mesmo durante a emissão ativa de notas fiscais.
- **Pacote Compactado ZIP:** Contém o banco de dados snapshotado + todos os XMLs fiscais armazenados em disco, com **checksum SHA-256** e política de retenção de 30 dias.
- **Trilha de Auditoria Imutável (`audit_logs`):** Registra logins, logouts, manifestações na SEFAZ, exclusão de certificados e backups, com e-mail, IP e data/hora.
- **Interface Integrada:** Tanto os backups quanto a trilha de auditoria podem ser visualizados, filtrados e baixados diretamente na subaba de **Configurações**.

---

## 🏛️ Arquitetura do Projeto

```
nfes-main/
├── backend/
│   ├── database/          # Conexão SQLite WAL, repositórios e queries
│   ├── routers/           # Rotas REST organizadas por domínio (FastAPI)
│   ├── services/          # Regras de negócio (PyNFe, DANFE, Backup, Auditoria, Sync)
│   └── main.py            # Entry-point FastAPI, middlewares e lifespan
├── frontend/
│   ├── index.html         # Single Page Application estruturada
│   ├── css/               # Estilos, variáveis e temas (Claro/Escuro)
│   └── js/
│       ├── api.js         # Cliente HTTP com injeção de Session Token e Request ID
│       ├── app.js         # Bootstrap do frontend
│       └── modules/       # 14 submódulos independentes por funcionalidade
│           ├── core.js          # Estado global e helpers
│           ├── navigation.js    # Roteamento e Command Palette (Ctrl+K)
│           ├── certificados.js  # Gestão de certificados A1
│           ├── danfe.js         # Visualizador e impressor de DANFE
│           ├── documentos.js    # Tabela de notas e drawer lateral
│           ├── manifestacao.js  # Manifestação individual e em lote
│           ├── emissor.js       # Emissão rápida Modelo 55
│           ├── nfe-ops.js       # Cancelamento, CC-e e inutilização
│           ├── contabil.js      # Fechamento mensal e relatórios
│           ├── financeiro.js    # Contas a pagar, duplicatas e DRE
│           ├── manutencao.js    # Limpeza, Backups Fiscais e Auditoria
│           ├── cadastros.js     # Clientes, produtos e consulta CNPJ
│           ├── sync.js          # Robô DF-e e semáforo SEFAZ
│           └── updater.js       # Atualizador via GitHub
├── alembic/               # Migrações versionadas do banco de dados
├── scripts/               # Scripts utilitários e instalador de desktop
├── tests/                 # Suíte com 43 testes automatizados (pytest)
├── Dockerfile             # Multi-stage build seguro para produção
├── docker-compose.yml     # Orquestração de containers com healthcheck
├── instalar.sh            # Instalador universal para Linux
└── pyproject.toml         # Configurações do projeto e linter Ruff
```

---

## 🧪 Comandos Úteis para Desenvolvedores

```bash
# Executar a suíte de testes com banco em memória isolado:
PYTHONPATH=. venv/bin/pytest tests/

# Executar verificação de linting e regras de código (Ruff):
venv/bin/ruff check --config pyproject.toml backend/ tests/

# Criar uma nova migração estrutural de banco de dados:
venv/bin/alembic revision --autogenerate -m "descricao_da_mudanca"

# Aplicar migrações pendentes:
venv/bin/alembic upgrade head

# Iniciar servidor em desenvolvimento com auto-reload:
venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

---

## ⚖️ Licença e Suporte

Desenvolvido para alta disponibilidade e autonomia fiscal. Para dúvidas operacionais ou sugestões de novas melhorias, utilize as issues do repositório ou o canal de suporte da sua empresa.
