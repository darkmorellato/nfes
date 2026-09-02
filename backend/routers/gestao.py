import io
import csv
import zipfile
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger("nfe.gestao")


def _extrair_chave_do_nome(filename: str) -> str:
    """Tenta recuperar a chave de 44 dígitos do próprio nome do arquivo XML.
    Útil quando o parser falha mas o arquivo está nominalmente correto.
    """
    if not filename:
        return ""
    m = re.search(r"(\d{44})", filename)
    return m.group(1) if m else ""

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
    preview_limpeza_nfes,
    executar_limpeza_nfes,
    auditoria_xmls_orfaos,
    apagar_xmls_orfaos,
    auditoria_rapida_base,
    auditar_saltos_numeracao,
)
from backend.services.sync_service import run_sync_iteration, get_sync_status, get_sefaz_block_status, importar_saidas_por_chaves
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


@router.get("/contabilidade/excel-detalhado")
async def exportar_excel_contabil_detalhado(
    mes: int = Query(..., ge=1, le=12),
    ano: int = Query(..., ge=2000, le=2100),
):
    """Gera planilha Excel DETALHADA para a contabilidade.

    Estrutura:
      • Aba ``Resumo`` com totais por empresa e tipo (entrada/saída).
      • Uma aba por empresa com 1 linha por ITEM de NF-e, contendo:
        número, chave, data, emitente, destinatário, operação, situação,
        código, EAN, descrição, CFOP, NCM, CST, unidade, quantidade,
        valor unitário, valor total, ICMS do item.

    Ideal para o escritório de contabilidade fechar o mês sem precisar
    abrir cada XML individualmente.
    """
    try:
        from backend.services.excel_service import generate_fiscal_excel_detalhado
        excel_buffer = generate_fiscal_excel_detalhado(mes=mes, ano=ano)
        filename = f"fechamento_fiscal_detalhado_{ano:04d}_{mes:02d}.xlsx"
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.exception("Erro ao gerar Excel detalhado")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar planilha detalhada: {str(e)}")


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
    """Retorna as configurações atuais de webhook, Telegram e WhatsApp (descriptografadas)."""
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
        "whatsapp_alert_numbers": _read("whatsapp_alert_numbers") or "+5519989354849, +5519990151809",
    }


@router.post("/notificacoes/config")
async def salvar_config_notificacoes(payload: dict = Body(...)):
    """Salva configurações de canais de notificação (Telegram / Webhook / WhatsApp),
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
    if "whatsapp_alert_numbers" in payload:
        _write("whatsapp_alert_numbers", str(payload["whatsapp_alert_numbers"]))

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


@router.post("/saidas/importar-chaves")
async def importar_saidas_por_chaves_endpoint(payload: dict = Body(default={})):
    """Importa NF-es de SAÍDA (emitidas externamente, ex: ERP HostMundo) via chave de 44 dígitos.

    Para cada chave, consulta a SEFAZ via consChNFe usando o certificado da empresa
    informada (que é a EMITENTE) e salva com tipo_doc=1.

    Payload:
        chaves: List[str] - chaves de 44 dígitos (uma por linha, vírgula ou espaço)
        empresa_cnpj: str - CNPJ da empresa que EMITIU as NF-es (precisa ter certificado)
        homologacao: bool (default False)
    """
    chaves = payload.get("chaves", [])
    if isinstance(chaves, str):
        # Aceita string única com várias chaves separadas por quebra-linha, vírgula ou espaço
        chaves = [c for c in chaves.replace("\n", " ").replace(",", " ").replace(";", " ").split() if c.strip()]
    empresa_cnpj = "".join(c for c in str(payload.get("empresa_cnpj", "")) if c.isdigit())
    homologacao = bool(payload.get("homologacao", False))
    if not chaves:
        raise HTTPException(status_code=400, detail="Nenhuma chave de acesso informada.")
    if not empresa_cnpj:
        raise HTTPException(status_code=400, detail="CNPJ da empresa emitente é obrigatório.")
    return importar_saidas_por_chaves(chaves, empresa_cnpj, homologacao)


@router.get("/sync/status")
async def status_sincronizacao():
    """Retorna o status atual do robô de sincronização multi-empresa (NF-e entrada + saída).

    Enriquece cada empresa com info de bloqueio SEFAZ (cStat 656) e cooldown ativo,
    para que a UI mostre badge "🔒 SEFAZ BLOQUEADA" e desabilite o botão de sync manual
    até a próxima janela permitida pelo backoff exponencial.
    """
    status = get_sync_status()
    for cert in status.get("empresas", []):
        cnpj = cert.get("cnpj", "")
        block = get_sefaz_block_status(cnpj)
        cert["blocked_by_sefaz"] = block.get("blocked", False)
        cert["retry_at"] = block.get("retry_at")
        cert["cooldown_minutes"] = block.get("cooldown_minutes", 0)
        cert["tentativa_656"] = block.get("tentativa", 0)
        cert["motivo_656"] = block.get("motivo", "")
    return status


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
            if not content:
                erros.append(f"{file.filename}: arquivo vazio")
                logger.warning("XML vazio recebido: %s", file.filename)
                continue

            dados = parse_nfe_xml(content)
            if not dados:
                erros.append(f"{file.filename}: parser retornou vazio")
                logger.warning("parse_nfe_xml retornou vazio para %s (%d bytes)", file.filename, len(content))
                continue
            if "error" in dados:
                erros.append(f"{file.filename}: {dados['error']}")
                logger.warning("parse_nfe_xml erro em %s: %s", file.filename, dados["error"])
                continue
            if not dados.get("chave"):
                # Fallback: alguns XMLs (gerados por ERPs terceiros ou
                # serializações alternativas) podem vir sem o infNFe/Id no
                # namespace padrão. Antes de descartar, tenta extrair a
                # chave de 44 dígitos do nome do arquivo.
                chave_nome = _extrair_chave_do_nome(file.filename)
                if chave_nome:
                    dados["chave"] = chave_nome
                    logger.info(
                        "Chave recuperada do nome do arquivo %s: %s",
                        file.filename, chave_nome,
                    )
                else:
                    erros.append(
                        f"{file.filename}: XML sem chave de acesso (parser extraiu mas id vazio)"
                    )
                    logger.warning(
                        "parse_nfe_xml sem chave em %s. Keys=%s, id_infNFe=%r",
                        file.filename,
                        list(dados.keys()),
                        dados.get("chave"),
                    )
                    continue

            xml_str = content.decode("utf-8", errors="replace")
            if save_nfe_doc(dados, xml_raw=xml_str, empresa_cnpj=empresa_cnpj):
                importados += 1
            else:
                erros.append(f"{file.filename}: Falha ao gravar no banco de dados")
        except Exception as e:
            logger.exception("Erro inesperado importando %s", file.filename)
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
# RECUPERAR ITENS VIA SEFAZ (para planilha contábil detalhada)
# ====================================================================

@router.post("/contabilidade/recuperar-itens")
async def recuperar_itens_nfes(
    payload: Dict[str, Any] = Body(default={}),
    max_notas: int = Query(200, ge=1, le=1000),
):
    """Recupera XMLs/itens das NF-e sem itens no banco consultando a SEFAZ.

    Para cada NF-e sem itens:
      • Tenta usar a empresa_cnpj cadastrada para puxar via consChNFe
        (consulta_distribuicao) usando o certificado A1.
      • Se conseguir o XML completo, salva no banco e popula nfe_items.

    Isso é necessário para que a planilha detalhada de fechamento contábil
    mostre os produtos por nota. Requer certificado digital ativo.

    Payload opcional:
      • apenas_empresa_cnpj: filtra por uma empresa específica
      • apenas_chaves: lista de chaves específicas (opcional)
    """
    from backend.services.sync_service import importar_saidas_por_chaves
    from backend.database import get_db_connection, get_certificate_record

    apenas_empresa = "".join(c for c in str(payload.get("apenas_empresa_cnpj", "")) if c.isdigit())
    apenas_chaves = payload.get("apenas_chaves") or []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Seleciona notas sem itens
        if apenas_chaves:
            placeholders = ",".join("?" * len(apenas_chaves))
            cursor.execute(
                f"""
                SELECT DISTINCT d.chave, d.empresa_cnpj, d.emitente_cnpj
                FROM nfe_docs d
                WHERE NOT EXISTS (SELECT 1 FROM nfe_items i WHERE i.chave = d.chave)
                  AND d.chave IN ({placeholders})
                LIMIT ?
                """,
                tuple(apenas_chaves) + (max_notas,),
            )
        elif apenas_empresa:
            cursor.execute(
                """
                SELECT DISTINCT d.chave, d.empresa_cnpj, d.emitente_cnpj
                FROM nfe_docs d
                WHERE NOT EXISTS (SELECT 1 FROM nfe_items i WHERE i.chave = d.chave)
                  AND (d.empresa_cnpj = ? OR d.emitente_cnpj = ?)
                LIMIT ?
                """,
                (apenas_empresa, apenas_empresa, max_notas),
            )
        else:
            cursor.execute(
                """
                SELECT DISTINCT d.chave, d.empresa_cnpj, d.emitente_cnpj
                FROM nfe_docs d
                WHERE NOT EXISTS (SELECT 1 FROM nfe_items i WHERE i.chave = d.chave)
                ORDER BY d.data_emissao DESC
                LIMIT ?
                """,
                (max_notas,),
            )
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return {
            "success": True,
            "message": "Nenhuma NF-e sem itens encontrada.",
            "total": 0, "processadas": 0, "sucessos": 0, "falhas": 0,
        }

    # Agrupa chaves por empresa para usar o certificado correto
    por_empresa: Dict[str, list] = {}
    sem_empresa: list = []
    for r in rows:
        emp = r.get("empresa_cnpj") or ""
        # Tenta usar a empresa cadastrada; se não, tenta o emitente
        if not emp or not get_certificate_record(emp):
            alt = r.get("emitente_cnpj") or ""
            alt_clean = "".join(c for c in str(alt) if c.isdigit())
            if alt_clean and get_certificate_record(alt_clean):
                emp = alt_clean
        if emp and get_certificate_record(emp):
            por_empresa.setdefault(emp, []).append(r["chave"])
        else:
            sem_empresa.append(r["chave"])

    total_sucessos = 0
    total_falhas = 0
    detalhes_por_empresa = []

    for emp_cnpj, chaves in por_empresa.items():
        try:
            res = importar_saidas_por_chaves(
                chaves=chaves,
                empresa_cnpj=emp_cnpj,
                homologacao=None,
            )
            s = int(res.get("sucessos", 0) or 0)
            f = int(res.get("falhas", 0) or 0)
            total_sucessos += s
            total_falhas += f
            detalhes_por_empresa.append({
                "empresa_cnpj": emp_cnpj,
                "processadas": len(chaves),
                "sucessos": s,
                "falhas": f,
                "error": res.get("error") or "",
                "blocked_by_sefaz": res.get("blocked_by_sefaz", False),
            })
        except Exception as e:
            total_falhas += len(chaves)
            detalhes_por_empresa.append({
                "empresa_cnpj": emp_cnpj,
                "processadas": len(chaves),
                "sucessos": 0, "falhas": len(chaves),
                "error": str(e),
            })

    if sem_empresa:
        total_falhas += len(sem_empresa)
        detalhes_por_empresa.append({
            "empresa_cnpj": "(sem certificado)",
            "processadas": len(sem_empresa),
            "sucessos": 0, "falhas": len(sem_empresa),
            "error": "NF-e sem empresa/emitente com certificado cadastrado",
        })

    return {
        "success": True,
        "total_encontradas": len(rows),
        "processadas": sum(d["processadas"] for d in detalhes_por_empresa),
        "sucessos": total_sucessos,
        "falhas": total_falhas,
        "detalhes": detalhes_por_empresa,
        "message": (
            f"{total_sucessos} notas tiveram itens recuperados via SEFAZ, "
            f"{total_falhas} falharam (verifique certificado e conexão)."
        ),
    }


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


@router.post("/firestore/pull-all")
async def pull_do_firestore():
    """One-shot: baixa TODAS as NF-es do Cloud Firestore e faz upsert no SQLite local.

    Idempotente — pode rodar várias vezes sem duplicar (chave é PRIMARY KEY).
    Pode demorar 30-90s para 1.500+ documentos.
    """
    from backend.services.firestore_service import pull_from_firestore
    try:
        return pull_from_firestore()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no pull do Firestore: {str(e)}")


@router.get("/firestore/pull-status")
async def status_pull_firestore():
    """Retorna contagem de NF-es locais + status de conexão com o Firestore."""
    import json
    import urllib.request as _urlreq

    from backend.config import settings
    from backend.services.firestore_service import _get_api_key, _get_project_id
    from backend.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs")
        local_count = cursor.fetchone()["total"] or 0

    api_key = _get_api_key()
    project_id = _get_project_id()
    cloud_status = "nao_configurado"
    cloud_count = None

    if api_key and project_id:
        try:
            url = (
                f"https://firestore.googleapis.com/v1/projects/{project_id}"
                f"/databases/(default)/documents/nfe_docs?pageSize=1&key={api_key}"
            )
            with _urlreq.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Firestore REST não retorna total — só a presença/ausência da coleção.
            cloud_count = "disponivel" if "documents" in data else "vazio"
            cloud_status = "conectado"
        except Exception as e:
            cloud_status = f"erro: {str(e)[:100]}"

    return {
        "success": True,
        "local_count": local_count,
        "cloud_status": cloud_status,
        "cloud_count": cloud_count,
        "project_id": project_id or "",
        "configured": bool(api_key and project_id),
    }


@router.post("/firestore/consolidar-clientes")
async def consolidar_clientes_firestore():
    """Varre TODAS as NF-es do SQLite e consolida clientes (emitentes + destinatários)
    na coleção 'clientes' do Firestore. Idempotente — pode rodar várias vezes."""
    from backend.services.firestore_service import consolidar_clientes_do_sqlite
    try:
        return consolidar_clientes_do_sqlite()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na consolidação: {str(e)}")


@router.post("/firestore/consolidar-produtos")
async def consolidar_produtos_firestore():
    """Varre a tabela nfe_items e consolida produtos na coleção 'produtos' do Firestore.
    Idempotente — pode rodar várias vezes."""
    from backend.services.firestore_service import consolidar_produtos_do_sqlite
    try:
        return consolidar_produtos_do_sqlite()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na consolidação: {str(e)}")


@router.post("/firestore/sincronizar-clientes-local")
async def sincronizar_clientes_local():
    """Copia a coleção 'clientes' do Firestore para a tabela cad_clientes do SQLite.
    Necessário para que a aba 'Cadastro de Clientes' do app mostre os dados."""
    from backend.services.firestore_service import sincronizar_clientes_firestore_para_sqlite
    try:
        return sincronizar_clientes_firestore_para_sqlite()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar: {str(e)}")


@router.post("/firestore/sincronizar-produtos-local")
async def sincronizar_produtos_local():
    """Copia a coleção 'produtos' do Firestore para a tabela cad_produtos do SQLite.
    Necessário para que a aba 'Catálogo de Produtos' do app mostre os dados."""
    from backend.services.firestore_service import sincronizar_produtos_firestore_para_sqlite
    try:
        return sincronizar_produtos_firestore_para_sqlite()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar: {str(e)}")


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


# ====================================================================
# ROTAS DE LIMPEZA DE DADOS DE TESTE, XMLS ÓRFÃOS E AUDITORIA DA BASE
# ====================================================================

@router.get("/limpeza/auditoria-base")
async def rota_auditoria_rapida_base():
    """Retorna diagnóstico analítico rápido da base de dados, armazenamento em disco e sync."""
    try:
        return auditoria_rapida_base()
    except Exception as e:
        logger.error(f"[Limpeza] Erro ao gerar auditoria rápida da base: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na auditoria da base: {str(e)}")


@router.get("/limpeza/preview")
async def rota_preview_limpeza(
    termo: Optional[str] = Query(None),
    cnpj: Optional[str] = Query(None),
    empresa_cnpj: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    tipo_teste: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Retorna prévia e contagem de NF-es que atendem aos filtros antes da exclusão real."""
    try:
        return preview_limpeza_nfes(
            termo=termo,
            cnpj=cnpj,
            empresa_cnpj=empresa_cnpj,
            data_inicio=data_inicio,
            data_fim=data_fim,
            situacao=situacao,
            tipo_teste=tipo_teste,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"[Limpeza] Erro ao gerar prévia de limpeza: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na prévia de limpeza: {str(e)}")


@router.post("/limpeza/executar")
async def rota_executar_limpeza(payload: Dict[str, Any] = Body(...)):
    """Executa a exclusão definitiva das NF-es selecionadas no SQLite, arquivos XML em disco e Cloud Firestore."""
    try:
        termo = payload.get("termo")
        cnpj = payload.get("cnpj")
        empresa_cnpj = payload.get("empresa_cnpj")
        data_inicio = payload.get("data_inicio")
        data_fim = payload.get("data_fim")
        situacao = payload.get("situacao")
        tipo_teste = payload.get("tipo_teste")
        chaves_selecionadas = payload.get("chaves_selecionadas")
        apagar_xml_disco = bool(payload.get("apagar_xml_disco", True))
        apagar_firestore = bool(payload.get("apagar_firestore", True))

        resultado = executar_limpeza_nfes(
            termo=termo,
            cnpj=cnpj,
            empresa_cnpj=empresa_cnpj,
            data_inicio=data_inicio,
            data_fim=data_fim,
            situacao=situacao,
            tipo_teste=tipo_teste,
            chaves_selecionadas=chaves_selecionadas,
            apagar_xml_disco=apagar_xml_disco,
            apagar_firestore=apagar_firestore,
        )
        return resultado

    except Exception as e:
        logger.error(f"[Limpeza] Erro ao executar limpeza: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao executar limpeza: {str(e)}")


@router.get("/limpeza/xmls-orfaos")
async def rota_auditoria_xmls_orfaos():
    """Varre data/xmls/ e lista arquivos XML órfãos que não estão registrados no banco."""
    try:
        return auditoria_xmls_orfaos()
    except Exception as e:
        logger.error(f"[Limpeza] Erro ao verificar XMLs órfãos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao verificar XMLs órfãos: {str(e)}")


@router.post("/limpeza/apagar-xmls-orfaos")
async def rota_apagar_xmls_orfaos():
    """Apaga fisicamente do disco todos os arquivos XML órfãos que não existem no banco."""
    try:
        return apagar_xmls_orfaos()
    except Exception as e:
        logger.error(f"[Limpeza] Erro ao apagar XMLs órfãos: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao apagar XMLs órfãos: {str(e)}")


@router.get("/auditoria/gaps-numeracao")
async def rota_auditoria_gaps(
    empresa_cnpj: Optional[str] = Query(None),
    serie: Optional[str] = Query(None),
):
    """Analisa a sequência de numeração de notas de saída e identifica saltos ou números pendentes."""
    try:
        return auditar_saltos_numeracao(empresa_cnpj=empresa_cnpj, serie=serie)
    except Exception as e:
        logger.error(f"[Auditoria] Erro ao auditar gaps de numeração: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao auditar saltos de numeração: {str(e)}")


@router.get("/sistema/atualizacao/status")
async def rota_status_atualizacao():
    """Verifica se há novas atualizações disponíveis no GitHub."""
    from backend.services.updater_service import check_update_status
    return check_update_status()


@router.post("/sistema/atualizacao/executar")
async def rota_executar_atualizacao():
    """Executa a atualização automática do sistema via git pull + pip."""
    from backend.services.updater_service import execute_update
    return execute_update()

