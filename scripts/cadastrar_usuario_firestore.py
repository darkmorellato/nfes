#!/usr/bin/env python3
"""
Script para cadastrar usuário no Firestore (coleção "usuarios").

COMO USAR:
    1. Edite a variável SENHA_PLAIN abaixo com a senha desejada.
    2. Execute:  cd /home/dark/Desktop/codes/NFE && python scripts/cadastrar_usuario_firestore.py
    3. Após cadastrar, apague ou limpe SENHA_PLAIN por segurança.

O documento criado no Firestore terá a senha armazenada como SHA-256 (hash irreversível).
O login no sistema faz a mesma hash e compara — nenhuma senha em texto puro no banco.

Se preferir cadastrar manualmente pelo Console Firebase:
    URL: https://console.firebase.google.com/project/nfes-dd7ab/firestore
    Coleção: usuarios
    Documento ID: contasgeraljack@gmail.com
    Campos:
        email  (string): contasgeraljack@gmail.com
        nome   (string): Administrador
        ativo  (boolean): true
        senha  (string): <SHA-256 da sua senha>
"""

import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha256_hex(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ─── EDITE AQUI ──────────────────────────────────────────────────────────────
EMAIL = "contasgeraljack@gmail.com"
NOME = "Administrador"
SENHA_PLAIN = ""  # Ex: "#ADMIN_PASSWORD_REMOVED"  — APAGUE APÓS EXECUTAR
# ─────────────────────────────────────────────────────────────────────────────


def main():
    if not SENHA_PLAIN:
        senha_exemplo = sha256_hex("#ADMIN_PASSWORD_REMOVED")
        print("=" * 60)
        print("INSTRUÇÃO: Preencha SENHA_PLAIN no script e execute novamente.")
        print()
        print("Ou cadastre manualmente no Console Firebase:")
        print("  URL: https://console.firebase.google.com/project/nfes-dd7ab/firestore")
        print()
        print("  Coleção: usuarios")
        print("  Documento: contasgeraljack@gmail.com")
        print("  Campos:")
        print("    email:  contasgeraljack@gmail.com")
        print("    nome:   Administrador")
        print("    ativo:  true (boolean)")
        print(f"    senha:  {senha_exemplo}")
        print("           ^ SHA-256 de '#ADMIN_PASSWORD_REMOVED'")
        print("=" * 60)
        return

    senha_hash = sha256_hex(SENHA_PLAIN)
    print(f"SHA-256 da senha: {senha_hash}")

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fs_client

        cred_path = os.path.join(os.path.dirname(__file__), "firebase-adminsdk.json")
        if not os.path.exists(cred_path):
            raise FileNotFoundError("firebase-adminsdk.json não encontrado em scripts/")

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        db = fs_client.client()
        doc_ref = db.collection("usuarios").document(EMAIL)
        doc_ref.set({
            "email": EMAIL,
            "nome": NOME,
            "ativo": True,
            "senha": senha_hash,
            "perfil": "admin",
            "created_at": fs_client.SERVER_TIMESTAMP,
        }, merge=True)

        print(f"✅ Usuário '{EMAIL}' cadastrado com sucesso no Firestore!")

    except ImportError:
        print("firebase-admin não instalado. Instale com: pip install firebase-admin")
        print()
        print("Cadastre manualmente no Console Firebase usando o SHA-256 acima.")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("Baixe em: Firebase Console → Configurações do projeto → Contas de serviço")
        print()
        print("Cadastre manualmente no Console Firebase usando o SHA-256 acima.")


if __name__ == "__main__":
    main()
