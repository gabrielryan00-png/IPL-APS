"""
Interface Tkinter Avançada: Análise de Exames e Visualização de Dados
Interface visual completa com aba para análise detalhada de analitos alterados
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import os
from datetime import datetime, date, timedelta
from threading import Thread
import sys
from gui_buscar_exames import GerenciadorExames

# Importa funções do módulo de processamento (comentado para não executar na importação)
# Para usar: descomente imports e reustle processaexames nas funções necessárias

class ProcessadorComGUI:
    """Gerencia o processamento de exames via interface gráfica"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Processador de Exames com Interface")
        self.root.geometry("600x500")
        
        self.processando = False
        self._criar_interface()
    
    def _criar_interface(self):
        """Cria interface para configuração de processamento"""
        
        # Frame principal
        frame_principal = ttk.Frame(self.root, padding=15)
        frame_principal.pack(fill=tk.BOTH, expand=True)
        
        # Título
        ttk.Label(
            frame_principal,
            text="Processador de Exames",
            font=("Helvetica", 16, "bold")
        ).pack(pady=10)
        
        # ===== SEÇÃO DE DATAS =====
        frame_datas = ttk.LabelFrame(frame_principal, text="Configuração de Datas", padding=10)
        frame_datas.pack(fill=tk.X, pady=10)
        
        # Data inicial
        ttk.Label(frame_datas, text="Data Inicial (YYYY-MM-DD):").pack(anchor=tk.W, pady=5)
        self.entry_data_ini = ttk.Entry(frame_datas)
        self.entry_data_ini.insert(0, str(date.today()))
        self.entry_data_ini.pack(fill=tk.X, pady=5)
        
        # Data final
        ttk.Label(frame_datas, text="Data Final (YYYY-MM-DD):").pack(anchor=tk.W, pady=5)
        self.entry_data_fim = ttk.Entry(frame_datas)
        self.entry_data_fim.insert(0, str(date.today()))
        self.entry_data_fim.pack(fill=tk.X, pady=5)
        
        # ===== SEÇÃO DE OPÇÕES =====
        frame_opcoes = ttk.LabelFrame(frame_principal, text="Opções", padding=10)
        frame_opcoes.pack(fill=tk.X, pady=10)
        
        self.var_nao_lidos = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame_opcoes,
            text="Baixar apenas NÃO LIDOS",
            variable=self.var_nao_lidos
        ).pack(anchor=tk.W, pady=5)
        
        # ===== SEÇÃO DE PROCESSAMENTO =====
        frame_proc = ttk.LabelFrame(frame_principal, text="Status", padding=10)
        frame_proc.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Text widget para logs
        self.text_log = tk.Text(frame_proc, height=12, width=70)
        self.text_log.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(self.text_log)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_log.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.text_log.yview)
        
        # Barra de progresso
        self.progress = ttk.Progressbar(
            frame_proc,
            mode='indeterminate'
        )
        self.progress.pack(fill=tk.X, pady=10)
        
        # ===== FRAME BOTÕES =====
        frame_botoes = ttk.Frame(frame_principal)
        frame_botoes.pack(fill=tk.X, pady=10)
        
        self.btn_processar = ttk.Button(
            frame_botoes,
            text="▶ Processar Exames",
            command=self._iniciar_processamento
        )
        self.btn_processar.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            frame_botoes,
            text="🔍 Abrir Buscador",
            command=self._abrir_buscador
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            frame_botoes,
            text="📂 Abrir Pasta",
            command=self._abrir_pasta_exames
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            frame_botoes,
            text="❌ Sair",
            command=self.root.quit
        ).pack(side=tk.LEFT, padx=5)
    
    def _escrever_log(self, mensagem: str):
        """Escreve mensagem no text widget de log"""
        self.text_log.insert(tk.END, f"{mensagem}\n")
        self.text_log.see(tk.END)
        self.root.update()
    
    def _limpar_log(self):
        """Limpa o log"""
        self.text_log.delete(1.0, tk.END)
    
    def _validar_datas(self) -> tuple:
        """Valida datas inseridas"""
        try:
            data_ini_str = self.entry_data_ini.get().strip()
            data_fim_str = self.entry_data_fim.get().strip()
            
            data_ini = datetime.strptime(data_ini_str, "%Y-%m-%d").date() if data_ini_str else date.today()
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date() if data_fim_str else date.today()
            
            if data_fim < data_ini:
                raise ValueError("Data final não pode ser menor que data inicial")
            
            return data_ini, data_fim
        except Exception as e:
            messagebox.showerror("Erro de Data", f"Formato inválido: {e}")
            return None, None
    
    def _iniciar_processamento(self):
        """Inicia processamento em thread separada"""
        if self.processando:
            messagebox.showwarning("Aviso", "Processamento já em andamento")
            return
        
        datas = self._validar_datas()
        if datas[0] is None:
            return
        
        self.processando = True
        self.btn_processar.config(state=tk.DISABLED)
        self.progress.start()
        self._limpar_log()
        
        # Inicia processamento em thread
        thread = Thread(target=self._executar_processamento, args=datas)
        thread.daemon = True
        thread.start()
    
    def _executar_processamento(self, data_ini: date, data_fim: date):
        """Executa processamento (rodaria processaexames.py aqui)"""
        try:
            self._escrever_log("=" * 50)
            self._escrever_log("PROCESSADOR DE EXAMES")
            self._escrever_log("=" * 50)
            self._escrever_log(f"Data Inicial: {data_ini}")
            self._escrever_log(f"Data Final: {data_fim}")
            self._escrever_log(f"Apenas não lidos: {self.var_nao_lidos.get()}")
            self._escrever_log("")
            
            self._escrever_log("⚠️  Nota: Para executar o processamento completo,")
            self._escrever_log("use o comando: python processaexames.py")
            self._escrever_log("")
            self._escrever_log("Você pode:")
            self._escrever_log("1. Executar processaexames.py no terminal")
            self._escrever_log("2. Usar o botão 'Abrir Buscador' para visualizar dados processados")
            self._escrever_log("")
            
            import os
            if os.path.exists("relatorio_exames.xlsx"):
                self._escrever_log("✅ Relatório encontrado: relatorio_exames.xlsx")
                self._escrever_log("Clique em 'Abrir Buscador' para visualizar os dados")
            else:
                self._escrever_log("⚠️  relatorio_exames.xlsx não encontrado")
                self._escrever_log("Execute processaexames.py para processar e-mails")
            
            self._escrever_log("")
            self._escrever_log("=" * 50)
            
        except Exception as e:
            self._escrever_log(f"❌ Erro: {e}")
        finally:
            self.processando = False
            self.btn_processar.config(state=tk.NORMAL)
            self.progress.stop()
    
    def _abrir_buscador(self):
        """Abre a janela de buscador de exames"""
        try:
            from gui_buscar_exames import AplicacaoBuscaExames
            
            janela_busca = tk.Toplevel(self.root)
            app_busca = AplicacaoBuscaExames(janela_busca)
        except ImportError:
            messagebox.showerror(
                "Erro",
                "Não foi possível importar o módulo de busca.\nCertifique-se que gui_buscar_exames.py está no mesmo diretório."
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir buscador: {e}")
    
    def _abrir_pasta_exames(self):
        """Abre a pasta de exames no gerenciador de arquivos"""
        try:
            pasta = os.path.abspath("exames")
            if not os.path.exists(pasta):
                os.makedirs(pasta, exist_ok=True)
            
            import subprocess
            import platform
            
            if platform.system() == "Linux":
                subprocess.Popen(["xdg-open", pasta])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", pasta])
            elif platform.system() == "Windows":
                os.startfile(pasta)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir pasta: {e}")


class AplicacaoBuscaExames:
    """Interface Tkinter para busca e visualização de exames"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Buscar Exames")
        self.root.geometry("1200x700")
        
        self.df_exames = None
        self._carregar_dados()
        
        if self.df_exames is None:
            messagebox.showwarning(
                "Aviso",
                "Nenhum relatório encontrado."
            )
            self.root.after(1000, self.root.destroy)
            return
        
        self._criar_widgets()
        self._atualizar_tabela()
    
    def _carregar_dados(self):
        """Carrega dados do arquivo Excel"""
        try:
            if not os.path.exists("relatorio_exames.xlsx"):
                return
            
            xls = pd.ExcelFile("relatorio_exames.xlsx")
            if "exames" in xls.sheet_names:
                self.df_exames = pd.read_excel("relatorio_exames.xlsx", sheet_name="exames")
        except Exception as e:
            print(f"Erro ao carregar dados: {e}")
    
    def _criar_widgets(self):
        """Cria widgets da interface"""
        
        frame_controles = ttk.LabelFrame(self.root, text="Filtros", padding=10)
        frame_controles.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(frame_controles, text="Paciente:").grid(row=0, column=0, sticky=tk.W)
        self.entry_paciente = ttk.Entry(frame_controles, width=25)
        self.entry_paciente.grid(row=0, column=1, padx=5)
        self.entry_paciente.bind("<KeyRelease>", lambda e: self._aplicar_filtros())
        
        ttk.Label(frame_controles, text="Analito:").grid(row=0, column=2, sticky=tk.W)
        self.entry_analito = ttk.Entry(frame_controles, width=25)
        self.entry_analito.grid(row=0, column=3, padx=5)
        self.entry_analito.bind("<KeyRelease>", lambda e: self._aplicar_filtros())
        
        ttk.Label(frame_controles, text="Status:").grid(row=0, column=4, sticky=tk.W)
        self.combo_status = ttk.Combobox(
            frame_controles,
            values=["TODOS", "ALTERADO", "NORMAL", "REVISAR"],
            width=15,
            state="readonly"
        )
        self.combo_status.set("TODOS")
        self.combo_status.grid(row=0, column=5, padx=5)
        self.combo_status.bind("<<ComboboxSelected>>", lambda e: self._aplicar_filtros())
        
        frame_botoes = ttk.Frame(frame_controles)
        frame_botoes.grid(row=1, column=0, columnspan=6, sticky=tk.EW, pady=10)
        
        ttk.Button(frame_botoes, text="Limpar", command=self._limpar_filtros).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="Alterdados", command=self._buscar_alterados).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes, text="Exportar", command=self._exportar).pack(side=tk.LEFT, padx=5)
        
        # Treeview
        frame_tabela = ttk.Frame(self.root)
        frame_tabela.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(frame_tabela)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        colunas = ["Paciente", "Analito", "Valor", "Referencia", "Status"]
        self.tree = ttk.Treeview(frame_tabela, columns=colunas, height=25, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tree.yview)
        
        self.tree.column("#0", width=0)
        for col in colunas:
            self.tree.column(col, width=150)
            self.tree.heading(col, text=col)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure("alterado", foreground="red")
    
    def _atualizar_tabela(self, df=None):
        """Atualiza tabela"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if df is None:
            df = self.df_exames
        
        if df is None or df.empty:
            return
        
        for idx, row in df.iterrows():
            status = str(row.get("Status", "")).upper()
            tags = ("alterado",) if "ALTERADO" in status else ()
            
            self.tree.insert("", tk.END, values=[
                row.get("Paciente", ""),
                row.get("Analito", ""),
                str(row.get("Valor", "")),
                row.get("Referencia", ""),
                row.get("Status", "")
            ], tags=tags)
    
    def _aplicar_filtros(self):
        """Aplica filtros"""
        if self.df_exames is None:
            return
        
        df = self.df_exames.copy()
        
        paciente = self.entry_paciente.get()
        if paciente:
            df = df[df["Paciente"].astype(str).str.contains(paciente, case=False, na=False)]
        
        analito = self.entry_analito.get()
        if analito:
            df = df[df["Analito"].astype(str).str.contains(analito, case=False, na=False)]
        
        status = self.combo_status.get()
        if status != "TODOS":
            df = df[df["Status"].astype(str).str.contains(status, case=False, na=False)]
        
        self._atualizar_tabela(df)
    
    def _limpar_filtros(self):
        """Limpa filtros"""
        self.entry_paciente.delete(0, tk.END)
        self.entry_analito.delete(0, tk.END)
        self.combo_status.set("TODOS")
        self._atualizar_tabela()
    
    def _buscar_alterados(self):
        """Busca apenas alterados"""
        if self.df_exames is None:
            return
        df_alt = self.df_exames[self.df_exames["Status"].astype(str).str.contains("ALTERADO", na=False)]
        self._atualizar_tabela(df_alt)
    
    def _exportar(self):
        """Exporta resultados"""
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("Aviso", "Nenhum resultado")
            return
        
        arquivo = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if arquivo:
            try:
                dados = []
                for item in items:
                    valores = self.tree.item(item)["values"]
                    dados.append(dict(zip(["Paciente", "Analito", "Valor", "Referencia", "Status"], valores)))
                
                pd.DataFrame(dados).to_excel(arquivo, index=False)
                messagebox.showinfo("Sucesso", f"Salvo: {arquivo}")
            except Exception as e:
                messagebox.showerror("Erro", str(e))


def main():
    root = tk.Tk()
    app = ProcessadorComGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
