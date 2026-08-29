import os
import json
import re
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime

from backend.config import settings
from backend.database import (
    save_certificate_record,
    list_certificates_db,
    get_certificate_record,
    delete_certificate_record,
)


def save_certificate(content: bytes, password: str, filename: str = "certificado.pfx") -> Dict[str, Any]:
    """Salva um certificado PFX/P12, inspeciona seus dados e cadastra na tabela de certificados."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.serialization import pkcs12

    pass_bytes = password.encode("utf-8") if isinstance(password, str) else password
    key, cert, _ = pkcs12.load_key_and_certificates(content, pass_bytes, backend=default_backend())
    if not cert:
        raise ValueError("Não foi possível extrair o certificado do arquivo fornecido")

    subject = cert.subject.rfc4514_string()
    issuer = cert.issuer.rfc4514_string()

    # Extrai CNPJ
    cnpj = ""
    for part in subject.split(","):
        if ":" in part:
            _, v = part.split(":", 1)
            digits = "".join(c for c in v if c.isdigit())
            if len(digits) == 14:
                cnpj = digits
    if not cnpj:
        digits_all = re.findall(r"\d{14}", subject)
        if digits_all:
            cnpj = digits_all[0]

    if not cnpj:
        raise ValueError("CNPJ não encontrado no Certificado Digital A1")

    # Extrai Razão Social
    razao = ""
    for attr in cert.subject:
        if attr.oid._name == "commonName":
            razao = attr.value.split(":")[0].strip()
            break
    if not razao:
        razao = os.path.splitext(filename)[0]

    safe_razao = re.sub(r'[^a-zA-Z0-9_]', '_', razao)
    final_filename = f"{cnpj}_{safe_razao}.pfx"
    cert_path = os.path.join(settings.CERT_DIR, final_filename)

    with open(cert_path, "wb") as f:
        f.write(content)

    val_from = cert.not_valid_before_utc.strftime("%d/%m/%Y")
    val_to = cert.not_valid_after_utc.strftime("%d/%m/%Y")
    days_rem = max(0, (cert.not_valid_after_utc.replace(tzinfo=None) - datetime.utcnow()).days)

    save_certificate_record({
        "cnpj": cnpj,
        "razao_social": razao,
        "filename": final_filename,
        "path": cert_path,
        "password": password,
        "valid_from": val_from,
        "valid_to": val_to,
        "days_remaining": days_rem,
        "is_active": 1,
    })

    # Atualiza cert_meta.json com o último carregado
    metadata = {
        "filename": final_filename,
        "path": cert_path,
        "password": password,
        "cnpj": cnpj,
        "razao_social": razao,
        "uploaded_at": datetime.now().isoformat(),
    }
    with open(os.path.join(settings.CERT_DIR, "cert_meta.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return {
        "loaded": True,
        "cnpj": cnpj,
        "razao_social": razao,
        "valid_from": val_from,
        "valid_to": val_to,
        "days_remaining": days_rem,
        "filename": final_filename,
    }


def load_certificate(content: bytes, password: str, filename: str = "certificado.pfx") -> Dict[str, Any]:
    return save_certificate(content, password, filename)


def get_cert_path(cnpj: Optional[str] = None) -> str:
    """Obtém o caminho do arquivo de certificado. Se cnpj for informado, busca a empresa correspondente."""
    if cnpj:
        rec = get_certificate_record(cnpj)
        if rec and rec.get("path") and os.path.exists(rec["path"]):
            return rec["path"]

    # Fallback para o primeiro certificado ativo do banco
    certs = list_certificates_db()
    for c in certs:
        if c.get("is_active") and c.get("path") and os.path.exists(c["path"]):
            return c["path"]

    meta_path = os.path.join(settings.CERT_DIR, "cert_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        if meta.get("path") and os.path.exists(meta["path"]):
            return meta["path"]

    raise FileNotFoundError("Nenhum certificado digital cadastrado ou encontrado.")


def get_cert_password(cnpj: Optional[str] = None) -> str:
    """Obtém a senha do certificado."""
    if cnpj:
        rec = get_certificate_record(cnpj)
        if rec and rec.get("password"):
            return rec["password"]

    certs = list_certificates_db()
    for c in certs:
        if c.get("is_active") and c.get("password"):
            return c["password"]

    meta_path = os.path.join(settings.CERT_DIR, "cert_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        return meta.get("password", "")

    return ""


def get_cert_info(cnpj: Optional[str] = None) -> Dict[str, Any]:
    """Retorna informações detalhadas do certificado digital."""
    try:
        cert_path = get_cert_path(cnpj)
        cert_password = get_cert_password(cnpj)

        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import pkcs12

        with open(cert_path, "rb") as f:
            pfx_data = f.read()

        pass_bytes = cert_password.encode("utf-8") if isinstance(cert_password, str) else cert_password
        _, cert, _ = pkcs12.load_key_and_certificates(pfx_data, pass_bytes, backend=default_backend())

        if not cert:
            return {"loaded": False, "error": "Não foi possível extrair o certificado do arquivo PFX"}

        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        valid_from = cert.not_valid_before_utc.strftime("%d/%m/%Y")
        valid_to = cert.not_valid_after_utc.strftime("%d/%m/%Y")
        days_rem = max(0, (cert.not_valid_after_utc.replace(tzinfo=None) - datetime.utcnow()).days)

        return {
            "loaded": True,
            "subject": subject,
            "issuer": issuer,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "days_remaining": days_rem,
            "path": cert_path,
        }
    except Exception as e:
        return {"loaded": False, "error": str(e)}


def get_cert_cnpj(cnpj: Optional[str] = None) -> Optional[str]:
    """Extrai o CNPJ da empresa."""
    if cnpj:
        clean = "".join(c for c in cnpj if c.isdigit())
        if len(clean) == 14:
            return clean

    info = get_cert_info(cnpj)
    if not info.get("loaded"):
        return None
    subject = info.get("subject", "")
    cnpj_match = re.search(r':(\d{14})', subject)
    if cnpj_match:
        return cnpj_match.group(1)
    digits = re.findall(r'\d{14}', subject)
    if digits:
        return digits[0]
    return None


def list_all_certificates() -> List[Dict[str, Any]]:
    return list_certificates_db()


def delete_certificate(cnpj: str) -> bool:
    return delete_certificate_record(cnpj)


def check_linux_deps() -> Dict[str, Any]:
    checks = {}
    try:
        import lxml
        checks["lxml"] = {"installed": True, "version": lxml.__version__}
    except Exception as e:
        checks["lxml"] = {"installed": False, "error": str(e)}

    try:
        import OpenSSL
        checks["pyopenssl"] = {"installed": True, "version": OpenSSL.__version__}
    except Exception as e:
        checks["pyopenssl"] = {"installed": False, "error": str(e)}

    try:
        import signxml
        checks["signxml"] = {"installed": True, "version": signxml.__version__}
    except Exception as e:
        checks["signxml"] = {"installed": False, "error": str(e)}

    try:
        import cryptography
        checks["cryptography"] = {"installed": True, "version": cryptography.__version__}
    except Exception as e:
        checks["cryptography"] = {"installed": False, "error": str(e)}

    return checks
