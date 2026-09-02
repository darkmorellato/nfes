# Guia de Configuração do Ambiente Linux

Este guia detalha a configuração do ambiente para executar o NFE Manager em distribuições Linux, com foco em CachyOS, Ubuntu e Zorin OS.

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [CachyOS (Arch-based)](#cachyos)
3. [Ubuntu](#ubuntu)
4. [Zorin OS](#zorin-os)
5. [Configuração de Certificados](#configuração-de-certificados)
6. [Verificação do Ambiente](#verificação-do-ambiente)
7. [Solução de Problemas](#solução-de-problemas)

## Pré-requisitos

- Python 3.9 ou superior
- pip e venv
- Acesso sudo para instalação de pacotes
- Certificado Digital A1 (.pfx/.p12) ou A3 (token)

## CachyOS

### Instalação de Dependências

```bash
# Atualizar sistema
sudo pacman -Syu

# Instalar dependências do sistema
sudo pacman -S --noconfirm \
    python \
    python-pip \
    base-devel \
    openssl \
    libffi \
    libxml2 \
    libxslt \
    p11-kit \
    opensc
```

### Configuração do Ambiente

```bash
# Clonar o projeto
git clone <repo-url>
cd NFE

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# Instalar dependências Python
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Configuração de Token A3 (opcional)

```bash
# Verificar slots disponíveis
pkcs11-tool --list-slots

# Configurar módulo PKCS#11
export PKCS11_MODULE=/usr/lib/opensc-pkcs11.so

# Testar acesso ao token
pkcs11-tool --module $PKCS11_MODULE --list-objects
```

## Ubuntu

### Ubuntu 20.04 / 22.04 / 24.04

```bash
# Atualizar pacotes
sudo apt-get update

# Instalar dependências do sistema
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    openssl \
    p11-kit \
    p11-kit-modules \
    build-essential \
    libjpeg-dev \
    zlib1g-dev
```

### Configuração do Ambiente

```bash
# Clonar o projeto
git clone <repo-url>
cd NFE

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências Python
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Configuração de Token A3 (opcional)

```bash
# Instalar OpenSC
sudo apt-get install -y opensc

# Verificar token
pkcs11-tool --list-slots

# Configurar módulo
export PKCS11_MODULE=/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so
```

## Zorin OS

Zorin OS é baseado em Ubuntu, então os passos são idênticos aos do Ubuntu.

```bash
# Seguir exatamente os passos da seção Ubuntu acima
```

## Configuração de Certificados

### Certificado A1 (Arquivo .pfx/.p12)

1. Obtenha o arquivo de certificado digital (.pfx ou .p12) da Receita Federal ou certificadora autorizada
2. Acesse a interface web: http://localhost:8000
3. Vá para "Certificado Digital" > "Carregar Certificado"
4. Selecione o arquivo .pfx
5. Digite a senha do certificado
6. Clique em "Carregar Certificado"

**Armazenamento seguro:**
- O certificado é armazenado temporariamente em `certs/` durante a execução
- A senha é armazenada em memória apenas
- Nunca comite o diretório `certs/` no controle de versão

### Certificado A3 (Token/Hardware)

1. Instale o driver do token:

```bash
# Ubuntu/Debian
sudo apt-get install -y opensc

# CachyOS/Arch
sudo pacman -S --noconfirm opensc
```

2. Conecte o token na porta USB
3. Verifique se foi reconhecido:

```bash
pkcs11-tool --list-slots
```

4. Configure a variável de ambiente no `backend/config.py` ou `.env`:

```python
PKCS11_MODULE = "/usr/lib/opensc-pkcs11.so"  # CachyOS
# ou
PKCS11_MODULE = "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so"  # Ubuntu
```

5. Adapte o `cert_service.py` para usar PKCS#11 quando detectar token A3

## Verificação do Ambiente

Execute o verificador de dependências:

```bash
python3 -c "
import sys
print(f'Python: {sys.version}')

try:
    import lxml
    print(f'lxml: {lxml.__version__}')
except: print('lxml: FALTA')

try:
    import OpenSSL
    print(f'pyOpenSSL: {OpenSSL.__version__}')
except: print('pyOpenSSL: FALTA')

try:
    import signxml
    print(f'signxml: {signxml.__version__}')
except: print('signxml: FALTA')

try:
    import cryptography
    print(f'cryptography: {cryptography.__version__}')
except: print('cryptography: FALTA')

try:
    import requests
    print(f'requests: {requests.__version__}')
except: print('requests: FALTA')

import subprocess
try:
    result = subprocess.run(['openssl', 'version'], capture_output=True, text=True)
    print(f'OpenSSL: {result.stdout.strip()}')
except: print('OpenSSL: FALTA')
"
```

## Solução de Problemas

### Erro: "No module named 'lxml'"

```bash
# Ubuntu
sudo apt-get install -y libxml2-dev libxslt1-dev
pip install --force-reinstall lxml

# CachyOS
sudo pacman -S --noconfirm libxml2 libxslt
pip install --force-reinstall lxml
```

### Erro: "cryptography" ou "OpenSSL"

```bash
# Ubuntu
sudo apt-get install -y libssl-dev libffi-dev
pip install --force-reinstall cryptography pyOpenSSL

# CachyOS
sudo pacman -S --noconfirm openssl libffi
pip install --force-reinstall cryptography pyOpenSSL
```

### Erro de conexão com SEFAZ

```bash
# Verifique se o firewall não está bloqueando conexões HTTPS
sudo ufw status

# Teste conectividade
curl -v https://www.nfe.fazenda.gov.br/portal/principal.aspx

# Verifique o proxy (se houver)
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

### Token A3 não reconhecido

```bash
# Verificar se o usuário está no grupo plugdev
sudo usermod -aG plugdev $USER

# Reiniciar a sessão
logout && login

# Verificar permissões do dispositivo
ls -la /dev/bus/usb/
```

### Timeout nas requisições

Aumente o timeout em `backend/config.py`:

```python
TIMEOUT = 120  # segundos
```

### Erro de certificado expirado

Verifique a validade do certificado:

```bash
openssl pkcs12 -in certificado.pfx -nokeys -info
```

## Variáveis de Ambiente Recomendadas

Crie um arquivo `.env` na raiz do projeto:

```env
APP_NAME=NFE Manager
DEBUG=False
SECRET_KEY=<gere-uma-chave-forte-aqui>
CERT_DIR=./certs
HOMOLOGACAO=False
DEFAULT_UF=SP
TIMEOUT=120
```

Para produção, utilize:
- `HOMOLOGACAO=False`
- `DEBUG=False`
- `SECRET_KEY` forte e única
- Proxy reverso com HTTPS (Nginx/Caddy)

## Suporte

- Documentação PyNFe: https://github.com/TadaSoftware/PyNFe/wiki
- Issues: https://github.com/TadaSoftware/PyNFe/issues
