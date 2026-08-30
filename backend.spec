# -*- mode: python ; coding: utf-8 -*-
"""Freeze do backend NFE Manager (onefile) + frontend, para AppImage.

Gera um binário executável que embute backend/ e frontend/. O Chromium é
empacotado à parte (PLAYWRIGHT_BROWSERS_PATH) e aberto pelo app_launcher.
"""
import os

ROOT = os.path.abspath(".")

a = Analysis(
    ["app_launcher.py"],
    pathex=[ROOT, os.path.join(ROOT, "backend")],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "frontend"), "frontend"),
        (os.path.join(ROOT, "backend"), "backend"),
    ],
    hiddenimports=[
        # núcleo fiscal / nativas
        "pynfe", "pynfe.client", "pynfe.utils", "pynfe.xml", "pynfe.nfe",
        "pynfe.nfce", "pynfe.mdfe",
        "lxml", "lxml.etree", "lxml.objectify",
        "cryptography", "cryptography.hazmat.backends.openssl",
        "signxml",
        # web
        "fastapi", "uvicorn", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto", "python_multipart",
        "starlette", "jinja2", "anyio",
        # routers
        "backend.routers", "backend.routers.status", "backend.routers.cert",
        "backend.routers.reports", "backend.routers.danfe", "backend.routers.gestao",
        "backend.routers.emissao", "backend.routers.nfe", "backend.routers.nfce",
        "backend.routers.mdfe", "backend.routers.nfse", "backend.routers.auth",
        # services / db
        "backend.services", "backend.services.pynfe_service", "backend.services.cert_service",
        "backend.services.report_service", "backend.services.nfe_emissao_service",
        "backend.services.sync_service", "backend.services.danfe_service",
        "backend.database", "backend.database.schema", "backend.database.certificates",
        "backend.database.nfe_docs", "backend.database.financeiro", "backend.database.estoque",
        "backend.database.analytics", "backend.database.cadastros", "backend.database.notifications",
        "backend.database.sync_state",
    ],
    excludes=["PyQt5", "PySide2", "PySide6", "tkinter"],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="NFE-Manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    target_arch=None,
)
