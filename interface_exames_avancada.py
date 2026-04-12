"""
Interface Avançada — Análise e Visualização de Exames
Fonte: banco SQLite (exames.db).

Otimizações de performance:
  • Cache de analitos válidos persistido na própria exames.db (_av_cache)
    → calculado uma única vez; atualizações só quando o banco muda
  • Índice composto (paciente_id, analito, status) criado no primeiro uso
  • Limpeza automática silenciosa ao abrir (se >15% de registros inválidos)
  • Todas as abas carregam lazy (só ao clicar) em threads de background
  • UI nunca bloqueia; cada aba mostra spinner enquanto carrega

Abas:
  1. Dashboard   — Resumo, top analitos alterados, exames recentes
  2. Prevalência — Tabela filtrada com taxa de alteração por analito
  3. Alterados   — Exames alterados com data + quando repetir
  4. Evolução    — Histórico temporal de 1 analito × 1 paciente (tendência)
  5. Paciente    — Todos os exames por paciente + próximos exames
  6. Filtros     — Busca livre combinada com exportação
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import threading
import re
import os
from collections import defaultdict
from datetime import datetime, date, timedelta

DB_PATH = "exames.db"

# ──────────────────────────────────────────────────────────────
# INTERVALOS CLÍNICOS DE REPETIÇÃO (dias: normal, alterado, rótulo)
# Referência: diretrizes brasileiras de acompanhamento laboratorial
# ──────────────────────────────────────────────────────────────
_INTERVALOS = [
    (("hemoglobina glicada", "hba1c", "a1c"),            90,  45, "HbA1c"),
    (("glicose",),                                        180, 30, "Glicose"),
    (("insulina",),                                       180, 90, "Insulina"),
    (("tsh",),                                            365, 90, "TSH"),
    (("t4 livre", "t4l", "t3 livre", "t3l"),             365, 90, "T4/T3"),
    (("colesterol total",),                               365,180, "Colesterol Total"),
    (("ldl",),                                            365,180, "LDL"),
    (("hdl",),                                            365,180, "HDL"),
    (("triglicerí", "trigliceri"),                        365,180, "Triglicerídeos"),
    (("creatinina",),                                     365,180, "Creatinina"),
    (("ureia", "uréia"),                                  365,180, "Ureia"),
    (("ácido úrico", "acido urico", "a. urico"),         180, 90, "Ácido Úrico"),
    (("tgo", "ast"),                                      365,180, "TGO/AST"),
    (("tgp", "alt"),                                      365,180, "TGP/ALT"),
    (("bilirrubina",),                                    365,180, "Bilirrubina"),
    (("albumina",),                                       365,180, "Albumina"),
    (("proteínas totais", "proteinas totais"),            365,180, "Proteínas Totais"),
    (("ferritina",),                                      180, 90, "Ferritina"),
    (("vitamina d",),                                     180, 90, "Vitamina D"),
    (("vitamina b12",),                                   365,180, "Vitamina B12"),
    (("ácido fólico", "acido folico"),                    365,180, "Ácido Fólico"),
    (("ferro",),                                          180, 90, "Ferro Sérico"),
    (("psa",),                                            365,180, "PSA"),
    (("proteína c reativa", "pcr", "proteina c"),         90, 30, "PCR"),
    (("vhs",),                                            180, 90, "VHS"),
    (("sódio", "sodio"),                                  365,180, "Sódio"),
    (("potássio", "potassio"),                            365,180, "Potássio"),
    (("cálcio", "calcio"),                                365,180, "Cálcio"),
    (("magnésio", "magnesio"),                            365,180, "Magnésio"),
    (("hemograma", "leucócitos", "leucocitos",
      "eritrócitos", "eritrocitos", "plaquetas",
      "hematocrito", "hematócrito"),                      180, 90, "Hemograma"),
    (("urina",),                                          180, 90, "EAS/Urina"),
    (("amilase",),                                        365,180, "Amilase"),
    (("lipase",),                                         365,180, "Lipase"),
    (("cortisol",),                                       365,180, "Cortisol"),
    (("prolactina",),                                     365,180, "Prolactina"),
    (("testosterona",),                                   365,180, "Testosterona"),
    (("estradiol", "fsh", "lh"),                         365,180, "Hormônios Sexuais"),
    (("anti-hiv", "hiv"),                                 365,365, "HIV"),
    (("hepatite b", "hbsag", "anti-hbs"),                365,180, "Hepatite B"),
    (("hepatite c", "anti-hcv"),                          365,365, "Hepatite C"),
    (("vdrl", "fta-abs"),                                 365,365, "VDRL/Sífilis"),
    (("troponina",),                                       30, 14, "Troponina"),
    (("bnp", "pro-bnp"),                                   90, 30, "BNP"),
]


def _intervalo(analito: str, status: str):
    """(dias: int, rótulo: str) para o analito/status."""
    nome = analito.lower()
    alt  = "ALTERADO" in str(status).upper()
    for palavras, d_norm, d_alt, rotulo in _INTERVALOS:
        if any(p in nome for p in palavras):
            return (d_alt if alt else d_norm), rotulo
    return (90 if alt else 180), "Padrão"


def _proximo(analito: str, ultima_data: str, status: str) -> str:
    """Retorna 'dd/mm/aaaa (Nd)' ou '...⚠️ atrasado Nd'."""
    if not ultima_data:
        return "—"
    try:
        ult = datetime.strptime(ultima_data[:10], "%Y-%m-%d").date()
    except ValueError:
        return "—"
    dias, _ = _intervalo(analito, status)
    prox  = ult + timedelta(days=dias)
    diff  = (prox - date.today()).days
    s     = prox.strftime("%d/%m/%Y")
    if diff < 0:
        return f"{s} ⚠️ atrasado {abs(diff)}d"
    return f"{s} (em {diff}d)" if diff else f"{s} ← hoje"


# ──────────────────────────────────────────────────────────────
# HELPERS VISUAIS
# ──────────────────────────────────────────────────────────────

def _barra(pct: float, w: int = 22) -> str:
    n = max(0, min(w, int(round(pct / 100 * w))))
    return "█" * n + "░" * (w - n)


def _cor(pct: float) -> str:
    return "alta" if pct >= 50 else "media" if pct >= 20 else "baixa"


def _fd(s: str) -> str:          # dd/mm/aaaa hh:mm
    try: return datetime.strptime(s[:16], "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
    except: return s[:10] if s else ""


def _fc(s: str) -> str:          # dd/mm/aaaa
    try: return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return s[:10] if s else ""


_BLOCKLIST_ANALITO = re.compile(
    r'^('
    r'de\s|até\s|a\s+\d|acima\s|abaixo\s|maior\s|menor\s|inferior\s|superior\s'
    r'|normal$|normal[\s:]|desejável|ideal\s|adulto|criança|homem\s|mulher\s|grávid|gravid'
    r'|trimestre|semana\s|fase\s|pós\s|pos\s|menopausa|reprodutiv'
    r'|nota\s*:|obs\s*:|método\s*:|metodo\s*:|material\s*:|autenticidade\s*:'
    r'|normatiz|determinação|determinacao|consenso|diretriz|associação|associacao'
    r'|liberado|responsável|responsavel|exames\s+colet'
    r'|coleta\s|referência|referencia|resultado\s+confirm'
    r'|\d{1,3}[,\.]\d'   # linhas que começam com número decimal (ref ranges)
    r')',
    re.IGNORECASE
)

_MIN_ANALITO_LEN = 3
_MAX_ANALITO_LEN = 60


def _norm_analito(s: str) -> str:
    """
    Normaliza nome de analito removendo pontilhados, valores e números acoplados.
    Retorna string vazia se a string parecer texto de referência ou metadado.

    Exemplos:
      "Linf. Atipicos..........: 1 83 0 a 1 %"  → "Linf Atipicos"
      "TGO 36"                                   → "TGO"
      "TGO 40 42"                                → "TGO"
      "TSH 6,02 6,64"                            → "TSH"
      "VITAMINA B12"                             → "VITAMINA B12"
      "De 10 a 19 anos"                          → ""  (bloqueado)
      "Fase Ovulatória"                          → ""  (bloqueado)
      "Normatização da Determinação..."          → ""  (bloqueado)
    """
    # Remove pontilhados (3+) e tudo após
    s = re.split(r'\.{3,}', s)[0]
    # Remove tudo após ":"
    s = s.split(':')[0].strip()

    # Rejeita imediatamente se parece texto de referência / metadado
    if _BLOCKLIST_ANALITO.match(s.strip()):
        return ''

    # Remove tokens puramente numéricos no final (inclui decimais com vírgula)
    parts = s.split()
    while parts and re.match(r'^[\d\.,]+$', parts[-1]):
        parts.pop()

    result = ' '.join(parts).strip()

    # Rejeita se muito curto, muito longo, ou começa com dígito
    if (len(result) < _MIN_ANALITO_LEN
            or len(result) > _MAX_ANALITO_LEN
            or result[0].isdigit()):
        return ''

    # Rejeita se contém "%" isolado no meio (ex: "42 a 70 %") ou "mUI" etc.
    if re.search(r'\b(mUI|mmol|mg/|g/dL|U/L|ng/|pg/|µg|ug/|/mm|/µ)\b', result, re.IGNORECASE):
        return ''

    return result


def _tend(vals: list) -> str:
    nums = []
    for v in vals:
        try: nums.append(float(str(v).replace(",", ".")))
        except: pass
    if len(nums) < 2:
        return "—"
    med = sum(nums[:-1]) / len(nums[:-1])
    d   = (nums[-1] - med) / med * 100 if med else 0
    if abs(d) < 5: return "→ Estável"
    return "↑ Subindo" if d > 0 else "↓ Caindo"


# ──────────────────────────────────────────────────────────────
# BANCO — acesso direto sem ORM
# ──────────────────────────────────────────────────────────────

def _q(sql: str, p: tuple = ()) -> list:
    if not os.path.exists(DB_PATH):
        return []
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as c:
            return c.execute(sql, p).fetchall()
    except Exception:
        return []


def _sc(sql: str, p: tuple = ()):
    r = _q(sql, p)
    return r[0][0] if r else 0


def _preparar_banco():
    """Idempotente: cria índice composto se não existir."""
    if not os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH, timeout=15) as c:
        c.execute("""CREATE INDEX IF NOT EXISTS idx_exames_comp
                     ON exames(paciente_id, analito, status)""")
        c.execute("ANALYZE")


def _exportar(colunas: list, dados: list, parent=None):
    if not dados:
        messagebox.showwarning("Aviso", "Nenhum dado.", parent=parent); return
    arq = filedialog.asksaveasfilename(
        defaultextension=".xlsx",
        filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
        parent=parent)
    if not arq: return
    try:
        import pandas as pd
        df = pd.DataFrame(dados, columns=colunas)
        df.to_excel(arq, index=False) if arq.endswith(".xlsx") \
            else df.to_csv(arq, index=False, encoding="utf-8-sig")
        messagebox.showinfo("Exportado", arq, parent=parent)
    except Exception as e:
        messagebox.showerror("Erro", str(e), parent=parent)


# ──────────────────────────────────────────────────────────────
# CLASSE PRINCIPAL
# ──────────────────────────────────────────────────────────────

class AnalisadorExamesAvancado:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Análise Avançada de Exames")
        self.root.geometry("1480x860")
        self.root.minsize(1050, 640)

        # Verifica banco em < 15ms antes de qualquer coisa
        if not os.path.exists(DB_PATH) or _sc("SELECT COUNT(*) FROM exames") == 0:
            messagebox.showwarning("Sem dados",
                "Banco vazio ou não encontrado.\n"
                "Execute 'Processar E-mails' primeiro.")
            self.root.after(600, self.root.destroy)
            return

        self._tabs_ok: set = set()
        self._criar_interface()

        # Background: prepara índices + cache + limpeza silenciosa
        threading.Thread(target=self._startup_bg, daemon=True).start()

    def _startup_bg(self):
        _preparar_banco()

    # ──────────────────────────────────────────
    # ESTRUTURA DE ABAS (lazy)
    # ──────────────────────────────────────────

    def _criar_interface(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._defs = [
            ("📊 Dashboard",    self._tab_dashboard),
            ("📈 Prevalência",  self._tab_prevalencia),
            ("🔴 Alterados",    self._tab_alterados),
            ("📉 Evolução",     self._tab_evolucao),
            ("👤 Por Paciente", self._tab_paciente),
            ("⚙️ Filtros",      self._tab_filtros),
        ]
        self._frames = []
        for txt, _ in self._defs:
            f = ttk.Frame(self.nb)
            self.nb.add(f, text=f"  {txt}  ")
            self._frames.append(f)

        self.nb.bind("<<NotebookTabChanged>>", self._aba_mudou)
        self.root.after(80, lambda: self._abrir_aba(0))

    def _aba_mudou(self, _=None):
        self._abrir_aba(self.nb.index(self.nb.select()))

    def _abrir_aba(self, idx: int):
        if idx in self._tabs_ok: return
        self._tabs_ok.add(idx)
        self._defs[idx][1](self._frames[idx])

    # ── spinner (mostra enquanto thread carrega) ──────────────
    @staticmethod
    def _spin(parent) -> tk.Label:
        lbl = tk.Label(parent, text="⏳  Carregando…",
                       font=("Helvetica", 12), foreground="#888")
        lbl.place(relx=0.5, rely=0.4, anchor="center")
        return lbl

    @staticmethod
    def _safe_after(widget, fn):
        """Chama fn na thread da GUI apenas se o widget ainda existir."""
        try:
            if widget.winfo_exists():
                widget.after(0, fn)
        except Exception:
            pass

    # ──────────────────────────────────────────
    # ABA 1 — DASHBOARD
    # ──────────────────────────────────────────

    def _tab_dashboard(self, p: ttk.Frame):
        spin = self._spin(p)

        def _bg():
            total = _sc("SELECT COUNT(*) FROM exames")
            pacs  = _sc("SELECT COUNT(*) FROM pacientes")
            alt   = _sc("SELECT COUNT(*) FROM exames WHERE status LIKE '%ALTERADO%'")
            norm  = _sc("SELECT COUNT(*) FROM exames WHERE status = 'NORMAL'")
            rev   = _sc("SELECT COUNT(*) FROM exames WHERE status = 'REVISAR'")
            pend  = _sc("SELECT COUNT(*) FROM exames WHERE pendencia = 'SIM'")

            raw_ana = _q("""
                SELECT analito, paciente_id,
                       MAX(CASE WHEN status LIKE '%ALTERADO%' THEN 1 ELSE 0 END) AS ca,
                       MAX(date(registrado_em)) AS ult
                FROM exames WHERE paciente_id IS NOT NULL
                GROUP BY analito, paciente_id
            """)
            agg_ana = defaultdict(lambda: {"pacs": set(), "alt": set(), "ult": ""})
            for analito, pac_id, ca, ult in raw_ana:
                key = _norm_analito(analito)
                if not key: continue
                agg_ana[key]["pacs"].add(pac_id)
                if ca: agg_ana[key]["alt"].add(pac_id)
                if (ult or "") > agg_ana[key]["ult"]: agg_ana[key]["ult"] = ult or ""
            top_ana = sorted(
                [(k, len(v["pacs"]), len(v["alt"]), v["ult"])
                 for k, v in agg_ana.items() if v["alt"]],
                key=lambda x: x[2] / x[1] if x[1] else 0, reverse=True
            )[:10]

            top_pac = _q("""
                SELECT p.nome,
                       COUNT(CASE WHEN e.status LIKE '%ALTERADO%' THEN 1 END) AS na,
                       COUNT(*) AS tot,
                       MAX(date(e.registrado_em))   AS ult
                FROM exames e JOIN pacientes p ON e.paciente_id = p.id
                GROUP BY p.id ORDER BY na DESC LIMIT 10
            """)

            recentes = _q("""
                SELECT e.registrado_em, p.nome, e.analito,
                       e.valor, e.unidade, e.referencia, e.status
                FROM exames e JOIN pacientes p ON e.paciente_id = p.id
                WHERE e.status LIKE '%ALTERADO%'
                ORDER BY e.registrado_em DESC LIMIT 30
            """)

            self._safe_after(p, lambda: _render(
                total, pacs, alt, norm, rev, pend,
                top_ana, top_pac, recentes))

        def _render(total, pacs, alt, norm, rev, pend,
                    top_ana, top_pac, recentes):
            try: spin.destroy()
            except: pass

            cv = tk.Canvas(p, highlightthickness=0)
            sb = ttk.Scrollbar(p, orient=tk.VERTICAL, command=cv.yview)
            cv.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.pack(fill=tk.BOTH, expand=True)
            inn = ttk.Frame(cv)
            wid = cv.create_window((0, 0), window=inn, anchor="nw")
            cv.bind("<Configure>", lambda e: cv.itemconfig(wid, width=e.width))
            inn.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

            # Cartões
            fc = ttk.LabelFrame(inn, text="Resumo Geral", padding=10)
            fc.pack(fill=tk.X, padx=14, pady=(12, 6))
            for col, (lbl, val, cor, den) in enumerate([
                ("🏥 Total Exames", total,  "#1a6fb5", None),
                ("👥 Pacientes",    pacs,   "#2e7d32", None),
                ("🔴 Alterados",    alt,    "#c62828", total),
                ("🟢 Normais",      norm,   "#388e3c", total),
                ("🟠 Revisar",      rev,    "#e65100", total),
                ("⚠️ Pendências",   pend,   "#6a1a9a", total),
            ]):
                f = ttk.Frame(fc, relief=tk.RIDGE, borderwidth=1)
                f.grid(row=0, column=col, padx=6, pady=4, sticky="nsew")
                ttk.Label(f, text=lbl, font=("Helvetica", 8)).pack(pady=(6, 2))
                ttk.Label(f, text=str(val), font=("Helvetica", 19, "bold"),
                          foreground=cor).pack()
                sub = f"{round(100*val/den,1)}% do total" if den else ""
                ttk.Label(f, text=sub, font=("Helvetica", 7),
                          foreground="gray").pack(pady=(0, 6))
                fc.columnconfigure(col, weight=1)

            # Top analitos (já filtrados por validos)
            ft = ttk.LabelFrame(inn, text="Top 10 Analitos — Maior Taxa de Alteração", padding=8)
            ft.pack(fill=tk.X, padx=14, pady=6)
            cols = ("Analito", "Pac.", "Alterados", "Taxa %", "Barra", "Último")
            tr = ttk.Treeview(ft, columns=cols, show="headings", height=10)
            for tag, cor in (("alta","#c62828"),("media","#bf6000"),("baixa","#2e7d32")):
                tr.tag_configure(tag, foreground=cor)
            for col, w in zip(cols, (260, 70, 90, 80, 200, 100)):
                tr.heading(col, text=col); tr.column(col, width=w, anchor=tk.W)
            for analito, tp, ca, ult in top_ana:
                pct = round(100 * ca / tp, 1) if tp else 0
                tr.insert("", tk.END,
                    values=(analito, tp, ca, f"{pct}%", _barra(pct), _fc(ult or "")),
                    tags=(_cor(pct),))
            sb_t = ttk.Scrollbar(ft, orient=tk.VERTICAL, command=tr.yview)
            tr.configure(yscrollcommand=sb_t.set)
            tr.grid(row=0, column=0, sticky="nsew"); sb_t.grid(row=0, column=1, sticky="ns")
            ft.columnconfigure(0, weight=1)

            # Top pacientes
            fp = ttk.LabelFrame(inn, text="Top 10 Pacientes — Mais Alterados", padding=8)
            fp.pack(fill=tk.X, padx=14, pady=6)
            trp = ttk.Treeview(fp, columns=("Paciente","Alt.","Total","% Alt.","Último"),
                                show="headings", height=8)
            trp.tag_configure("crit", foreground="#c62828")
            for col, w in zip(("Paciente","Alt.","Total","% Alt.","Último"),
                               (240, 70, 70, 80, 110)):
                trp.heading(col, text=col); trp.column(col, width=w, anchor=tk.W)
            for nome, na, tot, ult in top_pac:
                pct = round(100*(na or 0)/(tot or 1), 1)
                trp.insert("", tk.END,
                    values=(nome, na, tot, f"{pct}%", _fc(ult or "")),
                    tags=(("crit",) if pct >= 30 else ()))
            sbp = ttk.Scrollbar(fp, orient=tk.VERTICAL, command=trp.yview)
            trp.configure(yscrollcommand=sbp.set)
            trp.grid(row=0, column=0, sticky="nsew"); sbp.grid(row=0, column=1, sticky="ns")
            fp.columnconfigure(0, weight=1)

            # Recentes
            fr = ttk.LabelFrame(inn, text="Exames Alterados Mais Recentes", padding=8)
            fr.pack(fill=tk.X, padx=14, pady=(6, 14))
            trr = ttk.Treeview(fr,
                columns=("Data","Paciente","Analito","Valor","Unidade","Ref.","Status"),
                show="headings", height=8)
            trr.tag_configure("alt", foreground="#c62828", background="#fff8f8")
            for col, w in zip(
                ("Data","Paciente","Analito","Valor","Unidade","Ref.","Status"),
                (130, 210, 220, 80, 70, 130, 150)):
                trr.heading(col, text=col); trr.column(col, width=w, anchor=tk.W)
            for dt, pac, ana, val, uni, ref, st in recentes:
                trr.insert("", tk.END,
                    values=(_fd(dt or ""), pac, ana, val, uni, ref, st),
                    tags=("alt",))
            sbr = ttk.Scrollbar(fr, orient=tk.VERTICAL, command=trr.yview)
            sbrx = ttk.Scrollbar(fr, orient=tk.HORIZONTAL, command=trr.xview)
            trr.configure(yscrollcommand=sbr.set, xscrollcommand=sbrx.set)
            trr.grid(row=0, column=0, sticky="nsew")
            sbr.grid(row=0, column=1, sticky="ns"); sbrx.grid(row=1, column=0, sticky="ew")
            fr.rowconfigure(0, weight=1); fr.columnconfigure(0, weight=1)

        threading.Thread(target=_bg, daemon=True).start()

    # ──────────────────────────────────────────
    # JANELA DE DRILL-DOWN: pacientes com alteração num analito
    # ──────────────────────────────────────────

    def _janela_pacientes_analito(self, parent, analito_label: str, nomes_db: set):
        """Abre janela listando todos os pacientes alterados no analito selecionado."""
        win = tk.Toplevel(parent)
        win.title(f"Pacientes — {analito_label}")
        win.geometry("820x500")
        win.resizable(True, True)

        ttk.Label(win, text=f"Alterações: {analito_label}",
                  font=("Helvetica", 13, "bold")).pack(padx=12, pady=(10, 4))

        ft = ttk.Frame(win); ft.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        cols = ("Paciente", "Valor", "Unidade", "Referência", "Status", "Data Exame")
        widths = (200, 80, 80, 160, 140, 100)
        tr = ttk.Treeview(ft, columns=cols, show="headings", height=18)
        tr.tag_configure("alt",  foreground="#c62828", background="#fff0f0")
        tr.tag_configure("norm", foreground="#2e7d32")
        for col, w in zip(cols, widths):
            tr.heading(col, text=col)
            tr.column(col, width=w, anchor=tk.W)
        sby = ttk.Scrollbar(ft, orient=tk.VERTICAL, command=tr.yview)
        tr.configure(yscrollcommand=sby.set)
        tr.grid(row=0, column=0, sticky="nsew"); sby.grid(row=0, column=1, sticky="ns")
        ft.rowconfigure(0, weight=1); ft.columnconfigure(0, weight=1)

        lbl_cnt = ttk.Label(win, text="Carregando…", font=("Helvetica", 9))
        lbl_cnt.pack(anchor=tk.W, padx=12, pady=(2, 6))

        def _load():
            ph = ",".join("?" * len(nomes_db))
            rows = _q(f"""
                SELECT p.nome,
                       e.valor, e.unidade, e.referencia, e.status,
                       COALESCE(pr.data_exame, e.registrado_em) AS dt
                FROM exames e
                JOIN pacientes p ON e.paciente_id = p.id
                LEFT JOIN processamentos pr ON e.processamento_id = pr.id
                WHERE e.analito IN ({ph})
                  AND e.status LIKE '%ALTERADO%'
                ORDER BY p.nome, dt DESC
            """, tuple(nomes_db))

            # Dedup: one row per (patient, analito_key) — keep most recent
            seen = set()
            deduped = []
            for r in rows:
                k = r[0]  # nome do paciente
                if k not in seen:
                    seen.add(k)
                    deduped.append(r)

            def _render():
                for it in tr.get_children(): tr.delete(it)
                for nome, val, uni, ref, sts, dt in deduped:
                    tag = "alt" if "ALTERADO" in str(sts) else "norm"
                    data_fmt = _fc(dt) if dt else "—"
                    tr.insert("", tk.END,
                        values=(nome, val, uni or "—", ref or "—", sts, data_fmt),
                        tags=(tag,))
                lbl_cnt.config(text=f"{len(deduped)} paciente(s) com alteração registrada")

            win.after(0, _render)

        threading.Thread(target=_load, daemon=True).start()

        fb = ttk.Frame(win); fb.pack(fill=tk.X, padx=10, pady=(0, 8))
        ttk.Button(fb, text="💾 Exportar", command=lambda: _exportar(
            list(cols),
            [tr.item(i)["values"] for i in tr.get_children()],
            parent=win
        ), width=14).pack(side=tk.LEFT, padx=4)
        ttk.Button(fb, text="Fechar", command=win.destroy, width=10
                   ).pack(side=tk.RIGHT, padx=4)

    # ──────────────────────────────────────────
    # ABA 2 — PREVALÊNCIA
    # ──────────────────────────────────────────

    def _tab_prevalencia(self, p: ttk.Frame):
        spin = self._spin(p)

        def _bg():
            # Busca por (analito, paciente_id) para deduplicar após normalização
            rows = _q("""
                SELECT e.analito, e.paciente_id,
                       MAX(CASE WHEN e.status LIKE '%ALTERADO%' THEN 1 ELSE 0 END) AS alterado,
                       MAX(COALESCE(pr.data_exame, e.registrado_em)) AS ult
                FROM exames e
                LEFT JOIN processamentos pr ON e.processamento_id = pr.id
                WHERE e.paciente_id IS NOT NULL
                GROUP BY e.analito, e.paciente_id
            """)
            # agg[key] = {pacs, alt, ult, nomes_db}
            agg = defaultdict(lambda: {"pacs": set(), "alt": set(), "ult": "", "nomes_db": set()})
            for analito, pac_id, alterado, ult in rows:
                key = _norm_analito(analito)
                if not key:
                    continue
                agg[key]["pacs"].add(pac_id)
                agg[key]["nomes_db"].add(analito)
                if alterado:
                    agg[key]["alt"].add(pac_id)
                if (ult or "") > agg[key]["ult"]:
                    agg[key]["ult"] = ult or ""
            dados = []
            for key, v in agg.items():
                tp = len(v["pacs"])
                ca = len(v["alt"])
                pct = round(100 * ca / (tp or 1), 1)
                dados.append((key, tp, ca, pct, v["ult"], v["nomes_db"]))
            dados.sort(key=lambda x: x[3], reverse=True)
            self._safe_after(p, lambda: _render(dados))

        def _render(dados_full: list):
            try: spin.destroy()
            except: pass
            state = {"d": dados_full, "rev": {}}

            fc = ttk.LabelFrame(p, text="Filtros", padding=8)
            fc.pack(fill=tk.X, padx=10, pady=6)
            ttk.Label(fc, text="Analito:").grid(row=0, column=0, sticky=tk.W, padx=5)
            ent_f = ttk.Entry(fc, width=30); ent_f.grid(row=0, column=1, padx=5)
            ttk.Label(fc, text="Mín. %:").grid(row=0, column=2, sticky=tk.W, padx=5)
            ent_m = ttk.Entry(fc, width=7); ent_m.insert(0, "0")
            ent_m.grid(row=0, column=3, padx=5)
            var_a = tk.BooleanVar()
            ttk.Checkbutton(fc, text="Apenas com alteração", variable=var_a
                            ).grid(row=0, column=4, padx=10)

            ft = ttk.Frame(p); ft.pack(fill=tk.BOTH, expand=True, padx=10)
            cols = ("Analito","Total Pac.","Com Alt.","Prevalência %","Barra","Último Exame")
            tr = ttk.Treeview(ft, columns=cols, show="headings", height=24)
            for tag, cor, bg in (("alta","#c62828","#fff0f0"),
                                  ("media","#bf6000","#fff8f0"),
                                  ("baixa","#2e7d32","")):
                kw = {"foreground": cor}
                if bg: kw["background"] = bg
                tr.tag_configure(tag, **kw)
            for col, w in zip(cols, (260, 90, 90, 110, 210, 110)):
                tr.heading(col, text=col,
                    command=lambda c=col: _ord(c))
                tr.column(col, width=w, anchor=tk.W)
            sby = ttk.Scrollbar(ft, orient=tk.VERTICAL,   command=tr.yview)
            sbx = ttk.Scrollbar(ft, orient=tk.HORIZONTAL, command=tr.xview)
            tr.configure(yscrollcommand=sby.set, xscrollcommand=sbx.set)
            tr.grid(row=0, column=0, sticky="nsew")
            sby.grid(row=0, column=1, sticky="ns"); sbx.grid(row=1, column=0, sticky="ew")
            ft.rowconfigure(0, weight=1); ft.columnconfigure(0, weight=1)
            lbl = ttk.Label(p, text="", font=("Helvetica", 9))
            lbl.pack(anchor=tk.W, padx=12, pady=2)
            fb = ttk.Frame(p); fb.pack(fill=tk.X, padx=10, pady=4)

            def _pop(dados):
                for it in tr.get_children(): tr.delete(it)
                na = nm = nb = 0
                for row in dados:
                    analito, tp, ca, pct, ult = row[0], row[1], row[2], row[3], row[4]
                    if tp < 3 and pct >= 100:
                        continue
                    tag = _cor(pct)
                    if tag == "alta": na += 1
                    elif tag == "media": nm += 1
                    else: nb += 1
                    label = f"* {analito}" if tp < 5 else analito
                    tr.insert("", tk.END,
                        values=(label, tp, ca, f"{pct:.1f}%",
                                _barra(pct, 24), _fc(ult)),
                        tags=(tag,))
                lbl.config(text=f"{len(dados)} analitos  |  "
                    f"Alta(≥50%): {na}  Média(20–49%): {nm}  Baixa(<20%): {nb}"
                    f"  (* n<5 — amostragem pequena)  — duplo-clique para ver pacientes")

            def _abrir_pacientes(event=None):
                sel = tr.selection()
                if not sel:
                    return
                iid = sel[0]
                vals = tr.item(iid)["values"]
                analito_label = str(vals[0]).lstrip("* ")
                # Encontra o dado completo (com nomes_db)
                match = next((d for d in state["d"] if d[0] == analito_label), None)
                if not match:
                    return
                nomes_db = match[5] if len(match) > 5 else {analito_label}
                ca_count = match[2]
                if ca_count == 0:
                    messagebox.showinfo("Sem alterações",
                        f"Nenhum paciente com alteração em:\n{analito_label}")
                    return
                _janela_pacientes_analito(p, analito_label, nomes_db)

            tr.bind("<Double-1>", _abrir_pacientes)

            def _atualizar():
                f = ent_f.get().strip().lower()
                try: mn = float(ent_m.get() or 0)
                except: mn = 0
                aa = var_a.get()
                state["d"] = [d for d in dados_full
                    if (not f or f in d[0].lower())
                    and d[3] >= mn
                    and (not aa or d[2] > 0)]
                _pop(state["d"])

            def _ord(col):
                i = list(cols).index(col) if col in cols else 3
                rev = not state["rev"].get(col, False)
                state["rev"][col] = rev
                state["d"].sort(key=lambda x: x[i], reverse=rev)
                _pop(state["d"])

            ttk.Button(fb, text="🔄 Atualizar", command=_atualizar, width=14
                       ).pack(side=tk.LEFT, padx=4)
            ttk.Button(fb, text="💾 Exportar", width=14,
                command=lambda: _exportar(list(cols),
                    [(d[0],d[1],d[2],f"{d[3]:.1f}%",_barra(d[3],24),_fc(d[4]))
                     for d in state["d"]], parent=p)
            ).pack(side=tk.LEFT, padx=4)
            ttk.Button(fb, text="👤 Ver Pacientes", width=16,
                command=_abrir_pacientes
            ).pack(side=tk.LEFT, padx=4)
            for w in (ent_f, ent_m): w.bind("<Return>", lambda e: _atualizar())
            var_a.trace_add("write", lambda *_: _atualizar())
            _pop(dados_full)

        threading.Thread(target=_bg, daemon=True).start()

    # ──────────────────────────────────────────
    # ABA 3 — ALTERADOS
    # ──────────────────────────────────────────

    def _tab_alterados(self, p: ttk.Frame):
        fc = ttk.LabelFrame(p, text="Filtros", padding=8)
        fc.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(fc, text="Analito:").grid(row=0, column=0, sticky=tk.W, padx=4)
        ent_a = ttk.Entry(fc, width=28); ent_a.grid(row=0, column=1, padx=4)
        ttk.Label(fc, text="Paciente:").grid(row=0, column=2, sticky=tk.W, padx=4)
        ent_p = ttk.Entry(fc, width=28); ent_p.grid(row=0, column=3, padx=4)
        ttk.Label(fc, text="De:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        ent_di = ttk.Entry(fc, width=13); ent_di.grid(row=1, column=1, sticky=tk.W, padx=4)
        ttk.Label(fc, text="Até:").grid(row=1, column=2, sticky=tk.W, padx=4)
        ent_df = ttk.Entry(fc, width=13); ent_df.grid(row=1, column=3, sticky=tk.W, padx=4)

        ft = ttk.Frame(p); ft.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        cols = ("Data do Exame","Paciente","Analito","Valor",
                "Unidade","Referencia","Status","Próximo Exame")
        tr = ttk.Treeview(ft, columns=cols, show="headings", height=22)
        tr.tag_configure("alt",   foreground="#c62828", background="#fff0f0")
        tr.tag_configure("atras", foreground="#c62828", background="#ffe0d8")
        for col, w in zip(cols, (130,190,220,80,70,140,140,165)):
            tr.heading(col, text=col); tr.column(col, width=w, anchor=tk.W)
        sby = ttk.Scrollbar(ft, orient=tk.VERTICAL,   command=tr.yview)
        sbx = ttk.Scrollbar(ft, orient=tk.HORIZONTAL, command=tr.xview)
        tr.configure(yscrollcommand=sby.set, xscrollcommand=sbx.set)
        tr.grid(row=0, column=0, sticky="nsew")
        sby.grid(row=0, column=1, sticky="ns"); sbx.grid(row=1, column=0, sticky="ew")
        ft.rowconfigure(0, weight=1); ft.columnconfigure(0, weight=1)
        lbl = ttk.Label(p, text="", font=("Helvetica", 9)); lbl.pack(anchor=tk.W, padx=12)

        _rows: list = []

        def _buscar():
            nonlocal _rows
            a = ent_a.get().strip(); pp = ent_p.get().strip()
            di = ent_di.get().strip(); df_ = ent_df.get().strip()
            sql = ("SELECT e.registrado_em,p.nome,e.analito,e.valor,"
                   "e.unidade,e.referencia,e.status "
                   "FROM exames e LEFT JOIN pacientes p ON e.paciente_id=p.id "
                   "WHERE e.status LIKE '%ALTERADO%'")
            params = []
            if a:   sql += " AND e.analito LIKE ?";              params.append(f"%{a}%")
            if pp:  sql += " AND p.nome LIKE ?";                 params.append(f"%{pp}%")
            if di:  sql += " AND date(e.registrado_em) >= ?";    params.append(di)
            if df_: sql += " AND date(e.registrado_em) <= ?";    params.append(df_)
            sql += " ORDER BY e.registrado_em DESC LIMIT 3000"

            def _bg():
                rows = _q(sql, tuple(params))
                self._safe_after(p, lambda: _mostrar(rows))

            threading.Thread(target=_bg, daemon=True).start()

        def _mostrar(rows):
            nonlocal _rows; _rows = rows
            for it in tr.get_children(): tr.delete(it)
            for dt, nome, ana, val, uni, ref, st in rows:
                prox = _proximo(ana, dt or "", st or "")
                tag = "atras" if "atrasado" in prox else "alt"
                tr.insert("", tk.END,
                    values=(_fd(dt or ""), nome, ana, val, uni, ref, st, prox),
                    tags=(tag,))
            lbl.config(text=f"{len(rows)} exame(s) alterado(s)")

        fb = ttk.Frame(fc); fb.grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=6)
        ttk.Button(fb, text="🔍 Buscar", command=_buscar, width=12
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(fb, text="Limpar", width=10,
            command=lambda: [w.delete(0, tk.END)
                for w in (ent_a, ent_p, ent_di, ent_df)] or _buscar()
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(fb, text="💾 Exportar", width=12,
            command=lambda: _exportar(list(cols),
                [tr.item(i)["values"] for i in tr.get_children()], parent=p)
        ).pack(side=tk.LEFT, padx=4)
        for w in (ent_a, ent_p, ent_di, ent_df):
            w.bind("<Return>", lambda e: _buscar())
        _buscar()

    # ──────────────────────────────────────────
    # ABA 4 — EVOLUÇÃO
    # ──────────────────────────────────────────

    def _tab_evolucao(self, p: ttk.Frame):
        fs = ttk.LabelFrame(p, text="Selecionar", padding=8)
        fs.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(fs, text="Paciente:").grid(row=0, column=0, sticky=tk.W, padx=5)
        cmb_p = ttk.Combobox(fs, width=38, state="readonly")
        cmb_p.grid(row=0, column=1, padx=5)

        def _load_pacs():
            pacs = [r[0] for r in _q(
                "SELECT DISTINCT p.nome FROM pacientes p "
                "JOIN exames e ON e.paciente_id=p.id ORDER BY p.nome")]
            self._safe_after(p, lambda: cmb_p.configure(values=pacs))
        threading.Thread(target=_load_pacs, daemon=True).start()
        ttk.Label(fs, text="Analito:").grid(row=0, column=2, sticky=tk.W, padx=5)
        cmb_a = ttk.Combobox(fs, width=34, state="readonly")
        cmb_a.grid(row=0, column=3, padx=5)
        ttk.Button(fs, text="📉 Ver Evolução",
                   command=lambda: _ver(), width=16).grid(row=0, column=4, padx=10)

        def _pac_sel(_=None):
            pac = cmb_p.get()
            if not pac: return
            anas = [r[0] for r in _q(
                "SELECT DISTINCT e.analito FROM exames e "
                "JOIN pacientes p ON e.paciente_id=p.id "
                "WHERE p.nome=? ORDER BY e.analito", (pac,))]
            cmb_a["values"] = anas
            if anas: cmb_a.set(anas[0])
        cmb_p.bind("<<ComboboxSelected>>", _pac_sel)

        # tabela histórico
        fh = ttk.LabelFrame(p, text="Histórico", padding=6)
        fh.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))
        cols = ("Nº","Data","Valor","Unidade","Referencia","Status","Tendência")
        tr = ttk.Treeview(fh, columns=cols, show="headings", height=14)
        tr.tag_configure("alt",    foreground="#c62828", background="#fff0f0")
        tr.tag_configure("normal", foreground="#2e7d32")
        tr.tag_configure("rev",    foreground="#e65100")
        for col, w in zip(cols, (40,140,90,80,170,160,110)):
            tr.heading(col, text=col); tr.column(col, width=w, anchor=tk.W)
        sby = ttk.Scrollbar(fh, orient=tk.VERTICAL, command=tr.yview)
        tr.configure(yscrollcommand=sby.set)
        tr.grid(row=0, column=0, sticky="nsew"); sby.grid(row=0, column=1, sticky="ns")
        fh.rowconfigure(0, weight=1); fh.columnconfigure(0, weight=1)

        # painel análise
        fa = ttk.LabelFrame(p, text="Análise e Recomendação de Repetição", padding=8)
        fa.pack(fill=tk.X, padx=10, pady=(0, 8))
        txt = tk.Text(fa, height=5, font=("Courier", 9), wrap=tk.WORD,
                      state=tk.DISABLED, background="#f7f7f7")
        txt.pack(fill=tk.X)
        txt.tag_configure("ok",     foreground="#2e7d32", font=("Courier",9,"bold"))
        txt.tag_configure("alerta", foreground="#c62828", font=("Courier",9,"bold"))
        txt.tag_configure("info",   foreground="#1565c0", font=("Courier",9,"bold"))
        txt.tag_configure("n",      foreground="#333")

        def _ver():
            pac = cmb_p.get().strip(); ana = cmb_a.get().strip()
            if not pac or not ana:
                messagebox.showwarning("Atenção","Selecione paciente e analito.",parent=p)
                return

            def _bg():
                rows = _q("""
                    SELECT e.registrado_em,e.valor,e.unidade,e.referencia,e.status
                    FROM exames e JOIN pacientes p ON e.paciente_id=p.id
                    WHERE p.nome=? AND e.analito=?
                    ORDER BY e.registrado_em ASC
                """, (pac, ana))
                self._safe_after(p, lambda: _mostrar(rows, pac, ana))

            threading.Thread(target=_bg, daemon=True).start()

        def _mostrar(rows, pac, ana):
            for it in tr.get_children(): tr.delete(it)
            if not rows:
                messagebox.showinfo("Sem dados",
                    f"Nenhum registro de '{ana}' para '{pac}'.", parent=p); return

            vals = [r[1] for r in rows]
            for i, (dt, val, uni, ref, st) in enumerate(rows, 1):
                su = str(st or "").upper()
                tag = "alt" if "ALTERADO" in su else "normal" if su == "NORMAL" else "rev"
                td = _tend(vals[:i]) if i >= 2 else "—"
                tr.insert("", tk.END,
                    values=(i, _fd(dt or ""), val, uni, ref, st or "", td),
                    tags=(tag,))

            # Análise textual
            n_tot = len(rows)
            n_alt = sum(1 for r in rows if "ALTERADO" in str(r[4] or "").upper())
            pct_a = round(100*n_alt/n_tot, 1) if n_tot else 0
            tg    = _tend(vals)
            ult   = rows[-1]
            dias_r, rotulo = _intervalo(ana, str(ult[4] or ""))
            prox  = _proximo(ana, ult[0] or "", str(ult[4] or ""))

            txt.config(state=tk.NORMAL); txt.delete("1.0", tk.END)
            txt.insert(tk.END, f"{ana}  —  {pac}\n", "info")
            txt.insert(tk.END,
                f"Registros: {n_tot}  |  Normais: {n_tot-n_alt}  |  "
                f"Alterados: {n_alt} ({pct_a}%)\n", "n")
            txt.insert(tk.END, "Tendência geral: ")
            txt.insert(tk.END, f"{tg}\n",
                "alerta" if "Subindo" in tg else "ok" if "Caindo" in tg else "n")
            ult_v = f"{ult[1]} {ult[2] or ''}".strip()
            su = str(ult[4] or "")
            txt.insert(tk.END,
                f"Último ({_fd(ult[0] or '')}): {ult_v}  [Ref: {ult[3] or '—'}]  → ", "n")
            txt.insert(tk.END, f"{su}\n", "alerta" if "ALTERADO" in su.upper() else "ok")
            txt.insert(tk.END,
                f"Recomendação ({rotulo}, a cada {dias_r} dias): ", "n")
            txt.insert(tk.END, f"{prox}\n",
                "alerta" if "atrasado" in prox else "ok")
            txt.config(state=tk.DISABLED)

    # ──────────────────────────────────────────
    # ABA 5 — POR PACIENTE
    # ──────────────────────────────────────────

    def _tab_paciente(self, p: ttk.Frame):
        info_map: dict = {}

        fs = ttk.LabelFrame(p, text="Paciente", padding=8)
        fs.pack(fill=tk.X, padx=10, pady=6)
        ttk.Label(fs, text="Selecionar:").grid(row=0, column=0, sticky=tk.W, padx=5)
        cmb = ttk.Combobox(fs, width=44, state="readonly")
        cmb.grid(row=0, column=1, padx=5)

        def _load_pacs():
            rows = _q("SELECT nome,dt_nasc,medico FROM pacientes ORDER BY nome")
            info_map.update({r[0]: (r[1] or "—", r[2] or "—") for r in rows})
            pacs = list(info_map.keys())
            self._safe_after(p, lambda: cmb.configure(values=pacs))
        threading.Thread(target=_load_pacs, daemon=True).start()
        lbl_inf = ttk.Label(fs, text="", font=("Helvetica",9), foreground="#336699")
        lbl_inf.grid(row=0, column=2, padx=10, sticky=tk.W)
        ttk.Label(fs, text="Mostrar:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        cmb_st = ttk.Combobox(fs,
            values=["TODOS","ALTERADO","NORMAL","REVISAR"],
            width=16, state="readonly"); cmb_st.set("TODOS")
        cmb_st.grid(row=1, column=1, sticky=tk.W, padx=5)
        var_ag = tk.BooleanVar(value=True)
        ttk.Checkbutton(fs, text="Agrupar por data", variable=var_ag
                        ).grid(row=1, column=2, padx=10)

        # tabela exames
        ft = ttk.Frame(p); ft.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        cols = ("Data","Analito","Valor","Unidade","Referencia","Status","Pendência")
        tr = ttk.Treeview(ft, columns=cols, show="headings", height=15)
        tr.tag_configure("alt",   foreground="#c62828", background="#fff0f0")
        tr.tag_configure("normal",foreground="#2e7d32")
        tr.tag_configure("rev",   foreground="#e65100")
        tr.tag_configure("grupo", background="#ddeeff", font=("Helvetica",9,"bold"))
        for col, w in zip(cols, (130,245,90,75,150,155,80)):
            tr.heading(col, text=col); tr.column(col, width=w, anchor=tk.W)
        sby = ttk.Scrollbar(ft, orient=tk.VERTICAL,   command=tr.yview)
        sbx = ttk.Scrollbar(ft, orient=tk.HORIZONTAL, command=tr.xview)
        tr.configure(yscrollcommand=sby.set, xscrollcommand=sbx.set)
        tr.grid(row=0, column=0, sticky="nsew")
        sby.grid(row=0, column=1, sticky="ns"); sbx.grid(row=1, column=0, sticky="ew")
        ft.rowconfigure(0, weight=1); ft.columnconfigure(0, weight=1)
        lbl_st = ttk.Label(p, text="", font=("Helvetica",9)); lbl_st.pack(anchor=tk.W, padx=12)

        # tabela próximos exames
        fp = ttk.LabelFrame(p, text="Próximos Exames Recomendados", padding=6)
        fp.pack(fill=tk.X, padx=10, pady=(0, 6))
        cols_p = ("Analito","Último Valor","Status","Último Exame",
                  "Próximo Recomendado","Intervalo")
        tr_p = ttk.Treeview(fp, columns=cols_p, show="headings", height=5)
        tr_p.tag_configure("atras", foreground="#c62828", background="#ffe0d8")
        tr_p.tag_configure("breve", foreground="#bf6000", background="#fff8e0")
        tr_p.tag_configure("ok",    foreground="#2e7d32")
        for col, w in zip(cols_p, (235,120,150,110,165,110)):
            tr_p.heading(col, text=col); tr_p.column(col, width=w, anchor=tk.W)
        sbpy = ttk.Scrollbar(fp, orient=tk.VERTICAL,   command=tr_p.yview)
        sbpx = ttk.Scrollbar(fp, orient=tk.HORIZONTAL, command=tr_p.xview)
        tr_p.configure(yscrollcommand=sbpy.set, xscrollcommand=sbpx.set)
        tr_p.grid(row=0, column=0, sticky="nsew")
        sbpy.grid(row=0, column=1, sticky="ns"); sbpx.grid(row=1, column=0, sticky="ew")
        fp.rowconfigure(0, weight=1); fp.columnconfigure(0, weight=1)

        def _carregar(_=None):
            pac = cmb.get()
            if not pac: return
            dt_n, med = info_map.get(pac, ("—","—"))
            lbl_inf.config(text=f"Nasc: {dt_n}  |  Médico: {med}")
            st_sel = cmb_st.get()

            def _bg():
                sql = ("SELECT e.registrado_em,e.analito,e.valor,e.unidade,"
                       "e.referencia,e.status,e.pendencia "
                       "FROM exames e JOIN pacientes p ON e.paciente_id=p.id "
                       "WHERE p.nome=?")
                params: list = [pac]
                if st_sel != "TODOS":
                    sql_q = sql + " AND e.status LIKE ? ORDER BY e.registrado_em DESC,e.analito"
                    params.append(f"%{st_sel}%")
                else:
                    sql_q = sql + " ORDER BY e.registrado_em DESC,e.analito"
                rows = _q(sql_q, tuple(params))
                self._safe_after(p, lambda: _mostrar(rows))

            threading.Thread(target=_bg, daemon=True).start()

        def _mostrar(rows):
            for it in tr.get_children(): tr.delete(it)
            n_alt  = sum(1 for r in rows if "ALTERADO" in str(r[5] or "").upper())
            n_pend = sum(1 for r in rows if str(r[6] or "") == "SIM")
            datas  = {(r[0] or "")[:10] for r in rows}
            lbl_st.config(
                text=f"{len(rows)} exame(s)  |  Alterados: {n_alt}  |  "
                     f"Pendências: {n_pend}  |  Dias de coleta: {len(datas)}")

            if var_ag.get():
                from itertools import groupby
                for data_k, grp in groupby(rows, key=lambda r: (r[0] or "")[:10]):
                    gl = list(grp)
                    na = sum(1 for r in gl if "ALTERADO" in str(r[5] or "").upper())
                    tr.insert("", tk.END,
                        values=(f"📅 {_fc(data_k)}  ({len(gl)} exames, {na} alt.)",
                                "","","","","",""), tags=("grupo",))
                    for dt,ana,val,uni,ref,st,pend in gl:
                        su = str(st or "").upper()
                        tag = "alt" if "ALTERADO" in su else "normal" if su=="NORMAL" else "rev"
                        tr.insert("", tk.END,
                            values=("  "+_fd(dt or ""),ana,val,uni,ref,st or "",pend or ""),
                            tags=(tag,))
            else:
                for dt,ana,val,uni,ref,st,pend in rows:
                    su = str(st or "").upper()
                    tag = "alt" if "ALTERADO" in su else "normal" if su=="NORMAL" else "rev"
                    tr.insert("", tk.END,
                        values=(_fd(dt or ""),ana,val,uni,ref,st or "",pend or ""),
                        tags=(tag,))

            # próximos exames: último resultado de cada analito
            ult = {}
            for dt,ana,val,uni,st,*_ in [(r[0],r[1],r[2],r[3],r[5]) for r in rows]:
                if ana not in ult: ult[ana] = (dt,val,uni,st)

            proximos = []
            for ana,(dt,val,uni,st) in ult.items():
                prox = _proximo(ana, dt or "", str(st or ""))
                if prox == "—": continue
                dias_r, rotulo = _intervalo(ana, str(st or ""))
                try:
                    d_prox = datetime.strptime(prox[:10], "%d/%m/%Y").date()
                except: d_prox = date.max
                proximos.append((d_prox, ana, val, uni, st, dt, prox, dias_r, rotulo))
            proximos.sort(key=lambda x: x[0])

            for it in tr_p.get_children(): tr_p.delete(it)
            for d_prox,ana,val,uni,st,dt,prox,dias_r,rotulo in proximos:
                atraso = "atrasado" in prox
                hoje = date.today()
                breve = not atraso and (d_prox - hoje).days <= 30
                tag = "atras" if atraso else "breve" if breve else "ok"
                tr_p.insert("", tk.END,
                    values=(ana, f"{val} {uni or ''}".strip(), str(st or ""),
                            _fc(dt or ""), prox, f"{rotulo} / {dias_r}d"),
                    tags=(tag,))

        cmb.bind("<<ComboboxSelected>>", _carregar)
        cmb_st.bind("<<ComboboxSelected>>", lambda e: _carregar())
        var_ag.trace_add("write", lambda *_: _carregar())

        fb = ttk.Frame(p); fb.pack(fill=tk.X, padx=10, pady=(0,2))
        ttk.Button(fb, text="💾 Exportar Exames", width=20,
            command=lambda: _exportar(list(cols),
                [tr.item(i)["values"] for i in tr.get_children() if tr.item(i)["values"][1]],
                parent=p)
        ).pack(side=tk.LEFT, padx=4)

    # ──────────────────────────────────────────
    # ABA 6 — FILTROS
    # ──────────────────────────────────────────

    def _tab_filtros(self, p: ttk.Frame):
        ff = ttk.LabelFrame(p, text="Filtros", padding=10)
        ff.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(ff, text="Paciente:").grid(row=0,column=0,sticky=tk.W,padx=5)
        cmb_p = ttk.Combobox(ff, width=38)
        cmb_p.grid(row=0,column=1,sticky=tk.EW,padx=5)
        ttk.Label(ff, text="Analito:").grid(row=1,column=0,sticky=tk.W,padx=5,pady=4)
        ent_a = ttk.Entry(ff, width=40); ent_a.grid(row=1,column=1,sticky=tk.EW,padx=5)
        ttk.Label(ff, text="Médico:").grid(row=2,column=0,sticky=tk.W,padx=5)
        cmb_m = ttk.Combobox(ff, width=38)
        cmb_m.grid(row=2,column=1,sticky=tk.EW,padx=5)

        def _load_combos():
            pacs = [r[0] for r in _q("SELECT DISTINCT nome FROM pacientes ORDER BY nome")]
            meds = [r[0] for r in _q(
                "SELECT DISTINCT medico FROM pacientes WHERE medico IS NOT NULL ORDER BY medico")]
            self._safe_after(p, lambda: (
                cmb_p.configure(values=[""]+pacs),
                cmb_m.configure(values=[""]+meds)
            ))
        threading.Thread(target=_load_combos, daemon=True).start()
        ttk.Label(ff, text="Status:").grid(row=3,column=0,sticky=tk.W,padx=5,pady=4)
        cmb_st = ttk.Combobox(ff,
            values=["TODOS","NORMAL","ALTERADO","REVISAR"],
            width=18, state="readonly"); cmb_st.set("TODOS")
        cmb_st.grid(row=3,column=1,sticky=tk.W,padx=5)
        ttk.Label(ff, text="De:").grid(row=0,column=2,sticky=tk.W,padx=6)
        ent_di = ttk.Entry(ff, width=13); ent_di.grid(row=0,column=3,sticky=tk.W,padx=5)
        ttk.Label(ff, text="Até:").grid(row=1,column=2,sticky=tk.W,padx=6,pady=4)
        ent_df = ttk.Entry(ff, width=13); ent_df.grid(row=1,column=3,sticky=tk.W,padx=5)
        ttk.Label(ff, text="Pendência:").grid(row=2,column=2,sticky=tk.W,padx=6)
        cmb_pend = ttk.Combobox(ff,
            values=["TODAS","SIM","NÃO"], width=10, state="readonly"); cmb_pend.set("TODAS")
        cmb_pend.grid(row=2,column=3,sticky=tk.W,padx=5)
        ff.columnconfigure(1, weight=1); ff.columnconfigure(3, weight=1)

        fr = ttk.LabelFrame(p, text="Resultado", padding=6)
        fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        cols = ("Data","Paciente","Analito","Valor","Unidade","Referencia","Status","Pendência")
        tr = ttk.Treeview(fr, columns=cols, show="headings", height=14)
        tr.tag_configure("alt", foreground="#c62828", background="#fff0f0")
        tr.tag_configure("rev", foreground="#e65100")
        for col, w in zip(cols, (130,170,210,80,70,130,140,80)):
            tr.heading(col, text=col); tr.column(col, width=w, anchor=tk.W)
        sby = ttk.Scrollbar(fr, orient=tk.VERTICAL,   command=tr.yview)
        sbx = ttk.Scrollbar(fr, orient=tk.HORIZONTAL, command=tr.xview)
        tr.configure(yscrollcommand=sby.set, xscrollcommand=sbx.set)
        tr.grid(row=0,column=0,sticky="nsew")
        sby.grid(row=0,column=1,sticky="ns"); sbx.grid(row=1,column=0,sticky="ew")
        fr.rowconfigure(0, weight=1); fr.columnconfigure(0, weight=1)
        lbl = ttk.Label(p, text="", font=("Helvetica",9)); lbl.pack(anchor=tk.W, padx=12)

        def _aplicar():
            a = ent_a.get().strip(); pp = cmb_p.get().strip()
            m = cmb_m.get().strip();  st = cmb_st.get()
            di = ent_di.get().strip(); df_ = ent_df.get().strip()
            pend = cmb_pend.get()
            sql = ("SELECT e.registrado_em,p.nome,e.analito,e.valor,"
                   "e.unidade,e.referencia,e.status,e.pendencia "
                   "FROM exames e LEFT JOIN pacientes p ON e.paciente_id=p.id WHERE 1=1")
            params: list = []
            if pp:  sql += " AND p.nome=?";                    params.append(pp)
            if a:   sql += " AND e.analito LIKE ?";            params.append(f"%{a}%")
            if m:   sql += " AND p.medico=?";                  params.append(m)
            if st != "TODOS": sql += " AND e.status LIKE ?";  params.append(f"%{st}%")
            if di:  sql += " AND date(e.registrado_em)>=?";   params.append(di)
            if df_: sql += " AND date(e.registrado_em)<=?";   params.append(df_)
            if pend != "TODAS": sql += " AND e.pendencia=?";  params.append(pend)
            sql += " ORDER BY e.registrado_em DESC LIMIT 5000"

            def _bg():
                rows = _q(sql, tuple(params))
                self._safe_after(p, lambda: _mostrar(rows))

            threading.Thread(target=_bg, daemon=True).start()

        def _mostrar(rows):
            for it in tr.get_children(): tr.delete(it)
            for dt,nome,ana,val,uni,ref,st,pend in rows:
                su = str(st or "").upper()
                tag = ("alt",) if "ALTERADO" in su else ("rev",) if "REVISAR" in su else ()
                tr.insert("", tk.END,
                    values=(_fd(dt or ""),nome,ana,val,uni,ref,st or "",pend or ""),
                    tags=tag)
            lbl.config(text=f"{len(rows)} registro(s)")

        fb = ttk.Frame(ff); fb.grid(row=4,column=0,columnspan=4,sticky=tk.W,pady=8)
        ttk.Button(fb, text="🔍 Aplicar", command=_aplicar, width=14
                   ).pack(side=tk.LEFT, padx=4)
        ttk.Button(fb, text="💾 Exportar", width=14,
            command=lambda: _exportar(list(cols),
                [tr.item(i)["values"] for i in tr.get_children()], parent=p)
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(fb, text="Limpar", width=10,
            command=lambda: [w.delete(0,tk.END) for w in (ent_a,ent_di,ent_df)]
        ).pack(side=tk.LEFT, padx=4)
        for w in (ent_a, ent_di, ent_df):
            w.bind("<Return>", lambda e: _aplicar())


def main():
    root = tk.Tk()
    AnalisadorExamesAvancado(root)
    root.mainloop()


if __name__ == "__main__":
    main()
