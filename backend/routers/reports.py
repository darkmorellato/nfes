from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import matplotlib
matplotlib.use('Agg')
from datetime import datetime
from backend.dependencies import require_session

from backend.services.report_service import (
    generate_invoice_status_report,
    generate_monthly_volume_report,
    generate_compliance_report,
    generate_emitter_report,
)

router = APIRouter(dependencies=[Depends(require_session)])


@router.get("/fiscal/status")
async def report_fiscal_status(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = Query(30, ge=1, le=365)
):
    try:
        pdf_buffer = generate_invoice_status_report(
            uf=uf, homologacao=homologacao, periodo_dias=periodo_dias
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=relatorio_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fiscal/volume-mensal")
async def report_monthly_volume(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    meses: int = Query(6, ge=1, le=24)
):
    try:
        pdf_buffer = generate_monthly_volume_report(
            uf=uf, homologacao=homologacao, meses=meses
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=relatorio_volume_mensal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fiscal/compliance")
async def report_compliance(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = Query(30, ge=1, le=365)
):
    try:
        pdf_buffer = generate_compliance_report(
            uf=uf, homologacao=homologacao, periodo_dias=periodo_dias
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=relatorio_compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fiscal/emissores")
async def report_emitters(
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    periodo_dias: int = Query(30, ge=1, le=365)
):
    try:
        pdf_buffer = generate_emitter_report(
            uf=uf, homologacao=homologacao, periodo_dias=periodo_dias
        )
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=relatorio_emissores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
