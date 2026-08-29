from typing import Dict

EMPRESAS_OFICIAIS: Dict[str, str] = {
    "34511185000110": "JACKCELL CELULARES E IMPORTADOS LTDA",
    "13787408000105": "FERNANDES COMERCIO DE CELULARES E IMPORTACAO LTDA",
    "44739622000101": "FILIPE ALMEIDA GIL DE SOUZA LTDA",
    "58186781000130": "J DE A FERNANDES OPERACOES DE CREDITO",
    "58495100000116": "MI PLACE AMPARO LTDA",
}


def nome_empresa(cnpj: str, fallback: str = "EMPRESA") -> str:
    digits = "".join(c for c in str(cnpj or "") if c.isdigit())
    return EMPRESAS_OFICIAIS.get(digits, fallback)
