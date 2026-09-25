import os
import shutil
import tempfile

import pytest


@pytest.fixture(autouse=True, scope="session")
def isolate_test_database():
    """Isola a suíte de testes da base e dos arquivos de produção.

    Garante três coisas:

    1. o SQLite usado pelos testes é uma **cópia** de ``data/nfe_database.db``
       (nunca a base real);
    2. o schema é (re)aplicado sobre essa cópia — ``init_db()`` é idempotente e
       cria colunas/tabelas que existiam apenas em ``schema.py``;
    3. ``data/xmls/`` e ``data/danfe_pdfs/`` são redirecionados para um diretório
       temporário, de modo que nenhum teste apague ou sobrescreva XML fiscal real.
    """
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    real_db = os.path.join(raiz, "data", "nfe_database.db")

    temp_dir = tempfile.mkdtemp(prefix="nfe_test_")
    temp_db = os.path.join(temp_dir, "test_nfe.db")
    temp_xmls = os.path.join(temp_dir, "xmls")
    temp_pdfs = os.path.join(temp_dir, "danfe_pdfs")
    os.makedirs(temp_xmls, exist_ok=True)
    os.makedirs(temp_pdfs, exist_ok=True)

    if os.path.exists(real_db):
        shutil.copy2(real_db, temp_db)

    orig_env = os.environ.get("NFE_DB_PATH")
    orig_data_dir = os.environ.get("NFE_DATA_DIR")
    os.environ["NFE_DB_PATH"] = temp_db
    os.environ["NFE_DATA_DIR"] = temp_dir

    # --- Redireciona diretório de escrita de XML/PDF para a área temporária ---
    from backend.config import settings as _settings
    import backend.database as _db
    import backend.database.nfe_docs as _nfe_docs
    import backend.services.nfe_emissao_service as _emissao

    backups = {
        "settings.DATA_DIR": getattr(_settings, "DATA_DIR", None),
        "db.DATA_DIR": getattr(_db, "DATA_DIR", None),
        "db.XML_STORAGE_DIR": getattr(_db, "XML_STORAGE_DIR", None),
        "nfe_docs.XML_STORAGE_DIR": getattr(_nfe_docs, "XML_STORAGE_DIR", None),
        "emissao.XML_STORAGE_DIR": getattr(_emissao, "XML_STORAGE_DIR", None),
    }
    _settings.DATA_DIR = temp_dir
    _db.DATA_DIR = temp_dir
    _db.XML_STORAGE_DIR = temp_xmls
    _nfe_docs.XML_STORAGE_DIR = temp_xmls
    _emissao.XML_STORAGE_DIR = temp_xmls

    # --- Aplica o schema idempotente sobre a cópia isolada ---
    from backend.database import init_db
    init_db()

    # --- TLS da SEFAZ: mesmo comportamento da produção (sem InsecureRequestWarning) ---
    from backend.services.tls_sefaz import aplicar_verificacao_tls
    aplicar_verificacao_tls()

    # --- Isola a NUVEM: sem isto, cada documento de teste era empurrado para o
    # Firestore e o servidor de produção (rodando ao lado) o puxava de volta
    # para data/nfe_database.db — poluindo a base real com dados de teste.
    from unittest.mock import patch
    from backend.services import firestore_service as _fs
    from backend.services import notification_service as _notify

    _foradores = [
        patch.object(_fs, "sync_single_nfe_async", lambda *a, **k: None),
        patch.object(_fs, "sync_nfe_items_to_firestore_async", lambda *a, **k: None),
        patch.object(_fs, "sync_event_to_firestore_async", lambda *a, **k: None),
        patch.object(_fs, "sync_cliente_to_firestore_async", lambda *a, **k: None),
        patch.object(_fs, "sync_produto_to_firestore_async", lambda *a, **k: None),
        patch.object(_fs, "sync_cliente_to_firestore", lambda *a, **k: False),
        patch.object(_fs, "sync_produto_to_firestore", lambda *a, **k: False),
        patch.object(_fs, "flush_firestore_pending_queue", lambda *a, **k: None),
        patch.object(_notify, "dispatch_notification", lambda *a, **k: None),
    ]
    for p in _foradores:
        p.start()

    yield temp_db

    for p in reversed(_foradores):
        p.stop()

    # Restaura tudo
    if orig_env is not None:
        os.environ["NFE_DB_PATH"] = orig_env
    else:
        os.environ.pop("NFE_DB_PATH", None)
    if orig_env is None and orig_data_dir is None:
        os.environ.pop("NFE_DATA_DIR", None)

    _settings.DATA_DIR = backups["settings.DATA_DIR"]
    _db.DATA_DIR = backups["db.DATA_DIR"]
    _db.XML_STORAGE_DIR = backups["db.XML_STORAGE_DIR"]
    _nfe_docs.XML_STORAGE_DIR = backups["nfe_docs.XML_STORAGE_DIR"]
    _emissao.XML_STORAGE_DIR = backups["emissao.XML_STORAGE_DIR"]

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
