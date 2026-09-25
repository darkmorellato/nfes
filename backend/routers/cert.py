import os

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Query, Depends, Request
from pydantic import BaseModel
from typing import Optional
from backend.services.cert_service import (
    save_certificate,
    get_cert_info,
    list_all_certificates,
    delete_certificate as delete_cert_service,
)
from backend.dependencies import require_session, require_admin

router = APIRouter(dependencies=[Depends(require_session)])

# Limites de upload do certificado A1 (.pfx/.p12)
EXTENSOES_CERTIFICADO = (".pfx", ".p12")
TAMANHO_MAX_CERTIFICADO = 2 * 1024 * 1024  # 2 MB — um .p12 real raramente passa de 300 KB


def _sanitizar_certificado(c: dict) -> dict:
    """Remove tudo que não pode sair pela API: senha decifrada e caminho em disco."""
    d = dict(c)
    d.pop("password", None)
    d.pop("path", None)
    d.pop("filename", None)
    return d


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
    """Retorna todos os certificados digitais A1 cadastrados para visualização de validades.

    Nunca devolve a senha decifrada nem o caminho do arquivo em disco.
    """
    return [_sanitizar_certificado(c) for c in list_all_certificates()]


@router.post("/certificado/upload", response_model=CertificadoResponse)
async def upload_certificate(file: UploadFile = File(...), password: str = Form("")):
    if not password:
        raise HTTPException(status_code=400, detail="Senha do certificado obrigatória")

    filename = file.filename or "certificado.pfx"
    extensao = os.path.splitext(filename)[1].lower()
    if extensao not in EXTENSOES_CERTIFICADO:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo inválido: envie um certificado { ' ou '.join(EXTENSOES_CERTIFICADO) }.",
        )

    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo enviado.")
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(content) > TAMANHO_MAX_CERTIFICADO:
        raise HTTPException(status_code=413, detail="Certificado acima do limite de 2 MB.")

    try:
        res = save_certificate(content, password, filename=filename)
        info = get_cert_info(res.get("cnpj"))
        if not info.get("loaded"):
            return CertificadoResponse(loaded=False, filename=filename, error=info.get("error", "Certificado inválido ou senha incorreta"))
        return CertificadoResponse(filename=filename, **info)
    except ValueError as e:
        # Erro de negócio (senha errada, CNPJ inválido): devolve a mensagem.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Nunca expor exceção interna (caminho, stack, tipo de erro).
        import logging
        logging.getLogger("nfe.cert").exception("Falha ao importar certificado %s", filename)
        raise HTTPException(status_code=500, detail="Falha ao importar o certificado. Verifique o arquivo e a senha.")


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
async def delete_single_certificate(cnpj: str, request: Request, session: dict = Depends(require_admin)):
    """Exclui um certificado específico pelo CNPJ. Restrito ao perfil admin."""
    ok = delete_cert_service(cnpj)
    if not ok:
        raise HTTPException(status_code=404, detail="Certificado não encontrado")
    from backend.services.audit_service import record_audit
    record_audit("EXCLUSAO_CERTIFICADO", "CERTIFICADO", cnpj, detalhe=f"Certificado da empresa {cnpj} excluído", request=request, usuario_email=session.get("email"), usuario_nome=session.get("nome"))
    return {"status": "ok", "message": f"Certificado {cnpj} excluído com sucesso"}


@router.delete("/certificado")
async def delete_all_certificates(request: Request, session: dict = Depends(require_admin)):
    """Exclui TODOS os certificados. Restrito ao perfil admin (ação irreversível)."""
    certs = list_all_certificates()
    for c in certs:
        delete_cert_service(c["cnpj"])
    from backend.services.audit_service import record_audit
    record_audit("EXCLUSAO_TODOS_CERTIFICADOS", "CERTIFICADO", "TODOS", detalhe=f"{len(certs)} certificados excluídos", request=request, usuario_email=session.get("email"), usuario_nome=session.get("nome"))
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


@router.post("/certificado/sync-empresa-fiscal")
async def sync_empresa_fiscal_endpoint(payload: dict):
    """Sincroniza dados fiscais de empresa recebidos via Firestore sem retransmitir."""
    from backend.database import update_certificate_fiscal_data
    cnpj = str(payload.get("cnpj") or "").strip()
    if not cnpj:
        raise HTTPException(status_code=400, detail="CNPJ é obrigatório")
    ok = update_certificate_fiscal_data(cnpj, payload, sync_remote=False)
    return {"success": True, "updated": ok}

