import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection

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
    csc_token = str(cert_data.get("csc_token") or "")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO certificates (
                cnpj, razao_social, filename, path, password, valid_from, valid_to,
                days_remaining, is_active, last_nsu, max_nsu, last_sync_time, last_sync_status,
                crt, csc_token, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cnpj) DO UPDATE SET
                razao_social = excluded.razao_social,
                filename = excluded.filename,
                path = excluded.path,
                password = excluded.password,
                valid_from = excluded.valid_from,
                valid_to = excluded.valid_to,
                days_remaining = excluded.days_remaining,
                is_active = excluded.is_active,
                crt = excluded.crt,
                csc_token = excluded.csc_token,
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
            int(cert_data.get("crt") or 1),
            csc_token,
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


def update_certificate_fiscal_data(cnpj: str, data: Dict[str, Any], sync_remote: bool = True) -> bool:
    """Atualiza dados fiscais e cadastrais (IE, nome fantasia, endereço, CRT) da empresa/certificado."""
    import json
    from backend.config import settings
    cnpj_clean = "".join(c for c in str(cnpj) if c.isdigit())
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE certificates
            SET ie = ?, nome_fantasia = ?, logradouro = ?, numero = ?,
                complemento = ?, bairro = ?, municipio = ?, cod_municipio = ?,
                uf = ?, cep = ?, crt = ?, updated_at = ?
            WHERE cnpj = ?
        """, (
            str(data.get("ie") or "").strip(),
            str(data.get("nome_fantasia") or "").strip(),
            str(data.get("logradouro") or "").strip(),
            str(data.get("numero") or "").strip(),
            str(data.get("complemento") or "").strip(),
            str(data.get("bairro") or "").strip(),
            str(data.get("municipio") or "").strip(),
            str(data.get("cod_municipio") or "").strip(),
            str(data.get("uf") or "SP").strip().upper(),
            "".join(c for c in str(data.get("cep") or "") if c.isdigit()),
            int(data.get("crt") or 1),
            now,
            cnpj_clean
        ))
        conn.commit()
        updated = cursor.rowcount > 0

    if updated:
        try:
            # Garante que salva em certs/empresas_fiscais.json (gitignored), nunca sujando o repositório git
            os.makedirs(settings.CERT_DIR, exist_ok=True)
            path = os.path.join(settings.CERT_DIR, "empresas_fiscais.json")
            empresas = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    empresas = json.load(f).get("empresas", [])
            else:
                # Inicializa cópia a partir de data/empresas_fiscais.json se existir
                seed_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "empresas_fiscais.json")
                if os.path.exists(seed_path):
                    try:
                        with open(seed_path, "r", encoding="utf-8") as f:
                            empresas = json.load(f).get("empresas", [])
                    except Exception:
                        empresas = []

            found = False
            for emp in empresas:
                if emp.get("cnpj") == cnpj_clean:
                    emp.update({
                        "ie": str(data.get("ie") or "").strip(),
                        "nome_fantasia": str(data.get("nome_fantasia") or "").strip(),
                        "logradouro": str(data.get("logradouro") or "").strip(),
                        "numero": str(data.get("numero") or "").strip(),
                        "complemento": str(data.get("complemento") or "").strip(),
                        "bairro": str(data.get("bairro") or "").strip(),
                        "municipio": str(data.get("municipio") or "").strip(),
                        "cod_municipio": str(data.get("cod_municipio") or "").strip(),
                        "uf": str(data.get("uf") or "SP").strip().upper(),
                        "cep": "".join(c for c in str(data.get("cep") or "") if c.isdigit()),
                        "crt": int(data.get("crt") or 1),
                    })
                    found = True
                    break
            if not found:
                cert = get_certificate_record(cnpj_clean)
                empresas.append({
                    "cnpj": cnpj_clean,
                    "razao_social": cert.get("razao_social") if cert else "",
                    "ie": str(data.get("ie") or "").strip(),
                    "nome_fantasia": str(data.get("nome_fantasia") or "").strip(),
                    "logradouro": str(data.get("logradouro") or "").strip(),
                    "numero": str(data.get("numero") or "").strip(),
                    "complemento": str(data.get("complemento") or "").strip(),
                    "bairro": str(data.get("bairro") or "").strip(),
                    "municipio": str(data.get("municipio") or "").strip(),
                    "cod_municipio": str(data.get("cod_municipio") or "").strip(),
                    "uf": str(data.get("uf") or "SP").strip().upper(),
                    "cep": "".join(c for c in str(data.get("cep") or "") if c.isdigit()),
                    "crt": int(data.get("crt") or 1),
                })
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"empresas": empresas}, f, indent=2, ensure_ascii=False)

            from backend.constants import reload_empresas_oficiais
            reload_empresas_oficiais()

            if sync_remote:
                try:
                    from backend.services.firestore_service import sync_empresa_fiscal_to_firestore_async
                    emp_fiscal_info = {
                        "cnpj": cnpj_clean,
                        "ie": str(data.get("ie") or "").strip(),
                        "nome_fantasia": str(data.get("nome_fantasia") or "").strip(),
                        "logradouro": str(data.get("logradouro") or "").strip(),
                        "numero": str(data.get("numero") or "").strip(),
                        "complemento": str(data.get("complemento") or "").strip(),
                        "bairro": str(data.get("bairro") or "").strip(),
                        "municipio": str(data.get("municipio") or "").strip(),
                        "cod_municipio": str(data.get("cod_municipio") or "").strip(),
                        "uf": str(data.get("uf") or "SP").strip().upper(),
                        "cep": "".join(c for c in str(data.get("cep") or "") if c.isdigit()),
                        "crt": int(data.get("crt") or 1),
                    }
                    sync_empresa_fiscal_to_firestore_async(cnpj_clean, emp_fiscal_info)
                except Exception:
                    pass

        except Exception:
            pass

    return updated
