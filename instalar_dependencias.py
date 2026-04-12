#!/usr/bin/env python3
"""
Instalador de Dependências - Sistema de Exames
Instala todos os packages necessários para o sistema funcionar
"""

import subprocess
import sys


def instalar_dependencias():
    """Instala todas as dependências necessárias"""
    
    dependencias = [
        "pandas>=1.3.0",
        "openpyxl>=3.1.0",
        "pdfplumber>=0.7.0",
        "pytesseract>=0.3.8",
        "pdf2image>=1.16.0",
        "imapclient>=2.3.0",
        "pyzmail>=1.0.3",
        "pillow>=8.0.0"
    ]
    
    print("=" * 70)
    print("INSTALADOR DE DEPENDÊNCIAS - Sistema de Exames")
    print("=" * 70)
    print()
    
    print("Dependências a instalar:")
    for i, dep in enumerate(dependencias, 1):
        print(f"  {i}. {dep}")
    
    print()
    print("Iniciando instalação...")
    print()
    
    # Instalar todas as dependencies
    comando = [sys.executable, "-m", "pip", "install", "-U"] + dependencias
    
    try:
        resultado = subprocess.run(comando, check=True)
        print()
        print("=" * 70)
        print("✅ SUCESSO! Todas as dependências foram instaladas.")
        print("=" * 70)
        print()
        print("Você pode agora executar:")
        print("  python gui_buscar_exames.py")
        print("  python interface_exames.py")
        print("  python processaexames.py")
        print()
        
        return True
    
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 70)
        print("❌ ERRO ao instalar dependências")
        print("=" * 70)
        print(f"Erro: {e}")
        print()
        print("Tente manualmente:")
        print(f"  pip install {' '.join(dependencias)}")
        print()
        return False
    
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False


def verificar_dependencias():
    """Verifica se as dependências estão instaladas"""
    
    print("\nVerificando dependências instaladas...")
    
    modulos_obrigatorios = [
        "pandas",
        "openpyxl",
        "pdfplumber",
        "pytesseract",
        "pdf2image",
        "imapclient",
        "pyzmail"
    ]
    
    todos_ok = True
    
    for modulo in modulos_obrigatorios:
        try:
            __import__(modulo)
            print(f"  ✓ {modulo}")
        except ImportError:
            print(f"  ✗ {modulo} - FALTANDO")
            todos_ok = False
    
    print()
    return todos_ok


def main():
    """Função principal"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Instalador de dependências para Sistema de Exames"
    )
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="Apenas verificar dependências sem instalar"
    )
    
    args = parser.parse_args()
    
    if args.verificar:
        ok = verificar_dependencias()
        if ok:
            print("✅ Todas as dependências estão instaladas!")
        else:
            print("⚠️ Algumas dependências estão faltando")
            print("Execute: python instalar_dependencias.py")
            sys.exit(1)
    else:
        ok = instalar_dependencias()
        if ok:
            verificar_dependencias()
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
