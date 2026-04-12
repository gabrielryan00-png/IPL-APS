"""
EXEMPLO DE INTEGRAÇÃO - Como usar o GerenciadorReferencias no processaexames.py

Este arquivo mostra como otimizar o código existente usando o banco de dados SQL
de valores de referência.
"""

import json
from gerenciador_referencias import GerenciadorReferencias, inicializar, encerrar
from typing import Dict, List, Tuple

# =====================================================
# EXEMPLO 1: Classificação Simples de Valor
# =====================================================

def exemplo_classificacao_simples():
    """Exemplo básico de classificação de um valor"""
    print("\n" + "="*70)
    print("EXEMPLO 1: CLASSIFICAÇÃO SIMPLES")
    print("="*70)
    
    gerenciador = inicializar()
    
    # Classificar um valor simples
    resultado = gerenciador.classificar_valor(
        nome_exame="Creatinina",
        valor=1.1,
        genero="M",
        idade=45
    )
    
    print(f"\nExame: {resultado['exame']}")
    print(f"Valor: {resultado['valor']} {resultado['unidade']}")
    print(f"Status: {resultado['status']}")
    print(f"Categoria: {resultado['categoria']}")
    print(f"Referência: {resultado['referencia']}")
    print(f"Detalhes: {resultado['detalhes']}")

# =====================================================
# EXEMPLO 2: Processamento de Múltiplos Resultados
# =====================================================

def exemplo_processar_multiplos():
    """Processa múltiplos valores de um exame (laudo)"""
    print("\n" + "="*70)
    print("EXEMPLO 2: PROCESSAMENTO DE MÚLTIPLOS VALORES")
    print("="*70)
    
    gerenciador = inicializar()
    
    # Simular dados extraídos de um laudo PDF
    laudo_extraido = {
        "paciente": "João Silva",
        "genero": "M",
        "idade": 52,
        "exames": [
            {"nome": "Ureia", "valor": 35.0},
            {"nome": "Creatinina", "valor": 0.9},
            {"nome": "Glicemia Jejum", "valor": 105.0},
            {"nome": "Colesterol Total", "valor": 220.0},
            {"nome": "Triglicérides", "valor": 200.0},
            {"nome": "HDL", "valor": 35.0},
        ]
    }
    
    resultados_classificados = []
    
    for exame in laudo_extraido["exames"]:
        classificacao = gerenciador.classificar_valor(
            nome_exame=exame["nome"],
            valor=exame["valor"],
            genero=laudo_extraido["genero"],
            idade=laudo_extraido["idade"]
        )
        resultados_classificados.append(classificacao)
    
    # Exibir resultados com ícones
    print(f"\nPaciente: {laudo_extraido['paciente']} ({laudo_extraido['genero']}, {laudo_extraido['idade']})")
    print("-" * 70)
    
    normais = []
    limitrofes = []
    alterados = []
    
    for res in resultados_classificados:
        icone = "🟢" if res['status'] == "NORMAL" else \
                "🟡" if res['status'] == "LIMÍTROFE" else "🔴"
        
        print(f"{icone} {res['exame']:<20} {res['valor']:>8} {res['unidade']:<12} {res['status']:<12}")
        
        if res['status'] == 'NORMAL':
            normais.append(res)
        elif res['status'] == 'LIMÍTROFE':
            limitrofes.append(res)
        else:
            alterados.append(res)
    
    # Resumo
    print("-" * 70)
    print(f"✓ Normais: {len(normais)} | ⚠ Limítrofes: {len(limitrofes)} | ✗ Alterados: {len(alterados)}")
    
    return {
        'laudo': laudo_extraido,
        'normais': normais,
        'limitrofes': limitrofes,
        'alterados': alterados
    }

# =====================================================
# EXEMPLO 3: Integração com Exportação JSON
# =====================================================

def exemplo_exportar_json(resultados: Dict):
    """Exporta resultados em formato JSON estruturado"""
    print("\n" + "="*70)
    print("EXEMPLO 3: EXPORTAÇÃO JSON")
    print("="*70)
    
    # Estrutura JSON compatível com API/BD
    relatorio_json = {
        "dados_paciente": {
            "nome": resultados['laudo']['paciente'],
            "genero": resultados['laudo']['genero'],
            "idade": resultados['laudo']['idade']
        },
        "resumo": {
            "total_exames": len(resultados['laudo']['exames']),
            "normais": len(resultados['normais']),
            "limitrofes": len(resultados['limitrofes']),
            "alterados": len(resultados['alterados'])
        },
        "exames": {
            "normais": resultados['normais'],
            "limitrofes": resultados['limitrofes'],
            "alterados": resultados['alterados']
        }
    }
    
    print("\nJSON Completo:")
    print(json.dumps(relatorio_json, ensure_ascii=False, indent=2))
    
    return relatorio_json

# =====================================================
# EXEMPLO 4: Busca de Referências
# =====================================================

def exemplo_buscar_referencias():
    """Demonstra busca de referências com diferentes contextos"""
    print("\n" + "="*70)
    print("EXEMPLO 4: BUSCA DE REFERÊNCIAS")
    print("="*70)
    
    gerenciador = inicializar()
    
    # Buscar com diferentes critérios
    buscas = [
        ("Creatinina", "M", 45),  # Homem 45 anos
        ("Colesterol Total", None, 25),  # Qualquer genero, 25 anos
        ("TSH", None, 65),  # TSH para 65 anos
        ("Triglicérides", None, 8),  # Triglicérides para criança 8 anos
    ]
    
    for nome, gen, ida in buscas:
        ref = gerenciador.buscar_referencia(nome, gen, ida)
        print(f"\n{nome} (Gênero: {gen}, Idade: {ida})")
        if ref:
            print(f"  Valor mín: {ref['valor_min']}")
            print(f"  Valor máx: {ref['valor_max']}")
            print(f"  Unidade: {ref['unidade']}")
            print(f"  Ref: {ref['referencia_texto']}")
        else:
            print("  ❌ Não encontrado")

# =====================================================
# EXEMPLO 5: Classificação com Valores Qualitativos
# =====================================================

def exemplo_valores_qualitativos():
    """Processa valores qualitativos (Negativo, Ausente, etc)"""
    print("\n" + "="*70)
    print("EXEMPLO 5: VALORES QUALITATIVOS (URINA, SOROLOGIAS)")
    print("="*70)
    
    gerenciador = inicializar()
    
    # Simular resultado de urina tipo I
    urina_resultados = [
        ("Proteínas", "Ausentes"),
        ("Glicose", "Ausente"),
        ("Hemoglobina", "Presente"),  # Anormal
        ("Nitrito", "Não Reagente"),
        ("Corpos cetônicos", "Ausentes"),
    ]
    
    print("\nResultados de Urina Tipo I:")
    print("-" * 50)
    
    for nome, valor in urina_resultados:
        classificacao = gerenciador.classificar_valor_qualitativo(nome, valor)
        icone = "🟢" if classificacao['status'] == 'NORMAL' else "🔴"
        
        print(f"{icone} {nome:<25} {valor:<20} {classificacao['status']}")

# =====================================================
# EXEMPLO 6: Listando Dados Disponíveis
# =====================================================

def exemplo_listar_opcoes():
    """Mostra exames e categorias disponíveis"""
    print("\n" + "="*70)
    print("EXEMPLO 6: DADOS DISPONÍVEIS NO BANCO")
    print("="*70)
    
    gerenciador = inicializar()
    
    print("\nCategorias disponíveis:")
    categorias = gerenciador.get_categorias()
    for cat in categorias:
        print(f"  • {cat}")
    
    print("\nExemplos de exames (primeiros 20):")
    exames = gerenciador.get_todos_exames()[:20]
    for exame in exames:
        print(f"  • {exame}")

# =====================================================
# COMO INTEGRAR NO processaexames.py ATUAL
# =====================================================

"""
PASSO 1: Adicionar imports no início do processaexames.py:

    from gerenciador_referencias import GerenciadorReferencias, inicializar, encerrar

PASSO 2: Inicializar gerenciador no início:

    # Logo após os imports
    gerenciador = inicializar()

PASSO 3: Substituir função de classificação antiga:

    # Antes (versão antiga):
    def classificar_resultado(nome_exame, valor, referencia_texto):
        # código complexo aqui...
        return status
    
    # Depois (versão otimizada):
    def classificar_resultado(nome_exame, valor, genero=None, idade=None):
        resultado = gerenciador.classificar_valor(
            nome_exame=nome_exame,
            valor=valor,
            genero=genero,
            idade=idade
        )
        return resultado['status']

PASSO 4: No final do processaexames.py:

    # Encerrar gerenciador
    encerrar()

PASSO 5: Para processar laudo completo:

    def processar_laudo(metadados, exames_extraidos):
        resultados = []
        genero = metadados.get('Genero')  # Extrair de metadados
        idade = calcular_idade(metadados.get('Dt Nasc'))
        
        for exame_nome, valor_str in exames_extraidos.items():
            try:
                valor = float(valor_str)
                # Usar gerenciador para classificar
                classificacao = gerenciador.classificar_valor(
                    exame_nome, valor, genero, idade
                )
                resultados.append(classificacao)
            except ValueError:
                # Valor qualitativo
                classificacao = gerenciador.classificar_valor_qualitativo(
                    exame_nome, valor_str
                )
                resultados.append(classificacao)
        
        return resultados

BENEFÍCIOS:
✓ Centralização de dados de referência (não espalhados no código)
✓ Fácil atualização de referências (editar SQL, não Python)
✓ Suporte a gênero e idade automático
✓ Classificação consistente (NORMAL, ALTERADO, LIMÍTROFE)
✓ Performance otimizada com índices SQL
✓ Rastreabilidade de mudanças (histórico no BD)
✓ Fácil expansão para novas referências
"""

# =====================================================
# FUNÇÃO PARA DEMONSTRAÇÃO COMPLETA
# =====================================================

def rodar_todos_exemplos():
    """Executa todos os exemplos"""
    try:
        exemplo_classificacao_simples()
        resultados = exemplo_processar_multiplos()
        exemplo_exportar_json(resultados)
        exemplo_buscar_referencias()
        exemplo_valores_qualitativos()
        exemplo_listar_opcoes()
        
    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        encerrar()

if __name__ == "__main__":
    print("\n" + "="*70)
    print("EXEMPLOS DE INTEGRAÇÃO - GERENCIADOR DE REFERÊNCIAS")
    print("="*70)
    
    rodar_todos_exemplos()
    
    print("\n" + "="*70)
    print("FIM DOS EXEMPLOS")
    print("="*70)
