from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query, Depends, Request
from pydantic import BaseModel
from typing import Optional
from backend.services.cert_service import (
    save_certificate,
    get_cert_info,
    list_all_certificates,
    delete_certificate as delete_cert_service,
)
from backend.dependencies import require_session

router = APIRouter(dependencies=[Depends(require_session)])


class CertificadoResponse(BaseModel):
    loaded: bool
    filename: Optional[str] = None
    subject: Optional[str] = None
    issuer: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    days_remaining: Optional[int] = None
    error: Optional[str] = None


@router.get("/certificado/list")
async def list_certificates_endpoint():
    """Retorna todos os certificados digitais A1 cadastrados para visualização de validades."""
    certs = list_all_certificates()
    sanitized = []
    for c in certs:
        d = dict(c)
        d.pop("password", None)
        sanitized.append(d)
    return sanitized


@router.post("/certificado/upload", response_model=CertificadoResponse)
async def upload_certificate(file: UploadFile = File(...), password: str = Form("")):
    if not password:
        raise HTTPException(status_code=400, detail="Senha do certificado obrigatória")

    try:
        content = await file.read()
        filename = file.filename or "certificado.pfx"
        res = save_certificate(content, password, filename=filename)
        info = get_cert_info(res.get("cnpj"))
        if not info.get("loaded"):
            return CertificadoResponse(loaded=False, filename=filename, error=info.get("error", "Certificado inválido ou senha incorreta"))
        return CertificadoResponse(filename=filename, **info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/certificado/info", response_model=CertificadoResponse)
async def certificate_info(cnpj: Optional[str] = Query(None)):
    try:
        info = get_cert_info(cnpj)
        return CertificadoResponse(**info)
    except Exception as e:
        return CertificadoResponse(loaded=False, error=str(e))


@router.post("/certificado/load")
async def load_certificate_endpoint(file: UploadFile = File(...), password: str = Form("")):
    return await upload_certificate(file, password)


@router.delete("/certificado/{cnpj}")
async def delete_single_certificate(cnpj: str, request: Request):
    """Exclui um certificado específico pelo CNPJ."""
    ok = delete_cert_service(cnpj)
    if not ok:
        raise HTTPException(status_code=404, detail="Certificado não encontrado")
    from backend.services.audit_service import record_audit
    record_audit("EXCLUSAO_CERTIFICADO", "CERTIFICADO", cnpj, detalhe=f"Certificado da empresa {cnpj} excluído", request=request)
    return {"status": "ok", "message": f"Certificado {cnpj} excluído com sucesso"}


@router.delete("/certificado")
async def delete_all_certificates(request: Request):
    certs = list_all_certificates()
    for c in certs:
        delete_cert_service(c["cnpj"])
    from backend.services.audit_service import record_audit
    record_audit("EXCLUSAO_TODOS_CERTIFICADOS", "CERTIFICADO", "TODOS", detalhe=f"{len(certs)} certificados excluídos", request=request)
    return {"status": "ok", "message": "Todos os certificados foram removidos"}


@router.put("/certificado/{cnpj}/dados-fiscais")
async def update_cert_fiscal_data_endpoint(cnpj: str, payload: dict, request: Request):
    """Atualiza dados cadastrais e fiscais da empresa dona do certificado (IE, endereço, etc)."""
    from backend.database import update_certificate_fiscal_data, get_certificate_record
    from backend.services.audit_service import record_audit

    cert = get_certificate_record(cnpj)
    if not cert:
        raise HTTPException(status_code=404, detail="Certificado não encontrado")

    ok = update_certificate_fiscal_data(cnpj, payload)
    if not ok:
        raise HTTPException(status_code=400, detail="Não foi possível atualizar os dados fiscais")

    record_audit(
        "ATUALIZACAO_DADOS_FISCAIS_CERT",
        "CERTIFICADO",
        cnpj,
        detalhe=f"Dados fiscais da empresa {cert.get('razao_social', cnpj)} atualizados",
        request=request,
    )
    return {"success": True, "message": "Dados fiscais atualizados com sucesso!"}
