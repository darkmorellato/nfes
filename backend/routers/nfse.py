from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.pynfe_service import (
    status_nfse,
    consultar_nfse_numero,
    consultar_nfse_rps,
)
from backend.config import settings

router = APIRouter()


class ConsultaNFSeRequest(BaseModel):
    numero: str
    autorizador: str = "GINFES"
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class ConsultaRPSRequest(BaseModel):
    rps_numero: str
    autorizador: str = "GINFES"
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


@router.get("/status")
async def status_servico_nfse(autorizador: str = "GINFES", homologacao: Optional[bool] = None):
    try:
        result = status_nfse(autorizador=autorizador, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consulta/numero")
async def consulta_nfse_numero_endpoint(numero: str, autorizador: str = "GINFES", homologacao: Optional[bool] = None):
    try:
        result = consultar_nfse_numero(numero=numero, autorizador=autorizador, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consulta/rps")
async def consulta_nfse_rps_endpoint(rps_numero: str, autorizador: str = "GINFES", homologacao: Optional[bool] = None):
    try:
        result = consultar_nfse_rps(rps_numero=rps_numero, autorizador=autorizador, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
