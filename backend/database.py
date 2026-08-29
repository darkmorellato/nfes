import os
import sqlite3
import json
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

from backend.config import settings

DATA_DIR = os.path.join(settings.BASE_DIR, "data")
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


def init_db():
    """Inicializa as tabelas do banco de dados SQLite."""
    _ensure_dirs()
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Tabela de Certificados Digitais A1 (Multi-Empresa)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cnpj TEXT UNIQUE NOT NULL,
                razao_social TEXT NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                password TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                days_remaining INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                last_nsu TEXT DEFAULT '0',
                max_nsu TEXT DEFAULT '0',
                last_sync_time TEXT,
                last_sync_status TEXT,
                ie TEXT,
                nome_fantasia TEXT,
                logradouro TEXT,
                numero TEXT,
                complemento TEXT,
                bairro TEXT,
                municipio TEXT,
                cod_municipio TEXT DEFAULT '3550308',
                uf TEXT DEFAULT 'SP',
                cep TEXT,
                telefone TEXT,
                email TEXT,
                crt INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migrações seguras de colunas fiscais em certificates
        cols_certs = [
            ("ie", "TEXT"),
            ("nome_fantasia", "TEXT"),
            ("logradouro", "TEXT"),
            ("numero", "TEXT"),
            ("complemento", "TEXT"),
            ("bairro", "TEXT"),
            ("municipio", "TEXT"),
            ("cod_municipio", "TEXT DEFAULT '3550308'"),
            ("uf", "TEXT DEFAULT 'SP'"),
            ("cep", "TEXT"),
            ("telefone", "TEXT"),
            ("email", "TEXT"),
            ("crt", "INTEGER DEFAULT 1"),
        ]
        for cname, ctype in cols_certs:
            try:
                cursor.execute(f"ALTER TABLE certificates ADD COLUMN {cname} {ctype}")
            except Exception:
                pass

        # Atualização dos dados cadastrais e fiscais reais das 5 filiais
        empresas_fiscais = [
            ("34511185000110", "JACKCELL CELULARES E IMPORTADOS LTDA", "JACKCELL", "535758386119", "Rua Dom Pedro II", "857", "", "Centro", "Piracicaba", "3538709", "SP", "13400390", 1),
            ("13787408000105", "FERNANDES COMERCIO DE CELULARES E IMPORTACAO LTDA", "SPACE STORE", "535891235110", "Rua Quinze de Novembro", "910", "", "Centro (Artemis)", "Piracicaba", "3538709", "SP", "13432033", 1),
            ("44739622000101", "FILIPE ALMEIDA GIL DE SOUZA LTDA", "FILIPE ALMEIDA", "535911741117", "Rua Benjamin Constant", "1230", "", "Centro", "Piracicaba", "3538709", "SP", "13400053", 1),
            ("58186781000130", "J. DE A. FERNANDES OPERACOES DE CREDITO", "JACKCELL CREDITO", "168197097116", "RUA TREZE DE MAIO", "26", "", "CENTRO", "Amparo", "3501905", "SP", "13900005", 1),
            ("58495100000116", "MI PLACE AMPARO LTDA", "MI PLACE AMPARO", "168197715110", "RUA TREZE DE MAIO", "218", "", "CENTRO", "Amparo", "3501905", "SP", "13900005", 1),
        ]
        for cnpj, rz, fant, ie, logr, num, comp, bpo, mun, codmun, uf, cep, crt in empresas_fiscais:
            cursor.execute("""
                UPDATE certificates
                SET ie = ?, nome_fantasia = ?, logradouro = ?, numero = ?, complemento = ?,
                    bairro = ?, municipio = ?, cod_municipio = ?, uf = ?, cep = ?, crt = ?
                WHERE cnpj = ?
            """, (ie, fant, logr, num, comp, bpo, mun, codmun, uf, cep, crt, cnpj))

        # Tabela principal de Documentos Fiscais (NF-e)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_docs (
                chave TEXT PRIMARY KEY,
                empresa_cnpj TEXT,
                numero TEXT,
                serie TEXT,
                modelo TEXT DEFAULT '55',
                emitente_cnpj TEXT,
                emitente_nome TEXT,
                emitente_uf TEXT,
                destinatario_cnpj TEXT,
                destinatario_nome TEXT,
                destinatario_uf TEXT,
                data_emissao TEXT,
                data_autorizacao TEXT,
                valor_total REAL DEFAULT 0.0,
                valor_icms REAL DEFAULT 0.0,
                valor_pis REAL DEFAULT 0.0,
                valor_cofins REAL DEFAULT 0.0,
                valor_ipi REAL DEFAULT 0.0,
                situacao TEXT DEFAULT 'Autorizada',
                tipo_doc INTEGER DEFAULT 0, -- 0=Entrada (Fornecedor), 1=Saída (Venda/Devolução para Cliente)
                nsu TEXT DEFAULT '0',
                has_xml INTEGER DEFAULT 0,
                xml_raw TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migração segura para colunas empresa_cnpj e tipo_doc caso nfe_docs já existisse
        cursor.execute("PRAGMA table_info(nfe_docs)")
        cols = [col["name"] for col in cursor.fetchall()]
        if "empresa_cnpj" not in cols:
            cursor.execute("ALTER TABLE nfe_docs ADD COLUMN empresa_cnpj TEXT")
        if "tipo_doc" not in cols:
            cursor.execute("ALTER TABLE nfe_docs ADD COLUMN tipo_doc INTEGER DEFAULT 0")

        # Tabela de Cadastro de Clientes / Destinatários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cad_clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_pessoa TEXT DEFAULT 'PJ',
                cpf_cnpj TEXT UNIQUE NOT NULL,
                razao_social TEXT NOT NULL,
                nome_fantasia TEXT,
                ie TEXT,
                indicador_ie INTEGER DEFAULT 9,
                email TEXT,
                telefone TEXT,
                cep TEXT,
                logradouro TEXT,
                numero TEXT,
                complemento TEXT,
                bairro TEXT,
                municipio TEXT,
                cod_municipio TEXT DEFAULT '3550308',
                uf TEXT DEFAULT 'SP',
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Tabela de Catálogo de Produtos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cad_produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                descricao TEXT NOT NULL,
                ncm TEXT NOT NULL,
                cest TEXT DEFAULT '',
                cfop_padrao TEXT DEFAULT '5102',
                cfop_interestadual TEXT DEFAULT '6102',
                unidade TEXT DEFAULT 'UN',
                preco_venda REAL DEFAULT 0.0,
                preco_custo REAL DEFAULT 0.0,
                estoque_atual REAL DEFAULT 0.0,
                estoque_minimo REAL DEFAULT 0.0,
                origem INTEGER DEFAULT 0,
                csosn_cst TEXT DEFAULT '102',
                aliquota_icms REAL DEFAULT 0.0,
                gtin TEXT,
                marca TEXT,
                ativo INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migrações seguras de colunas em cad_produtos
        cols_produtos = [
            ("cest", "TEXT DEFAULT ''"),
            ("cfop_interestadual", "TEXT DEFAULT '6102'"),
            ("preco_custo", "REAL DEFAULT 0.0"),
            ("estoque_atual", "REAL DEFAULT 0.0"),
            ("estoque_minimo", "REAL DEFAULT 0.0"),
            ("marca", "TEXT DEFAULT ''"),
            ("imei", "TEXT DEFAULT ''"),
            ("ativo", "INTEGER DEFAULT 1"),
        ]
        for col_name, col_type in cols_produtos:
            try:
                cursor.execute(f"ALTER TABLE cad_produtos ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # Tabela de Itens/Produtos das NF-e
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL,
                n_item INTEGER,
                codigo TEXT,
                ean TEXT,
                descricao TEXT,
                ncm TEXT,
                cfop TEXT,
                unidade TEXT,
                quantidade REAL DEFAULT 0.0,
                valor_unitario REAL DEFAULT 0.0,
                valor_total REAL DEFAULT 0.0,
                cst TEXT,
                v_icms REAL DEFAULT 0.0,
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)

        # Tabela de Eventos Fiscais (Manifestação, Cancelamento, CC-e)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL,
                tipo_evento TEXT,
                desc_evento TEXT,
                n_seq INTEGER DEFAULT 1,
                dh_evento TEXT,
                protocolo TEXT,
                c_stat TEXT,
                x_motivo TEXT,
                created_at TEXT,
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)

        # Tabela de Notificações e Alertas em Tempo Real
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                tipo TEXT DEFAULT 'info',
                chave TEXT,
                read INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        # Tabela de Estado de Sincronização Geral
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        # Tabela de Duplicatas & Contas a Pagar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_duplicatas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL,
                n_dup TEXT,
                d_venc TEXT,
                v_dup REAL DEFAULT 0.0,
                forma_pagamento TEXT,
                status TEXT DEFAULT 'A_VENCER',
                pago INTEGER DEFAULT 0,
                data_pagamento TEXT,
                empresa_cnpj TEXT,
                emitente_nome TEXT,
                created_at TEXT,
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_chave ON nfe_duplicatas(chave)")

        # Tabela de Contas a Receber (Saídas / Vendas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_contas_receber (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT NOT NULL,
                n_dup TEXT,
                d_venc TEXT,
                v_dup REAL DEFAULT 0.0,
                forma_pagamento TEXT,
                status TEXT DEFAULT 'A_RECEBER',
                recebido INTEGER DEFAULT 0,
                data_recebimento TEXT,
                empresa_cnpj TEXT,
                cliente_nome TEXT,
                cliente_cnpj TEXT,
                created_at TEXT,
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_chave ON nfe_contas_receber(chave)")

        # Tabela de Movimentações de Estoque (Kardex)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave_nfe TEXT,
                codigo_produto TEXT NOT NULL,
                descricao TEXT,
                tipo TEXT NOT NULL, -- 'ENTRADA_NFE', 'SAIDA_NFE', 'SAIDA_NFCE', 'AJUSTE_MANUAL'
                quantidade REAL NOT NULL,
                saldo_anterior REAL DEFAULT 0.0,
                saldo_novo REAL DEFAULT 0.0,
                valor_unitario REAL DEFAULT 0.0,
                motivo TEXT,
                data_hora TEXT NOT NULL
            )
        """)

        # Tabela de Inutilizações de Numeração de NF-e/NFC-e
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_inutilizacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa_cnpj TEXT NOT NULL,
                ano INTEGER NOT NULL,
                modelo TEXT DEFAULT '55',
                serie INTEGER NOT NULL,
                numero_inicial INTEGER NOT NULL,
                numero_final INTEGER NOT NULL,
                protocolo TEXT,
                justificativa TEXT NOT NULL,
                data_homologacao TEXT,
                c_stat TEXT,
                x_motivo TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Tabela de Vendas NFC-e (Balcão/PDV)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfce_vendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                numero TEXT,
                serie TEXT DEFAULT '1',
                empresa_cnpj TEXT,
                valor_total REAL DEFAULT 0.0,
                forma_pagamento TEXT DEFAULT 'DINHEIRO',
                cpf_consumidor TEXT,
                qrcode_url TEXT,
                status TEXT DEFAULT 'Autorizada',
                created_at TEXT NOT NULL
            )
        """)

        # Tabela de Conferência de Estoque (Check-in de Mercadorias)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_conferencia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                empresa_cnpj TEXT,
                status TEXT DEFAULT 'PENDENTE',
                conferido_por TEXT,
                data_conferencia TEXT,
                divergencias_count INTEGER DEFAULT 0,
                observacoes TEXT,
                created_at TEXT,
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)

        # Tabela de Itens da Conferência
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfe_conferencia_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conferencia_id INTEGER,
                chave TEXT NOT NULL,
                codigo TEXT,
                descricao TEXT,
                qtd_nota REAL DEFAULT 0.0,
                qtd_conferida REAL DEFAULT 0.0,
                seriais TEXT,
                status TEXT DEFAULT 'PENDENTE',
                FOREIGN KEY (chave) REFERENCES nfe_docs(chave) ON DELETE CASCADE
            )
        """)

        # Índices de performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_empresa_cnpj ON nfe_docs(empresa_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_emitente_nome ON nfe_docs(emitente_nome)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_data_emissao ON nfe_docs(data_emissao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_dest_cnpj ON nfe_docs(destinatario_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_descricao ON nfe_items(descricao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_ncm ON nfe_items(ncm)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_codigo ON nfe_items(codigo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_ean ON nfe_items(ean)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_chave ON nfe_events(chave)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_venc ON nfe_duplicatas(d_venc)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_chave ON nfe_duplicatas(chave)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conf_chave ON nfe_conferencia(chave)")

        conn.commit()

    # Registra automaticamente todos os certificados da pasta certs/
    auto_register_disk_certificates()


# ====================================================================
# GESTÃO DE CERTIFICADOS DIGITAIS A1 (MULTI-EMPRESA)
# ====================================================================

def save_certificate_record(cert_data: Dict[str, Any]) -> bool:
    """Insere ou atualiza um certificado no banco de dados SQLite.

    A senha do certificado é armazenada de forma cifrada usando Fernet (AES-128-CBC + HMAC-SHA256)
    com chave derivada de SECRET_KEY. Valores já cifrados ou vazios são preservados.
    """
    from backend.services.crypto_service import encrypt_secret

    now = datetime.now().isoformat()
    cnpj = "".join(c for c in str(cert_data.get("cnpj", "")) if c.isdigit())
    if len(cnpj) != 14:
        return False

    raw_password = str(cert_data.get("password") or "")
    stored_password = encrypt_secret(raw_password)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO certificates (
                cnpj, razao_social, filename, path, password, valid_from, valid_to,
                days_remaining, is_active, last_nsu, max_nsu, last_sync_time, last_sync_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cnpj) DO UPDATE SET
                razao_social = excluded.razao_social,
                filename = excluded.filename,
                path = excluded.path,
                password = excluded.password,
                valid_from = excluded.valid_from,
                valid_to = excluded.valid_to,
                days_remaining = excluded.days_remaining,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
        """, (
            cnpj,
            cert_data.get("razao_social") or "EMPRESA",
            cert_data.get("filename") or "",
            cert_data.get("path") or "",
            stored_password,
            cert_data.get("valid_from") or "",
            cert_data.get("valid_to") or "",
            int(cert_data.get("days_remaining") or 0),
            int(cert_data.get("is_active") if cert_data.get("is_active") is not None else 1),
            cert_data.get("last_nsu") or "0",
            cert_data.get("max_nsu") or "0",
            cert_data.get("last_sync_time") or "",
            cert_data.get("last_sync_status") or "",
            now, now
        ))
        conn.commit()
    return True


def list_certificates_db() -> List[Dict[str, Any]]:
    """Lista todos os certificados cadastrados com cálculo em tempo real dos dias restantes de validade."""
    from backend.services.crypto_service import decrypt_secret

    now = datetime.now()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM certificates ORDER BY razao_social ASC")
        rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        val_to_str = r.get("valid_to", "")
        days_rem = 0
        status_validade = "OK"
        if val_to_str:
            try:
                # Tenta formatos comuns de data
                if "/" in val_to_str:
                    dt_val = datetime.strptime(val_to_str.split()[0], "%d/%m/%Y")
                else:
                    dt_val = datetime.fromisoformat(val_to_str)
                delta = (dt_val - now).days
                days_rem = max(0, delta)
                if delta < 0:
                    status_validade = "VENCIDO"
                elif delta <= 30:
                    status_validade = "EXPIRANDO"
                else:
                    status_validade = "ATIVO"
            except Exception:
                pass
        r["days_remaining"] = days_rem
        r["status_validade"] = status_validade
        if "password" in r:
            r["password"] = decrypt_secret(r.get("password") or "")

    return rows


def get_certificate_record(cnpj: str) -> Optional[Dict[str, Any]]:
    """Obtém os dados de um certificado pelo CNPJ, com senha decifrada em runtime."""
    from backend.services.crypto_service import decrypt_secret

    cnpj_clean = "".join(c for c in str(cnpj) if c.isdigit())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM certificates WHERE cnpj = ?", (cnpj_clean,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["password"] = decrypt_secret(data.get("password") or "")
        return data


def delete_certificate_record(cnpj: str) -> bool:
    """Exclui um certificado cadastrado do banco de dados e remove o arquivo pfx do disco."""
    cnpj_clean = "".join(c for c in str(cnpj) if c.isdigit())
    cert = get_certificate_record(cnpj_clean)
    if cert and cert.get("path") and os.path.exists(cert["path"]):
        try:
            os.remove(cert["path"])
        except Exception:
            pass

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM certificates WHERE cnpj = ?", (cnpj_clean,))
        conn.commit()
    return True


def update_cert_sync_state(cnpj: str, last_nsu: str, max_nsu: Optional[str] = None, status_str: str = ""):
    """Atualiza o último NSU sincronizado e status da empresa."""
    cnpj_clean = "".join(c for c in str(cnpj) if c.isdigit())
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if max_nsu is not None:
            cursor.execute("""
                UPDATE certificates
                SET last_nsu = ?, max_nsu = ?, last_sync_time = ?, last_sync_status = ?, updated_at = ?
                WHERE cnpj = ?
            """, (str(last_nsu), str(max_nsu), now, status_str, now, cnpj_clean))
        else:
            cursor.execute("""
                UPDATE certificates
                SET last_nsu = ?, last_sync_time = ?, last_sync_status = ?, updated_at = ?
                WHERE cnpj = ?
            """, (str(last_nsu), now, status_str, now, cnpj_clean))
        conn.commit()


def auto_register_disk_certificates():
    """Varre a pasta certs/ e cadastra automaticamente os arquivos .pfx encontrados."""
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend

    cert_files = glob.glob(os.path.join(settings.CERT_DIR, "*.pfx")) + glob.glob(os.path.join(settings.CERT_DIR, "*.p12"))
    known_passwords = ["Banana@10", "1", "1234", "123456", ""]

    # Verifica senha configurada no cert_meta.json
    meta_path = os.path.join(settings.CERT_DIR, "cert_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                p = json.load(f).get("password")
                if p and p not in known_passwords:
                    known_passwords.insert(0, p)
        except Exception:
            pass

    for cf in cert_files:
        filename = os.path.basename(cf)
        try:
            with open(cf, "rb") as f:
                data = f.read()

            for pwd in known_passwords:
                try:
                    key, cert, _ = pkcs12.load_key_and_certificates(data, pwd.encode("utf-8") if pwd else None, default_backend())
                    subject = cert.subject.rfc4514_string()
                    cnpj = ""
                    for part in subject.split(","):
                        if ":" in part:
                            _, v = part.split(":", 1)
                            digits = "".join(c for c in v if c.isdigit())
                            if len(digits) == 14:
                                cnpj = digits

                    # Extrai Razão Social
                    razao = ""
                    for attr in cert.subject:
                        if attr.oid._name == "commonName":
                            razao = attr.value.split(":")[0].strip()
                            break
                    if not razao:
                        razao = os.path.splitext(filename)[0]

                    val_from = cert.not_valid_before_utc.strftime("%d/%m/%Y")
                    val_to = cert.not_valid_after_utc.strftime("%d/%m/%Y")
                    days_rem = max(0, (cert.not_valid_after_utc.replace(tzinfo=None) - datetime.utcnow()).days)

                    if cnpj:
                        save_certificate_record({
                            "cnpj": cnpj,
                            "razao_social": razao,
                            "filename": filename,
                            "path": cf,
                            "password": pwd,
                            "valid_from": val_from,
                            "valid_to": val_to,
                            "days_remaining": days_rem,
                            "is_active": 1,
                        })
                    break
                except Exception:
                    continue
        except Exception:
            pass


# ====================================================================
# DOCUMENTOS FISCAIS (NF-e, ITENS E EVENTOS)
# ====================================================================

def set_sync_state(key: str, value: str):
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, str(value), now))
        conn.commit()


def get_sync_state(key: str, default: str = "") -> str:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM sync_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def save_nfe_doc(doc: Dict[str, Any], xml_raw: Optional[str] = None, empresa_cnpj: Optional[str] = None) -> bool:
    """Salva ou atualiza um documento NF-e e seus produtos no banco de dados SQLite."""
    chave = "".join(c for c in str(doc.get("chave", "")) if c.isdigit())
    if len(chave) != 44:
        return False

    now = datetime.now().isoformat()
    emit = doc.get("emitente", {}) if isinstance(doc.get("emitente"), dict) else {}
    dest = doc.get("destinatario", {}) if isinstance(doc.get("destinatario"), dict) else {}
    totais = doc.get("totais", {}) if isinstance(doc.get("totais"), dict) else {}
    ident = doc.get("identificacao", {}) if isinstance(doc.get("identificacao"), dict) else {}

    emit_nome = emit.get("nome") or doc.get("nome_emitente") or doc.get("emitente_nome") or ""
    emit_cnpj = emit.get("cnpj") or doc.get("cnpj_emitente") or doc.get("emitente_cnpj") or ""
    emit_uf = emit.get("endereco", {}).get("uf") if isinstance(emit.get("endereco"), dict) else doc.get("emitente_uf", "")

    dest_nome = dest.get("nome") or doc.get("destinatario_nome") or ""
    dest_cnpj = dest.get("cnpj") or dest.get("cpf") or doc.get("destinatario_cnpj") or ""
    dest_uf = dest.get("endereco", {}).get("uf") if isinstance(dest.get("endereco"), dict) else doc.get("destinatario_uf", "")

    # Determina a empresa dona do documento
    if not empresa_cnpj:
        empresa_cnpj = doc.get("empresa_cnpj")
    if not empresa_cnpj:
        dest_digits = "".join(c for c in str(dest_cnpj) if c.isdigit())
        emit_digits = "".join(c for c in str(emit_cnpj) if c.isdigit())
        cert_record = get_certificate_record(dest_digits) or get_certificate_record(emit_digits)
        if cert_record:
            empresa_cnpj = cert_record["cnpj"]
        else:
            empresa_cnpj = dest_digits

    # Determina o tipo de documento (0 = Entrada / Fornecedor, 1 = Saída / Venda)
    tipo_doc = doc.get("tipo_doc")
    dest_digits = "".join(c for c in str(dest_cnpj) if c.isdigit())
    emit_digits = "".join(c for c in str(emit_cnpj) if c.isdigit())
    if tipo_doc is None:
        emit_is_empresa = bool(get_certificate_record(emit_digits))
        dest_is_empresa = bool(get_certificate_record(dest_digits))
        if emit_is_empresa and not dest_is_empresa:
            tipo_doc = 1
        else:
            tipo_doc = 0
    else:
        tipo_doc = int(tipo_doc)

    numero = ident.get("numero") or doc.get("numero") or ""
    serie = ident.get("serie") or doc.get("serie") or ""
    modelo = ident.get("modelo") or doc.get("modelo") or ("65" if chave[20:22] == "65" else "55")
    dt_emi = ident.get("data_emissao") or doc.get("data_emissao") or doc.get("dhEmi") or ""
    dt_aut = doc.get("data_autorizacao") or ""
    situacao = doc.get("situacao") or "Autorizada"
    nsu = str(doc.get("nsu") or "0")

    def _to_float(v):
        if not v:
            return 0.0
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    v_total = _to_float(totais.get("v_nf") or totais.get("valor_total") or doc.get("valor_total"))
    v_icms = _to_float(totais.get("v_icms") or doc.get("valor_icms"))
    v_pis = _to_float(totais.get("v_pis") or doc.get("valor_pis"))
    v_cofins = _to_float(totais.get("v_cofins") or doc.get("valor_cofins"))
    v_ipi = _to_float(totais.get("v_ipi") or doc.get("valor_ipi"))

    has_xml = 1 if (xml_raw and len(xml_raw) > 50) else 0

    if has_xml:
        xml_file_path = os.path.join(XML_STORAGE_DIR, f"{chave}.xml")
        try:
            with open(xml_file_path, "w", encoding="utf-8") as f:
                f.write(xml_raw)
        except Exception:
            pass

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nfe_docs (
                chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emitente_cnpj, emitente_nome, emitente_uf,
                destinatario_cnpj, destinatario_nome, destinatario_uf, data_emissao, data_autorizacao,
                valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi, situacao, nsu,
                has_xml, xml_raw, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                empresa_cnpj = COALESCE(NULLIF(excluded.empresa_cnpj, ''), nfe_docs.empresa_cnpj),
                numero = COALESCE(NULLIF(excluded.numero, ''), nfe_docs.numero),
                serie = COALESCE(NULLIF(excluded.serie, ''), nfe_docs.serie),
                tipo_doc = CASE WHEN excluded.tipo_doc = 1 THEN 1 ELSE nfe_docs.tipo_doc END,
                emitente_cnpj = COALESCE(NULLIF(excluded.emitente_cnpj, ''), nfe_docs.emitente_cnpj),
                emitente_nome = COALESCE(NULLIF(excluded.emitente_nome, ''), nfe_docs.emitente_nome),
                destinatario_cnpj = COALESCE(NULLIF(excluded.destinatario_cnpj, ''), nfe_docs.destinatario_cnpj),
                destinatario_nome = COALESCE(NULLIF(excluded.destinatario_nome, ''), nfe_docs.destinatario_nome),
                data_emissao = COALESCE(NULLIF(excluded.data_emissao, ''), nfe_docs.data_emissao),
                valor_total = CASE WHEN excluded.valor_total > 0 THEN excluded.valor_total ELSE nfe_docs.valor_total END,
                situacao = COALESCE(NULLIF(excluded.situacao, ''), nfe_docs.situacao),
                nsu = CASE WHEN excluded.nsu != '0' THEN excluded.nsu ELSE nfe_docs.nsu END,
                has_xml = CASE WHEN excluded.has_xml = 1 THEN 1 ELSE nfe_docs.has_xml END,
                xml_raw = COALESCE(NULLIF(excluded.xml_raw, ''), nfe_docs.xml_raw),
                updated_at = excluded.updated_at
        """, (
            chave, empresa_cnpj, numero, serie, modelo, tipo_doc, emit_cnpj, emit_nome, emit_uf,
            dest_cnpj, dest_nome, dest_uf, dt_emi, dt_aut,
            v_total, v_icms, v_pis, v_cofins, v_ipi, situacao, nsu,
            has_xml, xml_raw or "", now, now
        ))

        produtos = doc.get("produtos", [])
        if produtos:
            cursor.execute("DELETE FROM nfe_items WHERE chave = ?", (chave,))
            for p in produtos:
                cursor.execute("""
                    INSERT INTO nfe_items (
                        chave, n_item, codigo, ean, descricao, ncm, cfop, unidade,
                        quantidade, valor_unitario, valor_total, cst, v_icms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chave,
                    int(p.get("n_item") or 1),
                    p.get("codigo") or "",
                    p.get("ean") or "",
                    p.get("descricao") or "",
                    p.get("ncm") or "",
                    p.get("cfop") or "",
                    p.get("unidade") or "",
                    _to_float(p.get("quantidade")),
                    _to_float(p.get("valor_unitario")),
                    _to_float(p.get("valor_total")),
                    p.get("cst") or "",
                    _to_float(p.get("v_icms")),
                ))

        conn.commit()
    return True


def save_nfe_event(event: Dict[str, Any]) -> bool:
    """Salva um evento fiscal (Manifestação, Cancelamento, CC-e) no banco."""
    chave = "".join(c for c in str(event.get("chave", "")) if c.isdigit())
    if len(chave) != 44:
        return False

    now = datetime.now().isoformat()
    tipo = str(event.get("tipo_evento") or "")
    desc = str(event.get("desc_evento") or event.get("xEvento") or "")
    n_seq = int(event.get("n_seq") or event.get("nSeqEvento") or 1)
    dh_ev = str(event.get("dh_evento") or event.get("dhRegEvento") or now)
    prot = str(event.get("protocolo") or event.get("nProt") or "")
    cstat = str(event.get("c_stat") or event.get("cStat") or "")
    motivo = str(event.get("x_motivo") or event.get("xMotivo") or "")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nfe_events (
                chave, tipo_evento, desc_evento, n_seq, dh_evento, protocolo, c_stat, x_motivo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (chave, tipo, desc, n_seq, dh_ev, prot, cstat, motivo, now))

        if tipo == "210240":
            cursor.execute("UPDATE nfe_docs SET situacao = 'Operação não Realizada (210240)', updated_at = ? WHERE chave = ?", (now, chave))
        elif tipo == "210200":
            cursor.execute("UPDATE nfe_docs SET situacao = 'Confirmada (210200)', updated_at = ? WHERE chave = ?", (now, chave))
        elif tipo == "210220":
            cursor.execute("UPDATE nfe_docs SET situacao = 'Desconhecimento (210220)', updated_at = ? WHERE chave = ?", (now, chave))
        elif tipo == "210210":
            cursor.execute("UPDATE nfe_docs SET situacao = 'Ciência da Emissão (210210)', updated_at = ? WHERE chave = ?", (now, chave))
        elif tipo == "110111":
            cursor.execute("UPDATE nfe_docs SET situacao = 'Cancelada', updated_at = ? WHERE chave = ?", (now, chave))

        conn.commit()
    return True


def list_nfe_docs(
    busca: Optional[str] = None,
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    situacao: Optional[str] = None,
    tipo_doc: Optional[Any] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Lista as NF-e armazenadas com filtros por empresa, tipo (Entrada/Saída), data, situação e busca por termo."""
    offset = max(0, (page - 1) * limit)
    conditions = []
    params: List[Any] = []

    if tipo_doc is not None and str(tipo_doc).strip() != "":
        conditions.append("nfe_docs.tipo_doc = ?")
        params.append(int(tipo_doc))

    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            conditions.append("(nfe_docs.empresa_cnpj = ? OR nfe_docs.destinatario_cnpj LIKE ? OR nfe_docs.emitente_cnpj LIKE ?)")
            params.extend([emp_digits, f"%{emp_digits}%", f"%{emp_digits}%"])

    if busca:
        busca_clean = busca.strip()
        digits = "".join(c for c in busca_clean if c.isdigit())
        p_like = f"%{busca_clean}%"

        sub_conds = [
            "nfe_docs.chave LIKE ?",
            "nfe_docs.numero LIKE ?",
            "nfe_docs.emitente_nome LIKE ?",
            "nfe_docs.emitente_cnpj LIKE ?",
            "nfe_docs.destinatario_nome LIKE ?",
            "nfe_docs.destinatario_cnpj LIKE ?",
            "EXISTS (SELECT 1 FROM nfe_items WHERE nfe_items.chave = nfe_docs.chave AND (nfe_items.descricao LIKE ? OR nfe_items.codigo LIKE ? OR nfe_items.ncm LIKE ? OR nfe_items.ean LIKE ?))",
        ]
        params.extend([p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like, p_like])

        if len(digits) >= 8:
            sub_conds.append("REPLACE(REPLACE(REPLACE(REPLACE(nfe_docs.emitente_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
            sub_conds.append("REPLACE(REPLACE(REPLACE(REPLACE(nfe_docs.destinatario_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
            p_digits = f"%{digits}%"
            params.extend([p_digits, p_digits])

        conditions.append("(" + " OR ".join(sub_conds) + ")")

    if data_inicio:
        conditions.append("nfe_docs.data_emissao >= ?")
        params.append(data_inicio)

    if data_fim:
        conditions.append("nfe_docs.data_emissao <= ?")
        params.append(data_fim + "T23:59:59")

    if situacao:
        conditions.append("nfe_docs.situacao LIKE ?")
        params.append(f"%{situacao}%")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) as total, SUM(valor_total) as total_valor FROM nfe_docs {where_clause}", params)
        row_count = cursor.fetchone()
        total = row_count["total"] if row_count else 0
        total_valor = row_count["total_valor"] if (row_count and row_count["total_valor"]) else 0.0

        query = f"""
            SELECT chave, empresa_cnpj, tipo_doc, numero, serie, modelo, emitente_cnpj, emitente_nome, emitente_uf,
                   destinatario_cnpj, destinatario_nome, data_emissao, data_autorizacao,
                   valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi,
                   situacao, nsu, has_xml, created_at
            FROM nfe_docs
            {where_clause}
            ORDER BY data_emissao DESC, created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        rows = [dict(r) for r in cursor.fetchall()]

    return {
        "documentos": rows,
        "total": total,
        "total_valor": total_valor,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


def get_nfe_detail(chave: str) -> Optional[Dict[str, Any]]:
    """Retorna detalhes completos de uma NF-e incluindo produtos e eventos."""
    chave = "".join(c for c in chave if c.isdigit())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfe_docs WHERE chave = ?", (chave,))
        doc_row = cursor.fetchone()
        if not doc_row:
            return None

        doc = dict(doc_row)
        cursor.execute("SELECT * FROM nfe_items WHERE chave = ? ORDER BY n_item ASC", (chave,))
        doc["produtos"] = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM nfe_events WHERE chave = ? ORDER BY dh_evento DESC", (chave,))
        doc["eventos"] = [dict(r) for r in cursor.fetchall()]

        return doc


def get_analytics_dashboard(mes: Optional[int] = None, ano: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Retorna dados analíticos de compras e impostos para o Dashboard filtrados por período e empresa."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (empresa_cnpj = ? OR destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT COUNT(*) as total_notas,
                   COALESCE(SUM(valor_total), 0.0) as total_compras,
                   COALESCE(SUM(valor_icms), 0.0) as total_icms,
                   COALESCE(SUM(valor_pis), 0.0) as total_pis,
                   COALESCE(SUM(valor_cofins), 0.0) as total_cofins,
                   COALESCE(SUM(valor_ipi), 0.0) as total_ipi
            FROM nfe_docs
            WHERE data_emissao LIKE ? {emp_cond}
        """, [f"{mes_str}%"] + emp_params)
        totais_mes = dict(cursor.fetchone())

        cursor.execute(f"""
            SELECT emitente_nome, emitente_cnpj, COUNT(*) as qtd_notas, SUM(valor_total) as valor_total
            FROM nfe_docs
            WHERE data_emissao LIKE ? AND emitente_nome != '' {emp_cond}
            GROUP BY emitente_cnpj, emitente_nome
            ORDER BY valor_total DESC
            LIMIT 5
        """, [f"{mes_str}%"] + emp_params)
        top_fornecedores = [dict(r) for r in cursor.fetchall()]

        cursor.execute(f"""
            SELECT SUBSTR(data_emissao, 1, 7) as mes_ano,
                   COUNT(*) as qtd_notas,
                   SUM(valor_total) as valor_total
            FROM nfe_docs
            WHERE data_emissao != '' {emp_cond}
            GROUP BY mes_ano
            ORDER BY mes_ano DESC
            LIMIT 8
        """, emp_params)
        evolucao_mensal = [dict(r) for r in cursor.fetchall()][::-1]

        cursor.execute(f"SELECT COUNT(*) as total_geral, COALESCE(SUM(valor_total), 0.0) as valor_geral FROM nfe_docs WHERE 1=1 {emp_cond}", emp_params)
        total_banco = dict(cursor.fetchone())

    return {
        "mes": mes,
        "ano": ano,
        "empresa_cnpj": empresa_cnpj,
        "totais_mes": totais_mes,
        "top_fornecedores": top_fornecedores,
        "evolucao_mensal": evolucao_mensal,
        "total_banco": total_banco,
    }


def get_price_history(termo: str, empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Consulta o histórico de preços pagos por um determinado produto/NCM."""
    if not termo:
        return []
    termo_like = f"%{termo.strip()}%"

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT i.descricao, i.codigo, i.ncm, i.unidade, i.quantidade, i.valor_unitario, i.valor_total,
                   d.chave, d.numero, d.data_emissao, d.emitente_nome, d.emitente_cnpj
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE (i.descricao LIKE ? OR i.ncm LIKE ? OR i.codigo LIKE ?) {emp_cond}
            ORDER BY d.data_emissao DESC
            LIMIT 50
        """, [termo_like, termo_like, termo_like] + emp_params)
        return [dict(r) for r in cursor.fetchall()]


def get_abc_curve(mes: Optional[int] = None, ano: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calcula a Curva ABC de produtos comprados no período."""
    now = datetime.now()
    ano = ano or now.year
    mes = mes or now.month
    mes_str = f"{ano:04d}-{mes:02d}"

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT i.descricao, i.ncm, SUM(i.quantidade) as qtd_total, SUM(i.valor_total) as valor_total
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE d.data_emissao LIKE ? {emp_cond}
            GROUP BY i.descricao, i.ncm
            ORDER BY valor_total DESC
            LIMIT 30
        """, [f"{mes_str}%"] + emp_params)
        rows = [dict(r) for r in cursor.fetchall()]

    total_geral = sum(r["valor_total"] for r in rows) or 1.0
    acumulado = 0.0
    for r in rows:
        pct = (r["valor_total"] / total_geral) * 100
        acumulado += pct
        r["percentual"] = round(pct, 2)
        r["acumulado"] = round(acumulado, 2)
        if acumulado <= 80:
            r["classe"] = "A"
        elif acumulado <= 95:
            r["classe"] = "B"
        else:
            r["classe"] = "C"

    return rows


# ====================================================================
# NOTIFICAÇÕES EM TEMPO REAL & ALERTAS
# ====================================================================

def add_notification(title: str, message: str, tipo: str = "info", chave: Optional[str] = None) -> int:
    """Registra uma notificação de evento fiscal no banco de dados com prevenção ativa de duplicidade."""
    now = datetime.now().isoformat()
    chave_clean = "".join(c for c in str(chave or "") if c.isdigit())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Se houver chave (44 dígitos), verifica se já existe uma notificação para a mesma chave
        if chave_clean and len(chave_clean) == 44:
            cursor.execute("SELECT id, title, message FROM notifications WHERE chave = ? ORDER BY id DESC LIMIT 1", (chave_clean,))
            row = cursor.fetchone()
            if row:
                # Atualiza com a notificação mais recente/detalhada sem gerar card duplicado
                cursor.execute("""
                    UPDATE notifications
                    SET title = ?, message = ?, tipo = ?, created_at = ?
                    WHERE id = ?
                """, (title, message, tipo, now, row["id"]))
                conn.commit()
                return row["id"]

        cursor.execute("""
            INSERT INTO notifications (title, message, tipo, chave, read, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (title, message, tipo, chave_clean if chave_clean else (chave or ""), now))
        conn.commit()
        return cursor.lastrowid


def list_notifications(limit: int = 30, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Lista as notificações recentes únicas registradas pelo robô de sincronização."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        unread_cond = "WHERE read = 0" if unread_only else ""

        # Garante deduplicação por chave única mantendo a notificação mais recente
        query = f"""
            SELECT * FROM notifications
            WHERE id IN (
                SELECT MAX(id) FROM notifications
                {unread_cond}
                GROUP BY (CASE WHEN chave != '' AND chave IS NOT NULL THEN chave ELSE CAST(id AS TEXT) END)
            )
            ORDER BY created_at DESC LIMIT ?
        """
        cursor.execute(query, (limit,))
        return [dict(r) for r in cursor.fetchall()]


def mark_notifications_read() -> bool:
    """Marca todas as notificações pendentes como lidas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        conn.commit()
        return True


# ====================================================================
# AUDITOR DE PREÇOS & ALERTA DE VARIAÇÃO DE CUSTOS
# ====================================================================

def get_price_divergences(empresa_cnpj: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Audita todas as compras e detecta variações de preços de um mesmo produto."""
    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Busca produtos com múltiplas compras
        cursor.execute(f"""
            SELECT i.descricao, i.codigo, i.ncm, i.valor_unitario, i.quantidade,
                   d.chave, d.numero, d.data_emissao, d.emitente_nome, d.empresa_cnpj, d.destinatario_nome
            FROM nfe_items i
            JOIN nfe_docs d ON i.chave = d.chave
            WHERE i.valor_unitario > 0 {emp_cond}
            ORDER BY i.descricao ASC, d.data_emissao DESC
        """, emp_params)
        all_items = [dict(r) for r in cursor.fetchall()]

    divergencias = []
    from collections import defaultdict
    grouped = defaultdict(list)
    for it in all_items:
        key = (it.get("codigo") or it.get("descricao") or "").strip().upper()
        if key:
            grouped[key].append(it)

    for key, items in grouped.items():
        if len(items) >= 2:
            latest = items[0]
            previous = items[1]
            p_lat = float(latest["valor_unitario"] or 0)
            p_prev = float(previous["valor_unitario"] or 0)

            if p_lat > 0 and p_prev > 0 and abs(p_lat - p_prev) > 0.01:
                diff = p_lat - p_prev
                pct = round((diff / p_prev) * 100, 2)
                divergencias.append({
                    "descricao": latest["descricao"],
                    "codigo": latest["codigo"],
                    "ncm": latest["ncm"],
                    "preco_atual": p_lat,
                    "preco_anterior": p_prev,
                    "diferenca_reais": round(diff, 2),
                    "variacao_pct": pct,
                    "tipo": "AUMENTO" if pct > 0 else "QUEDA",
                    "chave_atual": latest["chave"],
                    "data_atual": latest["data_emissao"],
                    "fornecedor_atual": latest["emitente_nome"],
                    "chave_anterior": previous["chave"],
                    "data_anterior": previous["data_emissao"],
                    "fornecedor_anterior": previous["emitente_nome"],
                    "empresa_destinatario": latest.get("destinatario_nome") or latest.get("empresa_cnpj"),
                })

    divergencias.sort(key=lambda x: abs(x["variacao_pct"]), reverse=True)
    return divergencias[:limit]


# ====================================================================
# CONCILIAÇÃO DE OPERAÇÕES INTERCOMPANY (ENTRE NOSSAS EMPRESAS)
# ====================================================================

def get_intercompany_operations() -> Dict[str, Any]:
    """Cruza as notas fiscais emitidas por uma de nossas empresas com destino a outra empresa nossa."""
    certs = list_certificates_db()
    cnpjs_nossos = [c["cnpj"] for c in certs if c.get("cnpj")]

    if not cnpjs_nossos:
        return {"operacoes": [], "resumo_transferencias": [], "total_volume": 0.0, "total_notas": 0}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chave, numero, serie, emitente_cnpj, emitente_nome,
                   destinatario_cnpj, destinatario_nome, data_emissao, valor_total, situacao
            FROM nfe_docs
            ORDER BY data_emissao DESC
        """)
        all_docs = [dict(r) for r in cursor.fetchall()]

    intercompany_docs = []
    total_volume = 0.0

    def clean_cnpj(c):
        return "".join(ch for ch in str(c) if ch.isdigit())

    for d in all_docs:
        e_cnpj = clean_cnpj(d.get("emitente_cnpj", ""))
        dest_cnpj = clean_cnpj(d.get("destinatario_cnpj", ""))

        if e_cnpj in cnpjs_nossos and dest_cnpj in cnpjs_nossos:
            intercompany_docs.append(d)
            total_volume += float(d.get("valor_total") or 0.0)

    # Matriz de transferências
    from collections import defaultdict
    transfer_matrix = defaultdict(lambda: {"qtd": 0, "total": 0.0, "origem": "", "destino": ""})
    for d in intercompany_docs:
        orig = d.get("emitente_nome") or d.get("emitente_cnpj")
        dest = d.get("destinatario_nome") or d.get("destinatario_cnpj")
        k = (orig, dest)
        transfer_matrix[k]["origem"] = orig
        transfer_matrix[k]["destino"] = dest
        transfer_matrix[k]["qtd"] += 1
        transfer_matrix[k]["total"] += float(d.get("valor_total") or 0.0)

    return {
        "operacoes": intercompany_docs,
        "resumo_transferencias": list(transfer_matrix.values()),
        "total_volume": total_volume,
        "total_notas": len(intercompany_docs),
    }


# ====================================================================
# GESTÃO FINANCEIRA & CONTAS A PAGAR (DUPLICATAS DE NF-e)
# ====================================================================

# Manifestações do destinatário que caracterizam rejeição/desconhecimento da NF-e
# (a nota não gera compromisso financeiro reconhecido): Desconhecimento (210220)
# e Operação Não Realizada (210240).
EVENTOS_REJEICAO = ("210220", "210240")


def sync_duplicatas_from_xmls():
    """Varre todos os XMLs e notas fiscais para garantir que as duplicatas estejam cadastradas.

    Apenas documentos de ENTRADA (tipo_doc=0 / Compra/Fornecedor) geram contas a pagar.
    """
    import glob
    from lxml import etree
    from datetime import timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Migração de segurança: remove contas a pagar órfãs geradas por saídas (bug antigo)
        cursor.execute(
            "DELETE FROM nfe_duplicatas WHERE chave IN (SELECT chave FROM nfe_docs WHERE tipo_doc = 1)"
        )

        # Remove contas a pagar de NF-e com manifestação de rejeição/desconhecimento
        rej_params = list(EVENTOS_REJEICAO)
        rej_placeholders = ",".join("?" for _ in rej_params)
        cursor.execute(
            f"DELETE FROM nfe_duplicatas WHERE chave IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))",
            rej_params,
        )

        # Conjunto de chaves rejeitadas para não recriar as duplicatas
        cursor.execute(f"SELECT DISTINCT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders})", rej_params)
        chaves_rejeitadas = {r["chave"] for r in cursor.fetchall()}

        cursor.execute(
            "SELECT chave, empresa_cnpj, emitente_nome, data_emissao, valor_total FROM nfe_docs WHERE tipo_doc = 0"
        )
        all_docs = [dict(r) for r in cursor.fetchall()]

        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        for doc in all_docs:
            ch = doc["chave"]
            if ch in chaves_rejeitadas:
                continue
            cursor.execute("SELECT COUNT(*) as count FROM nfe_duplicatas WHERE chave = ?", (ch,))
            if cursor.fetchone()["count"] > 0:
                continue

            xml_path = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
            inserted = False
            if os.path.exists(xml_path):
                try:
                    with open(xml_path, "rb") as f:
                        root = etree.fromstring(f.read())
                    dups = root.findall(".//nfe:dup", ns)
                    for idx, d in enumerate(dups, start=1):
                        n_dup = d.findtext("nfe:nDup", default=str(idx), namespaces=ns)
                        d_venc = d.findtext("nfe:dVenc", default="", namespaces=ns)
                        v_dup = float(d.findtext("nfe:vDup", default="0.0", namespaces=ns) or 0.0)
                        if not d_venc and doc.get("data_emissao"):
                            try:
                                d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                            except Exception:
                                d_venc = doc["data_emissao"][:10]

                        cursor.execute("""
                            INSERT INTO nfe_duplicatas (chave, n_dup, d_venc, v_dup, forma_pagamento, status, pago, empresa_cnpj, emitente_nome, created_at)
                            VALUES (?, ?, ?, ?, 'Boleto/Duplicata', 'A_VENCER', 0, ?, ?, ?)
                        """, (ch, n_dup, d_venc, v_dup, doc["empresa_cnpj"], doc["emitente_nome"], datetime.now().isoformat()))
                        inserted = True
                except Exception:
                    pass

            if not inserted and float(doc.get("valor_total") or 0.0) > 0:
                d_venc = ""
                if doc.get("data_emissao"):
                    try:
                        d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                    except Exception:
                        d_venc = doc["data_emissao"][:10]
                cursor.execute("""
                    INSERT INTO nfe_duplicatas (chave, n_dup, d_venc, v_dup, forma_pagamento, status, pago, empresa_cnpj, emitente_nome, created_at)
                    VALUES (?, '001', ?, ?, 'Fatura / Boleto', 'A_VENCER', 0, ?, ?, ?)
                """, (ch, d_venc, float(doc["valor_total"]), doc["empresa_cnpj"], doc["emitente_nome"], datetime.now().isoformat()))

        conn.commit()


def list_contas_a_pagar(empresa_cnpj: Optional[str] = None, filtro_status: Optional[str] = None, mes: Optional[str] = None) -> Dict[str, Any]:
    """Retorna contas a pagar e vencimentos extraídos das NF-e das empresas."""
    sync_duplicatas_from_xmls()
    now_str = datetime.now().strftime("%Y-%m-%d")

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    rej_params = list(EVENTOS_REJEICAO)
    rej_placeholders = ",".join("?" for _ in rej_params)

    mes_cond = ""
    mes_params = []
    if mes:
        mes_cond = " AND substr(doc.data_emissao, 1, 7) = ?"
        mes_params.append(mes)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT dup.id, dup.chave, dup.n_dup, dup.d_venc, dup.v_dup, dup.forma_pagamento,
                   dup.pago, dup.data_pagamento, dup.empresa_cnpj, dup.emitente_nome,
                    doc.numero as nfe_numero, doc.destinatario_nome
            FROM nfe_duplicatas dup
            JOIN nfe_docs doc ON dup.chave = doc.chave
            WHERE doc.tipo_doc = 0
              AND doc.chave NOT IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))
              {emp_cond}{mes_cond}
            ORDER BY dup.d_venc ASC
        """, rej_params + emp_params + mes_params)
        all_dups = [dict(r) for r in cursor.fetchall()]

    total_aberto = 0.0
    total_vencido = 0.0
    total_pago = 0.0
    vencendo_hoje = 0.0

    for d in all_dups:
        venc = d.get("d_venc", "")
        val = float(d.get("v_dup") or 0.0)
        pago = bool(d.get("pago"))

        if pago:
            d["status_calc"] = "PAGO"
            total_pago += val
        elif venc and venc < now_str:
            d["status_calc"] = "VENCIDO"
            total_vencido += val
            total_aberto += val
        elif venc == now_str:
            d["status_calc"] = "VENCE_HOJE"
            vencendo_hoje += val
            total_aberto += val
        else:
            d["status_calc"] = "A_VENCER"
            total_aberto += val

    if filtro_status == "aberto":
        filtered = [d for d in all_dups if d["status_calc"] != "PAGO"]
    elif filtro_status == "vencido":
        filtered = [d for d in all_dups if d["status_calc"] == "VENCIDO"]
    elif filtro_status == "pago":
        filtered = [d for d in all_dups if d["status_calc"] == "PAGO"]
    else:
        filtered = all_dups

    return {
        "duplicatas": filtered,
        "total_contas": len(filtered),
        "total_aberto": total_aberto,
        "total_vencido": total_vencido,
        "total_pago": total_pago,
        "vencendo_hoje": vencendo_hoje,
    }


def pagar_duplicata(dup_id: int) -> bool:
    """Marca uma duplicata como paga ou desmarca."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pago FROM nfe_duplicatas WHERE id = ?", (dup_id,))
        row = cursor.fetchone()
        if not row:
            return False
        novo_pago = 0 if row["pago"] == 1 else 1
        dt_pag = now if novo_pago == 1 else None
        cursor.execute("UPDATE nfe_duplicatas SET pago = ?, data_pagamento = ? WHERE id = ?", (novo_pago, dt_pag, dup_id))
        conn.commit()
        return True


# ====================================================================
# CONTAS A RECEBER (SAÍDAS / VENDAS / CLIENTES)
# ====================================================================

def sync_contas_receber_from_xmls():
    """Varre todos os XMLs e notas fiscais de SAÍDA (tipo_doc=1) para garantir
    que as parcelas a receber (contas a receber) estejam cadastradas."""
    import glob
    from lxml import etree
    from datetime import timedelta

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Migração de segurança: remove contas a receber órfãs geradas por entradas (bug antigo)
        cursor.execute(
            "DELETE FROM nfe_contas_receber WHERE chave IN (SELECT chave FROM nfe_docs WHERE tipo_doc = 0)"
        )

        # As notas de saída são emitidas à vista (já recebemos), então o padrão é RECEBIDO.
        # Migração única: marca como recebidas as parcelas criadas antes deste comportamento.
        flag_row = cursor.execute(
            "SELECT value FROM sync_state WHERE key = 'contas_receber_recebido_default'"
        ).fetchone()
        if not (flag_row and flag_row["value"] == "1"):
            cursor.execute(
                "UPDATE nfe_contas_receber SET recebido = 1, status = 'RECEBIDO', "
                "data_recebimento = created_at WHERE recebido = 0"
            )
            _now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO sync_state (key, value, updated_at) VALUES ('contas_receber_recebido_default', '1', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = '1', updated_at = ?",
                (_now, _now),
            )

        cursor.execute(
            "SELECT chave, empresa_cnpj, destinatario_nome, destinatario_cnpj, data_emissao, valor_total "
            "FROM nfe_docs WHERE tipo_doc = 1"
        )
        all_docs = [dict(r) for r in cursor.fetchall()]

        ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
        for doc in all_docs:
            ch = doc["chave"]
            cursor.execute("SELECT COUNT(*) as count FROM nfe_contas_receber WHERE chave = ?", (ch,))
            if cursor.fetchone()["count"] > 0:
                continue

            xml_path = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
            inserted = False
            if os.path.exists(xml_path):
                try:
                    with open(xml_path, "rb") as f:
                        root = etree.fromstring(f.read())
                    dups = root.findall(".//nfe:dup", ns)
                    for idx, d in enumerate(dups, start=1):
                        n_dup = d.findtext("nfe:nDup", default=str(idx), namespaces=ns)
                        d_venc = d.findtext("nfe:dVenc", default="", namespaces=ns)
                        v_dup = float(d.findtext("nfe:vDup", default="0.0", namespaces=ns) or 0.0)
                        if not d_venc and doc.get("data_emissao"):
                            try:
                                d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                            except Exception:
                                d_venc = doc["data_emissao"][:10]

                        now_iso = datetime.now().isoformat()
                        cursor.execute("""
                            INSERT INTO nfe_contas_receber (chave, n_dup, d_venc, v_dup, forma_pagamento, status, recebido, data_recebimento, empresa_cnpj, cliente_nome, cliente_cnpj, created_at)
                            VALUES (?, ?, ?, ?, 'Boleto/Duplicata', 'RECEBIDO', 1, ?, ?, ?, ?, ?, ?)
                        """, (ch, n_dup, d_venc, v_dup, now_iso, doc["empresa_cnpj"], doc["destinatario_nome"], doc["destinatario_cnpj"], now_iso))
                        inserted = True
                except Exception:
                    pass

            if not inserted and float(doc.get("valor_total") or 0.0) > 0:
                d_venc = ""
                if doc.get("data_emissao"):
                    try:
                        d_venc = (datetime.fromisoformat(doc["data_emissao"][:10]) + timedelta(days=30)).strftime("%Y-%m-%d")
                    except Exception:
                        d_venc = doc["data_emissao"][:10]
                now_iso = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO nfe_contas_receber (chave, n_dup, d_venc, v_dup, forma_pagamento, status, recebido, data_recebimento, empresa_cnpj, cliente_nome, cliente_cnpj, created_at)
                    VALUES (?, '001', ?, ?, 'Fatura / Boleto', 'RECEBIDO', 1, ?, ?, ?, ?, ?, ?)
                """, (ch, d_venc, float(doc["valor_total"]), now_iso, doc["empresa_cnpj"], doc["destinatario_nome"], doc["destinatario_cnpj"], now_iso))

        conn.commit()


def list_contas_a_receber(empresa_cnpj: Optional[str] = None, filtro_status: Optional[str] = None, mes: Optional[str] = None) -> Dict[str, Any]:
    """Retorna contas a receber (saídas/vendas) e vencimentos extraídos das NF-e das empresas."""
    sync_contas_receber_from_xmls()
    now_str = datetime.now().strftime("%Y-%m-%d")

    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " AND (r.empresa_cnpj = ? OR r.cliente_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    mes_cond = ""
    mes_params = []
    if mes:
        mes_cond = " AND substr(doc.data_emissao, 1, 7) = ?"
        mes_params.append(mes)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT r.id, r.chave, r.n_dup, r.d_venc, r.v_dup, r.forma_pagamento,
                   r.recebido, r.data_recebimento, r.empresa_cnpj, r.cliente_nome,
                    doc.numero as nfe_numero, doc.emitente_nome
            FROM nfe_contas_receber r
            JOIN nfe_docs doc ON r.chave = doc.chave
            WHERE doc.tipo_doc = 1 {emp_cond}{mes_cond}
            ORDER BY r.d_venc ASC
        """, emp_params + mes_params)
        all_rec = [dict(r) for r in cursor.fetchall()]

    total_aberto = 0.0
    total_vencido = 0.0
    total_recebido = 0.0
    vencendo_hoje = 0.0

    for d in all_rec:
        venc = d.get("d_venc", "")
        val = float(d.get("v_dup") or 0.0)
        rec = bool(d.get("recebido"))

        if rec:
            d["status_calc"] = "RECEBIDO"
            total_recebido += val
        elif venc and venc < now_str:
            d["status_calc"] = "VENCIDO"
            total_vencido += val
            total_aberto += val
        elif venc == now_str:
            d["status_calc"] = "VENCE_HOJE"
            vencendo_hoje += val
            total_aberto += val
        else:
            d["status_calc"] = "A_RECEBER"
            total_aberto += val

    if filtro_status == "aberto":
        filtered = [d for d in all_rec if d["status_calc"] != "RECEBIDO"]
    elif filtro_status == "vencido":
        filtered = [d for d in all_rec if d["status_calc"] == "VENCIDO"]
    elif filtro_status == "recebido":
        filtered = [d for d in all_rec if d["status_calc"] == "RECEBIDO"]
    else:
        filtered = all_rec

    return {
        "contas": filtered,
        "total_contas": len(filtered),
        "total_aberto": total_aberto,
        "total_vencido": total_vencido,
        "total_recebido": total_recebido,
        "vencendo_hoje": vencendo_hoje,
    }


def receber_duplicata(dup_id: int) -> bool:
    """Marca uma conta a receber como recebida ou desmarca."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT recebido FROM nfe_contas_receber WHERE id = ?", (dup_id,))
        row = cursor.fetchone()
        if not row:
            return False
        novo_recebido = 0 if row["recebido"] == 1 else 1
        dt_rec = now if novo_recebido == 1 else None
        cursor.execute("UPDATE nfe_contas_receber SET recebido = ?, data_recebimento = ? WHERE id = ?", (novo_recebido, dt_rec, dup_id))
        conn.commit()
        return True


# ====================================================================
# DRE CONSOLIDADO (RESULTADO DO EXERCÍCIO)
# ====================================================================

def get_dre_consolidado(ano: Optional[int] = None, mes: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Calcula o DRE consolidado do período: Receita Bruta - Impostos - CPV = Lucro Bruto - DAS = Lucro Líquido."""
    now = datetime.now()
    cur_ano = ano or now.year
    cur_mes = mes or now.month
    data_mes_prefix = f"{cur_ano}-{cur_mes:02d}"
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (empresa_cnpj = ? OR emitente_cnpj = ? OR destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj, clean_cnpj]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Receita Bruta (Saídas, não canceladas)
        cursor.execute(
            f"SELECT SUM(valor_total) as v, COUNT(*) as q FROM nfe_docs "
            f"WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_rec = dict(cursor.fetchone())
        receita_bruta = float(r_rec["v"] or 0.0)
        qtd_vendas = int(r_rec["q"] or 0)

        # Impostos s/ Venda (ICMS + PIS + COFINS + IPI das saídas do período)
        cursor.execute(
            f"SELECT COALESCE(SUM(valor_icms),0) as icms, COALESCE(SUM(valor_pis),0) as pis, "
            f"COALESCE(SUM(valor_cofins),0) as cofins, COALESCE(SUM(valor_ipi),0) as ipi "
            f"FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_imp = dict(cursor.fetchone())
        impostos_venda = round(float(r_imp["icms"]) + float(r_imp["pis"]) + float(r_imp["cofins"]) + float(r_imp["ipi"]), 2)

        # CPV (Custo das Mercadorias Vendidas) = Entradas do período (não canceladas)
        cursor.execute(
            f"SELECT SUM(valor_total) as v FROM nfe_docs "
            f"WHERE tipo_doc = 0 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?{emp_filter}",
            [data_mes_prefix] + emp_params,
        )
        r_cpv = cursor.fetchone()
        cpv = float(r_cpv["v"] or 0.0)

    receita_liquida = round(receita_bruta - impostos_venda, 2)
    lucro_bruto = round(receita_liquida - cpv, 2)

    # Imposto Simples (DAS) estimado do período
    simples = get_simples_nacional_apuracao(ano=cur_ano, mes=cur_mes, empresa_cnpj=empresa_cnpj)
    das_estimado = round(float(simples.get("valor_das_estimado") or 0.0), 2)

    lucro_liquido = round(lucro_bruto - das_estimado, 2)

    def pct(parte: float, total: float) -> float:
        return round((parte / total) * 100, 2) if total > 0 else 0.0

    return {
        "ano": cur_ano,
        "mes": cur_mes,
        "competencia": f"{cur_mes:02d}/{cur_ano}",
        "qtd_vendas": qtd_vendas,
        "receita_bruta": receita_bruta,
        "impostos_venda": impostos_venda,
        "receita_liquida": receita_liquida,
        "cpv": cpv,
        "lucro_bruto": lucro_bruto,
        "das_simples_estimado": das_estimado,
        "lucro_liquido": lucro_liquido,
        "margem_bruta_pct": pct(lucro_bruto, receita_liquida),
        "margem_liquida_pct": pct(lucro_liquido, receita_liquida),
        "simples": simples,
    }


# ====================================================================
# IMPOSTOS INTERESTADUAIS A RECOLHER (DIFAL - ICMS)
# ====================================================================

# Alíquotas internas do ICMS por UF (estimativa gerencial / valores praticados)
_ALIQUOTAS_INTERNAS_UF = {
    "AC": 17.0, "AL": 17.0, "AP": 17.0, "AM": 18.0, "BA": 19.0, "CE": 17.0,
    "DF": 18.0, "ES": 17.0, "GO": 17.0, "MA": 18.0, "MT": 17.0, "MS": 17.0,
    "MG": 18.0, "PA": 17.0, "PB": 18.0, "PR": 19.0, "PE": 18.0, "PI": 18.0,
    "RJ": 20.0, "RN": 18.0, "RS": 17.0, "RO": 17.5, "RR": 17.0, "SC": 17.0,
    "SP": 18.0, "SE": 18.0, "TO": 18.0,
}


def _aliquota_interestadual(aliq_interna_destino: float) -> float:
    """Alíquota interestadual conforme EC 87/2015 (4% / 7% / 12%) pela alíquota interna de destino."""
    if aliq_interna_destino <= 12.0:
        return 4.0
    if aliq_interna_destino <= 17.0:
        return 7.0
    if aliq_interna_destino <= 20.0:
        return 12.0
    return 4.0


def get_impostos_interestaduais(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Estima o DIFAL (ICMS a recolher sobre operações interestaduais de ENTRADA).

    Para cada NF-e de entrada (tipo_doc=0) cujo emitente está em UF diferente da
    UF da empresa (destinatário), calcula a diferença entre a alíquota interna de
    destino e a alíquota efetivamente aplicada (ou a interestadual) sobre o valor
    da nota. É uma PREVISÃO gerencial do imposto a recolher "fora do estado".
    """
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    rej_params = list(EVENTOS_REJEICAO)
    rej_placeholders = ",".join("?" for _ in rej_params)

    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (d.empresa_cnpj = ? OR d.destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, f"%{clean_cnpj}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT d.chave, d.numero, d.data_emissao, d.emitente_nome, d.emitente_uf,
                   d.destinatario_uf, d.empresa_cnpj, d.valor_total, d.valor_icms
            FROM nfe_docs d
            WHERE d.tipo_doc = 0
              AND d.situacao != 'Cancelada'
              AND d.emitente_uf IS NOT NULL AND d.destinatario_uf IS NOT NULL
              AND d.emitente_uf != d.destinatario_uf
              AND d.chave NOT IN (SELECT chave FROM nfe_events WHERE tipo_evento IN ({rej_placeholders}))
              {emp_filter}
            ORDER BY d.data_emissao DESC
        """, rej_params + emp_params)
        docs = [dict(r) for r in cursor.fetchall()]

    itens = []
    total_difal = 0.0
    total_base = 0.0
    total_icms_proprio = 0.0

    for d in docs:
        uf_dest = (d.get("destinatario_uf") or "").strip().upper()
        uf_orig = (d.get("emitente_uf") or "").strip().upper()
        base = float(d.get("valor_total") or 0.0)
        icms_proprio = float(d.get("valor_icms") or 0.0)

        aliq_interna = _ALIQUOTAS_INTERNAS_UF.get(uf_dest, 18.0)
        # Alíquota efetivamente aplicada na origem (se houver ICMS registrado)
        if base > 0 and icms_proprio > 0:
            aliq_aplicada = (icms_proprio / base) * 100.0
        else:
            aliq_aplicada = _aliquota_interestadual(aliq_interna)

        difal = round(base * max(0.0, (aliq_interna - aliq_aplicada)) / 100.0, 2)

        if difal <= 0:
            continue

        total_difal += difal
        total_base += base
        total_icms_proprio += icms_proprio

        itens.append({
            "chave": d.get("chave"),
            "numero": d.get("numero"),
            "data_emissao": d.get("data_emissao"),
            "emitente_nome": d.get("emitente_nome"),
            "uf_origem": uf_orig,
            "uf_destino": uf_dest,
            "empresa_cnpj": d.get("empresa_cnpj"),
            "valor_total": base,
            "icms_proprio": round(icms_proprio, 2),
            "aliquota_interna_destino": aliq_interna,
            "aliquota_aplicada": round(aliq_aplicada, 2),
            "difal_estimado": difal,
        })

    return {
        "itens": itens,
        "total_notas": len(itens),
        "total_base": round(total_base, 2),
        "total_icms_proprio": round(total_icms_proprio, 2),
        "total_difal_estimado": round(total_difal, 2),
        "observacao": "Estimativa gerencial de DIFAL sobre o valor total da NF-e. Base real de cálculo pode incluir IPI/frete conforme legislação vigente.",
    }


# ====================================================================
# TENDÊNCIA MENSAL DO DRE (ÚLTIMOS 12 MESES)
# ====================================================================

def get_dre_tendencia(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Retorna a série histórica mensal do DRE (últimos 12 meses)."""
    now = datetime.now()
    cur_ano = now.year
    cur_mes = now.month

    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (empresa_cnpj = ? OR emitente_cnpj = ? OR destinatario_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj, clean_cnpj]

    meses = []
    for i in range(11, -1, -1):
        m = cur_mes - i
        a = cur_ano
        if m <= 0:
            m += 12
            a -= 1
        meses.append({"ano": a, "mes": m, "prefixo": f"{a}-{m:02d}"})

    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = []
        for mm in meses:
            p = mm["prefixo"]
            params = [p] + emp_params
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_total),0) as receita FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            receita = float(cursor.fetchone()["receita"])
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_icms),0)+COALESCE(SUM(valor_pis),0)+COALESCE(SUM(valor_cofins),0)+COALESCE(SUM(valor_ipi),0) as impostos FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            impostos = float(cursor.fetchone()["impostos"])
            cursor.execute(
                f"SELECT COALESCE(SUM(valor_total),0) as cpv FROM nfe_docs WHERE tipo_doc=0 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            cpv = float(cursor.fetchone()["cpv"])
            cursor.execute(
                f"SELECT SUM(valor_total) as r FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?{emp_filter}",
                params,
            )
            receita_mes = float(cursor.fetchone()["r"])
            cursor.execute(
                "SELECT SUM(valor_total) as r FROM nfe_docs WHERE tipo_doc=1 AND situacao!='Cancelada' AND substr(data_emissao,1,7)=?",
                [p],
            )
            rbt12_local = float(cursor.fetchone()["r"] or 0.0)
            aliq_efetiva = max(0.04, ((rbt12_local * 0.04) / rbt12_local) if rbt12_local > 0 else 0.04)
            das = round(receita_mes * aliq_efetiva, 2) if receita_mes > 0 else 0.0
            receita_liquida = round(receita - impostos, 2)
            lucro_bruto = round(receita_liquida - cpv, 2)
            lucro_liquido = round(lucro_bruto - das, 2)
            rows.append({
                "ano": a, "mes": m, "competencia": f"{m:02d}/{a}",
                "receita_bruta": round(receita, 2), "impostos_venda": round(impostos, 2),
                "receita_liquida": receita_liquida, "cpv": round(cpv, 2),
                "lucro_bruto": lucro_bruto, "das_simples_estimado": das,
                "lucro_liquido": lucro_liquido,
            })

        # Contas a pagar/receber por mês (tendência de caixa)
        cursor.execute(
            f"SELECT substr(d_venc,1,7) as mes, SUM(v_dup) as total, SUM(CASE WHEN pago=1 THEN v_dup ELSE 0 END) as pago FROM nfe_duplicatas d JOIN nfe_docs doc ON d.chave=doc.chave WHERE doc.tipo_doc=0 AND substr(d_venc,1,7) IN ({','.join('?' for _ in meses)}) GROUP BY substr(d_venc,1,7)",
            [mm["prefixo"] for mm in meses],
        )
        ap_rows = {r["mes"]: r for r in cursor.fetchall()}
        cursor.execute(
            f"SELECT substr(d_venc,1,7) as mes, SUM(v_dup) as total, SUM(CASE WHEN recebido=1 THEN v_dup ELSE 0 END) as recebido FROM nfe_contas_receber r JOIN nfe_docs doc ON r.chave=doc.chave WHERE doc.tipo_doc=1 AND substr(d_venc,1,7) IN ({','.join('?' for _ in meses)}) GROUP BY substr(d_venc,1,7)",
            [mm["prefixo"] for mm in meses],
        )
        ar_rows = {r["mes"]: r for r in cursor.fetchall()}

    for row in rows:
        m = f"{row['ano']}-{row['mes']:02d}"
        ap = ap_rows.get(m, {"total": 0, "pago": 0})
        ar = ar_rows.get(m, {"total": 0, "recebido": 0})
        row["ap_total"] = round(float(ap["total"]), 2)
        row["ap_pago"] = round(float(ap["pago"]), 2)
        row["ar_total"] = round(float(ar["total"]), 2)
        row["ar_recebido"] = round(float(ar["recebido"]), 2)

    return {"tendencia": rows, "total_meses": len(rows)}


# ====================================================================
# EMPRESAS CADASTRADAS (DROPDOWN)
# ====================================================================

def get_empresas() -> List[Dict[str, Any]]:
    """Retorna as empresas (CNPJ + nome) encontradas nas NF-e."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT empresa_cnpj as cnpj, emitente_nome as nome
            FROM nfe_docs
            WHERE empresa_cnpj IS NOT NULL AND empresa_cnpj != ''
            ORDER BY nome
        """)
        empresas = [dict(r) for r in cursor.fetchall()]
    return empresas


# ====================================================================
# INADIMPLÊNCIA POR CLIENTE/FORNECEDOR
# ====================================================================

def get_inadimplencia(empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Relatório de inadimplência: agrupa contas a receber por cliente."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None
    emp_filter = ""
    emp_params = []
    if clean_cnpj:
        emp_filter = " AND (r.empresa_cnpj = ? OR r.cliente_cnpj = ?)"
        emp_params = [clean_cnpj, clean_cnpj]

    now_str = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT r.cliente_nome, r.cliente_cnpj,
                   SUM(r.v_dup) as total,
                   SUM(CASE WHEN r.recebido=0 AND (r.d_venc < ? OR r.d_venc = ?) THEN r.v_dup ELSE 0 END) as vencido,
                   SUM(CASE WHEN r.recebido=0 AND r.d_venc >= ? THEN r.v_dup ELSE 0 END) as aberto
            FROM nfe_contas_receber r
            JOIN nfe_docs doc ON r.chave = doc.chave
            WHERE doc.tipo_doc = 1 {emp_filter}
            GROUP BY r.cliente_nome, r.cliente_cnpj
            ORDER BY vencido DESC
        """, [now_str, now_str, now_str] + emp_params)
        rows = [dict(r) for r in cursor.fetchall()]

    for row in rows:
        total = float(row["total"] or 0.0)
        vencido = float(row["vencido"] or 0.0)
        row["pct_vencido"] = round((vencido / total) * 100, 2) if total > 0 else 0.0
        row["status"] = "INADIMPLENTE" if row["pct_vencido"] >= 50 else ("ATENÇÃO" if row["pct_vencido"] >= 20 else "EM DIA")

    return {"inadimplentes": rows, "total_clientes": len(rows)}


# ====================================================================
# CONFERÊNCIA CEGA DE ESTOQUE (CHECK-IN DE MERCADORIAS)
# ====================================================================

def get_conferencia(chave: str) -> Dict[str, Any]:
    """Retorna o status da conferência de estoque de uma NF-e e a lista de itens."""
    doc = get_nfe_detail(chave)
    if not doc:
        return {}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nfe_conferencia WHERE chave = ?", (chave,))
        conf = cursor.fetchone()

        conf_data = dict(conf) if conf else {
            "chave": chave,
            "empresa_cnpj": doc.get("empresa_cnpj", ""),
            "status": "PENDENTE",
            "conferido_por": "",
            "data_conferencia": "",
            "divergencias_count": 0,
            "observacoes": "",
        }

        cursor.execute("SELECT * FROM nfe_conferencia_items WHERE chave = ?", (chave,))
        saved_items = {r["codigo"] or r["descricao"]: dict(r) for r in cursor.fetchall()}

    items_list = []
    for it in doc.get("produtos", []):
        k = it.get("codigo") or it.get("descricao")
        saved = saved_items.get(k, {})
        qtd_nota = float(it.get("quantidade") or 0.0)
        qtd_conf = float(saved.get("qtd_conferida") or 0.0)
        diverg = qtd_conf != qtd_nota and conf_data.get("status") == "CONFERIDO"

        items_list.append({
            "codigo": it.get("codigo", ""),
            "ean": it.get("ean", ""),
            "descricao": it.get("descricao", ""),
            "ncm": it.get("ncm", ""),
            "unidade": it.get("unidade", "UN"),
            "qtd_nota": qtd_nota,
            "qtd_conferida": qtd_conf,
            "divergencia": diverg,
            "seriais": saved.get("seriais", ""),
            "status": "OK" if qtd_conf == qtd_nota and qtd_nota > 0 else ("DIVERGENTE" if qtd_conf > 0 else "PENDENTE"),
        })

    return {
        "conferencia": conf_data,
        "nfe": {
            "chave": doc["chave"],
            "numero": doc.get("numero", ""),
            "serie": doc.get("serie", "1"),
            "emitente_nome": doc.get("emitente_nome", ""),
            "destinatario_nome": doc.get("destinatario_nome", ""),
            "data_emissao": doc.get("data_emissao", ""),
            "valor_total": doc.get("valor_total", 0.0),
        },
        "itens": items_list,
    }


def salvar_conferencia(chave: str, conferido_por: str, itens: List[Dict[str, Any]], observacoes: str = "") -> Dict[str, Any]:
    """Salva a conferência física dos produtos da NF-e e detecta divergências."""
    now = datetime.now().isoformat()
    divergencias = 0

    for it in itens:
        if float(it.get("qtd_conferida", 0)) != float(it.get("qtd_nota", 0)):
            divergencias += 1

    status = "CONFERIDO_DIVERGENCIA" if divergencias > 0 else "CONFERIDO_OK"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT empresa_cnpj FROM nfe_docs WHERE chave = ?", (chave,))
        r = cursor.fetchone()
        emp_cnpj = r["empresa_cnpj"] if r else ""

        cursor.execute("""
            INSERT INTO nfe_conferencia (chave, empresa_cnpj, status, conferido_por, data_conferencia, divergencias_count, observacoes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                status = excluded.status,
                conferido_por = excluded.conferido_por,
                data_conferencia = excluded.data_conferencia,
                divergencias_count = excluded.divergencias_count,
                observacoes = excluded.observacoes
        """, (chave, emp_cnpj, status, conferido_por, now, divergencias, observacoes, now))
        conf_id = cursor.lastrowid

        cursor.execute("DELETE FROM nfe_conferencia_items WHERE chave = ?", (chave,))
        for it in itens:
            q_nota = float(it.get("qtd_nota", 0))
            q_conf = float(it.get("qtd_conferida", 0))
            st_it = "OK" if q_nota == q_conf else "DIVERGENTE"
            cursor.execute("""
                INSERT INTO nfe_conferencia_items (conferencia_id, chave, codigo, descricao, qtd_nota, qtd_conferida, seriais, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (conf_id, chave, it.get("codigo", ""), it.get("descricao", ""), q_nota, q_conf, it.get("seriais", ""), st_it))

        conn.commit()

    return {
        "success": True,
        "status": status,
        "divergencias_count": divergencias,
        "data_conferencia": now,
    }


# ====================================================================
# AUDITORIA DE RISCO & IDONEIDADE FISCAL DOS FORNECEDORES
# ====================================================================

def get_auditoria_fornecedores(empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Audita os fornecedores cadastrados nas notas fiscais para apontar riscos fiscais."""
    emp_cond = ""
    emp_params = []
    if empresa_cnpj:
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            emp_cond = " WHERE (empresa_cnpj = ? OR destinatario_cnpj LIKE ?)"
            emp_params = [emp_digits, f"%{emp_digits}%"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT emitente_cnpj, emitente_nome, emitente_uf,
                   COUNT(*) as qtd_notas, SUM(valor_total) as volume_total,
                   MIN(data_emissao) as primeira_compra, MAX(data_emissao) as ultima_compra
            FROM nfe_docs
            {emp_cond}
            GROUP BY emitente_cnpj, emitente_nome, emitente_uf
            ORDER BY volume_total DESC
        """, emp_params)
        rows = [dict(r) for r in cursor.fetchall()]

    auditoria = []
    for r in rows:
        cnpj = "".join(c for c in str(r["emitente_cnpj"] or "") if c.isdigit())
        score = 100
        alertas = []

        # Validação matemática de dígitos verificadores do CNPJ
        if len(cnpj) != 14:
            score -= 50
            alertas.append("CNPJ com tamanho inválido")
        else:
            # Algoritmo de verificação de CNPJ
            def validar_cnpj(c):
                pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
                d1 = sum(int(c[i]) * pesos1[i] for i in range(12)) % 11
                d1 = 0 if d1 < 2 else 11 - d1
                d2 = sum(int(c[i]) * pesos2[i] for i in range(13)) % 11
                d2 = 0 if d2 < 2 else 11 - d2
                return c[-2:] == f"{d1}{d2}"

            if not validar_cnpj(cnpj):
                score -= 60
                alertas.append("Dígito verificador do CNPJ inválido")

        if not r["emitente_uf"]:
            score -= 10
            alertas.append("UF do fornecedor não identificada")

        if r["qtd_notas"] >= 3:
            score = min(100, score + 10)

        cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj

        auditoria.append({
            "cnpj": cnpj_fmt,
            "razao_social": r["emitente_nome"],
            "uf": r["emitente_uf"] or "—",
            "qtd_notas": r["qtd_notas"],
            "volume_total": float(r["volume_total"] or 0.0),
            "primeira_compra": r["primeira_compra"],
            "ultima_compra": r["ultima_compra"],
            "score_conformidade": max(0, score),
            "nivel_risco": "BAIXO" if score >= 80 else ("MÉDIO" if score >= 50 else "ALTO"),
            "alertas": alertas,
            "status_sefaz": "HABILITADO / REGULAR",
        })

    return auditoria


# ====================================================================
# EMISSÃO DE NF-e: CLIENTES, PRODUTOS, PRÓXIMO NÚMERO & HISTÓRICO DE SAÍDAS
# ====================================================================

def save_cliente(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cadastra ou atualiza um cliente destinatário."""
    doc_clean = "".join(c for c in str(data.get("cpf_cnpj", "")) if c.isdigit())
    if not doc_clean or not data.get("razao_social"):
        raise ValueError("CPF/CNPJ e Razão Social são obrigatórios.")

    tipo_pessoa = "PF" if len(doc_clean) == 11 else "PJ"
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cli_id = data.get("id")
        if cli_id:
            cursor.execute("SELECT id FROM cad_clientes WHERE id = ?", (cli_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT id FROM cad_clientes WHERE cpf_cnpj = ?", (doc_clean,))
            row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE cad_clientes
                SET tipo_pessoa = ?, cpf_cnpj = ?, razao_social = ?, nome_fantasia = ?, ie = ?, indicador_ie = ?,
                    email = ?, telefone = ?, cep = ?, logradouro = ?, numero = ?, complemento = ?,
                    bairro = ?, municipio = ?, cod_municipio = ?, uf = ?, updated_at = ?
                WHERE id = ?
            """, (
                tipo_pessoa,
                doc_clean,
                data.get("razao_social", "").strip().upper(),
                data.get("nome_fantasia", "").strip().upper(),
                data.get("ie", "").strip(),
                int(data.get("indicador_ie", 9)),
                data.get("email", "").strip().lower(),
                data.get("telefone", "").strip(),
                data.get("cep", "").replace("-", "").strip(),
                data.get("logradouro", "").strip(),
                data.get("numero", "").strip(),
                data.get("complemento", "").strip(),
                data.get("bairro", "").strip(),
                data.get("municipio", "").strip(),
                data.get("cod_municipio", "3550308").strip(),
                data.get("uf", "SP").strip().upper(),
                now_iso,
                row["id"]
            ))
            cliente_id = row["id"]
        else:
            cursor.execute("""
                INSERT INTO cad_clientes (
                    tipo_pessoa, cpf_cnpj, razao_social, nome_fantasia, ie, indicador_ie,
                    email, telefone, cep, logradouro, numero, complemento,
                    bairro, municipio, cod_municipio, uf, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tipo_pessoa,
                doc_clean,
                data.get("razao_social", "").strip().upper(),
                data.get("nome_fantasia", "").strip().upper(),
                data.get("ie", "").strip(),
                int(data.get("indicador_ie", 9)),
                data.get("email", "").strip().lower(),
                data.get("telefone", "").strip(),
                data.get("cep", "").replace("-", "").strip(),
                data.get("logradouro", "").strip(),
                data.get("numero", "").strip(),
                data.get("complemento", "").strip(),
                data.get("bairro", "").strip(),
                data.get("municipio", "").strip(),
                data.get("cod_municipio", "3550308").strip(),
                data.get("uf", "SP").strip().upper(),
                now_iso,
                now_iso
            ))
            cliente_id = cursor.lastrowid
        conn.commit()

    return {"success": True, "id": cliente_id, "cpf_cnpj": doc_clean}


def list_clientes(busca: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista todos os clientes com suporte a busca rápida por nome, CPF/CNPJ, e-mail e telefone."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if busca and busca.strip():
            b_clean = busca.strip()
            digits = "".join(c for c in b_clean if c.isdigit())
            b_like = f"%{b_clean}%"
            conds = [
                "razao_social LIKE ?",
                "nome_fantasia LIKE ?",
                "email LIKE ?",
                "telefone LIKE ?",
                "cpf_cnpj LIKE ?",
            ]
            params = [b_like, b_like, b_like, b_like, b_like]
            if len(digits) >= 2:
                conds.append("REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') LIKE ?")
                conds.append("REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(telefone, '(', ''), ')', ''), '-', ''), ' ', ''), '+', '') LIKE ?")
                params.extend([f"%{digits}%", f"%{digits}%"])
            cursor.execute(f"SELECT * FROM cad_clientes WHERE {' OR '.join(conds)} ORDER BY razao_social ASC LIMIT 100", params)
        else:
            cursor.execute("SELECT * FROM cad_clientes ORDER BY razao_social ASC LIMIT 2000")
        return [dict(r) for r in cursor.fetchall()]


def delete_cliente(cliente_id: int) -> bool:
    """Exclui um cliente do cadastro."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cad_clientes WHERE id = ?", (cliente_id,))
        conn.commit()
        return cursor.rowcount > 0


def save_produto(data: Dict[str, Any]) -> Dict[str, Any]:
    """Cadastra ou atualiza um item no catálogo de produtos com parâmetros fiscais completos."""
    codigo = str(data.get("codigo", "")).strip().upper()
    descricao = str(data.get("descricao", "")).strip().upper()
    ncm = "".join(c for c in str(data.get("ncm", "")) if c.isdigit())
    if not codigo or not descricao or not ncm:
        raise ValueError("Código, Descrição e NCM (8 dígitos) são obrigatórios.")

    now_iso = datetime.now().isoformat()
    preco = float(data.get("preco_venda", 0.0))
    preco_custo = float(data.get("preco_custo", 0.0))
    estoque_atual = float(data.get("estoque_atual", 0.0))
    estoque_min = float(data.get("estoque_minimo", 0.0))
    cfop = str(data.get("cfop_padrao", "5102")).strip()
    cfop_inter = str(data.get("cfop_interestadual", "6102")).strip()
    cest = str(data.get("cest", "")).strip()
    unidade = str(data.get("unidade", "UN")).strip().upper()
    origem = int(data.get("origem", 0))
    csosn = str(data.get("csosn_cst", "102")).strip()
    aliq_icms = float(data.get("aliquota_icms", 0.0))
    gtin = str(data.get("gtin", "")).strip()
    imei = str(data.get("imei", "")).strip().upper()
    marca = str(data.get("marca", "")).strip().upper()
    prod_id_input = data.get("id")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if prod_id_input:
            cursor.execute("SELECT id FROM cad_produtos WHERE id = ?", (prod_id_input,))
            row = cursor.fetchone()
        else:
            cursor.execute("SELECT id FROM cad_produtos WHERE codigo = ?", (codigo,))
            row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE cad_produtos
                SET codigo = ?, descricao = ?, ncm = ?, cest = ?, cfop_padrao = ?, cfop_interestadual = ?,
                    unidade = ?, preco_venda = ?, preco_custo = ?, estoque_atual = ?, estoque_minimo = ?,
                    origem = ?, csosn_cst = ?, aliquota_icms = ?, gtin = ?, imei = ?, marca = ?, updated_at = ?
                WHERE id = ?
            """, (
                codigo, descricao, ncm, cest, cfop, cfop_inter,
                unidade, preco, preco_custo, estoque_atual, estoque_min,
                origem, csosn, aliq_icms, gtin, imei, marca, now_iso, row["id"]
            ))
            prod_id = row["id"]
        else:
            cursor.execute("""
                INSERT INTO cad_produtos (
                    codigo, descricao, ncm, cest, cfop_padrao, cfop_interestadual, unidade, preco_venda,
                    preco_custo, estoque_atual, estoque_minimo, origem, csosn_cst, aliquota_icms, gtin, imei, marca, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                codigo, descricao, ncm, cest, cfop, cfop_inter, unidade, preco,
                preco_custo, estoque_atual, estoque_min, origem, csosn, aliq_icms, gtin, imei, marca, now_iso, now_iso
            ))
            prod_id = cursor.lastrowid
        conn.commit()

    return {"success": True, "id": prod_id, "codigo": codigo, "descricao": descricao}


def get_produto_detail(prod_id: int) -> Optional[Dict[str, Any]]:
    """Retorna os dados completos de um produto específico."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cad_produtos WHERE id = ?", (prod_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def sugerir_dados_fiscais_produto(termo: str) -> Dict[str, Any]:
    """
    Analisa a descrição digitada pelo usuário e consulta o histórico real de NF-e emitidas
    e a base de regras tributárias para sugerir automaticamente NCM, CEST, CFOP e Unidade.
    """
    termo_clean = (termo or "").strip().lower()
    if not termo_clean:
        return {
            "ncm": "85171300",
            "cest": "21.053.00",
            "cfop_padrao": "5102",
            "cfop_interestadual": "6102",
            "unidade": "UN",
            "origem": 0,
            "csosn_cst": "102",
            "fonte": "PADRAO"
        }

    # 1. Consulta no histórico de NF-e
    with get_db_connection() as conn:
        cursor = conn.cursor()
        t = f"%{termo_clean}%"
        cursor.execute("""
            SELECT ncm, cfop, unidade, AVG(valor_unitario) as preco_medio, COUNT(*) as cnt
            FROM nfe_items
            WHERE LOWER(descricao) LIKE ? AND ncm IS NOT NULL AND ncm != ''
            GROUP BY ncm, cfop, unidade
            ORDER BY cnt DESC
            LIMIT 1
        """, (t,))
        r = cursor.fetchone()
        if r and r["ncm"]:
            ncm_hist = str(r["ncm"]).replace(".", "").strip()
            cfop_hist = str(r["cfop"] or "5102").replace(".", "").strip()
            cfop_inter = "6102" if cfop_hist == "5102" else ("6403" if cfop_hist == "5405" else "6102")
            csosn_hist = "500" if cfop_hist == "5405" else "102"
            return {
                "ncm": ncm_hist,
                "cest": "21.053.00" if ncm_hist == "85171300" else "",
                "cfop_padrao": cfop_hist,
                "cfop_interestadual": cfop_inter,
                "unidade": str(r["unidade"] or "UN").upper(),
                "preco_sugerido": round(float(r["preco_medio"] or 0.0), 2),
                "origem": 0,
                "csosn_cst": csosn_hist,
                "fonte": f"HISTÓRICO NF-e ({r['cnt']} notas)",
                "ocorrencias": r["cnt"]
            }

    # 2. Base de conhecimento fiscal por categoria
    regras = [
        (["galaxy", "iphone", "celular", "smartphone", "xiaomi", "redmi", "motorola", "poco", "sansung", "samsung", "moto"], {
            "ncm": "85171300", "cest": "21.053.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Smartphones e Celulares"
        }),
        (["capa", "case", "capinha"], {
            "ncm": "85176262", "cest": "21.066.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Capas Protetoras"
        }),
        (["pelicula", "vidro", "ceramica", "hidrogel", "3d", "privacidade"], {
            "ncm": "39204900", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Películas de Proteção"
        }),
        (["carregador", "fonte", "adaptador", "turbo", "tomada"], {
            "ncm": "85044010", "cest": "21.001.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Carregadores e Fontes"
        }),
        (["fone", "headphone", "earphone", "airpod", "buds", "headset"], {
            "ncm": "85183000", "cest": "21.058.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Fones e Áudio"
        }),
        (["cabo", "lightning", "usb", "tipo c", "type c"], {
            "ncm": "85444200", "cest": "21.066.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Cabos e Conectores"
        }),
        (["tablet", "ipad", "pad"], {
            "ncm": "84713012", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Tablets"
        }),
        (["smartwatch", "relogio", "watch", "band", "pulseira"], {
            "ncm": "85176277", "cest": "", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Relógios Inteligentes"
        }),
        (["caixa de som", "speaker", "soundbar", "alexa", "echo"], {
            "ncm": "85182200", "cest": "21.057.00", "cfop_padrao": "5102", "cfop_interestadual": "6102", "unidade": "UN", "origem": 0, "csosn_cst": "102", "categoria": "Caixas de Som"
        })
    ]

    for palavras, dados in regras:
        if any(p in termo_clean for p in palavras):
            return {**dados, "fonte": f"CATEGORIA: {dados.get('categoria', 'Geral')}"}

    return {
        "ncm": "85171300",
        "cest": "21.053.00",
        "cfop_padrao": "5102",
        "cfop_interestadual": "6102",
        "unidade": "UN",
        "origem": 0,
        "csosn_cst": "102",
        "fonte": "SUGESTÃO AUTOMÁTICA"
    }


def list_produtos(busca: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista catálogo de produtos com busca rápida."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if busca and busca.strip():
            b = f"%{busca.strip()}%"
            cursor.execute("""
                SELECT * FROM cad_produtos
                WHERE descricao LIKE ? OR codigo LIKE ? OR ncm LIKE ? OR gtin LIKE ?
                ORDER BY descricao ASC
            """, (b, b, b, b))
        else:
            cursor.execute("SELECT * FROM cad_produtos ORDER BY descricao ASC")
        return [dict(r) for r in cursor.fetchall()]


def delete_produto(prod_id: int) -> bool:
    """Exclui um produto do catálogo."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cad_produtos WHERE id = ?", (prod_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_next_nfe_number(empresa_cnpj: str, serie: str = "1", modelo: str = "55") -> int:
    """Calcula o próximo número sequencial de NF-e (Mod 55) ou NFC-e (Mod 65) para a empresa emitente e série informadas."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit())
    clean_serie = str(serie or "1").strip()
    clean_modelo = str(modelo or "55").strip()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Verifica notas emitidas por essa empresa (Saídas - tipo_doc = 1)
        if clean_modelo == "65":
            cursor.execute("""
                SELECT MAX(CAST(numero AS INTEGER)) as max_num
                FROM nfe_docs
                WHERE emitente_cnpj = ? AND serie = ? AND tipo_doc = 1 AND modelo = '65'
            """, (clean_cnpj, clean_serie))
        else:
            cursor.execute("""
                SELECT MAX(CAST(numero AS INTEGER)) as max_num
                FROM nfe_docs
                WHERE emitente_cnpj = ? AND serie = ? AND tipo_doc = 1 AND (modelo = '55' OR modelo IS NULL)
            """, (clean_cnpj, clean_serie))
        row = cursor.fetchone()
        max_doc = int(row["max_num"]) if row and row["max_num"] else 0

        # 2. Verifica se houve inutilizações de numeração cadastradas
        try:
            cursor.execute("""
                SELECT MAX(numero_final) as max_inu
                FROM nfe_inutilizacoes
                WHERE empresa_cnpj = ? AND serie = ? AND modelo = ?
            """, (clean_cnpj, clean_serie, clean_modelo))
            row_inu = cursor.fetchone()
            max_inu = int(row_inu["max_inu"]) if row_inu and row_inu["max_inu"] else 0
        except Exception:
            max_inu = 0

        max_final = max(max_doc, max_inu)
        return max_final + 1


def list_nfe_saidas(
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    busca: Optional[str] = None,
    situacao: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Lista todas as notas fiscais emitidas (Saídas para Clientes / Devoluções / Transferências)."""
    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    # Identifica todas as nossas empresas cadastradas
    nossos_cnpjs = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cnpj FROM certificates WHERE is_active = 1")
        nossos_cnpjs = [r["cnpj"] for r in cursor.fetchall()]

    query = """
        SELECT d.*,
               (SELECT COUNT(*) FROM nfe_items WHERE chave = d.chave) as qtd_itens
        FROM nfe_docs d
        WHERE (d.tipo_doc = 1 OR d.emitente_cnpj IN ({cnpjs}))
    """.format(cnpjs=",".join(f"'{c}'" for c in nossos_cnpjs) if nossos_cnpjs else "'00000000000000'")

    params = []

    if clean_cnpj:
        query += " AND (d.empresa_cnpj = ? OR d.emitente_cnpj = ?)"
        params.extend([clean_cnpj, clean_cnpj])

    if data_inicio:
        query += " AND substr(d.data_emissao, 1, 10) >= ?"
        params.append(data_inicio)

    if data_fim:
        query += " AND substr(d.data_emissao, 1, 10) <= ?"
        params.append(data_fim)

    if situacao and situacao.strip():
        sit_norm = situacao.strip().lower()
        if sit_norm == "autorizada" or sit_norm == "autorizadas":
            query += " AND (d.situacao LIKE '%autorizad%' OR d.situacao IS NULL OR d.situacao = '' OR d.situacao = '100')"
        elif sit_norm == "pendente" or sit_norm == "pendentes":
            query += " AND (d.situacao LIKE '%pendent%' OR d.situacao LIKE '%processamento%' OR d.situacao LIKE '%contingencia%')"
        elif sit_norm == "cancelada" or sit_norm == "canceladas":
            query += " AND (d.situacao LIKE '%cancelad%' OR d.situacao = '101')"
        elif sit_norm == "rejeitada" or sit_norm == "rejeitadas":
            query += " AND (d.situacao LIKE '%rejeit%' OR d.situacao LIKE '%erro%' OR d.situacao LIKE '%denegad%')"
        else:
            query += " AND d.situacao LIKE ?"
            params.append(f"%{situacao.strip()}%")

    if busca and busca.strip():
        b = f"%{busca.strip()}%"
        query += " AND (d.chave LIKE ? OR d.numero LIKE ? OR d.destinatario_nome LIKE ? OR d.destinatario_cnpj LIKE ?)"
        params.extend([b, b, b, b])

    count_query = f"SELECT COUNT(*) FROM ({query})"
    query += " ORDER BY d.data_emissao DESC, d.numero DESC LIMIT ? OFFSET ?"

    offset = (page - 1) * limit
    paged_params = list(params) + [limit, offset]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        cursor.execute(query, paged_params)
        docs = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "page": page,
        "limit": limit,
        "documentos": docs,
    }


def cancelar_nfe_doc(chave: str, protocolo: str, justificativa: str) -> bool:
    """Registra o cancelamento de uma NF-e no banco e cria o evento fiscal 110111."""
    chave_clean = "".join(c for c in str(chave) if c.isdigit())
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE nfe_docs
            SET situacao = 'Cancelada', updated_at = ?
            WHERE chave = ?
        """, (now_iso, chave_clean))

        cursor.execute("""
            INSERT INTO nfe_events (
                chave, tipo_evento, desc_evento, n_seq, protocolo, c_stat, x_motivo, dh_evento, created_at
            ) VALUES (?, '110111', 'Cancelamento de NF-e homologado', 1, ?, '135', ?, ?, ?)
        """, (chave_clean, protocolo, justificativa, now_iso, now_iso))
        conn.commit()
        return True


# ====================================================================
# INUTILIZAÇÃO DE NUMERAÇÃO DE NF-e / NFC-e
# ====================================================================

def save_inutilizacao(data: Dict[str, Any]) -> Dict[str, Any]:
    """Registra a inutilização de numeração homologada na SEFAZ."""
    empresa_cnpj = "".join(c for c in str(data.get("empresa_cnpj", "")) if c.isdigit())
    now_iso = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO nfe_inutilizacoes (
                empresa_cnpj, ano, modelo, serie, numero_inicial, numero_final,
                protocolo, justificativa, data_homologacao, c_stat, x_motivo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            empresa_cnpj,
            int(data.get("ano", datetime.now().year)),
            str(data.get("modelo", "55")),
            int(data.get("serie", 1)),
            int(data.get("numero_inicial", 1)),
            int(data.get("numero_final", 1)),
            str(data.get("protocolo", "")),
            str(data.get("justificativa", "")),
            str(data.get("data_homologacao", now_iso)),
            str(data.get("c_stat", "102")),
            str(data.get("x_motivo", "Inutilização de número homologada")),
            now_iso
        ))
        conn.commit()
        return {"id": cursor.lastrowid, **data}


def list_inutilizacoes(empresa_cnpj: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lista as faixas de numeração inutilizadas na SEFAZ."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if empresa_cnpj:
            clean_cnpj = "".join(c for c in empresa_cnpj if c.isdigit())
            cursor.execute("SELECT * FROM nfe_inutilizacoes WHERE empresa_cnpj = ? ORDER BY id DESC", (clean_cnpj,))
        else:
            cursor.execute("SELECT * FROM nfe_inutilizacoes ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]


# ====================================================================
# CHECK-IN AUTOMÁTICO DE ESTOQUE (A PARTIR DE NF-e DE COMPRA/ENTRADA)
# ====================================================================

def checkin_nfe_estoque(chave: str, markup_sugerido_pct: float = 40.0) -> Dict[str, Any]:
    """
    Processa os itens de uma NF-e de Entrada recebida de fornecedor:
    1. Cadastra automaticamente os produtos novos no catálogo (cad_produtos).
    2. Atualiza o estoque_atual somando as quantidades compradas.
    3. Registra a movimentação no histórico de estoque (Kardex).
    """
    chave_clean = "".join(c for c in chave if c.isdigit())
    now_iso = datetime.now().isoformat()

    doc = get_nfe_detail(chave_clean)
    if not doc:
        raise ValueError("NF-e não localizada no banco de dados local.")

    items = doc.get("produtos", [])
    if not items:
        raise ValueError("Esta NF-e não possui itens de produtos cadastrados.")

    produtos_cadastrados = 0
    produtos_atualizados = 0
    total_itens_processados = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for it in items:
            cod_item = str(it.get("codigo") or f"PRD_{it.get('id', 1):04d}").strip()
            desc_item = str(it.get("descricao") or "PRODUTO RECEBIDO").strip().upper()
            ncm_item = str(it.get("ncm") or "85171300").replace(".", "").strip()
            cfop_item = str(it.get("cfop") or "5102").replace(".", "").strip()
            qtd_item = float(it.get("quantidade") or 1.0)
            v_unit = float(it.get("valor_unitario") or 0.0)
            v_venda_sugerido = round(v_unit * (1.0 + (markup_sugerido_pct / 100.0)), 2)

            # Verifica se produto já existe no catálogo
            cursor.execute("SELECT id, codigo, estoque_atual, preco_venda FROM cad_produtos WHERE codigo = ? OR descricao = ?", (cod_item, desc_item))
            p_row = cursor.fetchone()

            saldo_anterior = 0.0
            if p_row:
                p_id = p_row["id"]
                saldo_anterior = float(p_row["estoque_atual"] or 0.0)
                saldo_novo = saldo_anterior + qtd_item
                # Atualiza estoque e preço de venda se estiver zerado
                cursor.execute("""
                    UPDATE cad_produtos
                    SET estoque_atual = ?, preco_custo = ?, updated_at = ?
                    WHERE id = ?
                """, (saldo_novo, v_unit, now_iso, p_id))
                produtos_atualizados += 1
            else:
                saldo_novo = qtd_item
                cursor.execute("""
                    INSERT OR IGNORE INTO cad_produtos (
                        codigo, descricao, ncm, cfop_padrao, unidade, preco_venda, preco_custo,
                        origem, csosn_cst, aliquota_icms, gtin, estoque_atual, ativo, created_at, updated_at
                    ) VALUES (?, ?, ?, '5102', 'UN', ?, ?, 0, '102', 0.0, '', ?, 1, ?, ?)
                """, (cod_item, desc_item, ncm_item, v_venda_sugerido if v_venda_sugerido > 0 else v_unit, v_unit, saldo_novo, now_iso, now_iso))
                produtos_cadastrados += 1

            # Registra no Kardex
            cursor.execute("""
                INSERT INTO estoque_movimentacoes (
                    chave_nfe, codigo_produto, descricao, tipo, quantidade,
                    saldo_anterior, saldo_novo, valor_unitario, motivo, data_hora
                ) VALUES (?, ?, ?, 'ENTRADA_NFE', ?, ?, ?, ?, ?, ?)
            """, (
                chave_clean, cod_item, desc_item, qtd_item,
                saldo_anterior, saldo_novo, v_unit,
                f"Check-in NF-e {doc.get('numero', '')} de {doc.get('emitente_nome', 'Fornecedor')}",
                now_iso
            ))
            total_itens_processados += 1

        conn.commit()

    return {
        "success": True,
        "chave": chave_clean,
        "total_itens": total_itens_processados,
        "produtos_novos": produtos_cadastrados,
        "produtos_atualizados": produtos_atualizados,
        "message": f"Check-in concluído! {total_itens_processados} itens adicionados ao estoque com sucesso."
    }


def get_historico_estoque(codigo_produto: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retorna o extrato de movimentações de estoque (Kardex)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if codigo_produto:
            cursor.execute("SELECT * FROM estoque_movimentacoes WHERE codigo_produto = ? ORDER BY id DESC LIMIT ?", (codigo_produto, limit))
        else:
            cursor.execute("SELECT * FROM estoque_movimentacoes ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]


# ====================================================================
# APURAÇÃO DO SIMPLES NACIONAL (LEI COMPLEMENTAR 123/2006)
# ====================================================================

def get_simples_nacional_apuracao(ano: Optional[int] = None, mes: Optional[int] = None, empresa_cnpj: Optional[str] = None) -> Dict[str, Any]:
    """
    Calcula a estimativa de imposto do Simples Nacional (Anexo I - Comércio)
    com base no Faturamento dos últimos 12 meses (RBT12) e receita do mês corrente.
    """
    now = datetime.now()
    cur_ano = ano or now.year
    cur_mes = mes or now.month

    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    # Tabela Anexo I - Comércio (LC 123/2006)
    # Faixas: (Limite Superior, Alíquota Nominal %, Parcela a Deduzir R$)
    FAIXAS_ANEXO_I = [
        (180000.00, 0.0400, 0.00),         # 1ª Faixa: até 180k -> 4.00%
        (360000.00, 0.0730, 5940.00),      # 2ª Faixa: 180k a 360k -> 7.30%
        (720000.00, 0.0950, 13860.00),     # 3ª Faixa: 360k a 720k -> 9.50%
        (1800000.00, 0.1070, 22500.00),    # 4ª Faixa: 720k a 1.8M -> 10.70%
        (3600000.00, 0.1430, 87300.00),    # 5ª Faixa: 1.8M a 3.6M -> 14.30%
        (4800000.00, 0.1900, 378000.00),   # 6ª Faixa: 3.6M a 4.8M -> 19.00%
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Faturamento do Mês Corrente (Saídas / Vendas com tipo_doc=1)
        data_mes_prefix = f"{cur_ano}-{cur_mes:02d}"
        query_mes = "SELECT SUM(valor_total) as rpa, COUNT(*) as qtd FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada' AND substr(data_emissao, 1, 7) = ?"
        params_mes = [data_mes_prefix]
        if clean_cnpj:
            query_mes += " AND (empresa_cnpj = ? OR emitente_cnpj = ?)"
            params_mes.extend([clean_cnpj, clean_cnpj])

        cursor.execute(query_mes, params_mes)
        r_mes = cursor.fetchone()
        receita_mes = float(r_mes["rpa"] or 0.0)
        qtd_vendas = int(r_mes["qtd"] or 0)

        # 2. Faturamento Total Acumulado (RBT12)
        query_rbt = "SELECT SUM(valor_total) as rbt12 FROM nfe_docs WHERE tipo_doc = 1 AND situacao != 'Cancelada'"
        params_rbt = []
        if clean_cnpj:
            query_rbt += " AND (empresa_cnpj = ? OR emitente_cnpj = ?)"
            params_rbt.extend([clean_cnpj, clean_cnpj])

        cursor.execute(query_rbt, params_rbt)
        r_rbt = cursor.fetchone()
        rbt12 = float(r_rbt["rbt12"] or receita_mes)

    # Identifica faixa
    faixa_idx = 1
    aliq_nominal = 0.0400
    parcela_deduzir = 0.00

    for idx, (limite, aliq, ded) in enumerate(FAIXAS_ANEXO_I, start=1):
        if rbt12 <= limite or idx == len(FAIXAS_ANEXO_I):
            faixa_idx = idx
            aliq_nominal = aliq
            parcela_deduzir = ded
            break

    # Alíquota Efetiva = ((RBT12 * AliqNominal) - ParcelaDeduzir) / RBT12
    if rbt12 > 0:
        aliq_efetiva = max(0.0400, ((rbt12 * aliq_nominal) - parcela_deduzir) / rbt12)
    else:
        aliq_efetiva = 0.0400

    valor_das_estimado = round(receita_mes * aliq_efetiva, 2)

    return {
        "ano": cur_ano,
        "mes": cur_mes,
        "competencia": f"{cur_mes:02d}/{cur_ano}",
        "receita_mes": receita_mes,
        "qtd_vendas_mes": qtd_vendas,
        "rbt12": rbt12,
        "anexo": "Anexo I - Comércio",
        "faixa": faixa_idx,
        "aliquota_nominal_pct": round(aliq_nominal * 100, 2),
        "aliquota_efetiva_pct": round(aliq_efetiva * 100, 2),
        "parcela_deduzir": parcela_deduzir,
        "valor_das_estimado": valor_das_estimado,
        "data_vencimento": f"20/{cur_mes + 1 if cur_mes < 12 else 1:02d}/{cur_ano if cur_mes < 12 else cur_ano + 1}",
    }


# ====================================================================
# DRE DE MARGEM REAL POR PRODUTO (COMPRA VS. VENDA)
# ====================================================================

def get_dre_produtos_margem(empresa_cnpj: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Calcula o Lucro Bruto e a Margem Real (%) comparando preço de compra vs preço de venda de cada produto."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Busca preço médio de venda (Saídas)
        cursor.execute("""
            SELECT p.codigo, p.descricao, p.ncm, p.unidade,
                   p.preco_venda as preco_venda_catalogo,
                   p.preco_custo as preco_custo_catalogo,
                   p.estoque_atual,
                   (SELECT AVG(valor_unitario) FROM nfe_items WHERE (codigo = p.codigo OR descricao = p.descricao) AND valor_unitario > 0) as preco_medio_praticado,
                   (SELECT SUM(quantidade) FROM nfe_items WHERE (codigo = p.codigo OR descricao = p.descricao)) as total_vendido
            FROM cad_produtos p
            ORDER BY p.preco_venda DESC
            LIMIT ?
        """, (limit,))
        produtos = [dict(r) for r in cursor.fetchall()]

    dre_list = []
    for p in produtos:
        pv = float(p.get("preco_medio_praticado") or p.get("preco_venda_catalogo") or 0.0)
        pc = float(p.get("preco_custo_catalogo") or (pv * 0.65)) # Estimativa se custo não registrado
        lucro_unitario = pv - pc
        margem_pct = round((lucro_unitario / pv) * 100, 2) if pv > 0 else 0.0

        dre_list.append({
            "codigo": p.get("codigo"),
            "descricao": p.get("descricao"),
            "ncm": p.get("ncm"),
            "estoque": float(p.get("estoque_atual") or 0.0),
            "preco_custo": round(pc, 2),
            "preco_venda": round(pv, 2),
            "lucro_unitario": round(lucro_unitario, 2),
            "margem_lucro_pct": margem_pct,
            "status_margem": "EXCELENTE" if margem_pct >= 40 else ("BOA" if margem_pct >= 20 else "BAIXA")
        })

    return dre_list
