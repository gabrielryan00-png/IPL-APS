import os
import re
import smtplib
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from email.utils import formatdate
from typing import Dict, List, Union, Optional, Tuple
import sqlite3
from contextlib import contextmanager

# Carrega variáveis de ambiente do .env (se disponível)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import imapclient
import pyzmail

# Importar OCR melhorado (v2.1)
try:
    from ocr_melhorado import ler_pdf_melhorado, diagnosticar_ocr
    OCR_MELHORADO_DISPONIVEL = True
except ImportError:
    OCR_MELHORADO_DISPONIVEL = False
    print("⚠️ ocr_melhorado não encontrado. Usando fallback.")

# Importar camadas de OCR avançado (compatibilidade)
try:
    import pymupdf  # PyMuPDF
except ImportError:
    pymupdf = None
    print("⚠️ pymupdf não instalado. Instalor: pip install pymupdf")

try:
    import pypdf  # Antes era PyPDF2, agora é pypdf
except ImportError:
    pypdf = None
    print("⚠️ pypdf não instalado. Instalar: pip install pypdf")

# Importar gerenciador de referências
try:
    from gerenciador_referencias import GerenciadorReferencias, inicializar, encerrar
    GERENCIADOR_DISPONIVEL = True
except ImportError:
    GERENCIADOR_DISPONIVEL = False
    print("⚠️ gerenciador_referencias não encontrado. Usando modo compatível.")

# =========================
# CONFIG GMAIL + PASTAS
# Lê do .env — nunca hardcode credenciais em código
# =========================
EMAIL        = os.getenv("GMAIL_EMAIL",    "")
SENHA_APP    = os.getenv("GMAIL_SENHA",    "")
REMETENTE_LAB = os.getenv("REMETENTE_LAB", "")

_DATA_DIR    = os.getenv("DATA_DIR", ".")
PASTA_EXAMES = os.path.join(_DATA_DIR, "exames")
RELATORIO    = os.path.join(_DATA_DIR, "relatorio_exames.xlsx")
DB_PATH      = os.path.join(_DATA_DIR, "exames.db")

LABEL_ALTERADO   = "Exames/🔴 ALTERADO - VERIFICAR"
LABEL_NORMAL     = "Exames/🟢 NORMAL"
LABEL_REVISAR    = "Exames/🟡 REVISAR (falha extração)"
LABEL_SINALIZADO = "Exames/✅ Sinalizado"  # evita duplicar resposta

os.makedirs(PASTA_EXAMES, exist_ok=True)

# =========================
# INICIALIZAR GERENCIADOR DE REFERÊNCIAS
# =========================
GERENCIADOR = None
if GERENCIADOR_DISPONIVEL:
    try:
        GERENCIADOR = inicializar()
        print("✓ Gerenciador de referências carregado")
    except Exception as e:
        print(f"⚠️ Erro ao carregar gerenciador: {e}")
        GERENCIADOR = None


# =========================
# PDF: EXTRAÇÃO + OCR
# =========================
def extrai_texto_pdf(pdf_path: str) -> str:
    texto = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                t = pagina.extract_text()
                if t:
                    texto += t + "\n"
    except Exception as e:
        print(f"Erro ao extrair texto com pdfplumber de {pdf_path}: {e}")
    return texto.strip()

def extrai_texto_pymupdf(pdf_path: str) -> str:
    """Extrai texto usando PyMuPDF (fitz)"""
    if not pymupdf:
        return ""
    
    texto = ""
    try:
        doc = pymupdf.open(pdf_path)
        for pagina in doc:
            t = pagina.get_text("text")
            if t:
                texto += t + "\n"
        doc.close()
    except Exception as e:
        print(f"Erro ao extrair texto com pymupdf de {pdf_path}: {e}")
    return texto.strip()

def extrai_texto_pypdf(pdf_path: str) -> str:
    """Extrai texto usando pypdf"""
    if not pypdf:
        return ""
    
    texto = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
    except Exception as e:
        print(f"Erro ao extrair texto com pypdf de {pdf_path}: {e}")
    return texto.strip()

def extrai_texto_ocr(pdf_path: str) -> str:
    """
    ✨ NOVO: Usa OCR melhorado v2.1 com pré/pós-processamento
    Fallback para Tesseract básico se ocr_melhorado não disponível
    """
    if OCR_MELHORADO_DISPONIVEL:
        try:
            texto, info = ler_pdf_melhorado(pdf_path, usar_cache=True, verbose=False)
            if texto:
                return texto
        except Exception as e:
            print(f"Aviso: OCR melhorado falhou, tentando fallback: {e}")
    
    # Fallback: Tesseract básico (compatibilidade)
    texto = ""
    try:
        imagens = convert_from_path(pdf_path)
        for img in imagens:
            texto += pytesseract.image_to_string(img, lang="por+eng") + "\n"
    except Exception as e:
        print(f"Erro no OCR de {pdf_path}: {e}")
    return texto.strip()

def ler_pdf(pdf_path: str) -> str:
    """
    ✨ NOVO: Lê PDF com múltiplas camadas OCR melhoradas (v2.1)
    
    Ordem de prioridade:
    1. OCR melhorado (pdfplumber + PyMuPDF + pypdf + EasyOCR + Tesseract)
    2. Fallback manual (compatibilidade com código antigo)
    """
    
    # Usa nova estratégia melhorada se disponível
    if OCR_MELHORADO_DISPONIVEL:
        try:
            print("  → Usando OCR Melhorado v2.1...")
            texto, info = ler_pdf_melhorado(pdf_path, usar_cache=True, verbose=True)
            if len(texto) >= 100:
                print(f"    ✓ {info.get('metodo', 'desconhecido')} OK (conf: {info.get('confianca', 0):.2f})")
                return texto
        except Exception as e:
            print(f"  ⚠️ OCR melhorado falhou: {e}. Tentando fallback...")
    
    # Fallback para método anterior (compatibilidade)
    print("  → Usando método legado...")
    
    # Camada 1: pdfplumber (padrão principal)
    print("  → Tentando pdfplumber...")
    texto = extrai_texto_pdf(pdf_path)
    if len(texto) >= 100:
        print("    ✓ pdfplumber OK")
        return texto
    
    # Camada 2: PyMuPDF
    print("  → Tentando PyMuPDF...")
    texto = extrai_texto_pymupdf(pdf_path)
    if len(texto) >= 100:
        print("    ✓ PyMuPDF OK")
        return texto
    
    # Camada 3: pypdf
    print("  → Tentando pypdf...")
    texto = extrai_texto_pypdf(pdf_path)
    if len(texto) >= 100:
        print("    ✓ pypdf OK")
        return texto
    
    # Camada 4: OCR com tesseract básico
    print("  → Usando OCR (tesseract)...")
    texto = extrai_texto_ocr(pdf_path)
    if len(texto) >= 100:
        print("    ✓ OCR OK")
        return texto
    
    print("  ⚠️ Falha ao extrair texto do PDF")
    return texto

# =========================
# METADADOS / PACIENTE
# =========================
def extrair_nome_paciente_universal(texto: str) -> str:
    match = re.search(
        r'Nome\s*:\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)(?:\s+(?:Invalid|S\s*e\s*x\s*o|Sexo|CPF|RG)|$)',
        texto,
        re.IGNORECASE
    )
    if match:
        nome = match.group(1).strip()
        nome = re.sub(r'\s+(Invalid|barcode|data|CPF).*', '', nome, flags=re.IGNORECASE)
        if len(nome) > 3 and len(nome.split()) >= 2:
            return nome

    match = re.search(
        r'N\.?\s*Pedido\s+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)\s+N\.\s*Registro',
        texto,
        re.IGNORECASE
    )
    if match:
        nome = match.group(1).strip()
        nome = re.sub(r'\d+', '', nome).strip()
        if len(nome) > 3:
            return nome

    return ""

def extrair_metadados(texto: str) -> Dict[str, str]:
    metadados = {}

    nome_paciente = extrair_nome_paciente_universal(texto)
    if nome_paciente:
        metadados["Paciente"] = nome_paciente

    match_pedido = re.search(r"(?:N\.?\s*Pedido|Pedido)[:\s]+(\d+)", texto, re.IGNORECASE)
    if match_pedido:
        metadados["Pedido"] = match_pedido.group(1)

    match_nasc = re.search(
        r"(?:Dt\.?\s*Nasc|Data\s*Nascimento|Nascimento)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})",
        texto,
        re.IGNORECASE
    )
    if match_nasc:
        metadados["Dt Nasc"] = match_nasc.group(1)

    match_medico = re.search(
        r"Solicitante[:\s]+([A-ZÀ-Ü][A-Za-zà-ÿ\s\.]+?)(?:\s+Data|\n)",
        texto,
        re.IGNORECASE
    )
    if match_medico:
        metadados["Medico"] = match_medico.group(1).strip()

    # Data de Emissão do laudo (= data de realização, não de processamento)
    # Suporta: "Data de Emissão : 0 6 :/04/2026" (dígitos separados por espaço)
    #          "Emissão: 15/12/2025" (sem "Data de")
    match_emissao = re.search(
        r"(?:Data\s+de\s+)?Emiss[aã]o\s*[:\s]+"
        r"(\d\s*\d)\s*:?/(\d{2})/(\d{4})",
        texto, re.IGNORECASE
    )
    if match_emissao:
        dia = re.sub(r"\s+", "", match_emissao.group(1))
        metadados["Data Exame"] = f"{dia}/{match_emissao.group(2)}/{match_emissao.group(3)}"

    return metadados

# =========================
# NORMALIZAÇÃO / FILTROS
# =========================
def normalizar_valor(valor_str: str) -> Union[float, str]:
    if not valor_str or not isinstance(valor_str, str):
        return valor_str

    valor_str = valor_str.strip().replace(",", ".")

    valores_qualitativos = [
        "REAGENTE", "NAO REAGENTE", "NÃO REAGENTE", "NEGATIVO", "POSITIVO",
        "AUSENTE", "PRESENTE", "DETECTADO", "NAO DETECTADO", "NÃO DETECTADO",
        "NORMAL", "ALTERADO", "AUSENTES", "RAROS", "NUMEROSOS", "INCONTÁVEIS",
        "TRAÇOS", "TRACOS"
    ]

    valor_upper = valor_str.upper()
    for val_qual in valores_qualitativos:
        if val_qual in valor_upper:
            return valor_str

    try:
        valor_limpo = re.sub(r"[^\d\.\-]", "", valor_str)
        if valor_limpo and valor_limpo not in [".", "-", ".-"]:
            return float(valor_limpo)
    except ValueError:
        pass

    return valor_str

# Importa validadores do módulo utilitário (evita duplicação)
from utils_analitos import e_nome_exame_valido, e_analito_observacao

# =========================
# HELPERS DE REFERÊNCIA
# =========================
def _to_float(x: str) -> Optional[float]:
    """Parse numeric string handling both comma-decimal (BR) and dot-decimal formats."""
    try:
        s = x.strip()
        if "," in s and "." in s:
            # Both separators: last one is the decimal
            if s.rindex(",") > s.rindex("."):
                s = s.replace(".", "").replace(",", ".")  # "1.234,56" → "1234.56"
            else:
                s = s.replace(",", "")  # "1,234.56" → "1234.56"
        elif "," in s:
            s = s.replace(",", ".")  # "3,80" → "3.80"
        elif "." in s:
            parts = s.split(".")
            # "10.000" (exactly 3 decimal digits) = thousands separator
            if len(parts) == 2 and len(parts[1]) == 3:
                s = s.replace(".", "")  # "10.000" → "10000"
            # else dot is decimal separator — parse as-is
        return float(s)
    except Exception:
        return None

def _parse_ref_text(ref_txt: str) -> Tuple[Optional[float], Optional[float], str]:
    """
    Lê referência em formatos comuns de laudo:
      - "De 5 a 7"
      - "0 - 10.000"
      - "até 10" / "ate 10"
      - "Normal até 10"
      - "inferior a 5,7"
      - "maior que 4,0"
      - "Negativo"
    Retorna (ref_inf, ref_sup, ref_txt_limpo)
    """
    if not ref_txt:
        return None, None, ""

    rt = re.sub(r"\s+", " ", ref_txt).strip()

    # Qualitativo
    if re.search(r"\b(negativo|não reagente|nao reagente|ausente)\b", rt, re.IGNORECASE):
        return None, None, rt
    if re.search(r"\b(positivo|reagente| presente|detectado)\b", rt, re.IGNORECASE):
        return None, None, rt

    # De X a Y / X - Y
    m = re.search(r"(?:de\s*)?([\d\.,]+)\s*(?:a|até|ate|-)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v1 = _to_float(m.group(1))
        v2 = _to_float(m.group(2))
        if v1 is not None and v2 is not None:
            return min(v1, v2), max(v1, v2), rt

    # até X / inferior a X / menor que X
    m = re.search(r"(?:até|ate|inferior a|menor que|normal até|normal ate)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return None, v, rt

    # maior que X / superior a X
    m = re.search(r"(?:maior que|superior a)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, None, rt

    return None, None, rt

def determinar_status(valor, ref_inf, ref_sup, ref_texto: str = "") -> str:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "REVISAR"

    # numérico
    if isinstance(valor, (int, float)):
        if isinstance(ref_inf, (int, float)) and isinstance(ref_sup, (int, float)):
            if valor < ref_inf:
                return "[ALTERADO] ABAIXO"
            if valor > ref_sup:
                return "[ALTERADO] ACIMA"
            return "NORMAL"

        if isinstance(ref_sup, (int, float)) and not isinstance(ref_inf, (int, float)):
            return "NORMAL" if valor <= ref_sup else "[ALTERADO] ACIMA"

        if isinstance(ref_inf, (int, float)) and not isinstance(ref_sup, (int, float)):
            return "NORMAL" if valor >= ref_inf else "[ALTERADO] ABAIXO"

        return "REVISAR"

    # qualitativo
    if isinstance(valor, str):
        v = valor.strip().upper()
        if v in ("NEGATIVO", "NÃO REAGENTE", "NAO REAGENTE", "AUSENTE", "NÃO DETECTADO", "NAO DETECTADO"):
            return "NORMAL"
        if v in ("POSITIVO", "REAGENTE", "PRESENTE", "DETECTADO"):
            return "[ALTERADO]"
        # exemplos urina: "1+", "2+", "3+" etc -> não cravo como alterado automaticamente (triagem)
        if re.fullmatch(r"\d\+", v):
            return "REVISAR"
        return "REVISAR"

    return "REVISAR"

def classificar_exame_otimizado(
    nome_exame: str,
    valor: Union[float, str],
    genero: Optional[str] = None,
    idade: Optional[int] = None
) -> Dict[str, Union[str, float]]:
    """
    Classifica exame usando gerenciador de referências (SQL).
    Fallback automático para determinar_status se gerenciador não disponível.
    
    Args:
        nome_exame: Nome do exame (ex: "Creatinina")
        valor: Valor do exame (numérico ou texto)
        genero: 'M' ou 'F' (opcional)
        idade: Idade em anos (opcional)
    
    Returns:
        Dict com {status, valor, unidade, categoria, referencia, detalhes}
    """
    
    # Se gerenciador disponível, usar ele (NOVO)
    if GERENCIADOR:
        try:
            # Tentar converter para float
            try:
                valor_float = float(str(valor).replace(",", "."))
                resultado = GERENCIADOR.classificar_valor(
                    nome_exame=nome_exame,
                    valor=valor_float,
                    genero=genero,
                    idade=idade
                )
            except (ValueError, TypeError):
                # Valor qualitativo
                resultado = GERENCIADOR.classificar_valor_qualitativo(
                    nome_exame=nome_exame,
                    valor=str(valor)
                )
            
            # Normalizar status para compatibilidade
            status = resultado.get('status', 'REVISAR')
            if status == 'NORMAL':
                status_final = "NORMAL"
            elif status == 'ALTERADO':
                status_final = "[ALTERADO]"
            elif status == 'LIMÍTROFE':
                status_final = "[LIMÍTROFE]"
            else:
                status_final = "REVISAR"
            
            return {
                'status': status_final,
                'valor': resultado.get('valor', valor),
                'unidade': resultado.get('unidade', ''),
                'categoria': resultado.get('categoria', ''),
                'referencia': resultado.get('referencia', ''),
                'detalhes': resultado.get('detalhes', '')
            }
        except Exception as e:
            print(f"  ⚠️ Erro ao classificar com gerenciador: {e} (usando fallback)")
    
    # Fallback: determinar_status (COMPATÍVEL COM CÓDIGO ANTIGO)
    # Esta função não classifica como LIMÍTROFE, só NORMAL/ALTERADO
    return {'status': 'REVISAR', 'valor': valor, 'unidade': '', 'categoria': '', 'referencia': ''}

# =========================
# PARSERS DEDICADOS: URINA E HEMOGRAMA
# =========================
def _is_urina_context(texto_upper: str) -> bool:
    return any(k in texto_upper for k in ("URINA", "EAS", "URINA TIPO", "ELEMENTOS ANORMAIS", "SEDIMENTO"))

def _is_hemograma_context(texto_upper: str) -> bool:
    return "HEMOGRAMA" in texto_upper or "ERITROGRAMA" in texto_upper or "LEUCOGRAMA" in texto_upper

def extrair_urina(texto: str) -> List[Dict[str, Union[str, float]]]:
    """
    Lê linhas tabulares do EAS/Urina:
      "PH................: 6.0 De 5 a 7"
      "Eritrócitos..: 1000 /ml De 0 a 10.000/ml"
      "Proteínas.....: Negativo Negativo"
    """
    resultados: List[Dict[str, Union[str, float]]] = []
    texto_upper = texto.upper()
    if not _is_urina_context(texto_upper):
        return resultados

    # Limitar ao bloco da seção de urina (entre o cabeçalho e a próxima seção)
    todas_linhas = texto.splitlines()
    inicio = None
    fim = len(todas_linhas)
    _URINA_HEADER = re.compile(r'\b(URINA\s*TIPO|URINA\s*ROTINA|EAS\b|ELEMENTOS\s+ANORMAIS|SEDIMENTO\s+URIN)', re.IGNORECASE)
    _NOVA_SECAO = re.compile(r'^(HEMOGRAMA|ERITROGRAMA|LEUCOGRAMA|LIPIDOGRAMA|COAGULOGRAMA|BIOQUÍMICA|BIOQUIMICA)', re.IGNORECASE)
    for idx, ln in enumerate(todas_linhas):
        if inicio is None and _URINA_HEADER.search(ln):
            inicio = idx
        elif inicio is not None and idx > inicio + 3 and _NOVA_SECAO.match(ln.strip()):
            fim = idx
            break
    if inicio is None:
        linhas = [l.rstrip() for l in todas_linhas if l.strip()]
    else:
        linhas = [l.rstrip() for l in todas_linhas[inicio:fim] if l.strip()]

    for ln in linhas:
        # Normaliza separadores
        line = re.sub(r"\s+", " ", ln).strip()

        # Padrão com ":" e pontilhado opcional
        m = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\/\-]+?)\s*(?:\.{2,}|\s)*:\s*(.+)$",
            line
        )
        if not m:
            continue

        analito = m.group(1).strip()
        resto = m.group(2).strip()

        # ignora cabeçalhos
        if not e_nome_exame_valido(analito):
            continue

        # Tenta capturar valor + unidade + referência
        # Ex: "1000 /ml De 0 a 10.000/ml"
        m2 = re.match(
            r"^([\d\.,]+|\w[\w\s\+\-]+)\s*(/ml|/uL|/µL|/mm3|/mm³|mg/dL|g/dL|uL|µL|mm³|mm3|%|)\s*(.*)$",
            resto,
            re.IGNORECASE
        )
        if m2:
            val_raw = m2.group(1).strip()
            unidade = m2.group(2).strip()
            ref_raw = m2.group(3).strip()
        else:
            # fallback: valor é a linha toda
            val_raw, unidade, ref_raw = resto, "", ""

        valor = normalizar_valor(val_raw)

        # Densidade: labs often write "1010" instead of "1.010"
        if "ensidade" in analito and isinstance(valor, (int, float)) and valor > 100:
            valor = round(valor / 1000.0, 3)

        # referência pode estar vazia ou repetida (ex: "Negativo Negativo")
        # tenta extrair uma referência mais "provável"
        ref_inf, ref_sup, ref_txt = _parse_ref_text(ref_raw)

        # Se ref_raw vier como "Negativo" e valor também qualitativo, ok.
        referencia = ref_txt

        status = determinar_status(valor, ref_inf, ref_sup, referencia)

        resultados.append({
            "Analito": f"URINA - {analito}",
            "Valor": valor,
            "Unidade": unidade,
            "Referencia": referencia,
            "Status": status
        })

    return resultados

def extrair_hemograma(texto: str) -> List[Dict[str, Union[str, float]]]:
    """
    Lê hemograma em formato tabular, incluindo diferencial:
      "Eritrocitos........: 4.31 milhoes/mm3 3.80 - 4.80"
      "Hemoglobina........: 12.9 g/dL 12.0 - 16.0"
      "Segmentados........: 65 6890 42 a 70 % 1800 a 7000/mm3"
    """
    resultados: List[Dict[str, Union[str, float]]] = []
    texto_upper = texto.upper()
    if not _is_hemograma_context(texto_upper):
        return resultados

    # Limitar ao bloco do hemograma (entre o cabeçalho e a próxima seção principal)
    todas_linhas = texto.splitlines()
    inicio = None
    fim = len(todas_linhas)
    _HEMO_HEADER = re.compile(r'\b(HEMOGRAMA|ERITROGRAMA|LEUCOGRAMA)', re.IGNORECASE)
    _NOVA_SECAO_HEM = re.compile(
        r'^(URINA\s*TIPO|URINA\s*ROTINA|EAS\b|LIPIDOGRAMA|COAGULOGRAMA|'
        r'BIOQUÍMICA|BIOQUIMICA|HORMÔNIO|HORMONIO|SOROLOGIA|CULTURA|'
        r'PARASITOLÓGICO|PARASITOLOGICO)',
        re.IGNORECASE
    )
    for idx, ln in enumerate(todas_linhas):
        if inicio is None and _HEMO_HEADER.search(ln):
            inicio = idx
        elif inicio is not None and idx > inicio + 5 and _NOVA_SECAO_HEM.match(ln.strip()):
            fim = idx
            break
    if inicio is None:
        linhas = [re.sub(r"\s+", " ", l).strip() for l in todas_linhas if l.strip()]
    else:
        linhas = [re.sub(r"\s+", " ", l).strip() for l in todas_linhas[inicio:fim] if l.strip()]

    # 1) Linhas padrão "Analito: valor unidade ref"
    for line in linhas:
        m = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\-\/]+?)\s*(?:\.{2,}|\s)*:\s*([\d\.,]+)\s*([A-Za-z%µ/³0-9]+)?\s*(.*)$",
            line
        )
        if not m:
            continue

        analito = m.group(1).strip()
        if not e_nome_exame_valido(analito):
            continue

        val_raw = m.group(2).strip()
        unidade = (m.group(3) or "").strip()
        ref_raw = (m.group(4) or "").strip()

        # Evita capturar cabeçalhos repetidos
        if analito.upper() in ("HEMOGRAMA", "ERITROGRAMA", "LEUCOGRAMA", "PLAQUETOGRAMA"):
            continue

        valor = normalizar_valor(val_raw)

        ref_inf, ref_sup, ref_txt = _parse_ref_text(ref_raw)
        referencia = ref_txt

        status = determinar_status(valor, ref_inf, ref_sup, referencia)

        resultados.append({
            "Analito": f"HEMOGRAMA - {analito}",
            "Valor": valor,
            "Unidade": unidade,
            "Referencia": referencia,
            "Status": status
        })

    # 2) Diferencial: "Nome: % absoluto ref% refAbs"
    # Ex: "Segmentados: 65 6890 42 a 70 % 1800 a 7000/mm3"
    for line in linhas:
        m = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\-\/]+?)\s*(?:\.{2,}|\s)*:\s*"
            r"(\d{1,3}(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s+"
            r"(\d+(?:[.,]\d+)?)\s*(?:a|-|até|ate)\s*(\d+(?:[.,]\d+)?)\s*%?\s+"
            r"(\d+(?:[.,]\d+)?)\s*(?:a|-|até|ate)\s*(\d+(?:[.,]\d+)?)\s*/?\s*(mm3|mm³|µL|uL|/mm3|/mm³)?$",
            line,
            re.IGNORECASE
        )
        if not m:
            continue

        nome = m.group(1).strip()
        if not e_nome_exame_valido(nome):
            continue

        perc = normalizar_valor(m.group(2))
        abs_ = normalizar_valor(m.group(3))

        refp1 = _to_float(m.group(4))
        refp2 = _to_float(m.group(5))
        refa1 = _to_float(m.group(6))
        refa2 = _to_float(m.group(7))
        un_abs = (m.group(8) or "mm³").replace("/","").strip()

        # % (sempre unidade %)
        if isinstance(perc, (int, float)) and refp1 is not None and refp2 is not None:
            st_perc = determinar_status(perc, min(refp1, refp2), max(refp1, refp2), f"{min(refp1, refp2)} - {max(refp1, refp2)} %")
            resultados.append({
                "Analito": f"HEMOGRAMA - {nome} (%)",
                "Valor": perc,
                "Unidade": "%",
                "Referencia": f"{min(refp1, refp2)} - {max(refp1, refp2)}",
                "Status": st_perc
            })

        # absoluto (unidade /mm³)
        if isinstance(abs_, (int, float)) and refa1 is not None and refa2 is not None:
            st_abs = determinar_status(abs_, min(refa1, refa2), max(refa1, refa2), f"{min(refa1, refa2)} - {max(refa1, refa2)} /{un_abs}")
            resultados.append({
                "Analito": f"HEMOGRAMA - {nome} (abs)",
                "Valor": abs_,
                "Unidade": f"/{un_abs}",
                "Referencia": f"{min(refa1, refa2)} - {max(refa1, refa2)}",
                "Status": st_abs
            })

    # Dedup simples (hemograma às vezes entra nos dois loops)
    vistos = set()
    out = []
    for r in resultados:
        key = (r["Analito"], r["Valor"], r["Unidade"], r["Referencia"])
        if key in vistos:
            continue
        vistos.add(key)
        out.append(r)

    return out

# =========================
# EXTRAÇÃO GENÉRICA (SEU MÉTODO ATUAL)
# =========================
def _extrair_limites_textuais(bloco_texto: str):
    ref_inf = None
    ref_sup = None
    ref_txt_normal = ""

    linhas = [l.strip() for l in bloco_texto.splitlines() if l.strip()]
    for linha in linhas:
        low = linha.lower()
        is_normal_line = "normal" in low

        m = re.search(r"(inferior a|menor que|até|ate|igual ou inferior a|<=)\s*([\d\.,]+)", low)
        if m:
            val = _to_float(m.group(2))
            if val is not None:
                if is_normal_line:
                    ref_sup = val
                    ref_txt_normal = linha
                else:
                    if ref_sup is None:
                        ref_sup = val

        m = re.search(r"(superior a|maior que|igual ou superior a|>=)\s*([\d\.,]+)", low)
        if m:
            val = _to_float(m.group(2))
            if val is not None:
                if is_normal_line:
                    ref_inf = val
                    ref_txt_normal = linha
                else:
                    if ref_inf is None:
                        ref_inf = val

        m = re.search(r"([\d\.,]+)\s*(a|até|ate|-)\s*([\d\.,]+)", low)
        if m and ("refer" in low or "risco" in low or "normal" in low):
            v1 = _to_float(m.group(1))
            v2 = _to_float(m.group(3))
            if v1 is not None and v2 is not None:
                if ref_inf is None and ref_sup is None and is_normal_line:
                    ref_inf, ref_sup = min(v1, v2), max(v1, v2)
                    ref_txt_normal = linha if is_normal_line else ref_txt_normal

    return ref_inf, ref_sup, ref_txt_normal

def extrair_resultado_referencia(bloco_texto: str) -> Dict[str, Union[str, float]]:
    dados = {
        "valor": "",
        "unidade": "",
        "ref_inf": "",
        "ref_sup": "",
        "referencia_texto": ""
    }

    match_resultado = re.search(
        r"Resultado[:\s]*(?:\n)?\s*([\d,\.]+)\s+([a-zA-Zµ°/%²³]+(?:/[a-zA-Z]+)?)",
        bloco_texto,
        re.IGNORECASE
    )
    if match_resultado:
        dados["valor"] = normalizar_valor(match_resultado.group(1))
        dados["unidade"] = match_resultado.group(2).strip()
    else:
        match_resultado = re.search(
            r"^\s*([\d,\.]+)\s+(mg/dL|g/dL|g/L|g%|mmol/L|mUI/L|U/L|ng/mL|ug/dL|pg/mL|fL|u3|%|/mm³|mil/mm³|milhoes/mm³|x10³/µL|mm³)\s*$",
            bloco_texto,
            re.MULTILINE | re.IGNORECASE
        )
        if match_resultado:
            dados["valor"] = normalizar_valor(match_resultado.group(1))
            dados["unidade"] = match_resultado.group(2).strip()

    match_ref_range = re.search(
        r"(?:Refer[eê]ncia|VR|V\.?R\.?)[:\s]*([\d,\.]+)\s*(?:a|até|-)\s*([\d,\.]+)",
        bloco_texto,
        re.IGNORECASE
    )
    if match_ref_range:
        v1 = _to_float(match_ref_range.group(1))
        v2 = _to_float(match_ref_range.group(2))
        if v1 is not None and v2 is not None:
            dados["ref_inf"] = min(v1, v2)
            dados["ref_sup"] = max(v1, v2)

    # Inline reference on Resultado line: "Resultado : 4.0 mmol/L De 3.5 a 5.1 mmol/L"
    # or "Resultado : 38 U/L 55 a 170 U/L" — range follows the value+unit on same line
    if dados["ref_inf"] == "" and dados["ref_sup"] == "":
        m_res_line = re.search(r'Resultado[:\s]*[^\n]+', bloco_texto, re.IGNORECASE)
        if m_res_line:
            m_inline = re.search(
                r'([\d,\.]+)\s+(?:a|até)\s+([\d,\.]+)',
                m_res_line.group(0),
                re.IGNORECASE
            )
            if m_inline:
                v1 = _to_float(m_inline.group(1))
                v2 = _to_float(m_inline.group(2))
                if v1 is not None and v2 is not None and v1 < v2:
                    dados["ref_inf"] = v1
                    dados["ref_sup"] = v2

    if dados["ref_inf"] == "" and dados["ref_sup"] == "":
        ref_inf, ref_sup, ref_txt_normal = _extrair_limites_textuais(bloco_texto)
        if ref_inf is not None:
            dados["ref_inf"] = ref_inf
        if ref_sup is not None:
            dados["ref_sup"] = ref_sup
        if ref_txt_normal:
            dados["referencia_texto"] = ref_txt_normal

    if dados["valor"] == "" or dados["valor"] is None:
        match_qualitativo = re.search(
            r"Resultado[:\s]+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇÃÕ][A-Za-zà-ÿ\s]+?)(?:\n|Refer|Obs|Método|Material|$)",
            bloco_texto,
            re.IGNORECASE
        )
        if match_qualitativo:
            dados["valor"] = match_qualitativo.group(1).strip()

    return dados

# Analitos já extraídos pelos parsers dedicados (hemograma/urina/hba1c) — o fallback não deve capturá-los
_ANALITOS_DEDICADOS = re.compile(
    r'^(HEMOGRAMA|ERITROGRAMA|LEUCOGRAMA|PLAQUETOGRAMA|LIPIDOGRAMA|'
    r'URINA\s*TIPO|URINA\s*ROTINA|EAS\b|EXAME\s+DE\s+URINA|'
    # Componentes do hemograma
    r'HEMOGLOBINA\b|HEMATOCRITO|ERITROCITOS|ERITR[OÓ]CITOS|'
    r'LEUCOCITOS|LEUCÓCITOS|PLAQUETAS\b|VCM\b|HCM\b|CHCM\b|RDW\b|'
    r'BASOFILOS|BASÓFILOS|EOSINOFILOS|EOSINÓFILOS|SEGMENTADOS|'
    r'LINFOCITOS|LINFÓCITOS|MONOCITOS|MONÓCITOS|BASTONETES|METAMIELOCITOS|'
    r'NEUTROFILOS|NEUTRÓFILOS|BASTOES\b|'
    # HbA1c e GME — extraídos pelo parser dedicado
    r'HEMOGLOBINA\s+GLICADA|GLICOSE\s+M[EÉ]DIA\s+ESTIMADA|'
    r'Risco\s+aumentado|Consistente\s+com\s+Diabetes|'
    # Calculados derivados (TFGe) — não devem ser capturados como referência de outro analito
    r'Taxa\s+de\s+filtra|Filtração\s+glomerular|TFGe\b|TFG\b|Clearance\s+de|'
    r'Depuração\s+de|CKD.EPI|MDRD|'
    # Linhas de contexto / referência
    r'Normal\s*[:\-]|Desejável|Limítrofe|'
    r'Fase\s+|Pós\s+|De\s+\d|Acima\s+de|'
    r'Mulhere|Homens?\b|Adulto|Criança)',
    re.IGNORECASE
)

_REF_HBA1C = "Normal: <5,7% | Pré-DM: 5,7-6,4% | DM: ≥6,5%"
_REF_GME   = "Normal: <117 mg/dL | Pré-DM: 117-139 mg/dL | DM: ≥140 mg/dL"

def extrair_hba1c(texto: str) -> List[Dict[str, Union[str, float]]]:
    """Parser dedicado para HEMOGLOBINA GLICADA (HbA1c) e GLICOSE MÉDIA ESTIMADA (GME)."""
    resultados = []

    # HbA1c — "Resultado : 8.8 %" embeddido nas linhas de referência
    m_hba = re.search(r'HEMOGLOBINA\s+GLICADA', texto, re.IGNORECASE)
    if m_hba:
        bloco = texto[m_hba.start(): m_hba.start() + 600]
        mr = re.search(r'Resultado\s*:\s*([\d,\.]+)\s*%', bloco, re.IGNORECASE)
        if mr:
            val_str = mr.group(1).replace(',', '.')
            try:
                val = float(val_str)
                status = 'NORMAL' if val < 5.7 else '[ALTERADO] ACIMA'
                resultados.append({
                    "Analito":    "HEMOGLOBINA GLICADA (HbA1c)",
                    "Valor":      val_str.replace('.', ','),
                    "Unidade":    "%",
                    "Referencia": _REF_HBA1C,
                    "Status":     status,
                })
            except ValueError:
                pass

    # GME — "Resultado : 206 mg/dL"
    m_gme = re.search(r'GLICOSE\s+M[EÉ]DIA\s+ESTIMADA', texto, re.IGNORECASE)
    if m_gme:
        bloco = texto[m_gme.start(): m_gme.start() + 300]
        mr = re.search(r'Resultado\s*:\s*([\d,\.]+)\s*mg', bloco, re.IGNORECASE)
        if mr:
            val_str = mr.group(1).replace(',', '.')
            try:
                val = float(val_str)
                status = 'NORMAL' if val < 117 else '[ALTERADO] ACIMA'
                resultados.append({
                    "Analito":    "GLICOSE MÉDIA ESTIMADA (GME)",
                    "Valor":      val_str,
                    "Unidade":    "mg/dL",
                    "Referencia": _REF_GME,
                    "Status":     status,
                })
            except ValueError:
                pass

    return resultados

def _e_analito_fallback_valido(linha: str, texto_doc: str) -> bool:
    """Retorna True se a linha pode ser tratada como analito pelo fallback genérico."""
    if _ANALITOS_DEDICADOS.match(linha.strip()):
        return False
    return e_nome_exame_valido(linha)


def extrair_exames(texto: str) -> List[Dict[str, Union[str, float]]]:
    """
    Estratégia:
      1) Se documento tem URINA/EAS => extrai via extrair_urina
      2) Se documento tem HEMOGRAMA => extrai via extrair_hemograma
      3) Sempre roda fallback genérico (para outros exames)
    """
    exames: List[Dict[str, Union[str, float]]] = []

    # Parsers dedicados
    exames.extend(extrair_urina(texto))
    exames.extend(extrair_hemograma(texto))
    exames.extend(extrair_hba1c(texto))

    # Fallback genérico (seu método atual)
    linhas = texto.split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()

        if linha and (linha.isupper() or (linha[0].isupper() and len(linha) > 3)):
            if _e_analito_fallback_valido(linha, texto):
                nome_exame = linha
                fim_bloco = min(i + 20, len(linhas))
                # Stop block at the next analyte name to avoid cross-contamination
                bloco_linhas = [linhas[i]]
                for j in range(i + 1, fim_bloco):
                    l = linhas[j].strip()
                    # Stop at dedicated-section headers (TFGe, hemograma components, etc.)
                    if l and _ANALITOS_DEDICADOS.match(l):
                        break
                    # Stop at the next standalone analyte candidate
                    if (l and j > i + 1
                            and (l.isupper() or (l[0:1].isupper() and len(l.split()) <= 5))
                            and not re.search(r'[\d\.,]+\s*(a|até|ate|-)\s*[\d\.,]+', l, re.IGNORECASE)
                            and e_nome_exame_valido(l)):
                        break
                    bloco_linhas.append(linhas[j])
                bloco = "\n".join(bloco_linhas)
                dados = extrair_resultado_referencia(bloco)

                if dados["valor"] != "" and dados["valor"] is not None:
                    status = determinar_status(
                        dados["valor"],
                        dados["ref_inf"],
                        dados["ref_sup"],
                        dados["referencia_texto"]
                    )

                    if dados["ref_inf"] != "" and dados["ref_sup"] != "":
                        referencia = f"{dados['ref_inf']} - {dados['ref_sup']}"
                    elif dados["referencia_texto"]:
                        referencia = dados["referencia_texto"]
                    else:
                        referencia = ""

                    exames.append({
                        "Analito": nome_exame,
                        "Valor": dados["valor"],
                        "Unidade": dados["unidade"],
                        "Referencia": referencia,
                        "Status": status
                    })

        i += 1

    # Dedup final
    vistos = set()
    out = []
    for r in exames:
        key = (r.get("Analito"), r.get("Valor"), r.get("Unidade"), r.get("Referencia"))
        if key in vistos:
            continue
        vistos.add(key)
        out.append(r)

    return out

# =========================
# GMAIL: LABELS + THREAD REPLY
# =========================
def garantir_label_existe(imap, nome_label: str):
    try:
        folders = imap.list_folders()
        existentes = {f[2] for f in folders}
        if nome_label not in existentes:
            imap.create_folder(nome_label)
            print(f"Label criada: {nome_label}")
    except Exception as e:
        print(f"Aviso: não consegui validar/criar label '{nome_label}': {e}")

def obter_message_id(pyz_msg) -> str:
    mid = (
        pyz_msg.get_decoded_header("Message-ID")
        or pyz_msg.get_decoded_header("Message-Id")
        or pyz_msg.get_decoded_header("MESSAGE-ID")
    )
    if not mid:
        return ""

    mid = str(mid).strip()
    if not (mid.startswith("<") and mid.endswith(">")):
        mid = f"<{mid.strip('<>')}>"
    return mid

def enviar_resposta_thread(subject_original: str, message_id: str, status_txt: str):
    msg = EmailMessage()
    msg["From"] = EMAIL
    msg["To"] = EMAIL
    msg["Date"] = formatdate(localtime=True)

    subj = subject_original or "Laudos"
    if not subj.lower().startswith("re:"):
        subj = "Re: " + subj
    msg["Subject"] = subj

    msg["In-Reply-To"] = message_id
    msg["References"] = message_id

    msg.set_content(
        f"{status_txt}\n\n"
        "— Sinalização automática para triagem de enfermagem."
    )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, SENHA_APP)
        smtp.send_message(msg)

# =========================
# BANCO DE DADOS SQLite
# =========================

def criar_banco():
    """Cria o banco SQLite com as tabelas necessárias (se não existirem)."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pacientes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT NOT NULL,
                dt_nasc     TEXT,
                medico      TEXT,
                criado_em   TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(nome, dt_nasc)
            );

            CREATE TABLE IF NOT EXISTS processamentos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid       INTEGER,
                arquivo_pdf     TEXT,
                paciente_id     INTEGER REFERENCES pacientes(id),
                pedido          TEXT,
                status_email    TEXT,
                data_exame      TEXT,
                processado_em   TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS exames (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                processamento_id    INTEGER REFERENCES processamentos(id),
                paciente_id         INTEGER REFERENCES pacientes(id),
                analito             TEXT NOT NULL,
                valor               TEXT,
                unidade             TEXT,
                referencia          TEXT,
                status              TEXT,
                pendencia           TEXT DEFAULT 'NÃO',
                motivo_pendencia    TEXT,
                data_exame          TEXT,
                registrado_em       TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_exames_paciente   ON exames(paciente_id);
            CREATE INDEX IF NOT EXISTS idx_exames_status     ON exames(status);
            CREATE INDEX IF NOT EXISTS idx_exames_analito    ON exames(analito);
            CREATE INDEX IF NOT EXISTS idx_exames_data       ON exames(data_exame);
            CREATE INDEX IF NOT EXISTS idx_proc_email_uid    ON processamentos(email_uid);
        """)
    print(f"✓ Banco de dados pronto: {DB_PATH}")


@contextmanager
def get_db():
    """Context manager para conexão SQLite com commit/rollback automático."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_paciente(nome: str, dt_nasc: str = None, medico: str = None) -> int:
    """Insere paciente se não existir (chave: nome + dt_nasc). Retorna o id."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO pacientes (nome, dt_nasc, medico) VALUES (?, ?, ?)",
            (nome.strip(), dt_nasc, medico)
        )
        row = conn.execute(
            "SELECT id FROM pacientes WHERE nome = ? AND (dt_nasc = ? OR (dt_nasc IS NULL AND ? IS NULL))",
            (nome.strip(), dt_nasc, dt_nasc)
        ).fetchone()
        return row["id"]


def inserir_processamento(email_uid: int, arquivo_pdf: str,
                          paciente_id: Optional[int], pedido: str,
                          status_email: str, data_exame: str = None) -> Optional[int]:
    """Registra o processamento de um PDF. Retorna o id gerado, ou None se já existir.

    Deduplicação em dois níveis:
    1. Mesmo email_uid + arquivo_pdf (caminho normal — mesmo email reprocessado)
    2. Mesmo arquivo_pdf independente do uid (PDF processado por caminhos diferentes,
       ex.: via e-mail e depois via processar_pdfs_locais)
    """
    with get_db() as conn:
        # Nível 1: uid + arquivo (evita reprocessar o mesmo e-mail)
        existing = conn.execute(
            "SELECT id FROM processamentos WHERE email_uid=? AND arquivo_pdf=?",
            (email_uid, arquivo_pdf)
        ).fetchone()
        if existing:
            return None

        # Nível 2: apenas arquivo (mesmo PDF chegou por caminho diferente)
        existing_by_file = conn.execute(
            "SELECT id FROM processamentos WHERE arquivo_pdf=?",
            (arquivo_pdf,)
        ).fetchone()
        if existing_by_file:
            return None

        cur = conn.execute(
            """INSERT INTO processamentos
               (email_uid, arquivo_pdf, paciente_id, pedido, status_email, data_exame)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email_uid, arquivo_pdf, paciente_id, pedido, status_email, data_exame)
        )
        return cur.lastrowid


def inserir_exames_bulk(processamento_id: int, paciente_id: Optional[int],
                        exames: List[Dict], data_exame: str = None) -> int:
    """Insere exames de um processamento, evitando duplicatas por data+analito+valor.

    Um paciente pode ter múltiplos exames ao longo do tempo — todos devem ser
    preservados. A deduplicação opera DENTRO da mesma data de exame: se já existe
    um registro de (paciente_id, analito, data_exame, valor) idêntico, o exame é
    ignorado (mesmo PDF processado por caminhos distintos).

    Retorna o número de exames efetivamente inseridos.
    """
    from datetime import datetime as _dt

    # Converte DD/MM/YYYY → YYYY-MM-DD para ordenação temporal correta
    data_exame_iso = None
    if data_exame and len(data_exame) >= 10:
        try:
            data_exame_iso = _dt.strptime(data_exame[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            data_exame_iso = data_exame[:10]

    with get_db() as conn:
        # Carrega chaves já existentes para este paciente nesta data de exame,
        # para deduplicar sem fazer N queries individuais.
        existentes: set = set()
        if paciente_id and data_exame_iso:
            for row in conn.execute(
                "SELECT analito, valor FROM exames WHERE paciente_id=? AND data_exame=?",
                (paciente_id, data_exame_iso)
            ):
                existentes.add((str(row[0]).strip().upper(), str(row[1]).strip()))

        rows = []
        ignorados = 0
        for ex in exames:
            analito_raw = str(ex.get("Analito", "")).strip()
            valor_raw   = str(ex.get("Valor",   "")).strip()
            chave = (analito_raw.upper(), valor_raw)

            # Pula exame já registrado com mesmo analito+valor na mesma data
            if chave in existentes:
                ignorados += 1
                continue
            existentes.add(chave)  # evita duplicata dentro do próprio lote

            status = str(ex.get("Status", ""))
            pendencia = "NÃO"
            motivos = []
            if "ALTERADO" in status.upper():
                pendencia = "SIM"
                motivos.append("Exame alterado")
            if status.upper() in ("REVISAR", "N/A", ""):
                pendencia = "SIM"
                motivos.append("Revisar (status indefinido)")
            if not str(ex.get("Referencia", "")).strip():
                pendencia = "SIM"
                motivos.append("Sem referência")
            if not valor_raw:
                pendencia = "SIM"
                motivos.append("Sem valor")
            rows.append((
                processamento_id, paciente_id,
                analito_raw, valor_raw,
                ex.get("Unidade", ""), ex.get("Referencia", ""),
                status, pendencia,
                " | ".join(motivos) if motivos else "",
                data_exame_iso,
            ))

        if rows:
            conn.executemany(
                """INSERT INTO exames
                   (processamento_id, paciente_id, analito, valor, unidade,
                    referencia, status, pendencia, motivo_pendencia, data_exame)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
        return len(rows)


def salvar_resultados_no_banco(todos_resultados: List[Dict]) -> None:
    """Persiste todos os resultados processados no banco SQLite."""
    if not todos_resultados:
        print("⚠️  Nenhum resultado para salvar no banco.")
        return

    grupos: Dict[tuple, List[Dict]] = {}
    for row in todos_resultados:
        chave = (row.get("EmailUID"), row.get("Arquivo", ""))
        grupos.setdefault(chave, []).append(row)

    total_exames = 0
    for (uid, arquivo), exames in grupos.items():
        meta = exames[0]
        nome = meta.get("Paciente", "").strip()
        dt_nasc = meta.get("Dt Nasc")
        medico = meta.get("Medico")
        pedido = meta.get("Pedido")
        status_email = meta.get("status_email", "REVISAR")
        data_exame = meta.get("Data Exame")

        paciente_id = None
        if nome:
            paciente_id = upsert_paciente(nome, dt_nasc, medico)

        proc_id = inserir_processamento(uid, arquivo, paciente_id, pedido, status_email, data_exame)
        if proc_id is None:
            print(f"  ⏭  Ignorado (já processado): {arquivo}")
            continue   # PDF já estava no banco — não duplica exames
        n_inseridos = inserir_exames_bulk(proc_id, paciente_id, exames, data_exame)
        total_exames += n_inseridos

    print(f"✓ {total_exames} exames salvos no banco '{DB_PATH}'")


def gerar_relatorio_do_banco(filtro_data_ini=None, filtro_data_fim=None) -> None:
    """Gera o Excel lendo os dados diretamente do banco SQLite."""
    query = """
        SELECT
            p.nome          AS Paciente,
            p.dt_nasc       AS "Dt Nasc",
            p.medico        AS Medico,
            pr.pedido       AS Pedido,
            pr.arquivo_pdf  AS Arquivo,
            pr.email_uid    AS EmailUID,
            pr.status_email AS "Status Email",
            e.analito       AS Analito,
            e.valor         AS Valor,
            e.unidade       AS Unidade,
            e.referencia    AS Referencia,
            e.status        AS Status,
            e.pendencia     AS Pendencia,
            e.motivo_pendencia AS Motivo,
            e.registrado_em AS "Registrado Em"
        FROM exames e
        LEFT JOIN processamentos pr ON e.processamento_id = pr.id
        LEFT JOIN pacientes p       ON e.paciente_id = p.id
    """
    params = []
    if filtro_data_ini:
        query += " WHERE date(e.registrado_em) >= ?"
        params.append(str(filtro_data_ini))
    if filtro_data_fim:
        conector = "AND" if filtro_data_ini else "WHERE"
        query += f" {conector} date(e.registrado_em) <= ?"
        params.append(str(filtro_data_fim))
    query += " ORDER BY e.registrado_em DESC"

    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        print("⚠️  Nenhum dado encontrado no banco para o período.")
        return

    df_pendencias = df[df["Pendencia"] == "SIM"].copy()

    with pd.ExcelWriter(RELATORIO, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="exames")
        df_pendencias.to_excel(writer, index=False, sheet_name="pendencias")
        for sheet_name in ["exames", "pendencias"]:
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_idx in range(1, ws.max_column + 1):
                ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 18

    total = len(df)
    alterados = len(df[df["Status"].astype(str).str.contains("ALTERADO", na=False)])
    pendencias = len(df_pendencias)
    pacientes_unicos = df["Paciente"].nunique() if "Paciente" in df.columns else 0
    print("=" * 60)
    print(f"✅ Relatório: {RELATORIO}")
    print(f"👥 Pacientes: {pacientes_unicos}")
    print(f"📊 Exames: {total}")
    print(f"⚠️  Pendências: {pendencias}")
    if total > 0:
        print(f"🔴 Alterados: {alterados} ({alterados/total*100:.1f}%)")
    print("=" * 60)


def estatisticas_gerais() -> Dict:
    """Retorna um resumo estatístico do banco."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        return {
            "total_exames":    cur.execute("SELECT COUNT(*) FROM exames").fetchone()[0],
            "total_pacientes": cur.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0],
            "alterados":       cur.execute("SELECT COUNT(*) FROM exames WHERE status LIKE '%ALTERADO%'").fetchone()[0],
            "pendencias":      cur.execute("SELECT COUNT(*) FROM exames WHERE pendencia = 'SIM'").fetchone()[0],
            "processamentos":  cur.execute("SELECT COUNT(*) FROM processamentos").fetchone()[0],
        }


# limpar_analitos_banco disponível via utils_analitos
from utils_analitos import limpar_analitos_banco  # noqa: F401


# =========================
# RELATÓRIO EXCEL (legado – mantido para compatibilidade)
# =========================
def gerar_relatorio(resultados: List[Dict]) -> None:
    if not resultados:
        print("⚠️  Nenhum exame processado")
        return

    df = pd.DataFrame(resultados)

    colunas_ordem = [
        "Arquivo", "Paciente", "Pedido", "Dt Nasc", "Medico",
        "Analito", "Valor", "Unidade", "Referencia", "Status",
        "EmailUID"
    ]
    colunas_disponiveis = [col for col in colunas_ordem if col in df.columns]
    df = df[colunas_disponiveis]

    df["Pendencia"] = "NÃO"
    df["Motivo"] = ""

    cond_alterado = df["Status"].astype(str).str.contains("ALTERADO", na=False)
    df.loc[cond_alterado, "Pendencia"] = "SIM"
    df.loc[cond_alterado, "Motivo"] = "Exame alterado"

    cond_revisar = df["Status"].astype(str).str.upper().isin(["REVISAR", "N/A", ""])
    df.loc[cond_revisar, "Pendencia"] = "SIM"
    df.loc[cond_revisar & (df["Motivo"] == ""), "Motivo"] = "Revisar (status indefinido)"
    df.loc[cond_revisar & (df["Motivo"] != ""), "Motivo"] += " | Revisar (status indefinido)"

    cond_sem_ref = df["Referencia"].isna() | (df["Referencia"].astype(str).str.strip() == "")
    df.loc[cond_sem_ref, "Pendencia"] = "SIM"
    df.loc[cond_sem_ref & (df["Motivo"] == ""), "Motivo"] = "Sem referência"
    df.loc[cond_sem_ref & (df["Motivo"] != ""), "Motivo"] += " | Sem referência"

    cond_sem_valor = df["Valor"].isna() | (df["Valor"].astype(str).str.strip() == "")
    df.loc[cond_sem_valor, "Pendencia"] = "SIM"
    df.loc[cond_sem_valor & (df["Motivo"] == ""), "Motivo"] = "Sem valor"
    df.loc[cond_sem_valor & (df["Motivo"] != ""), "Motivo"] += " | Sem valor"

    df_pendencias = df[df["Pendencia"] == "SIM"].copy()

    with pd.ExcelWriter(RELATORIO, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="exames")
        df_pendencias.to_excel(writer, index=False, sheet_name="pendencias")

        for sheet_name in ["exames", "pendencias"]:
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_idx in range(1, ws.max_column + 1):
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = 18

    total_exames = len(df)
    alterados = len(df[df["Status"].astype(str).str.contains("ALTERADO", na=False)])
    pendencias = len(df_pendencias)
    pacientes_unicos = df["Paciente"].nunique() if "Paciente" in df.columns else 0

    print("=" * 60)
    print(f"✅ Relatório: {RELATORIO}")
    print(f"👥 Pacientes: {pacientes_unicos}")
    print(f"📊 Exames: {total_exames}")
    print(f"⚠️  Pendências: {pendencias}")
    if total_exames > 0:
        print(f"🔴 Alterados: {alterados} ({alterados/total_exames*100:.1f}%)")
    print("=" * 60)

# =========================
# PIPELINE: BAIXAR -> PROCESSAR -> SINALIZAR -> BANCO
# =========================

def processar_emails(
    data_inicial,
    data_final,
    somente_nao_lidos: bool,
    log=print
) -> dict:
    """
    Core do processamento de e-mails.

    Pode ser chamada pelo terminal (main) ou pela GUI (menu_principal.py).
    `log` é uma callable que recebe uma string — use print (terminal) ou
    uma função que escreve no Text widget tkinter (GUI).

    Retorna dicionário com estatísticas finais do banco.
    """
    criar_banco()

    imap = imapclient.IMAPClient("imap.gmail.com", ssl=True)
    imap.login(EMAIL, SENHA_APP)
    imap.select_folder("INBOX")

    for lbl in (LABEL_ALTERADO, LABEL_NORMAL, LABEL_REVISAR, LABEL_SINALIZADO):
        garantir_label_existe(imap, lbl)

    before_date = data_final + timedelta(days=1)
    criteria = ["FROM", REMETENTE_LAB, "SINCE", data_inicial, "BEFORE", before_date]
    if somente_nao_lidos:
        criteria = ["UNSEEN"] + criteria

    uids = imap.search(criteria)
    log(f"{len(uids)} e-mail(s) encontrado(s) "
        f"({data_inicial} até {data_final} / "
        f"{'apenas não lidos' if somente_nao_lidos else 'todos'}).")

    todos_resultados = []
    sinalizados = 0
    pdfs = 0

    for uid in uids:
        fetched = imap.fetch([uid], ["X-GM-LABELS", "BODY[]"])
        labels_atuais = fetched[uid].get(b"X-GM-LABELS", [])
        labels_atuais_str = [
            x.decode() if isinstance(x, (bytes, bytearray)) else str(x)
            for x in labels_atuais
        ]

        message = pyzmail.PyzMessage.factory(fetched[uid][b"BODY[]"])
        subject_original = message.get_subject() or "Laudos"
        message_id = obter_message_id(message)

        # 1) BAIXAR PDFs DO EMAIL
        pdf_paths = []
        for part in message.mailparts:
            if part.filename and part.filename.lower().endswith(".pdf"):
                nome = f"{uid}_{part.filename}"
                caminho = os.path.join(PASTA_EXAMES, nome)
                with open(caminho, "wb") as f:
                    f.write(part.get_payload())
                pdf_paths.append((nome, caminho))
                pdfs += 1

        if not pdf_paths:
            continue

        # 2) PROCESSAR PDFs
        extraiu_algum = False
        falha_texto = False
        resultados_uid = []

        for nome, caminho in pdf_paths:
            log(f"\n[UID {uid}] 📄 {nome}")
            texto = ler_pdf(caminho)

            if not texto or len(texto) < 50:
                log("  ⚠️ Texto insuficiente (revisar)")
                falha_texto = True
                continue

            metadados = extrair_metadados(texto)
            exames = extrair_exames(texto)

            if exames:
                extraiu_algum = True

            log(f"  🔬 {len(exames)} exames extraídos")

            for ex in exames:
                row = {
                    "Arquivo": nome,
                    "EmailUID": uid,
                    **metadados,
                    **ex
                }
                todos_resultados.append(row)
                resultados_uid.append(row)

        # 3) DECISÃO DO EMAIL
        statuses = [str(r.get("Status", "")).upper() for r in resultados_uid]
        tem_alterado = any("ALTERADO" in s for s in statuses)
        tem_revisar  = any(s in ("REVISAR", "N/A", "") for s in statuses)

        if tem_alterado:
            status_email = "ALTERADO"
        elif falha_texto or (not extraiu_algum) or tem_revisar:
            status_email = "REVISAR"
        else:
            status_email = "NORMAL"

        for r in resultados_uid:
            r["status_email"] = status_email

        # 4) SINALIZAR NO GMAIL
        try:
            imap.remove_gmail_labels(uid, [LABEL_ALTERADO, LABEL_NORMAL, LABEL_REVISAR])

            if status_email == "ALTERADO":
                imap.add_gmail_labels(uid, [LABEL_ALTERADO])
                imap.add_flags(uid, ["\\Flagged"])
                status_txt = "🔴 EXAME ALTERADO — VERIFICAR (enfermagem)"
            elif status_email == "NORMAL":
                imap.add_gmail_labels(uid, [LABEL_NORMAL])
                status_txt = "🟢 Exame NORMAL — ok"
            else:
                imap.add_gmail_labels(uid, [LABEL_REVISAR])
                status_txt = "🟡 REVISAR — extração automática insuficiente"

            if message_id and (LABEL_SINALIZADO not in labels_atuais_str):
                enviar_resposta_thread(subject_original, message_id, status_txt)
                imap.add_gmail_labels(uid, [LABEL_SINALIZADO])
                sinalizados += 1

            log(f"[UID {uid}] ✅ {status_txt}")

        except Exception as e:
            log(f"[UID {uid}] ❌ Erro ao sinalizar no Gmail: {e}")

    imap.logout()

    # 5) SALVAR NO BANCO SQLite
    log("\n💾 Salvando no banco de dados...")
    salvar_resultados_no_banco(todos_resultados)

    # 6) LIMPEZA AUTOMÁTICA DE ANALITOS INVÁLIDOS
    log("🧬 Limpando analitos inválidos...")
    try:
        res_limpeza = limpar_analitos_banco(dry_run=False)
        n_rem = res_limpeza.get("invalidos", 0)
        if n_rem > 0:
            log(f"  ✓ {n_rem} registros inválidos removidos "
                f"({res_limpeza['analitos_invalidos']} tipos de analito)")
        else:
            log("  ✓ Nenhum analito inválido encontrado")
    except Exception as e:
        log(f"  ⚠️ Erro na limpeza de analitos: {e}")

    # 7) REMOÇÃO AUTOMÁTICA DO EXCEL (banco é a fonte principal)
    if os.path.exists(RELATORIO):
        try:
            os.remove(RELATORIO)
            log(f"🗑️  Excel '{RELATORIO}' removido — dados já persistidos no banco SQLite")
        except Exception as e:
            log(f"  ⚠️ Não foi possível remover Excel: {e}")

    # 8) ENCERRAR GERENCIADOR DE REFERÊNCIAS
    if GERENCIADOR:
        try:
            encerrar()
        except Exception:
            pass

    # Estatísticas finais
    stats = estatisticas_gerais()
    log(f"\n{'='*50}")
    log(f"✅ Concluído!")
    log(f"   PDFs baixados nesta execução : {pdfs}")
    log(f"   Threads sinalizadas          : {sinalizados}")
    log(f"   Pacientes no banco           : {stats['total_pacientes']}")
    log(f"   Exames no banco              : {stats['total_exames']}")
    log(f"   Alterados (histórico)        : {stats['alterados']}")
    log(f"   Pendências (histórico)       : {stats['pendencias']}")
    log(f"{'='*50}")
    return stats


def processar_pdfs_locais(pasta: str = PASTA_EXAMES, log=print) -> dict:
    """
    Processa PDFs já baixados que ainda NÃO estão no banco de dados.
    Não requer conexão com o Gmail.  Use para recuperar dados de PDFs
    antigos antes de apagá-los.

    Retorna: {"processados": N, "ignorados": N, "erros": N}
    """
    criar_banco()

    # Busca PDFs já registrados no banco
    with get_db() as conn:
        db_pdfs = {r[0] for r in conn.execute(
            "SELECT arquivo_pdf FROM processamentos"
        ).fetchall()}

    todos = sorted(
        f for f in os.listdir(pasta)
        if f.lower().endswith(".pdf") and f not in db_pdfs
    )
    log(f"PDFs não registrados: {len(todos)}")

    processados = ignorados = erros = 0

    for nome_arquivo in todos:
        caminho = os.path.join(pasta, nome_arquivo)

        # Deriva email_uid do nome do arquivo (formato UID_PEDIDO.pdf)
        m = re.match(r'^(\d+)_', nome_arquivo)
        uid_fake = int(m.group(1)) if m else abs(hash(nome_arquivo)) % 1_000_000

        try:
            texto = ler_pdf(caminho)
        except Exception as e:
            log(f"  ✗ {nome_arquivo}: erro ao ler PDF — {e}")
            erros += 1
            continue

        if not texto or len(texto.strip()) < 50:
            log(f"  ⚠ {nome_arquivo}: texto insuficiente, ignorado")
            ignorados += 1
            continue

        metadados = extrair_metadados(texto)
        exames = extrair_exames(texto)

        nome_pac = (metadados.get("Paciente") or "").strip()
        dt_nasc  = metadados.get("Dt Nasc")
        medico   = metadados.get("Medico")
        pedido   = metadados.get("Pedido")
        data_exame = metadados.get("Data Exame")

        # Determina status geral do conjunto
        statuses = [str(ex.get("Status", "")).upper() for ex in exames]
        if any("ALTERADO" in s for s in statuses):
            status_email = "ALTERADO"
        elif exames:
            status_email = "NORMAL" if all(s == "NORMAL" for s in statuses) else "REVISAR"
        else:
            status_email = "REVISAR"

        paciente_id = upsert_paciente(nome_pac, dt_nasc, medico) if nome_pac else None

        proc_id = inserir_processamento(
            uid_fake, nome_arquivo, paciente_id, pedido, status_email, data_exame
        )
        if proc_id is None:
            ignorados += 1
            continue

        if exames:
            n_inseridos = inserir_exames_bulk(proc_id, paciente_id, exames, data_exame)
            ignorados_exam = len(exames) - n_inseridos
            sufixo = f" ({ignorados_exam} já existiam)" if ignorados_exam else ""
        else:
            n_inseridos = 0
            sufixo = ""

        log(f"  ✓ {nome_arquivo}: {n_inseridos} exames ({status_email}){sufixo}")
        processados += 1

    log(f"\nConcluído — processados: {processados} | ignorados: {ignorados} | erros: {erros}")
    return {"processados": processados, "ignorados": ignorados, "erros": erros}


def main():
    """Ponto de entrada para uso via terminal (com input interativo)."""
    data_ini_str = input(
        "Baixar exames a partir de qual data? (YYYY-MM-DD) [ENTER = hoje]: "
    ).strip()
    if data_ini_str:
        try:
            data_inicial = datetime.strptime(data_ini_str, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("Data inicial inválida. Use YYYY-MM-DD")
    else:
        data_inicial = date.today()

    data_fim_str = input(
        "Baixar exames até qual data? (YYYY-MM-DD) [ENTER = hoje]: "
    ).strip()
    if data_fim_str:
        try:
            data_final = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("Data final inválida. Use YYYY-MM-DD")
    else:
        data_final = date.today()

    if data_final < data_inicial:
        raise SystemExit("Data final não pode ser menor que a data inicial.")

    nao_lidos_str = input("Baixar apenas NÃO LIDOS? (s/n) [s]: ").strip().lower()
    somente_nao_lidos = (nao_lidos_str in ("", "s", "sim", "y", "yes"))

    processar_emails(data_inicial, data_final, somente_nao_lidos)


if __name__ == "__main__":
    main()
