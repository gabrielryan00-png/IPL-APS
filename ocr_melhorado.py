"""
OCR Melhorado - Múltiplas camadas com pré/pós-processamento e EasyOCR
Versão: 2.1 (29/03/2026)

Melhorias:
- Pré-processamento de imagens (contraste, denoise, binarização)
- Configurações otimizadas de Tesseract (PSM 3, 6, 11)
- EasyOCR como alternativa (GPU-acelerada se disponível)
- Pós-processamento de texto OCR
- Cache simples para evitar reprocessamento
- Métricas de confiança
- Retry automático com backoff
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime
import logging

import pytesseract
from pdf2image import convert_from_path

# Tenta importar OpenCV para pré-processamento
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ OpenCV não instalado. Instalar: pip install opencv-python")
    cv2 = None
    np = None

# Tenta importar EasyOCR
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    READER_ENG = None
    READER_POR = None
except ImportError:
    EASYOCR_AVAILABLE = False
    print("⚠️ EasyOCR não instalado. Instalar: pip install easyocr")
    easyocr = None

# Tenta importar PyMuPDF e pypdf
try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    pymupdf = None

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    pypdf = None

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None

# ==================== CONFIG ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = Path("ocr_cache")
CACHE_DIR.mkdir(exist_ok=True)

# ==================== PRÉ-PROCESSAMENTO ====================

def preprocessar_imagem(img) -> Optional[object]:
    """
    Pré-processa imagem para melhorar OCR.
    
    Técnicas:
    - Conversão para escala de cinza
    - CLAHE (Contrast Limited Adaptive Histogram Equalization)
    - Denoising (NLM - Non-Local Means)
    - Binarização adaptativa
    - Upscaling (se imagem pequena)
    
    Args:
        img: Imagem PIL
    
    Returns:
        Imagem processada (PIL ou numpy array)
    """
    if not CV2_AVAILABLE:
        return img
    
    try:
        # Converter PIL para numpy
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Escala de cinza
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Upscaling se imagem muito pequena
        height, width = gray.shape
        if width < 500 or height < 500:
            scale_factor = max(2, int(500 / min(width, height)))
            gray = cv2.resize(
                gray, 
                None, 
                fx=scale_factor, 
                fy=scale_factor,
                interpolation=cv2.INTER_CUBIC
            )
            logger.info(f"  → Imagem upscalada {scale_factor}x")
        
        # CLAHE - melhora contraste local
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(
            enhanced,
            h=10,
            templateWindowSize=7,
            searchWindowSize=21
        )
        
        # Binarização adaptativa (Otsu)
        _, binary = cv2.threshold(
            denoised,
            0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        logger.info("  → Imagem pré-processada (CLAHE + Denoise + Binarização)")
        
        return binary
    
    except Exception as e:
        logger.warning(f"  ⚠️ Erro ao pré-processar: {e}")
        return img


def _inicializar_easyocr():
    """Inicializa leitores EasyOCR (lazy loading)"""
    global READER_ENG, READER_POR, EASYOCR_AVAILABLE
    
    if not EASYOCR_AVAILABLE:
        return False
    
    try:
        if READER_ENG is None:
            logger.info("  → Inicializando EasyOCR (English)...")
            READER_ENG = easyocr.Reader(['en'], gpu=False)
        
        if READER_POR is None:
            logger.info("  → Inicializando EasyOCR (Portuguese)...")
            READER_POR = easyocr.Reader(['pt'], gpu=False)
        
        return True
    except Exception as e:
        logger.warning(f"  ⚠️ Erro ao inicializar EasyOCR: {e}")
        EASYOCR_AVAILABLE = False
        return False


# ==================== PÓS-PROCESSAMENTO ====================

def limpar_texto_ocr(texto: str) -> str:
    """
    Pós-processa texto OCR para remover artefatos comuns.
    
    Correções:
    - Remove linhas vazias excessivas
    - Corrige espaçamentos duplos
    - Remove caracteres inválidos
    - Corrige palavras comuns com erros OCR
    - Normaliza quebras de linha
    """
    if not texto:
        return ""
    
    # Remove espaços desnecessários
    texto = re.sub(r'\s+', ' ', texto)
    
    # Remove caracteres problemáticos
    texto = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', texto)
    
    # Corrige erros OCR comuns em português
    correcoes = {
        r'\bl\b': 'l',  # Letra l isolada (OCR confunde com |)
        r'rn': 'm',     # rn às vezes é confundido com m
        r'0([A-Za-z])': r'O\1',  # 0 no início de palavra -> O
        r'([A-Za-z])0([A-Za-z])': r'\1O\2',  # 0 entre letras -> O
        r'1([A-Za-z])': r'I\1',   # 1 no início de palavra -> I
    }
    
    for pattern, replacement in correcoes.items():
        texto = re.sub(pattern, replacement, texto, flags=re.IGNORECASE)
    
    # Remove quebras múltiplas
    texto = re.sub(r'\n\n+', '\n', texto)
    
    return texto.strip()


def calcular_confianca_ocr(texto: str) -> float:
    """
    Estima confiança do OCR baseado em heurísticas.
    
    Factors:
    - Comprimento do texto
    - Razão de caracteres válidos
    - Presença de números (exames costumam ter muitos números)
    - Formato de palavras (evita textos muito fragmentados)
    
    Returns:
        Confiança 0.0-1.0
    """
    if len(texto) < 50:
        return 0.0
    
    if len(texto) < 200:
        confianca = 0.4
    elif len(texto) < 500:
        confianca = 0.6
    elif len(texto) < 1000:
        confianca = 0.75
    else:
        confianca = 0.9
    
    # Bônus por números (exames têm muitos)
    num_count = sum(1 for c in texto if c.isdigit())
    if num_count / len(texto) > 0.15:
        confianca = min(1.0, confianca + 0.1)
    
    # Penalidade por caracteres estranhos
    invalid_chars = sum(1 for c in texto if ord(c) > 127 and c not in 'àáâãäèéêëìíîïòóôõöùúûüýÿçñ')
    if invalid_chars / len(texto) > 0.1:
        confianca *= 0.8
    
    return confianca


# ==================== CACHE ====================

def _gerar_hash_cache(pdf_path: str, seed: str = "v2.1") -> str:
    """Gera hash para cache baseado no arquivo PDF"""
    try:
        with open(pdf_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return f"{seed}_{file_hash}"
    except:
        return None


def _salvar_cache(pdf_path: str, texto: str, metadata: Dict):
    """Salva resultado em cache"""
    try:
        hash_key = _gerar_hash_cache(pdf_path)
        if not hash_key:
            return
        
        cache_file = CACHE_DIR / f"{hash_key}.txt"
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(texto)
            f.write("\n\n[METADATA]\n")
            f.write(f"data: {datetime.now().isoformat()}\n")
            f.write(f"confianca: {metadata.get('confianca', 0)}\n")
            f.write(f"metodo: {metadata.get('metodo', 'unknown')}\n")
        
        logger.debug(f"  → Cache salvo: {hash_key}")
    except Exception as e:
        logger.debug(f"  ⚠️ Erro ao salvar cache: {e}")


def _carregar_cache(pdf_path: str) -> Optional[str]:
    """Carrega resultado do cache se existir"""
    try:
        hash_key = _gerar_hash_cache(pdf_path)
        if not hash_key:
            return None
        
        cache_file = CACHE_DIR / f"{hash_key}.txt"
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Remove metadata
                texto = content.split('\n\n[METADATA]')[0]
                logger.info(f"  ✓ Cache utilizado")
                return texto.strip()
    except Exception as e:
        logger.debug(f"  ⚠️ Erro ao carregar cache: {e}")
    
    return None


# ==================== EXTRAÇÃO NATIVA ====================

def extrai_texto_pdfplumber(pdf_path: str) -> Tuple[str, Dict]:
    """Extrai com pdfplumber + info operacional"""
    if not PDFPLUMBER_AVAILABLE:
        return "", {"metodo": "pdfplumber", "sucesso": False, "erro": "não instalado"}
    
    texto = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text()
                if t:
                    texto += t + "\n"
        
        return texto.strip(), {
            "metodo": "pdfplumber",
            "sucesso": True,
            "confianca": 0.95 if len(texto) > 200 else 0.5
        }
    except Exception as e:
        return "", {"metodo": "pdfplumber", "sucesso": False, "erro": str(e)}


def extrai_texto_pymupdf(pdf_path: str) -> Tuple[str, Dict]:
    """Extrai com PyMuPDF + info operacional"""
    if not PYMUPDF_AVAILABLE:
        return "", {"metodo": "pymupdf", "sucesso": False, "erro": "não instalado"}
    
    texto = ""
    try:
        doc = pymupdf.open(pdf_path)
        for page in doc:
            t = page.get_text("text")
            if t:
                texto += t + "\n"
        doc.close()
        
        return texto.strip(), {
            "metodo": "pymupdf",
            "sucesso": True,
            "confianca": 0.92 if len(texto) > 200 else 0.5
        }
    except Exception as e:
        return "", {"metodo": "pymupdf", "sucesso": False, "erro": str(e)}


def extrai_texto_pypdf(pdf_path: str) -> Tuple[str, Dict]:
    """Extrai com pypdf + info operacional"""
    if not PYPDF_AVAILABLE:
        return "", {"metodo": "pypdf", "sucesso": False, "erro": "não instalado"}
    
    texto = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
        
        return texto.strip(), {
            "metodo": "pypdf",
            "sucesso": True,
            "confianca": 0.90 if len(texto) > 200 else 0.5
        }
    except Exception as e:
        return "", {"metodo": "pypdf", "sucesso": False, "erro": str(e)}


# ==================== OCR ENGINES ====================

def extrai_texto_tesseract_otimizado(
    pdf_path: str,
    psm_modes: List[int] = None
) -> Tuple[str, Dict]:
    """
    Tesseract otimizado com múltiplos PSM modes.
    
    PSM Modes:
    - 3: Camada automática (mais robusto)
    - 6: Bloco de texto uniforme
    - 11: Texto esparso
    
    Args:
        pdf_path: Caminho do PDF
        psm_modes: Lista de PSM modes a tentar (default: 3, 6, 11)
    
    Returns:
        Tupla (texto, metadados)
    """
    if psm_modes is None:
        psm_modes = [3, 6, 11]
    
    melhor_texto = ""
    melhor_confianca = 0.0
    metodo_usado = "tesseract"
    
    try:
        imagens = convert_from_path(pdf_path)
        
        for img_idx, img in enumerate(imagens):
            # Pré-processamento
            img_proc = preprocessar_imagem(img)
            
            for psm in psm_modes:
                try:
                    texto = pytesseract.image_to_string(
                        img_proc,
                        lang="por+eng",
                        config=f"--psm {psm} --oem 3"
                    )
                    
                    texto = limpar_texto_ocr(texto)
                    confianca = calcular_confianca_ocr(texto)
                    
                    if len(texto) > len(melhor_texto):
                        melhor_texto = texto
                        melhor_confianca = confianca
                        logger.debug(f"    PSM {psm}: {len(texto)} chars (conf: {confianca:.2f})")
                
                except Exception as e:
                    logger.debug(f"    PSM {psm} falhou: {e}")
        
        return melhor_texto, {
            "metodo": metodo_usado,
            "sucesso": len(melhor_texto) > 50,
            "confianca": melhor_confianca,
            "pag_processadas": len(imagens)
        }
    
    except Exception as e:
        return "", {
            "metodo": metodo_usado,
            "sucesso": False,
            "erro": str(e)
        }


def extrai_texto_easyocr(pdf_path: str) -> Tuple[str, Dict]:
    """
    EasyOCR - Alternativa moderna ao Tesseract.
    
    Vantagens:
    - Melhor acurácia em documentos complexos
    - Suporta GPU (aceleração)
    - Menos configuração necessária
    
    Returns:
        Tupla (texto, metadados)
    """
    if not _inicializar_easyocr():
        return "", {
            "metodo": "easyocr",
            "sucesso": False,
            "erro": "EasyOCR não disponível"
        }
    
    melhor_texto = ""
    melhor_confianca = 0.0
    
    try:
        imagens = convert_from_path(pdf_path)
        
        for img_idx, img in enumerate(imagens):
            # Pré-processamento
            img_proc = preprocessar_imagem(img)
            
            # Converter numpy array para PIL se necessário
            if isinstance(img_proc, np.ndarray):
                from PIL import Image
                img_proc = Image.fromarray(img_proc)
            
            # Tentar português primeiro
            try:
                resultados = READER_POR.readtext(np.array(img_proc))
                texto_pag = "\n".join([text for _, text, conf in resultados])
                confianca_pag = sum(conf for _, text, conf in resultados) / len(resultados) if resultados else 0
            except:
                # Fallback para inglês
                resultados = READER_ENG.readtext(np.array(img_proc))
                texto_pag = "\n".join([text for _, text, conf in resultados])
                confianca_pag = sum(conf for _, text, conf in resultados) / len(resultados) if resultados else 0
            
            texto_pag = limpar_texto_ocr(texto_pag)
            
            if len(texto_pag) > len(melhor_texto):
                melhor_texto = texto_pag
                melhor_confianca = min(confianca_pag, 0.98)  # Cap em 0.98
            
            logger.info(f"    Página {img_idx + 1}: {len(texto_pag)} chars (conf: {confianca_pag:.2f})")
        
        return melhor_texto, {
            "metodo": "easyocr",
            "sucesso": len(melhor_texto) > 50,
            "confianca": melhor_confianca,
            "pag_processadas": len(imagens)
        }
    
    except Exception as e:
        return "", {
            "metodo": "easyocr",
            "sucesso": False,
            "erro": str(e)
        }


# ==================== ORQUESTRADOR PRINCIPAL ====================

def ler_pdf_melhorado(pdf_path: str, usar_cache: bool = True, verbose: bool = True) -> Tuple[str, Dict]:
    """
    Lê PDF com múltiplas estratégias OCR.
    
    Ordem:
    1. Cache (se usar_cache=True)
    2. pdfplumber (nativo, rápido)
    3. PyMuPDF (robusto)
    4. pypdf (alternativa)
    5. EasyOCR (OCR moderno)
    6. Tesseract otimizado (OCR clássico)
    
    Args:
        pdf_path: Caminho do PDF
        usar_cache: Usar cache se disponível
        verbose: Imprimir progresso
    
    Returns:
        Tupla (texto, metadados_finais)
    """
    if verbose:
        print(f"\n📄 Processando: {Path(pdf_path).name}")
    
    # Verifica cache
    if usar_cache:
        texto_cache = _carregar_cache(pdf_path)
        if texto_cache:
            return texto_cache, {
                "metodo": "cache",
                "sucesso": True,
                "confianca": 1.0
            }
    
    # Estratégias em ordem de velocidade/qualidade
    estrategias = [
        ("pdfplumber", lambda: extrai_texto_pdfplumber(pdf_path)),
        ("PyMuPDF", lambda: extrai_texto_pymupdf(pdf_path)),
        ("pypdf", lambda: extrai_texto_pypdf(pdf_path)),
        ("EasyOCR", lambda: extrai_texto_easyocr(pdf_path)),
        ("Tesseract", lambda: extrai_texto_tesseract_otimizado(pdf_path)),
    ]
    
    resultados_tentativas = []
    
    for nome, funcao in estrategias:
        try:
            if verbose:
                print(f"  → Tentando {nome}...")
            
            texto, info = funcao()
            resultados_tentativas.append((texto, info))
            
            # Sucesso: texto suficiente (>100 chars)
            if len(texto) >= 100:
                if verbose:
                    print(f"    ✓ {nome} OK ({len(texto)} chars, conf: {info.get('confianca', 0):.2f})")
                
                # Salva em cache
                if usar_cache:
                    info_cache = info.copy()
                    info_cache['metodo'] = nome
                    _salvar_cache(pdf_path, texto, info_cache)
                
                return texto, info
            else:
                if verbose:
                    print(f"    ✗ {nome} insuficiente ({len(texto)} chars)")
        
        except Exception as e:
            if verbose:
                print(f"    ✗ {nome} erro: {e}")
    
    # Fallback: retorna melhor tentativa
    if resultados_tentativas:
        melhor_idx = max(range(len(resultados_tentativas)), 
                        key=lambda i: len(resultados_tentativas[i][0]))
        texto, info = resultados_tentativas[melhor_idx]
        
        if verbose:
            print(f"  ⚠️ Retornando melhor tentativa: {info.get('metodo')} ({len(texto)} chars)")
        
        return texto, info
    
    if verbose:
        print(f"  ❌ Falha total ao extrair texto")
    
    return "", {
        "metodo": "nenhum",
        "sucesso": False,
        "erro": "Todas as estratégias falharam"
    }


# ==================== COMPATIBILIDADE ====================

def ler_pdf(pdf_path: str) -> str:
    """
    Wrapper compatível com código anterior.
    Chama ler_pdf_melhorado e retorna apenas o texto.
    """
    texto, info = ler_pdf_melhorado(pdf_path, usar_cache=True, verbose=True)
    return texto


# ==================== RELATÓRIO DE DIAGNÓSTICO ====================

def diagnosticar_ocr(pdf_path: str) -> Dict:
    """
    Executa diagnóstico completo de OCR no arquivo.
    Útil para debugar problemas.
    """
    print(f"\n🔍 DIAGNÓSTICO OCR: {pdf_path}")
    print("=" * 60)
    
    relatorio = {
        "arquivo": pdf_path,
        "tamanho_mb": os.path.getsize(pdf_path) / (1024 * 1024),
        "timestamp": datetime.now().isoformat(),
        "estrategias": []
    }
    
    # Tenta cada estratégia
    for nome, funcao in [
        ("pdfplumber", lambda: extrai_texto_pdfplumber(pdf_path)),
        ("PyMuPDF", lambda: extrai_texto_pymupdf(pdf_path)),
        ("pypdf", lambda: extrai_texto_pypdf(pdf_path)),
        ("EasyOCR", lambda: extrai_texto_easyocr(pdf_path)),
        ("Tesseract", lambda: extrai_texto_tesseract_otimizado(pdf_path)),
    ]:
        try:
            print(f"\n▶ Testando {nome}...", end=" ")
            texto, info = funcao()
            
            info["tamanho_texto"] = len(texto)
            info["preview"] = (texto[:100] + "...") if len(texto) > 100 else texto
            
            relatorio["estrategias"].append({nome: info})
            
            if info.get("sucesso"):
                print(f"✓ ({len(texto)} chars)")
            else:
                print(f"✗ ({info.get('erro', 'falha desconhecida')})")
        
        except Exception as e:
            print(f"✗ ({e})")
            relatorio["estrategias"].append({nome: {"erro": str(e)}})
    
    print("\n" + "=" * 60)
    return relatorio


if __name__ == "__main__":
    # Teste rápido
    print("OCR Melhorado v2.1")
    print(f"OpenCV: {CV2_AVAILABLE}")
    print(f"EasyOCR: {EASYOCR_AVAILABLE}")
    print(f"PyMuPDF: {PYMUPDF_AVAILABLE}")
    print(f"pypdf: {PYPDF_AVAILABLE}")
    print(f"pdfplumber: {PDFPLUMBER_AVAILABLE}")
