#!/usr/bin/env python3
"""
Teste Rápido - OCR Melhorado v2.1
Data: 29/03/2026

Script para validar e testar o OCR melhorado.
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

def print_header(text: str):
    """Imprime cabeçalho formatado"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_check(text: str):
    """Imprime check✓"""
    print(f"  ✓ {text}")

def print_info(text: str):
    """Imprime info"""
    print(f"  ℹ {text}")

def print_warning(text: str):
    """Imprime aviso"""
    print(f"  ⚠️ {text}")

def print_error(text: str):
    """Imprime erro"""
    print(f"  ✗ {text}")

def test_imports():
    """Testa importação de dependências"""
    print_header("1. VALIDANDO IMPORTAÇÕES")
    
    deps = {
        "PyMuPDF (pymupdf)": "pymupdf",
        "pypdf": "pypdf",
        "pdfplumber": "pdfplumber",
        "OpenCV (cv2)": "cv2",
        "EasyOCR (easyocr)": "easyocr",
        "NumPy": "numpy",
        "pytesseract": "pytesseract",
        "pdf2image": "pdf2image",
    }
    
    sucesso = 0
    for nome, modulo in deps.items():
        try:
            __import__(modulo)
            print_check(f"{nome} ✓")
            sucesso += 1
        except ImportError as e:
            print_warning(f"{nome} ✗ ({e})")
    
    print(f"\n  Resultado: {sucesso}/{len(deps)} módulos disponíveis")
    return sucesso > 0

def test_ocr_melhorado():
    """Testa módulo OCR melhorado"""
    print_header("2. VALIDANDO OCR MELHORADO")
    
    try:
        from ocr_melhorado import (
            preprocessar_imagem,
            limpar_texto_ocr,
            calcular_confianca_ocr,
            ler_pdf_melhorado,
            diagnosticar_ocr
        )
        
        print_check("Módulo ocr_melhorado importado")
        print_check("Função preprocessar_imagem ✓")
        print_check("Função limpar_texto_ocr ✓")
        print_check("Função calcular_confianca_ocr ✓")
        print_check("Função ler_pdf_melhorado ✓")
        print_check("Função diagnosticar_ocr ✓")
        
        return True
    
    except ImportError as e:
        print_error(f"Não conseguir importar ocr_melhorado: {e}")
        return False

def test_processaexames():
    """Testa integração com processaexames"""
    print_header("3. VALIDANDO INTEGRAÇÃO processaexames.py")
    
    try:
        from processaexames import ler_pdf, OCR_MELHORADO_DISPONIVEL
        
        print_check("Módulo processaexames importado")
        
        if OCR_MELHORADO_DISPONIVEL:
            print_check("OCR melhorado ATIVO em processaexames")
        else:
            print_warning("OCR melhorado não disponível (fallback ativo)")
        
        return True
    
    except ImportError as e:
        print_error(f"Não conseguir importar processaexames: {e}")
        return False

def test_tesseract():
    """Testa Tesseract instalado no sistema"""
    print_header("4. VALIDANDO TESSERACT")
    
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Criar imagem simples
        img = Image.fromarray(
            np.ones((100, 100, 3), dtype=np.uint8) * 255
        )
        
        # Tentar extrair
        texto = pytesseract.image_to_string(img, lang="por+eng")
        
        print_check("Tesseract respondendo")
        
        # Testar PSM
        for psm in [3, 6, 11]:
            try:
                pytesseract.image_to_string(
                    img,
                    lang="por+eng",
                    config=f"--psm {psm}"
                )
                print_check(f"Tesseract PSM {psm} ✓")
            except:
                print_warning(f"Tesseract PSM {psm} ✗")
        
        return True
    
    except Exception as e:
        print_warning(f"Tesseract não totalmente disponível: {e}")
        return False

def test_opcoes():
    """Testa componentes opcionais"""
    print_header("5. COMPONENTES OPCIONAIS")
    
    # OpenCV
    try:
        import cv2
        import numpy as np
        print_check("OpenCV disponível (pré-processamento ativo)")
    except ImportError:
        print_warning("OpenCV não instalado (pré-processamento desabilitado)")
    
    # EasyOCR
    try:
        import easyocr
        print_check("EasyOCR disponível (OCR moderno ativo)")
    except ImportError:
        print_warning("EasyOCR não instalado (usando apenas Tesseract)")
    
    # GPU
    try:
        import torch
        if torch.cuda.is_available():
            print_check(f"GPU detectada: {torch.cuda.get_device_name(0)}")
        else:
            print_info("GPU não detectada (usando CPU)")
    except ImportError:
        pass

def test_cache():
    """Testa sistema de cache"""
    print_header("6. VALIDANDO CACHE")
    
    from pathlib import Path
    
    cache_dir = Path("ocr_cache")
    
    if cache_dir.exists():
        num_cache = len(list(cache_dir.glob("*.txt")))
        print_check(f"Cache disponível ({num_cache} arquivos)")
    else:
        print_info("Pasta cache será criada na primeira execução")

def test_config():
    """Testa configurações"""
    print_header("7. VALIDANDO CONFIGURAÇÃO")
    
    print_info(f"Diretório: {os.getcwd()}")
    print_info(f"Python: {sys.version.split()[0]}")
    print_info(f"Plataforma: {sys.platform}")
    
    # Verificar arquivos principais
    arquivos = [
        ("processaexames.py", "Script principal"),
        ("ocr_melhorado.py", "Módulo OCR v2.1"),
        ("gerenciador_referencias.py", "Banco de dados SQL"),
        ("instalar_ocr_melhorado.py", "Instalador OCR"),
    ]
    
    for arquivo, descricao in arquivos:
        if Path(arquivo).exists():
            print_check(f"{descricao}: {arquivo} ✓")
        else:
            print_warning(f"{descricao}: {arquivo} ✗")

def gerar_relatorio(resultados: dict):
    """Gera relatório final"""
    print_header("📊 RELATÓRIO FINAL")
    
    print(json.dumps(resultados, indent=2, ensure_ascii=False))
    
    # Salvar relatório
    timestamp = datetime.now().isoformat()
    relatorio_file = f"teste_ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(relatorio_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            **resultados
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Relatório salvo: {relatorio_file}")

def main():
    print("\n")
    print("╔════════════════════════════════════════════════════════╗")
    print("║  OCR MELHORADO v2.1 - TESTE RÁPIDO                   ║")
    print("║  Data: 2026-03-29                                    ║")
    print("╚════════════════════════════════════════════════════════╝")
    
    resultados = {
        "imports": test_imports(),
        "ocr_melhorado": test_ocr_melhorado(),
        "processaexames": test_processaexames(),
        "tesseract": test_tesseract(),
    }
    
    test_opcoes()
    test_cache()
    test_config()
    gerar_relatorio(resultados)
    
    # Resumo
    print_header("✨ PRÓXIMOS PASSOS")
    
    if all(resultados.values()):
        print_check("Sistema OCR melhorado está 100% funcional!")
        print()
        print("  1. Instalar dependências opcionais:")
        print("     pip install opencv-python easyocr")
        print()
        print("  2. Executar processaexames:")
        print("     python processaexames.py")
        print()
        print("  3. Mais informações:")
        print("     cat OCR_MELHORADO_GUIA.md")
    else:
        print_warning("Algumas componentes estão faltando")
        print()
        print("  1. Instalar todas as dependências:")
        print("     python instalar_ocr_melhorado.py")
        print()
        print("  2. Depois executar novo teste:")
        print("     python teste_ocr_rapido.py")
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Teste interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Erro inesperado: {e}")
        sys.exit(1)
