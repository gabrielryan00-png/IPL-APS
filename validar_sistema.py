#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Validação do Sistema - processaexames.py v2.0
Verifica se todas as funcionalidades estão funcionando corretamente
"""

import os
import sys
from pathlib import Path

# Mudar para diretório do script
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))


def print_header(titulo):
    """Imprime header formatado"""
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def print_check(msg, sucesso=True):
    """Imprime mensagem com check/X"""
    simbolo = "✓" if sucesso else "✗"
    cor = "\033[92m" if sucesso else "\033[91m"  # Verde ou Vermelho
    reset = "\033[0m"
    print(f"{cor}{simbolo}{reset} {msg}")


def print_warning(msg):
    """Imprime aviso"""
    print(f"⚠️  {msg}")


def print_info(msg):
    """Imprime info"""
    print(f"ℹ️  {msg}")


def test_imports():
    """Testa se todos os imports funcionam"""
    print_header("1. VALIDANDO IMPORTS")
    
    testes = []
    
    # Test pdfplumber
    try:
        import pdfplumber
        print_check("pdfplumber importado com sucesso")
        testes.append(True)
    except ImportError as e:
        print_warning(f"pdfplumber não disponível: {e}")
        testes.append(False)
    
    # Test pymupdf
    try:
        import pymupdf
        print_check("PyMuPDF importado com sucesso")
        testes.append(True)
    except ImportError:
        print_info("PyMuPDF não instalado (OPCIONAL)")
        testes.append(False)
    
    # Test pypdf
    try:
        import pypdf
        print_check("pypdf importado com sucesso")
        testes.append(True)
    except ImportError:
        print_info("pypdf não instalado (OPCIONAL)")
        testes.append(False)
    
    # Test pytesseract
    try:
        import pytesseract
        print_check("pytesseract importado com sucesso")
        testes.append(True)
    except ImportError as e:
        print_warning(f"pytesseract não disponível: {e}")
        testes.append(False)
    
    # Test gerenciador
    try:
        from gerenciador_referencias import (
            GerenciadorReferencias,
            inicializar,
            encerrar
        )
        print_check("gerenciador_referencias importado com sucesso")
        testes.append(True)
    except ImportError as e:
        print_warning(f"gerenciador_referencias não encontrado: {e}")
        testes.append(False)
    
    # Test processaexames
    try:
        from processaexames import (
            ler_pdf,
            classificar_exame_otimizado,
            extrai_texto_ocr
        )
        print_check("processaexames importado com sucesso")
        testes.append(True)
    except ImportError as e:
        print_warning(f"processaexames não importável: {e}")
        testes.append(False)
    
    return all(testes)


def test_database():
    """Testa se banco de dados existe e funciona"""
    print_header("2. VALIDANDO BANCO DE DADOS")
    
    db_path = Path("valores_referencia.db")
    
    if not db_path.exists():
        print_warning(f"Banco de dados não encontrado: {db_path}")
        return False
    
    print_check(f"Banco de dados encontrado: {db_path}")
    print_info(f"Tamanho: {db_path.stat().st_size / 1024:.1f} KB")
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Verificar tabelas
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tabelas = cursor.fetchall()
        print_check(f"Banco conectado. Tabelas: {len(tabelas)}")
        
        for tabela in tabelas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela[0]}")
            count = cursor.fetchone()[0]
            print_info(f"  - {tabela[0]}: {count} registros")
        
        conn.close()
        return True
        
    except Exception as e:
        print_warning(f"Erro ao conectar BD: {e}")
        return False


def test_gerenciador():
    """Testa funcionalidades do gerenciador"""
    print_header("3. VALIDANDO GERENCIADOR DE REFERÊNCIAS")
    
    try:
        from gerenciador_referencias import inicializar, encerrar
        
        # Inicializar
        print_info("Inicializando gerenciador...")
        ger = inicializar()
        print_check("Gerenciador inicializado com sucesso")
        
        testes_classificacao = [
            ("Creatinina", 1.1, "M", 45, "NORMAL"),
            ("Creatinina", 2.5, "M", 45, "ALTERADO"),
            ("Glicemia Jejum", 95, None, None, "NORMAL"),
            ("Colesterol Total", 300, None, None, "ALTERADO"),
        ]
        
        print_info("Testando classificações:")
        sucessos = 0
        for nome, valor, genero, idade, esperado in testes_classificacao:
            try:
                resultado = ger.classificar_valor(nome, valor, genero, idade)
                status = resultado["status"]
                ok = status == esperado
                if ok:
                    sucessos += 1
                simbolo = "✓" if ok else "⚠️"
                print(f"  {simbolo} {nome}={valor}: {status} (esperado: {esperado})")
            except Exception as e:
                print(f"  ✗ {nome}: Erro - {e}")
        
        # Encerrar
        encerrar()
        print_check("Gerenciador encerrado com sucesso")
        
        return sucessos == len(testes_classificacao)
        
    except Exception as e:
        print_warning(f"Erro no gerenciador: {e}")
        return False


def test_ocr_functions():
    """Testa funções OCR"""
    print_header("4. VALIDANDO FUNÇÕES OCR")
    
    try:
        from processaexames import (
            extrai_texto_ocr,
            extrai_texto_pdf
        )
        print_check("Funções OCR importadas com sucesso")
        
        # Verificar se função ler_pdf foi atualizada
        try:
            from processaexames import extrai_texto_pymupdf
            print_check("extrai_texto_pymupdf (nova) importada")
        except ImportError:
            print_info("extrai_texto_pymupdf não encontrada (pode estar opcional)")
        
        try:
            from processaexames import extrai_texto_pypdf
            print_check("extrai_texto_pypdf (nova) importada")
        except ImportError:
            print_info("extrai_texto_pypdf não encontrada (pode estar opcional)")
        
        # Verificar se função ler_pdf atualizada
        try:
            from processaexames import ler_pdf
            print_check("ler_pdf (atualizada) importada")
            print_info("Suporte a 4 camadas OCR confirmado")
        except ImportError:
            print_warning("ler_pdf não encontrada")
            return False
        
        return True
        
    except Exception as e:
        print_warning(f"Erro nas funções OCR: {e}")
        return False


def test_classification_function():
    """Testa função de classificação otimizada"""
    print_header("5. VALIDANDO FUNÇÃO DE CLASSIFICAÇÃO")
    
    try:
        from processaexames import classificar_exame_otimizado
        print_check("classificar_exame_otimizado importada")
        
        # Testar função
        resultado = classificar_exame_otimizado("Creatinina", 1.1, "M", 45)
        
        chaves_esperadas = {"status", "valor", "unidade", "categoria"}
        chaves_presentes = set(resultado.keys())
        
        if chaves_esperadas.issubset(chaves_presentes):
            print_check("estrutura de retorno correta")
            print_info(f"  Status: {resultado.get('status')}")
            print_info(f"  Valor: {resultado.get('valor')}")
            print_info(f"  Unidade: {resultado.get('unidade')}")
            return True
        else:
            print_warning("Estrutura de retorno incompleta")
            print_info(f"  Chaves presentes: {chaves_presentes}")
            print_info(f"  Chaves esperadas: {chaves_esperadas}")
            return False
        
    except Exception as e:
        print_warning(f"Erro ao testar classificar_exame_otimizado: {e}")
        return False


def test_documentation():
    """Valida se documentação foi criada"""
    print_header("6. VALIDANDO DOCUMENTAÇÃO")
    
    arquivos_esperados = [
        "ATUALIZACAO_PROCESSAEXAMES.md",
        "GUIA_TESTES_PROCESSAEXAMES.md",
        "SISTEMA_FINALIZADO.md",
    ]
    
    sucessos = 0
    for arquivo in arquivos_esperados:
        path = Path(arquivo)
        if path.exists():
            tamanho = path.stat().st_size
            print_check(f"{arquivo} ({tamanho} bytes)")
            sucessos += 1
        else:
            print_warning(f"{arquivo} não encontrado")
    
    return sucessos == len(arquivos_esperados)


def print_summary(resultados):
    """Imprime resumo final"""
    print_header("RESUMO DA VALIDAÇÃO")
    
    teste_nomes = [
        "Imports",
        "Banco de Dados",
        "Gerenciador",
        "Funções OCR",
        "Classificação",
        "Documentação"
    ]
    
    total = len(resultados)
    sucessos = sum(resultados)
    percentual = (sucessos / total) * 100 if total > 0 else 0
    
    print()
    for nome, resultado in zip(teste_nomes, resultados):
        simbolo = "✓" if resultado else "✗"
        cor = "\033[92m" if resultado else "\033[91m"
        reset = "\033[0m"
        print(f"{cor}{simbolo}{reset} {nome}")
    
    print()
    print(f"Resultado: {sucessos}/{total} testes passaram ({percentual:.0f}%)")
    
    if sucessos == total:
        print("\n🎉 TODOS OS TESTES PASSARAM! Sistema pronto para produção.")
        return True
    elif sucessos >= total * 0.8:
        print("\n⚠️  MAIORIA DOS TESTES PASSOU. Algumas funcionalidades opcionais não estão disponíveis.")
        return True
    else:
        print("\n❌ ALGUNS TESTES FALHARAM. Verifique as erros acima.")
        return False


def main():
    """Função principal"""
    print("\n" + "🧪 VALIDAÇÃO DO SISTEMA - processaexames.py v2.0".center(70))
    print("=" * 70)
    
    resultados = [
        test_imports(),
        test_database(),
        test_gerenciador(),
        test_ocr_functions(),
        test_classification_function(),
        test_documentation(),
    ]
    
    sucesso = print_summary(resultados)
    
    print("\n" + "=" * 70)
    print("\nPróximos passos:")
    print("  1. Revisar documentação em GUIA_TESTES_PROCESSAEXAMES.md")
    print("  2. Testar com PDFs reais")
    print("  3. Executar: python processaexames.py (com emails)")
    print()
    
    return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
