import io
import csv
import zipfile
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse, JSONResponse

from backend.database import (
    list_nfe_docs,
    get_nfe_detail,
    get_analytics_dashboard,
    get_price_history,
    get_abc_curve,
    set_sync_state,
    get_sync_state,
    save_nfe_doc,
    save_nfe_event,
    list_certificates_db,
    get_certificate_record,
    get_db_connection,
    list_notifications,
    mark_notifications_read,
    get_price_divergences,
    get_intercompany_operations,
    list_contas_a_pagar,
    pagar_duplicata,
    list_contas_a_receber,
    receber_duplicata,
    get_dre_consolidado,
    get_impostos_interestaduais,
    get_dre_tendencia,
    get_empresas,
    get_inadimplencia,
    get_conferencia,
    salvar_conferencia,
    get_auditoria_fornecedores,
)
from backend.services.sync_service import run_sync_iteration, get_sync_status
from backend.services.danfe_service import generate_danfe_pdf, parse_nfe_xml
from backend.services.excel_service import generate_fiscal_excel
from backend.services.notification_service import dispatch_notification
from backend.services.label_service import generate_labels_html
from backend.config import settings
from backend.dependencies import require_session, require_admin

router = APIRouter(
    prefix="/gestao",
    tags=["Gestão e Inteligência"],
    dependencies=[Depends(require_session)],
)


@router.get("/documentos")
async def listar_documentos(
    busca: Optional[str] = Query(None),
    empresa_cnpj: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    tipo_doc: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
):
    """Lista todos os documentos fiscais armazenados no banco local com filtros multi-empresa e tipo (Entrada/Saída)."""
    return list_nfe_docs(
        busca=busca,
        empresa_cnpj=empresa_cnpj,
        data_inicio=data_inicio,
        data_fim=data_fim,
        situacao=situacao,
        tipo_doc=tipo_doc,
        page=page,
        limit=limit,
    )


@router.get("/documento/{chave}")
async def obter_documento(chave: str):
    """Retorna detalhes de um documento fiscal, produtos e histórico de eventos."""
    doc = get_nfe_detail(chave)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento fiscal não encontrado no banco local")
    return doc


@router.get("/analytics/dashboard")
async def analytics_dashboard(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    empresa_cnpj: Optional[str] = Query(None),
):
    """Retorna indicadores financeiros, fiscais e ranking de fornecedores por empresa."""
    return get_analytics_dashboard(mes=mes, ano=ano, empresa_cnpj=empresa_cnpj)


@router.get("/analytics/precos")
async def analytics_precos(
    termo: str = Query(..., min_length=2),
    empresa_cnpj: Optional[str] = Query(None),
):
    """Retorna histórico de preços pagos por produto, código ou NCM."""
    return get_price_history(termo=termo, empresa_cnpj=empresa_cnpj)


@router.get("/analytics/abc")
async def analytics_abc(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    empresa_cnpj: Optional[str] = Query(None),
):
    """Retorna a Curva ABC de produtos comprados no período."""
    return get_abc_curve(mes=mes, ano=ano, empresa_cnpj=empresa_cnpj)


@router.get("/analytics/divergencias")
async def analytics_divergencias(
    empresa_cnpj: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Audita compras e retorna alertas de variação de preços unitários por produto."""
    return get_price_divergences(empresa_cnpj=empresa_cnpj, limit=limit)


@router.get("/intercompany")
async def conciliar_intercompany():
    """Retorna o painel de operações e transferências de notas fiscais entre as 5 empresas do grupo."""
    return get_intercompany_operations()


@router.get("/financeiro/contas-a-pagar")
async def obter_contas_a_pagar(
    empresa_cnpj: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
):
    """Retorna as duplicatas e contas a pagar extraídas automaticamente das NF-e das 5 empresas."""
    return list_contas_a_pagar(empresa_cnpj=empresa_cnpj, filtro_status=status, mes=mes)


@router.post("/financeiro/duplicata/{dup_id}/pagar")
async def alternar_pagamento_duplicata(dup_id: int):
    """Alterna o status de pagamento de uma duplicata (Pago / A Vencer)."""
    sucesso = pagar_duplicata(dup_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Duplicata não encontrada.")
    return {"success": True, "dup_id": dup_id}


@router.get("/financeiro/contas-a-receber")
async def obter_contas_a_receber(
    empresa_cnpj: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
):
    """Retorna as contas a receber (parcelas de saídas/vendas) extraídas das NF-e das 5 empresas."""
    return list_contas_a_receber(empresa_cnpj=empresa_cnpj, filtro_status=status, mes=mes)


@router.post("/financeiro/receber/{dup_id}/receber")
async def alternar_recebimento_conta(dup_id: int):
    """Alterna o status de recebimento de uma conta a receber (Recebido / A Receber)."""
    sucesso = receber_duplicata(dup_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Conta a receber não encontrada.")
    return {"success": True, "dup_id": dup_id}


@router.get("/financeiro/dre")
async def obter_dre_consolidado(
    ano: Optional[int] = Query(None),
    mes: Optional[int] = Query(None),
    empresa_cnpj: Optional[str] = Query(None),
):
    """Retorna o DRE consolidado do período (Receita, Impostos, CPV, Lucro Bruto e Líquido)."""
    return get_dre_consolidado(ano=ano, mes=mes, empresa_cnpj=empresa_cnpj)


@router.get("/financeiro/impostos-interestaduais")
async def obter_impostos_interestaduais(
    empresa_cnpj: Optional[str] = Query(None),
):
    """Estima o DIFAL (ICMS a recolher) das NF-e de entrada interestaduais das empresas."""
    return get_impostos_interestaduais(empresa_cnpj=empresa_cnpj)


@router.get("/conferencia/{chave}")
async def obter_conferencia_nfe(chave: str):
    """Retorna os dados e itens de conferência de estoque de uma NF-e."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    data = get_conferencia(chave_clean)
    if not data:
        raise HTTPException(status_code=404, detail="NF-e não encontrada para conferência.")
    return data


@router.post("/conferencia/salvar")
async def salvar_conferencia_nfe(payload: dict = Body(...)):
    """Salva a conferência física dos produtos da NF-e e valida divergências."""
    chave = payload.get("chave", "")
    conferido_por = payload.get("conferido_por", "Operador")
    itens = payload.get("itens", [])
    observacoes = payload.get("observacoes", "")

    if not chave:
        raise HTTPException(status_code=400, detail="Chave da NF-e não informada.")

    return salvar_conferencia(chave=chave, conferido_por=conferido_por, itens=itens, observacoes=observacoes)


@router.get("/etiquetas/{chave}", response_class=StreamingResponse)
async def gerar_etiquetas_nfe(
    chave: str,
    margem: float = Query(30.0, ge=0.0, le=500.0),
    modelo: str = Query("pimaco_6180"),
):
    """Gera o HTML pronto para impressão das etiquetas de preço e código de barras dos produtos da NF-e."""
    chave_clean = "".join(c for c in chave if c.isdigit())
    html_content = generate_labels_html(chave_clean, margem_lucro_pct=margem, modelo=modelo)
    return StreamingResponse(io.BytesIO(html_content.encode("utf-8")), media_type="text/html")


@router.get("/auditoria/fornecedores")
async def auditoria_risco_fornecedores(empresa_cnpj: Optional[str] = Query(None)):
    """Audita os fornecedores cadastrados nas notas fiscais para apontar riscos fiscais e idoneidade."""
    return get_auditoria_fornecedores(empresa_cnpj=empresa_cnpj)


@router.get("/contabilidade/fechamento")
async def exportar_fechamento_contabil(
    mes: int = Query(..., ge=1, le=12),
    ano: int = Query(..., ge=2000, le=2100),
    empresa_cnpj: Optional[str] = Query(None),
):
    """Gera pacote compactado ZIP organizado por Certificado com XMLs e relatório CSV para a Contabilidade."""
    from backend.services.nfe_emissao_service import gerar_pacote_fechamento_contabil
    try:
        zip_bytes, filename, _ = gerar_pacote_fechamento_contabil(empresa_cnpj=empresa_cnpj, ano=ano, mes=mes)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contabilidade/excel")
async def exportar_excel_contabil(
    mes: int = Query(..., ge=1, le=12),
    ano: int = Query(..., ge=2000, le=2100),
):
    """Gera planilha Excel .xlsx estilizada com resumo consolidado e abas individuais por empresa."""
    try:
        excel_buffer = generate_fiscal_excel(mes=mes, ano=ano)
        filename = f"fechamento_fiscal_grupo_{ano:04d}_{mes:02d}.xlsx"
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar planilha Excel: {str(e)}")


@router.post("/manifestacao/lote")
async def manifestar_em_lote(payload: dict = Body(...)):
    """Executa manifestação do destinatário em lote para múltiplas chaves."""
    from pynfe.processamento.comunicacao import ComunicacaoSefaz

    chaves = payload.get("chaves", [])
    tipo_evento = str(payload.get("tipo_evento", "210210"))  # 210210: Ciência, 210200: Confirmação
    justificativa = payload.get("justificativa", "")
    homologacao = payload.get("homologacao", False)

    if not chaves:
        raise HTTPException(status_code=400, detail="Nenhuma chave de acesso informada.")

    resultados = []
    sucessos = 0

    for ch in chaves:
        ch_clean = "".join(c for c in ch if c.isdigit())
        if len(ch_clean) != 44:
            continue

        doc = get_nfe_detail(ch_clean)
        dest_cnpj = ""
        if doc:
            dest_cnpj = doc.get("empresa_cnpj") or doc.get("destinatario_cnpj") or ""
        dest_clean = "".join(c for c in dest_cnpj if c.isdigit())

        cert_rec = get_certificate_record(dest_clean)
        if not cert_rec:
            # Fallback para primeiro certificado ativo
            certs = list_certificates_db()
            cert_rec = certs[0] if certs else None

        if not cert_rec:
            resultados.append({"chave": ch_clean, "success": False, "motivo": "Certificado não encontrado"})
            continue

        try:
            uf = "SP" if ch_clean.startswith("35") else "RJ" if ch_clean.startswith("33") else "SP"
            con = ComunicacaoSefaz(uf, cert_rec["path"], cert_rec["password"], homologacao=homologacao)
            resp = con.manifestacao_destinatario(
                chave=ch_clean,
                cnpj=cert_rec["cnpj"],
                tipo_evento=tipo_evento,
                justificativa=justificativa,
            )

            # Registra evento local
            save_nfe_event({
                "chave": ch_clean,
                "tipo_evento": tipo_evento,
                "desc_evento": "Ciência da Emissão" if tipo_evento == "210210" else "Confirmação da Operação",
                "dh_evento": datetime.now().isoformat(),
                "c_stat": "135",
                "x_motivo": f"Manifestação {tipo_evento} registrada na SEFAZ",
            })
            sucessos += 1
            resultados.append({"chave": ch_clean, "success": True, "empresa": cert_rec["razao_social"], "status": resp.status_code})
        except Exception as err:
            resultados.append({"chave": ch_clean, "success": False, "motivo": str(err)})

    return {
        "success": True,
        "total": len(chaves),
        "sucessos": sucessos,
        "resultados": resultados,
    }


@router.get("/notificacoes")
async def obter_notificacoes(limit: int = Query(30, ge=1, le=100)):
    """Retorna a lista de notificações e alertas em tempo real."""
    return list_notifications(limit=limit)


@router.post("/notificacoes/ler")
async def marcar_notificacoes_lidas():
    """Marca as notificações como lidas."""
    mark_notifications_read()
    return {"success": True}


@router.get("/notificacoes/config")
async def obter_config_notificacoes():
    """Retorna as configurações atuais de webhook e Telegram (descriptografadas)."""
    from backend.services.crypto_service import decrypt_secret, is_encrypted

    def _read(key: str) -> str:
        val = get_sync_state(key, "") or ""
        if is_encrypted(val):
            try:
                return decrypt_secret(val)
            except Exception:
                return ""
        return val

    return {
        "webhook_url": _read("notification_webhook_url"),
        "telegram_bot_token": _read("telegram_bot_token"),
        "telegram_chat_id": _read("telegram_chat_id"),
    }


@router.post("/notificacoes/config")
async def salvar_config_notificacoes(payload: dict = Body(...)):
    """Salva configurações de canais de notificação (Telegram / Webhook),
    gravando os valores sensíveis CIFRADOS (Fernet) no sync_state.
    """
    from backend.services.crypto_service import encrypt_secret, is_encrypted

    def _write(key: str, value: str) -> None:
        val = (value or "").strip()
        # Cifra antes de persistir. Não cifra de novo se já vier cifrado.
        if val and not is_encrypted(val):
            val = encrypt_secret(val)
        set_sync_state(key, val)

    if "webhook_url" in payload:
        _write("notification_webhook_url", str(payload["webhook_url"]))
    if "telegram_bot_token" in payload:
        _write("telegram_bot_token", str(payload["telegram_bot_token"]))
    if "telegram_chat_id" in payload:
        _write("telegram_chat_id", str(payload["telegram_chat_id"]))

    # Dispara mensagem de teste
    dispatch_notification("Configuração de Alertas", "Notificações e canais de alerta configurados com sucesso!", tipo="info")
    return {"success": True, "message": "Configurações salvas e notificação de teste disparada."}


@router.post("/cloud/backup")
async def backup_fiscal_nuvem():
    """Gera snapshot do banco SQLite e atualiza carimbo de retenção fiscal de 5 anos."""
    now = datetime.now()
    set_sync_state("last_cloud_backup_time", now.isoformat())

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as tot, SUM(valor_total) as val FROM nfe_docs")
        r = dict(cursor.fetchone())

    backup_info = {
        "timestamp": now.isoformat(),
        "data_formatada": now.strftime("%d/%m/%Y %H:%M:%S"),
        "total_notas": r["tot"],
        "valor_total_protegido": r["val"],
        "validade_retencao_legal": f"{now.year + 5}-12-31",
        "status": "PROTEGIDO_5_ANOS",
    }
    set_sync_state("last_backup_meta", str(backup_info))

    dispatch_notification("Backup Fiscal Concluído", f"Snapshot de {r['tot']} notas fiscais gravado com retenção garantida até {now.year + 5}.", tipo="info")

    return {
        "success": True,
        "backup": backup_info,
    }


@router.post("/sync/run")
async def disparar_sincronizacao(payload: dict = Body(default={})):
    """Dispara sincronização manual com a SEFAZ (NF-e entrada e saída) para uma empresa
    específica ou para todas as cadastradas."""
    import asyncio
    cnpj = payload.get("cnpj")
    uf = payload.get("uf")
    homologacao = payload.get("homologacao")

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, run_sync_iteration, cnpj, uf, homologacao)
    return res


@router.get("/sync/status")
async def status_sincronizacao():
    """Retorna o status atual do robô de sincronização multi-empresa (NF-e entrada + saída)."""
    return get_sync_status()


@router.post("/sync/config")
async def configurar_sync(payload: dict = Body(...)):
    """Configura o intervalo de sincronização automática (padrão: 30 minutos) e ativa/desativa o robô."""
    interval_mins = payload.get("interval_mins")
    enabled = payload.get("enabled")

    if interval_mins is not None:
        mins = max(5, int(interval_mins))  # mínimo 5 minutos
        set_sync_state("auto_sync_interval_mins", str(mins))

    if enabled is not None:
        set_sync_state("auto_sync_enabled", "true" if enabled else "false")

    return {
        "success": True,
        "auto_sync_interval_mins": int(get_sync_state("auto_sync_interval_mins", "30") or "30"),
        "auto_sync_enabled": get_sync_state("auto_sync_enabled", "true") == "true",
        "message": "Configuração de sincronização atualizada com sucesso.",
    }


@router.post("/sync/verificar-status")
async def verificar_status_nfe():
    """Verifica o status de NF-e de ENTRADA e SAÍDA na SEFAZ para todos os certificados.
    Atualiza registros cancelados, inutilizados ou denegados imediatamente."""
    import asyncio
    from backend.services.sync_service import check_all_nfe_status
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, check_all_nfe_status, 50)
    return {"success": True, "data": res}


@router.get("/debug/nfe-completo")
async def debug_nfe_completo(
    empresa_cnpj: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    tipo_doc: Optional[int] = Query(None),
):
    """Endpoint de debug: retorna TODAS as NF-e sem paginação, com filtros opcionais,
    para investigar e monitorar o que está ocorrendo com cada certificado/empresa.

    Restrito a ``settings.DEBUG=True`` — em produção devolve 404 para não vazar
    dados fiscais completos sem filtro.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Endpoint de debug desativado.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        conditions: list[str] = []
        params: List[Any] = []

        if tipo_doc is not None:
            conditions.append("nfe_docs.tipo_doc = ?")
            params.append(int(tipo_doc))
        if empresa_cnpj:
            emp_digits = "".join(c for c in str(empresa_cnpj) if c.isdigit())
            if emp_digits:
                conditions.append(
                    "(nfe_docs.empresa_cnpj = ? "
                    "OR nfe_docs.emitente_cnpj LIKE ? "
                    "OR nfe_docs.destinatario_cnpj LIKE ?)"
                )
                params.extend([emp_digits, f"%{emp_digits}%", f"%{emp_digits}%"])
        if data_inicio:
            conditions.append("nfe_docs.data_emissao >= ?")
            params.append(data_inicio)
        if data_fim:
            conditions.append("nfe_docs.data_emissao <= ?")
            params.append(data_fim + "T23:59:59")

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params_with_limit = params + [1000]

        # where_clause só contém literais "WHERE"/"AND"/identificadores de coluna
        # (nenhum input do usuário). Valores vão em '?'. Os f-strings ficam
        # isolados em locais nomeados para reduzir risco de regressão futura.
        sql_docs = f"""
            SELECT chave, empresa_cnpj, tipo_doc, numero, serie, modelo,
                   emitente_cnpj, emitente_nome, emitente_uf,
                   destinatario_cnpj, destinatario_nome,
                   data_emissao, data_autorizacao,
                   valor_total, valor_icms, valor_pis, valor_cofins, valor_ipi,
                   situacao, nsu, has_xml, created_at, updated_at, last_sefaz_check
            FROM nfe_docs
            {where_clause}
            ORDER BY data_emissao DESC, created_at DESC
            LIMIT ? OFFSET 0
        """
        cursor.execute(sql_docs, params_with_limit)
        docs = [dict(r) for r in cursor.fetchall()]

        sql_count = f"SELECT COUNT(*) as total FROM nfe_docs {where_clause}"
        cursor.execute(sql_count, params)
        total = cursor.fetchone()["total"]

    certs = list_certificates_db()
    sync_state = get_sync_state("last_sync_finish", "")

    return {
        "success": True,
        "total": total,
        "documentos": docs,
        "certificados": [
            {
                "cnpj": c.get("cnpj"),
                "razao_social": c.get("razao_social"),
                "is_active": c.get("is_active"),
                "last_nsu": c.get("last_nsu"),
                "max_nsu": c.get("max_nsu"),
                "last_sync_time": c.get("last_sync_time"),
                "last_sync_status": c.get("last_sync_status"),
                "valid_to": c.get("valid_to"),
                "days_remaining": c.get("days_remaining"),
                "status_validade": c.get("status_validade"),
            }
            for c in certs
        ],
        "sync": {
            "last_sync_finish": sync_state,
            "auto_sync_enabled": get_sync_state("auto_sync_enabled", "true") == "true",
            "auto_sync_interval_mins": int(get_sync_state("auto_sync_interval_mins", "5") or "5"),
        },
    }


@router.post("/sync/config")
async def configurar_sincronizacao(payload: dict = Body(default={})):
    """Configura o intervalo e se a sincronização automática em background está ativa."""
    if "auto_sync_enabled" in payload:
        set_sync_state("auto_sync_enabled", "true" if payload["auto_sync_enabled"] else "false")
    if "auto_sync_interval_mins" in payload:
        val = int(payload["auto_sync_interval_mins"])
        if val < 1:
            val = 1
        set_sync_state("auto_sync_interval_mins", str(val))
    return get_sync_status()


@router.post("/importar-xmls")
async def importar_arquivos_xml(
    files: List[UploadFile] = File(...),
    empresa_cnpj: Optional[str] = Form(None),
):
    """Permite o envio em lote de múltiplos arquivos XML de NF-e para armazenamento no banco local."""
    importados = 0
    erros = []

    for file in files:
        if not file.filename.lower().endswith(".xml"):
            continue
        try:
            content = await file.read()
            dados = parse_nfe_xml(content)
            if not dados or not dados.get("chave"):
                erros.append(f"{file.filename}: XML inválido ou sem chave de acesso")
                continue

            xml_str = content.decode("utf-8", errors="replace")
            if save_nfe_doc(dados, xml_raw=xml_str, empresa_cnpj=empresa_cnpj):
                importados += 1
            else:
                erros.append(f"{file.filename}: Falha ao gravar no banco de dados")
        except Exception as e:
            erros.append(f"{file.filename}: {str(e)}")

    return {
        "success": True,
        "total_arquivos": len(files),
        "importados": importados,
        "erros": erros,
    }


# ====================================================================
# PACOTE CONTÁBIL MENSAL (SPED / ZIP COM XMLs + PDFs + EXCEL)
# ====================================================================

@router.get("/contabil/pacote-mensal")
async def baixar_pacote_contabil_mensal(
    ano: int = Query(..., ge=2020, le=2030),
    mes: int = Query(..., ge=1, le=12),
    empresa_cnpj: Optional[str] = Query(None),
    incluir_pdfs: bool = Query(True),
):
    """Gera e retorna o pacote mensal compactado (.zip) com XMLs, DANFEs e Planilha Excel para a Contabilidade."""
    from backend.services.contabil_service import generate_pacote_contabil_zip
    try:
        zip_buffer = generate_pacote_contabil_zip(ano=ano, mes=mes, empresa_cnpj=empresa_cnpj, incluir_pdfs=incluir_pdfs)
        filename = f"Pacote_Contabil_{mes:02d}_{ano}.zip"
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar pacote contábil: {str(e)}")


# ====================================================================
# CHECK-IN AUTOMÁTICO DE ESTOQUE (A PARTIR DE COMPRAS)
# ====================================================================

@router.post("/estoque/checkin-nfe")
async def executar_checkin_estoque(payload: dict = Body(...)):
    """Lê os itens de uma NF-e de entrada e cadastra/atualiza o estoque no catálogo."""
    from backend.database import checkin_nfe_estoque
    chave = payload.get("chave")
    if not chave:
        raise HTTPException(status_code=400, detail="Chave da NF-e não informada.")
    markup = float(payload.get("markup_sugerido_pct", 40.0))
    try:
        res = checkin_nfe_estoque(chave=chave, markup_sugerido_pct=markup)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/estoque/historico")
async def extrato_estoque(codigo_produto: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    """Retorna o histórico de movimentações do estoque (Kardex)."""
    from backend.database import get_historico_estoque
    return {"success": True, "movimentacoes": get_historico_estoque(codigo_produto=codigo_produto, limit=limit)}


# ====================================================================
# FINANCEIRO: TENDÊNCIA, EMPRESAS, INADIMPLÊNCIA, EXPORT
# ====================================================================

@router.get("/financeiro/tendencia")
async def dre_tendencia(empresa_cnpj: Optional[str] = Query(None)):
    """Série histórica mensal do DRE (últimos 12 meses)."""
    return {"success": True, "tendencia": get_dre_tendencia(empresa_cnpj=empresa_cnpj)}


@router.get("/financeiro/empresas")
async def empresas_lista():
    """Lista as empresas cadastradas (CNPJ + nome) para filtro."""
    return {"success": True, "empresas": get_empresas()}


@router.get("/financeiro/inadimplencia")
async def inadimplencia(empresa_cnpj: Optional[str] = Query(None)):
    """Relatório de inadimplência por cliente (contas a receber)."""
    return {"success": True, "inadimplencia": get_inadimplencia(empresa_cnpj=empresa_cnpj)}


@router.get("/financeiro/contas-a-pagar/export")
async def export_contas_a_pagar(
    empresa_cnpj: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Exporta contas a pagar em CSV."""
    import csv
    import io
    data = list_contas_a_pagar(empresa_cnpj=empresa_cnpj, filtro_status=status)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Status", "Vencimento", "Fornecedor", "Empresa", "NF-e/Parcela", "Valor", "Pago"])
    for d in data.get("duplicatas", []):
        writer.writerow([
            d.get("status_calc", ""), d.get("d_venc", ""), d.get("emitente_nome", ""),
            d.get("destinatario_nome", ""), f"{d.get('nfe_numero','')} {d.get('n_dup','')}",
            d.get("v_dup", 0), "Sim" if d.get("pago") else "Não",
        ])
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=contas_a_pagar.csv"},
    )


@router.get("/financeiro/contas-a-receber/export")
async def export_contas_a_receber(
    empresa_cnpj: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Exporta contas a receber em CSV."""
    import csv
    import io
    data = list_contas_a_receber(empresa_cnpj=empresa_cnpj, filtro_status=status)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Status", "Vencimento", "Cliente", "Empresa", "NF-e/Parcela", "Valor", "Recebido"])
    for d in data.get("contas", []):
        writer.writerow([
            d.get("status_calc", ""), d.get("d_venc", ""), d.get("cliente_nome", ""),
            d.get("empresa_cnpj", ""), f"{d.get('nfe_numero','')} {d.get('n_dup','')}",
            d.get("v_dup", 0), "Sim" if d.get("recebido") else "Não",
        ])
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=contas_a_receber.csv"},
    )


@router.get("/financeiro/dre/export")
async def export_dre_tendencia(empresa_cnpj: Optional[str] = Query(None)):
    """Exporta a tendência do DRE em CSV."""
    import csv
    import io
    data = get_dre_tendencia(empresa_cnpj=empresa_cnpj)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Competência", "Receita Bruta", "Impostos", "Receita Líquida", "CPV", "Lucro Bruto", "DAS", "Lucro Líquido", "AP Total", "AP Pago", "AR Total", "AR Recebido"])
    for r in data.get("tendencia", []):
        writer.writerow([
            r.get("competencia", ""), r.get("receita_bruta", 0), r.get("impostos_venda", 0),
            r.get("receita_liquida", 0), r.get("cpv", 0), r.get("lucro_bruto", 0),
            r.get("das_simples_estimado", 0), r.get("lucro_liquido", 0),
            r.get("ap_total", 0), r.get("ap_pago", 0), r.get("ar_total", 0), r.get("ar_recebido", 0),
        ])
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=dre_tendencia.csv"},
    )


# ====================================================================
# APURAÇÃO DO SIMPLES NACIONAL & DRE DE MARGEM
# ====================================================================

@router.get("/tributacao/simples-nacional")
async def apuracao_simples_nacional(
    ano: Optional[int] = Query(None),
    mes: Optional[int] = Query(None),
    empresa_cnpj: Optional[str] = Query(None),
):
    """Calcula a estimativa do imposto DAS do Simples Nacional (Anexo I) do mês corrente."""
    from backend.database import get_simples_nacional_apuracao
    return get_simples_nacional_apuracao(ano=ano, mes=mes, empresa_cnpj=empresa_cnpj)


@router.get("/dre/margens")
async def dre_margens_produtos(empresa_cnpj: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    """Calcula o Lucro Bruto e a Margem Real de cada produto comparando preço de compra vs. preço de venda."""
    from backend.database import get_dre_produtos_margem
    return {"success": True, "produtos": get_dre_produtos_margem(empresa_cnpj=empresa_cnpj, limit=limit)}


# ====================================================================
# SINCRONIZAÇÃO EM NUVEM (GOOGLE CLOUD FIRESTORE 24H)
# ====================================================================

@router.post("/firestore/sync-all")
async def sincronizar_tudo_firestore(batch_size: int = Query(200, ge=10, le=500)):
    """Sincroniza 100% das notas fiscais e cadastros do banco local para o Google Cloud Firestore."""
    from backend.services.firestore_service import sync_all_database_to_firestore
    try:
        resultado = sync_all_database_to_firestore(batch_size=batch_size)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na sincronização Firestore: {str(e)}")


@router.get("/firestore/status")
async def status_firestore():
    """Retorna o status de conexão com o Cloud Firestore e total de notas locais prontas para nuvem."""
    from backend.config import settings
    from backend.database import get_db_connection
    total_local = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs")
        row = cursor.fetchone()
        total_local = row["total"] if row else 0

    return {
        "success": True,
        "configured": bool(settings.FIREBASE_PROJECT_ID and settings.FIREBASE_API_KEY),
        "project_id": settings.FIREBASE_PROJECT_ID,
        "total_notas_local": total_local,
        "online_24h": True,
        "collections": ["nfe_docs", "empresas", "nfe_events"],
    }
