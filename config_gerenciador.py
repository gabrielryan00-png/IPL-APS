"""
CONFIGURAÇÕES DO GERENCIADOR DE REFERÊNCIAS

Ajuste esses valores para customizar o comportamento do classificador
"""

# =====================================================
# MARGENS DE CLASSIFICAÇÃO
# =====================================================

# Percentual de margem para classificar como LIMÍTROFE
# Valores dentro desta margem dos limites serão "LIMÍTROFE" em vez de "NORMAL"
# Exemplo: Se max=100 e margem=5%, então 95-100 é LIMÍTROFE, >100 é ALTERADO
MARGEM_LIMITROFE_PERCENTUAL = 5.0  # 5% por padrão

# Usar margem também para limite inferior?
APLICAR_MARGEM_LIM_INFERIOR = True
APLICAR_MARGEM_LIM_SUPERIOR = True

# =====================================================
# COMPORTAMENTO DE BUSCA
# =====================================================

# Quando NOT encontrado, retornar INDEFINIDO ou tentar fuzzy match?
USAR_FUZZY_MATCH_EXAME = False  # True = usa difflib para encontrar similar

# Distância máxima de Levenshtein para fuzzy match (0-100)
FUZZY_MATCH_THRESHOLD = 80

# =====================================================
# VALORES PRÉ-DEFINIDOS
# =====================================================

# Status possíveis (não altere!)
STATUS_NORMAL = "NORMAL"
STATUS_ALTERADO = "ALTERADO"
STATUS_LIMITROFE = "LIMÍTROFE"
STATUS_INDEFINIDO = "INDEFINIDO"

# =====================================================
# DATABASE
# =====================================================

# Caminho do banco de dados (ajuste se necessário)
# Deixe vazio para usar diretório do script
DB_PATH = ""  # Usa Path(__file__).parent / "valores_referencia.db"

# Auto-criar banco se não existir?
AUTO_CRIAR_DB = True

# Caminho do arquivo SQL para criar banco
SQL_FILE = "valores_referencia.sql"

# =====================================================
# LOGGING E DEBUG
# =====================================================

# Nível de verbosidade
DEBUG_MODE = False  # True = imprime queries e operações

# Registrar em log?
USAR_LOG = False
LOG_FILE = "gerenciador_referencias.log"

# =====================================================
# CLASSIFICAÇÃO CUSTOMIZADA
# =====================================================

# Exames que sempre retornam INDEFINIDO (para pesquisa manual)
EXAMES_REVISAO_MANUAL = [
    "Comentários",
    "Observações",
    "Notas",
    "Achados",
]

# Mapeamento de alias/sinônimos (nome_padrao : [alias1, alias2])
SINONIMOS_EXAMES = {
    "Creatinina": ["Creat", "Creatinina sérica", "Crea"],
    "Hemoglobina": ["Hemoglobin", "Hgb", "Hb"],
    "Proteínas totais": ["Prot Total", "ProtT", "Proteína sérica"],
    "TGO": ["AST", "Aspartato"],
    "TGP": ["ALT", "Alanina"],
    "PSA": ["AG prostatico", "Antígeno PSA"],
    "Anti-HTLV": ["HTLV", "HTLV 1 e 2"],
    "Sangue Oculto": ["Pesquisa sangue oculto", "FOB"],
}

# =====================================================
# LIMÍTROFES CUSTOMIZADOS
# =====================================================

# Exames com MARGEM customizada (sobrescreve MARGEM_LIMITROFE_PERCENTUAL)
MARGEM_CUSTOMIZADA = {
    "Glicemia Jejum": 10.0,  # 10% para glicemia
    "Colesterol Total": 8.0,  # 8% para colesterol
    "Triglicérides": 7.0,    # 7% para triglicérides
    "Hemoglobina": 5.0,      # 5% para hemoglobina
}

# =====================================================
# PERFORMANCE
# =====================================================

# Cache de buscas recentes (para evitar queries repetidas)
USAR_CACHE = True
CACHE_SIZE_MAX = 500  # máximo de resultados em cache

# Usar índices de texto para busca (SQL FTS5)?
USAR_FULL_TEXT_SEARCH = False

# =====================================================
# VALIDAÇÃO
# =====================================================

# Validar valores numéricos antes de classificar?
VALIDAR_VALORES = True

# Range de valores válidos (warnings se fora deste range)
MIN_VALOR_VALIDO = -999999
MAX_VALOR_VALIDO = 999999

# Avisar se valor tem muitos dígitos decimais?
MAX_CASAS_DECIMAIS = 2
AVISAR_MUITOS_DECIMAIS = False

# =====================================================
# SAÍDA / EXPORT
# =====================================================

# Incluir campos adicionais na resposta?
INCLUIR_CATEGORIA = True
INCLUIR_NOTAS = True
INCLUIR_REFERENCIA_TEXTO = True
INCLUIR_DETALHES = True

# Formato de unidade (normalizar?)
NORMALIZAR_UNIDADES = False
UNIDADES_NORMALIZADAS = {
    "mg/dl": "mg/dL",
    "mmol/l": "mmol/L",
    "u/l": "U/L",
    "ml/min": "mL/min",
}

# =====================================================
# FEATURES EXPERIMENTAIS
# =====================================================

# Aplicar IA para classificação?
USAR_ML = False  # Experimento futuro

# Histórico de consultas (para análise)
REGISTRAR_HISTORICO = False
ARQUIVO_HISTORICO = "consultas_historico.json"

# =====================================================
# COMO USAR ESTAS CONFIGURAÇÕES
# =====================================================

"""
Opção 1: Editar este arquivo diretamente
===========================================
1. Abra config_gerenciador.py
2. Altere valores necessários
3. Salve o arquivo
4. Execute seu código normalmente

Exemplo: Aumentar margem para 10%
    MARGEM_LIMITROFE_PERCENTUAL = 10.0

Opção 2: Sobrescrever via código
=================================
from gerenciador_referencias import GerenciadorReferencias
import config_gerenciador as cfg

# Antes de inicializar
cfg.MARGEM_LIMITROFE_PERCENTUAL = 10.0
cfg.DEBUG_MODE = True

# Depois inicializar
g = GerenciadorReferencias()

Opção 3: Variáveis de ambiente (futuro)
=======================================
export GERENCIADOR_MARGEM=10.0
export GERENCIADOR_DEBUG=1
python meu_script.py
"""

# =====================================================
# PRESETS (Combinações de configuração)
# =====================================================

PRESET_RIGOROSO = {
    "MARGEM_LIMITROFE_PERCENTUAL": 2.0,  # Mais rigoroso
    "VALIDAR_VALORES": True,
    "DEBUG_MODE": True,
}

PRESET_LENIENTE = {
    "MARGEM_LIMITROFE_PERCENTUAL": 10.0,  # Mais leniente
    "INVALIDAR_VALORES": False,
    "DEBUG_MODE": False,
}

PRESET_PRODUCAO = {
    "DEBUG_MODE": False,
    "USAR_LOG": True,
    "USAR_CACHE": True,
    "CACHE_SIZE_MAX": 1000,
}

PRESET_DESENVOLVIMENTO = {
    "DEBUG_MODE": True,
    "USAR_LOG": True,
    "VALIDAR_VALORES": True,
    "AVISAR_MUITOS_DECIMAIS": True,
}

def aplicar_preset(nome_preset: str):
    """Aplica um preset de configuração (ainda não implementado)"""
    presets = {
        "rigoroso": PRESET_RIGOROSO,
        "leniente": PRESET_LENIENTE,
        "producao": PRESET_PRODUCAO,
        "desenvolvimento": PRESET_DESENVOLVIMENTO,
    }
    
    if nome_preset in presets:
        preset = presets[nome_preset]
        for chave, valor in preset.items():
            globals()[chave] = valor
        print(f"✓ Preset '{nome_preset}' aplicado")
    else:
        print(f"✗ Preset '{nome_preset}' não encontrado")

# =====================================================
# FUNÇÃO PARA IMPRIMIR CONFIGURAÇÕES ATIVAS
# =====================================================

def imprimir_config():
    """Mostra configurações ativas"""
    print("\n" + "="*70)
    print("CONFIGURAÇÕES ATIVAS DO GERENCIADOR")
    print("="*70)
    
    import inspect
    
    for nome, valor in sorted(globals().items()):
        if nome.isupper() and not nome.startswith("_"):
            if not isinstance(valor, dict) and not isinstance(valor, type):
                print(f"{nome:<40} = {valor}")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    imprimir_config()
