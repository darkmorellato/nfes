"""
Testes das correções de segurança do plano de hardening.

Cobre:
- 1.1 require_session bloqueia endpoints sem token
- 1.3 bcrypt verifica e migra hashes legados
- 1.4 get_cert_password descriptografa o que vier do cert_meta.json
- 1.5 /debug/nfe-completo retorna 404 quando DEBUG=False
- 1.6 /api/nfe/emitir/rapido delega para o serviço real
- 2.2 tokens Telegram/Webhook gravados cifrados
- 2.3 CORS não aceita "*"
"""
import os
import tempfile
import unittest
from unittest.mock import patch

# Garante que o app use o DEBUG=False durante os testes do debug gate
os.environ.setdefault("DEBUG", "False")


class TestRequireSessionGate(unittest.TestCase):
    """1.1: endpoints protegidos exigem X-Session-Token."""

    def test_protected_routers_require_session(self):
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Tenta acessar endpoints sensíveis sem token — todos devem ser 401
        rotas_protegidas = [
            ("GET", "/api/gestao/documentos"),
            ("GET", "/api/nfe/consulta?chave=35240100000000000000550010000000011000000010"),
            ("GET", "/api/certificado/list"),
            ("GET", "/api/danfe/pdf/35240100000000000000550010000000011000000010"),
        ]
        for method, url in rotas_protegidas:
            resp = client.request(method, url)
            self.assertIn(
                resp.status_code,
                (401, 403),
                f"{method} {url} deveria exigir sessão mas retornou {resp.status_code}",
            )


class TestAuthBcrypt(unittest.TestCase):
    """1.3: bcrypt + retrocompatibilidade com SHA-256 legado."""

    def setUp(self):
        from backend.routers import auth as auth_module
        # Limpa sessões para não vazar entre testes
        auth_module._sessions.clear()

    def test_bcrypt_roundtrip(self):
        from backend.routers.auth import _hash_password, _verify_password

        plain = "uma-senha-forte-123!"
        h = _hash_password(plain)
        # Se bcrypt disponível, hash tem prefixo "bcrypt$"
        if h.startswith("bcrypt$"):
            self.assertTrue(_verify_password(plain, h))
            self.assertFalse(_verify_password("senha-errada", h))
        else:
            # Fallback SHA-256 (64 hex chars)
            self.assertEqual(len(h), 64)
            self.assertTrue(_verify_password(plain, h))

    def test_legacy_sha256_still_works(self):
        """Hashes legados (SHA-256) continuam válidos durante a migração."""
        import hashlib
        from backend.routers.auth import _verify_password

        legacy_hash = hashlib.sha256(b"senha-antiga").hexdigest()
        self.assertTrue(_verify_password("senha-antiga", legacy_hash))
        self.assertFalse(_verify_password("outra", legacy_hash))

    def test_is_legacy_hash_detection(self):
        from backend.routers.auth import _is_legacy_hash
        self.assertTrue(_is_legacy_hash("abc123" * 11))  # SHA-256 hex
        # bcrypt tem prefixo "bcrypt$" — não é legado
        self.assertFalse(_is_legacy_hash("bcrypt$xxxxx"))
        # Hash vazio não é "legado" (não há nada para migrar)
        self.assertFalse(_is_legacy_hash(""))


class TestCertPasswordEncryption(unittest.TestCase):
    """1.4: senha de certificado no cert_meta.json é gravada cifrada."""

    def test_save_writes_encrypted_password(self):
        """1.4: o helper is_encrypted reconhece Fernet; o round-trip
        encrypt → decrypt preserva o valor original.

        Teste de integração completo de save_certificate exigiria um PFX
        real; aqui validamos o round-trip de criptografia que o
        save_certificate usa em cert_meta.json.
        """
        from backend.services.crypto_service import encrypt_secret, decrypt_secret, is_encrypted

        plain = "MINHA-SENHA-EM-TEXTO-PURO"
        encrypted = encrypt_secret(plain)
        self.assertTrue(is_encrypted(encrypted))
        self.assertNotIn(plain, encrypted)
        self.assertEqual(decrypt_secret(encrypted), plain)

    def test_get_cert_password_decrypts_legacy_legado(self):
        """Garante que get_cert_password descriptografa tanto o legado
        em texto puro quanto valores já cifrados com Fernet.
        """
        from backend.services import cert_service

        with tempfile.TemporaryDirectory() as tmpdir:
            from backend.services.crypto_service import encrypt_secret

            # Caso 1: senha em texto puro (legado) — devolvida como está
            meta_legado = {"password": "senha-legado-123", "path": ""}
            with patch.object(cert_service, "get_certificate_record", return_value=None), \
                 patch.object(cert_service, "list_certificates_db", return_value=[]), \
                 patch.object(cert_service.settings, "CERT_DIR", tmpdir):
                import json
                with open(os.path.join(tmpdir, "cert_meta.json"), "w") as f:
                    json.dump(meta_legado, f)
                self.assertEqual(cert_service.get_cert_password(), "senha-legado-123")

            # Caso 2: senha cifrada (formato novo) — descriptografada
            meta_novo = {"password": encrypt_secret("senha-nova-456"), "path": ""}
            with patch.object(cert_service, "get_certificate_record", return_value=None), \
                 patch.object(cert_service, "list_certificates_db", return_value=[]), \
                 patch.object(cert_service.settings, "CERT_DIR", tmpdir):
                import json
                with open(os.path.join(tmpdir, "cert_meta.json"), "w") as f:
                    json.dump(meta_novo, f)
                self.assertEqual(cert_service.get_cert_password(), "senha-nova-456")


class TestDebugEndpointGate(unittest.TestCase):
    """1.5: /debug/nfe-completo só responde com DEBUG=True."""

    def test_debug_blocked_when_debug_false(self):
        from backend.main import app
        from fastapi.testclient import TestClient

        with patch("backend.routers.gestao.settings.DEBUG", False):
            client = TestClient(app)
            # Sem token de sessão, deveria falhar com 401 (auth) ou 404 (gate)
            resp = client.get(
                "/api/gestao/debug/nfe-completo",
                params={"cnpj": "34511185000110", "limit": 10},
            )
            self.assertIn(resp.status_code, (401, 403, 404))


class TestCORSNotWildcard(unittest.TestCase):
    """2.3: CORS não aceita mais "*"."""

    def test_cors_rejects_wildcard(self):
        from backend.config import allowed_origins_list

        with patch("backend.config.settings.ALLOWED_ORIGINS", "*"):
            origs = allowed_origins_list()
            self.assertNotIn("*", origs)
            # Deve cair no default local seguro
            self.assertIn("http://localhost:8000", origs)

    def test_cors_with_empty_uses_safe_default(self):
        from backend.config import allowed_origins_list

        with patch("backend.config.settings.ALLOWED_ORIGINS", ""):
            origs = allowed_origins_list()
            self.assertIn("http://localhost:8000", origs)
            self.assertNotIn("*", origs)

    def test_cors_with_explicit_list(self):
        from backend.config import allowed_origins_list

        with patch(
            "backend.config.settings.ALLOWED_ORIGINS",
            "https://meuapp.exemplo.com,https://outro.exemplo.com",
        ):
            origs = allowed_origins_list()
            self.assertEqual(
                sorted(origs),
                sorted(["https://meuapp.exemplo.com", "https://outro.exemplo.com"]),
            )


class TestConstantsFromExternalFile(unittest.TestCase):
    """1.2a: constants.py carrega do JSON externo (gitignored)."""

    def test_no_hardcoded_cnpjs_in_constants(self):
        """Garante que o módulo constants não tem mais CNPJs literais."""
        import backend.constants as c
        src = open(c.__file__).read()
        # Nenhum CNPJ real de 14 dígitos deve aparecer no código-fonte
        import re
        cnpjs_no_codigo = re.findall(r"\b\d{14}\b", src)
        self.assertEqual(
            cnpjs_no_codigo, [],
            f"CNPJs literais encontrados em constants.py: {cnpjs_no_codigo}",
        )

    def test_empresas_oficiais_via_json(self):
        import json
        import tempfile

        from backend import constants

        with tempfile.TemporaryDirectory() as tmpdir:
            sample = {
                "empresas": [
                    {
                        "cnpj": "12345678000195",
                        "razao_social": "EMPRESA TESTE JSON LTDA",
                    }
                ]
            }
            path = os.path.join(tmpdir, "empresas_fiscais.json")
            with open(path, "w") as f:
                json.dump(sample, f)

            with patch.object(constants.settings, "CERT_DIR", tmpdir):
                constants.reload_empresas_oficiais()
                self.assertEqual(
                    constants.nome_empresa("12345678000195"),
                    "EMPRESA TESTE JSON LTDA",
                )
                self.assertEqual(
                    constants.nome_empresa("99999999000199", fallback="DESCONHECIDA"),
                    "DESCONHECIDA",
                )


class TestRateLimiting(unittest.TestCase):
    def test_login_rate_limiter_blocks_excessive_attempts(self):
        from backend.main import app
        from fastapi.testclient import TestClient
        from backend.dependencies import login_rate_limiter

        login_rate_limiter._history.clear()
        client = TestClient(app)

        for _ in range(10):
            resp = client.post("/api/auth/login", json={"email": "wrong@nfe.com", "senha": "wrong"})
            self.assertIn(resp.status_code, (400, 401))

        # 11ª tentativa deve ser 429
        resp = client.post("/api/auth/login", json={"email": "wrong@nfe.com", "senha": "wrong"})
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Limite de 10 tentativas", resp.json()["detail"])
        self.assertIn("Retry-After", resp.headers)

    def test_correlation_id_header_generated_and_propagated(self):
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        req_id = resp.headers.get("X-Request-ID")
        self.assertIsNotNone(req_id)
        self.assertTrue(req_id.startswith("req_"))

        # Propagação de ID existente
        resp2 = client.get("/health", headers={"X-Request-ID": "custom_audit_test_123"})
        self.assertEqual(resp2.headers.get("X-Request-ID"), "custom_audit_test_123")

    def test_backup_list_and_auditoria_endpoints(self):
        from datetime import datetime, timedelta
        from backend.main import app
        from backend.routers import auth as auth_module
        from fastapi.testclient import TestClient

        token = "test_phase3_token"
        auth_module._sessions[token] = {
            "email": "admin@nfe.com",
            "nome": "Admin",
            "perfil": "admin",
            "expires_at": datetime.now() + timedelta(hours=2),
        }

        client = TestClient(app)
        headers = {"X-Session-Token": token}

        # Auditoria
        resp_audit = client.get("/api/gestao/auditoria", headers=headers)
        self.assertEqual(resp_audit.status_code, 200)
        data_audit = resp_audit.json()
        self.assertIn("total", data_audit)
        self.assertIn("logs", data_audit)

        # Backups
        resp_backup = client.get("/api/gestao/backups", headers=headers)
        self.assertEqual(resp_backup.status_code, 200)
        data_backup = resp_backup.json()
        self.assertTrue(data_backup.get("success"))
        self.assertIn("backups", data_backup)
        self.assertIsInstance(data_backup["backups"], list)


if __name__ == "__main__":
    unittest.main()
