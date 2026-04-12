#!/usr/bin/env python3
"""
Instalador de dependências - OCR Melhorado v2.1
Data: 29/03/2026

Instala todas as dependências necessárias para rodar o sistema com OCR melhorado.
"""

import subprocess
import sys
import platform

def instalar_pacote(nome: str, pip_name: str = None):
    """Instala um pacote via pip com tratamento de erro"""
    pip_name = pip_name or nome
    print(f"📦 Instalando {nome}...", end=" ")
    
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name, "-q"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✓")
        return True
    except subprocess.CalledProcessError:
        print("✗")
        return False

def main():
    print("=" * 60)
    print("OCR MELHORADO v2.1 - INSTALADOR DE DEPENDÊNCIAS")
    print("=" * 60)
    print()
    
    # Dependências principais (já existentes)
    print("📋 Dependências principais:")
    deps_principais = [
        ("pdfplumber", "pdfplumber>=0.7.0"),
        ("pytesseract", "pytesseract>=0.3.8"),
        ("pdf2image", "pdf2image>=1.16.0"),
        ("pandas", "pandas>=1.3.0"),
        ("imapclient", "imapclient>=2.2.0"),
        ("pyzmail", "pyzmail>=1.0.5"),
        ("pymupdf", "pymupdf>=1.20.0"),
        ("pypdf", "pypdf>=3.0.0"),
    ]
    
    sucesso_principais = 0
    for nome, pip_name in deps_principais:
        if instalar_pacote(nome, pip_name):
            sucesso_principais += 1
    
    print()
    
    # Dependências OCR melhorado (novas)
    print("📋 Dependências OCR Melhorado (NOVAS):")
    deps_ocr = [
        ("OpenCV", "opencv-python>=4.5.0"),
        ("EasyOCR", "easyocr>=1.6.0"),
        ("NumPy", "numpy>=1.21.0"),
    ]
    
    sucesso_ocr = 0
    for nome, pip_name in deps_ocr:
        if instalar_pacote(nome, pip_name):
            sucesso_ocr += 1
    
    print()
    
    # Dependências gerenciador referências
    print("📋 Dependências Gerenciador Referências:")
    deps_gerenciador = [
        ("SQLAlchemy", "sqlalchemy>=1.3.0"),
    ]
    
    sucesso_gerenciador = 0
    for nome, pip_name in deps_gerenciador:
        if instalar_pacote(nome, pip_name):
            sucesso_gerenciador += 1
    
    print()
    
    # Resumo
    total = len(deps_principais) + len(deps_ocr) + len(deps_gerenciador)
    sucesso_total = sucesso_principais + sucesso_ocr + sucesso_gerenciador
    
    print("=" * 60)
    print(f"✓ {sucesso_total}/{total} dependências instaladas com sucesso")
    print("=" * 60)
    print()
    
    if sucesso_total == total:
        print("✨ Instalação COMPLETA!")
        print()
        print("Próximos passos:")
        print("  1. python validar_sistema.py         # Validar tudo")
        print("  2. python processaexames.py           # Executar sistema")
        print()
        return 0
    else:
        print("⚠️  Algumas dependências falharam")
        print()
        print("Tente instalar manualmente:")
        print("  pip install opencv-python easyocr  # Principais novas")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
