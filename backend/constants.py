"""
Constantes do sistema NFE.

ATENÇÃO: este módulo NÃO contém dados reais de emitentes. Para evitar
exposição via Git, os CNPJs e endereços fiscais das empresas ficam
em ``certs/empresas_fiscais.json`` (gitignored). Este arquivo só
carrega o cadastro em tempo de execução e mantém um dicionário
de razão social para uso pelo backend.
"""
import json
import logging
import os
from typing import Dict

from backend.config import settings

logger = logging.getLogger(__name__)

# Cache em memória das empresas carregadas do JSON externo.
# Recarregado por ``reload_empresas_oficiais()`` sempre que o
# backend inicia ou o arquivo é modificado.
_EMPRESAS_CACHE: Dict[str, str] = {}


def _empresas_file_path() -> str:
    """Resolve o caminho do JSON de empresas fiscais."""
    return os.path.join(settings.CERT_DIR, "empresas_fiscais.json")


def _load_from_disk() -> Dict[str, str]:
    """Lê o JSON de empresas e devolve {cnpj_digits: razao_social}."""
    path = _empresas_file_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[Constantes] Falha ao ler {path}: {e}")
        return {}
    mapping: Dict[str, str] = {}
    for emp in data.get("empresas", []) or []:
        cnpj = "".join(c for c in str(emp.get("cnpj") or "") if c.isdigit())
        rz = str(emp.get("razao_social") or "").strip()
        if cnpj and rz:
            mapping[cnpj] = rz
    return mapping


def reload_empresas_oficiais() -> Dict[str, str]:
    """Recarrega o dicionário de empresas do JSON externo."""
    global _EMPRESAS_CACHE
    _EMPRESAS_CACHE = _load_from_disk()
    return _EMPRESAS_CACHE


def get_empresas_oficiais() -> Dict[str, str]:
    """Devolve a lista atual de empresas (carrega do disco se vazia)."""
    if not _EMPRESAS_CACHE:
        reload_empresas_oficiais()
    return _EMPRESAS_CACHE


def get_empresa_by_cnpj(cnpj: str) -> dict:
    """Retorna o cadastro fiscal completo (incluindo endereço) de uma empresa.

    Procura tanto no JSON externo quanto na tabela ``certificates`` do
    banco de dados local (que pode ter sido populada via upload do PFX).
    Retorna ``None`` se não encontrar.
    """
    digits = "".join(c for c in str(cnpj or "") if c.isdigit())

    # 1) Tenta do JSON externo primeiro
    path = _empresas_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for emp in data.get("empresas", []) or []:
                if "".join(c for c in str(emp.get("cnpj") or "") if c.isdigit()) == digits:
                    return emp
        except (OSError, json.JSONDecodeError):
            pass

    # 2) Fallback: tabela certificates
    try:
        from backend.database.certificates import get_certificate_record
        rec = get_certificate_record(digits)
        if rec:
            return {
                "cnpj": digits,
                "razao_social": rec.get("razao_social", ""),
                "nome_fantasia": rec.get("nome_fantasia", ""),
                "ie": rec.get("ie", ""),
                "logradouro": rec.get("logradouro", ""),
                "numero": rec.get("numero", ""),
                "complemento": rec.get("complemento", ""),
                "bairro": rec.get("bairro", ""),
                "municipio": rec.get("municipio", ""),
                "cod_municipio": rec.get("cod_municipio", ""),
                "uf": rec.get("uf", ""),
                "cep": rec.get("cep", ""),
                "crt": rec.get("crt", 1),
            }
    except Exception:
        pass
    return None


# Compatibilidade retroativa: propriedade que carrega dinamicamente.
# Código que fazia ``EMPRESAS_OFICIAIS[chave]`` passa a usar ``get_empresas_oficiais()``,
# mas mantemos o nome como proxy para evitar refatoração em massa.
class _EmpresasProxy(dict):
    """Proxy de dict que recarrega do JSON em cada acesso ``[]``."""

    def __getitem__(self, key):
        return get_empresas_oficiais()[key]

    def __contains__(self, key):
        return key in get_empresas_oficiais()

    def __iter__(self):
        return iter(get_empresas_oficiais())

    def __len__(self):
        return len(get_empresas_oficiais())

    def get(self, key, default=None):
        return get_empresas_oficiais().get(key, default)

    def keys(self):
        return get_empresas_oficiais().keys()

    def values(self):
        return get_empresas_oficiais().values()

    def items(self):
        return get_empresas_oficiais().items()


EMPRESAS_OFICIAIS = _EmpresasProxy()


def nome_empresa(cnpj: str, fallback: str = "EMPRESA") -> str:
    """Devolve a razão social de uma empresa pelo CNPJ.

    Procura primeiro no JSON externo (``certs/empresas_fiscais.json``) e,
    em seguida, na tabela ``certificates`` do banco. Retorna ``fallback``
    se não encontrar.
    """
    digits = "".join(c for c in str(cnpj or "") if c.isdigit())
    nome = get_empresas_oficiais().get(digits)
    if nome:
        return nome
    cad = get_empresa_by_cnpj(digits)
    if cad and cad.get("razao_social"):
        return cad["razao_social"]
    return fallback
