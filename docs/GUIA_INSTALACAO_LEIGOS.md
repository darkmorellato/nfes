# 📖 Guia de Instalação e Uso para Iniciantes — NFE Manager

Este guia foi feito para **qualquer pessoa conseguir instalar e usar o sistema**, mesmo sem nenhum conhecimento prévio de programação ou linha de comando.

---

## 🪟 Instalação no Windows (Passo a Passo)

### 1️⃣ Passo 1: Instalar o Python (se ainda não tiver)
1. Acesse o site oficial do Python: **[https://www.python.org/downloads/](https://www.python.org/downloads/)**
2. Clique no botão amarelo **"Download Python 3.x"**.
3. Abra o instalador baixado.
4. ⚠️ **MUITO IMPORTANTE:** Na primeira janelinha que abrir, **marque a caixinha na parte inferior**:
   - ☑️ **"Add Python to PATH"** (ou *"Adicionar Python às variáveis de ambiente"*).
5. Clique em **"Install Now"** e aguarde concluir.

---

### 2️⃣ Passo 2: Baixar o Sistema NFE Manager
1. No topo desta página do GitHub, clique no botão verde **`Code`** e depois em **`Download ZIP`**.
2. Vá até a sua pasta de *Downloads*, clique com o botão direito no arquivo baixado (`nfes-main.zip`) e escolha **"Extrair Tudo..."**.
3. Mova a pasta extraída para um local de sua preferência (exemplo: `C:\NFE-Manager` ou na sua pasta `Documentos`).

---

### 3️⃣ Passo 3: Iniciar o Sistema (1 Clique)
1. Abra a pasta do NFE Manager.
2. Dê **dois cliques** no arquivo:
   - 👉 **`iniciar_windows.bat`** (ou `instalar_windows.bat`).
3. Uma janelinha preta se abrirá e fará a instalação automática de todos os pacotes necessários (isso só demora cerca de 1 minuto na primeira vez).
4. Em seguida, seu navegador de internet abrirá automaticamente na página do sistema:
   - **`http://127.0.0.1:8000`**

> 💡 **Dica de Ouro:** Você pode criar um atalho na sua Área de Trabalho! Clique com o botão direito em `iniciar_windows.bat` ➡️ **"Enviar para"** ➡️ **"Área de trabalho (criar atalho)"**.

---

## 🐧 Instalação no Linux (Ubuntu, Debian, Linux Mint, Zorin, Arch, Fedora)

### 1️⃣ Passo 1: Baixar ou Clonar o Repositório
Abra o seu terminal e execute:
```bash
git clone https://github.com/darkmorellato/nfes.git
cd nfes
```

### 2️⃣ Passo 2: Instalar e Iniciar
Basta dar permissão e executar o script de inicialização automática:
```bash
chmod +x iniciar_linux.sh instalar.sh
./iniciar_linux.sh
```
O script verifica o Python, cria o ambiente virtual isolado, instala todas as dependências e abre o sistema automaticamente no seu navegador em `http://127.0.0.1:8000`.

---

## 🔄 Como Atualizar o Sistema (Novas Versões)

Sempre que fizermos melhorias, correções de layout ou novas funções no GitHub, você pode atualizar de 3 formas muito fáceis:

### Método 1: Pelo Botão na Tela do Sistema (Mais Fácil - 1 Clique)
1. No topo direito do sistema (na barra superior), clique no botão **`🔄 Atualizar`**.
2. Uma janela se abrirá mostrando a sua versão atual e as novidades disponíveis.
3. Clique no botão verde **`🚀 Atualizar Agora (1-Clique)`**.
4. O sistema baixa as novidades do GitHub e atualiza tudo sozinho!

### Método 2: Automático ao Iniciar
- Toda vez que você inicia o sistema pelo `iniciar_windows.bat` ou `iniciar_linux.sh`, ele já confere se há novidades no repositório e sincroniza automaticamente.

### Método 3: Pelo Terminal / Prompt
Na pasta do projeto, basta digitar:
```bash
git pull origin main
```

---

## 🔑 Primeiro Acesso ao Sistema

1. Abra **`http://127.0.0.1:8000`** no seu navegador.
2. **E-mail de Acesso:** `contasgeraljack@gmail.com`
3. **Senha:** No primeiro uso, o sistema exibirá uma senha inicial na janela do terminal.
4. **Troca Obrigatória:** Por segurança, no primeiro login o sistema solicitará que você cadastre a sua própria senha pessoal.

---

## 🏢 Cadastrando seu Certificado Digital A1

1. No menu superior, clique em **`🏢 Certificados A1`**.
2. Clique em **`Adicionar Certificado`**.
3. Selecione o arquivo do seu certificado digital (formato `.pfx` ou `.p12`) e digite a senha dele.
4. Pronto! O sistema já começará a sincronizar com a SEFAZ, baixar notas emitidas contra o seu CNPJ e permitir a emissão de novas notas.

---

## ❓ Dúvidas Frequentes (FAQ)

### ❓ "Apareceu erro: Python não encontrado"
- **Solução:** Você precisa instalar o Python e marcar a opção **"Add Python to PATH"** durante a instalação, conforme explicado no Passo 1 do Windows. Após instalar, feche a janelinha e abra o `iniciar_windows.bat` novamente.

### ❓ "Como fechar o sistema?"
- **Solução:** Basta fechar a janelinha do terminal/Prompt que ficou aberta em segundo plano.

### ❓ "Posso usar em rede local com outros computadores da minha empresa?"
- **Solução:** Sim! Basta que os outros computadores na mesma rede acessem o IP do computador principal (exemplo: `http://192.168.1.100:8000`).

---

## 📞 Precisa de Ajuda?
Se encontrar qualquer dificuldade, abra uma solicitação em:
👉 **[https://github.com/darkmorellato/nfes/issues](https://github.com/darkmorellato/nfes/issues)**
