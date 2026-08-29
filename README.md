# NFE Manager — Portal NF-e Local para Linux

## Visão Geral

O **NFE Manager** é um portal NF-e local, escrito em Python (FastAPI) com
interface web vanilla, que replica a experiência do portal oficial da SEFAZ
(`www.nfe.fazenda.gov.br`) sem exigir Java, sem exigir `.jnlp` e com
integração direta aos webservices da SEFAZ/Receita Federal por meio da
biblioteca **PyNFe**. Suporta NF-e, NFC-e, MDF-e, NFS-e, Manifestação do
Destinatário, EPEC, Distribuição DF-e, geração de DANFE/DANFE-Simplificado
em PDF via **brazilfiscalreport**, relatórios fiscais e gerenciamento de
certificado digital A1.

## Por que existe

O portal oficial da SEFAZ depende do **Java Web Start (`.jnlp`)** para
disponibilizar o *assinador* de NF-e. Esse assinador utiliza a
**Windows CryptoAPI** (CSP/PKCS#11 específico do Windows) e o **NSS** do
navegador Mozilla/Firefox. Em sistemas Linux modernos, essa cadeia quebra
de várias formas:

- O `.jnlp` requer um JRE com Web Start — removido do OpenJDK a partir do
  Java 11.
- A CryptoAPI da Microsoft não está disponível fora do Windows.
- O bridge `libpkcs11` ↔ NSS tem problemas de detecção de token A3
  (SafeNet, Gemalto, etc.) na maioria das distros.
- O Java Web Start não respeita mais os manifests de permissões dos
  pacotes `.deb`/`.rpm` recentes.

O resultado: **a maioria dos contadores e empresas que migraram de
Windows para Linux (Ubuntu, Zorin, CachyOS, Fedora, Mint) perderam o
acesso direto ao portal da SEFAZ via navegador**.

O NFE Manager resolve isso **substituindo todo o stack cliente** por um
backend Python que:

1. Usa o PyNFe para gerar o XML da NF-e e assinar com `cryptography`
   (PKCS#12 para A1, PKCS#11 via `python-pkcs11` para A3).
2. Conversa via SOAP direto com os WSDLs da SEFAZ (sem `.jnlp`, sem
   applets, sem NPAPI).
3. Renderiza o DANFE em PDF no servidor usando `brazilfiscalreport`.
4. Expõe a mesma interface visual do portal SEFAZ (paleta dourada, mesmo
   layout, mesmas opções) para reduzir a curva de aprendizado.

> **Sem Java. Sem .jnlp. Sem Windows.**

## Recursos

- **NF-e / NFC-e:** Status do Serviço, Consulta por Chave de Acesso,
  Consulta de Cadastro, Distribuição DF-e (NSU), EPEC, Manifestação do
  Destinatário (NT 2012.002), Eventos (Cancelamento, Carta de Correção,
  Inutilização).
- **DANFE / DANFE Simplificado:** Geração de PDF oficial via
  `brazilfiscalreport` (com código de barras e numeração de protocolo).
- **Certificado Digital A1/A3:** Upload de `.pfx`/`.p12`, leitura via
  PKCS#11, exibição de informações (CNPJ, validade, emissor).
- **Relatórios Fiscais em PDF:** Status de Documentos, Volume Mensal,
  Conformidade Fiscal, Emissores (com gráficos de pizza e barras).
- **Consultas auxiliares (informativas):** NCM (tabela estática local),
  GTIN (validador de dígito verificador mod 10), CCC (aponta para o
  portal oficial — o PyNFe não implementa este webservice).
- **Navegação completa estilo SEFAZ:** menu superior com abas,
  breadcrumb, badge de ambiente (Homologação/Produção) e UF.

## Instalação

### Requisitos

- Python 3.11+ (3.12 e 3.13 testados; 3.14 suportado com flag)
- `pip`, `venv`, `libssl`, `libffi`, `libxml2`, `libxslt`
- Certificado A1 (`.pfx`/`.p12`) ou A3 (token PKCS#11) para operações
  que exigem autenticação

### Passos

```bash
# 1) Ambiente virtual
python3.11+ -m venv venv

# 2) Dependências Python
./venv/bin/pip install -r backend/requirements.txt

# 3) (somente Python 3.14) flag de compatibilidade pyo3
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 ./venv/bin/pip install -r backend/requirements.txt
```

> Se estiver em Python 3.14, exporte `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`
> antes do `pip install` para que wheels como `cryptography` e
> `lxml` consigam compilar/instalar via ABI3.

### Dependências do sistema (Ubuntu/Zorin/Debian)

```bash
sudo apt-get install -y python3 python3-venv python3-dev \
    libssl-dev libffi-dev libxml2-dev libxslt1-dev \
    openssl p11-kit build-essential
```

### Dependências do sistema (Arch/CachyOS)

```bash
sudo pacman -S --noconfirm python python-pip base-devel \
    openssl libffi libxml2 libxslt p11-kit
```

## Como rodar

```bash
./venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: <http://localhost:8000>

> O `--reload` recarrega o backend automaticamente a cada alteração em
> `backend/`. Os arquivos de `frontend/` são servidos como estáticos, então
> basta atualizar o navegador (`Ctrl+F5`) para ver mudanças de HTML/CSS/JS.

## Endpoints

| Método | Rota                              | Descrição                                |
|--------|-----------------------------------|------------------------------------------|
| GET    | `/`                               | Interface web                            |
| GET    | `/api/status/{tipo}`              | Status do serviço (NF-e/NFC-e)           |
| GET    | `/api/consulta/chave`             | Consulta NF-e por chave de 44 dígitos    |
| GET    | `/api/consulta/cadastro`          | Consulta cadastro (CNPJ/CPF/IE)          |
| GET    | `/api/consulta/distribuicao`      | Distribuição DF-e (NSU)                  |
| POST   | `/api/nfe/autorizar`              | Autorização de NF-e                      |
| POST   | `/api/nfe/cancelar`               | Cancelamento de NF-e                     |
| POST   | `/api/nfe/carta-correcao`         | Carta de Correção Eletrônica             |
| POST   | `/api/nfe/inutilizar`             | Inutilização de numeração                |
| POST   | `/api/nfe/manifestacao`           | Manifestação do Destinatário             |
| GET    | `/api/danfe/parse/{chave}`        | Faz parse do XML e devolve JSON          |
| GET    | `/api/danfe/pdf/{chave}`          | Retorna o DANFE em PDF                   |
| POST   | `/api/danfe/upload-xml`           | Envia XML e renderiza DANFE              |
| GET    | `/api/certificado/info`           | Info do certificado carregado            |
| POST   | `/api/certificado/upload`         | Upload de certificado A1                 |
| DELETE | `/api/certificado`                | Remove certificado                       |
| GET    | `/api/fiscal/{status,volume-mensal,compliance,emissores}` | Relatórios PDF |
| GET    | `/docs`                           | Documentação OpenAPI (Swagger UI)        |

## Estrutura

```
NFE/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Settings (.env)
│   ├── requirements.txt
│   ├── routers/                # Endpoints REST
│   │   ├── status.py
│   │   ├── cert.py
│   │   ├── nfe.py
│   │   ├── nfce.py
│   │   ├── mdfe.py
│   │   ├── nfse.py
│   │   └── reports.py
│   └── services/
│       ├── pynfe_service.py    # Wrapper PyNFe (NF-e/NFC-e/MDFe)
│       ├── cert_service.py     # PKCS#12 + PKCS#11
│       └── report_service.py   # PDFs com brazilfiscalreport + matplotlib
├── frontend/
│   ├── index.html              # Interface estilo SEFAZ
│   ├── css/style.css           # Paleta dourada SEFAZ
│   └── js/
│       ├── api.js              # Cliente REST
│       └── app.js              # Lógica de UI + validações
├── scripts/
│   ├── setup_linux.sh          # Instala deps de sistema
│   ├── install_service.sh      # systemd user unit
│   └── run.sh                  # Atalho de execução
├── docs/
│   └── SETUP.md                # Guia detalhado
├── .env.example
├── .gitignore
├── README.md
└── venv/                       # Ambiente virtual
```

## Próximos passos

- [ ] **Integração com CCC** — quando a SEFAZ publicar o WSDL público do
      Cadastro Centralizado de Contribuinte, expor via `/api/ccc/*`.
- [ ] **EPEC de fato** — adicionar cliente SOAP para o serviço
      `RecepcaoEPEC` (atualmente apenas *consulta* via chave).
- [ ] **NF-e 4.00 → NT 2024.003** — acompanhar notas técnicas e
      atualizar schemas em `pynfe_service.py`.
- [ ] **MDF-e em produção** — terminar o ciclo de Encerramento + Inclusão
      de Condutor.
- [ ] **NFS-e nacional** — padronizar com o modelo da ABRASF quando a
      prefeitura/UF adotar.
- [ ] **Cache de certificado** — suportar cache criptografado em disco
      (atualmente o `.pfx` é recarregado a cada startup).
- [ ] **Sincronização de NCM/GTIN** — expor endpoint para atualizar a
      tabela local a partir da TIPI/Receita Federal.

## Licença

LGPL-3.0 (compatível com PyNFe).

## Suporte

- Documentação local: <http://localhost:8000/docs>
- PyNFe: <https://github.com/TadaSoftware/PyNFe>
- SEFAZ NF-e: <https://www.nfe.fazenda.gov.br/>
- Issues do projeto: abra uma issue neste repositório.
