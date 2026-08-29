from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.pynfe_service import (
    status_mdfe,
    consultar_mdfe,
    autorizar_mdfe,
    cancelar_mdfe,
    encerrar_mdfe,
)
from backend.config import settings

router = APIRouter()


class AutorizacaoMDFeRequest(BaseModel):
    xml: str
    id_lote: int = 1
    ind_sinc: int = 1
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class EventoMDFeRequest(BaseModel):
    xml_evento: str
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


@router.get("/status")
async def status_servico_mdfe(uf: Optional[str] = None, homologacao: Optional[bool] = None):
    try:
        result = status_mdfe(uf=uf, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consulta")
async def consulta_mdfe_endpoint(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None):
    try:
        result = consultar_mdfe(chave=chave, uf=uf, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autorizar")
async def autorizar_mdfe_endpoint(req: AutorizacaoMDFeRequest):
    try:
        result = autorizar_mdfe(
            xml=req.xml,
            id_lote=req.id_lote,
            ind_sinc=req.ind_sinc,
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancelar")
async def cancelar_mdfe_endpoint(req: EventoMDFeRequest):
    try:
        result = cancelar_mdfe(
            xml_evento=req.xml_evento,
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/encerrar")
async def encerrar_mdfe_endpoint(req: EventoMDFeRequest):
    try:
        result = encerrar_mdfe(
            xml_evento=req.xml_evento,
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
