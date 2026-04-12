"""
IPL-APS Engine v1.0
Computa o Índice de Prioridade Laboratorial a partir do banco exames.db
"""

import sqlite3, os, re, unicodedata, math
from datetime import datetime, date, timedelta
from collections import defaultdict
from contextvars import ContextVar

# Carrega variáveis de ambiente do .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# DB_PATH padrão — pode ser sobrescrito por calcular_territorio(db_path=...)
# sem afetar outras requisições simultâneas (thread/async safe via ContextVar)
DB_PATH = os.path.join(os.getenv("DATA_DIR", "."), "exames.db")
_CTX_DB: ContextVar[str] = ContextVar("db_path", default=DB_PATH)

# ── Normalização ──────────────────────────────────────────────────────────────
_BLOCKLIST_NORM = re.compile(
    r'^('
    r'de\s|até\s|a\s+\d|acima\s|abaixo\s|maior\s|menor\s|inferior\s|superior\s'
    r'|normal$|normal[\s:]|desejável|ideal\s|adulto|criança|homem\s|mulher\s|grávid|gravid'
    r'|trimestre|semana\s|fase\s|pós\s|pos\s|menopausa|reprodutiv'
    r'|nota\s*:|obs\s*:|método\s*:|material\s*:|autenticidade\s*:'
    r'|normatiz|determinação|consenso|diretriz|associação'
    r'|liberado|responsável|exames\s+colet'
    r'|coleta\s|referência|resultado\s+confirm'
    r'|\d{1,3}[,\.]\d'
    r')',
    re.IGNORECASE
)

def _norm(s: str) -> str:
    s = re.split(r'\.{3,}', s)[0].split(':')[0].strip()
    if _BLOCKLIST_NORM.match(s):
        return ''
    parts = s.split()
    # Strip trailing numeric tokens (including comma-decimals like "6,02")
    while parts and re.match(r'^[\d\.,]+$', parts[-1]):
        parts.pop()
    result = ' '.join(parts).strip().upper()
    # Reject strings that look like reference ranges (contain units)
    if (len(result) < 3 or len(result) > 60 or result[:1].isdigit()
            or re.search(r'\b(MUI|MMOL|MG/|G/DL|U/L|NG/|PG/|UG/|/MM)\b', result)):
        return ''
    return result

def _ascii(s: str) -> str:
    """Remove acentos para comparação insensível a diacríticos."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')

def _contem(analito: str, keyword: str) -> bool:
    """Verifica se keyword é substring de analito, ignorando acentos."""
    return _ascii(keyword) in _ascii(analito)

# ── Grupos ────────────────────────────────────────────────────────────────────
# Palavras-chave sem acentos — comparação usa _ascii() em ambos os lados
_GRUPOS_KW = [
    ("renal",        ["CREATININA","UREIA","CLEARANCE","CISTATINA","PROTEINURIA","MICROALBUMINA"]),
    ("eletrolitico", ["SODIO","POTASSIO","CALCIO","MAGNESIO","FOSFORO","BICARBONATO","CLORETO",
                      "PARATORMONIO","PTH"]),
    ("hematologico", ["HEMOGRAMA","HEMOGLOBINA","HEMATOCRIT","ERITROCIT","LEUCOCIT","PLAQUETA",
                      "VCM","HCM","CHCM","RDW","NEUTROF","LINFOCIT","MONOCIT","EOSINOF","BASOF",
                      "SEGMENTAD","LINF","FERRO","FERRITIN","TRANSFERRIN"]),
    ("inflamatorio", ["PCR","PROTEINA C","VHS","FIBRINOGEN","PROCALCIT","INTERLEUCINA"]),
    ("metabolico",   ["GLICOSE","GLICEMIA","HBA1C","HEMOGLOBINA GLICADA","INSULINA","COLESTEROL",
                      "LDL","HDL","VLDL","TRIGLICERID","FRUTOSAMINA","PEPTIDEO","TSH","T4","T3",
                      "VITAMINA","ACIDO URICO","BILIRRUB","TGO","TGP","AST","ALT","GGT",
                      "FOSFATASE","AMILASE","LIPASE","ALBUMINA","CORTISOL","PROLACTINA",
                      "TESTOSTERONA","ESTRADIOL","FSH","LH","CPK","CREATINOQUINAS",
                      "INSULINA","PSA","TIROXINA","TRIIODOTIRONINA"]),
]

def _grupo(a: str) -> str:
    for grp, kws in _GRUPOS_KW:
        if any(_contem(a, k) for k in kws):
            return grp
    return "metabolico"

# ── Pesos ─────────────────────────────────────────────────────────────────────
# Chaves sem acentos — _ascii() normaliza na hora da comparação
_PESOS_KW = [
    (["CREATININA"],                        25),
    (["UREIA"],                             15),
    (["POTASSIO"],                          18),
    (["SODIO"],                             15),
    (["CALCIO"],                            12),
    (["MAGNESIO"],                          10),
    (["HBA1C","HEMOGLOBINA GLICADA"],       20),
    (["GLICOSE","GLICEMIA"],                15),
    (["HEMOGLOBINA"],                       15),
    (["PLAQUETA"],                          12),
    (["LEUCOCIT"],                          10),
    (["PCR","PROTEINA C"],                  12),
    (["LDL"],                               12),
    (["PARATORMONIO","PTH"],                10),
    (["CORTISOL"],                          10),
    (["COLESTEROL"],                        10),
    (["TRIGLICERID"],                       10),
    (["TGO","AST"],                         10),
    (["TGP","ALT"],                         10),
    (["TSH"],                               10),
    (["ACIDO URICO"],                       10),
    (["HDL"],                                8),
    (["T4","T3"],                            8),
    (["FERRITIN","FERRO SERIC","FERRO SER"], 8),
    (["TRANSFERRIN"],                        8),
    (["VITAMINA"],                           8),
    (["VHS"],                                8),
    (["CPK","CREATINOQUINAS"],               6),
    (["FSH","LH"],                           6),
    (["TESTOSTERONA","ESTRADIOL"],           6),
    (["PROLACTINA"],                         5),
    (["AMILASE","LIPASE"],                   5),
]

def _peso(a: str) -> float:
    a_ascii = _ascii(a)
    for kws, p in _PESOS_KW:
        if any(_ascii(k) in a_ascii for k in kws):
            return float(p)
    return 5.0

# ── Condições crônicas inferidas ──────────────────────────────────────────────
# Chaves sem acentos — _ascii() usado em _inferir_cronicas
_INFER_COND = [
    ("DM2",          ["HBA1C","HEMOGLOBINA GLICADA","GLICOSE","GLICEMIA","INSULINA"]),
    ("DRC",          ["CREATININA","UREIA","CISTATINA","MICROALBUMINA","PARATORMONIO","PTH"]),
    ("DLP",          ["COLESTEROL","LDL","HDL","TRIGLICERID"]),
    ("ICC",          ["BNP","PRO-BNP","TROPONINA"]),
    ("Tireoidopatia",["TSH","T4 LIVRE","T3 LIVRE","TIROXINA","T4","T3","TRIIODOTIRONINA"]),
    ("Anemia",       ["HEMOGLOBINA","FERRITIN","FERRO","TRANSFERRIN","VITAMINA B12"]),
    ("Hepatopatia",  ["TGO","TGP","AST","ALT","GGT","BILIRRUB","ALBUMINA"]),
    ("Gota",         ["ACIDO URICO"]),
    ("Insuficiencia Adrenal", ["CORTISOL"]),
]

def _inferir_cronicas(por_analito: dict) -> list:
    """
    Infere condição crônica somente se ao menos um analito do painel estiver ALTERADO
    na direção clínica esperada (evita DM2 de HbA1c baixa, Anemia de Hb alta, etc.).
    """
    # Exclusões de substring (falso positivo)
    _EXCL: dict = {
        "Anemia":      ["GLICADA", "HBA1C", "A1C"],       # HbA1c é DM2, não anemia
        "DM2":         ["HEMOGLOBINA GLICADA ESTIMADA"],   # GME é derivado
        "Hepatopatia": ["HEMOGLOBINA", "HEMATOCRIT"],
    }
    # Direção obrigatória — None = qualquer ALTERADO
    _DIRECAO: dict = {
        "DM2":         "ACIMA",    # hiperglicemia / HbA1c elevada
        "Anemia":      "ABAIXO",   # hemoglobina / ferritina baixa
        "DRC":         "ACIMA",    # creatinina / ureia elevada
        "Gota":        "ACIMA",    # ácido úrico elevado
        "Hepatopatia": "ACIMA",    # transaminases elevadas
        "ICC":         "ACIMA",    # BNP / troponina elevados
    }
    result = []
    for cond, kws in _INFER_COND:
        excl    = _EXCL.get(cond, [])
        dir_req = _DIRECAO.get(cond)
        for key, registros in por_analito.items():
            if excl and any(_contem(key, e) for e in excl):
                continue
            if any(_contem(key, k) for k in kws):
                st_up = str(registros[-1][2]).upper()
                if "ALTERADO" not in st_up:
                    continue
                if dir_req and dir_req not in st_up:
                    continue   # direção errada — não confirma condição
                result.append(cond)
                break
    return result

# ── Faixa etária ──────────────────────────────────────────────────────────────
def _anos(dt_nasc: str) -> int:
    """Parse birth date in DD/MM/YYYY or YYYY-MM-DD and return age in years."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return (date.today() - datetime.strptime(dt_nasc[:10], fmt).date()).days // 365
        except Exception:
            continue
    return 50  # fallback

def _faixa(dt_nasc: str) -> tuple:
    """Faixa etária com granularidade por decênio — transição clínica mais precisa."""
    if not dt_nasc:
        return "50-59", 8.0
    anos = _anos(dt_nasc)
    if anos >= 80: return "80+",   22.0
    if anos >= 70: return "70-79", 16.0
    if anos >= 60: return "60-69", 11.0
    if anos >= 50: return "50-59",  8.0
    if anos >= 40: return "40-49",  5.0
    if anos >= 18: return "18-39",  2.0
    return "<18",   1.0


def _magnitude_fator(valor_str: str, ref_str: str, status: str) -> float:
    """
    Fator de severidade baseado em quanto o valor desvia da referência.
    Bordeline (≤10% fora): 0.75 | Moderado (10-50%): 1.0
    Grave (50-100%): 1.4       | Crítico (>100%):    1.85
    Sem referência parseável:  1.0
    """
    if not valor_str or not ref_str:
        return 1.0
    m = re.match(r'([\d,\.]+)\s*[-–]\s*([\d,\.]+)', ref_str.strip())
    if not m:
        return 1.0
    try:
        ref_inf = float(m.group(1).replace(',', '.'))
        ref_sup = float(m.group(2).replace(',', '.'))
        val     = float(str(valor_str).replace(',', '.'))
        span    = ref_sup - ref_inf
        if span <= 0:
            return 1.0
        if "ACIMA" in str(status).upper():
            desvio = (val - ref_sup) / span
        elif "ABAIXO" in str(status).upper():
            desvio = (ref_inf - val) / span
        else:
            return 1.0
        if desvio <= 0.10: return 0.75   # borderline
        if desvio <= 0.50: return 1.00   # moderado
        if desvio <= 1.00: return 1.40   # grave
        return 1.85                       # crítico
    except Exception:
        return 1.0


# ── Padrões sinérgicos — combinações clínicas que amplificam o risco ──────────
# Formato: ([frag_key:DIRECAO, ...], bônus, descrição)
_PADROES_SINERGICOS = [
    # Renal crítico
    (["CREATININA:ACIMA",  "POTASSIO:ACIMA"],        28, "Nefropatia + hipercalemia"),
    (["CREATININA:ACIMA",  "UREIA:ACIMA"],            16, "Síndrome urêmica"),
    (["CREATININA:ACIMA",  "MICROALBUMINA:ACIMA"],    14, "Nefropatia com albuminúria"),
    # DM complicado
    (["HBA1C:ACIMA",       "CREATININA:ACIMA"],       20, "Nefropatia diabética"),
    (["HBA1C:ACIMA",       "LDL:ACIMA"],              12, "DM + dislipidemia"),
    (["HBA1C:ACIMA",       "HEMOGLOBINA:ABAIXO"],     10, "DM + anemia"),
    # Risco cardiovascular composto
    (["LDL:ACIMA",         "GLICOSE:ACIMA"],          12, "Síndrome metabólica"),
    (["LDL:ACIMA",         "TRIGLICERID:ACIMA"],      10, "Dislipidemia mista"),
    (["POTASSIO:ACIMA",    "SODIO:ABAIXO"],           18, "Desequilíbrio eletrolítico grave"),
    (["POTASSIO:ABAIXO",   "MAGNESIO:ABAIXO"],        14, "Depleção eletrolítica composta"),
    # Anemia
    (["HEMOGLOBINA:ABAIXO","FERRITIN:ABAIXO"],        10, "Anemia ferropriva confirmada"),
    (["HEMOGLOBINA:ABAIXO","LEUCOCIT:ACIMA"],         14, "Anemia + leucocitose (infecção?)"),
    (["HEMOGLOBINA:ABAIXO","PLAQUETA:ABAIXO"],        12, "Bi-citopenia (pancitopenia?)"),
    # Inflamação/infecção
    (["PCR:ACIMA",         "LEUCOCIT:ACIMA"],         14, "Resposta inflamatória/infecção sistêmica"),
    (["PCR:ACIMA",         "VHS:ACIMA"],               8, "Inflamação persistente"),
    # Tireoide + anemia
    (["TSH:ACIMA",         "HEMOGLOBINA:ABAIXO"],     10, "Hipotireoidismo + anemia"),
    # Hepático
    (["TGO:ACIMA",         "TGP:ACIMA"],              10, "Hepatite/lesão hepatocelular"),
    (["TGO:ACIMA",         "BILIRRUB:ACIMA"],         10, "Lesão hepática com colestase"),
    (["ALBUMINA:ABAIXO",   "TGO:ACIMA"],              12, "Insuficiência hepática"),
    # DRC avançada
    (["CREATININA:ACIMA",  "HEMOGLOBINA:ABAIXO"],     14, "DRC + anemia da doença crônica"),
    (["CREATININA:ACIMA",  "PARATORMONIO:ACIMA"],     12, "DRC + hiperparatireoidismo secundário"),
]

def _padroes_bonus(ultimos: dict) -> tuple:
    """Computa bônus sinérgico e lista de padrões detectados."""
    # Monta mapa: {fragment_ascii → ACIMA|ABAIXO} para todos analitos alterados
    pat_map: dict[str, str] = {}
    for key, reg in ultimos.items():
        st = str(reg[2]).upper()
        if "ALTERADO" not in st:
            continue
        a = _ascii(key)
        if "ACIMA"  in st: pat_map[a] = "ACIMA"
        elif "ABAIXO" in st: pat_map[a] = "ABAIXO"

    bonus = 0.0
    padroes_det = []
    for reqs, val, desc in _PADROES_SINERGICOS:
        ok = True
        for item in reqs:
            frag, direcao = item.rsplit(":", 1)
            frag_a = _ascii(frag)
            if not any(frag_a in k and pat_map[k] == direcao for k in pat_map):
                ok = False
                break
        if ok:
            bonus += val
            padroes_det.append(desc)
    return min(bonus, 60.0), padroes_det


def _comp_cronicas(n: int) -> float:
    """Componente de contexto clínico — progressão não-linear com nº de condições."""
    if n == 0: return 0.0
    if n == 1: return 5.0
    if n == 2: return 12.0
    if n == 3: return 20.0
    if n == 4: return 28.0
    return 35.0   # ≥5 condições — polimorbidade complexa


def _comp_tfg_bonus(tfg: float | None) -> float:
    """Bônus adicional por estadiamento da TFG (além do peso da creatinina)."""
    if tfg is None: return 0.0
    if tfg < 15:  return 22.0   # G5 — falência renal
    if tfg < 30:  return 14.0   # G4 — redução grave
    if tfg < 45:  return  7.0   # G3b
    return 0.0                   # G1-G3a — peso da creatinina já representa

# ── Pesos direcionados (ACIMA vs ABAIXO têm relevância clínica distinta) ──────
# Formato: ([keywords_ascii], peso_acima, peso_abaixo)
_PESOS_DIRECAO = [
    # Emergencial
    (["TROPONINA"],                        40,  5),
    (["BNP","PRO-BNP"],                    30,  5),
    # Eletrólitos críticos
    (["POTASSIO"],                         22, 20),   # hiper/hipocalemia ambas graves
    (["SODIO"],                            17, 15),
    (["CALCIO"],                           13, 12),
    (["MAGNESIO"],                          9,  8),
    (["PARATORMONIO","PTH"],               10, 10),
    # Renal
    (["CREATININA"],                       26,  3),   # alto=uremia; baixo=sarcopenia/benigno
    (["UREIA"],                            14,  2),
    (["MICROALBUMINA"],                    12,  0),
    # Glicemia / DM
    (["HBA1C","HEMOGLOBINA GLICADA"],      22,  2),   # alto=DM descontrolado; baixo=benigno
    (["GLICOSE","GLICEMIA"],               16,  8),   # hiperglicemia>hipoglicemia na APS
    # Hematológico
    (["HEMOGLOBINA"],                       4, 16),   # anemia (ABAIXO) >> policitemia
    (["PLAQUETA"],                         12, 14),
    (["LEUCOCIT"],                          9,  8),
    (["RDW"],                               7,  2),   # alto RDW = anisocitose
    (["VCM","HCM","CHCM"],                  3,  5),   # microcítico/hipocrômico
    # Inflamatório
    (["PCR","PROTEINA C"],                 14,  0),
    (["VHS"],                               8,  0),
    # Lipídeos
    (["LDL"],                              14,  1),
    (["HDL"],                               2, 11),   # baixo HDL = risco CV
    (["TRIGLICERID"],                       9,  1),
    (["COLESTEROL"],                        7,  1),
    # Tireoide
    (["TSH"],                              12, 10),
    (["TIROXINA","TRIIODO","T4","T3"],       8,  8),
    # Hepático
    (["TGO","AST","TGP","ALT"],            12,  1),
    (["GGT","GAMAGTL"],                     9,  1),
    (["BILIRRUB"],                          9,  0),
    (["ALBUMINA"],                          2, 10),   # baixo=hipoalbuminemia
    (["FOSFATASE"],                         6,  1),
    # Outros metabólicos
    (["ACIDO URICO"],                      10,  1),
    (["CORTISOL"],                         10,  7),
    (["FERRITIN","FERRO SERIC","FERRO SER"], 2, 10),
    (["TRANSFERRIN"],                        2,  7),
    (["VITAMINA"],                           2,  7),
    (["PSA"],                              12,  0),
    (["PROLACTINA"],                        7,  3),
    (["TESTOSTERONA","ESTRADIOL"],           5,  4),
    (["FSH","LH"],                          5,  4),
    (["AMILASE","LIPASE"],                   5,  4),
    (["CPK","CREATINOQUINAS"],              5,  1),
]

# Cap de contribuição por grupo — evita que hemograma sozinho domine o score
_CAP_GRUPO = {
    "hematologico": 32,
    "metabolico":   55,
    "renal":        62,
    "eletrolitico": 56,
    "inflamatorio": 28,
}

def _peso_v2(key: str, status: str) -> float:
    """Peso clínico direcionado: distingue excesso (ACIMA) de deficiência (ABAIXO)."""
    a_key    = _ascii(key)
    acima    = "ACIMA"  in str(status).upper()
    abaixo   = "ABAIXO" in str(status).upper()
    for kws, w_ac, w_ab in _PESOS_DIRECAO:
        if any(_ascii(k) in a_key for k in kws):
            if acima:  return float(w_ac)
            if abaixo: return float(w_ab)
            return float((w_ac + w_ab) / 2)   # direção não especificada
    return 5.0 if (acima or abaixo) else 4.0

def _chave_base(key: str) -> str:
    """Remove sufixo (%) / (abs) para deduplicação de sub-componentes do hemograma."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', key).strip()

# ── SQL helper ────────────────────────────────────────────────────────────────
def _q(sql: str, p: tuple = ()) -> list:
    """Executa query no banco corrente do contexto (thread/async safe)."""
    path = _CTX_DB.get()
    if not os.path.exists(path):
        return []
    try:
        with sqlite3.connect(path, timeout=10) as c:
            return c.execute(sql, p).fetchall()
    except Exception:
        return []

# ── IPL por paciente ──────────────────────────────────────────────────────────
def _ipl_paciente(pac_id: int, nome: str, dt_nasc: str, medico: str) -> dict | None:
    exames = _q("""
        SELECT analito, valor, status,
               COALESCE(data_exame, SUBSTR(registrado_em,1,10)) as data_ref,
               unidade, referencia
        FROM exames WHERE paciente_id=?
        ORDER BY data_ref ASC
    """, (pac_id,))
    if not exames:
        return None

    # Agrupa por analito normalizado — 6-tupla (analito, valor, status, dt, unidade, ref)
    por_analito: dict = defaultdict(list)
    for row in exames:
        analito, valor, status, dt = row[0], row[1], row[2], row[3]
        uni  = row[4] if len(row) > 4 else ""
        ref  = row[5] if len(row) > 5 else ""
        key = _norm(analito)
        if key:
            por_analito[key].append((analito, valor, status, dt or "", uni or "", ref or ""))
    if not por_analito:
        return None

    ultimos = {key: lista[-1] for key, lista in por_analito.items()}
    datas = sorted({e[3][:10] for e in exames if e[3]})
    ultima_dt = datas[-1] if datas else None
    dias_coleta = (date.today() - datetime.strptime(ultima_dt, "%Y-%m-%d").date()).days if ultima_dt else 9999

    # ── Score base com pesos direcionados + deduplicação ─────────────────────
    score_base   = 0.0
    analitos_alt = []
    grupos_alt:  set  = set()
    bases_vistas: set = set()   # dedup: sub-componentes (%) / (abs) do hemograma
    hba1c_contado = False       # dedup: GME derivado de HbA1c

    acum_grupo: dict = defaultdict(float)   # acumulador por grupo para cap

    for key, registro in ultimos.items():
        status = registro[2]
        if "ALTERADO" not in str(status).upper():
            continue

        # Dedup 1 — GME: pular se HbA1c já foi contado
        if _ascii("GLICOSE MEDIA ESTIMADA") in _ascii(key) and hba1c_contado:
            continue

        # Dedup 2 — sub-componentes hemograma: (%) pula se (abs) já contado para a mesma base
        base = _chave_base(key)
        base_abs = base + " (ABS)"
        if key.endswith("(%)") and base_abs in bases_vistas:
            continue
        # Se existe a versão (abs) no ultimos, preferir ela e pular a base simples
        if not key.endswith("(ABS)") and not key.endswith("(%)") and (base + " (ABS)") in {k for k in ultimos}:
            continue

        bases_vistas.add(key)
        if "HBA1C" in _ascii(key) or "HEMOGLOBINA GLICADA" in _ascii(key).replace(" ",""):
            hba1c_contado = True

        # Peso direcional × fator de magnitude (severidade do desvio)
        p_dir = _peso_v2(key, status)
        mag   = _magnitude_fator(registro[1], registro[5], status)
        p     = round(p_dir * mag, 1)

        g = _grupo(key)

        # Cap por grupo fisiológico
        cap = _CAP_GRUPO.get(g, 999)
        p_efetivo = min(p, cap - acum_grupo[g])
        if p_efetivo <= 0:
            continue
        acum_grupo[g] += p_efetivo

        score_base += p_efetivo
        analitos_alt.append((key, g, p_efetivo))
        grupos_alt.add(g)

    analitos_alt.sort(key=lambda x: x[2], reverse=True)
    analito_critico = analitos_alt[0][0].title() if analitos_alt else "—"
    grupo_critico   = analitos_alt[0][1]          if analitos_alt else "—"

    # ── Analitos alterados — detalhe para o frontend ─────────────────────────
    analitos_alterados_detail = []
    for key, g, peso in analitos_alt:
        r = por_analito[key][-1]
        analito_nome, valor, status = r[0], r[1], r[2]
        unidade    = r[4] if len(r) > 4 else ""
        referencia = r[5] if len(r) > 5 else ""
        direcao = ("ACIMA" if "ACIMA" in str(status).upper()
                   else "ABAIXO" if "ABAIXO" in str(status).upper() else "")
        # Limpeza do campo referencia (evita mostrar texto longo/corrompido)
        ref_display = referencia[:60] if referencia and len(referencia) <= 60 else ""
        analitos_alterados_detail.append({
            "nome":      analito_nome,
            "key":       key,
            "valor":     str(valor),
            "unidade":   unidade,
            "referencia":ref_display,
            "status":    status,
            "direcao":   direcao,
            "grupo":     g,
            "peso":      round(peso, 1),
        })

    # ── Padrões sinérgicos — substituem interações planas por combinações clínicas ──
    comp_int, padroes_detectados = _padroes_bonus(ultimos)

    # ── Faixa etária ─────────────────────────────────────────────────────────
    faixa, comp_etario = _faixa(dt_nasc)

    # ── Condições crônicas ───────────────────────────────────────────────────
    cronicas = _inferir_cronicas(por_analito)
    comp_ctx = _comp_cronicas(len(cronicas))

    # Detalhe: quais analitos dispararam cada condição (mesmas exclusões + direção)
    _EXCL_DET: dict = {
        "Anemia":      ["GLICADA", "HBA1C", "A1C"],
        "DM2":         ["HEMOGLOBINA GLICADA ESTIMADA"],
        "Hepatopatia": ["HEMOGLOBINA", "HEMATOCRIT"],
    }
    _DIR_DET: dict = {
        "DM2": "ACIMA", "Anemia": "ABAIXO", "DRC": "ACIMA",
        "Gota": "ACIMA", "Hepatopatia": "ACIMA", "ICC": "ACIMA",
    }
    cronicas_detail = []
    for cond, kws in _INFER_COND:
        if cond not in cronicas:
            continue
        excl    = _EXCL_DET.get(cond, [])
        dir_req = _DIR_DET.get(cond)
        analitos_cond = []
        for key, registros in por_analito.items():
            if excl and any(_contem(key, e) for e in excl):
                continue
            if any(_contem(key, k) for k in kws):
                r2 = registros[-1]; nome_db, valor, status = r2[0], r2[1], r2[2]
                st_up = str(status).upper()
                if "ALTERADO" not in st_up:
                    continue
                if dir_req and dir_req not in st_up:
                    continue
                direcao = "ACIMA" if "ACIMA" in st_up else "ABAIXO" if "ABAIXO" in st_up else ""
                analitos_cond.append({"nome": nome_db, "valor": str(valor), "direcao": direcao})
        cronicas_detail.append({"condicao": cond, "analitos": analitos_cond})

    # ── Tendência temporal ───────────────────────────────────────────────────
    por_data: dict = {}
    for d in datas:
        exs_d = [e for e in exames if e[3] and e[3][:10] == d]
        por_data[d] = sum(_peso_v2(_norm(e[0]), e[2]) for e in exs_d if "ALTERADO" in str(e[2]).upper())

    delta = vel = 0.0
    tend_dom = "SEM HISTÓRICO ANTERIOR"
    if len(datas) >= 2:
        d_ant, d_cur = datas[-2], datas[-1]
        dias_int = max((datetime.strptime(d_cur, "%Y-%m-%d").date() -
                        datetime.strptime(d_ant, "%Y-%m-%d").date()).days, 1)
        delta = por_data.get(d_cur, 0) - por_data.get(d_ant, 0)
        vel   = delta / dias_int
        if   vel > 0.15:  tend_dom = "PIORA GRAVE"
        elif vel > 0.08:  tend_dom = "PIORA MODERADA"
        elif vel > 0.02:  tend_dom = "PIORA LEVE"
        elif vel < -0.05: tend_dom = "MELHORA"
        else:             tend_dom = "ESTÁVEL"
    comp_tend = round(max(0.0, delta * 0.3), 1)

    # Piora persistente: ≥3 coletas com scores crescentes → amplifica penalidade
    if len(datas) >= 3:
        scores_seq = [por_data.get(d, 0) for d in datas[-3:]]
        if scores_seq[0] < scores_seq[1] < scores_seq[2]:
            comp_tend = round(comp_tend * 1.6, 1)
            if tend_dom not in ("PIORA GRAVE", "PIORA MODERADA"):
                tend_dom = "PIORA PROGRESSIVA"

    # ── Lacuna ───────────────────────────────────────────────────────────────
    if   dias_coleta > 365: comp_lacuna = 15.0; lacuna_gl = "LACUNA CRÍTICA"
    elif dias_coleta > 180: comp_lacuna = 10.0; lacuna_gl = "ATENÇÃO"
    elif dias_coleta > 90:  comp_lacuna =  5.0; lacuna_gl = "ATENÇÃO"
    else:                   comp_lacuna =  0.0; lacuna_gl = "ADEQUADA"

    # ── TFG CKD-EPI (calculada ANTES do IPL para ser incluída no score) ─────────
    tfg = tfg_est = None
    for key in por_analito:
        if "CREATININA" in key:
            try:
                v = float(str(por_analito[key][-1][1]).replace(",", "."))
                anos_pac = _anos(dt_nasc) if dt_nasc else 50
                r = v / 0.9
                tfg = round(142 * (r**-0.302 if r < 1 else r**-1.200) * (0.9938**anos_pac), 1)
                if   tfg >= 90: tfg_est = "G1 (normal ou elevada)"
                elif tfg >= 60: tfg_est = "G2 (levemente reduzida)"
                elif tfg >= 45: tfg_est = "G3a (redução leve-moderada)"
                elif tfg >= 30: tfg_est = "G3b (redução moderada-grave)"
                elif tfg >= 15: tfg_est = "G4 (redução grave)"
                else:           tfg_est = "G5 (falência renal)"
            except Exception:
                pass
            break

    comp_tfg = _comp_tfg_bonus(tfg)

    # ── IPL v3 — compressão exponencial ─────────────────────────────────────
    # Componentes aditivos (escala aberta):
    #   score_base  = soma ponderada dos analitos × fator de magnitude
    #   comp_int    = padrões sinérgicos clínicos (bônus combinatório)
    #   comp_etario = risco etário por decênio
    #   comp_tend   = penalidade por deterioração temporal
    #   comp_lacuna = penalidade por lacuna de coleta
    #   comp_ctx    = multimorbidade (não-linear)
    #   comp_tfg    = estadiamento renal G3b-G5
    #
    # Compressão: IPL = 100 × (1 − e^{−raw/90})
    #   Garante que scores brutos muito altos não colapcem no mesmo valor.
    #   Exemplos de mapeamento raw → IPL:
    #     raw=27  → IPL=26  (REVISÃO PROGRAMADA)
    #     raw=55  → IPL=46  (ACOMPANHAMENTO)
    #     raw=115 → IPL=72  (PRIORITÁRIA)
    #     raw=144 → IPL=80  |  raw=200 → IPL=89  |  raw=280 → IPL=95
    #
    _K = 90.0   # constante de escala — calibrada para P75 da base ≈ limiar PRIORITÁRIA
    ipl_raw = (score_base + comp_int + comp_etario
               + comp_tend + comp_lacuna + comp_ctx + comp_tfg)
    ipl = round(min(100.0, 100.0 * (1.0 - math.exp(-ipl_raw / _K))), 1)
    if   ipl >= 72: classif = "AVALIAÇÃO CLÍNICA PRIORITÁRIA"
    elif ipl >= 46: classif = "PRIORIDADE DE ACOMPANHAMENTO"
    elif ipl >= 24: classif = "REVISÃO PROGRAMADA"
    else:           classif = "SEGUIMENTO HABITUAL"

    # ── Gaps de cuidado ──────────────────────────────────────────────────────
    INTERVS_COND = {
        "DM2":                {"GLICOSE": 30, "HBA1C": 90, "HEMOGLOBINA GLICADA": 90},
        "DRC":                {"CREATININA": 30, "UREIA": 30},
        "DLP":                {"COLESTEROL": 180, "LDL": 180, "TRIGLICERID": 180},
        "ICC":                {"BNP": 60, "SODIO": 30},
        "Anemia":             {"HEMOGLOBINA": 90, "FERRITIN": 180},
        "Tireoidopatia":      {"TSH": 180, "T4": 365},
        "Hepatopatia":        {"TGO": 180, "TGP": 180},
        "Gota":               {"ACIDO URICO": 180},
        "Insuficiencia Adrenal": {"CORTISOL": 365},
    }
    gaps = []
    vistos: set = set()
    for cond in cronicas:
        for ak, intervalo in INTERVS_COND.get(cond, {}).items():
            if ak in vistos:
                continue
            ult_an = None
            for key in por_analito:
                if _contem(key, ak):   # insensível a acentos
                    ult_an = por_analito[key][-1][3]
                    break
            dias_an = None
            if ult_an:
                try:
                    dias_an = (date.today() - datetime.strptime(ult_an[:10], "%Y-%m-%d").date()).days
                except Exception:
                    pass
            if dias_an is None or dias_an > intervalo:
                gaps.append({
                    "analyte":  ak.lower(),
                    "label":    ak.title(),
                    "tipo":     "EXAME AUSENTE PARA CONDIÇÃO CRÔNICA",
                    "dias":     dias_an,
                    "intervalo": intervalo,
                    "condicao": cond,
                    "just":     f"{ak.title()}: {'?d' if dias_an is None else str(dias_an)+'d'} sem coleta "
                                f"(intervalo: {intervalo}d) — essencial para {cond}.",
                })
                vistos.add(ak)

    if   not gaps:        lacuna_an = "ADEQUADA"
    elif len(gaps) >= 4:  lacuna_an = "LACUNA CRÍTICA"
    else:                 lacuna_an = "ATENÇÃO"

    # ── Tendências por grupo ─────────────────────────────────────────────────
    d_ant2 = datas[-2] if len(datas) >= 2 else None
    d_cur2 = datas[-1] if datas else None
    dias_int2 = None
    if d_ant2 and d_cur2:
        dias_int2 = max((datetime.strptime(d_cur2, "%Y-%m-%d").date() -
                         datetime.strptime(d_ant2, "%Y-%m-%d").date()).days, 1)

    tendencias = []
    for grp in ["hematologico", "renal", "eletrolitico", "inflamatorio", "metabolico"]:
        s_ant_g = s_cur_g = 0.0
        for row in exames:
            a, st, dt = row[0], row[2], row[3]
            if not dt: continue
            key = _norm(a)
            if _grupo(key) != grp: continue
            w = _peso_v2(key, st) if "ALTERADO" in str(st).upper() else 0.0
            if d_ant2 and dt[:10] == d_ant2: s_ant_g += w
            if d_cur2 and dt[:10] == d_cur2: s_cur_g += w
        delta_g = s_cur_g - s_ant_g
        vel_g   = delta_g / dias_int2 if dias_int2 else 0.0
        if   not d_ant2:    tend_g = "SEM HISTÓRICO ANTERIOR"
        elif vel_g > 0.15:  tend_g = "PIORA GRAVE"
        elif vel_g > 0.08:  tend_g = "PIORA MODERADA"
        elif vel_g > 0.02:  tend_g = "PIORA LEVE"
        elif vel_g < -0.05: tend_g = "MELHORA"
        else:               tend_g = "ESTÁVEL"
        tendencias.append({"grupo": grp, "delta": round(delta_g, 1), "vel": round(vel_g, 3) if d_ant2 else None,
                           "tend": tend_g, "s_ant": round(s_ant_g, 1), "s_cur": round(s_cur_g, 1), "dias": dias_int2})

    # ── Histórico de coletas ─────────────────────────────────────────────────
    historico = []
    for d in datas:
        exs_d = [e for e in exames if e[3] and e[3][:10] == d]
        s_d = min(sum(_peso_v2(_norm(e[0]), e[2]) for e in exs_d if "ALTERADO" in str(e[2]).upper()), 100.0)
        sub = {g: round(sum(_peso_v2(_norm(e[0]), e[2]) for e in exs_d
                        if "ALTERADO" in str(e[2]).upper() and _grupo(_norm(e[0])) == g), 1)
               for g in ["hematologico", "renal", "eletrolitico", "inflamatorio", "metabolico"]}
        if   s_d >= 70: cls_d = "AVALIAÇÃO CLÍNICA PRIORITÁRIA"
        elif s_d >= 45: cls_d = "PRIORIDADE DE ACOMPANHAMENTO"
        elif s_d >= 25: cls_d = "REVISÃO PROGRAMADA"
        else:           cls_d = "SEGUIMENTO HABITUAL"
        historico.append({"data": d, "score": round(s_d, 1), "classif": cls_d,
                          "ctx": "coleta laboratorial", "sub": sub})

    ma_num = (abs(hash(medico or nome)) % 5) + 1
    return {
        "id":               f"PAC_{pac_id:04d}",
        "nome":             nome,
        "dt_nasc":          dt_nasc or "",
        "faixa":            faixa,
        "sexo":             "?",
        "ma":               f"MA-{ma_num:02d}",
        "acs":              f"ACS_{(pac_id % 10) + 1:02d}",
        "cronicas":              cronicas,
        "cronicas_detail":       cronicas_detail,
        "analitos_alterados":    analitos_alterados_detail,
        "ipl":              ipl,
        "classif":          classif,
        "fator_dom":        "score_laboratorial_base",
        "analito_critico":  analito_critico,
        "grupo_critico":    grupo_critico,
        "tendencia_dom":    tend_dom,
        "lacuna_global":    lacuna_gl,
        "dias_coleta":      dias_coleta if dias_coleta < 9000 else None,
        "lacuna_analitica": lacuna_an,
        "n_gaps":           len(gaps),
        "tfg":              tfg,
        "tfg_estadio":      tfg_est,
        "gaps":             gaps,
        "componentes": [
            {"nome": "score_laboratorial_base",    "contribuicao": round(score_base,  1), "desc": "Pontuação ponderada dos analitos alterados (×fator de magnitude)"},
            {"nome": "padroes_sinergicos",         "contribuicao": round(comp_int,    1), "desc": f"Padrões clínicos detectados: {', '.join(padroes_detectados) or '—'}"},
            {"nome": "faixa_etaria",               "contribuicao": round(comp_etario, 1), "desc": "Componente etário por decênio"},
            {"nome": "tendencia_temporal",         "contribuicao": round(comp_tend,   1), "desc": "Penalidade por velocidade/persistência de deterioração"},
            {"nome": "lacuna_coleta",              "contribuicao": round(comp_lacuna, 1), "desc": "Penalidade por lacuna de coleta"},
            {"nome": "contexto_clinico",           "contribuicao": round(comp_ctx,    1), "desc": "Multimorbidade (progressão não-linear)"},
            {"nome": "estadio_renal",              "contribuicao": round(comp_tfg,    1), "desc": "Bônus por estadio G3b-G5 da TFGe"},
        ],
        "padroes_detectados": padroes_detectados,
        "tendencias": tendencias,
        "historico":  historico,
    }


def calcular_territorio(db_path: str = None) -> dict:
    """Retorna estrutura completa do território para o frontend HTML.

    Args:
        db_path: caminho do banco SQLite da USF. Se None usa DB_PATH global.
                 Thread/async-safe: cada chamada tem seu próprio contexto.
    """
    token = _CTX_DB.set(db_path or DB_PATH)
    try:
        return _calcular_territorio_impl()
    finally:
        _CTX_DB.reset(token)


def _calcular_territorio_impl() -> dict:
    pacs = _q("SELECT id, nome, dt_nasc, medico FROM pacientes ORDER BY nome")

    pacientes = []
    for pac_id, nome, dt_nasc, medico in pacs:
        p = _ipl_paciente(pac_id, nome or f"PAC_{pac_id}", dt_nasc, medico)
        if p:
            pacientes.append(p)
    pacientes.sort(key=lambda x: x["ipl"], reverse=True)

    # ── Vigilância analítica ──────────────────────────────────────────────────
    # Usa o exame mais recente por data_exame (não por id de inserção)
    rows = _q("""
        SELECT e.analito, e.status, e.paciente_id
        FROM exames e
        WHERE e.id IN (
            SELECT id FROM exames e2
            WHERE e2.paciente_id = e.paciente_id
              AND e2.analito     = e.analito
            ORDER BY COALESCE(e2.data_exame, e2.registrado_em) DESC
            LIMIT 1
        )
    """)
    agg: dict = defaultdict(lambda: {"pacs": set(), "alt": set(), "grupo": "", "label": ""})
    for analito, status, pac_id in rows:
        key = _norm(analito)
        if not key:
            continue
        agg[key]["pacs"].add(pac_id)
        if "ALTERADO" in str(status).upper():
            agg[key]["alt"].add(pac_id)
        agg[key]["grupo"] = _grupo(key)
        agg[key]["label"] = key.title()

    total_pacs = len(pacientes)
    # Mínimo estatístico: pelo menos 5% da base ou 20 pacientes (o maior)
    min_n = max(20, round(total_pacs * 0.05))

    vigilancia = []
    for key, v in agg.items():
        n = len(v["pacs"]); alt = len(v["alt"])
        # Exclui analitos com cobertura insuficiente para vigilância territorial
        if n < min_n:
            continue
        prev = round(100 * alt / n, 1)
        if   prev > 75: padrao = "PADRÃO TERRITORIAL MUITO ELEVADO"
        elif prev > 50: padrao = "CRÍTICO"
        elif prev > 25: padrao = "PREVALENTE"
        elif prev > 0:  padrao = "ATENÇÃO DIFUSA"
        else:           padrao = "NEGLIGENCIÁVEL"
        vigilancia.append({"analyte": key.lower(), "label": v["label"], "group": v["grupo"],
                           "n": n, "alt": alt, "prev": prev, "min_n": min_n,
                           "sev": {"leve": 0, "moderada": alt, "grave": 0}, "padrao": padrao})
    vigilancia.sort(key=lambda x: (-x["prev"], -x["alt"]))

    return {"id": "UBS_CENTRAL", "pacientes": pacientes, "vigilancia": vigilancia[:25]}
