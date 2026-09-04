import os
import shutil
import tempfile
import pytest

@pytest.fixture(autouse=True, scope="session")
def isolate_test_database():
    """Garante que a suíte de testes utilize uma cópia isolada do banco SQLite,
    evitando poluir ou alterar os dados reais de produção em data/nfe_database.db.
    """
    real_db = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "nfe_database.db"))
    temp_dir = tempfile.mkdtemp(prefix="nfe_test_")
    temp_db = os.path.join(temp_dir, "test_nfe.db")

    if os.path.exists(real_db):
        shutil.copy2(real_db, temp_db)
    else:
        from backend.database import init_db
        os.environ["NFE_DB_PATH"] = temp_db
        init_db()

    orig_path = os.environ.get("NFE_DB_PATH")
    os.environ["NFE_DB_PATH"] = temp_db

    yield temp_db

    # Restaura variável e remove diretório temporário
    if orig_path:
        os.environ["NFE_DB_PATH"] = orig_path
    else:
        os.environ.pop("NFE_DB_PATH", None)

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
