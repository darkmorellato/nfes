"""
Módulo de Auditoria de Saltos de Numeração de Saídas (Gap Detector).

Identifica quebras de sequência numérica em NF-es de saída emitidas por cada filial e série,
cruzando com a tabela de inutilizações da SEFAZ para garantir conformidade contábil e fiscal.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection
from backend.database.certificates import list_certificates_db

logger = logging.getLogger(__name__)


def auditar_saltos_numeracao(
    empresa_cnpj: Optional[str] = None,
    serie: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analisa a sequência de numeração de todas as notas fiscais de saída emitidas
    pelas empresas cadastradas e identifica lacunas/gaps na numeração.
    """
    clean_cnpj = ''.join(c for c in str(empresa_cnpj) if c.isdigit()) if empresa_cnpj else None

    todas_empresas = list_certificates_db()
    if clean_cnpj:
        empresas_alvo = [e for e in todas_empresas if e['cnpj'] == clean_cnpj]
        if not empresas_alvo:
            empresas_alvo = [{'cnpj': clean_cnpj, 'razao_social': f'CNPJ {clean_cnpj}'}]
    else:
        empresas_alvo = todas_empresas

    relatorio_empresas: List[Dict[str, Any]] = []
    total_gaps_grupo = 0
    total_inutilizados_grupo = 0
    total_faltando_grupo = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        for emp in empresas_alvo:
            cnpj = emp['cnpj']
            razao = emp.get('razao_social', '')

            q_series = """
                SELECT DISTINCT COALESCE(NULLIF(serie, ''), '1') as serie_num
                FROM nfe_docs
                WHERE (empresa_cnpj = ? OR emitente_cnpj = ?) AND (tipo_doc = 1 OR emitente_cnpj = ?)
            """
            cursor.execute(q_series, (cnpj, cnpj, cnpj))
            series_rows = cursor.fetchall()
            series_list = [r['serie_num'] for r in series_rows] if series_rows else ['1']
            if serie and serie.strip():
                series_list = [s for s in series_list if s == serie.strip()]

            series_auditadas = []

            for s_num in series_list:
                q_notas = """
                    SELECT chave, numero, CAST(numero AS INTEGER) as num_int, data_emissao, situacao, valor_total, destinatario_nome
                    FROM nfe_docs
                    WHERE (empresa_cnpj = ? OR emitente_cnpj = ?)
                      AND (tipo_doc = 1 OR emitente_cnpj = ?)
                      AND COALESCE(NULLIF(serie, ''), '1') = ?
                      AND numero IS NOT NULL AND numero != ''
                    ORDER BY CAST(numero AS INTEGER) ASC
                """
                cursor.execute(q_notas, (cnpj, cnpj, cnpj, s_num))
                notas_rows = cursor.fetchall()

                notas_map: Dict[int, Dict[str, Any]] = {}
                for r in notas_rows:
                    n_int = r['num_int']
                    if n_int and n_int > 0:
                        notas_map[n_int] = dict(r)

                q_inut = """
                    SELECT id, ano, serie, numero_inicial, numero_final, protocolo, justificativa, COALESCE(data_homologacao, created_at) as data_inutilizacao
                    FROM nfe_inutilizacoes
                    WHERE empresa_cnpj = ? AND CAST(serie AS TEXT) = ?
                """
                cursor.execute(q_inut, (cnpj, s_num))
                inut_rows = cursor.fetchall()

                inut_set: Dict[int, Dict[str, Any]] = {}
                for inut in inut_rows:
                    ini = int(inut['numero_inicial'] or 0)
                    fim = int(inut['numero_final'] or ini)
                    for n in range(ini, fim + 1):
                        inut_set[n] = dict(inut)

                if not notas_map and not inut_set:
                    continue

                todos_numeros = sorted(list(notas_map.keys()) + list(inut_set.keys()))
                min_num = min(todos_numeros) if todos_numeros else 1
                max_num = max(todos_numeros) if todos_numeros else 1

                gaps: List[Dict[str, Any]] = []
                qtd_faltando = 0
                qtd_inutilizados = 0

                i = min_num
                while i <= max_num:
                    if i in notas_map:
                        i += 1
                        continue

                    gap_inicio = i
                    while i <= max_num and i not in notas_map:
                        i += 1
                    gap_fim = i - 1
                    qtd_gap = gap_fim - gap_inicio + 1

                    inutilizados_no_gap = [n for n in range(gap_inicio, gap_fim + 1) if n in inut_set]

                    if len(inutilizados_no_gap) == qtd_gap:
                        status_gap = 'Inutilizada'
                        badge_class = 'badge-ambiente'
                        detalhe = f'Inutilizada na SEFAZ (Prot: {inut_set[gap_inicio].get("protocolo", "--")})'
                        qtd_inutilizados += qtd_gap
                    elif len(inutilizados_no_gap) > 0:
                        status_gap = 'Parcialmente Inutilizada'
                        badge_class = 'tag-pill'
                        detalhe = f'{len(inutilizados_no_gap)} de {qtd_gap} números inutilizados'
                        qtd_inutilizados += len(inutilizados_no_gap)
                        qtd_faltando += (qtd_gap - len(inutilizados_no_gap))
                    else:
                        status_gap = '🚨 Faltando / Salto'
                        badge_class = 'badge-teste-tag'
                        detalhe = 'Sem registro de emissão ou inutilização na SEFAZ'
                        qtd_faltando += qtd_gap

                    gaps.append({
                        'numero_inicio': gap_inicio,
                        'numero_fim': gap_fim,
                        'quantidade': qtd_gap,
                        'faixa_formatada': f'Nº {gap_inicio}' if gap_inicio == gap_fim else f'Nº {gap_inicio} a {gap_fim}',
                        'status': status_gap,
                        'badge_class': badge_class,
                        'detalhes': detalhe,
                        'inutilizado': len(inutilizados_no_gap) == qtd_gap,
                    })

                total_gaps_grupo += len(gaps)
                total_inutilizados_grupo += qtd_inutilizados
                total_faltando_grupo += qtd_faltando

                series_auditadas.append({
                    'serie': s_num,
                    'menor_numero': min_num,
                    'maior_numero': max_num,
                    'total_esperado': max_num - min_num + 1 if todos_numeros else 0,
                    'total_presente': len(notas_map),
                    'total_inutilizados': qtd_inutilizados,
                    'total_faltando': qtd_faltando,
                    'tem_gaps': len(gaps) > 0,
                    'gaps': gaps,
                })

            if series_auditadas:
                relatorio_empresas.append({
                    'cnpj': cnpj,
                    'razao_social': razao,
                    'series': series_auditadas,
                })

    return {
        'success': True,
        'total_empresas_auditadas': len(relatorio_empresas),
        'total_gaps_encontrados': total_gaps_grupo,
        'total_numeros_inutilizados': total_inutilizados_grupo,
        'total_numeros_faltando': total_faltando_grupo,
        'empresas': relatorio_empresas,
    }
