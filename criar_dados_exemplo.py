"""
Criador de dados de exemplo para testes da interface
Gera relatorio_exames_exemplo.xlsx com dados fictícios
"""

import pandas as pd
import os
from datetime import datetime, timedelta
import random


def criar_dados_exemplo():
    """Cria dados de exemplo para teste da interface"""
    
    # Dados fictícios
    pacientes = [
        "Silva, João", "Santos, Maria", "Oliveira, Pedro",
        "Costa, Ana", "Ferreira, Carlos", "Gomes, Juliana",
        "Martins, Roberto", "Alves, Fernanda", "Souza, Bruno",
        "Dias, Patricia", "Barbosa, Ricardo", "Ribeiro, Isabela",
        "Mendes, David", "Teixeira, Camila", "Cavalcanti, Lucas"
    ]
    
    analitos = [
        "GLICOSE", "HEMOGLOBINA", "HEMATÓCRITO", "TRIGLICERÍDEOS",
        "COLESTEROL TOTAL", "HDL", "LDL", "PROTEÍNA C REATIVA",
        "TSH", "T4 LIVRE", "UREIA", "CREATININA", "ÁCIDO ÚRICO",
        "ALT (TGP)", "AST (TGO)", "FOSFATASE ALCALINA"
    ]
    
    medicos = [
        "Dr. Silva", "Dra. Santos", "Dr. Oliveira",
        "Dra. Costa", "Dr. Ferreira", "Dra. Gomes"
    ]
    
    # Gera 100 registros
    dados = []
    
    for i in range(100):
        paciente = random.choice(pacientes)
        analito = random.choice(analitos)
        medico = random.choice(medicos)
        
        # Gera valor aleatório
        valor = round(random.uniform(50, 300), 2)
        
        # Define referência e status baseado no analito
        if analito == "GLICOSE":
            referencia = "70 - 100"
            status = "ALTERADO" if valor > 100 or valor < 70 else "NORMAL"
        elif analito == "HEMOGLOBINA":
            referencia = "12 - 16"
            status = "ALTERADO" if valor > 16 or valor < 12 else "NORMAL"
        elif analito == "COLESTEROL TOTAL":
            referencia = "até 200"
            status = "ALTERADO" if valor > 200 else "NORMAL"
        else:
            referencia = f"até {round(random.uniform(50, 100), 1)}"
            status = random.choice(["NORMAL", "ALTERADO", "REVISAR"])
        
        # 30% chance de ser "REVISAR"
        if random.random() < 0.1:
            status = "REVISAR"
        
        # 20% chance de ser alterado
        elif random.random() < 0.2:
            status = "ALTERADO"
        else:
            status = "NORMAL"
        
        # Define motivo
        if status == "ALTERADO":
            motivo = "Exame alterado"
        elif status == "REVISAR":
            motivo = "Revisar (status indefinido)"
        else:
            motivo = ""
        
        # Conta como pendência
        pendencia = "SIM" if status in ["ALTERADO", "REVISAR"] else "NÃO"
        
        dados.append({
            "Arquivo": f"PDF_{i:04d}.pdf",
            "Paciente": paciente,
            "Pedido": f"{2000000 + i}",
            "Dt Nasc": f"{random.randint(1950, 2000)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "Medico": medico,
            "Analito": f"{analito}",
            "Valor": valor,
            "Unidade": random.choice(["mg/dL", "g/dL", "mmol/L", "%", "U/L", "ng/mL"]),
            "Referencia": referencia,
            "Status": status,
            "Pendencia": pendencia,
            "Motivo": motivo,
            "EmailUID": f"UID_{i:05d}"
        })
    
    return pd.DataFrame(dados)


def salvar_exemplo(arquivo: str = "relatorio_exames_exemplo.xlsx"):
    """Salva dados de exemplo em arquivo Excel"""
    
    print("Gerando dados de exemplo...")
    df = criar_dados_exemplo()
    
    # Separa pendências
    df_pendencias = df[df["Pendencia"] == "SIM"].copy()
    
    print(f"Criando arquivo: {arquivo}")
    
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="exames")
        df_pendencias.to_excel(writer, index=False, sheet_name="pendencias")
        
        # Formata sheets
        for sheet_name in ["exames", "pendencias"]:
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_idx in range(1, ws.max_column + 1):
                col_letter = ws.cell(row=1, column=col_idx).column_letter
                ws.column_dimensions[col_letter].width = 18
    
    print(f"✓ Arquivo criado: {arquivo}")
    
    # Estatísticas
    total = len(df)
    alterados = len(df[df["Status"] == "ALTERADO"])
    normais = len(df[df["Status"] == "NORMAL"])
    revisar = len(df[df["Status"] == "REVISAR"])
    
    print(f"\nEstatísticas:")
    print(f"  Total de exames: {total}")
    print(f"  Alterados: {alterados} ({alterados/total*100:.1f}%)")
    print(f"  Normais: {normais} ({normais/total*100:.1f}%)")
    print(f"  Revisar: {revisar} ({revisar/total*100:.1f}%)")
    print(f"  Pendências: {len(df_pendencias)}")


def testar_com_exemplo():
    """Testa interface com dados de exemplo"""
    
    print("\n" + "="*60)
    print("TESTE COM DADOS DE EXEMPLO")
    print("="*60 + "\n")
    
    arquivo = "relatorio_exames_exemplo.xlsx"
    
    if not os.path.exists(arquivo):
        print("Criando dados de exemplo...")
        salvar_exemplo(arquivo)
    else:
        print(f"Usando arquivo existente: {arquivo}")
    
    print("\nCom os dados de exemplo, você pode testar a interface:")
    print(f"  1. Copie {arquivo} como relatorio_exames.xlsx")
    print("  2. Execute: python gui_buscar_exames.py")
    print("  3. Ou use programaticamente:\n")
    
    exemplo_codigo = f"""
    from gui_buscar_exames import GerenciadorExames
    
    gerenciador = GerenciadorExames("{arquivo}")
    
    # Testa busca de alterados
    df_alt = gerenciador.buscar_analitos_alterados()
    print(f"Alterados encontrados: {{len(df_alt)}}")
    
    # Testa filtro por paciente
    df_silva = gerenciador.buscar_por_paciente("Silva")
    print(f"Exames Silva: {{len(df_silva)}}")
    
    # Testa busca avançada
    df_combo = gerenciador.busca_avancada(
        paciente="Silva",
        analito="GLICOSE",
        status="ALTERADO"
    )
    print(f"Silva + Glicose + Alterado: {{len(df_combo)}}")
    """
    
    print(exemplo_codigo)


def main():
    """Função principal"""
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--teste":
        testar_com_exemplo()
    else:
        salvar_exemplo()
        print("\nPróximas etapas:")
        print("  1. Para testar com dados de exemplo:")
        print("     python criar_dados_exemplo.py --teste")
        print("  2. Para usar em gui_buscar_exames.py:")
        print("     cp relatorio_exames_exemplo.xlsx relatorio_exames.xlsx")
        print("     python gui_buscar_exames.py")


if __name__ == "__main__":
    main()
