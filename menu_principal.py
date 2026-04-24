#!/usr/bin/env python3
"""
MENU PRINCIPAL - Interface Tkinter para Busca de Exames

Banco SQLite (exames.db) como fonte principal de análise.
Excel gerado como exportação secundária e pode ser removido quando redundante.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sqlite3
import threading
import queue
from datetime import date
import sys

DB_PATH = "exames.db"
RELATORIO_XLSX = "relatorio_exames.xlsx"


def _status_banco() -> tuple:
    """
    Retorna (texto_status, tem_banco, tem_excel).
    Texto indica o estado atual do banco SQLite.
    """
    tem_db  = os.path.exists(DB_PATH)
    tem_xls = os.path.exists(RELATORIO_XLSX)
    if not tem_db:
        return "⚠️ Banco não encontrado — processe e-mails primeiro", False, tem_xls
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            total = cur.execute("SELECT COUNT(*) FROM exames").fetchone()[0]
            pacs  = cur.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
            alt   = cur.execute(
                "SELECT COUNT(*) FROM exames WHERE status LIKE '%ALTERADO%'"
            ).fetchone()[0]
            pend  = cur.execute(
                "SELECT COUNT(*) FROM exames WHERE pendencia = 'SIM'"
            ).fetchone()[0]
        txt = (f"🗄️  {pacs} pacientes · {total} exames · "
               f"{alt} alterados · {pend} pendências")
        return txt, True, tem_xls
    except Exception:
        return f"🗄️ {DB_PATH} encontrado (leitura falhou)", True, tem_xls


class MenuPrincipal:
    """Menu interativo para acesso a todas as ferramentas"""

    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Exames - Menu Principal")
        self.root.geometry("720x730")

        style = ttk.Style()
        style.theme_use("clam")

        self._criar_interface()

    def _criar_interface(self):

        # ===== HEADER =====
        frame_header = ttk.Frame(self.root)
        frame_header.pack(fill=tk.X, padx=20, pady=(20, 5))

        ttk.Label(
            frame_header,
            text="🏥 Sistema de Busca de Exames",
            font=("Helvetica", 18, "bold")
        ).pack()

        ttk.Label(
            frame_header,
            text="Banco de dados SQLite como fonte principal de análise",
            font=("Helvetica", 10)
        ).pack()

        # ===== PAINEL DE STATUS DO BANCO =====
        frame_status = ttk.LabelFrame(self.root, text="Banco SQLite", padding=8)
        frame_status.pack(fill=tk.X, padx=20, pady=(5, 0))

        txt, tem_db, tem_xls = _status_banco()
        self._tem_db  = tem_db
        self._tem_xls = tem_xls

        self.label_status_banco = ttk.Label(
            frame_status, text=txt,
            font=("Helvetica", 9),
            foreground="#336699" if tem_db else "#cc0000"
        )
        self.label_status_banco.pack(anchor=tk.W)

        # Aviso se Excel ainda existe e SQLite está populado
        self.label_excel_aviso = ttk.Label(
            frame_status,
            text=(f"📊 '{RELATORIO_XLSX}' ainda existe — "
                  "use 'Consolidar' para removê-lo após verificar os dados.")
            if tem_db and tem_xls else "",
            font=("Helvetica", 8), foreground="#995500"
        )
        self.label_excel_aviso.pack(anchor=tk.W)

        # ===== OPÇÕES =====
        frame_opcoes = ttk.LabelFrame(self.root, text="O que deseja fazer?", padding=12)
        frame_opcoes.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        self._criar_botao_opcao(
            frame_opcoes,
            "📧 Processar E-mails",
            "Baixar e processar novos exames do Gmail — salva no banco SQLite",
            self._processar_exames
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "📈 Análise Avançada  (Dashboard + Prevalência)",
            "Dashboard, prevalência de analitos, alterados, filtros e exportação",
            self._abrir_interface_avancada
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "🔍 Buscar Exames",
            "Busca com filtros por paciente, analito, status e datas",
            self._abrir_busca
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "🗂️ Auditar Banco SQLite",
            "Inspecionar diretamente o banco — todos os registros com filtros em tempo real",
            self._auditar_banco
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "🔴 Procurar Alterados  (acesso rápido)",
            "Localizar exames com resultado alterado por analito ou paciente",
            self._procurar_alterados
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "🌐 IPL-APS — Dashboard Web",
            "Abrir dashboard de prioridade laboratorial no browser (porta 8765)",
            self._abrir_ipl_aps
        ).pack(fill=tk.X, pady=5)

        self._criar_botao_opcao(
            frame_opcoes,
            "⚙️ Instalar Dependências",
            "Instalar todos os pacotes Python necessários",
            self._instalar_deps
        ).pack(fill=tk.X, pady=5)

        # ===== FOOTER =====
        frame_footer = ttk.Frame(self.root)
        frame_footer.pack(fill=tk.X, padx=20, pady=8)

        ttk.Button(
            frame_footer, text="❌ Sair",
            command=self.root.quit, width=20
        ).pack(side=tk.RIGHT)

        ttk.Button(
            frame_footer, text="🔁 Atualizar",
            command=self._atualizar_status, width=18
        ).pack(side=tk.LEFT)

        ttk.Button(
            frame_footer, text="📖 Documentação",
            command=self._abrir_documentacao, width=20
        ).pack(side=tk.LEFT, padx=10)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _criar_botao_opcao(self, parent, titulo, descricao, comando):
        frame = ttk.Frame(parent, relief=tk.SUNKEN, borderwidth=1)

        frame_texto = ttk.Frame(frame)
        frame_texto.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        lbl_titulo = ttk.Label(frame_texto, text=titulo, font=("Helvetica", 11, "bold"))
        lbl_titulo.pack(anchor=tk.W)
        lbl_desc = ttk.Label(frame_texto, text=descricao, font=("Helvetica", 9), foreground="gray")
        lbl_desc.pack(anchor=tk.W)

        for widget in [frame, frame_texto, lbl_titulo, lbl_desc]:
            widget.bind("<Button-1>", lambda e, c=comando: c())
            widget.bind("<Enter>",    lambda e, f=frame: self._on_enter(f))
            widget.bind("<Leave>",    lambda e, f=frame: self._on_leave(f))

        frame.config(cursor="hand2")
        return frame

    def _on_enter(self, frame):
        try:
            frame.config(background="#E8F4F8")
        except Exception:
            pass

    def _on_leave(self, frame):
        try:
            frame.config(background="")
        except Exception:
            pass

    def _atualizar_status(self):
        txt, tem_db, tem_xls = _status_banco()
        self._tem_db  = tem_db
        self._tem_xls = tem_xls
        self.label_status_banco.config(
            text=txt,
            foreground="#336699" if tem_db else "#cc0000"
        )
        self.label_excel_aviso.config(
            text=(f"📊 '{RELATORIO_XLSX}' ainda existe — "
                  "use 'Consolidar' para removê-lo após verificar os dados.")
            if tem_db and tem_xls else ""
        )

    # ------------------------------------------------------------------
    # AÇÕES
    # ------------------------------------------------------------------
    def _instalar_deps(self):
        try:
            cmd = ["python" if sys.platform == "win32" else "python3", "instalar_dependencias.py"]
            subprocess.Popen(cmd)
            messagebox.showinfo("Instalação", "Janela de instalação aberta.\nAguarde a conclusão...")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao instalar: {e}")

    def _abrir_busca(self):
        """Abre a interface de busca (SQLite + Excel)."""
        try:
            from gui_buscar_exames import AplicacaoBuscaExames
            janela = tk.Toplevel(self.root)
            AplicacaoBuscaExames(janela)
        except ImportError:
            messagebox.showerror("Erro", "gui_buscar_exames.py não encontrado")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir busca: {e}")

    def _abrir_interface_avancada(self):
        try:
            from interface_exames_avancada import AnalisadorExamesAvancado
            janela = tk.Toplevel(self.root)
            AnalisadorExamesAvancado(janela)
        except ImportError:
            messagebox.showerror("Erro", "interface_exames_avancada.py não encontrado")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir interface: {e}")

    def _auditar_banco(self):
        """Abre janela de auditoria do banco SQLite."""
        if not os.path.exists(DB_PATH):
            messagebox.showwarning(
                "Banco não encontrado",
                f"O banco '{DB_PATH}' ainda não existe.\n"
                "Execute 'Processar E-mails' primeiro para criá-lo."
            )
            return

        janela = tk.Toplevel(self.root)
        janela.title(f"Auditoria — {DB_PATH}")
        janela.geometry("860x560")
        janela.transient(self.root)

        # --- barra de filtros ---
        frame_filtros = ttk.LabelFrame(janela, text="Filtros", padding=8)
        frame_filtros.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(frame_filtros, text="Paciente:").grid(row=0, column=0, sticky=tk.W, padx=4)
        entry_pac = ttk.Entry(frame_filtros, width=25)
        entry_pac.grid(row=0, column=1, padx=4)

        ttk.Label(frame_filtros, text="Analito:").grid(row=0, column=2, sticky=tk.W, padx=4)
        entry_ana = ttk.Entry(frame_filtros, width=20)
        entry_ana.grid(row=0, column=3, padx=4)

        ttk.Label(frame_filtros, text="Status:").grid(row=0, column=4, sticky=tk.W, padx=4)
        combo_status = ttk.Combobox(
            frame_filtros, width=16,
            values=["(todos)", "NORMAL", "ALTERADO", "REVISAR"],
            state="readonly"
        )
        combo_status.set("(todos)")
        combo_status.grid(row=0, column=5, padx=4)

        ttk.Label(frame_filtros, text="Pendência:").grid(row=0, column=6, sticky=tk.W, padx=4)
        combo_pend = ttk.Combobox(
            frame_filtros, width=8,
            values=["(todas)", "SIM", "NÃO"],
            state="readonly"
        )
        combo_pend.set("(todas)")
        combo_pend.grid(row=0, column=7, padx=4)

        # --- tabela de resultados ---
        frame_tabela = ttk.Frame(janela)
        frame_tabela.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        colunas = ("Paciente", "Analito", "Valor", "Unidade", "Referencia", "Status", "Pendencia", "Data")
        tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=18)
        larguras = (160, 160, 70, 60, 130, 110, 80, 140)
        for col, larg in zip(colunas, larguras):
            tree.heading(col, text=col)
            tree.column(col, width=larg, anchor=tk.W)

        scroll_y = ttk.Scrollbar(frame_tabela, orient=tk.VERTICAL, command=tree.yview)
        scroll_x = ttk.Scrollbar(frame_tabela, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        frame_tabela.rowconfigure(0, weight=1)
        frame_tabela.columnconfigure(0, weight=1)

        # label de contagem
        label_count = ttk.Label(janela, text="", font=("Helvetica", 9))
        label_count.pack(anchor=tk.W, padx=12)

        def _cor_linha(status: str) -> str:
            s = status.upper()
            if "ALTERADO" in s:
                return "alterado"
            if "REVISAR" in s:
                return "revisar"
            return ""

        tree.tag_configure("alterado", foreground="#cc0000")
        tree.tag_configure("revisar",  foreground="#cc8800")

        def buscar():
            for item in tree.get_children():
                tree.delete(item)

            filtro_pac = entry_pac.get().strip()
            filtro_ana = entry_ana.get().strip()
            filtro_sta = combo_status.get()
            filtro_pen = combo_pend.get()

            query = """
                SELECT p.nome, e.analito, e.valor, e.unidade,
                       e.referencia, e.status, e.pendencia, e.registrado_em
                FROM exames e
                LEFT JOIN pacientes p ON e.paciente_id = p.id
                WHERE 1=1
            """
            params = []
            if filtro_pac:
                query += " AND p.nome LIKE ?"
                params.append(f"%{filtro_pac}%")
            if filtro_ana:
                query += " AND e.analito LIKE ?"
                params.append(f"%{filtro_ana}%")
            if filtro_sta != "(todos)":
                query += " AND e.status LIKE ?"
                params.append(f"%{filtro_sta}%")
            if filtro_pen != "(todas)":
                query += " AND e.pendencia = ?"
                params.append(filtro_pen)
            query += " ORDER BY e.registrado_em DESC LIMIT 2000"

            try:
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.execute(query, params)
                    rows = cur.fetchall()
            except Exception as ex:
                messagebox.showerror("Erro SQL", str(ex))
                return

            for row in rows:
                tag = _cor_linha(row[5] or "")
                tree.insert("", tk.END, values=row, tags=(tag,))

            label_count.config(text=f"{len(rows)} registro(s) encontrado(s)")

        ttk.Button(frame_filtros, text="🔍 Buscar", command=buscar, width=10).grid(row=0, column=8, padx=8)

        # carrega tudo ao abrir
        buscar()

    def _procurar_alterados(self):
        """Busca rápida de alterados no banco SQLite."""
        if not os.path.exists(DB_PATH):
            messagebox.showwarning(
                "Banco não encontrado",
                "Execute 'Processar E-mails' primeiro."
            )
            return

        try:
            from gui_buscar_exames import GerenciadorExames

            janela_dialog = tk.Toplevel(self.root)
            janela_dialog.title("Procurar Alterados")
            janela_dialog.geometry("440x240")
            janela_dialog.transient(self.root)
            janela_dialog.grab_set()

            frame = ttk.Frame(janela_dialog, padding=15)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text="Filtro de Analito (opcional):").pack(
                anchor=tk.W, pady=4)
            entry_analito = ttk.Entry(frame, width=45)
            entry_analito.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text="Filtro de Paciente (opcional):").pack(
                anchor=tk.W, pady=4)
            entry_paciente = ttk.Entry(frame, width=45)
            entry_paciente.pack(fill=tk.X, pady=2)

            def fazer_busca():
                gerenciador = GerenciadorExames(db_path=DB_PATH,
                                                caminho_relatorio=RELATORIO_XLSX)
                df = gerenciador.buscar_analitos_alterados(
                    filtro_analito=entry_analito.get(),
                    nome_paciente=entry_paciente.get()
                )
                mensagem = f"Encontrados {len(df)} analito(s) alterado(s)\n\n"
                if not df.empty:
                    mensagem += "Primeiros 10:\n"
                    for _, row in df.head(10).iterrows():
                        mensagem += (f"• {row.get('Paciente','?')}: "
                                     f"{row.get('Analito','?')} = "
                                     f"{row.get('Valor','?')}\n")
                messagebox.showinfo("Resultados", mensagem)
                janela_dialog.destroy()

            frame_botoes = ttk.Frame(frame)
            frame_botoes.pack(fill=tk.X, pady=14)
            ttk.Button(frame_botoes, text="Procurar",
                       command=fazer_busca, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Cancelar",
                       command=janela_dialog.destroy, width=15).pack(
                           side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao procurar alterados: {e}")

    def _consolidar_excluir_excel(self):
        """Verifica se SQLite tem dados e oferece remover o Excel redundante."""
        try:
            from gui_buscar_exames import GerenciadorExames
            g = GerenciadorExames(db_path=DB_PATH, caminho_relatorio=RELATORIO_XLSX)
            pode, motivo = g.pode_excluir_excel()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        if not pode:
            messagebox.showinfo("Consolidar", motivo)
            return

        resposta = messagebox.askyesno(
            "Consolidar — Remover Excel",
            f"{motivo}\n\n"
            f"Deseja excluir '{RELATORIO_XLSX}'?\n\n"
            "O banco SQLite continuará sendo a fonte principal.\n"
            "Você pode gerar um novo Excel a qualquer momento\n"
            "processando os e-mails novamente.",
            icon="warning"
        )
        if not resposta:
            return

        try:
            os.remove(RELATORIO_XLSX)
            self._atualizar_status()
            messagebox.showinfo(
                "Concluído",
                f"'{RELATORIO_XLSX}' removido.\n"
                f"O banco '{DB_PATH}' permanece como fonte principal."
            )
        except Exception as e:
            messagebox.showerror("Erro ao remover", str(e))

    def _abrir_ipl_aps(self):
        try:
            from servidor_ipl import iniciar
            _, url = iniciar(abrir_browser=True)
            messagebox.showinfo(
                "IPL-APS",
                f"Dashboard aberto em:\n{url}\n\nO servidor continuará ativo enquanto o programa estiver aberto."
            )
        except OSError as e:
            if e.errno == 98:
                import webbrowser
                webbrowser.open("http://localhost:8765/")
                messagebox.showinfo("IPL-APS", "Servidor já está rodando.\nDashboard aberto no browser.")
            else:
                messagebox.showerror("Erro", f"Erro ao abrir IPL-APS: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir IPL-APS: {e}")

    def _processar_exames(self):
        """Abre janela tkinter para configurar e executar o processamento de e-mails."""
        janela = tk.Toplevel(self.root)
        janela.title("Processar E-mails")
        janela.geometry("720x560")
        janela.transient(self.root)
        janela.resizable(True, True)

        # ── Configuração ─────────────────────────────────────────────
        frame_cfg = ttk.LabelFrame(janela, text="Configuração", padding=10)
        frame_cfg.pack(fill=tk.X, padx=14, pady=(12, 0))

        hoje = date.today().strftime("%Y-%m-%d")

        ttk.Label(frame_cfg, text="Data inicial (YYYY-MM-DD):").grid(
            row=0, column=0, sticky=tk.W, padx=6, pady=4)
        entry_ini = ttk.Entry(frame_cfg, width=14)
        entry_ini.insert(0, hoje)
        entry_ini.grid(row=0, column=1, sticky=tk.W, padx=6, pady=4)

        ttk.Label(frame_cfg, text="Data final (YYYY-MM-DD):").grid(
            row=0, column=2, sticky=tk.W, padx=6, pady=4)
        entry_fim = ttk.Entry(frame_cfg, width=14)
        entry_fim.insert(0, hoje)
        entry_fim.grid(row=0, column=3, sticky=tk.W, padx=6, pady=4)

        var_nao_lidos = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame_cfg, text="Apenas não lidos", variable=var_nao_lidos
        ).grid(row=0, column=4, padx=14, pady=4)

        # ── Log de saída ─────────────────────────────────────────────
        frame_log = ttk.LabelFrame(janela, text="Log de execução", padding=6)
        frame_log.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        txt_log = tk.Text(frame_log, font=("Courier", 9), wrap=tk.WORD,
                          state=tk.DISABLED, background="#1e1e1e",
                          foreground="#d4d4d4", insertbackground="white")
        sb_log = ttk.Scrollbar(frame_log, orient=tk.VERTICAL, command=txt_log.yview)
        txt_log.configure(yscrollcommand=sb_log.set)
        txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_log.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Barra de progresso ────────────────────────────────────────
        progresso = ttk.Progressbar(janela, mode="indeterminate")
        progresso.pack(fill=tk.X, padx=14, pady=(0, 4))

        # ── Botões ────────────────────────────────────────────────────
        frame_btn = ttk.Frame(janela)
        frame_btn.pack(fill=tk.X, padx=14, pady=(0, 10))

        btn_iniciar = ttk.Button(frame_btn, text="▶  Iniciar", width=16)
        btn_iniciar.pack(side=tk.LEFT, padx=4)
        btn_fechar = ttk.Button(frame_btn, text="Fechar", width=12,
                                command=janela.destroy)
        btn_fechar.pack(side=tk.LEFT, padx=4)

        label_status = ttk.Label(frame_btn, text="", font=("Helvetica", 9))
        label_status.pack(side=tk.LEFT, padx=10)

        # fila para comunicação thread → GUI
        fila: queue.Queue = queue.Queue()

        def _append_log(texto: str):
            """Thread-safe: enfileira linha para o Text widget."""
            fila.put(texto)

        def _poll_fila():
            """Consome a fila e atualiza o Text widget (roda na thread GUI)."""
            try:
                while True:
                    linha = fila.get_nowait()
                    txt_log.config(state=tk.NORMAL)
                    txt_log.insert(tk.END, linha + "\n")
                    txt_log.see(tk.END)
                    txt_log.config(state=tk.DISABLED)
            except queue.Empty:
                pass
            if janela.winfo_exists():
                janela.after(100, _poll_fila)

        def _executar():
            from datetime import datetime as _dt
            ini_str = entry_ini.get().strip()
            fim_str = entry_fim.get().strip()
            try:
                data_ini = _dt.strptime(ini_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Data inválida",
                                     "Data inicial inválida. Use YYYY-MM-DD.",
                                     parent=janela)
                return
            try:
                data_fim = _dt.strptime(fim_str, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Data inválida",
                                     "Data final inválida. Use YYYY-MM-DD.",
                                     parent=janela)
                return
            if data_fim < data_ini:
                messagebox.showerror("Data inválida",
                                     "Data final não pode ser menor que a inicial.",
                                     parent=janela)
                return

            btn_iniciar.config(state=tk.DISABLED)
            btn_fechar.config(state=tk.DISABLED)
            label_status.config(text="Processando...", foreground="#0066cc")
            progresso.start(12)

            def _thread():
                try:
                    import importlib, sys
                    if "processaexames" in sys.modules:
                        importlib.reload(sys.modules["processaexames"])
                    from processaexames import processar_emails
                    processar_emails(
                        data_ini,
                        data_fim,
                        var_nao_lidos.get(),
                        log=_append_log
                    )
                    fila.put("\n✅ Processamento concluído.")
                    fila.put("_DONE_OK_")
                except Exception as exc:
                    fila.put(f"\n❌ Erro: {exc}")
                    fila.put("_DONE_ERR_")

            threading.Thread(target=_thread, daemon=True).start()

        def _check_done():
            try:
                while True:
                    msg = fila.get_nowait()
                    if msg == "_DONE_OK_":
                        progresso.stop()
                        btn_iniciar.config(state=tk.NORMAL)
                        btn_fechar.config(state=tk.NORMAL)
                        label_status.config(text="Concluído!", foreground="#006600")
                        self._atualizar_status()
                        return
                    elif msg == "_DONE_ERR_":
                        progresso.stop()
                        btn_iniciar.config(state=tk.NORMAL)
                        btn_fechar.config(state=tk.NORMAL)
                        label_status.config(text="Erro — veja o log", foreground="#cc0000")
                        return
                    else:
                        txt_log.config(state=tk.NORMAL)
                        txt_log.insert(tk.END, msg + "\n")
                        txt_log.see(tk.END)
                        txt_log.config(state=tk.DISABLED)
            except queue.Empty:
                pass
            if janela.winfo_exists():
                janela.after(100, _check_done)

        btn_iniciar.config(command=lambda: [_executar(), _check_done()])

        janela.after(100, _poll_fila)

    def _abrir_documentacao(self):
        documentacao = """
DOCUMENTAÇÃO RÁPIDA
==================

BANCO DE DADOS (fonte única de análise)
========================================

exames.db  — banco SQLite, fonte principal e permanente
  • Criado/atualizado automaticamente pelo processaexames.py
  • Indexado por nome de paciente
  • Contém histórico completo de todos os processamentos

relatorio_exames.xlsx  — exportação gerada após cada processamento
  • Redundante quando o banco existe e está completo
  • Use "Consolidar" para removê-lo e manter só o banco

FLUXO RECOMENDADO
=================
1. Processar E-mails   → popula o banco SQLite
2. Análise Avançada    → Dashboard + Prevalência de analitos
3. Buscar Exames       → filtros por paciente/analito/data
4. Auditar Banco       → inspeção direta do banco
5. Consolidar          → remove Excel redundante (opcional)

ANÁLISE DE PREVALÊNCIA
======================
Mostra, para cada analito, qual % dos pacientes
que fizeram aquele exame apresentaram resultado
alterado. Cores:
  🔴 Alta prevalência  ≥ 50%
  🟠 Média prevalência 20–49%
  🟢 Baixa prevalência < 20%

BANCO SQLITE — ESTRUTURA
=========================
pacientes      (id, nome, dt_nasc, medico, criado_em)
processamentos (id, email_uid, arquivo_pdf, paciente_id, status_email)
exames         (id, paciente_id, analito, valor, unidade,
                referencia, status, pendencia, registrado_em)
"""
        janela_doc = tk.Toplevel(self.root)
        janela_doc.title("Documentação")
        janela_doc.geometry("600x500")

        text_widget = tk.Text(janela_doc, wrap=tk.WORD, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, documentacao)
        text_widget.config(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(text_widget)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=text_widget.yview)


def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = tk.Tk()
    MenuPrincipal(root)
    # Agendador automático: processa e-mails a cada 2h nos dias úteis
    from servidor_ipl import iniciar_agendador
    iniciar_agendador()
    root.mainloop()


if __name__ == "__main__":
    main()
