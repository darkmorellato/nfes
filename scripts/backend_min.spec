# -*- mode: python ; coding: utf-8 -*-
# Spec mínimo do spike: congela o entrypoint e força os imports pesados.
a = Analysis(
    ["spike_entry.py"],
    pathex=["backend"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pynfe", "pynfe.client", "pynfe.utils", "pynfe.xml", "pynfe.nfe",
        "lxml", "lxml.etree", "lxml.objectify",
        "cryptography", "cryptography.hazmat.backends.openssl",
        "signxml",
        "fastapi", "uvicorn", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.websockets",
    ],
    excludes=["PyQt5", "PySide2", "tkinter", "test", "unittest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="nfe_spike",
         debug=False, bootloader_ignore_signals=False,
         strip=False, upx=True, console=True)
