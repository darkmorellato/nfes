"""
Validação de payload na fronteira da API (Pydantic).

Antes, 26 endpoints de escrita aceitavam ``Dict[str, Any]``: quantidades
negativas, ``tPag`` fora da tabela e CPF com 12 dígitos só apareciam (quando
apareciam) como rejeição da SEFAZ — a um custo de cota do certificado e de um
número de nota consumido.
"""
import pytest
from fastapi.testclient import TestClient

from backend.schemas.nfe import (
    EmissaoNFeRequest,
    CancelamentoNFeRequest,
    InutilizacaoNFeRequest,
    CartaCorrecaoRequest,
    payload_do_body,
)


def _payload_valido(**sobre):
    base = {
        "emitente_cnpj": "13787408000105",
        "destinatario": {
            "cpf_cnpj": "12345678909",
            "razao_social": "CLIENTE TESTE",
        },
        "produtos": [
            {
                "descricao": "PRODUTO",
                "ncm": "85171300",
                "quantidade": 1,
                "valor_unitario": 100.0,
            }
        ],
    }
    base.update(sobre)
    return base


# ====================================================================
# 1. Modelos
# ====================================================================

def test_payload_valido_e_convertido_para_dict():
    modelo = EmissaoNFeRequest(**_payload_valido())
    d = payload_do_body(modelo)
    assert isinstance(d, dict)
    assert d["emitente_cnpj"] == "13787408000105"
    assert d["destinatario"]["cpf_cnpj"] == "12345678909"
    assert len(d["produtos"]) == 1
    # campos enviados apenas pelo front não são descartados
    assert d["produtos"][0]["ncm"] == "85171300"


def test_quantidade_zero_e_rejeitada():
    with pytest.raises(ValueError):
        EmissaoNFeRequest(**_payload_valido(produtos=[
            {"descricao": "X", "quantidade": 0, "valor_unitario": 10}
        ]))


def test_desconto_maior_que_item_e_rejeitado():
    with pytest.raises(ValueError, match="desconto"):
        EmissaoNFeRequest(**_payload_valido(produtos=[
            {"descricao": "X", "quantidade": 1, "valor_unitario": 10, "desconto": 50}
        ]))


def test_cnpj_emitente_com_tamanho_errado_e_rejeitado():
    with pytest.raises(ValueError, match="14 dígitos"):
        EmissaoNFeRequest(**_payload_valido(emitente_cnpj="123"))


def test_destinatario_com_documento_invalido_e_rejeitado():
    with pytest.raises(ValueError, match="11 dígitos"):
        EmissaoNFeRequest(**_payload_valido(
            destinatario={"cpf_cnpj": "12345", "razao_social": "X"}
        ))


def test_forma_de_pagamento_fora_da_tabela_e_rejeitada():
    with pytest.raises(ValueError, match="formas de pagamento"):
        EmissaoNFeRequest(**_payload_valido(forma_pagamento="77"))


def test_lista_de_produtos_vazia_e_rejeitada():
    with pytest.raises(ValueError):
        EmissaoNFeRequest(**_payload_valido(produtos=[]))


def test_tp_integra_fora_de_1_ou_2_e_rejeitado():
    with pytest.raises(ValueError):
        EmissaoNFeRequest(**_payload_valido(cartao={"tp_integra": "9"}))


def test_finalidade_fora_da_faixa_e_rejeitada():
    with pytest.raises(ValueError):
        EmissaoNFeRequest(**_payload_valido(finalidade=7))


def test_condicao_de_pagamento_invalida_e_rejeitada():
    with pytest.raises(ValueError, match="a_vista"):
        EmissaoNFeRequest(**_payload_valido(condicao_pagamento="parcelado"))


def test_numero_negativo_e_rejeitado():
    with pytest.raises(ValueError):
        EmissaoNFeRequest(**_payload_valido(numero=-5))


# ====================================================================
# 2. Cancelamento / inutilização / CC-e
# ====================================================================

def test_cancelamento_exige_justificativa_minima():
    with pytest.raises(ValueError):
        CancelamentoNFeRequest(chave="35" + "0" * 42, justificativa="curta")


def test_cancelamento_normaliza_a_chave():
    req = CancelamentoNFeRequest(chave="35" + "0" * 42, justificativa="justificativa com 15 digitos")
    assert req.chave.isdigit() and len(req.chave) == 44


def test_inutilizacao_valida_e_com_faixa_coerente():
    ok = InutilizacaoNFeRequest(
        empresa_cnpj="13787408000105", numero_inicial=10, numero_final=20,
        justificativa="Quebra de sequencia por falha da impressora",
    )
    assert ok.modelo == "55"

    with pytest.raises(ValueError):
        InutilizacaoNFeRequest(
            empresa_cnpj="13787408000105", numero_inicial=20, numero_final=10,
            justificativa="Quebra de sequencia por falha da impressora",
        )


def test_inutilizacao_com_modelo_invalido_e_rejeitada():
    with pytest.raises(ValueError, match="55"):
        InutilizacaoNFeRequest(
            empresa_cnpj="13787408000105", numero_inicial=1, numero_final=2,
            justificativa="Quebra de sequencia por falha da impressora", modelo="57",
        )


def test_carta_correcao_exige_texto_minimo():
    with pytest.raises(ValueError):
        CartaCorrecaoRequest(chave="35" + "0" * 42, correcao="curto")


# ====================================================================
# 3. Formato do erro HTTP (o front lê `detail` como string)
# ====================================================================

def test_erro_de_validacao_devolve_detail_como_string():
    import secrets
    from backend.main import app
    from backend.routers.auth import save_session

    token = secrets.token_hex(16)
    save_session(token, {"email": "validacao@teste", "nome": "T", "perfil": "operador"})

    corpo = _payload_valido(produtos=[
        {"descricao": "X", "quantidade": 0, "valor_unitario": 10}
    ])
    resp = TestClient(app).post(
        "/api/emissao/nfe/emitir", json=corpo, headers={"X-Session-Token": token}
    )

    assert resp.status_code == 422
    detalhe = resp.json()["detail"]
    assert isinstance(detalhe, str), "detail precisa ser string para a tela de rejeição"
    assert "quantidade" in detalhe
