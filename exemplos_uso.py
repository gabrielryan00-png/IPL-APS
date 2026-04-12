"""
EXEMPLOS DE USO - Interface de Busca de Exames

Este arquivo demonstra diferentes formas de usar
a interface de busca programaticamente.
"""

# ============================================================
# EXEMPLO 1: Uso Básico da Classe GerenciadorExames
# ============================================================

def exemplo_1_basico():
    """Exemplo básico de carregamento e busca de dados"""
    print("\n" + "="*60)
    print("EXEMPLO 1: USO BÁSICO")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    
    # Cria gerenciador (carrega dados automaticamente)
    gerenciador = GerenciadorExames("relatorio_exames.xlsx")
    
    # Verifica se dados foram carregados
    if gerenciador.df_exames is None:
        print("Erro: Nenhum relatório encontrado!")
        return
    
    print(f"\nTotal de exames: {len(gerenciador.df_exames)}")
    
    # Busca simples por paciente
    df_silva = gerenciador.buscar_por_paciente("Silva")
    print(f"Exames do Silva: {len(df_silva)}")
    if not df_silva.empty:
        print(df_silva[["Paciente", "Analito", "Status"]].head())


# ============================================================
# EXEMPLO 2: Procurando Analitos Alterados
# ============================================================

def exemplo_2_analitos_alterados():
    """Exemplo: Procurar analitos alterados específicos"""
    print("\n" + "="*60)
    print("EXEMPLO 2: PROCURAR ANALITOS ALTERADOS")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    
    gerenciador = GerenciadorExames("relatorio_exames.xlsx")
    
    # 1. Todos os alterados
    print("\n1. Todos os analitos alterados:")
    df_alt = gerenciador.buscar_analitos_alterados()
    print(f"   Total: {len(df_alt)}")
    
    # 2. Alterados de um paciente específico
    print("\n2. Alterados do paciente 'Maria':")
    df_maria_alt = gerenciador.buscar_analitos_alterados(nome_paciente="Maria")
    print(f"   Total: {len(df_maria_alt)}")
    if not df_maria_alt.empty:
        for idx, row in df_maria_alt.iterrows():
            print(f"   - {row['Analito']}: {row['Valor']} (ref: {row['Referencia']})")
    
    # 3. Alterados de um tipo de analito
    print("\n3. Alterados tipo 'GLICOSE':")
    df_glicose_alt = gerenciador.buscar_analitos_alterados(filtro_analito="GLICOSE")
    print(f"   Total: {len(df_glicose_alt)}")
    
    # 4. Combinar filtros
    print("\n4. Alterados de 'HEMOGLOBINA' do 'João':")
    df_combinado = gerenciador.buscar_analitos_alterados(
        filtro_analito="HEMOGLOBINA",
        nome_paciente="João"
    )
    print(f"   Total: {len(df_combinado)}")


# ============================================================
# EXEMPLO 3: Buscas Avançadas
# ============================================================

def exemplo_3_busca_avancada():
    """Exemplo: Busca avançada com múltiplos filtros"""
    print("\n" + "="*60)
    print("EXEMPLO 3: BUSCA AVANÇADA")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    
    gerenciador = GerenciadorExames("relatorio_exames.xlsx")
    
    # Busca com múltiplos filtros
    df = gerenciador.busca_avancada(
        paciente="Silva",
        analito="GLICOSE",
        status="ALTERADO"
    )
    
    print(f"\nBusca: Paciente=Silva, Analito=GLICOSE, Status=ALTERADO")
    print(f"Resultados: {len(df)}")
    
    if not df.empty:
        print("\nDetalhes:")
        print(df[["Paciente", "Analito", "Valor", "Referencia", "Status"]].to_string())


# ============================================================
# EXEMPLO 4: Análise de Dados
# ============================================================

def exemplo_4_analise():
    """Exemplo: Análise dos dados"""
    print("\n" + "="*60)
    print("EXEMPLO 4: ANÁLISE DOS DADOS")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    
    gerenciador = GerenciadorExames("relatorio_exames.xlsx")
    df = gerenciador.df_exames
    
    if df is None or df.empty:
        print("Sem dados disponíveis")
        return
    
    print(f"\nTotal de exames: {len(df)}")
    
    # Análises
    df_status = df["Status"].astype(str).str.upper()
    
    alterados = len(df[df_status.str.contains("ALTERADO", na=False)])
    normais = len(df[df_status.str.contains("^NORMAL$", na=False)])
    revisar = len(df[df_status.str.contains("REVISAR", na=False)])
    
    print(f"Status:")
    print(f"  - Alterados: {alterados} ({alterados/len(df)*100:.1f}%)")
    print(f"  - Normais:   {normais} ({normais/len(df)*100:.1f}%)")
    print(f"  - Revisar:   {revisar} ({revisar/len(df)*100:.1f}%)")
    
    # Pacientes únicos
    pacientes = df["Paciente"].nunique()
    print(f"\nPacientes únicos: {pacientes}")
    
    # Analitos mais frequentes
    print(f"\nAnalitos mais frequentes:")
    top_analitos = df["Analito"].value_counts().head(5)
    for analito, count in top_analitos.items():
        print(f"  - {analito}: {count} vezes")


# ============================================================
# EXEMPLO 5: Exportar Dados Filtrados
# ============================================================

def exemplo_5_exportar():
    """Exemplo: Exportar dados filtrados"""
    print("\n" + "="*60)
    print("EXEMPLO 5: EXPORTAR DADOS FILTRADOS")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    import pandas as pd
    
    gerenciador = GerenciadorExames("relatorio_exames.xlsx")
    
    # Busca específica
    df_export = gerenciador.buscar_analitos_alterados(
        filtro_analito="GLICOSE"
    )
    
    if df_export.empty:
        print("Nenhum resultado para exportar")
        return
    
    # Exportar para Excel
    arquivo_saida = "glicose_alterada.xlsx"
    df_export.to_excel(arquivo_saida, index=False, sheet_name="resultados")
    print(f"\n✓ Exportado para: {arquivo_saida}")
    print(f"  Total de registros: {len(df_export)}")
    
    # Exportar para CSV
    arquivo_csv = "glicose_alterada.csv"
    df_export.to_csv(arquivo_csv, index=False, encoding="utf-8-sig")
    print(f"✓ Exportado para: {arquivo_csv}")


# ============================================================
# EXEMPLO 6: Usar em Aplicação Customizada
# ============================================================

def exemplo_6_custom_app():
    """Exemplo: Integrar em aplicação customizada"""
    print("\n" + "="*60)
    print("EXEMPLO 6: APLICAÇÃO CUSTOMIZADA")
    print("="*60)
    
    from gui_buscar_exames import GerenciadorExames
    
    class AnalisadorExames:
        """Classe customizada que usa o gerenciador"""
        
        def __init__(self, arquivo_relatorio):
            self.gerenciador = GerenciadorExames(arquivo_relatorio)
        
        def gerar_relatorio_alterados(self):
            """Gera relatório de exames alterados por paciente"""
            
            df_alt = self.gerenciador.buscar_analitos_alterados()
            
            if df_alt.empty:
                return "Sem exames alterados encontrados"
            
            relatorio = "RELATÓRIO DE EXAMES ALTERADOS\n"
            relatorio += "=" * 50 + "\n\n"
            
            pacientes = df_alt["Paciente"].unique()
            for paciente in pacientes:
                df_pac = df_alt[df_alt["Paciente"] == paciente]
                relatorio += f"\n👤 {paciente}\n"
                relatorio += "-" * 40 + "\n"
                for idx, row in df_pac.iterrows():
                    relatorio += f"  • {row['Analito']}\n"
                    relatorio += f"    Valor: {row['Valor']} {row['Unidade']}\n"
                    relatorio += f"    Referência: {row['Referencia']}\n"
                    relatorio += f"    Status: {row['Status']}\n"
            
            return relatorio
        
        def contar_alterados_por_analito(self):
            """Conta quantos alterados de cada tipo de analito"""
            
            df_alt = self.gerenciador.buscar_analitos_alterados()
            
            if df_alt.empty:
                return {}
            
            return dict(df_alt["Analito"].value_counts())
    
    # Usar a classe
    analisador = AnalisadorExames("relatorio_exames.xlsx")
    
    print("\nRelatório de Alterados:")
    print(analisador.gerar_relatorio_alterados())
    
    print("\nContagem por Analito:")
    contagem = analisador.contar_alterados_por_analito()
    for analito, count in sorted(contagem.items(), key=lambda x: x[1], reverse=True):
        print(f"  {analito}: {count}")


# ============================================================
# EXEMPLO 7: Interface Gráfica Customizada
# ============================================================

def exemplo_7_gui_customizada():
    """Exemplo: Criar interface gráfica customizada"""
    print("\n" + "="*60)
    print("EXEMPLO 7: INTERFACE GRÁFICA CUSTOMIZADA")
    print("="*60)
    
    import tkinter as tk
    from tkinter import ttk
    from gui_buscar_exames import GerenciadorExames
    
    class MeuBuscador:
        def __init__(self, root):
            self.root = root
            self.root.title("Meu Buscador")
            self.root.geometry("600x400")
            
            self.gerenciador = GerenciadorExames()
            
            # Frame principal
            frame = ttk.Frame(root, padding=10)
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Entrada
            ttk.Label(frame, text="Digite um analito:").pack(anchor=tk.W)
            self.entry = ttk.Entry(frame)
            self.entry.pack(fill=tk.X, pady=5)
            
            # Botão
            ttk.Button(
                frame,
                text="Procurar Alterados",
                command=self._buscar
            ).pack(pady=5)
            
            # Resultado
            self.text_result = tk.Text(frame, height=15)
            self.text_result.pack(fill=tk.BOTH, expand=True)
        
        def _buscar(self):
            analito = self.entry.get()
            
            df = self.gerenciador.buscar_analitos_alterados(
                filtro_analito=analito
            )
            
            self.text_result.delete(1.0, tk.END)
            
            if df.empty:
                self.text_result.insert(tk.END, "Nenhum resultado encontrado")
            else:
                texto = f"Encontrados {len(df)} resultados:\n\n"
                for idx, row in df.iterrows():
                    texto += f"Paciente: {row['Paciente']}\n"
                    texto += f"Analito: {row['Analito']}\n"
                    texto += f"Valor: {row['Valor']} {row['Unidade']}\n"
                    texto += f"Status: {row['Status']}\n"
                    texto += "-" * 40 + "\n"
                
                self.text_result.insert(tk.END, texto)
    
    print("Para executar, descomente a linha abaixo:")
    print("# root = tk.Tk()")
    print("# app = MeuBuscador(root)")
    print("# root.mainloop()")


# ============================================================
# MENU DE EXEMPLOS
# ============================================================

def main():
    """Menu principal de exemplos"""
    
    exemplos = [
        ("Uso Básico", exemplo_1_basico),
        ("Procurar Analitos Alterados", exemplo_2_analitos_alterados),
        ("Busca Avançada", exemplo_3_busca_avancada),
        ("Análise dos Dados", exemplo_4_analise),
        ("Exportar Dados", exemplo_5_exportar),
        ("Aplicação Customizada", exemplo_6_custom_app),
        ("Interface GUI Customizada", exemplo_7_gui_customizada),
    ]
    
    print("\n" + "="*60)
    print("  EXEMPLOS DE USO - INTERFACE DE BUSCA DE EXAMES")
    print("="*60)
    
    print("\nEscolha um exemplo:")
    for i, (nome, _) in enumerate(exemplos, 1):
        print(f"  {i}. {nome}")
    print(f"  0. Executar Todos")
    print(f"  9. Sair")
    
    while True:
        try:
            escolha = input("\nOpção: ").strip()
            
            if escolha == "9":
                print("\nAté logo!")
                break
            elif escolha == "0":
                for _, func in exemplos:
                    try:
                        func()
                    except Exception as e:
                        print(f"\n✗ Erro: {e}")
                input("\nPressione ENTER para continuar...")
            else:
                idx = int(escolha) - 1
                if 0 <= idx < len(exemplos):
                    try:
                        exemplos[idx][1]()
                    except Exception as e:
                        print(f"\n✗ Erro: {e}")
                        import traceback
                        traceback.print_exc()
                    input("\nPressione ENTER para continuar...")
                else:
                    print("Opção inválida!")
        except KeyboardInterrupt:
            print("\n\nInterrompido pelo usuário")
            break
        except Exception as e:
            print(f"Erro: {e}")


if __name__ == "__main__":
    main()
