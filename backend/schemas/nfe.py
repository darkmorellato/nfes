"""
Modelos de entrada (Pydantic) das rotas de emissão fiscal.

Por quê: 26 endpoints de escrita recebiam ``Dict[str, Any] = Body(...)``, o que
significava zero validação de tipo, faixa e enumeração — quantidades negativas,
``tPag`` fora do leiaute, CPF/CNPJ com tamanho errado e parcelas negativas só
eram descobertas (quando eram) na SEFAZ, a um custo de cota do certificado
(rejeição 656) e de um número de nota consumido.

Os campos que a interface envia hoje são declarados; o restante é preservado via
``extra="allow"`` para não quebrar chamadas legadas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _BaseModel(BaseModel):
    # Preserva campos extras enviados pelo front em vez de descartá-los.
    model_config = ConfigDict(extra="allow")


class DestinatarioEmissao(_BaseModel):
    cpf_cnpj: str = Field(..., description="CPF (11) ou CNPJ (14) apenas dígitos")
    razao_social: str = Field(..., min_length=1, max_length=60)
    indicador_ie: Optional[int] = Field(None, ge=0, le=9)
    ie: Optional[str] = None
    cep: Optional[str] = None
    logradouro: Optional[str] = Field(None, max_length=60)
    numero: Optional[str] = Field(None, max_length=60)
    complemento: Optional[str] = Field(None, max_length=60)
    bairro: Optional[str] = Field(None, max_length=60)
    municipio: Optional[str] = Field(None, max_length=60)
    cod_municipio: Optional[str] = None
    uf: Optional[str] = Field(None, min_length=2, max_length=2)
    email: Optional[str] = Field(None, max_length=60)
    telefone: Optional[str] = None
    nome_fantasia: Optional[str] = None

    @field_validator("cpf_cnpj")
    @classmethod
    def _digitos_documento(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if len(digitos) not in (11, 14):
            raise ValueError("CPF deve ter 11 dígitos e CNPJ 14 dígitos.")
        return digitos


class ItemEmissao(_BaseModel):
    codigo: Optional[str] = Field(None, max_length=60)
    descricao: str = Field(..., min_length=1, max_length=120)
    ncm: Optional[str] = Field(None, max_length=8)
    cfop: Optional[str] = Field(None, max_length=4)
    unidade: Optional[str] = Field(None, max_length=6)
    quantidade: float = Field(..., gt=0, le=1_000_000_000)
    valor_unitario: float = Field(..., ge=0, le=1_000_000_000)
    desconto: float = Field(0.0, ge=0)
    csosn_cst: Optional[str] = Field(None, max_length=3)
    origem: Optional[int] = Field(None, ge=0, le=8)
    imei: Optional[str] = None

    @field_validator("descricao")
    @classmethod
    def _descricao_obrigatoria(cls, v: str) -> str:
        if not str(v).strip():
            raise ValueError("A descrição do item não pode ser vazia.")
        return v

    @field_validator("unidade")
    @classmethod
    def _unidade_curta(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(str(v).strip()) > 6:
            raise ValueError("A unidade comercial tem no máximo 6 caracteres.")
        return v


class ParcelaEmissao(_BaseModel):
    numero: Optional[str] = Field(None, max_length=60)
    vencimento: Optional[str] = None
    valor: Optional[float] = Field(None, ge=0)


class TransporteEmissao(_BaseModel):
    modalidade_frete: Optional[str] = Field(None, max_length=2)
    transportadora_cnpj_cpf: Optional[str] = None
    transportadora_nome: Optional[str] = None
    transportadora_ie: Optional[str] = None
    transportadora_endereco: Optional[str] = None
    transportadora_municipio: Optional[str] = None
    transportadora_uf: Optional[str] = None
    placa_veiculo: Optional[str] = None
    uf_veiculo: Optional[str] = None
    volumes_qtd: Optional[int] = Field(None, ge=0, le=999999)
    volumes_especie: Optional[str] = None
    volumes_marca: Optional[str] = None
    volumes_numeracao: Optional[str] = None
    peso_liquido: Optional[float] = Field(None, ge=0)
    peso_bruto: Optional[float] = Field(None, ge=0)


class CartaoEmissao(_BaseModel):
    """Grupo <card> — obrigatório para tPag 03/04/17 (regra 391_YA04-10)."""

    tp_integra: Optional[str] = Field(None, pattern=r"^[12]$")
    cnpj: Optional[str] = None
    bandeira: Optional[str] = None
    aut: Optional[str] = None


class EmissaoNFeRequest(_BaseModel):
    """Payload de POST /api/emissao/nfe/emitir (e da prévia do DANFE)."""

    model_config = ConfigDict(extra="allow")

    emitente_cnpj: str
    natureza_operacao: str = Field("VENDA DE MERCADORIA", max_length=60)
    serie: str = Field("1", max_length=3)
    numero: Optional[int] = Field(None, ge=1, le=999_999_999)
    regime_tributario: Optional[int] = Field(None, ge=1, le=3)
    emitente_uf: Optional[str] = Field(None, min_length=2, max_length=2)
    finalidade: int = Field(1, ge=1, le=4)
    indicador_presencial: Optional[int] = Field(None, ge=0, le=9)
    consumidor_final: Optional[int] = Field(None, ge=0, le=1)
    indicador_destino: Optional[int] = Field(None, ge=0, le=4)
    chave_referenciada: Optional[str] = None
    nfe_referenciada: Optional[str] = None
    data_saida: Optional[str] = None

    destinatario: DestinatarioEmissao
    produtos: List[ItemEmissao] = Field(..., min_length=1, max_length=999)

    valor_frete: float = Field(0.0, ge=0)
    valor_seguro: float = Field(0.0, ge=0)
    outras_despesas: float = Field(0.0, ge=0)
    transporte: Optional[TransporteEmissao] = None
    modalidade_frete: Optional[str] = Field(None, max_length=2)

    condicao_pagamento: str = Field("a_vista")
    parcelas: List[ParcelaEmissao] = Field(default_factory=list, max_length=180)
    forma_pagamento: str = Field("17", max_length=2)
    cartao: Optional[CartaoEmissao] = None

    salvar_cliente: bool = True
    informacoes_complementares: Optional[str] = None
    homologacao: Optional[bool] = None

    # --- Contingência (tpEmis) ---
    # `contingencia: true` pede SVC automático derivado da UF; `tp_emis` permite
    # forçar o código (6 = SVC-AN, 7 = SVC-RS). Exige contingencia_justificativa.
    contingencia: Optional[bool] = None
    tp_emis: Optional[int] = Field(None, ge=1, le=9)
    contingencia_justificativa: Optional[str] = Field(None, max_length=255)

    @field_validator("contingencia_justificativa")
    @classmethod
    def _justificativa_contingencia(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        limpo = str(v).strip()
        return limpo or None

    @field_validator("emitente_cnpj")
    @classmethod
    def _cnpj_emitente(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if len(digitos) != 14:
            raise ValueError("O CNPJ do emitente deve ter 14 dígitos.")
        return digitos

    @field_validator("serie")
    @classmethod
    def _serie_numerica(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if not digitos:
            raise ValueError("A série da NF-e deve ser numérica.")
        return digitos.lstrip("0") or "0"

    @field_validator("condicao_pagamento")
    @classmethod
    def _condicao_valida(cls, v: str) -> str:
        if v not in ("a_vista", "a_prazo"):
            raise ValueError("condicao_pagamento deve ser 'a_vista' ou 'a_prazo'.")
        return v

    @field_validator("forma_pagamento")
    @classmethod
    def _tpag_valido(cls, v: str) -> str:
        digitos = str(v).strip().zfill(2)
        # Tabela de formas de pagamento da NF-e (grupo YA01)
        validos = {
            "01", "02", "03", "04", "05", "10", "11", "12", "13", "14",
            "15", "16", "17", "18", "19", "90", "99",
        }
        if digitos not in validos:
            raise ValueError(
                f"forma_pagamento '{v}' não consta na tabela de formas de pagamento da NF-e."
            )
        return digitos

    @field_validator("produtos")
    @classmethod
    def _descontos_coerentes(cls, itens: List[ItemEmissao]) -> List[ItemEmissao]:
        for i, item in enumerate(itens, start=1):
            bruto = item.quantidade * item.valor_unitario
            if item.desconto > bruto:
                raise ValueError(
                    f"Item {i}: o desconto (R$ {item.desconto:.2f}) é maior que o "
                    f"valor do item (R$ {bruto:.2f})."
                )
        return itens


class CancelamentoNFeRequest(_BaseModel):
    model_config = ConfigDict(extra="allow")

    chave: str
    justificativa: str = Field(..., min_length=15, max_length=255)
    protocolo: Optional[str] = None
    homologacao: Optional[bool] = None

    @field_validator("chave")
    @classmethod
    def _chave_44(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if len(digitos) != 44:
            raise ValueError("A chave de acesso deve conter 44 dígitos.")
        return digitos


class CartaCorrecaoRequest(_BaseModel):
    model_config = ConfigDict(extra="allow")

    chave: str
    correcao: Optional[str] = None
    texto: Optional[str] = None
    sequencia: Optional[int] = Field(None, ge=1, le=20)
    homologacao: Optional[bool] = None

    @field_validator("chave")
    @classmethod
    def _chave_44(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if len(digitos) != 44:
            raise ValueError("A chave de acesso deve conter 44 dígitos.")
        return digitos

    @field_validator("correcao")
    @classmethod
    def _texto_obrigatorio(cls, v: Optional[str]) -> Optional[str]:
        # aceitamos o alias `texto` no service; só validamos quando presente
        if v is not None and len(v.strip()) < 15:
            raise ValueError("O texto da Carta de Correção deve ter no mínimo 15 caracteres.")
        return v


class InutilizacaoNFeRequest(_BaseModel):
    model_config = ConfigDict(extra="allow")

    empresa_cnpj: str
    serie: str = "1"
    numero_inicial: int = Field(..., ge=1)
    numero_final: int = Field(..., ge=1)
    justificativa: str = Field(..., min_length=15, max_length=255)
    modelo: str = Field("55")
    homologacao: Optional[bool] = None

    @field_validator("empresa_cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        digitos = "".join(c for c in str(v) if c.isdigit())
        if len(digitos) not in (11, 14):
            raise ValueError("Informe CNPJ (14 dígitos) ou CPF (11 dígitos).")
        return digitos

    @field_validator("modelo")
    @classmethod
    def _modelo_valido(cls, v: str) -> str:
        if str(v) not in ("55", "65"):
            raise ValueError("modelo deve ser 55 (NF-e) ou 65 (NFC-e).")
        return str(v)

    @field_validator("numero_final")
    @classmethod
    def _faixa(cls, v: int, info) -> int:
        inicial = info.data.get("numero_inicial")
        if inicial is not None and v < inicial:
            raise ValueError("numero_final não pode ser menor que numero_inicial.")
        return v


def payload_do_body(model: _BaseModel) -> Dict[str, Any]:
    """Converte o modelo para o dicionário que os services já esperam."""
    return model.model_dump()
