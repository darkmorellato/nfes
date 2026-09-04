"""
Serviço de Backup e Retenção Fiscal de Alta Confiabilidade.

Atende às exigências do Ajuste SINIEF 07/05 e art. 173 do CTN (guarda obrigatória
por 5 anos de documentos fiscais eletrônicos).

Funcionalidades:
- Snapshot online e consistente do banco SQLite usando a API nativa sqlite3.Connection.backup().
- Compactação do banco e de todo o diretório de XMLs (ZIP com DEFLATE).
- Cálculo de hash SHA-256 para garantia de integridade e não-repúdio.
- Política automática de retenção (mantém os últimos N backups, default: 30).
- Verificação de integridade pós-geração.
"""
from __future__ import annotations

import os
import sqlite3
import zipfile
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection, XML_STORAGE_DIR, DATA_DIR
from backend.database.sync_state import set_sync_state

logger = logging.getLogger("nfe.backup")

BACKUP_DIR = os.path.join(DATA_DIR, "backups")


def _ensure_backup_dir() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def _calcular_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def create_fiscal_backup(max_retention: int = 30) -> Dict[str, Any]:
    """Cria um backup completo dos dados fiscais (Banco SQLite + XMLs).

    Retorna um dicionário com os metadados do backup gerado.
    """
    _ensure_backup_dir()
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    zip_filename = f"backup_nfe_{timestamp_str}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_filename)

    # Informações de negócio no momento do snapshot
    total_docs = 0
    total_valor = 0.0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) as tot, COALESCE(SUM(valor_total), 0) as val FROM nfe_docs")
            r = cursor.fetchone()
            if r:
                total_docs = r["tot"]
                total_valor = float(r["val"])
        except Exception as e:
            logger.warning(f"[Backup] Erro ao consultar totais: {e}")

    # Cria snapshot consistente do SQLite em arquivo temporário via conn.backup()
    temp_db_snapshot = os.path.join(BACKUP_DIR, f"_temp_{timestamp_str}.db")
    try:
        with get_db_connection() as src_conn:
            dest_conn = sqlite3.connect(temp_db_snapshot)
            src_conn.backup(dest_conn)
            dest_conn.close()

        xml_count = 0
        db_size = os.path.getsize(temp_db_snapshot)

        # Monta o arquivo ZIP contendo o SQLite snapshot e todos os XMLs
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # 1. Banco de dados
            zf.write(temp_db_snapshot, arcname="database/nfe_database.db")

            # 2. XMLs armazenados
            if os.path.exists(XML_STORAGE_DIR):
                for root, _, files in os.walk(XML_STORAGE_DIR):
                    for file in files:
                        if file.endswith(".xml"):
                            abs_file = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_file, DATA_DIR)
                            zf.write(abs_file, arcname=rel_path)
                            xml_count += 1

            # 3. Metadados do backup gravados dentro do próprio ZIP
            meta_internal = {
                "created_at": now.isoformat(),
                "legal_retention_until": f"{now.year + 5}-12-31",
                "total_docs": total_docs,
                "total_valor": total_valor,
                "xml_count": xml_count,
                "db_size_bytes": db_size,
                "schema_version": "1.0.0",
                "app_version": "1.0.0",
            }
            zf.writestr("metadata.json", json.dumps(meta_internal, indent=2))

        # Testa integridade física do ZIP gerado
        with zipfile.ZipFile(zip_path, "r") as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                raise RuntimeError(f"Arquivo corrompido detectado no zip gerado: {corrupt}")

        zip_size = os.path.getsize(zip_path)
        zip_sha256 = _calcular_sha256(zip_path)

        meta = {
            "filename": zip_filename,
            "path": zip_path,
            "size_bytes": zip_size,
            "size_mb": round(zip_size / (1024 * 1024), 2),
            "sha256": zip_sha256,
            "created_at": now.isoformat(),
            "created_at_br": now.strftime("%d/%m/%Y %H:%M:%S"),
            "legal_retention_until": f"{now.year + 5}-12-31",
            "total_docs": total_docs,
            "total_valor": total_valor,
            "xml_count": xml_count,
            "status": "VALIDO",
        }

        # Atualiza estado no sync_state
        set_sync_state("last_backup_time", now.isoformat())
        set_sync_state("last_backup_filename", zip_filename)
        set_sync_state("last_backup_sha256", zip_sha256)
        set_sync_state("last_backup_docs", str(total_docs))
        set_sync_state("last_backup_xmls", str(xml_count))

        # Aplica política de retenção (limpa backups antigos além do limite)
        _aplicar_politica_retencao(max_retention=max_retention)

        logger.info(
            f"[Backup] Backup fiscal concluído com sucesso: {zip_filename} "
            f"({meta['size_mb']} MB | {xml_count} XMLs | SHA256: {zip_sha256[:12]}...)"
        )
        return {"success": True, "backup": meta}

    except Exception as e:
        logger.error(f"[Backup] Erro crítico ao criar backup fiscal: {e}")
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
        return {"success": False, "error": str(e)}

    finally:
        # Sempre limpa o arquivo temporário do snapshot
        if os.path.exists(temp_db_snapshot):
            try:
                os.remove(temp_db_snapshot)
            except Exception:
                pass


def _aplicar_politica_retencao(max_retention: int = 30) -> int:
    """Remove backups excedentes mantendo apenas os `max_retention` mais recentes."""
    _ensure_backup_dir()
    arquivos = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("backup_nfe_") and f.endswith(".zip"):
            caminho = os.path.join(BACKUP_DIR, f)
            try:
                mtime = os.path.getmtime(caminho)
                arquivos.append((mtime, caminho))
            except Exception:
                pass

    # Ordena do mais antigo para o mais novo
    arquivos.sort(key=lambda x: x[0])
    excedentes = len(arquivos) - max_retention
    removidos = 0
    if excedentes > 0:
        for _, caminho in arquivos[:excedentes]:
            try:
                os.remove(caminho)
                removidos += 1
                logger.info(f"[Backup] Retenção: removido backup antigo {os.path.basename(caminho)}")
            except Exception as e:
                logger.warning(f"[Backup] Falha ao remover backup antigo {caminho}: {e}")
    return removidos


def list_backups() -> List[Dict[str, Any]]:
    """Lista todos os backups fiscais existentes no diretório de backups."""
    _ensure_backup_dir()
    lista: List[Dict[str, Any]] = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("backup_nfe_") and f.endswith(".zip"):
            p = os.path.join(BACKUP_DIR, f)
            try:
                sz = os.path.getsize(p)
                mtime = datetime.fromtimestamp(os.path.getmtime(p))
                sha = _calcular_sha256(p)
                lista.append({
                    "filename": f,
                    "size_bytes": sz,
                    "size_mb": round(sz / (1024 * 1024), 2),
                    "created_at": mtime.isoformat(),
                    "created_at_br": mtime.strftime("%d/%m/%Y %H:%M:%S"),
                    "sha256": sha,
                })
            except Exception:
                pass

    # Mais recentes primeiro
    lista.sort(key=lambda x: x["created_at"], reverse=True)
    return lista


def get_backup_path(filename: str) -> Optional[str]:
    """Retorna o caminho seguro do arquivo de backup evitando directory traversal."""
    _ensure_backup_dir()
    clean_name = os.path.basename(filename)
    if not clean_name.startswith("backup_nfe_") or not clean_name.endswith(".zip"):
        return None
    full_path = os.path.abspath(os.path.join(BACKUP_DIR, clean_name))
    if not full_path.startswith(os.path.abspath(BACKUP_DIR)):
        return None
    if os.path.exists(full_path):
        return full_path
    return None
