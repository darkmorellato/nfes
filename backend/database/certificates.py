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
