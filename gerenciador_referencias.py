"""
Módulo de Gerenciamento de Valores de Referência Laboratoriais
Integração com SQL para otimizar classificação de exames
"""

import sqlite3
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from datetime import datetime

# Caminho do banco de dados
DB_PATH = Path(__file__).parent / "valores_referencia.db"

class GerenciadorReferencias:
    """Gerencia classificação de valores laboratoriais contra referências técnicas"""
    
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self.conexao = None
        self.inicializar_db()
    
    def inicializar_db(self):
        """Inicializa banco de dados from SQL file"""
        if not Path(self.db_path).exists():
            self._criar_db_from_sql()
        self.conectar()
    
    def _criar_db_from_sql(self):
        """Cria banco de dados executando o arquivo SQL"""
        sql_file = Path(__file__).parent / "valores_referencia.sql"
        if not sql_file.exists():
            raise FileNotFoundError(f"Arquivo SQL não encontrado: {sql_file}")
        
        conexao = sqlite3.connect(self.db_path)
        cursor = conexao.cursor()
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            cursor.executescript(sql_script)
        
        conexao.commit()
        conexao.close()
        print(f"✓ Banco de dados criado: {self.db_path}")
    
    def conectar(self):
        """Conecta ao banco de dados"""
        self.conexao = sqlite3.connect(self.db_path)
        self.conexao.row_factory = sqlite3.Row
    
    def desconectar(self):
        """Fecha conexão com banco de dados"""
        if self.conexao:
            self.conexao.close()
    
    def buscar_referencia(
        self,
        nome_exame: str,
        genero: Optional[str] = None,
        idade: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Busca valores de referência com prioridade de correspondência.
        
        Args:
            nome_exame: Nome do exame (ex: "Creatinina", "Colesterol Total")
            genero: 'M', 'F' ou None
            idade: Idade em anos ou None
        
        Returns:
            Dict com {valor_min, valor_max, unidade, categoria, notas} ou None
        """
        cursor = self.conexao.cursor()
        
        # Normalizar nome do exame
        nome_exame_norm = nome_exame.strip().upper()
        
        # Busca com prioridade de correspondência
        query = """
        SELECT 
            nome_exame,
            genero,
            idade_min,
            idade_max,
            valor_min,
            valor_max,
            unidade,
            notas,
            referencia_texto
        FROM valores_referencia
        WHERE UPPER(nome_exame) LIKE ?
        AND ativo = 1
        ORDER BY 
            -- Prioridade 1: Genero exato + Idade na faixa
            CASE 
                WHEN genero = ? AND ? BETWEEN COALESCE(idade_min, -999) AND COALESCE(idade_max, 999999) 
                    THEN 0
                ELSE 1
            END,
            -- Prioridade 2: Genero exato sem faixa de idade
            CASE 
                WHEN genero = ? AND idade_min IS NULL AND idade_max IS NULL 
                    THEN 0
                ELSE 1
            END,
            -- Prioridade 3: Genero NULL + Idade na faixa
            CASE 
                WHEN genero IS NULL AND ? BETWEEN COALESCE(idade_min, -999) AND COALESCE(idade_max, 999999) 
                    THEN 0
                ELSE 1
            END,
            -- Prioridade 4: Genero NULL sem faixa de idade
            CASE 
                WHEN genero IS NULL AND idade_min IS NULL AND idade_max IS NULL 
                    THEN 0
                ELSE 1
            END,
            idade_min
        LIMIT 1
        """
        
        cursor.execute(query, (
            f"%{nome_exame_norm}%",
            genero, idade,
            genero,
            idade
        ))
        
        resultado = cursor.fetchone()
        
        if resultado:
            return {
                'nome_exame': resultado['nome_exame'],
                'genero': resultado['genero'],
                'valor_min': resultado['valor_min'],
                'valor_max': resultado['valor_max'],
                'unidade': resultado['unidade'],
                'referencia_texto': resultado['referencia_texto'],
                'notas': resultado['notas']
            }
        
        return None
    
    def buscar_categoria(self, nome_exame: str) -> Optional[str]:
        """Busca categoria do exame (em valores_referencia ou valores_qualitativos)"""
        cursor = self.conexao.cursor()
        
        # Normalizar nome para busca
        nome_busca = nome_exame.strip()
        
        # Primeiro tenta valores_referencia
        query = """
        SELECT c.nome
        FROM valores_referencia vr
        LEFT JOIN categorias_exames c ON vr.categoria_id = c.id
        WHERE UPPER(vr.nome_exame) LIKE UPPER(?)
        AND vr.ativo = 1
        LIMIT 1
        """
        
        cursor.execute(query, (f"%{nome_busca}%",))
        resultado = cursor.fetchone()
        
        if resultado and resultado['nome']:
            return resultado['nome']
        
        # Se não encontrou, tenta valores_qualitativos
        query_qual = """
        SELECT c.nome
        FROM valores_qualitativos vq
        LEFT JOIN categorias_exames c ON vq.categoria_id = c.id
        WHERE UPPER(vq.nome_exame) LIKE UPPER(?)
        AND vq.ativo = 1
        LIMIT 1
        """
        
        cursor.execute(query_qual, (f"%{nome_busca}%",))
        resultado = cursor.fetchone()
        
        return resultado['nome'] if resultado and resultado['nome'] else None
    
    def classificar_valor(
        self,
        nome_exame: str,
        valor: float,
        genero: Optional[str] = None,
        idade: Optional[int] = None
    ) -> Dict:
        """
        Classifica um valor laboratorial como NORMAL, ALTERADO ou LIMÍTROFE.
        
        Args:
            nome_exame: Nome do exame
            valor: Valor numérico
            genero: 'M' ou 'F'
            idade: Idade em anos
        
        Returns:
            {
                'status': 'NORMAL|ALTERADO|LIMÍTROFE',
                'valor_min': float,
                'valor_max': float,
                'unidade': str,
                'categoria': str,
                'detalhes': str
            }
        """
        ref = self.buscar_referencia(nome_exame, genero, idade)
        
        if not ref:
            return {
                'status': 'INDEFINIDO',
                'valor': valor,
                'detalhes': f'Sem referência cadastrada para "{nome_exame}"'
            }
        
        valor_min = ref['valor_min']
        valor_max = ref['valor_max']
        categoria = self.buscar_categoria(nome_exame)
        
        # Margem de tolerância para limítrofe (5% dos limites)
        margem = 5.0
        
        resultado = {
            'exame': nome_exame,
            'valor': valor,
            'unidade': ref['unidade'],
            'categoria': categoria,
            'referencia': ref['referencia_texto'],
            'valor_min': valor_min,
            'valor_max': valor_max
        }
        
        # Ambos limites definidos
        if valor_min is not None and valor_max is not None:
            if valor_min <= valor <= valor_max:
                resultado['status'] = 'NORMAL'
                resultado['detalhes'] = f'Dentro do intervalo: {valor_min} - {valor_max}'
            else:
                # Verificar se é LIMÍTROFE (próximo aos limites)
                margem_inf = valor_min - (valor_max - valor_min) * (margem / 100)
                margem_sup = valor_max + (valor_max - valor_min) * (margem / 100)
                
                if margem_inf <= valor < valor_min or valor_max < valor <= margem_sup:
                    resultado['status'] = 'LIMÍTROFE'
                    if valor < valor_min:
                        resultado['detalhes'] = f'Abaixo da faixa ideal (limite: {valor_min})'
                    else:
                        resultado['detalhes'] = f'Acima da faixa ideal (limite: {valor_max})'
                else:
                    resultado['status'] = 'ALTERADO'
                    if valor < valor_min:
                        resultado['detalhes'] = f'Significativamente abaixo (valor mín: {valor_min})'
                    else:
                        resultado['detalhes'] = f'Significativamente acima (valor máx: {valor_max})'
        
        # Apenas limite inferior
        elif valor_min is not None:
            if valor >= valor_min:
                resultado['status'] = 'NORMAL'
                resultado['detalhes'] = f'Acima do mínimo: {valor_min}'
            else:
                resultado['status'] = 'ALTERADO'
                resultado['detalhes'] = f'Abaixo do mínimo: {valor_min}'
        
        # Apenas limite superior
        elif valor_max is not None:
            if valor <= valor_max:
                resultado['status'] = 'NORMAL'
                resultado['detalhes'] = f'Abaixo do máximo: {valor_max}'
            else:
                diferenca_percentual = ((valor - valor_max) / valor_max) * 100
                if diferenca_percentual <= margem:
                    resultado['status'] = 'LIMÍTROFE'
                    resultado['detalhes'] = f'Ligeiramente acima do máximo ({diferenca_percentual:.1f}%)'
                else:
                    resultado['status'] = 'ALTERADO'
                    resultado['detalhes'] = f'Significativamente acima do máximo ({diferenca_percentual:.1f}%)'
        
        return resultado
    
    def classificar_valor_qualitativo(
        self,
        nome_exame: str,
        valor: str
    ) -> Dict:
        """
        Classifica valor qualitativo (Negativo, Ausente, etc).
        
        Args:
            nome_exame: Nome do exame
            valor: Valor qualitativo
        
        Returns:
            {
                'status': 'NORMAL|ALTERADO|INDEFINIDO',
                'valor': str,
                'categoria': str
            }
        """
        cursor = self.conexao.cursor()
        
        # Normalizar nome para busca
        nome_norm = nome_exame.strip().upper()
        
        # Buscar valores normais conhecidos
        query = """
        SELECT vq.valor_normal, c.nome AS categoria
        FROM valores_qualitativos vq
        LEFT JOIN categorias_exames c ON vq.categoria_id = c.id
        WHERE UPPER(TRIM(vq.nome_exame)) = UPPER(TRIM(?))
        OR UPPER(TRIM(vq.nome_exame)) LIKE UPPER(TRIM(?))
        """
        
        cursor.execute(query, (nome_exame, f"%{nome_exame}%"))
        resultado = cursor.fetchone()
        
        categoria = resultado['categoria'] if resultado else None
        valor_normal = resultado['valor_normal'].upper() if resultado else None
        valor_upper = valor.upper()
        
        if valor_normal and valor_upper in valor_normal:
            status = 'NORMAL'
        elif valor_normal:
            status = 'ALTERADO'
        else:
            status = 'INDEFINIDO'
        
        return {
            'exame': nome_exame,
            'valor': valor,
            'categoria': categoria,
            'status': status,
            'valor_esperado': valor_normal
        }
    
    def get_todos_exames(self) -> List[str]:
        """Retorna lista de todos os exames cadastrados"""
        cursor = self.conexao.cursor()
        cursor.execute("""
            SELECT DISTINCT nome_exame 
            FROM valores_referencia 
            WHERE ativo = 1
            ORDER BY nome_exame
        """)
        return [row[0] for row in cursor.fetchall()]
    
    def get_categorias(self) -> List[str]:
        """Retorna lista de todas as categorias"""
        cursor = self.conexao.cursor()
        cursor.execute("""
            SELECT nome 
            FROM categorias_exames 
            ORDER BY nome
        """)
        return [row[0] for row in cursor.fetchall()]
    
    def exportar_referencia_json(self, nome_exame: str) -> Dict:
        """Exporta referência em formato JSON"""
        ref = self.buscar_referencia(nome_exame)
        categoria = self.buscar_categoria(nome_exame)
        
        if not ref:
            return {'erro': f'Exame "{nome_exame}" não encontrado'}
        
        return {
            'exame': nome_exame,
            'categoria': categoria,
            'valor_min': ref['valor_min'],
            'valor_max': ref['valor_max'],
            'unidade': ref['unidade'],
            'genero': ref['genero'],
            'referencia': ref['referencia_texto'],
            'notas': ref['notas']
        }

# =====================================================
# FUNÇÕES DE CONVENIÊNCIA
# =====================================================

# Instância global
_gerenciador_global = None

def inicializar():
    """Inicializa gerenciador global"""
    global _gerenciador_global
    if not _gerenciador_global:
        _gerenciador_global = GerenciadorReferencias()
    return _gerenciador_global

def classificar(nome_exame: str, valor, genero=None, idade=None) -> Dict:
    """Função conveniente para classificar valor"""
    gerenciador = inicializar()
    
    try:
        valor_float = float(valor) if isinstance(valor, (str, int, float)) else None
        if valor_float is None:
            return gerenciador.classificar_valor_qualitativo(nome_exame, str(valor))
        return gerenciador.classificar_valor(nome_exame, valor_float, genero, idade)
    except (ValueError, TypeError):
        return gerenciador.classificar_valor_qualitativo(nome_exame, str(valor))

def encerrar():
    """Encerra gerenciador global"""
    global _gerenciador_global
    if _gerenciador_global:
        _gerenciador_global.desconectar()
        _gerenciador_global = None

if __name__ == "__main__":
    # Teste rápido
    gerenciador = GerenciadorReferencias()
    
    # Testes
    testes = [
        ("Creatinina", 1.1, "M", 45),
        ("Glicemia Jejum", 110.0, None, None),
        ("Colesterol Total", 180.0, None, 22),
        ("TSH", 3.5, None, 35),
    ]
    
    print("\n" + "="*70)
    print("TESTES DE CLASSIFICAÇÃO")
    print("="*70)
    
    for nome, valor, gen, ida in testes:
        resultado = gerenciador.classificar_valor(nome, valor, gen, ida)
        print(f"\n{nome}: {valor} {resultado.get('unidade', '')}")
        print(f"  Status: {resultado['status']}")
        print(f"  Ref: {resultado['referencia']}")
        print(f"  {resultado['detalhes']}")
    
    gerenciador.desconectar()
