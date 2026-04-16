# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — IPL-APS
Gera: dist/IPL-APS/IPL-APS  (Linux/Mac)
       dist/IPL-APS/IPL-APS.exe  (Windows)

Uso:
    pyinstaller ipl_aps.spec
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Arquivos de dados a incluir no bundle ─────────────────────────────────────
added_files = [
    ("iclabs_v5.html",            "."),   # dashboard web
    ("valores_referencia.sql",    "."),   # schema/dados de referência
    (".env.example",              "."),   # template de configuração
    ("IPL_SCORE_METODOLOGIA.md",  "."),   # documentação
]

# Adiciona apenas arquivos que existem
datas = []
for src, dst in added_files:
    if os.path.exists(src):
        datas.append((src, dst))

# Dependências dinâmicas do uvicorn / fastapi
datas += collect_data_files("uvicorn")
datas += collect_data_files("fastapi")
datas += collect_data_files("starlette")

# ── Hidden imports ─────────────────────────────────────────────────────────────
hidden_imports = [
    # FastAPI / uvicorn
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.config",
    "uvicorn.main",
    "fastapi",
    "fastapi.responses",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "starlette.responses",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "anyio",
    "anyio._backends._asyncio",
    "h11",
    # Auth
    "jose",
    "jose.jwt",
    "jose.exceptions",
    "bcrypt",
    # PDF
    "pdfplumber",
    "pdfminer",
    "pdfminer.high_level",
    "pdfminer.layout",
    # Email
    "imapclient",
    "pyzmail36",
    # Outros
    "dotenv",
    "email",
    "email.mime",
    "email.mime.text",
    "email.mime.multipart",
    "smtplib",
    "imaplib",
    "chardet",
    # Tkinter (normalmente já incluído, mas por garantia)
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    # Projeto
    "gateway",
    "ipl_engine",
    "processaexames",
    "setup_auth",
    "servidor_ipl",
    "menu_principal",
    "gui_buscar_exames",
    "interface_exames_avancada",
    "utils_analitos",
    "gerenciador_referencias",
    "config_gerenciador",
    "ocr_melhorado",
]

hidden_imports += collect_submodules("uvicorn")
hidden_imports += collect_submodules("starlette")
hidden_imports += collect_submodules("anyio")

# ── Análise ───────────────────────────────────────────────────────────────────
a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "numpy", "pandas", "scipy",
        "PIL", "cv2", "torch", "tensorflow",
        "IPython", "jupyter", "notebook",
        "test", "tests", "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys as _sys

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IPL-APS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # sem janela de terminal (modo GUI puro)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # substitua por "icon.ico" se tiver um ícone
    # Windows: evita que o antivírus bloqueie (sem manifest de UAC elevado)
    uac_admin=False,
    uac_uiaccess=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IPL-APS",
)
