"""Utilitários compartilhados."""
from __future__ import annotations


def decode_xml(conteudo) -> str:
    """
    Decodifica bytes de XML fiscal sem perder caracteres silenciosamente.

    ``errors="ignore"`` (usado antes) descartava bytes inválidos e gravava XML
    corrompido em disco — um `<` ou `&` perdido invalida o documento. Aqui a
    ordem é: UTF-8 estrito (padrão da NF-e) → Latin-1 (round-trip de bytes,
    nunca falha) → UTF-8 com reposição, como último recurso.
    """
    if isinstance(conteudo, str):
        return conteudo
    if conteudo is None:
        return ""
    for codificacao in ("utf-8", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return conteudo.decode("utf-8", errors="replace")
