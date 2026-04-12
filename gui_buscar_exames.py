"""
Interface Tkinter para buscar e filtrar exames processados
Banco SQLite (exames.db) como fonte principal.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import sqlite3
import re
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = "exames.db"

# ---------------------------------------------------------------------------
# VALIDADOR DE ANALITOS — importado de utils_analitos (módulo leve, sem
# dependências de e-mail).  Fallback embutido se o módulo não existir.
# ---------------------------------------------------------------------------
try:
    from utils_analitos import e_nome_exame_valido as _analito_valido
except Exception:
    # Versão compacta de fallback (cobre os padrões mais comuns)
    _PAT_INVALIDO = re.compile(
        r"\.{3,}\s*:"                            # pontilhado+dois-pontos
        r"|:\s+[\d<>]"                           # dois-pontos + número
        r"|\b(mg/dL|g/dL|g/L|pg/mL|ng/mL|mUI/L|U/L|nmol/L|mmol/L|fL|mm³|/mm3|cm|kg|IU/mL)\b"
        r"|\bDe\s+[\d<>]|\bAté\s+\d"            # faixa de referência
        r"|\s+\d+[,.]?\d*\s*$"                  # número no final
        r"|\b\d+[,.]?\d*\b.*\b\d+[,.]?\d*\b"   # dois números
        r"|\b\d\+\s*$"                           # 1+, 3+ no final
        r"|Fase\s+(Fol|L[uú]t|Ovu)"
        r"|(Ausentes?|Reagente|Negativo|Positivo)\s+(Ausentes?|Reagente|Negativo|Positivo|\d)"
        r"|\b(anos|adultos|crianças|mulheres:|homens:|normatização|vigilância)\b"
        r"|R\s+e\s+s\s+u\s+l"                   # "R e s u l t a d o"
        r"|Metodo\s*:|Metodologia\s*:|Interpretação:|Relação paciente"
        r"|Nome\s*:",
        re.IGNORECASE
    )
    _TERMOS_FIXOS = {
        "VALORES", "RESULTADO", "AUTENTICIDADE", "REFERÊNCIA", "UNIDADE",
        "MÉTODO", "MATERIAL", "LAUDO", "PÁGINA", "LABORATÓRIO", "PREFEITURA",
        "MUNICIPAL", "ASSOCIAÇÃO", "CORRELAÇÃO", "EPIDEMIOLÓGICO",
        "ERITROGRAMA", "LEUCOGRAMA", "CPF", "SOLICITANTE", "EMISSÃO",
        "CNES", "GRÁVIDAS", "TRIMESTRE", "NORMATIZAÇÃO", "ADOLFO LUTZ",
        "VIGILÂNCIA", "CUTOFF", "SATURAÇÃO", "INSUFICIÊNCIA",
        "PLASMA DO PACIENTE", "RISCO ELEVADO", "RISCO MODERADO",
        "PÓS MENOPAUSA", "IDADE REPRODUTIVA", "MEIO CICLO",
        "ATIVIDADE DE PROTR", "RELAÇÃO PACIENTE", "LEUCOCITOSE",
        "CONSISTENTE COM", "NÃO FORAM ENCONTRADOS", "HOUVE CRESCIMENTO",
    }

    def _analito_valido(nome: str) -> bool:
        s = nome.strip()
        if len(s) < 3 or len(s) > 90:
            return False
        if re.match(r"^\d", s):
            return False
        if re.match(r"^[\.\:\-\=\*\_\+\s]+$", s):
            return False
        if s.count(" ") > 12:
            return False
        if _PAT_INVALIDO.search(s):
            return False
        su = s.upper()
        if any(t in su for t in _TERMOS_FIXOS):
            return False
        return True


# ===========================
# CLASSE GERENCIADORA DE DADOS
# ===========================
class GerenciadorExames:
    """
    Gerencia dados de exames.
    Prioriza o banco SQLite (exames.db); usa Excel como fallback.
    """

    def __init__(self, caminho_relatorio: str = "relatorio_exames.xlsx",
                 db_path: str = DB_PATH):
        self.caminho_relatorio = caminho_relatorio
        self.db_path = db_path
        self.df_exames: Optional[pd.DataFrame] = None
        self.df_pendencias: Optional[pd.DataFrame] = None
        self.fonte: str = "nenhuma"   # "sqlite" | "excel" | "nenhuma"
        self.carregar_dados()

    # ------------------------------------------------------------------
    # CARREGAMENTO
    # ------------------------------------------------------------------
    def carregar_dados(self) -> bool:
        """Tenta SQLite primeiro; cai no Excel se não disponível."""
        if self._carregar_sqlite():
            return True
        return self._carregar_excel()

    def _carregar_sqlite(self) -> bool:
        """Carrega dados do banco SQLite."""
        if not os.path.exists(self.db_path):
            return False
        try:
            query = """
                SELECT
                    pr.arquivo_pdf  AS Arquivo,
                    p.nome          AS Paciente,
                    p.dt_nasc       AS "Dt Nasc",
                    p.medico        AS Medico,
                    pr.pedido       AS Pedido,
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
                ORDER BY e.registrado_em DESC
            """
            with sqlite3.connect(self.db_path) as conn:
                self.df_exames = pd.read_sql_query(query, conn)

            # Pendências
            self.df_pendencias = self.df_exames[
                self.df_exames["Pendencia"] == "SIM"
            ].copy() if "Pendencia" in self.df_exames.columns else pd.DataFrame()

            self.fonte = "sqlite"
            return not self.df_exames.empty

        except Exception as e:
            print(f"Erro ao carregar SQLite: {e}")
            return False

    def _carregar_excel(self) -> bool:
        """Carrega dados do arquivo Excel (fallback)."""
        try:
            if not os.path.exists(self.caminho_relatorio):
                return False

            xls = pd.ExcelFile(self.caminho_relatorio)
            if "exames" in xls.sheet_names:
                self.df_exames = pd.read_excel(self.caminho_relatorio, sheet_name="exames")
            if "pendencias" in xls.sheet_names:
                self.df_pendencias = pd.read_excel(self.caminho_relatorio, sheet_name="pendencias")

            self.fonte = "excel"
            return self.df_exames is not None and not self.df_exames.empty

        except Exception as e:
            print(f"Erro ao carregar Excel: {e}")
            return False

    # ------------------------------------------------------------------
    # CONSULTAS DIRETAS AO SQLite (mais eficientes para grandes volumes)
    # ------------------------------------------------------------------
    def _query_sqlite(self, where: str = "", params: tuple = ()) -> pd.DataFrame:
        """Executa query genérica no SQLite com JOIN padrão."""
        base = """
            SELECT
                pr.arquivo_pdf  AS Arquivo,
                p.nome          AS Paciente,
                p.dt_nasc       AS "Dt Nasc",
                p.medico        AS Medico,
                pr.pedido       AS Pedido,
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
        query = base + (f" WHERE {where}" if where else "") + " ORDER BY e.registrado_em DESC"
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(query, conn, params=params)

    # ------------------------------------------------------------------
    # BUSCAS (funcionam com SQLite ou com o df em memória)
    # ------------------------------------------------------------------
    def buscar_por_paciente(self, nome_paciente: str) -> pd.DataFrame:
        if not nome_paciente.strip():
            return self.df_exames.copy() if self.df_exames is not None else pd.DataFrame()

        if self.fonte == "sqlite":
            try:
                return self._query_sqlite("p.nome LIKE ?", (f"%{nome_paciente}%",))
            except Exception:
                pass

        if self.df_exames is None:
            return pd.DataFrame()
        mask = self.df_exames["Paciente"].astype(str).str.contains(nome_paciente, case=False, na=False)
        return self.df_exames[mask].copy()

    def buscar_por_analito(self, nome_analito: str) -> pd.DataFrame:
        if not nome_analito.strip():
            return self.df_exames.copy() if self.df_exames is not None else pd.DataFrame()

        if self.fonte == "sqlite":
            try:
                return self._query_sqlite("e.analito LIKE ?", (f"%{nome_analito}%",))
            except Exception:
                pass

        if self.df_exames is None:
            return pd.DataFrame()
        mask = self.df_exames["Analito"].astype(str).str.contains(nome_analito, case=False, na=False)
        return self.df_exames[mask].copy()

    def buscar_por_status(self, status: str) -> pd.DataFrame:
        if not status or status == "TODOS":
            return self.df_exames.copy() if self.df_exames is not None else pd.DataFrame()

        if self.fonte == "sqlite":
            try:
                return self._query_sqlite("e.status LIKE ?", (f"%{status}%",))
            except Exception:
                pass

        if self.df_exames is None:
            return pd.DataFrame()
        mask = self.df_exames["Status"].astype(str).str.contains(status, case=False, na=False)
        return self.df_exames[mask].copy()

    def buscar_analitos_alterados(self, filtro_analito: str = "",
                                   nome_paciente: str = "") -> pd.DataFrame:
        if self.fonte == "sqlite":
            try:
                conditions = ["e.status LIKE '%ALTERADO%'"]
                params: list = []
                if filtro_analito.strip():
                    conditions.append("e.analito LIKE ?")
                    params.append(f"%{filtro_analito}%")
                if nome_paciente.strip():
                    conditions.append("p.nome LIKE ?")
                    params.append(f"%{nome_paciente}%")
                return self._query_sqlite(" AND ".join(conditions), tuple(params))
            except Exception:
                pass

        if self.df_exames is None:
            return pd.DataFrame()

        df = self.df_exames[
            self.df_exames["Status"].astype(str).str.contains("ALTERADO", case=False, na=False)
        ].copy()
        if filtro_analito.strip():
            df = df[df["Analito"].astype(str).str.contains(filtro_analito, case=False, na=False)]
        if nome_paciente.strip():
            df = df[df["Paciente"].astype(str).str.contains(nome_paciente, case=False, na=False)]
        return df.sort_values(["Paciente", "Analito"], ascending=True)

    def busca_avancada(self, paciente: str = "", analito: str = "",
                       status: str = "", data_inicio: str = "",
                       data_fim: str = "") -> pd.DataFrame:
        if self.fonte == "sqlite":
            try:
                conditions = []
                params: list = []
                if paciente.strip():
                    conditions.append("p.nome LIKE ?")
                    params.append(f"%{paciente}%")
                if analito.strip():
                    conditions.append("e.analito LIKE ?")
                    params.append(f"%{analito}%")
                if status and status != "TODOS":
                    conditions.append("e.status LIKE ?")
                    params.append(f"%{status}%")
                if data_inicio.strip():
                    conditions.append("date(e.registrado_em) >= ?")
                    params.append(data_inicio.strip())
                if data_fim.strip():
                    conditions.append("date(e.registrado_em) <= ?")
                    params.append(data_fim.strip())
                where = " AND ".join(conditions) if conditions else ""
                return self._query_sqlite(where, tuple(params))
            except Exception:
                pass

        # Fallback em memória
        if self.df_exames is None:
            return pd.DataFrame()

        df = self.df_exames.copy()
        if paciente.strip():
            df = df[df["Paciente"].astype(str).str.contains(paciente, case=False, na=False)]
        if analito.strip():
            df = df[df["Analito"].astype(str).str.contains(analito, case=False, na=False)]
        if status and status != "TODOS":
            df = df[df["Status"].astype(str).str.contains(status, case=False, na=False)]
        return df

    def prevalencia_analitos(self, apenas_com_alterados: bool = False) -> pd.DataFrame:
        """
        Calcula prevalência de alteração por analito.
        Aplica automaticamente o validador de analitos para excluir ruído.
        Retorna DataFrame: Analito | Total_Pacientes | Com_Alteracao | Prevalencia_Pct
        """
        if self.fonte == "sqlite":
            try:
                query = """
                    SELECT
                        e.analito AS Analito,
                        COUNT(DISTINCT e.paciente_id) AS Total_Pacientes,
                        COUNT(DISTINCT CASE WHEN e.status LIKE '%ALTERADO%'
                              THEN e.paciente_id END) AS Com_Alteracao,
                        ROUND(100.0 *
                            COUNT(DISTINCT CASE WHEN e.status LIKE '%ALTERADO%'
                                  THEN e.paciente_id END) /
                            NULLIF(COUNT(DISTINCT e.paciente_id), 0), 1
                        ) AS Prevalencia_Pct
                    FROM exames e
                    WHERE e.paciente_id IS NOT NULL
                    GROUP BY e.analito
                    HAVING COUNT(DISTINCT e.paciente_id) > 0
                    ORDER BY Prevalencia_Pct DESC, Com_Alteracao DESC
                """
                with sqlite3.connect(self.db_path) as conn:
                    df = pd.read_sql_query(query, conn)
                # filtra analitos inválidos (ruído de extração)
                df = df[df["Analito"].apply(_analito_valido)].copy()
                if apenas_com_alterados:
                    df = df[df["Com_Alteracao"] > 0]
                return df.reset_index(drop=True)
            except Exception as e:
                print(f"Erro prevalência SQLite: {e}")

        if self.df_exames is None:
            return pd.DataFrame()

        df = self.df_exames.copy()
        # filtra analitos inválidos
        df = df[df["Analito"].apply(_analito_valido)]
        alt_mask = df["Status"].astype(str).str.contains("ALTERADO", na=False)
        resultado = []
        for analito, grp in df.groupby("Analito"):
            total = grp["Paciente"].nunique()
            com_alt = grp.loc[alt_mask[grp.index], "Paciente"].nunique()
            pct = round(100.0 * com_alt / total, 1) if total > 0 else 0.0
            resultado.append({
                "Analito": analito,
                "Total_Pacientes": total,
                "Com_Alteracao": com_alt,
                "Prevalencia_Pct": pct,
            })
        df_res = pd.DataFrame(resultado)
        if apenas_com_alterados:
            df_res = df_res[df_res["Com_Alteracao"] > 0]
        return df_res.sort_values("Prevalencia_Pct", ascending=False).reset_index(drop=True)

    def pode_excluir_excel(self) -> tuple:
        """
        Verifica se o SQLite já contém dados suficientes para dispensar o Excel.
        Retorna (bool, str) — pode_excluir, motivo.
        """
        import os
        if not os.path.exists(self.db_path):
            return False, "Banco SQLite não encontrado."
        if not os.path.exists(self.caminho_relatorio):
            return False, "Arquivo Excel não existe, nada a excluir."
        try:
            with sqlite3.connect(self.db_path) as conn:
                n_sql = conn.execute("SELECT COUNT(*) FROM exames").fetchone()[0]
            if n_sql == 0:
                return False, "Banco SQLite está vazio."
            return True, f"SQLite contém {n_sql} exames — Excel pode ser removido."
        except Exception as e:
            return False, f"Erro ao verificar banco: {e}"

    def estatisticas(self) -> Dict:
        """Retorna estatísticas gerais do banco/Excel."""
        if self.fonte == "sqlite":
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    return {
                        "total":      cur.execute("SELECT COUNT(*) FROM exames").fetchone()[0],
                        "pacientes":  cur.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0],
                        "alterados":  cur.execute("SELECT COUNT(*) FROM exames WHERE status LIKE '%ALTERADO%'").fetchone()[0],
                        "normais":    cur.execute("SELECT COUNT(*) FROM exames WHERE status = 'NORMAL'").fetchone()[0],
                        "revisar":    cur.execute("SELECT COUNT(*) FROM exames WHERE status LIKE '%REVISAR%'").fetchone()[0],
                        "pendencias": cur.execute("SELECT COUNT(*) FROM exames WHERE pendencia = 'SIM'").fetchone()[0],
                    }
            except Exception:
                pass

        if self.df_exames is None or self.df_exames.empty:
            return {"total": 0, "pacientes": 0, "alterados": 0, "normais": 0, "revisar": 0, "pendencias": 0}

        df_s = self.df_exames["Status"].astype(str).str.upper()
        return {
            "total":      len(self.df_exames),
            "pacientes":  self.df_exames["Paciente"].nunique() if "Paciente" in self.df_exames.columns else 0,
            "alterados":  df_s.str.contains("ALTERADO", na=False).sum(),
            "normais":    df_s.str.fullmatch("NORMAL", na=False).sum(),
            "revisar":    df_s.str.contains("REVISAR", na=False).sum(),
            "pendencias": (self.df_exames.get("Pendencia", pd.Series(dtype=str)) == "SIM").sum(),
        }


# ===========================
# INTERFACE TKINTER PRINCIPAL
# ===========================
class AplicacaoBuscaExames:
    """Interface Tkinter para busca e visualização de exames"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Buscar Exames")
        self.root.geometry("1280x750")

        self.gerenciador = GerenciadorExames()

        if self.gerenciador.df_exames is None or self.gerenciador.df_exames.empty:
            messagebox.showwarning(
                "Aviso",
                "Nenhum dado encontrado.\n\n"
                "Verifique se o banco 'exames.db' ou o arquivo\n"
                "'relatorio_exames.xlsx' existem nesta pasta."
            )

        self._criar_widgets()
        self._atualizar_tabela()

    # ------------------------------------------------------------------
    # CONSTRUÇÃO DA INTERFACE
    # ------------------------------------------------------------------
    def _criar_widgets(self):

        # ===== FILTROS =====
        frame_controles = ttk.LabelFrame(self.root, text="Filtros de Busca", padding=10)
        frame_controles.pack(fill=tk.X, padx=10, pady=8)

        # Linha 0
        ttk.Label(frame_controles, text="Paciente:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.entry_paciente = ttk.Entry(frame_controles, width=28)
        self.entry_paciente.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.entry_paciente.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        ttk.Label(frame_controles, text="Analito:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.entry_analito = ttk.Entry(frame_controles, width=28)
        self.entry_analito.grid(row=0, column=3, sticky=tk.EW, padx=5)
        self.entry_analito.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        ttk.Label(frame_controles, text="Status:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.combo_status = ttk.Combobox(
            frame_controles,
            values=["TODOS", "NORMAL", "ALTERADO", "REVISAR"],
            width=14, state="readonly"
        )
        self.combo_status.set("TODOS")
        self.combo_status.grid(row=0, column=5, sticky=tk.EW, padx=5)
        self.combo_status.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtros())

        # Linha 1: datas (só ativas com SQLite)
        ttk.Label(frame_controles, text="De (AAAA-MM-DD):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.entry_data_ini = ttk.Entry(frame_controles, width=14)
        self.entry_data_ini.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.entry_data_ini.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        ttk.Label(frame_controles, text="Até:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.entry_data_fim = ttk.Entry(frame_controles, width=14)
        self.entry_data_fim.grid(row=1, column=3, sticky=tk.W, padx=5)
        self.entry_data_fim.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        frame_controles.columnconfigure(1, weight=1)
        frame_controles.columnconfigure(3, weight=1)

        # Botões
        frame_botoes = ttk.Frame(frame_controles)
        frame_botoes.grid(row=2, column=0, columnspan=6, sticky=tk.EW, pady=8)

        ttk.Button(frame_botoes, text="🔄 Limpar Filtros",
                   command=self._limpar_filtros).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="🔴 Procurar Alterados",
                   command=self._buscar_alterados).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="📊 Atualizar Dados",
                   command=self._atualizar_dados).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="💾 Exportar Resultados",
                   command=self._exportar_resultados).pack(side=tk.LEFT, padx=5)

        # ===== LABEL INFO =====
        frame_info = ttk.Frame(self.root)
        frame_info.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.label_info = ttk.Label(frame_info,
                                    text="Total: — | Alterados: — | Normais: — | Revisar: —",
                                    relief=tk.SUNKEN)
        self.label_info.pack(fill=tk.X)

        # ===== TREEVIEW =====
        frame_tabela = ttk.Frame(self.root)
        frame_tabela.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar_y = ttk.Scrollbar(frame_tabela)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x = ttk.Scrollbar(frame_tabela, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        colunas = ["Arquivo", "Paciente", "Pedido", "Analito",
                   "Valor", "Unidade", "Referencia", "Status", "Motivo", "Registrado Em"]

        self.tree = ttk.Treeview(
            frame_tabela, columns=colunas, height=20,
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )
        scrollbar_y.config(command=self.tree.yview)
        scrollbar_x.config(command=self.tree.xview)

        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.heading("#0", text="", anchor=tk.W)

        larguras = {
            "Arquivo": 120, "Paciente": 160, "Pedido": 80,
            "Analito": 200, "Valor": 80, "Unidade": 70,
            "Referencia": 110, "Status": 100, "Motivo": 160, "Registrado Em": 130
        }
        for col in colunas:
            self.tree.column(col, width=larguras.get(col, 100), anchor=tk.W)
            self.tree.heading(col, text=col, anchor=tk.W)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # ===== STATUS BAR =====
        frame_status = ttk.Frame(self.root)
        frame_status.pack(fill=tk.X, padx=10, pady=5)
        self.label_status = ttk.Label(frame_status, text="Pronto", relief=tk.SUNKEN)
        self.label_status.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # ATUALIZAÇÃO DA TABELA
    # ------------------------------------------------------------------
    def _atualizar_tabela(self, df: pd.DataFrame = None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if df is None:
            df = self.gerenciador.df_exames

        if df is None or df.empty:
            self._atualizar_info()
            return

        for _, row in df.iterrows():
            valores = [
                row.get("Arquivo", ""),
                row.get("Paciente", ""),
                row.get("Pedido", ""),
                row.get("Analito", ""),
                str(row.get("Valor", "")) if pd.notna(row.get("Valor")) else "",
                row.get("Unidade", ""),
                row.get("Referencia", ""),
                row.get("Status", ""),
                row.get("Motivo", ""),
                row.get("Registrado Em", ""),
            ]
            status = str(row.get("Status", "")).upper()
            tags = ("alterado",) if "ALTERADO" in status else ("revisar",) if "REVISAR" in status else ()
            self.tree.insert("", tk.END, values=valores, tags=tags)

        self.tree.tag_configure("alterado", foreground="red",    background="#ffe6e6")
        self.tree.tag_configure("revisar",  foreground="#995500", background="#fff3e6")

        self._atualizar_info()
        self._atualizar_status(f"Exibindo {len(df)} registros")

    def _atualizar_info(self):
        stats = self.gerenciador.estatisticas()
        self.label_info.config(
            text=(
                f"Total: {stats['total']} exames"
                f" | Pacientes: {stats['pacientes']}"
                f" | Alterados: {stats['alterados']}"
                f" | Normais: {stats['normais']}"
                f" | Revisar: {stats['revisar']}"
                f" | Pendências: {stats['pendencias']}"
            )
        )

    def _atualizar_status(self, mensagem: str):
        self.label_status.config(text=mensagem)
        self.root.update()

    # ------------------------------------------------------------------
    # AÇÕES DOS BOTÕES
    # ------------------------------------------------------------------
    def _aplicar_filtros(self):
        df = self.gerenciador.busca_avancada(
            paciente=self.entry_paciente.get(),
            analito=self.entry_analito.get(),
            status=self.combo_status.get(),
            data_inicio=self.entry_data_ini.get(),
            data_fim=self.entry_data_fim.get(),
        )
        self._atualizar_tabela(df)
        self._atualizar_status(f"Filtro aplicado: {len(df)} resultado(s)")

    def _limpar_filtros(self):
        self.entry_paciente.delete(0, tk.END)
        self.entry_analito.delete(0, tk.END)
        self.entry_data_ini.delete(0, tk.END)
        self.entry_data_fim.delete(0, tk.END)
        self.combo_status.set("TODOS")
        self._atualizar_tabela()
        self._atualizar_status("Filtros limpos")

    def _buscar_alterados(self):
        janela = tk.Toplevel(self.root)
        janela.title("Procurar Analitos Alterados")
        janela.geometry("420x210")
        janela.transient(self.root)
        janela.grab_set()

        frame = ttk.Frame(janela, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Filtro de Analito (opcional):").pack(anchor=tk.W, pady=4)
        entry_analito = ttk.Entry(frame, width=45)
        entry_analito.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text="Filtro de Paciente (opcional):").pack(anchor=tk.W, pady=4)
        entry_paciente = ttk.Entry(frame, width=45)
        entry_paciente.pack(fill=tk.X, pady=2)

        def executar_busca():
            df_alt = self.gerenciador.buscar_analitos_alterados(
                filtro_analito=entry_analito.get(),
                nome_paciente=entry_paciente.get()
            )
            self._atualizar_tabela(df_alt)
            self._atualizar_status(f"Analitos alterados encontrados: {len(df_alt)}")
            janela.destroy()

        frame_botoes = ttk.Frame(frame)
        frame_botoes.pack(fill=tk.X, pady=12)
        ttk.Button(frame_botoes, text="Procurar",  command=executar_busca, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="Cancelar",  command=janela.destroy,  width=15).pack(side=tk.LEFT, padx=5)

    def _atualizar_dados(self):
        if self.gerenciador.carregar_dados():
            self._limpar_filtros()
            messagebox.showinfo("Sucesso", "Dados recarregados com sucesso!")
        else:
            messagebox.showerror("Erro", "Não foi possível carregar dados.\n"
                                         "Verifique se 'exames.db' existe nesta pasta.")

    def _exportar_resultados(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("Aviso", "Nenhum resultado na tabela para exportar.")
            return

        colunas = ["Arquivo", "Paciente", "Pedido", "Analito",
                   "Valor", "Unidade", "Referencia", "Status", "Motivo", "Registrado Em"]
        dados_export = [
            dict(zip(colunas, self.tree.item(i)["values"])) for i in items
        ]
        df_export = pd.DataFrame(dados_export)

        arquivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")]
        )
        if arquivo:
            try:
                if arquivo.endswith(".xlsx"):
                    df_export.to_excel(arquivo, index=False, sheet_name="exames")
                else:
                    df_export.to_csv(arquivo, index=False, encoding="utf-8-sig")
                messagebox.showinfo("Sucesso", f"Arquivo salvo: {arquivo}")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao salvar: {e}")


# ===========================
# FUNÇÃO PRINCIPAL
# ===========================
def main():
    root = tk.Tk()
    app = AplicacaoBuscaExames(root)
    root.mainloop()


if __name__ == "__main__":
    main()
