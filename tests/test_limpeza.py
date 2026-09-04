import os
import pytest

from backend.database import get_db_connection, XML_STORAGE_DIR
from backend.database.limpeza import (
    preview_limpeza_nfes,
    executar_limpeza_nfes,
    auditoria_xmls_orfaos,
    apagar_xmls_orfaos,
    auditoria_rapida_base,
)
from backend.database.nfe_docs import save_nfe_doc


class TestLimpezaEAuditoria:
    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        # Insere notas fiscais fictícias para teste
        self.chave_teste_1 = "99999999999999999999999999999999999999999901"
        self.chave_teste_2 = "99999999999999999999999999999999999999999902"
        self.chave_real = "99999999999999999999999999999999999999999903"

        save_nfe_doc({
            "chave": self.chave_teste_1,
            "emitente_nome": "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL",
            "emitente_cnpj": "00000000000000",
            "destinatario_nome": "CLIENTE TESTE",
            "destinatario_cnpj": "11111111111111",
            "data_emissao": "2026-08-31 10:00:00",
            "valor_total": 100.0,
            "situacao": "Autorizada",
        }, xml_raw="<nfeProc>teste 1</nfeProc>")

        save_nfe_doc({
            "chave": self.chave_teste_2,
            "emitente_nome": "FORNECEDOR BETA",
            "emitente_cnpj": "22222222000122",
            "destinatario_nome": "NF-E HOMOLOGACAO TESTE",
            "destinatario_cnpj": "99999999999999",
            "data_emissao": "2026-08-30 15:00:00",
            "valor_total": 0.0,
            "situacao": "Autorizada",
        })

        save_nfe_doc({
            "chave": self.chave_real,
            "emitente_nome": "EMPRESA REAL S.A.",
            "emitente_cnpj": "33333333000133",
            "destinatario_nome": "CLIENTE REAL LTDA",
            "destinatario_cnpj": "44444444000144",
            "data_emissao": "2026-08-29 12:00:00",
            "valor_total": 1500.50,
            "situacao": "Autorizada",
        })

        yield

        # Limpa resíduos de teste
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM nfe_docs WHERE chave IN (?, ?, ?)", (self.chave_teste_1, self.chave_teste_2, self.chave_real))
            conn.commit()

    def test_auditoria_rapida_base(self):
        res = auditoria_rapida_base()
        assert res["success"] is True
        assert "resumo_notas" in res
        assert res["resumo_notas"]["total_docs"] >= 3
        assert res["resumo_notas"]["total_testes_identificados"] >= 2
        assert "armazenamento" in res
        assert "db_size_formatado" in res["armazenamento"]
        assert "top_emitentes" in res

    def test_preview_e_executar_limpeza(self):
        # 1. Preview
        prev = preview_limpeza_nfes(tipo_teste="homologacao")
        assert prev["success"] is True
        assert prev["total_encontradas"] >= 2
        chaves_encontradas = [it["chave"] for it in prev["itens"]]
        assert self.chave_teste_1 in chaves_encontradas

        # 2. Executa a limpeza apenas das chaves de teste
        exec_res = executar_limpeza_nfes(
            chaves_selecionadas=[self.chave_teste_1, self.chave_teste_2],
            apagar_xml_disco=True,
            apagar_firestore=False,
        )
        assert exec_res["success"] is True
        assert exec_res["deleted_count"] == 2

        # Verifica se foram apagadas no banco
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) as c FROM nfe_docs WHERE chave IN (?, ?)", (self.chave_teste_1, self.chave_teste_2))
            assert c.fetchone()["c"] == 0

            # Nota real permaneceu
            c.execute("SELECT COUNT(*) as c FROM nfe_docs WHERE chave = ?", (self.chave_real,))
            assert c.fetchone()["c"] == 1

    def test_xmls_orfaos(self):
        # Cria arquivo órfão no disco
        orphan_chave = "88888888888888888888888888888888888888888888"
        orphan_path = os.path.join(XML_STORAGE_DIR, f"{orphan_chave}.xml")
        with open(orphan_path, "w", encoding="utf-8") as f:
            f.write("<orphan>conteudo orfao</orphan>")

        try:
            audit = auditoria_xmls_orfaos()
            assert audit["success"] is True
            assert audit["total_orfaos"] >= 1
            orphan_files = [o["filename"] for o in audit["amostra_orfaos"]]
            assert f"{orphan_chave}.xml" in orphan_files

            # Apaga órfãos
            clean_res = apagar_xmls_orfaos()
            assert clean_res["success"] is True
            assert clean_res["deleted_files"] >= 1
            assert not os.path.exists(orphan_path)
        finally:
            if os.path.exists(orphan_path):
                os.remove(orphan_path)
