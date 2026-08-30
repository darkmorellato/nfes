import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.config import settings
from backend.services.cert_service import (
    get_cert_path,
    get_cert_password,
    get_cert_cnpj,
    list_all_certificates,
)
from backend.services.danfe_service import parse_nfe_xml, parse_distribuicao_xml, parse_resumo_sefaz
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
                            title=f"Resumo de NF-e ({cert_rec.get('razao_social', clean_cnpj)})",
                            message=f"Emitente: {doc.get('nome_emitente', '')} | Valor: R$ {float(doc.get('valor_total', 0)):,.2f}",
                            tipo="nfe_nova",
                            chave=doc.get("chave"),
                        )
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
                # Se a SEFAZ indicou um ultNSU específico no cabeçalho de rejeição 656, atualiza o NSU para a próxima
                if next_ult > 0:
                    update_cert_sync_state(clean_cnpj, str(next_ult), str(max_nsu_retornado), f"cStat 656: {final_motivo}")
                break
            if final_cstat == "137":  # Nenhum documento localizado
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

    status_str = f"cStat {final_cstat} - {total_docs_saved} notas baixadas" if final_cstat else f"{total_docs_saved} notas baixadas"
    update_cert_sync_state(clean_cnpj, str(ult_nsu_retornado), str(max_nsu_retornado), status_str)

    return {
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
                logger.info(f"[Robô DF-e] Iniciando ciclo de sincronização para todos os certificados...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, run_sync_iteration)
                logger.info("[Robô DF-e] Verificando status de NF-e de entrada e saída na SEFAZ...")
                await loop.run_in_executor(None, check_all_nfe_status)
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
