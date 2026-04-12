"""
Script de teste para validar instalação e funcionamento da interface
Run: python testar_interface.py
"""

import sys
import os


def testar_imports():
    """Testa se todos os módulos necessários estão disponíveis"""
    print("=" * 60)
    print("TESTE DE IMPORTS")
    print("=" * 60)
    
    modulos_obrigatorios = [
        ("tkinter", "Interface gráfica (geralmente incluído com Python)"),
        ("pandas", "Processamento de dados"),
        ("openpyxl", "Trabalhar com arquivos Excel")
    ]
    
    todos_ok = True
    
    for modulo, descricao in modulos_obrigatorios:
        try:
            __import__(modulo)
            print(f"✓ {modulo:20} - {descricao}")
        except ImportError:
            print(f"✗ {modulo:20} - FALTANDO! {descricao}")
            todos_ok = False
    
    print()
    return todos_ok


def testar_arquivos():
    """Testa se arquivos necessários existem"""
    print("=" * 60)
    print("VERIFICAÇÃO DE ARQUIVOS")
    print("=" * 60)
    
    arquivos_necessarios = [
        ("gui_buscar_exames.py", "Interface de busca"),
        ("interface_exames.py", "Interface integrada"),
        ("processaexames.py", "Processador de exames"),
        ("README_GUI.md", "Documentação")
    ]
    
    todos_ok = True
    
    for arquivo, descricao in arquivos_necessarios:
        if os.path.exists(arquivo):
            tamanho = os.path.getsize(arquivo) / 1024  # em KB
            print(f"✓ {arquivo:30} - {descricao} ({tamanho:.1f} KB)")
        else:
            print(f"✗ {arquivo:30} - FALTANDO! {descricao}")
            todos_ok = False
    
    print()
    return todos_ok


def testar_dados():
    """Testa se arquivo de dados existe"""
    print("=" * 60)
    print("VERIFICAÇÃO DE DADOS")
    print("=" * 60)
    
    if os.path.exists("relatorio_exames.xlsx"):
        size = os.path.getsize("relatorio_exames.xlsx") / 1024 / 1024
        print(f"✓ relatorio_exames.xlsx encontrado ({size:.2f} MB)")
        
        try:
            import pandas as pd
            xls = pd.ExcelFile("relatorio_exames.xlsx")
            print(f"  Abas disponíveis: {', '.join(xls.sheet_names)}")
            
            if "exames" in xls.sheet_names:
                df = pd.read_excel("relatorio_exames.xlsx", sheet_name="exames")
                print(f"  Total de exames: {len(df)}")
                print(f"  Colunas: {', '.join(df.columns[:5])}...")
        except Exception as e:
            print(f"✗ Erro ao ler arquivo: {e}")
    else:
        print("⚠ relatorio_exames.xlsx não encontrado")
        print("  Execute processaexames.py primeiro para gerar dados")
    
    print()


def executar_teste_gui():
    """Testa se a interface GUI funciona"""
    print("=" * 60)
    print("TESTE DE INTERFACE GRÁFICA")
    print("=" * 60)
    
    try:
        import tkinter as tk
        from gui_buscar_exames import GerenciadorExames
        
        print("✓ Módulo gui_buscar_exames importado com sucesso")
        
        gerenciador = GerenciadorExames()
        print("✓ GerenciadorExames instanciado")
        
        if gerenciador.df_exames is not None:
            print(f"✓ Dados carregados: {len(gerenciador.df_exames)} exames")
            
            # Testa buscas
            df_alt = gerenciador.buscar_analitos_alterados()
            print(f"✓ Busca de alterados: {len(df_alt)} registros")
            
            df_pac = gerenciador.buscar_por_paciente("Silva")
            print(f"✓ Busca por paciente: {len(df_pac)} registros")
        else:
            print("⚠ Sem dados carregados (execute processaexames.py primeiro)")
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    print()


def mostrar_instruções():
    """Mostra instruções de uso"""
    print("=" * 60)
    print("COMO USAR A INTERFACE")
    print("=" * 60)
    print()
    print("1️⃣ Interface de Busca (recomendado):")
    print("   python gui_buscar_exames.py")
    print()
    print("2️⃣ Interface Integrada:")
    print("   python interface_exames.py")
    print()
    print("3️⃣ Com opcões:")
    print("   python executar_com_interface.py --gui")
    print("   python executar_com_interface.py --cli")
    print("   python executar_com_interface.py --buscar")
    print()
    print("4️⃣ Processamento tradicional:")
    print("   python processaexames.py")
    print()
    print("=" * 60)
    print()


def main():
    """Função principal de teste"""
    
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  TESTE DE INSTALAÇÃO - INTERFACE DE EXAMES".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Executa testes
    deps_ok = testar_imports()
    arquivos_ok = testar_arquivos()
    testar_dados()
    
    try:
        executar_teste_gui()
    except Exception as e:
        print(f"Erro ao testar GUI: {e}")
    
    mostrar_instruções()
    
    # Resumo
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    if deps_ok and arquivos_ok:
        print("✓ TUDO OK! Você pode usar a interface.")
        print("\nInicie com:")
        print("  python gui_buscar_exames.py")
    else:
        print("⚠ Alguns problemas foram encontrados:")
        if not deps_ok:
            print("  - Instale dependências: pip install pandas openpyxl")
        if not arquivos_ok:
            print("  - Verifique se todos os arquivos foram criados corretamente")
    
    print()


if __name__ == "__main__":
    main()
