import os
import sqlite3
from contextlib import contextmanager

from backend.config import settings

DATA_DIR = settings.DATA_DIR
DB_PATH = os.path.join(DATA_DIR, "nfe_database.db")
XML_STORAGE_DIR = os.path.join(DATA_DIR, "xmls")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(XML_STORAGE_DIR, exist_ok=True)


@contextmanager
def get_db_connection():
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Re-exports from schema
from .schema import init_db, auto_register_disk_certificates

# Re-exports from certificates
from .certificates import (
    save_certificate_record,
    list_certificates_db,
    get_certificate_record,
    delete_certificate_record,
    update_cert_sync_state,
)

# Re-exports from nfe_docs
from .nfe_docs import (
    save_nfe_doc,
    save_nfe_event,
    list_nfe_docs,
    get_nfe_detail,
    list_nfe_saidas,
    cancelar_nfe_doc,
    save_inutilizacao,
    list_inutilizacoes,
)

# Re-exports from financeiro
from .financeiro import (
    sync_duplicatas_from_xmls,
    list_contas_a_pagar,
    pagar_duplicata,
    sync_contas_receber_from_xmls,
    list_contas_a_receber,
    receber_duplicata,
    get_dre_consolidado,
    get_impostos_interestaduais,
    get_dre_tendencia,
    get_simples_nacional_apuracao,
    get_dre_produtos_margem,
)

# Re-exports from estoque
from .estoque import (
    checkin_nfe_estoque,
    get_historico_estoque,
    get_conferencia,
    salvar_conferencia,
)

# Re-exports from analytics
from .analytics import (
    get_analytics_dashboard,
    get_price_history,
    get_abc_curve,
    get_price_divergences,
    get_intercompany_operations,
    get_inadimplencia,
    get_auditoria_fornecedores,
)

# Re-exports from cadastros
from .cadastros import (
    save_cliente,
    list_clientes,
    delete_cliente,
    save_produto,
    get_produto_detail,
    sugerir_dados_fiscais_produto,
    list_produtos,
    delete_produto,
    get_next_nfe_number,
    get_empresas,
)

# Re-exports from notifications
from .notifications import add_notification, list_notifications, mark_notifications_read

# Re-exports from sync_state
from .sync_state import set_sync_state, get_sync_state

# Re-exports from limpeza
from .limpeza import (
    preview_limpeza_nfes,
    executar_limpeza_nfes,
    auditoria_xmls_orfaos,
    apagar_xmls_orfaos,
    auditoria_rapida_base,
)

# Re-exports from gap_detector
from .gap_detector import auditar_saltos_numeracao

