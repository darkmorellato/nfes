import os
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from backend.config import settings
from backend.database import get_db_connection, XML_STORAGE_DIR, DATA_DIR, DB_PATH
from backend.database.certificates import list_certificates_db


def _format_bytes(size: int) -> str:
    """Formata bytes em formato legível (KB, MB, GB)."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _montar_condicoes_busca(
    termo: Optional[str] = None,
    cnpj: Optional[str] = None,
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    situacao: Optional[str] = None,
    tipo_teste: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    """Gera cláusula WHERE segura com parâmetros para filtros de limpeza."""
    where_clauses = ["1=1"]
    params: List[Any] = []

    if empresa_cnpj and empresa_cnpj.strip():
        emp_digits = "".join(c for c in empresa_cnpj if c.isdigit())
        if emp_digits:
            where_clauses.append(
                "(empresa_cnpj = ? OR emitente_cnpj LIKE ? OR destinatario_cnpj LIKE ?)"
            )
            params.extend([emp_digits, f"%{emp_digits}%", f"%{emp_digits}%"])

    if termo and termo.strip():
        t = f"%{termo.strip().upper()}%"
        where_clauses.append(
            "(UPPER(emitente_nome) LIKE ? OR UPPER(destinatario_nome) LIKE ? OR chave LIKE ? OR numero LIKE ?)"
        )
        params.extend([t, t, t, t])

    if cnpj and cnpj.strip():
        c_digits = "".join(c for c in cnpj if c.isdigit())
        if c_digits:
            c_term = f"%{c_digits}%"
            where_clauses.append(
                "(emitente_cnpj LIKE ? OR destinatario_cnpj LIKE ? OR empresa_cnpj LIKE ?)"
            )
            params.extend([c_term, c_term, c_term])

    if data_inicio and data_inicio.strip():
        where_clauses.append("SUBSTR(data_emissao, 1, 10) >= ?")
        params.append(data_inicio.strip()[:10])

    if data_fim and data_fim.strip():
        where_clauses.append("SUBSTR(data_emissao, 1, 10) <= ?")
        params.append(data_fim.strip()[:10])

    if situacao and situacao.strip() and situacao.strip().lower() != "todas":
        where_clauses.append("situacao = ?")
        params.append(situacao.strip())

    # Presets de teste
    if tipo_teste == "homologacao":
        where_clauses.append(
            """(
                UPPER(emitente_nome) LIKE '%HOMOLOG%' OR UPPER(emitente_nome) LIKE '%TESTE%'
                OR UPPER(emitente_nome) LIKE '%SEM VALOR%' OR UPPER(emitente_nome) LIKE '%TREINAMENTO%'
                OR UPPER(destinatario_nome) LIKE '%HOMOLOG%' OR UPPER(destinatario_nome) LIKE '%TESTE%'
                OR UPPER(destinatario_nome) LIKE '%SEM VALOR%'
                OR emitente_cnpj IN ('00000000000000', '99999999999999', '11111111111111')
                OR destinatario_cnpj IN ('00000000000000', '99999999999999', '11111111111111')
            )"""
        )
    elif tipo_teste == "zeradas":
        where_clauses.append("valor_total <= 0.001")
    elif tipo_teste == "sem_itens":
        where_clauses.append("chave NOT IN (SELECT DISTINCT chave FROM nfe_items)")

    return " AND ".join(where_clauses), params


def preview_limpeza_nfes(
    termo: Optional[str] = None,
    cnpj: Optional[str] = None,
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    situacao: Optional[str] = None,
    tipo_teste: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Busca e retorna prévia de NF-es que atendem aos filtros antes da exclusão."""
    where_sql, params = _montar_condicoes_busca(
        termo=termo,
        cnpj=cnpj,
        empresa_cnpj=empresa_cnpj,
        data_inicio=data_inicio,
        data_fim=data_fim,
        situacao=situacao,
        tipo_teste=tipo_teste,
    )


    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Contagem e valor total somado
        cursor.execute(
            f"SELECT COUNT(*) as total, COALESCE(SUM(valor_total), 0.0) as valor_total FROM nfe_docs WHERE {where_sql}",
            params,
        )
        agg_row = cursor.fetchone()
        total_encontradas = agg_row["total"] if agg_row else 0
        valor_total_somado = float(agg_row["valor_total"]) if agg_row else 0.0

        # Amostra de itens
        cursor.execute(
            f"""
            SELECT chave, empresa_cnpj, numero, serie, modelo, tipo_doc,
                   emitente_cnpj, emitente_nome, emitente_uf,
                   destinatario_cnpj, destinatario_nome, destinatario_uf,
                   data_emissao, valor_total, situacao, has_xml
            FROM nfe_docs
            WHERE {where_sql}
            ORDER BY data_emissao DESC
            LIMIT ?
            """,
            params + [limit],
        )
        rows = cursor.fetchall()

    itens = []
    for r in rows:
        ch = r["chave"]
        xml_path = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
        tem_xml_disco = os.path.exists(xml_path)
        itens.append({
            "chave": ch,
            "empresa_cnpj": r["empresa_cnpj"] or "",
            "numero": r["numero"] or "",
            "serie": r["serie"] or "",
            "tipo_doc": r["tipo_doc"],
            "emitente_cnpj": r["emitente_cnpj"] or "",
            "emitente_nome": r["emitente_nome"] or "",
            "destinatario_cnpj": r["destinatario_cnpj"] or "",
            "destinatario_nome": r["destinatario_nome"] or "",
            "data_emissao": r["data_emissao"] or "",
            "valor_total": float(r["valor_total"] or 0.0),
            "situacao": r["situacao"] or "",
            "has_xml": bool(r["has_xml"]),
            "xml_exists_on_disk": tem_xml_disco,
        })

    return {
        "success": True,
        "total_encontradas": total_encontradas,
        "valor_total_somado": round(valor_total_somado, 2),
        "limite_exibicao": limit,
        "itens": itens,
    }


def executar_limpeza_nfes(
    termo: Optional[str] = None,
    cnpj: Optional[str] = None,
    empresa_cnpj: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    situacao: Optional[str] = None,
    tipo_teste: Optional[str] = None,
    chaves_selecionadas: Optional[List[str]] = None,
    apagar_xml_disco: bool = True,
    apagar_firestore: bool = True,
) -> Dict[str, Any]:
    """Exclui com segurança as NF-es especificadas do SQLite, arquivos XML em disco e Cloud Firestore."""
    target_chaves: List[str] = []
    target_empresas: List[str] = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if chaves_selecionadas and len(chaves_selecionadas) > 0:
            placeholders = ",".join(["?"] * len(chaves_selecionadas))
            cursor.execute(
                f"SELECT chave, empresa_cnpj FROM nfe_docs WHERE chave IN ({placeholders})",
                chaves_selecionadas,
            )
            rows = cursor.fetchall()
            for r in rows:
                target_chaves.append(r["chave"])
                if r["empresa_cnpj"]:
                    target_empresas.append(r["empresa_cnpj"])
        else:
            where_sql, params = _montar_condicoes_busca(
                termo=termo,
                cnpj=cnpj,
                empresa_cnpj=empresa_cnpj,
                data_inicio=data_inicio,
                data_fim=data_fim,
                situacao=situacao,
                tipo_teste=tipo_teste,
            )
            cursor.execute(f"SELECT chave, empresa_cnpj FROM nfe_docs WHERE {where_sql}", params)
            rows = cursor.fetchall()
            for r in rows:
                target_chaves.append(r["chave"])
                if r["empresa_cnpj"]:
                    target_empresas.append(r["empresa_cnpj"])

        if not target_chaves:
            return {
                "success": True,
                "deleted_count": 0,
                "xmls_deleted": 0,
                "firestore_deleted": 0,
                "message": "Nenhuma NF-e localizada para os critérios informados.",
            }

        batch_size = 300
        for i in range(0, len(target_chaves), batch_size):
            slice_chaves = target_chaves[i:i + batch_size]
            ph = ",".join(["?"] * len(slice_chaves))

            cursor.execute(f"DELETE FROM nfe_conferencia_items WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_conferencia WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_duplicatas WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_contas_receber WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_events WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_items WHERE chave IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM estoque_movimentacoes WHERE chave_nfe IN ({ph})", slice_chaves)
            cursor.execute(f"DELETE FROM nfe_docs WHERE chave IN ({ph})", slice_chaves)

        conn.commit()

    xmls_deleted = 0
    if apagar_xml_disco:
        for ch in target_chaves:
            xml_file = os.path.join(XML_STORAGE_DIR, f"{ch}.xml")
            try:
                if os.path.exists(xml_file):
                    os.remove(xml_file)
                    xmls_deleted += 1
            except Exception:
                pass

    firestore_deleted = 0
    if apagar_firestore:
        try:
            from backend.services.firestore_service import delete_nfes_from_firestore
            firestore_deleted = delete_nfes_from_firestore(target_chaves, target_empresas)
        except Exception:
            pass

    return {
        "success": True,
        "deleted_count": len(target_chaves),
        "xmls_deleted": xmls_deleted,
        "firestore_deleted": firestore_deleted,
        "message": f"Limpeza concluída com sucesso: {len(target_chaves)} NF-e(s) apagada(s) do banco local, {xmls_deleted} XML(s) removido(s) do disco e {firestore_deleted} documento(s) na nuvem.",
    }


def auditoria_xmls_orfaos() -> Dict[str, Any]:
    """Varre o diretório data/xmls/ e identifica XMLs órfãos que não estão registrados no SQLite."""
    os.makedirs(XML_STORAGE_DIR, exist_ok=True)
    all_disk_files = glob.glob(os.path.join(XML_STORAGE_DIR, "*.xml"))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chave FROM nfe_docs")
        db_chaves = {row["chave"] for row in cursor.fetchall() if row["chave"]}

    orfaos = []
    total_orphan_bytes = 0

    for fpath in all_disk_files:
        fname = os.path.basename(fpath)
        chave_candidate = os.path.splitext(fname)[0]
        try:
            st = os.stat(fpath)
            fsize = st.st_size
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            fsize = 0
            mtime = ""

        if chave_candidate not in db_chaves or fsize == 0:
            total_orphan_bytes += fsize
            orfaos.append({
                "filename": fname,
                "chave": chave_candidate if len(chave_candidate) == 44 else "",
                "size_bytes": fsize,
                "size_formatted": _format_bytes(fsize),
                "modified_at": mtime,
                "is_corrupt_or_empty": fsize == 0,
            })

    return {
        "success": True,
        "total_xmls_disco": len(all_disk_files),
        "total_docs_banco": len(db_chaves),
        "total_orfaos": len(orfaos),
        "tamanho_orfaos_bytes": total_orphan_bytes,
        "tamanho_orfaos_formatado": _format_bytes(total_orphan_bytes),
        "amostra_orfaos": orfaos[:100],
    }


def apagar_xmls_orfaos() -> Dict[str, Any]:
    """Exclui com segurança todos os arquivos XML do disco que não possuem registro no banco."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT chave FROM nfe_docs")
        db_chaves = {row["chave"] for row in cursor.fetchall() if row["chave"]}

    all_disk_files = glob.glob(os.path.join(XML_STORAGE_DIR, "*.xml"))
    deleted_count = 0
    freed_bytes = 0

    for fpath in all_disk_files:
        fname = os.path.basename(fpath)
        chave_candidate = os.path.splitext(fname)[0]
        try:
            fsize = os.path.getsize(fpath)
        except Exception:
            fsize = 0

        if chave_candidate not in db_chaves or fsize == 0:
            try:
                os.remove(fpath)
                deleted_count += 1
                freed_bytes += fsize
            except Exception:
                pass

    return {
        "success": True,
        "deleted_files": deleted_count,
        "freed_bytes": freed_bytes,
        "freed_formatted": _format_bytes(freed_bytes),
        "message": f"Limpeza concluída com sucesso: {deleted_count} arquivo(s) XML órfão(s) apagado(s), liberando {_format_bytes(freed_bytes)} em disco.",
    }


def auditoria_rapida_base() -> Dict[str, Any]:
    """Retorna diagnóstico completo e rápido do estado do banco, armazenamento e sincronização."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs")
        total_docs = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs WHERE tipo_doc = 0")
        total_entradas = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs WHERE tipo_doc = 1")
        total_saidas = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs WHERE has_xml = 1")
        total_com_xml = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM nfe_docs WHERE has_xml = 0")
        total_sem_xml = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) as total, COALESCE(SUM(valor_total), 0.0) as valor_total
            FROM nfe_docs
            WHERE UPPER(emitente_nome) LIKE '%HOMOLOG%' OR UPPER(emitente_nome) LIKE '%TESTE%'
               OR UPPER(emitente_nome) LIKE '%SEM VALOR%' OR UPPER(emitente_nome) LIKE '%TREINAMENTO%'
               OR UPPER(destinatario_nome) LIKE '%HOMOLOG%' OR UPPER(destinatario_nome) LIKE '%TESTE%'
               OR UPPER(destinatario_nome) LIKE '%SEM VALOR%'
               OR emitente_cnpj IN ('00000000000000', '99999999999999', '11111111111111')
               OR destinatario_cnpj IN ('00000000000000', '99999999999999', '11111111111111')
               OR valor_total <= 0.001
        """)
        row_teste = cursor.fetchone()
        total_testes = row_teste["total"] if row_teste else 0
        valor_testes = float(row_teste["valor_total"]) if row_teste else 0.0

        cursor.execute("""
            SELECT emitente_cnpj, emitente_nome, emitente_uf,
                   COUNT(*) as total_notas,
                   SUM(valor_total) as valor_total,
                   MAX(data_emissao) as ultima_emissao
            FROM nfe_docs
            WHERE emitente_nome IS NOT NULL AND emitente_nome != ''
            GROUP BY emitente_cnpj, emitente_nome
            ORDER BY total_notas DESC
            LIMIT 10
        """)
        top_emitentes = []
        for r in cursor.fetchall():
            nome = r["emitente_nome"] or ""
            is_test = any(k in nome.upper() for k in ["HOMOLOG", "TESTE", "SEM VALOR", "TREINAMENTO"])
            top_emitentes.append({
                "cnpj": r["emitente_cnpj"] or "",
                "nome": nome,
                "uf": r["emitente_uf"] or "",
                "total_notas": r["total_notas"],
                "valor_total": round(float(r["valor_total"] or 0.0), 2),
                "ultima_emissao": r["ultima_emissao"] or "",
                "is_teste_suspeito": is_test,
            })

        cursor.execute("""
            SELECT destinatario_cnpj, destinatario_nome, destinatario_uf,
                   COUNT(*) as total_notas,
                   SUM(valor_total) as valor_total,
                   MAX(data_emissao) as ultima_emissao
            FROM nfe_docs
            WHERE destinatario_nome IS NOT NULL AND destinatario_nome != ''
            GROUP BY destinatario_cnpj, destinatario_nome
            ORDER BY total_notas DESC
            LIMIT 10
        """)
        top_destinatarios = []
        for r in cursor.fetchall():
            top_destinatarios.append({
                "cnpj": r["destinatario_cnpj"] or "",
                "nome": r["destinatario_nome"] or "",
                "uf": r["destinatario_uf"] or "",
                "total_notas": r["total_notas"],
                "valor_total": round(float(r["valor_total"] or 0.0), 2),
                "ultima_emissao": r["ultima_emissao"] or "",
            })

    certificados = list_certificates_db()
    empresas_audit = []
    for c in certificados:
        empresas_audit.append({
            "cnpj": c.get("cnpj", ""),
            "razao_social": c.get("razao_social", ""),
            "valid_to": c.get("valid_to", ""),
            "days_remaining": c.get("days_remaining", 0),
            "last_nsu": c.get("last_nsu", "0"),
            "max_nsu": c.get("max_nsu", "0"),
            "last_sync_time": c.get("last_sync_time", "Nunca"),
            "last_sync_status": c.get("last_sync_status", "Pendente"),
            "is_active": bool(c.get("is_active", 1)),
        })

    db_size = 0
    if os.path.exists(DB_PATH):
        try:
            db_size = os.path.getsize(DB_PATH)
        except Exception:
            pass

    xml_files = glob.glob(os.path.join(XML_STORAGE_DIR, "*.xml"))
    total_xmls_disco = len(xml_files)
    xml_dir_size = 0
    for xf in xml_files:
        try:
            xml_dir_size += os.path.getsize(xf)
        except Exception:
            pass

    orphan_count = max(0, total_xmls_disco - total_com_xml)
    firestore_configured = bool(settings.FIREBASE_PROJECT_ID and settings.FIREBASE_API_KEY)

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "resumo_notas": {
            "total_docs": total_docs,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "total_com_xml": total_com_xml,
            "total_sem_xml": total_sem_xml,
            "total_testes_identificados": total_testes,
            "valor_testes_somado": round(valor_testes, 2),
        },
        "armazenamento": {
            "db_size_bytes": db_size,
            "db_size_formatado": _format_bytes(db_size),
            "xmls_count_disco": total_xmls_disco,
            "xmls_dir_size_bytes": xml_dir_size,
            "xmls_dir_size_formatado": _format_bytes(xml_dir_size),
            "xmls_orfaos_estimados": orphan_count,
        },
        "firestore": {
            "configurado": firestore_configured,
            "project_id": settings.FIREBASE_PROJECT_ID if firestore_configured else "Não configurado",
        },
        "empresas": empresas_audit,
        "top_emitentes": top_emitentes,
        "top_destinatarios": top_destinatarios,
    }
