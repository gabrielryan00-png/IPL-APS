import os
import re
import smtplib
from datetime import datetime, date
from email.message import EmailMessage
from email.utils import formatdate
from typing import Dict, List, Optional, Tuple, Union

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import imapclient
import pyzmail
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG GMAIL + PASTAS
# =========================
EMAIL         = os.getenv("GMAIL_EMAIL",    "")
SENHA_APP     = os.getenv("GMAIL_SENHA",    "")
REMETENTE_LAB = os.getenv("REMETENTE_LAB",  "")
_DATA_DIR     = os.getenv("DATA_DIR",       ".")

PASTA_EXAMES = os.path.join(_DATA_DIR, "exames")
RELATORIO    = os.path.join(_DATA_DIR, "relatorio_exames.xlsx")

LABEL_ALTERADO   = "Exames/🔴 ALTERADO - VERIFICAR"
LABEL_NORMAL     = "Exames/🟢 NORMAL"
LABEL_REVISAR    = "Exames/🟡 REVISAR (falha extração)"
LABEL_SINALIZADO = "Exames/✅ Sinalizado"

os.makedirs(PASTA_EXAMES, exist_ok=True)

# =========================
# INPUT: DATA INICIAL + FINAL + FILTRO
# =========================
def _parse_date(s: str, label: str) -> Optional[date]:
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"Data {label} invalida. Use YYYY-MM-DD")

data_ini_str = input("Baixar exames a partir de qual data? (YYYY-MM-DD) [ENTER = hoje]: ")
data_fim_str = input("Ate qual data?                       (YYYY-MM-DD) [ENTER = hoje]: ")

data_inicial: date = _parse_date(data_ini_str, "inicial") or date.today()
data_final:   date = _parse_date(data_fim_str, "final")   or date.today()

if data_final < data_inicial:
    raise SystemExit("Data final nao pode ser anterior a data inicial.")

somente_nao_lidos = input("Baixar apenas NAO LIDOS? (s/n) [s]: ").strip().lower()
somente_nao_lidos = somente_nao_lidos in ("", "s", "sim", "y", "yes")

# =========================
# PDF: EXTRACAO + OCR
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
        print(f"Erro ao extrair texto de {pdf_path}: {e}")
    return texto.strip()

def extrai_texto_ocr(pdf_path: str) -> str:
    texto = ""
    try:
        imagens = convert_from_path(pdf_path)
        for img in imagens:
            texto += pytesseract.image_to_string(img, lang="por") + "\n"
    except Exception as e:
        print(f"Erro no OCR de {pdf_path}: {e}")
    return texto.strip()

def ler_pdf(pdf_path: str) -> str:
    texto = extrai_texto_pdf(pdf_path)
    if len(texto) < 100:
        print("  -> OCR...")
        texto_ocr = extrai_texto_ocr(pdf_path)
        if len(texto_ocr) > len(texto):
            texto = texto_ocr
    return texto

# =========================
# METADADOS / PACIENTE
# =========================
def extrair_nome_paciente_universal(texto: str) -> str:
    match = re.search(
        r'Nome\s*:\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)'
        r'(?:\s+(?:Invalid|S\s*e\s*x\s*o|Sexo|CPF|RG)|$)',
        texto, re.IGNORECASE
    )
    if match:
        nome = match.group(1).strip()
        nome = re.sub(r'\s+(Invalid|barcode|data|CPF).*', '', nome, flags=re.IGNORECASE)
        if len(nome) > 3 and len(nome.split()) >= 2:
            return nome

    match = re.search(
        r'N\.?\s*Pedido\s+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)\s+N\.\s*Registro',
        texto, re.IGNORECASE
    )
    if match:
        nome = re.sub(r'\d+', '', match.group(1)).strip()
        if len(nome) > 3:
            return nome

    return ""

def extrair_metadados(texto: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}

    nome = extrair_nome_paciente_universal(texto)
    if nome:
        meta["Paciente"] = nome

    m = re.search(r"(?:N\.?\s*Pedido|Pedido)[:\s]+(\d+)", texto, re.IGNORECASE)
    if m:
        meta["Pedido"] = m.group(1)

    m = re.search(
        r"(?:Dt\.?\s*Nasc|Data\s*Nascimento|Nascimento)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})",
        texto, re.IGNORECASE
    )
    if m:
        meta["Dt Nasc"] = m.group(1)

    m = re.search(
        r"Solicitante[:\s]+([A-ZÀ-Ü][A-Za-zà-ÿ\s\.]+?)(?:\s+Data|\n)",
        texto, re.IGNORECASE
    )
    if m:
        meta["Medico"] = m.group(1).strip()

    return meta

# =========================
# DETECCAO DE SECAO DO LAUDO
# =========================
def detectar_secao(texto: str) -> str:
    """Retorna 'urina', 'cultura', 'antibiograma' ou 'generico'."""
    upper = texto.upper()
    if "ANTIBIOGRAMA" in upper:
        return "antibiograma"
    if "CULTURA DE URINA" in upper:
        return "cultura"
    if "URINA TIPO I" in upper or "ANALISE MICROSCOPICA" in upper or "ANÁLISE MICROSCÓPICA" in upper:
        return "urina"
    return "generico"

# =========================
# NORMALIZACAO DE VALORES
# =========================
QUALITATIVOS_NORMAIS = {
    "NEGATIVO", "NAO REAGENTE", "NÃO REAGENTE", "AUSENTE", "AUSENTES",
    "NAO DETECTADO", "NÃO DETECTADO", "NORMAL",
}
QUALITATIVOS_ALTERADOS = {
    "POSITIVO", "REAGENTE", "PRESENTE", "DETECTADO",
}

def normalizar_valor(valor_str: str) -> Union[float, str]:
    if not valor_str or not isinstance(valor_str, str):
        return valor_str

    s = valor_str.strip()
    upper = s.upper()

    for q in (QUALITATIVOS_NORMAIS | QUALITATIVOS_ALTERADOS):
        if q in upper:
            return s

    # remove sinal > < antes de converter
    s_num = re.sub(r"^[<>]=?\s*", "", s)
    # remove separador de milhar (ponto antes de exatamente 3 digitos)
    s_num = re.sub(r"\.(?=\d{3}(?:\D|$))", "", s_num)
    s_num = s_num.replace(",", ".").strip()

    try:
        valor_limpo = re.sub(r"[^\d\.\-]", "", s_num)
        if valor_limpo and valor_limpo not in (".", "-", ".-"):
            return float(valor_limpo)
    except ValueError:
        pass

    return s

def _to_float(x: str) -> Optional[float]:
    try:
        s = x.strip()
        s = re.sub(r"\.(?=\d{3}(?:\D|$))", "", s)
        return float(s.replace(",", "."))
    except Exception:
        return None

# =========================
# PARSER DEDICADO: URINA TIPO I
# =========================
# Regex para linha no formato pontilhado deste laboratorio:
#   "Proteinas.........: Ausentes    Normal ate 0.05 g/l"
#   "Eritrocitos..: 1000 /ml         De 0 a 10.000/ml"
#   "PH................: 6.0          De 5 a 7"
_RE_LINHA_PONTILHADA = re.compile(
    r"^([A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü\sçÇ/\.]+?)"   # nome
    r"\.{2,}[:\s]+"                                    # pontos e separador
    r"([^\t]+?)"                                       # valor (e possivel unidade)
    r"(?:\s{2,}|\t)"                                   # espaco largo separando coluna ref
    r"(.+)?$",                                         # referencia (opcional)
    re.IGNORECASE
)

def _parse_referencia_urina(ref_str: str) -> Tuple[Optional[float], Optional[float], str]:
    """
    Extrai (ref_inf, ref_sup, texto_original) dos formatos presentes nos laudos
    de urina deste laboratorio.

    Exemplos suportados:
      "De 5 a 7"             -> (5.0, 7.0)
      "De 1005 a 1020"       -> (1005.0, 1020.0)
      "De 0 a 10.000/ml"     -> (0.0, 10000.0)
      "Normal ate 0.05 g/l"  -> (None, 0.05)
      "Normal a 1.0 mg/dl"   -> (None, 1.0)
      "Ausente" / "Negativo" -> (None, None)  qualitativo
    """
    if not ref_str:
        return None, None, ""

    ref_str = ref_str.strip()

    # "De X a Y" — intervalo
    m = re.search(r"[Dd]e\s+([\d\.,]+)\s+a\s+([\d\.,]+)", ref_str)
    if m:
        v1 = _to_float(m.group(1))
        v2 = _to_float(m.group(2))
        if v1 is not None and v2 is not None:
            return min(v1, v2), max(v1, v2), ref_str

    # "Normal ate X" / "ate X"
    m = re.search(r"(?:[Nn]ormal\s+)?[Aa]t[eé]\s+([\d\.,]+)", ref_str)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return None, v, ref_str

    # "Normal a X.Y"
    m = re.search(r"[Nn]ormal\s+a\s+([\d\.,]+)", ref_str)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return None, v, ref_str

    # intervalo solto "X a Y"
    m = re.search(r"([\d\.,]+)\s+a\s+([\d\.,]+)", ref_str)
    if m:
        v1 = _to_float(m.group(1))
        v2 = _to_float(m.group(2))
        if v1 is not None and v2 is not None:
            return min(v1, v2), max(v1, v2), ref_str

    return None, None, ref_str

def _separar_valor_unidade(raw: str) -> Tuple[str, str]:
    """
    Divide 'valor [unidade]' num par (valor_str, unidade).
    Exemplos: '1000 /ml' -> ('1000', '/ml')
              'Ausentes'  -> ('Ausentes', '')
              '6.0'       -> ('6.0', '')
    """
    raw = raw.strip()
    m = re.match(
        r"^([\d\.,]+|[A-ZÀ-Üa-zà-ü][A-Za-zà-ÿ\s]+?)"
        r"\s*([a-zA-Zµ°/%²³]+(?:/[a-zA-Z³]+)?)?$",
        raw
    )
    if m:
        return m.group(1).strip(), (m.group(2) or "").strip()
    return raw, ""

def extrair_exames_urina(texto: str) -> List[Dict]:
    """
    Parser especializado para Urina Tipo I neste laboratorio.
    Le linha a linha no formato pontilhado.
    """
    exames = []

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue

        m = _RE_LINHA_PONTILHADA.match(linha)
        if not m:
            continue

        nome_raw  = m.group(1).strip().rstrip(".")
        valor_raw = m.group(2).strip() if m.group(2) else ""
        ref_raw   = m.group(3).strip() if m.group(3) else ""

        valor_str, unidade = _separar_valor_unidade(valor_raw)
        valor = normalizar_valor(valor_str)

        ref_inf, ref_sup, ref_txt = _parse_referencia_urina(ref_raw)

        if ref_inf is not None and ref_sup is not None:
            referencia = f"{ref_inf} - {ref_sup}"
        elif ref_sup is not None:
            referencia = f"ate {ref_sup}"
        elif ref_txt:
            referencia = ref_txt
        else:
            referencia = ""

        status = determinar_status(valor, ref_inf, ref_sup, referencia)

        if valor in ("", None):
            continue

        exames.append({
            "Analito":    nome_raw,
            "Valor":      valor,
            "Unidade":    unidade,
            "Referencia": referencia,
            "Status":     status,
        })

    return exames

# =========================
# PARSER: CULTURA DE URINA
# =========================
def extrair_exames_cultura(texto: str) -> List[Dict]:
    exames = []

    m = re.search(r"Microorganismo\s*\d*\s*:\s*(.+)", texto, re.IGNORECASE)
    if not m:
        return exames

    organismo = m.group(1).strip()

    mc = re.search(r"Crescimento bacteriano\s+(.+?)(?:\n|$)", texto, re.IGNORECASE)
    crescimento = mc.group(1).strip() if mc else "Positivo"

    ufc_val = None
    mu = re.search(r"([\d\.]+)\s*UFC", crescimento, re.IGNORECASE)
    if mu:
        ufc_val = _to_float(mu.group(1))

    status = "[ALTERADO]" if (ufc_val is not None and ufc_val >= 100_000) else "REVISAR"

    exames.append({
        "Analito":    f"Cultura de Urina — {organismo}",
        "Valor":      crescimento,
        "Unidade":    "",
        "Referencia": "< 100.000 UFC/mL",
        "Status":     status,
    })
    return exames

# =========================
# PARSER: ANTIBIOGRAMA
# =========================
def extrair_exames_antibiograma(texto: str) -> List[Dict]:
    """
    Extrai cada antibiotico com seu resultado S/R/I.
    Resistentes e Intermediarios sao sinalizados como [ALTERADO].
    """
    exames = []

    for m in re.finditer(
        r"^([A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü/\.\s]+?)\s{2,}([SRI])\s*$",
        texto, re.MULTILINE
    ):
        nome  = m.group(1).strip()
        resul = m.group(2).strip().upper()

        if resul == "S":
            status = "NORMAL"
        elif resul == "R":
            status = "[ALTERADO] RESISTENTE"
        elif resul == "I":
            status = "[ALTERADO] INTERMEDIARIO"
        else:
            status = "REVISAR"

        exames.append({
            "Analito":    f"ATB: {nome}",
            "Valor":      resul,
            "Unidade":    "",
            "Referencia": "S=Sensivel / R=Resistente / I=Intermediario",
            "Status":     status,
        })

    return exames

# =========================
# REFERENCIAS TEXTUAIS (parser generico)
# =========================
def _extrair_limites_textuais(bloco: str) -> Tuple[Optional[float], Optional[float], str]:
    ref_inf = ref_sup = None
    ref_txt = ""

    for linha in bloco.splitlines():
        low = linha.strip().lower()
        is_normal = "normal" in low

        m = re.search(r"(inferior a|menor que|até|ate|igual ou inferior a|<=)\s*([\d\.,]+)", low)
        if m:
            v = _to_float(m.group(2))
            if v is not None and ref_sup is None:
                ref_sup = v
                if is_normal:
                    ref_txt = linha.strip()

        m = re.search(r"(superior a|maior que|igual ou superior a|>=)\s*([\d\.,]+)", low)
        if m:
            v = _to_float(m.group(2))
            if v is not None and ref_inf is None:
                ref_inf = v
                if is_normal:
                    ref_txt = linha.strip()

        m = re.search(r"([\d\.,]+)\s*(?:a|até|ate|-)\s*([\d\.,]+)", low)
        if m and any(kw in low for kw in ("refer", "risco", "normal", "de ")):
            v1 = _to_float(m.group(1))
            v2 = _to_float(m.group(2))
            if v1 is not None and v2 is not None and ref_inf is None and ref_sup is None:
                ref_inf, ref_sup = min(v1, v2), max(v1, v2)
                if is_normal:
                    ref_txt = linha.strip()

    return ref_inf, ref_sup, ref_txt

def extrair_resultado_referencia(bloco: str) -> Dict[str, Union[str, float]]:
    dados: Dict[str, Union[str, float]] = {
        "valor": "", "unidade": "", "ref_inf": "", "ref_sup": "", "referencia_texto": ""
    }

    m = re.search(
        r"Resultado[:\s]*(?:\n)?\s*([\d,\.]+)\s+([a-zA-Zµ°/%²³]+(?:/[a-zA-Z]+)?)",
        bloco, re.IGNORECASE
    )
    if m:
        dados["valor"]   = normalizar_valor(m.group(1))
        dados["unidade"] = m.group(2).strip()
    else:
        m = re.search(
            r"^\s*([\d,\.]+)\s+"
            r"(mg/dL|g/dL|g/L|g%|mmol/L|mUI/L|U/L|ng/mL|ug/dL|pg/mL|fL|u3|%"
            r"|/mm³|mil/mm³|milhoes/mm³|x10³/µL|mm³)\s*$",
            bloco, re.MULTILINE | re.IGNORECASE
        )
        if m:
            dados["valor"]   = normalizar_valor(m.group(1))
            dados["unidade"] = m.group(2).strip()

    m = re.search(
        r"(?:De|Refer[eê]ncia|VR|V\.?R\.?)[:\s]*([\d,\.]+)\s*(?:a|até|-)\s*([\d,\.]+)",
        bloco, re.IGNORECASE
    )
    if m:
        v1 = _to_float(m.group(1))
        v2 = _to_float(m.group(2))
        if v1 is not None and v2 is not None:
            dados["ref_inf"] = min(v1, v2)
            dados["ref_sup"] = max(v1, v2)

    if dados["ref_inf"] == "" and dados["ref_sup"] == "":
        ri, rs, rt = _extrair_limites_textuais(bloco)
        if ri is not None:
            dados["ref_inf"] = ri
        if rs is not None:
            dados["ref_sup"] = rs
        if rt:
            dados["referencia_texto"] = rt

    if dados["valor"] in ("", None):
        m = re.search(
            r"Resultado[:\s]+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇÃÕ][A-Za-zà-ÿ\s]+?)(?:\n|Refer|Obs|Método|Material|$)",
            bloco, re.IGNORECASE
        )
        if m:
            dados["valor"] = m.group(1).strip()

    return dados

# =========================
# DETERMINACAO DE STATUS
# =========================
def determinar_status(
    valor,
    ref_inf: Optional[float],
    ref_sup: Optional[float],
    ref_texto: str = ""
) -> str:

    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "REVISAR"

    if isinstance(valor, (int, float)):
        if isinstance(ref_inf, float) and isinstance(ref_sup, float):
            if valor < ref_inf:
                return "[ALTERADO] ABAIXO"
            if valor > ref_sup:
                return "[ALTERADO] ACIMA"
            return "NORMAL"
        if isinstance(ref_sup, float) and not isinstance(ref_inf, float):
            return "NORMAL" if valor <= ref_sup else "[ALTERADO] ACIMA"
        if isinstance(ref_inf, float) and not isinstance(ref_sup, float):
            return "NORMAL" if valor >= ref_inf else "[ALTERADO] ABAIXO"
        return "REVISAR"

    if isinstance(valor, str):
        v = valor.strip().upper()
        if v in {q.upper() for q in QUALITATIVOS_NORMAIS}:
            return "NORMAL"
        if v in {q.upper() for q in QUALITATIVOS_ALTERADOS}:
            return "[ALTERADO]"
        if v in ("RARAS", "RAROS"):
            return "[ALTERADO]"
        return "REVISAR"

    return "REVISAR"

# =========================
# FILTROS PARSER GENERICO (HEMOGRAMA ETC.)
# =========================
_OBSERVACOES_MORFOLOGICAS = {
    "MICROCITOSE", "MACROCITOSE", "ANISOCITOSE", "POIQUILOCITOSE",
    "HIPOCROMIA", "POLICROMASIA", "DISCRETA", "MODERADA", "ACENTUADA",
    "LEVE", "INTENSA", "OCASIONAL", "RAROS", "NUMEROSOS",
    "VALORES DE", "SERIE BRANCA", "SÉRIE BRANCA", "SERIE VERMELHA", "SÉRIE VERMELHA",
    "ERITROGRAMA", "LEUCOGRAMA", "PLAQUETOGRAMA",
}

_TERMOS_INVALIDOS = {
    "VALORES", "RESULTADO", "AUTENTICIDADE", "EVOLUCAO", "REFERENCIA",
    "UNIDADE", "METODO", "MATERIAL", "LAUDO", "PAGINA", "LABORATORIO",
    "PREFEITURA", "MUNICIPAL", "DIETA", "ASSOCIACAO",
    "REQUER", "CORRELACAO", "DADOS CLINICOS", "EPIDEMIOLOGICOS",
    "LIBERADO", "RESPONSAVEL", "EXAMES COLETADOS", "ANALISE",
    "PEDIDO", "CPF", "SOLICITANTE", "DESTINO", "ORIGEM", "EMISSAO",
    "CNES", "GRAVIDAS", "DATA", "NOTAS", "FL.:", "TRIMESTRE",
    "MICROORGANISMO", "CRESCIMENTO BACTERIANO", "LEGENDA", "URINA",
    "SEMI AUTOMATIZADO",
}

def e_analito_observacao(linha: str) -> bool:
    up = linha.upper().strip()
    return any(obs in up for obs in _OBSERVACOES_MORFOLOGICAS)

def e_nome_exame_valido(linha: str) -> bool:
    if e_analito_observacao(linha):
        return False
    up = linha.upper().strip()
    if any(t in up for t in _TERMOS_INVALIDOS):
        return False
    if re.match(r"^[\.\:\-\=\*\_\+]+$", linha):
        return False
    if len(linha.strip()) < 3 or len(linha) > 70:
        return False
    if linha.count(" ") > 10:
        return False
    if re.match(r"^\d", linha):
        return False
    return True

def extrair_exames_generico(texto: str) -> List[Dict]:
    """Parser generico para hemograma e outros exames em formato de bloco."""
    exames = []
    linhas = texto.split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha and (linha.isupper() or (linha[0].isupper() and len(linha) > 3)):
            if e_nome_exame_valido(linha):
                bloco = "\n".join(linhas[i: min(i + 45, len(linhas))])
                dados = extrair_resultado_referencia(bloco)

                if dados["valor"] not in ("", None):
                    ri = dados["ref_inf"] if isinstance(dados["ref_inf"], float) else None
                    rs = dados["ref_sup"] if isinstance(dados["ref_sup"], float) else None

                    status = determinar_status(dados["valor"], ri, rs, dados["referencia_texto"])

                    if ri is not None and rs is not None:
                        referencia = f"{ri} - {rs}"
                    elif dados["referencia_texto"]:
                        referencia = dados["referencia_texto"]
                    else:
                        referencia = ""

                    exames.append({
                        "Analito":    linha,
                        "Valor":      dados["valor"],
                        "Unidade":    dados["unidade"],
                        "Referencia": referencia,
                        "Status":     status,
                    })
        i += 1
    return exames

# =========================
# DISPATCHER: ESCOLHE PARSER POR SECAO
# =========================
def extrair_exames(texto: str) -> List[Dict]:
    secao = detectar_secao(texto)
    if secao == "urina":
        return extrair_exames_urina(texto)
    if secao == "cultura":
        return extrair_exames_cultura(texto)
    if secao == "antibiograma":
        return extrair_exames_antibiograma(texto)
    return extrair_exames_generico(texto)

# =========================
# GMAIL: LABELS + THREAD REPLY
# =========================
def garantir_label_existe(imap, nome_label: str) -> None:
    try:
        existentes = {f[2] for f in imap.list_folders()}
        if nome_label not in existentes:
            imap.create_folder(nome_label)
            print(f"Label criada: {nome_label}")
    except Exception as e:
        print(f"Aviso: nao consegui validar/criar label '{nome_label}': {e}")

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

def enviar_resposta_thread(subject_original: str, message_id: str, status_txt: str) -> None:
    msg = EmailMessage()
    msg["From"]        = EMAIL
    msg["To"]          = EMAIL
    msg["Date"]        = formatdate(localtime=True)
    subj               = subject_original or "Laudos"
    msg["Subject"]     = subj if subj.lower().startswith("re:") else f"Re: {subj}"
    msg["In-Reply-To"] = message_id
    msg["References"]  = message_id
    msg.set_content(
        f"{status_txt}\n\n— Sinalizacao automatica para triagem de enfermagem."
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, SENHA_APP)
        smtp.send_message(msg)

# =========================
# RELATORIO EXCEL
# =========================
def gerar_relatorio(resultados: List[Dict]) -> None:
    if not resultados:
        print("Nenhum exame processado")
        return

    df = pd.DataFrame(resultados)

    colunas_ordem = [
        "Arquivo", "Paciente", "Pedido", "Dt Nasc", "Medico",
        "Analito", "Valor", "Unidade", "Referencia", "Status", "EmailUID"
    ]
    df = df[[c for c in colunas_ordem if c in df.columns]]

    df["Pendencia"] = "NAO"
    df["Motivo"]    = ""

    def _flag(mask, motivo):
        df.loc[mask, "Pendencia"] = "SIM"
        df.loc[mask & (df["Motivo"] == ""), "Motivo"] = motivo
        df.loc[mask & (df["Motivo"] != ""), "Motivo"] += f" | {motivo}"

    _flag(df["Status"].str.contains("ALTERADO", na=False),                  "Exame alterado")
    _flag(df["Status"].str.upper().isin(["REVISAR", "N/A", ""]),             "Revisar (status indefinido)")
    _flag(df["Referencia"].isna() | (df["Referencia"].str.strip() == ""),   "Sem referencia")
    _flag(df["Valor"].isna() | (df["Valor"].astype(str).str.strip() == ""), "Sem valor")

    df_pend = df[df["Pendencia"] == "SIM"].copy()

    with pd.ExcelWriter(RELATORIO, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="exames")
        df_pend.to_excel(writer, index=False, sheet_name="pendencias")
        for sheet in ("exames", "pendencias"):
            ws = writer.book[sheet]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for ci in range(1, ws.max_column + 1):
                ws.column_dimensions[ws.cell(1, ci).column_letter].width = 18

    total     = len(df)
    alterados = len(df[df["Status"].str.contains("ALTERADO", na=False)])
    pend_n    = len(df_pend)
    pacientes = df["Paciente"].nunique() if "Paciente" in df.columns else 0

    print("=" * 60)
    print(f"Relatorio: {RELATORIO}")
    print(f"Pacientes: {pacientes}")
    print(f"Exames:    {total}")
    print(f"Pendencias:{pend_n}")
    if total > 0:
        print(f"Alterados: {alterados} ({alterados/total*100:.1f}%)")
    print("=" * 60)

# =========================
# PIPELINE PRINCIPAL
# =========================
def main() -> None:
    imap = imapclient.IMAPClient("imap.gmail.com", ssl=True)
    imap.login(EMAIL, SENHA_APP)
    imap.select_folder("INBOX")

    for lbl in (LABEL_ALTERADO, LABEL_NORMAL, LABEL_REVISAR, LABEL_SINALIZADO):
        garantir_label_existe(imap, lbl)

    criteria = ["FROM", REMETENTE_LAB, "SINCE", data_inicial]
    if somente_nao_lidos:
        criteria = ["UNSEEN"] + criteria

    uids = imap.search(criteria)
    print(f"{len(uids)} e-mails encontrados (desde {data_inicial} ate {data_final}"
          f" / {'UNSEEN' if somente_nao_lidos else 'todos'}).")

    todos_resultados: List[Dict] = []
    sinalizados = pdfs = 0

    for uid in uids:
        fetched = imap.fetch([uid], ["X-GM-LABELS", "BODY[]", "ENVELOPE"])

        # ── Filtro de data final ──────────────────────────────────────
        envelope = fetched[uid].get(b"ENVELOPE")
        if envelope and envelope.date:
            try:
                data_email = envelope.date.date() if hasattr(envelope.date, "date") else envelope.date
                if data_email > data_final:
                    continue
            except Exception:
                pass
        # ──────────────────────────────────────────────────────────────

        labels_atuais = fetched[uid].get(b"X-GM-LABELS", [])
        labels_str = [
            x.decode() if isinstance(x, (bytes, bytearray)) else str(x)
            for x in labels_atuais
        ]

        message = pyzmail.PyzMessage.factory(fetched[uid][b"BODY[]"])
        subject_original = message.get_subject() or "Laudos"
        message_id = obter_message_id(message)

        # ── 1) Baixar PDFs ────────────────────────────────────────────
        pdf_paths = []
        for part in message.mailparts:
            if part.filename and part.filename.lower().endswith(".pdf"):
                nome    = f"{uid}_{part.filename}"
                caminho = os.path.join(PASTA_EXAMES, nome)
                with open(caminho, "wb") as f:
                    f.write(part.get_payload())
                pdf_paths.append((nome, caminho))
                pdfs += 1

        if not pdf_paths:
            continue

        # ── 2) Processar PDFs ─────────────────────────────────────────
        extraiu_algum = falha_texto = False
        resultados_uid: List[Dict] = []

        for nome, caminho in pdf_paths:
            print(f"\n[UID {uid}] {nome}")
            texto = ler_pdf(caminho)

            if not texto or len(texto) < 50:
                print("  Texto insuficiente (revisar)")
                falha_texto = True
                continue

            metadados = extrair_metadados(texto)
            exames    = extrair_exames(texto)

            if exames:
                extraiu_algum = True

            print(f"  {len(exames)} exames extraidos")

            for ex in exames:
                row = {"Arquivo": nome, "EmailUID": uid, **metadados, **ex}
                todos_resultados.append(row)
                resultados_uid.append(row)

        # ── 3) Decisao por e-mail ─────────────────────────────────────
        statuses = [str(r.get("Status", "")).upper() for r in resultados_uid]
        tem_alt  = any("ALTERADO" in s for s in statuses)
        tem_rev  = any(s in ("REVISAR", "N/A", "") for s in statuses)

        if tem_alt:
            status_email = "ALTERADO"
        elif falha_texto or not extraiu_algum or tem_rev:
            status_email = "REVISAR"
        else:
            status_email = "NORMAL"

        # ── 4) Sinalizar no Gmail ─────────────────────────────────────
        try:
            imap.remove_gmail_labels(uid, [LABEL_ALTERADO, LABEL_NORMAL, LABEL_REVISAR])

            if status_email == "ALTERADO":
                imap.add_gmail_labels(uid, [LABEL_ALTERADO])
                imap.add_flags(uid, ["\\Flagged"])
                status_txt = "EXAME ALTERADO — VERIFICAR (enfermagem)"
            elif status_email == "NORMAL":
                imap.add_gmail_labels(uid, [LABEL_NORMAL])
                status_txt = "Exame NORMAL — ok"
            else:
                imap.add_gmail_labels(uid, [LABEL_REVISAR])
                status_txt = "REVISAR — extracao automatica insuficiente / referencia indefinida"

            if message_id and LABEL_SINALIZADO not in labels_str:
                enviar_resposta_thread(subject_original, message_id, status_txt)
                imap.add_gmail_labels(uid, [LABEL_SINALIZADO])
                sinalizados += 1

            print(f"[UID {uid}] Gmail sinalizado: {status_txt}")

        except Exception as e:
            print(f"[UID {uid}] Erro ao sinalizar no Gmail: {e}")

    imap.logout()

    # ── 5) Excel ──────────────────────────────────────────────────────
    print("\nGerando relatorio...")
    gerar_relatorio(todos_resultados)

    print(f"\nResumo:")
    print(f"- PDFs baixados:       {pdfs}")
    print(f"- Threads sinalizadas: {sinalizados}")
    print(f"- Periodo:             {data_inicial} a {data_final}")

if __name__ == "__main__":
    main()
