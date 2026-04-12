"""
Utilitários de validação e limpeza de analitos.
Módulo isolado — sem dependências de e-mail ou interação com o usuário.
"""

import re
import os
import sqlite3
from typing import Dict

DB_PATH = "exames.db"


# ──────────────────────────────────────────────────────────────
# VALIDADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────

def e_nome_exame_valido(linha: str) -> bool:
    """
    Retorna True somente se a string parecer um nome de analito legítimo.
    Rejeita: faixas de referência embutidas, valores numéricos colados,
    linhas de cabeçalho/rodapé, texto livre, metadados de laudo, etc.
    """
    s = linha.strip()

    # Comprimento fora de faixa
    if len(s) < 3 or len(s) > 90:
        return False

    # Começa com dígito
    if re.match(r"^\d", s):
        return False

    # Só separadores
    if re.match(r"^[\.\:\-\=\*\_\+\s]+$", s):
        return False

    # Excesso de espaços (texto corrido)
    if s.count(" ") > 12:
        return False

    # ── Padrões estruturais de ruído ────────────────────────────────

    # Pontilhado + ":" = linha de laudo  "CHCM.....: 33.8"
    if re.search(r"\.{3,}\s*:", s):
        return False

    # "Analito : número" = valor embutido no nome
    if re.search(r":\s+[\d<>]", s):
        return False

    # Unidades de medida embutidas no nome
    if re.search(
        r"\b(mg/dL|g/dL|g/L|pg/mL|ng/mL|mUI/mL|mUI/L|nmol/L|µmol/L|"
        r"U/L|uI/mL|mmol/L|mEq/L|g%|fL|mm³|/mm3|/uL|µL|cm|kg|IU/mL)\b",
        s, re.IGNORECASE
    ):
        return False

    # Faixa de referência embutida: "De X a Y", "Até X", "ate X"
    if re.search(r"\bDe\s+[\d<>]|\bAté\s+\d|\bate\s+\d", s, re.IGNORECASE):
        return False

    # Número no final (valor colado): "CREATININA 0.8", "SODIO 139"
    if re.search(r"\s+\d+[,.]?\d*\s*$", s):
        return False

    # Dois ou mais números distintos no nome: "SODIO 139 144"
    if len(re.findall(r"\b\d+[,.]?\d*\b", s)) >= 2:
        return False

    # Sinal de "+" qualitativo colado (urina): "HEMOGLOBINA 1+", "GLICOSE 3+ Ausentes"
    if re.search(r"\b\d\+", s):
        return False

    # Qualitativo isolado após nome: "PROTEINAS Ausentes", "UREIA Negativo"
    if re.match(
        r"^[\w\s\-/()]+\s+(Ausentes?|Reagente|N[eé]gativo|Positivo|Presente)\s*$",
        s, re.IGNORECASE
    ):
        return False

    # ── Termos de contexto / texto livre ───────────────────────────

    _TERMOS = {
        # Cabeçalhos de laudo
        "VALORES", "RESULTADO", "AUTENTICIDADE", "EVOLUÇÃO", "REFERÊNCIA",
        "UNIDADE", "MÉTODO", "MATERIAL", "LAUDO", "PÁGINA", "LABORATÓRIO",
        "PREFEITURA", "MUNICIPAL", "DIETA", "ASSOCIAÇÃO",
        "REQUER", "CORRELAÇÃO", "DADOS CLÍNICOS", "EPIDEMIOLÓGICOS",
        "LIBERADO", "RESPONSÁVEL", "EXAMES COLETADOS", "ANÁLISE",
        "ERITROGRAMA", "LEUCOGRAMA", "PEDIDO", "CPF", "SOLICITANTE",
        "DESTINO", "ORIGEM", "EMISSÃO", "CNES", "GRAVIDAS", "GRÁVIDAS",
        "DATA", "NOTAS", "FL.:", "TRIMESTRE",
        # Faixas etárias / contextuais capturadas como analito
        "ANOS", "ADULTOS", "CRIANÇAS", "GESTANTES",
        # Gênero como linha solta
        "MULHERES:", "HOMENS:", "MULHERES.", "HOMENS.",
        # Texto de laudo de cultura/parasitológico
        "NÃO FORAM ENCONTRADOS", "HOUVE CRESCIMENTO",
        "LEUCOCITOSE", "CONSISTENTE COM",
        # Metadados de laudo
        "METODO :", "METODOLOGIA :", "INTERPRETAÇÃO:", "R E S U L T A D O",
        "NORMATIZAÇÃO", "LABORATORIAL DO PERFIL",
        "VIGILÂNCIA EPIDEMIOLÓGICA", "ADOLFO LUTZ",
        "INSTITUTO ", "CARE.", "PSA LIVRE/PSA TOTAL",
        # Linhas de cabeçalho/nota
        "RELAÇÃO PACIENTE", "PLASMA DO PACIENTE", "ATIVIDADE DE PROTR",
        "CUTOFF DA REAÇÃO", "DENSIDADE ÓTICA", "INSUFICIÊNCIA",
        "SATURAÇÃO", "RISCO ELEVADO", "RISCO MODERADO",
        "PÓS MENOPAUSA", "IDADE REPRODUTIVA", "MEIO CICLO",
        "SUGEREM:", "INVALID", "BARCODE",
    }

    s_upper = s.upper()
    if any(t in s_upper for t in _TERMOS):
        return False

    # Reference-range descriptor lines stored as analyte names
    if re.match(r"^Normal\s*[:\-]", s, re.IGNORECASE):
        return False
    if re.match(r"^(Desejável|Desejavel|Limítrofe|Limitrofe|Risco\s)", s, re.IGNORECASE):
        return False

    # Fases hormonais
    if re.search(r"\bFase\s+(Fol|L[uú]t|Ovu)", s, re.IGNORECASE):
        return False

    # "Mulheres" / "Homens" como linha isolada ou com faixa etária
    if re.match(r"^(Mulheres?|Homens?)\s*[:\.\-]?\s*$", s, re.IGNORECASE):
        return False
    if re.search(r"^(Mulheres?|Homens?)\s+(adultas?|acima|>|\d)", s,
                 re.IGNORECASE):
        return False

    # Linha inteira em formato "Nome : PACIENTE ..."
    if re.match(r"^Nome\s*:", s, re.IGNORECASE):
        return False

    # Sub-resultado com qualitativo duplicado: "Ausente Ausente"
    if re.search(
        r"\b(Ausentes?|Reagente|Negativo|Positivo|Presente)\s+"
        r"(Ausentes?|Reagente|Negativo|Positivo|Presente|\d)",
        s, re.IGNORECASE
    ):
        return False

    return True


# ── Observações morfológicas (não são analitos mensuráveis) ────────────────

_OBS = {
    "MICROCITOSE", "MACROCITOSE", "ANISOCITOSE", "POIQUILOCITOSE",
    "HIPOCROMIA", "POLICROMASIA", "DISCRETA", "MODERADA", "ACENTUADA",
    "LEVE", "INTENSA", "OCASIONAL", "RAROS", "NUMEROSOS",
    "VALORES DE", "SÉRIE BRANCA", "SÉRIE VERMELHA",
}

def e_analito_observacao(linha: str) -> bool:
    u = linha.upper().strip()
    return any(o in u for o in _OBS)


# ──────────────────────────────────────────────────────────────
# LIMPEZA RETROATIVA DO BANCO
# ──────────────────────────────────────────────────────────────

def limpar_analitos_banco(dry_run: bool = True) -> Dict:
    """
    Varre todos os analitos do banco e remove (ou lista, se dry_run=True)
    os registros cujo nome de analito não passa pelo validador.

    Retorna dict com:
      total_antes        : total de exames antes da operação
      invalidos          : exames a remover / removidos
      analitos_invalidos : quantidade de tipos de analito inválidos
      amostras           : até 30 exemplos de analitos removidos
      total_depois       : total após remoção
      dry_run            : bool
    """
    if not os.path.exists(DB_PATH):
        return {"erro": f"Banco '{DB_PATH}' não encontrado."}

    with sqlite3.connect(DB_PATH) as conn:
        total_antes = conn.execute("SELECT COUNT(*) FROM exames").fetchone()[0]
        analitos_db = [r[0] for r in
                       conn.execute("SELECT DISTINCT analito FROM exames")]

    # Classifica
    invalidos_set = {a for a in analitos_db if not e_nome_exame_valido(a)}
    amostras = sorted(invalidos_set)[:30]

    if dry_run:
        invalidos_count = 0
        if invalidos_set:
            with sqlite3.connect(DB_PATH) as conn:
                ph = ",".join("?" * len(invalidos_set))
                invalidos_count = conn.execute(
                    f"SELECT COUNT(*) FROM exames WHERE analito IN ({ph})",
                    list(invalidos_set)
                ).fetchone()[0]
        return {
            "total_antes": total_antes,
            "invalidos":   invalidos_count,
            "analitos_invalidos": len(invalidos_set),
            "amostras":    amostras,
            "total_depois": total_antes,
            "dry_run": True,
        }

    # Remoção em lotes (SQLite suporta até ~999 parâmetros por query)
    removidos = 0
    BATCH = 200
    lista = list(invalidos_set)
    for i in range(0, len(lista), BATCH):
        lote = lista[i:i + BATCH]
        ph = ",".join("?" * len(lote))
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.execute(
                f"DELETE FROM exames WHERE analito IN ({ph})", lote)
            removidos += c.rowcount

    # Remove processamentos sem exames vinculados
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            DELETE FROM processamentos
            WHERE id NOT IN (
                SELECT DISTINCT processamento_id FROM exames
                WHERE processamento_id IS NOT NULL
            )
        """)
        total_depois = conn.execute("SELECT COUNT(*) FROM exames").fetchone()[0]

    return {
        "total_antes":  total_antes,
        "invalidos":    removidos,
        "analitos_invalidos": len(invalidos_set),
        "amostras":     amostras,
        "total_depois": total_depois,
        "dry_run": False,
    }


def _to_float_correto(x: str):
    """Versão corrigida de _to_float que trata ponto como decimal, não separador de milhar."""
    try:
        s = x.strip()
        if "," in s and "." in s:
            if s.rindex(",") > s.rindex("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        elif "." in s:
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                s = s.replace(".", "")
        return float(s)
    except Exception:
        return None


def _parse_ref_correta(referencia_txt: str):
    """Re-parse referencia text using the fixed _to_float."""
    if not referencia_txt:
        return None, None
    import re
    rt = re.sub(r"\s+", " ", referencia_txt).strip()
    # Range: X a Y / X - Y
    m = re.search(r"([\d\.,]+)\s*(?:a|até|ate|-)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v1 = _to_float_correto(m.group(1))
        v2 = _to_float_correto(m.group(2))
        if v1 is not None and v2 is not None:
            return min(v1, v2), max(v1, v2)
    # até X / inferior a X
    m = re.search(r"(?:até|ate|inferior a|menor que|normal até|<)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float_correto(m.group(1))
        if v is not None:
            return None, v
    # maior que X / superior a X
    m = re.search(r"(?:maior que|superior a|>)\s*([\d\.,]+)", rt, re.IGNORECASE)
    if m:
        v = _to_float_correto(m.group(1))
        if v is not None:
            return v, None
    return None, None


def _determinar_status_correto(valor_float, ref_inf, ref_sup) -> str:
    if ref_inf is not None and ref_sup is not None:
        if valor_float < ref_inf:
            return "[ALTERADO] ABAIXO"
        if valor_float > ref_sup:
            return "[ALTERADO] ACIMA"
        return "NORMAL"
    if ref_sup is not None:
        return "NORMAL" if valor_float <= ref_sup else "[ALTERADO] ACIMA"
    if ref_inf is not None:
        return "NORMAL" if valor_float >= ref_inf else "[ALTERADO] ABAIXO"
    return "REVISAR"


def recalcular_status_por_referencia(dry_run: bool = True) -> Dict:
    """
    Re-parses stored referencia text for all records using the corrected _to_float
    (which treats dot as decimal separator, not thousands separator).
    Updates status where the re-parsed classification differs from stored status.
    """
    if not os.path.exists(DB_PATH):
        return {"erro": f"Banco '{DB_PATH}' não encontrado."}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, analito, valor, status, referencia
            FROM exames
            WHERE referencia IS NOT NULL AND referencia != ''
              AND valor IS NOT NULL AND valor != ''
              AND status IN ('[ALTERADO] ABAIXO', '[ALTERADO] ACIMA', 'NORMAL')
        """).fetchall()

    to_update = []
    amostras = []
    for row in rows:
        try:
            valor_f = float(str(row["valor"]).replace(",", "."))
        except (ValueError, TypeError):
            continue

        # Skip corrupted references (scientific notation = parsing artifact)
        if re.search(r"e[+\-]\d{2,}", row["referencia"], re.IGNORECASE):
            continue

        ref_inf, ref_sup = _parse_ref_correta(row["referencia"])
        if ref_inf is None and ref_sup is None:
            continue

        # Skip clearly corrupted references
        if ref_sup is not None and ref_sup > 10000:
            continue
        if ref_inf is not None and ref_inf > 10000:
            continue

        novo = _determinar_status_correto(valor_f, ref_inf, ref_sup)
        if novo != row["status"] and novo != "REVISAR":
            to_update.append((novo, row["id"]))
            if len(amostras) < 30:
                amostras.append({
                    "analito": row["analito"],
                    "valor": valor_f,
                    "status_antigo": row["status"],
                    "status_novo": novo,
                    "referencia": row["referencia"],
                    "ref_inf": ref_inf,
                    "ref_sup": ref_sup,
                })

    corrigidos = 0
    if not dry_run and to_update:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany("UPDATE exames SET status = ? WHERE id = ?", to_update)
        corrigidos = len(to_update)

    return {
        "corrigidos": len(to_update) if dry_run else corrigidos,
        "amostras": amostras,
        "dry_run": dry_run,
    }


def reclassificar_status_banco(dry_run: bool = True) -> Dict:
    """
    Re-classifica registros cujo status foi calculado a partir de referências
    claramente corrompidas (e.g. ref_inf > 30 para CREATININA, ou ref_sup < 25
    para COLESTEROL), usando GerenciadorReferencias como fonte autoritativa.

    Retorna dict com corrigidos, amostras, dry_run.
    """
    if not os.path.exists(DB_PATH):
        return {"erro": f"Banco '{DB_PATH}' não encontrado."}

    import unicodedata

    def _ascii_upper(s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').upper()

    try:
        from gerenciador_referencias import inicializar
        gerenciador_bruto = inicializar()
        _ref_db_path = getattr(gerenciador_bruto, 'db_path', None) or 'valores_referencia.db'
    except Exception as e:
        return {"erro": f"GerenciadorReferencias indisponível: {e}"}

    def _buscar_ref_direta(analito_nome: str, genero: str = None, idade: int = None):
        """Lookup direto com normalização de acentos, ignorando o bug do UPPER do SQLite.
        Requer que o nome do DB e o nome buscado sejam mutuamente parecidos (evita falsos positivos)."""
        nome_ascii = _ascii_upper(analito_nome)

        # Build search candidates: try first two words (sufficient for most lab names)
        words = nome_ascii.split()
        candidates = []
        if len(words) >= 2:
            candidates.append(f"{words[0]} {words[1]}")  # e.g. "T4 TOTAL", "TIROXINA LIVRE"
        candidates.append(words[0])  # first word only (fallback)
        # Extract parenthetical short name: "TIROXINA LIVRE (T4 LIVRE)" → "T4 LIVRE"
        m_paren = re.search(r'\(([^)]{3,})\)', analito_nome)
        if m_paren:
            paren_ascii = _ascii_upper(m_paren.group(1))
            paren_words = paren_ascii.split()
            if len(paren_words) >= 2:
                candidates.insert(0, f"{paren_words[0]} {paren_words[1]}")

        with sqlite3.connect(_ref_db_path) as c:
            c.create_function("ASCII_UPPER", 1, _ascii_upper)
            # Load all DB analyte names once
            all_db = c.execute(
                "SELECT nome_exame, valor_min, valor_max, unidade, referencia_texto, genero, idade_min, idade_max "
                "FROM valores_referencia WHERE ativo = 1"
            ).fetchall()

        # Match: DB name must share substantial overlap with search term
        def _match_quality(db_name: str, search_ascii: str) -> int:
            db_ascii = _ascii_upper(db_name)
            db_words = db_ascii.split()
            if not db_words:
                return 0
            shared = sum(1 for w in db_words if len(w) >= 3 and w in search_ascii)
            if shared == 0:
                return 0
            return shared

        found_rows = []
        best_quality = 0
        for row in all_db:
            q = _match_quality(row[0], nome_ascii)
            if q > best_quality:
                best_quality = q
                found_rows = [row]
            elif q == best_quality and q > 0:
                found_rows.append(row)

        if not found_rows or best_quality == 0:
            return None

        # Among matched rows, pick best gender/age fit
        best = None
        best_score = -1
        for row in found_rows:
            score = 0
            if genero and row[5] == genero:
                score += 2
            if idade is not None and row[6] is not None and row[7] is not None:
                if row[6] <= idade <= row[7]:
                    score += 2
            if row[6] is None and row[7] is None:
                score += 1
            if score > best_score:
                best_score = score
                best = row
        return best

    # Padrão de referências corrompidas: ref_inf e ref_sup parecem ser de outro exame
    # Detectamos pela comparação com o valor do analito (valores na faixa fisiológica
    # que caem fora de uma referência absurda para aquele analito)
    _FAIXAS_FISIOLOGICAS = {
        # analito_upper_ascii: (min_fisiologico, max_fisiologico)
        "CREATININA":        (0.3, 3.5),
        "COLESTEROL TOTAL":  (100.0, 350.0),
        "GLICOSE":           (60.0, 400.0),
        "UREIA":             (10.0, 180.0),
        "ACIDO URICO":       (1.5, 12.0),
        "A. URICO":          (1.5, 12.0),
        "TRIGLICERIDES":     (30.0, 500.0),
        "HDL":               (20.0, 120.0),
        "LDL":               (40.0, 300.0),
        "VLDL":              (5.0, 100.0),
        "SODIO":             (120.0, 160.0),
        "POTASSIO":          (2.5, 7.0),
        "TSH":               (0.05, 20.0),
        "T4 TOTAL":          (4.5, 20.0),
        "TIROXINA LIVRE":    (0.3, 3.0),
        "T4 LIVRE":          (0.3, 3.0),
        "T3 TOTAL":          (50.0, 250.0),
        "TETRAIODOTIRONINA": (4.5, 20.0),
    }

    corrigidos = 0
    amostras = []

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT e.id, e.analito, e.valor, e.status, e.referencia,
                   p.dt_nasc
            FROM exames e
            LEFT JOIN pacientes p ON e.paciente_id = p.id
            WHERE e.status IN ('[ALTERADO] ABAIXO', '[ALTERADO] ACIMA', 'NORMAL')
              AND e.valor IS NOT NULL AND e.valor != ''
              AND e.referencia IS NOT NULL AND e.referencia != ''
        """).fetchall()

    to_update = []
    for row in rows:
        analito_ascii = _ascii_upper(row["analito"])
        faixa = None
        for key, val in _FAIXAS_FISIOLOGICAS.items():
            if key in analito_ascii:
                faixa = val
                break
        if faixa is None:
            continue

        try:
            valor_f = float(str(row["valor"]).replace(",", "."))
        except (ValueError, TypeError):
            continue

        # Skip records with physiologically impossible values
        if not (faixa[0] <= valor_f <= faixa[1]):
            continue

        # Re-classify using direct DB lookup (bypasses SQLite UPPER accent bug)
        try:
            age = None
            if row["dt_nasc"]:
                import datetime
                try:
                    born = datetime.datetime.strptime(row["dt_nasc"], "%d/%m/%Y").date()
                    age = (datetime.date.today() - born).days // 365
                except Exception:
                    pass
            ref_row = _buscar_ref_direta(row["analito"], idade=age)
            if not ref_row:
                continue

            r_min = ref_row[1]  # valor_min
            r_max = ref_row[2]  # valor_max
            r_ref_txt = ref_row[4]  # referencia_texto

            novo_status_db = _determinar_status_correto(valor_f, r_min, r_max)
            if novo_status_db == "REVISAR":
                continue

            if novo_status_db != row["status"]:
                nova_ref = r_ref_txt or (f"{r_min} - {r_max}" if r_min and r_max else "")
                to_update.append((novo_status_db, nova_ref, row["id"]))
                if len(amostras) < 20:
                    amostras.append({
                        "id": row["id"],
                        "analito": row["analito"],
                        "valor": valor_f,
                        "status_antigo": row["status"],
                        "status_novo": novo_status_db,
                        "ref_antiga": row["referencia"],
                        "ref_nova": nova_ref,
                    })
        except Exception:
            continue

    if not dry_run and to_update:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(
                "UPDATE exames SET status = ?, referencia = ? WHERE id = ?",
                to_update
            )
        corrigidos = len(to_update)

    return {
        "corrigidos": len(to_update) if dry_run else corrigidos,
        "amostras": amostras,
        "dry_run": dry_run,
    }
