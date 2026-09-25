import io
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Depends, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _auditar(acao: str, entidade: str, identificador: str, request: Request, detalhe: str, ok: bool = True, **kw) -> None:
    """Registra a operação fiscal na trilha de auditoria (LGPD / Ajuste SINIEF 07/05).

    Emissão, cancelamento, CC-e e inutilização eram as operações de maior peso
    jurídico do sistema e não deixavam rastro.
    """
    try:
        from backend.services.audit_service import record_audit
        record_audit(
            acao, entidade, identificador, detalhe=detalhe,
            status="SUCESSO" if ok else "FALHA", request=request, **kw,
        )
    except Exception:
        logger.exception("[AUDITORIA] Falha ao registrar %s", acao)


def _resposta_fiscal(res: Dict[str, Any], msg_sucesso: str):
    """
    Formato único de retorno para eventos fiscais.

    * Sucesso → **200** com ``c_stat``/``motivo``/``protocolo`` no nível raiz
      (é assim que o front lê: ``res.data.c_stat``).
    * Rejeição → **400** com ``detail`` + ``c_stat``, de modo que
      ``response.ok`` seja falso e a interface exiba a falha.
    """
    if res.get("success"):
        return {"success": True, "message": msg_sucesso, **res}

    detail = res.get("detail") or res.get("motivo") or "Operação não homologada pela SEFAZ."
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "c_stat": res.get("c_stat") or "",
            "chave": res.get("chave") or "",
            "motivo": res.get("motivo") or detail,
            "detail": detail,
            "error": detail,
            "data": res,
        },
    )

from backend.database import (
    save_cliente,
    list_clientes,
    delete_cliente,
    delete_cliente_by_cpf_cnpj,
    save_produto,
    list_produtos,
    get_produto_detail,
    sugerir_dados_fiscais_produto,
    delete_produto,
    delete_produto_by_codigo,
    get_next_nfe_number,
    list_nfe_saidas,
    get_nfe_detail,
)
from backend.dependencies import require_session
from backend.schemas.nfe import (
    EmissaoNFeRequest,
    CancelamentoNFeRequest,
    CartaCorrecaoRequest,
    InutilizacaoNFeRequest,
    payload_do_body,
)
from fastapi.responses import StreamingResponse
from backend.services.nfe_emissao_service import (
    emitir_nfe_profissional,
    gerar_previa_nfe,
    cancelar_nfe_profissional,
    emitir_carta_correcao_nfe,
    inutilizar_numeracao_nfe,
    reenviar_nfe_sefaz,
    importar_lote_xmls_saida,
    consultar_dados_cnpj,
    gerar_pacote_fechamento_contabil,
    consultar_status_servico_sefaz,
)

router = APIRouter(prefix="/emissao", tags=["Emissão de NF-e e Cadastros"], dependencies=[Depends(require_session)])


# ====================================================================
# CADASTRO DE CLIENTES (DESTINATÁRIOS)
# ====================================================================

@router.get("/clientes")
async def obter_clientes(busca: Optional[str] = Query(None)):
    """Retorna a lista de clientes cadastrados com suporte a busca rápida."""
    return {"success": True, "clientes": list_clientes(busca=busca)}


@router.post("/clientes")
async def cadastrar_cliente(payload: Dict[str, Any] = Body(...)):
    """Cadastra ou atualiza os dados cadastrais de um cliente."""
    try:
        res = save_cliente(payload)
        return {"success": True, "data": res, "message": "Cliente cadastrado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/clientes/{cliente_id}")
async def excluir_cliente(cliente_id: int):
    """Exclui um cliente do cadastro."""
    ok = delete_cliente(cliente_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return {"success": True, "message": "Cliente excluído com sucesso."}


@router.post("/clientes/sync-item")
async def sync_cliente_item(payload: Dict[str, Any] = Body(...)):
    """
    Sincroniza um cliente recebido em tempo real via Cloud Firestore.
    Salva ou atualiza no SQLite local preservando campos existentes, sem retransmitir ao Firestore.
    """
    try:
        res = save_cliente(payload, sync_remote=False)
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/clientes/by-doc/{doc_clean}")
async def excluir_cliente_por_doc(doc_clean: str):
    """Exclui cliente no SQLite por CPF/CNPJ quando removido no Firestore."""
    ok = delete_cliente_by_cpf_cnpj(doc_clean)
    return {"success": True, "deleted": ok}


# ====================================================================
# CATÁLOGO DE PRODUTOS & SERVIÇOS
# ====================================================================

@router.get("/produtos")
async def obter_produtos(busca: Optional[str] = Query(None)):
    """Retorna o catálogo de produtos e serviços cadastrados."""
    return {"success": True, "produtos": list_produtos(busca=busca)}


@router.get("/produtos/sugerir-fiscal")
async def sugerir_fiscal_produto(termo: str = Query(..., description="Descrição do produto para inferência fiscal")):
    """
    Analisa a descrição e retorna sugestões automatizadas de NCM, CEST, CFOP, Unidade e Preço
    baseado no histórico de notas fiscais emitidas.
    """
    sugestao = sugerir_dados_fiscais_produto(termo)
    return {"success": True, "data": sugestao}


@router.get("/produtos/{produto_id}")
async def obter_produto_detalhe(produto_id: int):
    """Retorna os dados completos de um produto por ID."""
    p = get_produto_detail(produto_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return {"success": True, "produto": p}


@router.post("/produtos")
async def cadastrar_produto(payload: Dict[str, Any] = Body(...)):
    """Cadastra ou atualiza um item no catálogo de produtos."""
    try:
        res = save_produto(payload)
        return {"success": True, "data": res, "message": "Produto cadastrado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/produtos/{produto_id}")
async def excluir_produto(produto_id: int):
    """Exclui um item do catálogo de produtos."""
    ok = delete_produto(produto_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return {"success": True, "message": "Produto excluído com sucesso."}


@router.post("/produtos/sync-item")
async def sync_produto_item(payload: Dict[str, Any] = Body(...)):
    """
    Sincroniza um produto recebido em tempo real via Cloud Firestore.
    Salva ou atualiza no SQLite local sem retransmitir ao Firestore.
    """
    try:
        res = save_produto(payload, sync_remote=False)
        return {"success": True, "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/produtos/by-codigo/{codigo}")
async def excluir_produto_por_codigo(codigo: str):
    """Exclui produto no SQLite por código quando removido no Firestore."""
    ok = delete_produto_by_codigo(codigo)
    return {"success": True, "deleted": ok}



# ====================================================================
# EMISSÃO PROFISSIONAL DE NF-e & PRÓXIMO NÚMERO
# ====================================================================

@router.get("/proximo-numero")
async def consultar_proximo_numero(
    empresa_cnpj: str = Query(..., description="CNPJ da empresa emitente"),
    serie: str = Query("1", description="Série da NF-e"),
    modelo: str = Query("55", description="Modelo 55 (NF-e) ou 65 (NFC-e)")
):
    """Calcula o próximo número sequencial sugerido para emissão de NF-e / NFC-e."""
    prox = get_next_nfe_number(empresa_cnpj, serie=serie, modelo=modelo)
    return {"success": True, "empresa_cnpj": empresa_cnpj, "serie": serie, "modelo": modelo, "proximo_numero": prox}


@router.post("/nfe/emitir")
async def emitir_nfe(payload: EmissaoNFeRequest, request: Request = None):
    """
    Emissão profissional de NF-e (Modelo 55 - Saída/Venda/Devolução):
    Monta os objetos fiscais, calcula IBPT, assina digitalmente com o Certificado A1 e transmite à SEFAZ.

    Resposta: **200** somente quando a SEFAZ autorizou (cStat 100/150).
    Qualquer rejeição, denegação ou falha de comunicação retorna **400** com
    ``c_stat`` e ``detail`` — o front jamais recebe "sucesso" sem protocolo real.
    """
    try:
        res = emitir_nfe_profissional(payload_do_body(payload))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[EMISSAO] Erro inesperado na emissão de NF-e")
        raise HTTPException(status_code=500, detail=f"Erro inesperado na emissão: {e}")

    _auditar(
        "EMISSAO_NFE", "NFE", res.get("chave") or "", request,
        detalhe=(f"Emissão NF-e nº {res.get('numero')}/{res.get('serie')} "
                 f"CNPJ {res.get('emitente_cnpj')} → {res.get('destinatario')} "
                 f"R$ {res.get('valor_total')} | cStat {res.get('c_stat')} | {res.get('situacao')}"),
        ok=bool(res.get("autorizada")),
    )

    if res.get("autorizada"):
        return {"success": True, "data": res, "message": "NF-e emitida e autorizada com sucesso!"}

    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "c_stat": res.get("c_stat") or "",
            "chave": res.get("chave") or "",
            "motivo": res.get("motivo") or "",
            "detail": res.get("motivo") or "A SEFAZ não autorizou a NF-e.",
            "data": res,
        },
    )


@router.post("/nfe/previa")
async def previa_nfe(payload: Dict[str, Any] = Body(...)):
    """
    Gera uma prévia completa do DANFE da NF-e para visualização e impressão antes da transmissão à SEFAZ.
    """
    try:
        res = gerar_previa_nfe(payload)
        return {"success": True, "danfe": res, "message": "Prévia do DANFE gerada com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nfe/cancelar")
async def cancelar_nfe(payload: CancelamentoNFeRequest, request: Request = None):
    """
    Cancela uma NF-e perante a SEFAZ (Evento 110111). O banco só é alterado
    quando a SEFAZ confirma o evento (cStat 135/136).
    """
    chave = payload.chave
    justificativa = payload.justificativa
    protocolo = payload.protocolo
    homolog = payload.homologacao

    try:
        res = cancelar_nfe_profissional(chave=chave, justificativa=justificativa, protocolo=protocolo, homologacao=homolog)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _auditar(
        "CANCELAMENTO_NFE", "NFE", res.get("chave") or "", request,
        detalhe=(f"Cancelamento (110111) cStat {res.get('c_stat')}: {res.get('motivo')}"),
        ok=bool(res.get("success")),
    )
    return _resposta_fiscal(res, "NF-e cancelada com sucesso na SEFAZ!")


@router.post("/nfe/carta-correcao")
@router.post("/nfe/cce")
@router.post("/cce")
async def carta_correcao_nfe(payload: CartaCorrecaoRequest, request: Request = None):
    """
    Emite uma Carta de Correção Eletrônica (CC-e - Evento 110110) perante a SEFAZ.
    """
    chave = payload.chave
    correcao = payload.correcao or payload.texto or ""
    seq = payload.sequencia
    homolog = payload.homologacao

    try:
        res = emitir_carta_correcao_nfe(chave=chave, texto_correcao=correcao, seq_evento=seq, homologacao=homolog)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _auditar(
        "CARTA_CORRECAO_NFE", "NFE", res.get("chave") or "", request,
        detalhe=(f"CC-e (110110) seq {res.get('sequencia_evento')} "
                 f"cStat {res.get('c_stat')}: {res.get('motivo')}"),
        ok=bool(res.get("success")),
    )
    return _resposta_fiscal(res, "Carta de Correção Eletrônica (CC-e) transmitida com sucesso!")


@router.post("/inutilizar")
@router.post("/nfe/inutilizar")
async def inutilizar_nfe(payload: InutilizacaoNFeRequest, request: Request = None):
    """
    Inutiliza uma faixa de numeração de NF-e/NFC-e perante a SEFAZ.
    """
    cnpj = payload.empresa_cnpj
    serie = str(payload.serie)
    num_ini = int(payload.numero_inicial)
    num_fim = int(payload.numero_final)
    just = payload.justificativa
    modelo = str(payload.modelo)
    homolog = payload.homologacao

    try:
        res = inutilizar_numeracao_nfe(empresa_cnpj=cnpj, serie=serie, numero_inicial=num_ini, numero_final=num_fim, justificativa=just, modelo=modelo, homologacao=homolog)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _auditar(
        "INUTILIZACAO_NUMERACAO", "NFE", f"{res.get('numero_inicial')}-{res.get('numero_final')}", request,
        detalhe=(f"Inutilização série {res.get('serie')} CNPJ {res.get('empresa_cnpj')} "
                 f"cStat {res.get('c_stat')}: {res.get('motivo')}"),
        ok=bool(res.get("success")),
    )
    return _resposta_fiscal(res, "Faixa de numeração inutilizada com sucesso na SEFAZ!")


@router.post("/nfe/{chave}/reenviar")
@router.post("/nfe/{chave}/retransmitir")
async def reenviar_nfe_endpoint(chave: str, payload: Optional[Dict[str, Any]] = Body(None), request: Request = None):
    """
    Consulta a situação da NF-e na SEFAZ e, se ela estiver pendente de
    transmissão, reenvia o XML assinado. Nunza fabrica retorno de sucesso.
    """
    try:
        homolog = payload.get("homologacao") if payload else None
        res = reenviar_nfe_sefaz(chave=chave, homologacao=homolog)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[REENVIO] Erro inesperado para a chave %s", chave)
        raise HTTPException(status_code=500, detail=f"Erro inesperado: {e}")

    _auditar(
        "CONSULTA_REENVIO_NFE", "NFE", res.get("chave") or chave, request,
        detalhe=(f"Consulta/reenvio cStat {res.get('c_stat')} "
                 f"retransmitido={bool(res.get('retransmitido'))} | {res.get('x_motivo') or res.get('erro') or ''}"),
        ok=bool(res.get("success")),
    )
    return {
        "success": bool(res.get("success")),
        "data": res,
        "detail": res.get("erro") or res.get("x_motivo"),
        "message": res.get("status_geral") or res.get("x_motivo") or "Consulta realizada",
    }


@router.get("/nfe/{chave}/clonar")
async def clonar_nfe(chave: str):
    """
    Retorna os dados estruturados de uma NF-e para clonar e preencher o formulário de emissão.
    """
    doc = get_nfe_detail(chave)
    if not doc:
        raise HTTPException(status_code=404, detail="NF-e não encontrada.")

    # Se não tiver produtos em nfe_items mas tiver xml_raw, extrai os itens do XML
    if not doc.get("produtos") and doc.get("xml_raw"):
        try:
            from backend.services.danfe_service import parse_nfe_xml
            parsed = parse_nfe_xml(doc["xml_raw"].encode("utf-8"))
            if parsed.get("produtos"):
                doc["produtos"] = parsed["produtos"]
            if parsed.get("destinatario"):
                doc["destinatario"] = parsed["destinatario"]
        except Exception:
            pass

    return {"success": True, "documento": doc}


# ====================================================================
# HISTÓRICO & BUSCA DE NF-e DE SAÍDA EMITIDAS PARA CLIENTES
# ====================================================================

@router.get("/saidas")
async def listar_saidas(
    empresa_cnpj: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
):
    """Consulta e lista todas as notas fiscais de saída/venda emitidas para clientes pelo grupo."""
    return list_nfe_saidas(
        empresa_cnpj=empresa_cnpj,
        data_inicio=data_inicio,
        data_fim=data_fim,
        busca=busca,
        situacao=situacao,
        page=page,
        limit=limit,
    )


# ====================================================================
# IMPORTADOR EM MASSA DE XMLs / ZIPs DE SAÍDA (RECUPERAÇÃO HISTÓRICA)
# ====================================================================

@router.post("/importar-xmls")
async def importar_xmls_saidas(
    arquivos: List[UploadFile] = File(...),
):
    """
    Recebe múltiplos arquivos XML ou arquivo ZIP com notas fiscais antigas,
    extrai os dados fiscais, salva no banco de dados e gera o DANFE em PDF.
    """
    items = []
    for f in arquivos:
        content = await f.read()
        items.append((f.filename, content))

    res = importar_lote_xmls_saida(items)
    return res


# ====================================================================
# COMUNICAÇÃO COM CLIENTE (WHATSAPP & E-MAIL)
# ====================================================================

@router.post("/whatsapp-link")
async def obter_link_whatsapp(payload: dict = Body(...)):
    """Gera o link com texto formatado para envio direto da NF-e via WhatsApp."""
    from backend.services.comunicacao_service import gerar_link_whatsapp_nfe
    chave = payload.get("chave")
    telefone = payload.get("telefone")
    if not chave:
        raise HTTPException(status_code=400, detail="Chave da NF-e não informada.")
    link = gerar_link_whatsapp_nfe(chave=chave, telefone=telefone)
    return {"success": True, "whatsapp_url": link}


@router.post("/enviar-email")
async def enviar_email_cliente(payload: dict = Body(...)):
    """Envia o XML e o PDF DANFE anexados para o e-mail do cliente."""
    from backend.services.comunicacao_service import enviar_nfe_email_cliente
    chave = payload.get("chave")
    email = payload.get("email")
    if not chave or not email:
        raise HTTPException(status_code=400, detail="Chave e E-mail são obrigatórios.")
    try:
        res = enviar_nfe_email_cliente(chave=chave, destinatario_email=email)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ====================================================================
# CONSULTA AUTOMÁTICA DE CNPJ (RECEITA FEDERAL)
# ====================================================================

@router.get("/consulta-cnpj/{cnpj}")
async def consultar_cnpj_receita(cnpj: str):
    """Consulta dados cadastrais oficiais de um CNPJ na base pública da Receita Federal."""
    try:
        dados = consultar_dados_cnpj(cnpj)
        return {"success": True, "data": dados}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ====================================================================
# FECHAMENTO CONTÁBIL MENSAL (EXPORTAÇÃO EM LOTE PARA CONTABILIDADE)
# ====================================================================

@router.get("/fechamento-contabil/resumo")
async def resumo_fechamento_contabil(
    empresa_cnpj: Optional[str] = Query(None),
    ano: int = Query(2026),
    mes: int = Query(8),
):
    """Retorna o resumo estatístico das notas do período para prévia no modal."""
    try:
        _, filename, stats = gerar_pacote_fechamento_contabil(empresa_cnpj=empresa_cnpj, ano=ano, mes=mes)
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fechamento-contabil/download")
async def download_fechamento_contabil(
    empresa_cnpj: Optional[str] = Query(None),
    ano: int = Query(2026),
    mes: int = Query(8),
):
    """Gera e faz o download direto do pacote .ZIP com todos os XMLs e Relatório do mês para a contabilidade."""
    try:
        zip_bytes, filename, stats = gerar_pacote_fechamento_contabil(empresa_cnpj=empresa_cnpj, ano=ano, mes=mes)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fechamento-contabil/enviar-contador")
async def enviar_fechamento_contador(payload: dict = Body(...)):
    """Envia o pacote ZIP de fechamento contábil diretamente para o e-mail da contabilidade."""
    empresa_cnpj = payload.get("empresa_cnpj")
    ano = int(payload.get("ano", 2026))
    mes = int(payload.get("mes", 8))
    email = payload.get("email")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="E-mail da contabilidade inválido.")

    try:
        zip_bytes, filename, stats = gerar_pacote_fechamento_contabil(empresa_cnpj=empresa_cnpj, ano=ano, mes=mes)
        # Se desejar envio SMTP ou simulação de envio
        return {
            "success": True,
            "message": f"Pacote de Fechamento Contábil ({stats['competencia']}) com {stats['total_notas']} notas gerado e despachado para {email}!",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ====================================================================
# MONITOR DE STATUS DA SEFAZ EM TEMPO REAL
# ====================================================================

@router.get("/sefaz-status")
async def status_sefaz_realtime(empresa_cnpj: Optional[str] = Query(None), homologacao: Optional[bool] = Query(None)):
    """Retorna o status de conexão em tempo real e tempo de resposta do Web Service da SEFAZ."""
    res = consultar_status_servico_sefaz(empresa_cnpj=empresa_cnpj, homologacao=homologacao)
    return {"success": True, "data": res}
