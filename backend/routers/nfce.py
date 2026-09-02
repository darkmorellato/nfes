from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from backend.services.pynfe_service import (
    autorizar_nfce,
    consultar_nota_nfce,
    cancelar_nota_nfce,
)
from backend.config import settings
from backend.dependencies import require_session

router = APIRouter(dependencies=[Depends(require_session)])


class AutorizacaoNFCeRequest(BaseModel):
    xml: str
    id_lote: int = 1
    ind_sinc: int = 1
    contingencia: bool = False
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class EventoNFCeRequest(BaseModel):
    xml_evento: Optional[str] = None
    id_lote: int = 1
    chave: Optional[str] = None
    cnpj: Optional[str] = None
    nProt: Optional[str] = None
    protocolo: Optional[str] = None
    justificativa: Optional[str] = None
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


@router.post("/autorizar")
async def autorizar_nfce_endpoint(req: AutorizacaoNFCeRequest):
    try:
        result = autorizar_nfce(
            xml=req.xml,
            id_lote=req.id_lote,
            ind_sinc=req.ind_sinc,
            contingencia=req.contingencia,
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consulta")
async def consulta_nfce(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None):
    try:
        result = consultar_nota_nfce(chave=chave, uf=uf, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancelar")
async def cancelar_nfce_endpoint(req: EventoNFCeRequest):
    try:
        from backend.services.pynfe_service import cancelar_nota
        result = cancelar_nota(
            xml_evento=req.xml_evento,
            id_lote=req.id_lote,
            modelo="nfce",
            chave=req.chave,
            cnpj=req.cnpj,
            n_prot=req.nProt or req.protocolo,
            justificativa=req.justificativa or "",
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emitir-pdv")
async def emitir_nfce_pdv_endpoint(payload: dict):
    """Emite uma NFC-e de balcão diretamente do PDV com QR Code e baixa de estoque."""
    from backend.services.nfce_service import emitir_nfce_pdv
    try:
        res = emitir_nfce_pdv(payload)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
