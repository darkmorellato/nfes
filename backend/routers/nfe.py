import logging
from fastapi import APIRouter, HTTPException, Query, Body, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

logger = logging.getLogger("nfe.router")

from backend.services.pynfe_service import (
    autorizar_nfe,
    consultar_nota,
    consultar_recibo,
    cancelar_nota,
    carta_correcao,
    inutilizar_numeracao,
    manifestacao_destinatario,
)
from backend.services.nfe_emissao_service import (
    cancelar_nfe_profissional,
    emitir_carta_correcao_nfe,
    inutilizar_numeracao_nfe,
)
from backend.database import get_nfe_detail
from backend.config import settings
from backend.dependencies import require_session

router = APIRouter(dependencies=[Depends(require_session)])


class AutorizacaoRequest(BaseModel):
    xml: str
    id_lote: int = 1
    ind_sinc: int = 1
    contingencia: bool = False
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class ConsultaReciboRequest(BaseModel):
    numero: str
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class EventoRequest(BaseModel):
    xml_evento: Optional[str] = None
    id_lote: int = 1
    chave: Optional[str] = None
    cnpj: Optional[str] = None
    nProt: Optional[str] = None
    protocolo: Optional[str] = None
    justificativa: Optional[str] = None
    texto: Optional[str] = None
    nSeqEvento: Optional[int] = None   # None = sequência automática por chave (1..20)
    modelo: str = "nfe"
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class InutilizacaoRequest(BaseModel):
    cnpj: str
    numero_inicial: int
    numero_final: int
    justificativa: str = ""
    serie: str = "1"
    ano: Optional[int] = None
    modelo: str = "nfe"
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


class ManifestacaoRequest(BaseModel):
    chave: str
    cnpj: str
    tipo_manifestacao: str
    justificativa: str = ""
    uf: Optional[str] = None
    homologacao: Optional[bool] = None


@router.post("/autorizar")
async def autorizar(req: AutorizacaoRequest):
    try:
        result = autorizar_nfe(
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
async def consulta_nfe(chave: str, uf: Optional[str] = None, homologacao: Optional[bool] = None):
    try:
        result = consultar_nota(chave=chave, uf=uf, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recibo")
async def consulta_recibo(numero: str, uf: Optional[str] = None, homologacao: Optional[bool] = None):
    try:
        result = consultar_recibo(numero=numero, uf=uf, homologacao=homologacao)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancelar")
async def cancelar(req: EventoRequest):
    """
    Cancela uma NF-e (Evento 110111).

    Quando a nota existe localmente, delega ao fluxo profissional — que valida,
    transmite e **só grava no banco após cStat 135/136**. Sem nota local (uso
    avançado), mantém o envio cru do evento construído pelo cliente.
    """
    chave_clean = "".join(c for c in str(req.chave or "") if c.isdigit())
    if len(chave_clean) == 44 and not req.xml_evento and get_nfe_detail(chave_clean):
        try:
            res = cancelar_nfe_profissional(
                chave=chave_clean,
                justificativa=req.justificativa or "",
                protocolo=req.nProt or req.protocolo,
                homologacao=req.homologacao,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not res.get("success"):
            raise HTTPException(
                status_code=400,
                detail=res.get("motivo") or "A SEFAZ não homologou o cancelamento.",
            )
        return res

    try:
        result = cancelar_nota(
            xml_evento=req.xml_evento,
            id_lote=req.id_lote,
            modelo=req.modelo or "nfe",
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


@router.post("/carta-correcao")
async def cc(req: EventoRequest):
    """Carta de Correção (Evento 110110) — ver nota de ``/cancelar``."""
    chave_clean = "".join(c for c in str(req.chave or "") if c.isdigit())
    if len(chave_clean) == 44 and not req.xml_evento and get_nfe_detail(chave_clean):
        try:
            res = emitir_carta_correcao_nfe(
                chave=chave_clean,
                texto_correcao=req.texto or "",
                seq_evento=req.nSeqEvento,
                homologacao=req.homologacao,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not res.get("success"):
            raise HTTPException(
                status_code=400,
                detail=res.get("motivo") or "A SEFAZ não homologou a Carta de Correção.",
            )
        return res

    try:
        result = carta_correcao(
            xml_evento=req.xml_evento,
            id_lote=req.id_lote,
            modelo=req.modelo or "nfe",
            chave=req.chave,
            cnpj=req.cnpj,
            texto=req.texto,
            n_seq_evento=req.nSeqEvento or 1,
            uf=req.uf,
            homologacao=req.homologacao,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inutilizar")
async def inutilizar(req: InutilizacaoRequest):
    """
    Inutiliza faixa de numeração (serviço 404/405).

    Delega ao fluxo profissional: valida a faixa contra as notas locais,
    transmite e só registra após confirmação da SEFAZ.
    """
    try:
        return inutilizar_numeracao_nfe(
            empresa_cnpj=req.cnpj,
            serie=req.serie,
            numero_inicial=req.numero_inicial,
            numero_final=req.numero_final,
            justificativa=req.justificativa,
            modelo="55" if (req.modelo or "nfe") in ("nfe", "55") else "65",
            homologacao=req.homologacao,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[INUTILIZACAO] Erro inesperado")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manifestacao")
async def manifestacao(req: ManifestacaoRequest, request: Request):
    try:
        result = manifestacao_destinatario(
            chave=req.chave,
            cnpj=req.cnpj,
            tipo_manifestacao=req.tipo_manifestacao,
            justificativa=req.justificativa,
            uf=req.uf,
            homologacao=req.homologacao,
        )

        from backend.services.audit_service import record_audit
        desc_map = {
            "210200": "Confirmacao da Operacao",
            "210210": "Ciencia da Operacao",
            "210220": "Desconhecimento da Operacao",
            "210240": "Operacao nao Realizada",
        }
        record_audit(
            "MANIFESTACAO",
            "NFE",
            req.chave,
            detalhe=f"Tipo {req.tipo_manifestacao} ({desc_map.get(req.tipo_manifestacao, '')}) - cStat {result.get('c_stat')}: {result.get('motivo')}",
            status="SUCESSO" if (result.get("success") or result.get("c_stat") in ("135", "136", "573")) else "FALHA",
            request=request,
        )

        # Se manifestação teve sucesso ou duplicidade (já homologada), tenta obter o XML completo imediatamente
        if result.get("success") or result.get("c_stat") in ("135", "136", "573"):
            try:
                import time
                from backend.services.danfe_service import parse_distribuicao_xml, parse_nfe_xml
                from backend.database import get_certificate_record, list_certificates_db, save_nfe_doc
                from pynfe.processamento.comunicacao import ComunicacaoSefaz

                clean_cnpj = "".join(c for c in str(req.cnpj) if c.isdigit())
                clean_chave = "".join(c for c in str(req.chave) if c.isdigit())
                cert_rec = get_certificate_record(clean_cnpj) or (list_certificates_db()[0] if list_certificates_db() else None)
                if cert_rec:
                    time.sleep(0.5)
                    uf = (req.uf or "SP").upper()
                    homolog = req.homologacao if req.homologacao is not None else settings.HOMOLOGACAO
                    con = ComunicacaoSefaz(uf, cert_rec["path"], cert_rec["password"], homologacao=homolog)
                    dl_resp = con.consulta_distribuicao(cnpj=clean_cnpj, chave=clean_chave)
                    if dl_resp.status_code == 200:
                        parsed = parse_distribuicao_xml(dl_resp.text)
                        for d in parsed.get("documentos", []):
                            if d.get("tag") in ("nfeProc", "NFe") and d.get("xml_raw"):
                                dados = parse_nfe_xml(d["xml_raw"].encode("utf-8"))
                                dados["empresa_cnpj"] = clean_cnpj
                                save_nfe_doc(dados, xml_raw=d["xml_raw"], empresa_cnpj=clean_cnpj)
                                result["xml_completo_baixado"] = True
                                break
            except Exception as dl_err:
                logger.debug(f"Erro ao baixar XML pós-manifestação: {dl_err}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emitir/rapido")
async def emitir_nfe_rapido(payload: dict):
    """Endpoint legado de simulação — REMOVIDO por integridade fiscal.

    Este recurso devolvia ``cStat 100`` e um "protocolo" inventados sem
    montar XML, assinar com o Certificado A1 nem transmitir à SEFAZ, o que
    gerava notas aparentemente autorizadas sem validade fiscal.

    Use ``POST /api/emissao/nfe/emitir`` — a emissão profissional real.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Endpoint descontinuado: ele apenas simulava a autorização. "
            "Transmita a NF-e por POST /api/emissao/nfe/emitir."
        ),
    )


# ====================================================================
# DACCE (DOCUMENTO AUXILIAR DA CARTA DE CORREÇÃO ELETRÔNICA)
# ====================================================================

@router.get("/cce/dacce/{chave}")
async def imprimir_dacce_pdf(chave: str, n_seq: int = Query(1, ge=1)):
    """Gera o Documento Auxiliar da Carta de Correção Eletrônica (DACCE) oficial em PDF."""
    from backend.services.cce_service import generate_dacce_pdf
    from fastapi.responses import StreamingResponse
    try:
        pdf_buf = generate_dacce_pdf(chave=chave, n_seq=n_seq)
        return StreamingResponse(
            pdf_buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=DACCE_{chave}_{n_seq}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar DACCE: {str(e)}")


# ====================================================================
# INUTILIZAÇÃO DE NUMERAÇÃO DE NF-e / NFC-e
# ====================================================================

@router.post("/inutilizacao/salvar")
async def salvar_inutilizacao_endpoint(payload: dict = Body(...)):
    """Registra o protocolo de inutilização de faixa homologada na SEFAZ."""
    from backend.database import save_inutilizacao
    try:
        res = save_inutilizacao(payload)
        return {"success": True, "data": res, "message": "Inutilização de numeração registrada com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inutilizacao/listar")
async def listar_inutilizacoes_endpoint(empresa_cnpj: Optional[str] = Query(None)):
    """Lista as numerações inutilizadas homologadas na SEFAZ."""
    from backend.database import list_inutilizacoes
    return {"success": True, "inutilizacoes": list_inutilizacoes(empresa_cnpj=empresa_cnpj)}
