"""
Wrapper para executar processaexames.py com opção de interface gráfica ou CLI
Mantém compatibilidade com execução anterior + adiciona interface Tkinter
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
import subprocess
import os


class DialogoConfiguracaoProcessamento:
    """Diálogo para configurar parâmetros de processamento"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Configurar Processamento de Exames")
        self.root.geometry("500x400")
        self.root.transient(root)
        self.root.grab_set()
        
        self.resultado = None
        
        self._criar_widgets()
    
    def _criar_widgets(self):
        """Cria widgets do diálogo"""
        
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        ttk.Label(
            frame,
            text="Configuração de Processamento",
            font=("Helvetica", 12, "bold")
        ).pack(pady=10)
        
        # Data Inicial
        ttk.Label(frame, text="Data Inicial (YYYY-MM-DD):").pack(anchor=tk.W, pady=(10, 5))
        self.entry_data_ini = ttk.Entry(frame)
        self.entry_data_ini.insert(0, str(date.today()))
        self.entry_data_ini.pack(fill=tk.X, pady=(0, 10))
        
        # Data Final
        ttk.Label(frame, text="Data Final (YYYY-MM-DD):").pack(anchor=tk.W, pady=(10, 5))
        self.entry_data_fim = ttk.Entry(frame)
        self.entry_data_fim.insert(0, str(date.today()))
        self.entry_data_fim.pack(fill=tk.X, pady=(0, 10))
        
        # Checkbox apenas não lidos
        self.var_nao_lidos = tk.BooleanVar(value=True)
        self.check_nao_lidos = ttk.Checkbutton(
            frame,
            text="Baixar apenas NÃO LIDOS",
            variable=self.var_nao_lidos
        )
        self.check_nao_lidos.pack(anchor=tk.W, pady=10)
        
        # Área de informação
        info_text = """
Configurar os parâmetros de processamento:
• Data Inicial: Primeiro dia a processar
• Data Final: Último dia a processar  
• Não Lidos: Se marcado, processa apenas e-mails não lidos
        """
        
        text_info = tk.Text(frame, height=7, width=50)
        text_info.insert(tk.END, info_text.strip())
        text_info.config(state=tk.DISABLED)
        text_info.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Botões
        frame_botoes = ttk.Frame(frame)
        frame_botoes.pack(fill=tk.X, pady=10)
        
        ttk.Button(
            frame_botoes,
            text="Processar",
            command=self._validar
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            frame_botoes,
            text="Cancelar",
            command=self.root.destroy
        ).pack(side=tk.LEFT, padx=5)
    
    def _validar(self):
        """Valida dados inseridos"""
        try:
            data_ini_str = self.entry_data_ini.get().strip()
            data_fim_str = self.entry_data_fim.get().strip()
            
            data_ini = datetime.strptime(data_ini_str, "%Y-%m-%d").date()
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
            
            if data_fim < data_ini:
                raise ValueError("Data final não pode ser anterior à data inicial")
            
            self.resultado = {
                "data_ini": data_ini_str,
                "data_fim": data_fim_str,
                "nao_lidos": self.var_nao_lidos.get()
            }
            
            self.root.destroy()
        except ValueError as e:
            messagebox.showerror("Erro", str(e))


def criar_entrada_gui(root, prompt: str):
    """Cria diálogo GUI para entrada de dados"""
    
    dialog = tk.Toplevel(root)
    dialog.title("Entrada")
    dialog.geometry("400x150")
    
    resultado = [None]
    
    ttk.Label(dialog, text=prompt).pack(pady=10)
    
    entry = ttk.Entry(dialog, width=40)
    entry.pack(pady=10, padx=10)
    entry.focus()
    
    def ok():
        resultado[0] = entry.get()
        dialog.destroy()
    
    def cancelar():
        dialog.destroy()
    
    ttk.Button(dialog, text="OK", command=ok).pack(side=tk.LEFT, padx=10, pady=10)
    ttk.Button(dialog, text="Cancelar", command=cancelar).pack(side=tk.LEFT, padx=10)
    
    root.wait_window(dialog)
    return resultado[0]


def processar_com_gui():
    """Executa processamento de exames com interface gráfica"""
    
    # Cria janela raiz (invisível)
    root = tk.Tk()
    root.withdraw()
    
    # Pergunta se deseja usar GUI ou CLI
    resultado = messagebox.askyesno(
        "Interface de Processamento",
        "Deseja configurar via interface gráfica?\n\n"
        "Sim = Interface Gráfica\n"
        "Não = Entrada via terminal (CLI)"
    )
    
    if resultado:
        # GUI
        root.deiconify()
        
        dialog = tk.Toplevel(root)
        config = DialogoConfiguracaoProcessamento(dialog)
        root.wait_window(dialog)
        
        if config.resultado:
            # Executa processaexames.py com simulação de entrada
            print("\nParâmetros de processamento:")
            print(f"  Data Inicial: {config.resultado['data_ini']}")
            print(f"  Data Final: {config.resultado['data_fim']}")
            print(f"  Apenas Não Lidos: {'Sim' if config.resultado['nao_lidos'] else 'Não'}")
            print("\nPara executar o processamento com estes parâmetros:")
            print("  1. Execute: python processaexames.py")
            print("  2. Digite as datas quando solicitado")
            print("  3. Respond 's' para opção de não lidos")
        
        root.destroy()
    else:
        # CLI - executa processaexames.py normalmente
        root.destroy()
        print("\nIniciando processamento com entrada via terminal...")
        
        # Importa e executa main de processaexames
        # Nota: isso assumirá que processaexames.py está no mesmo diretório
        try:
            import processaexames
            processaexames.main()
        except ImportError:
            print("Erro: processaexames.py não encontrado no diretório atual")
            sys.exit(1)


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Processador de Exames com Interface Gráfica"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Usar apenas CLI (sem GUI)"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Forçar uso de GUI"
    )
    parser.add_argument(
        "--buscar",
        action="store_true",
        help="Abrir interface de busca"
    )
    
    args = parser.parse_args()
    
    if args.buscar:
        # Abre interface de busca
        try:
            from gui_buscar_exames import AplicacaoBuscaExames
            root = tk.Tk()
            app = AplicacaoBuscaExames(root)
            root.mainloop()
        except ImportError:
            print("Erro: gui_buscar_exames.py não encontrado")
            sys.exit(1)
    
    elif args.cli:
        # Força CLI
        try:
            import processaexames
            processaexames.main()
        except ImportError:
            print("Erro: processaexames.py não encontrado")
            sys.exit(1)
    
    elif args.gui or (not args.cli and not args.buscar):
        # GUI ou padrão
        try:
            processar_com_gui()
        except ImportError as e:
            print(f"Erro: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
