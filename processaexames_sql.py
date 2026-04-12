import os
import re
import sqlite3
import smtplib
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from email.utils import formatdate
from typing import Dict, List, Union, Optional, Tuple
from contextlib import contextmanager

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

try:
    import pymupdf
except ImportError:
    pymupdf = None
    print("⚠️ pymupdf não instalado. Instalar: pip install pymupdf")

try:
    import pypdf
except ImportError:
    pypdf = None
    print("⚠️ pypdf não instalado. Instalar: pip install pypdf")

try:
    from gerenciador_referencias import GerenciadorReferencias, inicializar, encerrar
    GERENCIADOR_DISPONIVEL = True
except ImportError:
    GERENCIADOR_DISPONIVEL = False
    print("⚠️ gerenciador_referencias não encontrado. Usando modo compatível.")

# =========================
# CONFIG GMAIL + PASTAS
# =========================
from dotenv import load_dotenv
load_dotenv()

EMAIL         = os.getenv("GMAIL_EMAIL",    "")
SENHA_APP     = os.getenv("GMAIL_SENHA",    "")
REMETENTE_LAB = os.getenv("REMETENTE_LAB",  "")
_DATA_DIR     = os.getenv("DATA_DIR",       ".")

PASTA_EXAMES = os.path.join(_DATA_DIR, "exames")
RELATORIO    = os.path.join(_DATA_DIR, "relatorio_exames.xlsx")
DB_PATH      = os.path.join(_DATA_DIR, "exames.db")

LABEL_ALTERADO   = "Exames/🔴 ALTERADO - VERIFICAR"
LABEL_NORMAL     = "Exames/🟢 NORMAL"
LABEL_REVISAR    = "Exames/🟡 REVISAR (falha extração)"
LABEL_SINALIZADO = "Exames/✅ Sinalizado"

os.makedirs(PASTA_EXAMES, exist_ok=True)

# =========================
# BANCO DE DADOS SQLite
# =========================

def criar_banco():
    """
    Cria o banco SQLite com as tabelas necessárias (se não existirem).
    Tabelas:
      - pacientes: dados do paciente (nome, nascimento, médico)
      - processamentos: cada e-mail/lote processado
      - exames: cada resultado individual de exame
    """
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
                registrado_em       TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_exames_paciente  ON exames(paciente_id);
            CREATE INDEX IF NOT EXISTS idx_exames_status    ON exames(status);
            CREATE INDEX IF NOT EXISTS idx_exames_analito   ON exames(analito);
            CREATE INDEX IF NOT EXISTS idx_proc_email_uid   ON processamentos(email_uid);
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
    """
    Insere paciente se não existir (chave: nome + dt_nasc).
    Retorna o id do paciente.
    """
    with get_db() as conn:
        # Tenta inserir; se já existir, ignora
        conn.execute(
            """INSERT OR IGNORE INTO pacientes (nome, dt_nasc, medico)
               VALUES (?, ?, ?)""",
            (nome.strip(), dt_nasc, medico)
        )
        row = conn.execute(
            "SELECT id FROM pacientes WHERE nome = ? AND (dt_nasc = ? OR (dt_nasc IS NULL AND ? IS NULL))",
            (nome.strip(), dt_nasc, dt_nasc)
        ).fetchone()
        return row["id"]


def inserir_processamento(email_uid: int, arquivo_pdf: str,
                          paciente_id: Optional[int], pedido: str,
                          status_email: str) -> int:
    """Registra o processamento de um PDF. Retorna o id gerado."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO processamentos (email_uid, arquivo_pdf, paciente_id, pedido, status_email)
               VALUES (?, ?, ?, ?, ?)""",
            (email_uid, arquivo_pdf, paciente_id, pedido, status_email)
        )
        return cur.lastrowid


def inserir_exames_bulk(processamento_id: int, paciente_id: Optional[int],
                        exames: List[Dict]) -> None:
    """
    Insere todos os exames de um processamento em lote (mais eficiente).
    Calcula pendência antes de inserir.
    """
    rows = []
    for ex in exames:
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
        if not str(ex.get("Valor", "")).strip():
            pendencia = "SIM"
            motivos.append("Sem valor")

        rows.append((
            processamento_id,
            paciente_id,
            ex.get("Analito", ""),
            str(ex.get("Valor", "")),
            ex.get("Unidade", ""),
            ex.get("Referencia", ""),
            status,
            pendencia,
            " | ".join(motivos) if motivos else "",
        ))

    with get_db() as conn:
        conn.executemany(
            """INSERT INTO exames
               (processamento_id, paciente_id, analito, valor, unidade,
                referencia, status, pendencia, motivo_pendencia)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows
        )


def salvar_resultados_no_banco(todos_resultados: List[Dict]) -> None:
    """
    Persiste todos os resultados processados no banco SQLite,
    substituindo a gravação no Excel como passo principal.
    """
    if not todos_resultados:
        print("⚠️  Nenhum resultado para salvar no banco.")
        return

    # Agrupa por (email_uid, arquivo)
    grupos: Dict[tuple, List[Dict]] = {}
    for row in todos_resultados:
        chave = (row.get("EmailUID"), row.get("Arquivo", ""))
        grupos.setdefault(chave, []).append(row)

    total_exames = 0
    for (uid, arquivo), exames in grupos.items():
        # Pega metadados do primeiro item do grupo
        meta = exames[0]
        nome = meta.get("Paciente", "").strip()
        dt_nasc = meta.get("Dt Nasc")
        medico = meta.get("Medico")
        pedido = meta.get("Pedido")
        status_email = meta.get("status_email", "REVISAR")

        paciente_id = None
        if nome:
            paciente_id = upsert_paciente(nome, dt_nasc, medico)

        proc_id = inserir_processamento(uid, arquivo, paciente_id, pedido, status_email)
        inserir_exames_bulk(proc_id, paciente_id, exames)
        total_exames += len(exames)

    print(f"✓ {total_exames} exames salvos no banco '{DB_PATH}'")


# =========================
# RELATÓRIO EXCEL (agora lê do banco)
# =========================

def gerar_relatorio_do_banco(filtro_data_ini: Optional[date] = None,
                              filtro_data_fim: Optional[date] = None) -> None:
    """
    Gera o Excel lendo os dados diretamente do banco SQLite.
    Mantém compatibilidade com o fluxo anterior.
    """
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
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = 18

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


# =========================
# CONSULTAS ÚTEIS AO BANCO
# =========================

def buscar_historico_paciente(nome_parcial: str) -> pd.DataFrame:
    """Retorna o histórico de exames de um paciente pelo nome (busca parcial)."""
    query = """
        SELECT p.nome AS Paciente, p.dt_nasc AS "Dt Nasc",
               e.analito AS Analito, e.valor AS Valor, e.unidade AS Unidade,
               e.status AS Status, e.registrado_em AS Data
        FROM exames e
        JOIN pacientes p ON e.paciente_id = p.id
        WHERE p.nome LIKE ?
        ORDER BY e.registrado_em DESC
    """
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=(f"%{nome_parcial}%",))


def buscar_exames_alterados(dias: int = 30) -> pd.DataFrame:
    """Retorna exames alterados nos últimos N dias."""
    query = """
        SELECT p.nome AS Paciente, e.analito AS Analito,
               e.valor AS Valor, e.unidade AS Unidade,
               e.referencia AS Referencia, e.status AS Status,
               e.registrado_em AS Data
        FROM exames e
        LEFT JOIN pacientes p ON e.paciente_id = p.id
        WHERE e.status LIKE '%ALTERADO%'
          AND e.registrado_em >= datetime('now', ?, 'localtime')
        ORDER BY e.registrado_em DESC
    """
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=(f"-{dias} days",))


def estatisticas_gerais() -> Dict:
    """Retorna um resumo estatístico do banco."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        stats = {}
        stats["total_exames"]    = cur.execute("SELECT COUNT(*) FROM exames").fetchone()[0]
        stats["total_pacientes"] = cur.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
        stats["alterados"]       = cur.execute("SELECT COUNT(*) FROM exames WHERE status LIKE '%ALTERADO%'").fetchone()[0]
        stats["pendencias"]      = cur.execute("SELECT COUNT(*) FROM exames WHERE pendencia = 'SIM'").fetchone()[0]
        stats["processamentos"]  = cur.execute("SELECT COUNT(*) FROM processamentos").fetchone()[0]
        return stats


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
# INPUT (DATA INICIAL + FINAL)
# =========================
data_ini_str = input("Baixar exames a partir de qual data? (YYYY-MM-DD) [ENTER = hoje]: ").strip()
if data_ini_str:
    try:
        data_inicial = datetime.strptime(data_ini_str, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("Data inicial inválida. Use YYYY-MM-DD")
else:
    data_inicial = date.today()

data_fim_str = input("Baixar exames até qual data? (YYYY-MM-DD) [ENTER = hoje]: ").strip()
if data_fim_str:
    try:
        data_final = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("Data final inválida. Use YYYY-MM-DD")
else:
    data_final = date.today()

if data_final < data_inicial:
    raise SystemExit("Data final não pode ser menor que a data inicial.")

somente_nao_lidos = input("Baixar apenas NÃO LIDOS? (s/n) [s]: ").strip().lower()
somente_nao_lidos = (somente_nao_lidos in ("", "s", "sim", "y", "yes"))

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
    if OCR_MELHORADO_DISPONIVEL:
        try:
            texto, info = ler_pdf_melhorado(pdf_path, usar_cache=True, verbose=False)
            if texto:
                return texto
        except Exception as e:
            print(f"Aviso: OCR melhorado falhou, tentando fallback: {e}")
    texto = ""
    try:
        imagens = convert_from_path(pdf_path)
        for img in imagens:
            texto += pytesseract.image_to_string(img, lang="por+eng") + "\n"
    except Exception as e:
        print(f"Erro no OCR de {pdf_path}: {e}")
    return texto.strip()

def ler_pdf(pdf_path: str) -> str:
    if OCR_MELHORADO_DISPONIVEL:
        try:
            print("  → Usando OCR Melhorado v2.1...")
            texto, info = ler_pdf_melhorado(pdf_path, usar_cache=True, verbose=True)
            if len(texto) >= 100:
                print(f"    ✓ {info.get('metodo', 'desconhecido')} OK (conf: {info.get('confianca', 0):.2f})")
                return texto
        except Exception as e:
            print(f"  ⚠️ OCR melhorado falhou: {e}. Tentando fallback...")

    print("  → Usando método legado...")
    for nome_metodo, func in [
        ("pdfplumber", extrai_texto_pdf),
        ("PyMuPDF",    extrai_texto_pymupdf),
        ("pypdf",      extrai_texto_pypdf),
        ("OCR",        extrai_texto_ocr),
    ]:
        print(f"  → Tentando {nome_metodo}...")
        texto = func(pdf_path)
        if len(texto) >= 100:
            print(f"    ✓ {nome_metodo} OK")
            return texto

    print("  ⚠️ Falha ao extrair texto do PDF")
    return ""

# =========================
# METADADOS / PACIENTE
# =========================
def extrair_nome_paciente_universal(texto: str) -> str:
    match = re.search(
        r'Nome\s*:\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)(?:\s+(?:Invalid|S\s*e\s*x\s*o|Sexo|CPF|RG)|$)',
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
        texto, re.IGNORECASE
    )
    if match_nasc:
        metadados["Dt Nasc"] = match_nasc.group(1)

    match_medico = re.search(
        r"Solicitante[:\s]+([A-ZÀ-Ü][A-Za-zà-ÿ\s\.]+?)(?:\s+Data|\n)",
        texto, re.IGNORECASE
    )
    if match_medico:
        metadados["Medico"] = match_medico.group(1).strip()

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

def e_analito_observacao(linha: str) -> bool:
    observacoes = [
        "MICROCITOSE", "MACROCITOSE", "ANISOCITOSE", "POIQUILOCITOSE",
        "HIPOCROMIA", "POLICROMASIA", "DISCRETA", "MODERADA", "ACENTUADA",
        "LEVE", "INTENSA", "OCASIONAL", "RAROS", "NUMEROSOS",
        "VALORES DE", "SÉRIE BRANCA", "SÉRIE VERMELHA"
    ]
    linha_upper = linha.upper().strip()
    return any(obs in linha_upper for obs in observacoes)

def e_nome_exame_valido(linha: str) -> bool:
    if e_analito_observacao(linha):
        return False
    termos_invalidos = [
        "VALORES", "RESULTADO", "AUTENTICIDADE", "EVOLUÇÃO", "REFERÊNCIA",
        "UNIDADE", "MÉTODO", "MATERIAL", "LAUDO", "PÁGINA", "LABORATÓRIO",
        "PREFEITURA", "MUNICIPAL", "DIETA", "ASSOCIAÇÃO",
        "REQUER", "CORRELAÇÃO", "DADOS CLÍNICOS", "EPIDEMIOLÓGICOS",
        "LIBERADO", "RESPONSÁVEL", "EXAMES COLETADOS", "ANÁLISE",
        "ERITROGRAMA", "LEUCOGRAMA", "PEDIDO", "CPF", "SOLICITANTE",
        "DESTINO", "ORIGEM", "EMISSÃO", "CNES", "GRAVIDAS", "GRÁVIDAS",
        "DATA", "NOTAS", "FL.:", "TRIMESTRE"
    ]
    linha_upper = linha.upper().strip()
    if any(termo in linha_upper for termo in termos_invalidos):
        return False
    if re.match(r"^[\.:\-=\*\_\+]+$", linha):
        return False
    if len(linha.strip()) < 3 or len(linha) > 70:
        return False
    if linha.count(" ") > 10:
        return False
    if re.match(r"^\d", linha):
        return False
    return True

# =========================
# HELPERS DE REFERÊNCIA
# =========================
def _to_float(x: str) -> Optional[float]:
    try:
        return float(x.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None

def _parse_ref_text(ref_txt: str) -> Tuple[Optional[float], Optional[float], str]:
    if not ref_txt:
        return None, None, ""
    rt = re.sub(r"\s+", " ", ref_txt).strip()
    if re.search(r"\b(negativo|não reagente|nao reagente|ausente)\b", rt, re.IGNORECASE):
        return None, None, rt
    if re.search(r"\b(positivo|reagente| presente|detectado)\b", rt, re.IGNORECASE):
        return None, None, rt
    m = re.search(r"(?:de\s*)?[\d\.,]+\s*(?:a|até|ate|-)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        m = re.search(r"(?:de\s*)?([\d\.,]+)\s*(?:a|até|ate|-)\s*([\d\.,]+)", rt, re.IGNORECASE)
        v1 = _to_float(m.group(1))
        v2 = _to_float(m.group(2))
        if v1 is not None and v2 is not None:
            return min(v1, v2), max(v1, v2), rt
    m = re.search(r"(?:até|ate|inferior a|menor que|normal até|normal ate)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return None, v, rt
    m = re.search(r"(?:maior que|superior a)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return v, None, rt
    return None, None, rt

def determinar_status(valor, ref_inf, ref_sup, ref_texto: str = "") -> str:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "REVISAR"
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
    if isinstance(valor, str):
        v = valor.strip().upper()
        if v in ("NEGATIVO", "NÃO REAGENTE", "NAO REAGENTE", "AUSENTE", "NÃO DETECTADO", "NAO DETECTADO"):
            return "NORMAL"
        if v in ("POSITIVO", "REAGENTE", "PRESENTE", "DETECTADO"):
            return "[ALTERADO]"
        if re.fullmatch(r"\d\+", v):
            return "REVISAR"
        return "REVISAR"
    return "REVISAR"

def classificar_exame_otimizado(nome_exame, valor, genero=None, idade=None):
    if GERENCIADOR:
        try:
            try:
                valor_float = float(str(valor).replace(",", "."))
                resultado = GERENCIADOR.classificar_valor(
                    nome_exame=nome_exame, valor=valor_float,
                    genero=genero, idade=idade
                )
            except (ValueError, TypeError):
                resultado = GERENCIADOR.classificar_valor_qualitativo(
                    nome_exame=nome_exame, valor=str(valor)
                )
            status = resultado.get("status", "REVISAR")
            status_final = {"NORMAL": "NORMAL", "ALTERADO": "[ALTERADO]", "LIMÍTROFE": "[LIMÍTROFE]"}.get(status, "REVISAR")
            return {
                "status": status_final,
                "valor": resultado.get("valor", valor),
                "unidade": resultado.get("unidade", ""),
                "categoria": resultado.get("categoria", ""),
                "referencia": resultado.get("referencia", ""),
                "detalhes": resultado.get("detalhes", "")
            }
        except Exception as e:
            print(f"  ⚠️ Erro ao classificar com gerenciador: {e} (usando fallback)")
    return {"status": "REVISAR", "valor": valor, "unidade": "", "categoria": "", "referencia": ""}

# =========================
# PARSERS DEDICADOS: URINA E HEMOGRAMA
# =========================
def _is_urina_context(texto_upper):
    return any(k in texto_upper for k in ("URINA", "EAS", "URINA TIPO", "ELEMENTOS ANORMAIS", "SEDIMENTO"))

def _is_hemograma_context(texto_upper):
    return "HEMOGRAMA" in texto_upper or "ERITROGRAMA" in texto_upper or "LEUCOGRAMA" in texto_upper

def extrair_urina(texto: str) -> List[Dict]:
    resultados = []
    linhas = [l.rstrip() for l in texto.splitlines() if l.strip()]
    if not _is_urina_context(texto.upper()):
        return resultados
    for ln in linhas:
        line = re.sub(r"\s+", " ", ln).strip()
        m = re.match(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\/\-]+?)\s*(?:\.{2,}|\s)*:\s*(.+)$", line)
        if not m:
            continue
        analito = m.group(1).strip()
        resto = m.group(2).strip()
        if not e_nome_exame_valido(analito):
            continue
        m2 = re.match(
            r"^([\d\.,]+|\w[\w\s\+\-]+)\s*(/ml|/uL|/µL|/mm3|/mm³|mg/dL|g/dL|uL|µL|mm³|mm3|%|)\s*(.*)$",
            resto, re.IGNORECASE
        )
        if m2:
            val_raw, unidade, ref_raw = m2.group(1).strip(), m2.group(2).strip(), m2.group(3).strip()
        else:
            val_raw, unidade, ref_raw = resto, "", ""
        valor = normalizar_valor(val_raw)
        ref_inf, ref_sup, ref_txt = _parse_ref_text(ref_raw)
        status = determinar_status(valor, ref_inf, ref_sup, ref_txt)
        resultados.append({"Analito": f"URINA - {analito}", "Valor": valor, "Unidade": unidade, "Referencia": ref_txt, "Status": status})
    return resultados

def extrair_hemograma(texto: str) -> List[Dict]:
    resultados = []
    if not _is_hemograma_context(texto.upper()):
        return resultados
    linhas = [re.sub(r"\s+", " ", l).strip() for l in texto.splitlines() if l.strip()]
    for line in linhas:
        m = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\-\/]+?)\s*(?:\.{2,}|\s)*:\s*([\d\.,]+)\s*([A-Za-z%µ/³0-9]+)?\s*(.*)$",
            line
        )
        if not m:
            continue
        analito = m.group(1).strip()
        if not e_nome_exame_valido(analito) or analito.upper() in ("HEMOGRAMA", "ERITROGRAMA", "LEUCOGRAMA", "PLAQUETOGRAMA"):
            continue
        val_raw = m.group(2).strip()
        unidade = (m.group(3) or "").strip()
        ref_raw = (m.group(4) or "").strip()
        valor = normalizar_valor(val_raw)
        ref_inf, ref_sup, ref_txt = _parse_ref_text(ref_raw)
        status = determinar_status(valor, ref_inf, ref_sup, ref_txt)
        resultados.append({"Analito": f"HEMOGRAMA - {analito}", "Valor": valor, "Unidade": unidade, "Referencia": ref_txt, "Status": status})
    for line in linhas:
        m = re.match(
            r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\(\)\-\/]+?)\s*(?:\.{2,}|\s)*:\s*"
            r"(\d{1,3}(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s+"
            r"(\d+(?:[.,]\d+)?)\s*(?:a|-|até|ate)\s*(\d+(?:[.,]\d+)?)\s*%?\s+"
            r"(\d+(?:[.,]\d+)?)\s*(?:a|-|até|ate)\s*(\d+(?:[.,]\d+)?)\s*/?\s*(mm3|mm³|µL|uL|/mm3|/mm³)?$",
            line, re.IGNORECASE
        )
        if not m:
            continue
        nome = m.group(1).strip()
        if not e_nome_exame_valido(nome):
            continue
        perc, abs_ = normalizar_valor(m.group(2)), normalizar_valor(m.group(3))
        refp1, refp2 = _to_float(m.group(4)), _to_float(m.group(5))
        refa1, refa2 = _to_float(m.group(6)), _to_float(m.group(7))
        un_abs = (m.group(8) or "mm³").replace("/", "").strip()
        if isinstance(perc, (int, float)) and refp1 and refp2:
            st = determinar_status(perc, min(refp1, refp2), max(refp1, refp2), "")
            resultados.append({"Analito": f"HEMOGRAMA - {nome} (%)", "Valor": perc, "Unidade": "%", "Referencia": f"{min(refp1,refp2)} - {max(refp1,refp2)}", "Status": st})
        if isinstance(abs_, (int, float)) and refa1 and refa2:
            st = determinar_status(abs_, min(refa1, refa2), max(refa1, refa2), "")
            resultados.append({"Analito": f"HEMOGRAMA - {nome} (abs)", "Valor": abs_, "Unidade": f"/{un_abs}", "Referencia": f"{min(refa1,refa2)} - {max(refa1,refa2)}", "Status": st})
    vistos, out = set(), []
    for r in resultados:
        key = (r["Analito"], r["Valor"], r["Unidade"], r["Referencia"])
        if key not in vistos:
            vistos.add(key)
            out.append(r)
    return out

# =========================
# EXTRAÇÃO GENÉRICA
# =========================
def _extrair_limites_textuais(bloco_texto: str):
    ref_inf = ref_sup = None
    ref_txt_normal = ""
    for linha in [l.strip() for l in bloco_texto.splitlines() if l.strip()]:
        low = linha.lower()
        is_normal_line = "normal" in low
        m = re.search(r"(inferior a|menor que|até|ate|igual ou inferior a|<=)\s*([\d\.,]+)", low)
        if m:
            val = _to_float(m.group(2))
            if val and (is_normal_line or ref_sup is None):
                ref_sup = val
                if is_normal_line: ref_txt_normal = linha
        m = re.search(r"(superior a|maior que|igual ou superior a|>=)\s*([\d\.,]+)", low)
        if m:
            val = _to_float(m.group(2))
            if val and (is_normal_line or ref_inf is None):
                ref_inf = val
                if is_normal_line: ref_txt_normal = linha
        m = re.search(r"([\d\.,]+)\s*(a|até|ate|-)\s*([\d\.,]+)", low)
        if m and ("refer" in low or "risco" in low or "normal" in low):
            v1, v2 = _to_float(m.group(1)), _to_float(m.group(3))
            if v1 and v2 and ref_inf is None and ref_sup is None:
                ref_inf, ref_sup = min(v1, v2), max(v1, v2)
                if is_normal_line: ref_txt_normal = linha
    return ref_inf, ref_sup, ref_txt_normal

def extrair_resultado_referencia(bloco_texto: str) -> Dict:
    dados = {"valor": "", "unidade": "", "ref_inf": "", "ref_sup": "", "referencia_texto": ""}
    m = re.search(r"Resultado[:\s]*(?:\n)?\s*([\d,\.]+)\s+([a-zA-Zµ°/%²³]+(?:/[a-zA-Z]+)?)", bloco_texto, re.IGNORECASE)
    if m:
        dados["valor"] = normalizar_valor(m.group(1))
        dados["unidade"] = m.group(2).strip()
    else:
        m = re.search(
            r"^\s*([\d,\.]+)\s+(mg/dL|g/dL|g/L|g%|mmol/L|mUI/L|U/L|ng/mL|ug/dL|pg/mL|fL|u3|%|/mm³|mil/mm³|milhoes/mm³|x10³/µL|mm³)\s*$",
            bloco_texto, re.MULTILINE | re.IGNORECASE
        )
        if m:
            dados["valor"] = normalizar_valor(m.group(1))
            dados["unidade"] = m.group(2).strip()
    m = re.search(r"(?:De|Refer[eê]ncia|VR|V\.?R\.?)[:\s]*([\d,\.]+)\s*(?:a|até|-)\s*([\d,\.]+)", bloco_texto, re.IGNORECASE)
    if m:
        v1, v2 = _to_float(m.group(1)), _to_float(m.group(2))
        if v1 and v2:
            dados["ref_inf"], dados["ref_sup"] = min(v1, v2), max(v1, v2)
    if dados["ref_inf"] == "" and dados["ref_sup"] == "":
        ri, rs, rt = _extrair_limites_textuais(bloco_texto)
        if ri: dados["ref_inf"] = ri
        if rs: dados["ref_sup"] = rs
        if rt: dados["referencia_texto"] = rt
    if dados["valor"] == "" or dados["valor"] is None:
        m = re.search(r"Resultado[:\s]+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇÃÕ][A-Za-zà-ÿ\s]+?)(?:\n|Refer|Obs|Método|Material|$)", bloco_texto, re.IGNORECASE)
        if m:
            dados["valor"] = m.group(1).strip()
    return dados

def extrair_exames(texto: str) -> List[Dict]:
    exames = []
    exames.extend(extrair_urina(texto))
    exames.extend(extrair_hemograma(texto))
    linhas = texto.split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()
        if linha and (linha.isupper() or (linha[0].isupper() and len(linha) > 3)):
            if e_nome_exame_valido(linha):
                bloco = "\n".join(linhas[i:min(i + 45, len(linhas))])
                dados = extrair_resultado_referencia(bloco)
                if dados["valor"] not in ("", None):
                    status = determinar_status(dados["valor"], dados["ref_inf"], dados["ref_sup"], dados["referencia_texto"])
                    referencia = (
                        f"{dados['ref_inf']} - {dados['ref_sup']}" if dados["ref_inf"] != "" and dados["ref_sup"] != ""
                        else dados["referencia_texto"]
                    )
                    exames.append({"Analito": linha, "Valor": dados["valor"], "Unidade": dados["unidade"], "Referencia": referencia, "Status": status})
        i += 1
    vistos, out = set(), []
    for r in exames:
        key = (r.get("Analito"), r.get("Valor"), r.get("Unidade"), r.get("Referencia"))
        if key not in vistos:
            vistos.add(key)
            out.append(r)
    return out

# =========================
# GMAIL: LABELS + THREAD REPLY
# =========================
def garantir_label_existe(imap, nome_label):
    try:
        existentes = {f[2] for f in imap.list_folders()}
        if nome_label not in existentes:
            imap.create_folder(nome_label)
            print(f"Label criada: {nome_label}")
    except Exception as e:
        print(f"Aviso: não consegui validar/criar label '{nome_label}': {e}")

def obter_message_id(pyz_msg) -> str:
    mid = (
        pyz_msg.get_decoded_header("Message-ID") or
        pyz_msg.get_decoded_header("Message-Id") or
        pyz_msg.get_decoded_header("MESSAGE-ID")
    )
    if not mid:
        return ""
    mid = str(mid).strip()
    if not (mid.startswith("<") and mid.endswith(">")):
        mid = f"<{mid.strip('<>')}>"
    return mid

def enviar_resposta_thread(subject_original, message_id, status_txt):
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
    msg.set_content(f"{status_txt}\n\n— Sinalização automática para triagem de enfermagem.")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, SENHA_APP)
        smtp.send_message(msg)

# =========================
# PIPELINE PRINCIPAL
# =========================
def main():
    # Garante que o banco existe
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
    print(f"{len(uids)} e-mails encontrados ({data_inicial} até {data_final} / {'UNSEEN' if somente_nao_lidos else 'todos'}).")

    todos_resultados = []
    sinalizados = 0
    pdfs = 0

    for uid in uids:
        fetched = imap.fetch([uid], ["X-GM-LABELS", "BODY[]"])
        labels_atuais_str = [
            x.decode() if isinstance(x, (bytes, bytearray)) else str(x)
            for x in fetched[uid].get(b"X-GM-LABELS", [])
        ]
        message = pyzmail.PyzMessage.factory(fetched[uid][b"BODY[]"])
        subject_original = message.get_subject() or "Laudos"
        message_id = obter_message_id(message)

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

        extraiu_algum = False
        falha_texto = False
        resultados_uid = []

        for nome, caminho in pdf_paths:
            print(f"\n[UID {uid}] 📄 {nome}")
            texto = ler_pdf(caminho)
            if not texto or len(texto) < 50:
                print("  ⚠️ Texto insuficiente (revisar)")
                falha_texto = True
                continue

            metadados = extrair_metadados(texto)
            exames = extrair_exames(texto)
            if exames:
                extraiu_algum = True
            print(f"  🔬 {len(exames)} exames extraídos")

            for ex in exames:
                row = {"Arquivo": nome, "EmailUID": uid, **metadados, **ex}
                todos_resultados.append(row)
                resultados_uid.append(row)

        statuses = [str(r.get("Status", "")).upper() for r in resultados_uid]
        tem_alterado = any("ALTERADO" in s for s in statuses)
        tem_revisar = any(s in ("REVISAR", "N/A", "") for s in statuses)

        if tem_alterado:
            status_email = "ALTERADO"
        elif falha_texto or not extraiu_algum or tem_revisar:
            status_email = "REVISAR"
        else:
            status_email = "NORMAL"

        # Anota status_email em cada resultado deste UID (para salvar no banco)
        for r in resultados_uid:
            r["status_email"] = status_email

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
                status_txt = "🟡 REVISAR — extração automática insuficiente / referência indefinida"

            if message_id and (LABEL_SINALIZADO not in labels_atuais_str):
                enviar_resposta_thread(subject_original, message_id, status_txt)
                imap.add_gmail_labels(uid, [LABEL_SINALIZADO])
                sinalizados += 1

            print(f"[UID {uid}] ✅ Gmail sinalizado: {status_txt}")
        except Exception as e:
            print(f"[UID {uid}] ❌ Erro ao sinalizar no Gmail: {e}")

    imap.logout()

    # 5) SALVAR NO BANCO (substitui gravação direta em Excel como passo principal)
    print("\nSalvando no banco de dados...")
    salvar_resultados_no_banco(todos_resultados)

    # 6) EXCEL (gerado a partir do banco, mantém compatibilidade)
    print("\nGerando relatório Excel...")
    gerar_relatorio_do_banco(data_inicial, data_final)

    # Resumo final com estatísticas do banco
    stats = estatisticas_gerais()
    print("\nResumo do banco:")
    print(f"- PDFs baixados nesta execução: {pdfs}")
    print(f"- Threads sinalizadas: {sinalizados}")
    print(f"- Total de pacientes no banco: {stats['total_pacientes']}")
    print(f"- Total de exames no banco: {stats['total_exames']}")
    print(f"- Exames alterados (histórico): {stats['alterados']}")
    print(f"- Pendências (histórico): {stats['pendencias']}")

    if GERENCIADOR:
        try:
            encerrar()
            print("\n✓ Gerenciador de referências encerrado")
        except Exception as e:
            print(f"⚠️ Erro ao encerrar gerenciador: {e}")


if __name__ == "__main__":
    main()
