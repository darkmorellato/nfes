# JAN.md — NFE Manager

Portal NF-e local: servidor FastAPI (backend/) + UI web vanilla (frontend/, estática, sem build — não há package.json) acessada no navegador em http://localhost:8000. Não é microservice com migrations: usa SQLite (data/nfe_database.db; schema em backend/database/schema.py via init_db()).

## Comandos (repo NÃO tem CI, lint nem type-check)
- Setup: `./scripts/setup_linux.sh`  (apt/pacman + venv + pip install -r backend/requirements.txt)
- Run: `./scripts/run.sh`  ->  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
- Serviço: `./scripts/install_service.sh`  (systemd user: nfe-manager.service)
- Testes: com venv ativo, da raiz: `python -m pytest`  (ou `python -m unittest tests.test_all`)
- Python 3.14: exporte PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 antes do pip install (wheels cryptography/lxml)

## Arquitetura que não dá para inferir da árvore
- Routers (backend/routers/*.py, cada um `router = APIRouter()`) só orquestram; regra de negócio em backend/services/*.py; registro em backend/main.py via app.include_router(prefix="/api").
- Settings em backend/config.py (pydantic-settings, lê .env). CERT_DIR deve ser absoluto e terminar em "certs" (afirmado por tests/test_all.py::test_config).
- Comunicação fiscal real com SEFAZ/Receita via PyNFe (SOAP). Robô de sincronização em segundo plano em backend/services/sync_service.py (Distribuição DF-e).
- Firebase opcional (FIREBASE_ENABLED); backend só expõe /api/firebase-config.
- Relatórios/DANFE via BrazilFiscalReport + matplotlib + reportlab. Certificados A1 (PKCS#12) e A3 (PKCS#11/opensc).

## Convenções
- Routers não contêm regra de negócio; services sim. Respostas JSON. CORS via ALLOWED_ORIGINS.
- Persistência por funções em backend/database/* (sem ORM).
- Não exponha segredos no frontend além de /api/firebase-config.

## Gotchas (detalhados em memory/gotchas)
- SECRET_KEY: se não definida, config.py gera aleatória por startup -> quebra descriptografia Fernet de senhas de certificado após restart. Defina SECRET_KEY em produção.
- nfe_emissao_service.py grava DANFE em 'data/danfe_pdfs' hardcoded (linhas ~583 e ~1049) — bug fora do bundle também.
- DATA_DIR/CERT_DIR/BASE_DIR derivam de __file__ em config.py/database; sob PyInstaller (sys._MEIPASS, bundle read-only) quebram.
- tests/test_all.py limpa data/xmls e data/danfe_pdfs relativos ao CWD: mudar DATA_DIR para XDG quebra a suíte a menos que se defina NFE_DATA_DIR=./data no teste.
- A3 (token): exige p11-kit + opensc no host; PKCS11_MODULE difere por distro (/usr/lib/opensc-pkcs11.so Arch vs /usr/lib/x86_64-linux-gnu/opensc-pkcs11.so Ubuntu).

## Empacotamento (decisão aprovada, NÃO implementada ainda)
AppImage único portátil: backend congelado (PyInstaller) + Chromium embutido via Playwright em modo --app. Plano Fase0(spike) -> Fase1(código bundle-ready) -> Fase2(freeze) -> Fase3(AppDir/AppRun/.desktop/install.sh/uninstall.sh + fallback FUSE) -> Fase4(validação Ubuntu/Fedora/Arch, A1/A3, sem-FUSE). Exige glibc >= 2.35; A3 exige p11-kit no sistema. Push final: origin (github.com/darkmorellato/nfes.git) branch main.
