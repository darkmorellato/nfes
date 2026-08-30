# 🏛️ NFE Manager — Portal NF-e Local & Nuvem para Linux

> **O jeito mais fácil de consultar, emitir e gerenciar Notas Fiscais Eletrônicas (SEFAZ) no Linux.**  
> 🚫 **Sem Java** • 🚫 **Sem .jnlp** • 🚫 **Sem Windows** • ☁️ **Sincronizado 24h no Firestore**

---

## 🎯 O que é o NFE Manager?

O **NFE Manager** é um sistema completo de gestão fiscal com a mesma interface visual do portal oficial da SEFAZ, mas feito para rodar com **1 clique** no Linux.

Ele substitui todo o programa antigo da Receita Federal e permite:
- 📥 **Baixar automaticamente todas as notas emitidas contra o seu CNPJ** direto da SEFAZ (Robô DF-e).
- 🖨️ **Gerar e Imprimir DANFE em PDF** oficial com código de barras.
- 📤 **Emitir NF-e e NFC-e** de venda de forma simples.
- 🚫 **Cancelar notas fiscais e emitir Cartas de Correção (CC-e)**.
- 📦 **Fechamento Contábil Mensal:** gera pacote `.zip` com todos os XMLs e PDFs do mês para o seu contador.
- ☁️ **Nuvem 24h (Google Firestore):** todas as suas notas ficam salvas em tempo real na nuvem para consulta de qualquer lugar.

---

## 🚀 Guia Rápido de Instalação (Para Iniciantes)

Se você nunca mexeu com terminal, não se preocupe! Siga os 3 passos abaixo:

### Passo 1: Abra o Terminal e instale os pacotes básicos

Escolha a sua distribuição Linux:

#### 👉 Se você usa Ubuntu, Linux Mint, Debian ou Zorin OS:
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip openssl libxml2 libxslt1-dev
```

#### 👉 Se você usa Arch Linux ou CachyOS:
```bash
sudo pacman -S --noconfirm python python-pip openssl libxml2 libxslt
```

---

### Passo 2: Configurar o sistema automaticamente

Dentro da pasta do projeto, execute o script de instalação automática:

```bash
# 1. Entre na pasta do projeto
cd ~/Desktop/codes/NFE

# 2. Crie o ambiente e instale as dependências
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt

# 3. Crie o atalho no seu Menu de Aplicativos
./scripts/install.sh
```

---

### Passo 3: Abrir o NFE Manager

Você tem **duas formas** de abrir:

1. **Pelo Menu de Aplicativos (Recomendado):**  
   Abra o menu do seu computador (pressione a tecla `Super`/`Windows`) e pesquise por **NFE Manager**. Clique nele e a tela abrirá no seu navegador!

2. **Pelo Terminal:**
   ```bash
   ./scripts/run.sh
   ```
   Depois, acesse no seu navegador: **<http://localhost:8000>**

---

## 📖 Como Usar no Dia a Dia

### 1️⃣ Primeiro Acesso (Login)
Ao abrir a tela inicial, utilize o usuário padrão cadastrado:
- **E-mail:** `contasgeraljack@gmail.com`
- **Senha:** A senha cadastrada no seu primeiro uso.

---

### 2️⃣ Cadastrar seu Certificado Digital (A1)
Para consultar notas na SEFAZ ou emitir documentos:
1. Clique na aba superior **"Certificado"**.
2. Selecione o arquivo do seu certificado `.pfx` ou `.p12` do seu computador.
3. Digite a senha do certificado e clique em **"Enviar Certificado"**.
4. O sistema identificará automaticamente o **CNPJ**, **Razão Social** e **Data de Validade**.

---

### 3️⃣ Consultar e Baixar Notas Automaticamente (Robô SEFAZ)
- O sistema possui um **Robô Automático** que roda em segundo plano e busca todas as notas fiscais emitidas para a sua empresa na SEFAZ.
- Se quiser forçar uma busca imediata, vá na aba **"Distribuição DF-e"** ou **"Painel de Notas"** e clique em **"Buscar Notas na SEFAZ"**.

---

### 4️⃣ Visualizar Nota e Imprimir DANFE (PDF)
1. Na lista de notas fiscais, localize a nota desejada (você pode filtrar por data, fornecedor, número ou chave).
2. Clique no botão **"📄 DANFE (PDF)"** para visualizar e imprimir na hora.
3. Clique em **"📥 XML"** se quiser baixar o arquivo fiscal original.

---

### 5️⃣ Fechamento Mensal para o Contador
No final do mês, não perca tempo juntando arquivos um a um:
1. Clique no botão **"📦 Fechamento Contábil"**.
2. Escolha o **Mês** e o **Ano** de competência.
3. Clique em **"📥 Baixar Pacote ZIP (.zip)"**.
4. Pronto! O sistema entrega um arquivo único contendo todos os XMLs organizados, todos os DANFEs em PDF e uma planilha Excel com o resumo das notas.

---

### 6️⃣ Sincronização com a Nuvem (Google Firestore 24 Horas)
- Toda nota nova que entra no sistema é **automaticamente salva no Google Firestore**.
- Se você quiser enviar todas as notas existentes para a nuvem de uma só vez, basta clicar no botão **"☁️ Nuvem Firestore"** no topo da tela.

---

## ❓ Perguntas Frequentes (FAQ)

#### Preciso instalar o Java?
**Não!** O NFE Manager não usa Java, nem `.jnlp`, nem extensões de navegador antigas. Ele se comunica direto com a SEFAZ.

#### Onde ficam salvas as minhas notas?
Todas as notas ficam salvas no seu computador localmente em `data/nfe_database.db` e na pasta `data/xmls/`, além de ficarem espelhadas no **Google Cloud Firestore**.

#### O que fazer se a porta 8000 já estiver em uso?
Você pode rodar em outra porta definindo a variável `NFE_PORT`:
```bash
NFE_PORT=8080 ./scripts/run.sh
```

#### Como atualizar o sistema para a versão mais recente?
Abra o terminal na pasta do projeto e execute:
```bash
git pull
./scripts/install.sh
```

---

## 🛠️ Para Desenvolvedores & Suporte Técnico

| Endpoint | Descrição |
|---|---|
| `GET /` | Interface visual do Portal NF-e |
| `GET /api/status/{tipo}` | Verifica se a SEFAZ do seu estado está online |
| `GET /api/gestao/documentos` | Listagem paginada de notas com filtros avançados |
| `POST /api/gestao/firestore/sync-all` | Sincroniza em lote todas as notas locais para o Firestore |
| `GET /api/danfe/pdf/{chave}` | Renderiza o DANFE oficial em PDF |
| `GET /docs` | Documentação interativa Swagger/OpenAPI |

---

## 🔒 Segurança & Boas Práticas

Este projeto prioriza segurança por padrão:

- **Autenticação obrigatória:** todos os endpoints (exceto `/api/auth/login`, `/health`, `/`) exigem `X-Session-Token` válido.
- **Senhas:** armazenadas com **bcrypt** (rounds=12), com fallback transparente para hashes SHA-256 legados.
- **Segredos no disco:** senhas de certificado, tokens de Telegram/Webhook são cifrados com **Fernet (AES-128-CBC + HMAC-SHA256)** antes de ir para o banco/JSON.
- **Segredos no Git:** `.env`, `certs/`, `data/*.db*` estão em `.gitignore`. A chave Firebase do `.env` **NUNCA** é commitada.
- **CORS restritivo:** o coringa `*` foi removido. Apenas origens explícitas em `ALLOWED_ORIGINS` são aceitas.
- **SQL Injection:** o endpoint `/debug/nfe-completo` foi corrigido e fica disponível **apenas** quando `DEBUG=True`.

### ⚠️ Ação manual recomendada

Como o repositório foi publicado em algum momento com credenciais reais já commitadas no histórico, **recomenda-se rotacionar todas as chaves**:

1. **Firebase (você precisa fazer no console):**
   - Acesse [console.firebase.google.com](https://console.firebase.google.com/) → projeto `nfes-dd7ab`
   - Configurações do projeto → Chaves de API → clique em **Rotacionar** na chave exposta no histórico
   - Atualize o valor em `.env` no seu `.env` local
2. **Senha admin do sistema:** o `schema.py` agora gera uma senha aleatória na primeira inicialização (ela é exibida UMA vez no log). Faça login, troque via `/api/auth/alterar-senha`.
3. **Certificado A1:** se a senha do `.pfx` foi commitada em `certs/cert_meta.json` no histórico, recomenda-se emitir um novo certificado junto à Autoridade Certificadora.

### 🧹 Limpeza do histórico (opcional, destrutivo)

Se você precisar reescrever o histórico para remover vestígios de credenciais:

```bash
# 1. Instale a ferramenta
pip install git-filter-repo

# 2. Crie um arquivo replacements.txt com os termos a apagar
#    (preencha com os valores reais que você quer remover —
#     NUNCA coloque credenciais reais neste README!)
cat > /tmp/replacements.txt <<EOF
SUA_CHAVE_FIREBASE_AQUI==>FIREBASE_API_KEY_REMOVED
HASH_DA_SENHA_ADMIN_AQUI==>ADMIN_HASH_REMOVED
SENHA_ADMIN_AQUI==>ADMIN_PASSWORD_REMOVED
EOF

# 3. Reescreva o histórico
git filter-repo --replace-text /tmp/replacements.txt --force
git remote add origin git@github.com:SEU_USUARIO/NFE.git   # re-adiciona se necessário
git push origin --force --all
```

> ⚠️ **Atenção:** `git filter-repo` reescreve TODOS os hashes de commit. Todos os colaboradores precisam re-clonar ou fazer `git fetch && git reset --hard origin/main`.

---

## 📄 Licença
Distribuído sob licença LGPL-3.0 (compatível com PyNFe).
