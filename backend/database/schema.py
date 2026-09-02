import os
import sqlite3
import json
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

from backend.config import settings
from backend.database import get_db_connection, DATA_DIR, XML_STORAGE_DIR
from backend.database.certificates import save_certificate_record

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(XML_STORAGE_DIR, exist_ok=True)

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
                csc_token TEXT DEFAULT '',
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
            ("csc_token", "TEXT DEFAULT ''"),
        ]
        for cname, ctype in cols_certs:
            try:
                cursor.execute(f"ALTER TABLE certificates ADD COLUMN {cname} {ctype}")
            except Exception:
                pass

        # Atualização dos dados cadastrais e fiscais a partir do JSON externo.
        # O JSON ``certs/empresas_fiscais.json`` está em .gitignore e contém
        # os dados reais das emitentes; este template nunca toca o repositório.
        try:
            from backend.constants import _empresas_file_path
            import json
            _path = _empresas_file_path()
            if os.path.exists(_path):
                with open(_path, "r", encoding="utf-8") as _f:
                    _data = json.load(_f)
                for emp in _data.get("empresas", []) or []:
                    cnpj = "".join(c for c in str(emp.get("cnpj") or "") if c.isdigit())
                    if not cnpj:
                        continue
                    cursor.execute("""
                        UPDATE certificates
                        SET ie = ?, nome_fantasia = ?, logradouro = ?, numero = ?,
                            complemento = ?, bairro = ?, municipio = ?, cod_municipio = ?,
                            uf = ?, cep = ?, crt = ?
                        WHERE cnpj = ?
                    """, (
                        emp.get("ie", ""),
                        emp.get("nome_fantasia", ""),
                        emp.get("logradouro", ""),
                        emp.get("numero", ""),
                        emp.get("complemento", ""),
                        emp.get("bairro", ""),
                        emp.get("municipio", ""),
                        emp.get("cod_municipio", ""),
                        emp.get("uf", ""),
                        emp.get("cep", ""),
                        int(emp.get("crt", 1) or 1),
                        cnpj,
                    ))
        except Exception as _e:
            import logging
            logging.getLogger("nfe.schema").warning(
                f"Falha ao aplicar dados fiscais externos: {_e}"
            )

        # Tabela de Usuários do Sistema (autenticação backend)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                nome TEXT NOT NULL DEFAULT 'Usuário',
                ativo INTEGER DEFAULT 1,
                perfil TEXT DEFAULT 'admin',
                senha_padrao INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migração segura: adicionar coluna senha_padrao se não existir
        cursor.execute("PRAGMA table_info(usuarios)")
        cols_usu = [col["name"] for col in cursor.fetchall()]
        if "senha_padrao" not in cols_usu:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN senha_padrao INTEGER DEFAULT 0")

        # Seed do usuário administrador padrão (se ainda não existir).
        # IMPORTANTE: a senha do admin NÃO fica mais hardcoded no repositório.
        # Na primeira execução, geramos uma senha aleatória e a exibimos uma
        # única vez no log para que o operador anote. Caso o seed anterior
        # (SHA-256 legado) ainda esteja presente, deixamos intocado — ele
        # será migrado para bcrypt automaticamente no primeiro login válido
        # (ver backend/routers/auth.py).
        import hashlib
        import secrets
        import logging

        _admin_email = "contasgeraljack@gmail.com"
        _admin_nome = "Administrador"
        cursor.execute(
            "SELECT senha_hash FROM usuarios WHERE email = ?",
            (_admin_email,),
        )
        existing = cursor.fetchone()
        if not existing:
            try:
                # Tenta gerar hash bcrypt (preferencial)
                import bcrypt as _bcrypt
                _temp_password = secrets.token_urlsafe(16)
                _admin_hash = "bcrypt$" + _bcrypt.hashpw(
                    _temp_password.encode("utf-8"),
                    _bcrypt.gensalt(rounds=12),
                ).decode("utf-8")
                _log = logging.getLogger("nfe.schema")
                _log.warning(
                    "[NFE] Usuário admin criado com senha temporária: %s "
                    "(troque imediatamente via /api/auth/alterar-senha)",
                    _temp_password,
                )
            except ImportError:
                # Sem bcrypt: cai no legado SHA-256, mas ainda assim com
                # senha aleatória em vez de valor fixo no repositório.
                _temp_password = secrets.token_urlsafe(16)
                _admin_hash = hashlib.sha256(_temp_password.encode("utf-8")).hexdigest()
                _log = logging.getLogger("nfe.schema")
                _log.warning(
                    "[NFE] bcrypt indisponível — admin criado com hash SHA-256. "
                    "Senha temporária: %s",
                    _temp_password,
                )
            cursor.execute("""
                INSERT INTO usuarios (email, senha_hash, nome, ativo, perfil, created_at, updated_at)
                VALUES (?, ?, ?, 1, 'admin', datetime('now'), datetime('now'))
                ON CONFLICT(email) DO NOTHING
            """, (_admin_email, _admin_hash, _admin_nome))

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
        if "last_sefaz_check" not in cols:
            cursor.execute("ALTER TABLE nfe_docs ADD COLUMN last_sefaz_check TEXT")

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
        # Índices Estratégicos de Alta Performance para Consultas e BI
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_tipo_data ON nfe_docs(tipo_doc, data_emissao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_empresa_tipo_data ON nfe_docs(empresa_cnpj, tipo_doc, data_emissao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_emit_cnpj ON nfe_docs(emitente_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfe_situacao ON nfe_docs(situacao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_chave ON nfe_items(chave)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_venc ON nfe_contas_receber(d_venc)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rec_empresa ON nfe_contas_receber(empresa_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_empresa ON nfe_duplicatas(empresa_cnpj)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_venc ON nfe_duplicatas(d_venc)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dup_chave ON nfe_duplicatas(chave)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conf_chave ON nfe_conferencia(chave)")

        conn.commit()

    # Registra automaticamente todos os certificados da pasta certs/
    auto_register_disk_certificates()


# ====================================================================
# GESTÃO DE CERTIFICADOS DIGITAIS A1 (MULTI-EMPRESA)
# ====================================================================

def auto_register_disk_certificates():
    """Varre a pasta certs/ e cadastra automaticamente os arquivos .pfx encontrados.

    A senha do certificado deve estar em cert_meta.json ou na variável de ambiente CERT_PASSWORD.
    Não é feito brute-force com senhas padrão.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend

    cert_files = glob.glob(os.path.join(settings.CERT_DIR, "*.pfx")) + glob.glob(os.path.join(settings.CERT_DIR, "*.p12"))
    if not cert_files:
        return

    # Senha única: cert_meta.json ou env var (não brute-force)
    pwd: str = ""
    meta_path = os.path.join(settings.CERT_DIR, "cert_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                pwd = json.load(f).get("password") or ""
        except Exception:
            pass
    if not pwd:
        pwd = os.environ.get("CERT_PASSWORD", "")

    if not pwd:
        import logging
        logging.getLogger(__name__).warning(
            "Auto-registro de certificados pulado: nenhuma senha encontrada em cert_meta.json ou env var CERT_PASSWORD."
        )
        return

    for cf in cert_files:
        filename = os.path.basename(cf)
        try:
            with open(cf, "rb") as f:
                data = f.read()

            key, cert, _ = pkcs12.load_key_and_certificates(data, pwd.encode("utf-8"), default_backend())
            if not cert:
                continue

            subject = cert.subject.rfc4514_string()
            cnpj = ""
            for part in subject.split(","):
                if ":" in part:
                    _, v = part.split(":", 1)
                    digits = "".join(c for c in v if c.isdigit())
                    if len(digits) == 14:
                        cnpj = digits

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
        except Exception:
            continue


# ====================================================================
# DOCUMENTOS FISCAIS (NF-e, ITENS E EVENTOS)
# ====================================================================
