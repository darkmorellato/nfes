import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.config import settings
from backend.services.danfe_service import parse_nfe_xml, parse_distribuicao_xml, parse_resumo_sefaz
from backend.services.pynfe_service import manifestacao_destinatario
from backend.services.notification_service import dispatch_notification
from backend.database import (
    get_db_connection,
    save_nfe_doc,
    save_nfe_event,
    set_sync_state,
    get_sync_state,
    update_cert_sync_state,
    list_certificates_db,
    get_certificate_record,
)

logger = logging.getLogger(__name__)

_sync_task: Optional[asyncio.Task] = None


# Backoff exponencial para cStat 656 (Consumo Indevido da SEFAZ).
# A SEFAZ aplica bloqueio temporário quando detecta consultas em excesso
# (intervalo menor que o mínimo oficial, geralmente 1h). Para não martelar
# a SEFAZ e agravar o bloqueio, escalamos a espera entre tentativas:
# 1h → 2h → 4h → 8h → 24h (cap). Qualquer sync bem-sucedido reseta a contagem.
_COOLDOWN_KEY_TEMPLATE = "sefaz_656_cooldown_{cnpj}"
_COOLDOWN_BACKOFFS_MIN = [60, 120, 240, 480, 1440]  # em minutos


def _calcular_cooldown_656(cnpj: str) -> Optional[datetime]:
    """Retorna o datetime até quando a SEFAZ está bloqueada para esta empresa,
    ou None se a próxima tentativa já pode ser feita."""
    clean_cnpj = "".join(c for c in str(cnpj) if c.isdigit())
    raw = get_sync_state(_COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj), "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        retry_at = datetime.fromisoformat(data["retry_at"])
        if datetime.now() < retry_at:
            return retry_at
        # Cooldown expirou — limpa o registro
        set_sync_state(_COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj), "")
        return None
    except Exception:
        return None


def _registrar_656(cnpj: str, motivo: str) -> dict:
    """Registra um cStat 656 e calcula a próxima janela de retry com backoff exponencial.

    Returns dict com: tentativa (1..N), retry_at (datetime), cooldown_min (int).
    """
    clean_cnpj = "".join(c for c in str(cnpj) if c.isdigit())
    raw = get_sync_state(_COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj), "")
    tentativa = 1
    if raw:
        try:
            data = json.loads(raw)
            tentativa = min(int(data.get("tentativa", 0)) + 1, len(_COOLDOWN_BACKOFFS_MIN))
        except Exception:
            tentativa = 1
    minutos = _COOLDOWN_BACKOFFS_MIN[tentativa - 1]
    retry_at = datetime.now() + timedelta(minutes=minutos)
    set_sync_state(
        _COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj),
        json.dumps({
            "tentativa": tentativa,
            "retry_at": retry_at.isoformat(),
            "motivo": motivo,
        })
    )
    return {"tentativa": tentativa, "retry_at": retry_at, "cooldown_min": minutos}


def _limpar_656(cnpj: str):
    """Limpa o cooldown de 656 quando o sync volta a funcionar."""
    clean_cnpj = "".join(c for c in str(cnpj) if c.isdigit())
    set_sync_state(_COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj), "")


def run_sync_single_company(
    cnpj: str,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    max_batches: int = 50,
) -> Dict[str, Any]:
    """Executa a sincronização para uma empresa específica a partir do seu último NSU."""
    from pynfe.processamento.comunicacao import ComunicacaoSefaz

    clean_cnpj = "".join(c for c in str(cnpj) if c.isdigit())
    uf = (uf or settings.DEFAULT_UF).upper()
    homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    cert_rec = get_certificate_record(clean_cnpj)
    if not cert_rec:
        return {"success": False, "cnpj": clean_cnpj, "error": f"Certificado para CNPJ {clean_cnpj} não encontrado"}

    # Se a SEFAZ está bloqueando esta empresa (cStat 656) e o cooldown ainda
    # não expirou, pula o ciclo para não agravar o bloqueio.
    cooldown_until = _calcular_cooldown_656(clean_cnpj)
    if cooldown_until is not None:
        cooldown_min = max(0, int((cooldown_until - datetime.now()).total_seconds() / 60))
        return {
            "success": True,
            "skipped": True,
            "cnpj": clean_cnpj,
            "razao_social": cert_rec.get("razao_social", ""),
            "docs_saved": 0,
            "events_saved": 0,
            "ult_nsu": int(cert_rec.get("last_nsu", "0") or "0"),
            "max_nsu": int(cert_rec.get("max_nsu", "0") or "0"),
            "c_stat": "656",
            "motivo": "Bloqueio temporário SEFAZ (cStat 656) — cooldown ativo",
            "blocked_by_sefaz": True,
            "retry_at": cooldown_until.isoformat(),
            "cooldown_minutes": cooldown_min,
        }

    cert_path = cert_rec.get("path")
    cert_pwd = cert_rec.get("password")

    try:
        con = ComunicacaoSefaz(uf, cert_path, cert_pwd, homologacao=homolog)
    except Exception as e:
        status_msg = f"Erro de conexão/certificado: {str(e)}"
        update_cert_sync_state(clean_cnpj, cert_rec.get("last_nsu", "0"), status_str=status_msg)
        return {"success": False, "cnpj": clean_cnpj, "error": status_msg}

    cur_nsu = int(cert_rec.get("last_nsu", "0") or "0")
    total_docs_saved = 0
    total_events_saved = 0
    final_cstat = ""
    final_motivo = ""
    ult_nsu_retornado = cur_nsu
    max_nsu_retornado = int(cert_rec.get("max_nsu", "0") or "0")

    for batch in range(max_batches):
        try:
            response = con.consulta_distribuicao(cnpj=clean_cnpj, nsu=cur_nsu)
            if response.status_code != 200:
                final_cstat = str(response.status_code)
                final_motivo = f"HTTP {response.status_code}"
                break

            parsed = parse_distribuicao_xml(response.text)
            final_cstat = parsed.get("c_stat", "")
            final_motivo = parsed.get("motivo", "")

            next_ult = int(parsed.get("ult_nsu") or "0")
            next_max = int(parsed.get("max_nsu") or "0")

            if final_cstat == "589":
                update_cert_sync_state(
                    clean_cnpj,
                    "0",
                    "0",
                    f"cStat 589 (NSU inválido) — resetado para 0. Motivo: {final_motivo}",
                )
                cur_nsu = 0
                ult_nsu_retornado = 0
                max_nsu_retornado = 0
                break

            documentos = parsed.get("documentos", [])
            highest_nsu_saved = cur_nsu
            for doc in documentos:
                tag = doc.get("tag", "")
                xml_raw = doc.get("xml_raw", "")
                nsu_doc = doc.get("nsu", str(cur_nsu))

                try:
                    nsu_doc_int = int(nsu_doc or "0")
                except (ValueError, TypeError):
                    nsu_doc_int = 0
                highest_nsu_saved = max(highest_nsu_saved, nsu_doc_int)

                if tag in ("nfeProc", "NFe") and xml_raw:
                    try:
                        dados = parse_nfe_xml(xml_raw.encode("utf-8"))
                        dados["nsu"] = nsu_doc
                        dados["empresa_cnpj"] = clean_cnpj
                        if save_nfe_doc(dados, xml_raw=xml_raw, empresa_cnpj=clean_cnpj):
                            total_docs_saved += 1
                            v_tot = dados.get("totais", {}).get("v_nf") or dados.get("valor_total", 0.0)
                            emit_n = dados.get("emitente", {}).get("nome") or "Fornecedor"
                            dispatch_notification(
                                title=f"Nova NF-e Recebida ({cert_rec.get('razao_social', clean_cnpj)})",
                                message=f"Nota de {emit_n} no valor de R$ {float(v_tot):,.2f}",
                                tipo="nfe_nova",
                                chave=dados.get("chave"),
                            )
                    except Exception as parse_err:
                        logger.warning(f"Erro ao parsear NFe NSU {nsu_doc}: {parse_err}")
                        doc["empresa_cnpj"] = clean_cnpj
                        if save_nfe_doc(doc, xml_raw=xml_raw, empresa_cnpj=clean_cnpj):
                            total_docs_saved += 1
                elif tag == "resNFe":
                    doc["nsu"] = nsu_doc
                    doc["empresa_cnpj"] = clean_cnpj
                    if save_nfe_doc(doc, xml_raw=xml_raw, empresa_cnpj=clean_cnpj):
                        total_docs_saved += 1
                        dispatch_notification(
                            title=f"Nova NF-e Identificada ({cert_rec.get('razao_social', clean_cnpj)})",
                            message=f"Emitente: {doc.get('nome_emitente', '')} | Valor: R$ {float(doc.get('valor_total', 0)):,.2f}",
                            tipo="nfe_nova",
                            chave=doc.get("chave"),
                        )
                    # Auto-Ciência da Operação para liberar o download do XML completo na SEFAZ
                    chave_nfe = doc.get("chave")
                    if chave_nfe and len(chave_nfe) == 44:
                        try:
                            m_res = manifestacao_destinatario(
                                chave=chave_nfe,
                                cnpj=clean_cnpj,
                                tipo_manifestacao="210210",
                                justificativa="Ciencia da Operacao automatica para download do XML",
                                uf=uf,
                                homologacao=homolog,
                            )
                            logger.info(f"Auto-ciência registrada na SEFAZ para chave {chave_nfe}: cStat {m_res.get('c_stat')}")

                            # Tenta obter o XML completo imediatamente (com pequeno delay para replicação da SEFAZ)
                            try:
                                import time
                                time.sleep(0.6)
                                dl_resp = con.consulta_distribuicao(cnpj=clean_cnpj, chave=chave_nfe)
                                if dl_resp.status_code == 200:
                                    dl_parsed = parse_distribuicao_xml(dl_resp.text)
                                    for dl_doc in dl_parsed.get("documentos", []):
                                        dl_tag = dl_doc.get("tag", "")
                                        dl_raw = dl_doc.get("xml_raw", "")
                                        if dl_tag in ("nfeProc", "NFe") and dl_raw:
                                            dl_dados = parse_nfe_xml(dl_raw.encode("utf-8"))
                                            dl_dados["nsu"] = nsu_doc
                                            dl_dados["empresa_cnpj"] = clean_cnpj
                                            save_nfe_doc(dl_dados, xml_raw=dl_raw, empresa_cnpj=clean_cnpj)
                                            logger.info(f"XML completo obtido imediatamente para {chave_nfe} após auto-ciência!")
                                            break
                            except Exception as dl_err:
                                logger.debug(f"Download imediato pós-ciência para {chave_nfe}: {dl_err}")
                        except Exception as m_err:
                            logger.warning(f"Auto-ciência na sync para {chave_nfe}: {m_err}")
                elif tag in ("resEvento", "procEventoNFe", "evento"):
                    event_data = {
                        "chave": doc.get("chave"),
                        "tipo_evento": doc.get("tipo_evento"),
                        "desc_evento": doc.get("desc_evento"),
                        "n_seq": doc.get("n_seq", 1),
                        "dh_evento": doc.get("data_emissao"),
                        "c_stat": "135",
                        "x_motivo": doc.get("situacao"),
                    }
                    doc["nsu"] = nsu_doc
                    doc["empresa_cnpj"] = clean_cnpj
                    if save_nfe_event(event_data):
                        total_events_saved += 1
                        if doc.get("tipo_evento") == "110111":
                            dispatch_notification(
                                title="⚠️ NF-e Cancelada pelo Fornecedor",
                                message=f"O fornecedor cancelou a NF-e chave {doc.get('chave')}",
                                tipo="cancelamento",
                                chave=doc.get("chave"),
                            )
                        elif doc.get("tipo_evento") == "110110":
                            dispatch_notification(
                                title="📜 Carta de Correção (CC-e) Protocolada",
                                message=f"Carta de Correção vinculada à NF-e {doc.get('chave')}: {doc.get('desc_evento', '')}",
                                tipo="cc_e",
                                chave=doc.get("chave"),
                            )

            # Persiste o NSU somente APÓS processar os documentos do lote,
            # evitando perder notas caso o processamento falhe no meio do lote.
            if next_ult > 0:
                ult_nsu_retornado = max(next_ult, highest_nsu_saved)
            if next_max > 0:
                max_nsu_retornado = next_max
            update_cert_sync_state(
                clean_cnpj,
                str(ult_nsu_retornado),
                str(max_nsu_retornado),
                f"cStat {final_cstat}: {final_motivo}",
            )

            if final_cstat == "656":  # Consumo Indevido
                # Registra o 656 com backoff exponencial (1h→2h→4h→8h→24h)
                # e atualiza o status visível na UI com a próxima janela.
                info = _registrar_656(clean_cnpj, final_motivo)
                status_msg = (
                    f"🔒 SEFAZ BLOQUEADA (cStat 656) — "
                    f"Tentativa {info['tentativa']}/{len(_COOLDOWN_BACKOFFS_MIN)}. "
                    f"Próxima retentativa em {info['cooldown_min']} min "
                    f"({info['retry_at'].strftime('%d/%m/%Y %H:%M')})"
                )
                update_cert_sync_state(
                    clean_cnpj,
                    str(ult_nsu_retornado),
                    str(max_nsu_retornado),
                    status_msg,
                )
                final_cstat = "656"
                blocked = True
                retry_at_iso = info["retry_at"].isoformat()
                cooldown_min = info["cooldown_min"]
                break
            if final_cstat == "137":  # Nenhum documento localizado
                # Sync bem-sucedido (mesmo sem docs novos) — reseta cooldown 656
                _limpar_656(clean_cnpj)
                break
            if len(documentos) == 0:
                break
            if next_ult >= next_max and next_max > 0:
                break

            # Próxima consulta começa no NSU seguinte ao último recebido (protocolo DF-e).
            cur_nsu = next_ult + 1
        except Exception as loop_err:
            logger.error(f"Erro na sincronização de {clean_cnpj}: {loop_err}")
            break

    # Auto-resolução de resumos (resNFe) pendentes de XML completo
    if final_cstat != "656":
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT chave, nsu FROM nfe_docs
                    WHERE empresa_cnpj = ?
                      AND tipo_doc = 0
                      AND (xml_raw LIKE '%<resNFe%' OR NOT EXISTS (SELECT 1 FROM nfe_items WHERE nfe_items.chave = nfe_docs.chave))
                      AND situacao NOT IN ('Cancelada', 'Denegada')
                    ORDER BY data_emissao DESC
                    LIMIT 3
                """, (clean_cnpj,))
                resumos_pendentes = cursor.fetchall()

            for rp in resumos_pendentes:
                rp_chave = rp["chave"]
                rp_nsu = rp["nsu"]
                try:
                    import time
                    manifestacao_destinatario(
                        chave=rp_chave,
                        cnpj=clean_cnpj,
                        tipo_manifestacao="210210",
                        justificativa="Ciencia da Operacao automatica para download do XML",
                        uf=uf,
                        homologacao=homolog,
                    )
                    time.sleep(0.5)
                    dl_resp = con.consulta_distribuicao(cnpj=clean_cnpj, chave=rp_chave)
                    if dl_resp.status_code == 200:
                        dl_parsed = parse_distribuicao_xml(dl_resp.text)
                        for dl_doc in dl_parsed.get("documentos", []):
                            if dl_doc.get("tag") in ("nfeProc", "NFe") and dl_doc.get("xml_raw"):
                                dl_dados = parse_nfe_xml(dl_doc["xml_raw"].encode("utf-8"))
                                dl_dados["nsu"] = rp_nsu
                                dl_dados["empresa_cnpj"] = clean_cnpj
                                save_nfe_doc(dl_dados, xml_raw=dl_doc["xml_raw"], empresa_cnpj=clean_cnpj)
                                total_docs_saved += 1
                                logger.info(f"[Auto-Cura] XML completo recuperado para NF-e {rp_chave}")
                                break
                except Exception as rec_err:
                    logger.debug(f"[Auto-Cura] Tentativa para {rp_chave}: {rec_err}")
        except Exception:
            pass

    status_str = f"cStat {final_cstat} - {total_docs_saved} notas baixadas" if final_cstat else f"{total_docs_saved} notas baixadas"
    update_cert_sync_state(clean_cnpj, str(ult_nsu_retornado), str(max_nsu_retornado), status_str)

    # Se o sync baixou notas/eventos com sucesso, reseta o cooldown 656
    # (a SEFAZ desbloqueou a empresa).
    if total_docs_saved > 0 or total_events_saved > 0:
        _limpar_656(clean_cnpj)

    result = {
        "success": True,
        "cnpj": clean_cnpj,
        "razao_social": cert_rec.get("razao_social", ""),
        "docs_saved": total_docs_saved,
        "events_saved": total_events_saved,
        "ult_nsu": ult_nsu_retornado,
        "max_nsu": max_nsu_retornado,
        "c_stat": final_cstat,
        "motivo": final_motivo,
    }
    # Se o sync encontrou 656 neste ciclo, anexa info do bloqueio
    if 'blocked' in locals() and blocked:
        result["blocked_by_sefaz"] = True
        result["retry_at"] = retry_at_iso
        result["cooldown_minutes"] = cooldown_min
    return result


def run_sync_iteration(
    cnpj: Optional[str] = None,
    uf: Optional[str] = None,
    homologacao: Optional[bool] = None,
    max_batches: int = 50,
) -> Dict[str, Any]:
    """Executa a sincronização para uma empresa específica ou para todas as empresas cadastradas."""
    set_sync_state("sync_running", "true")
    set_sync_state("last_sync_start", datetime.now().isoformat())

    results: List[Dict[str, Any]] = []
    total_docs = 0
    total_events = 0

    try:
        if cnpj:
            res = run_sync_single_company(cnpj, uf=uf, homologacao=homologacao, max_batches=max_batches)
            results.append(res)
            total_docs += res.get("docs_saved", 0)
            total_events += res.get("events_saved", 0)
        else:
            certs = list_certificates_db()
            for c in certs:
                if c.get("is_active"):
                    res = run_sync_single_company(c["cnpj"], uf=uf, homologacao=homologacao, max_batches=max_batches)
                    results.append(res)
                    total_docs += res.get("docs_saved", 0)
                    total_events += res.get("events_saved", 0)
    finally:
        set_sync_state("sync_running", "false")
        set_sync_state("last_sync_finish", datetime.now().isoformat())
        set_sync_state("last_sync_docs_count", str(total_docs))
        set_sync_state("last_sync_events_count", str(total_events))

    return {
        "success": True,
        "total_empresas": len(results),
        "total_docs_saved": total_docs,
        "total_events_saved": total_events,
        "empresas": results,
        "last_sync_time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def get_sync_status() -> Dict[str, Any]:
    """Retorna o status atual do serviço de sincronização multi-empresa."""
    from backend.database import get_db_connection

    certs = list_certificates_db()
    for c in certs:
        block_info = get_sefaz_block_status(c["cnpj"])
        c["blocked_by_sefaz"] = block_info.get("blocked", False)
        c["retry_at"] = block_info.get("retry_at")
        c["cooldown_minutes"] = block_info.get("cooldown_minutes", 0)
        c["tentativa_656"] = block_info.get("tentativa", 0)

    first_nsu = certs[0].get("last_nsu", "0") if certs else "0"
    first_max = certs[0].get("max_nsu", "0") if certs else "0"

    total_banco = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs")
        row = cursor.fetchone()
        total_banco = row["total"] if row else 0

    return {
        "running": get_sync_state("sync_running", "false") == "true",
        "last_nsu": first_nsu,
        "max_nsu": first_max,
        "last_sync_start": get_sync_state("last_sync_start", ""),
        "last_sync_finish": get_sync_state("last_sync_finish", ""),
        "last_docs_count": int(get_sync_state("last_sync_docs_count", "0") or "0"),
        "last_events_count": int(get_sync_state("last_sync_events_count", "0") or "0"),
        "auto_sync_enabled": get_sync_state("auto_sync_enabled", "true") == "true",
        "auto_sync_interval_mins": int(get_sync_state("auto_sync_interval_mins", "60") or "60"),
        "total_empresas_cadastradas": len(certs),
        "total_banco": total_banco,
        "empresas": certs,
    }


def get_sefaz_block_status(cnpj: str) -> dict:
    """Retorna info de bloqueio da SEFAZ (cStat 656) para uma empresa específica.

    Returns:
        dict com chaves: blocked (bool), retry_at (str ISO), cooldown_minutes (int),
        tentativa (int), motivo (str). blocked=False significa que o sync pode ser feito.
    """
    clean_cnpj = "".join(c for c in str(cnpj) if c.isdigit())
    cooldown_until = _calcular_cooldown_656(clean_cnpj)
    if cooldown_until is None:
        return {"blocked": False, "retry_at": None, "cooldown_minutes": 0, "tentativa": 0, "motivo": ""}
    raw = get_sync_state(_COOLDOWN_KEY_TEMPLATE.format(cnpj=clean_cnpj), "")
    tentativa = 0
    motivo = ""
    if raw:
        try:
            data = json.loads(raw)
            tentativa = int(data.get("tentativa", 0))
            motivo = data.get("motivo", "")
        except Exception:
            pass
    return {
        "blocked": True,
        "retry_at": cooldown_until.isoformat(),
        "cooldown_minutes": max(0, int((cooldown_until - datetime.now()).total_seconds() / 60)),
        "tentativa": tentativa,
        "motivo": motivo,
    }


def check_all_nfe_status(max_checks: int = 20) -> Dict[str, Any]:
    """Verifica o status de NF-e de ENTRADA e SAÍDA de todos os certificados cadastrados.

    Consulta até ``max_checks`` notas autorizadas (qualquer período, qualquer tipo)
    que não foram verificadas na SEFAZ nos últimos 30 minutos. Atualiza o registro
    local quando o status muda (cancelada, inutilizada, denegada).
    """
    from pynfe.processamento.comunicacao import ComunicacaoSefaz

    now = datetime.now()
    last_check_limit = now - timedelta(minutes=30)

    # Cobre NF-e de ENTRADA (tipo_doc=0) e SAÍDA (tipo_doc=1)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chave, empresa_cnpj, data_emissao, situacao, tipo_doc
            FROM nfe_docs
            WHERE situacao = 'Autorizada'
              AND (last_sefaz_check IS NULL OR last_sefaz_check < ?)
            ORDER BY data_emissao DESC
            LIMIT ?
        """, (last_check_limit.isoformat(), max_checks))
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return {"checked": 0, "updated": 0, "message": "Nenhuma NF-e pendente de verificação na SEFAZ."}

    updated = 0
    checked = 0

    for row in rows:
        chave = row["chave"]
        empresa_cnpj = row["empresa_cnpj"]
        tipo_doc = row.get("tipo_doc", 0)
        tipo_label = "Saída" if tipo_doc == 1 else "Entrada"

        cert_rec = get_certificate_record(empresa_cnpj)
        if not cert_rec:
            continue

        cert_path = cert_rec.get("path")
        cert_pwd = cert_rec.get("password")
        uf = (settings.DEFAULT_UF).upper()
        homolog = settings.HOMOLOGACAO

        try:
            con = ComunicacaoSefaz(uf, cert_path, cert_pwd, homologacao=homolog)
            response = con.consulta_nota("nfe", chave)
            parsed = parse_resumo_sefaz(response.text)
            c_stat = parsed.get("c_stat", "")
            motivo = parsed.get("motivo", "")

            new_situacao = row["situacao"]
            if c_stat == "101":
                new_situacao = "Cancelada"
            elif c_stat == "102":
                new_situacao = "Inutilizada"
            elif c_stat in ("110", "205"):
                new_situacao = "Denegada"
            elif c_stat == "100":
                new_situacao = "Autorizada"

            if new_situacao != row["situacao"]:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE nfe_docs
                        SET situacao = ?, updated_at = ?, last_sefaz_check = ?
                        WHERE chave = ?
                    """, (new_situacao, now.isoformat(), now.isoformat(), chave))
                    conn.commit()
                logger.info(
                    f"[NF-e {tipo_label}] Status de {chave} atualizado: "
                    f"{row['situacao']} → {new_situacao} (cStat {c_stat}: {motivo})"
                )
                updated += 1

            checked += 1

            # Atualiza o timestamp da última verificação mesmo se não mudou o status
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE nfe_docs SET last_sefaz_check = ? WHERE chave = ?
                """, (now.isoformat(), chave))
                conn.commit()

        except Exception as e:
            logger.warning(f"[NF-e {tipo_label}] Erro ao verificar {chave} na SEFAZ: {e}")
            continue

    return {"checked": checked, "updated": updated}


def check_emitted_nfe_status(max_checks: int = 5) -> Dict[str, Any]:
    """Compatibilidade retroativa — delega para check_all_nfe_status (cobre entrada e saída)."""
    return check_all_nfe_status(max_checks=max_checks)


async def _background_worker_loop():
    """Loop em segundo plano que sincroniza NF-e de entrada e saída de todos os
    certificados a cada 60 minutos / 1 hora (respeitando a janela oficial de consumo indevido da SEFAZ)."""
    logger.info("Iniciando Robô de Sincronização DF-e Multi-Empresa (intervalo padrão: 60 min / 1 hora)...")
    await asyncio.sleep(10)

    while True:
        try:
            enabled = get_sync_state("auto_sync_enabled", "true") == "true"
            interval_mins = int(get_sync_state("auto_sync_interval_mins", "60") or "60")

            if enabled:
                logger.info("[Robô DF-e] Iniciando ciclo de sincronização para todos os certificados...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, run_sync_iteration)
                logger.info("[Robô DF-e] Verificando status de NF-e de entrada e saída na SEFAZ...")
                await loop.run_in_executor(None, check_all_nfe_status)

                # Rotina diária de backup automático (executa se o último backup foi há mais de 24h)
                try:
                    last_backup_str = get_sync_state("last_backup_time", "")
                    deve_fazer_backup = True
                    if last_backup_str:
                        last_b_dt = datetime.fromisoformat(last_backup_str)
                        if datetime.now() - last_b_dt < timedelta(hours=24):
                            deve_fazer_backup = False
                    if deve_fazer_backup:
                        logger.info("[Robô DF-e] Executando rotina diária de backup fiscal (DB + XMLs)...")
                        from backend.services.backup_service import create_fiscal_backup
                        await loop.run_in_executor(None, create_fiscal_backup, 30)
                except Exception as bkp_err:
                    logger.warning(f"[Robô DF-e] Rotina de backup automático falhou: {bkp_err}")

                logger.info(f"[Robô DF-e] Ciclo concluído. Próxima execução em {interval_mins} minutos.")

            await asyncio.sleep(max(3600, interval_mins * 60))  # mínimo 60 minutos (1 hora)
        except asyncio.CancelledError:
            logger.info("Robô de sincronização multi-empresa finalizado.")
            break
        except Exception as e:
            logger.error(f"Erro no robô de sincronização multi-empresa: {e}")
            await asyncio.sleep(3600)  # aguarda 1 hora antes de tentar novamente


def start_background_sync(loop: Optional[asyncio.AbstractEventLoop] = None):
    global _sync_task
    if _sync_task is None or _sync_task.done():
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
        _sync_task = loop.create_task(_background_worker_loop())


def stop_background_sync():
    global _sync_task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        _sync_task = None


def importar_saidas_por_chaves(
    chaves: List[str],
    empresa_cnpj: str,
    homologacao: Optional[bool] = None,
) -> Dict[str, Any]:
    """Importa NF-es de SAÍDA (emitidas externamente, ex: ERP HostMundo) via chave de 44 dígitos.

    Para cada chave, consulta a SEFAZ via consChNFe usando o certificado da empresa
    informada (que é a EMITENTE) e salva com tipo_doc=1.

    A SEFAZ não distribui NF-es para o emitente via distDFe (apenas destinatário),
    então esta é a forma oficial de o próprio emitente obter o XML autorizado
    de uma NF-e que ele emitiu por outro sistema.

    Returns:
        dict com sucessos, falhas e lista detalhada de resultados por chave.
    """
    from pynfe.processamento.comunicacao import ComunicacaoSefaz

    clean_cnpj = "".join(c for c in str(empresa_cnpj) if c.isdigit())
    homolog = homologacao if homologacao is not None else settings.HOMOLOGACAO

    if not chaves:
        return {"success": False, "error": "Nenhuma chave informada.", "sucessos": 0, "falhas": 0, "resultados": []}
    if not clean_cnpj:
        return {"success": False, "error": "CNPJ da empresa emitente é obrigatório.", "sucessos": 0, "falhas": 0, "resultados": []}

    cert_rec = get_certificate_record(clean_cnpj)
    if not cert_rec:
        return {
            "success": False,
            "error": f"Certificado para CNPJ {clean_cnpj} não encontrado",
            "sucessos": 0, "falhas": 0, "resultados": [],
        }

    # Se a empresa está em cooldown por 656, recusa sem martelar a SEFAZ
    cooldown_until = _calcular_cooldown_656(clean_cnpj)
    if cooldown_until is not None:
        return {
            "success": False,
            "error": f"Empresa bloqueada pela SEFAZ (cStat 656). Retry em {max(0, int((cooldown_until - datetime.now()).total_seconds() / 60))} min.",
            "blocked_by_sefaz": True,
            "sucessos": 0, "falhas": 0, "resultados": [],
        }

    cert_path = cert_rec.get("path")
    cert_pwd = cert_rec.get("password")
    uf = (settings.DEFAULT_UF).upper()

    try:
        con = ComunicacaoSefaz(uf, cert_path, cert_pwd, homologacao=homolog)
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro de conexão/certificado: {str(e)}",
            "sucessos": 0, "falhas": 0, "resultados": [],
        }

    sucessos = 0
    falhas = 0
    resultados = []

    for chave_raw in chaves:
        chave = "".join(c for c in str(chave_raw) if c.isdigit())
        if len(chave) != 44:
            falhas += 1
            resultados.append({
                "chave": chave_raw,
                "success": False,
                "motivo": f"Chave inválida (deve ter 44 dígitos; informado: {len(chave)}).",
            })
            continue

        # Deriva UF pela chave (posições 0-1: código da UF, 35=SP, 33=RJ, 31=MG, etc.)
        uf_chave = "SP" if chave.startswith("35") else "RJ" if chave.startswith("33") else (
            "MG" if chave.startswith("31") else "PR" if chave.startswith("41") else (
            "RS" if chave.startswith("43") else uf
        ))

        try:
            # consChNFe: consulta uma NF-e específica pela chave de 44 dígitos
            resp = con.consulta_distribuicao(cnpj=clean_cnpj, chave=chave)
            if resp.status_code != 200:
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": f"SEFAZ retornou HTTP {resp.status_code}.",
                })
                continue

            parsed = parse_distribuicao_xml(resp.text)
            c_stat = parsed.get("c_stat", "")
            motivo_sefaz = parsed.get("motivo", "")

            if c_stat == "656":
                _registrar_656(clean_cnpj, motivo_sefaz)
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": f"SEFAZ bloqueou (cStat 656): {motivo_sefaz}",
                    "blocked_by_sefaz": True,
                })
                # Para no primeiro 656 para não martelar a SEFAZ com várias chaves
                break

            if c_stat not in ("", "200", "137", "138"):
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": f"cStat {c_stat}: {motivo_sefaz}",
                })
                continue

            documentos = parsed.get("documentos", [])
            xml_encontrado = None
            dados_doc = None
            for doc in documentos:
                tag = doc.get("tag", "")
                xml_raw = doc.get("xml_raw", "")
                if tag in ("nfeProc", "NFe") and xml_raw:
                    xml_encontrado = xml_raw
                    try:
                        dados_doc = parse_nfe_xml(xml_raw.encode("utf-8"))
                    except Exception as parse_err:
                        logger.warning(f"Erro ao parsear XML da chave {chave}: {parse_err}")
                        dados_doc = None
                    break
                elif tag == "resNFe":
                    # resNFe tem apenas resumo (sem produtos). Envia auto-ciência e tenta obter o XML completo
                    try:
                        manifestacao_destinatario(
                            chave=chave,
                            cnpj=clean_cnpj,
                            tipo_manifestacao="210210",
                            justificativa="Ciencia da Operacao automatica para download do XML",
                            uf=uf_chave,
                            homologacao=homolog,
                        )
                        import time
                        time.sleep(0.6)
                        retry_resp = con.consulta_distribuicao(cnpj=clean_cnpj, chave=chave)
                        if retry_resp.status_code == 200:
                            retry_parsed = parse_distribuicao_xml(retry_resp.text)
                            for r_doc in retry_parsed.get("documentos", []):
                                if r_doc.get("tag") in ("nfeProc", "NFe") and r_doc.get("xml_raw"):
                                    xml_encontrado = r_doc["xml_raw"]
                                    dados_doc = parse_nfe_xml(xml_encontrado.encode("utf-8"))
                                    break
                    except Exception as m_err:
                        logger.debug(f"Auto-manifestação na consulta de chave {chave}: {m_err}")

                    if not dados_doc:
                        dados_doc = {
                            "chave": doc.get("chave") or chave,
                            "nome_emitente": doc.get("nome_emitente", ""),
                            "cnpj_emitente": doc.get("cnpj_emitente", ""),
                            "valor_total": doc.get("valor_total", 0),
                            "data_emissao": doc.get("data_emissao", ""),
                            "situacao": doc.get("situacao", "Autorizada"),
                        }
                    break

            if not dados_doc:
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": f"NF-e não localizada para esta chave (cStat {c_stat}: {motivo_sefaz}).",
                })
                continue

            # Validação: verifica se a chave pertence mesmo ao CNPJ informado
            emit_cnpj_xml = (
                dados_doc.get("emitente", {}).get("cnpj")
                or dados_doc.get("cnpj_emitente")
                or dados_doc.get("emitente_cnpj")
                or ""
            )
            emit_digits = "".join(c for c in str(emit_cnpj_xml) if c.isdigit())
            if emit_digits and emit_digits != clean_cnpj:
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": f"NFe pertence a outro CNPJ ({emit_digits}), não a {clean_cnpj}.",
                })
                continue

            # Salva com tipo_doc=1 (saída) e empresa_cnpj=clean_cnpj (a emitente)
            dados_doc["nsu"] = "0"
            dados_doc["empresa_cnpj"] = clean_cnpj
            dados_doc["tipo_doc"] = 1
            dados_doc["data_autorizacao"] = dados_doc.get("data_autorizacao") or datetime.now().isoformat()
            dados_doc["situacao"] = dados_doc.get("situacao") or "Autorizada"

            if save_nfe_doc(dados_doc, xml_raw=xml_encontrado, empresa_cnpj=clean_cnpj):
                sucessos += 1
                resultados.append({
                    "chave": chave,
                    "success": True,
                    "motivo": f"Importada: NF-e {dados_doc.get('numero', '?')} (R$ {float(dados_doc.get('valor_total') or dados_doc.get('totais', {}).get('v_nf') or 0):,.2f})",
                })
                dispatch_notification(
                    title=f"Nova NF-e de Saída importada ({cert_rec.get('razao_social', clean_cnpj)})",
                    message=f"NF-e {dados_doc.get('numero', '?')} — R$ {float(dados_doc.get('valor_total') or dados_doc.get('totais', {}).get('v_nf') or 0):,.2f}",
                    tipo="nfe_nova",
                    chave=chave,
                )
            else:
                falhas += 1
                resultados.append({
                    "chave": chave,
                    "success": False,
                    "motivo": "Falha ao salvar NF-e no banco (verifique se a chave tem 44 dígitos e é uma NF-e).",
                })

        except Exception as e:
            falhas += 1
            logger.warning(f"Erro ao consultar chave {chave} na SEFAZ: {e}")
            resultados.append({
                "chave": chave,
                "success": False,
                "motivo": f"Erro na consulta: {str(e)[:200]}",
            })

    return {
        "success": True,
        "empresa_cnpj": clean_cnpj,
        "razao_social": cert_rec.get("razao_social", ""),
        "sucessos": sucessos,
        "falhas": falhas,
        "total": len(chaves),
        "resultados": resultados,
    }
