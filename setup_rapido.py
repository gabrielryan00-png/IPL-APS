#!/usr/bin/env python3
"""
SETUP RÁPIDO - Instala tudo automaticamente e abre a interface
Execute: python setup_rapido.py
"""

import subprocess
import sys
import os


def main():
    """Setup rápido completo"""
    
    print("\n" + "=" * 70)
    print(" " * 15 + "🚀 SETUP RÁPIDO - SISTEMA DE EXAMES")
    print("=" * 70 + "\n")
    
    # Passo 1: Instalar dependências
    print("PASSO 1: Instalando dependências Python...")
    print("-" * 70)
    
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
    
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-U"] + dependencias
        resultado = subprocess.run(cmd, capture_output=True, text=True)
        
        if resultado.returncode == 0:
            print("✅ Dependências instaladas com sucesso!\n")
        else:
            print("⚠️ Algumas dependências podem não ter sido instaladas corretamente")
            print("Erro:", resultado.stderr)
    
    except Exception as e:
        print(f"❌ Erro ao instalar dependências: {e}\n")
        return False
    
    # Passo 2: Abrir interface
    print("PASSO 2: Abrindo interface principal...")
    print("-" * 70 + "\n")
    
    try:
        import tkinter as tk
        from menu_principal import MenuPrincipal
        
        root = tk.Tk()
        app = MenuPrincipal(root)
        root.mainloop()
        
        return True
    
    except ImportError as e:
        print(f"❌ Erro ao importar módulos: {e}")
        print("\nTente novamente em um momento...")
        return False
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


if __name__ == "__main__":
    try:
        sucesso = main()
        sys.exit(0 if sucesso else 1)
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
        sys.exit(1)
