"""
TESTES UNITÁRIOS - Gerenciador de Referências Laboratoriais

Execute: python teste_gerenciador.py
"""

import sys
from gerenciador_referencias import GerenciadorReferencias
import json

class TestesGerenciador:
    """Suite de testes para validar funcionamento"""
    
    def __init__(self):
        self.gerenciador = GerenciadorReferencias()
        self.total_testes = 0
        self.total_passou = 0
        self.total_falhou = 0
        
    def teste(self, nome: str, condicao: bool, esperado="", obtido=""):
        """Helper para rodar testes"""
        self.total_testes += 1
        
        if condicao:
            self.total_passou += 1
            print(f"✓ {nome}")
            return True
        else:
            self.total_falhou += 1
            print(f"✗ {nome}")
            if esperado and obtido:
                print(f"  Esperado: {esperado}")
                print(f"  Obtido: {obtido}")
            return False
    
    def testar_busca_referencia(self):
        """Testa busca de referência"""
        print("\n" + "="*70)
        print("TESTES: BUSCA DE REFERÊNCIA")
        print("="*70)
        
        # Test 1: Busca básica
        ref = self.gerenciador.buscar_referencia("Creatinina", "M", 45)
        self.teste("Busca básica - Creatinina", ref is not None)
        
        # Test 2: Verificar campos
        if ref:
            self.teste("Campo valor_min existe", "valor_min" in ref)
            self.teste("Campo valor_max existe", "valor_max" in ref)
            self.teste("Campo unidade existe", "unidade" in ref)
        
        # Test 3: Valores corretos
        if ref:
            self.teste("Creatinina M: min=0.6", ref['valor_min'] == 0.6, 
                      "0.6", ref['valor_min'])
            self.teste("Creatinina M: max=1.2", ref['valor_max'] == 1.2,
                      "1.2", ref['valor_max'])
        
        # Test 4: Creatinina para mulher
        ref_f = self.gerenciador.buscar_referencia("Creatinina", "F", 30)
        if ref_f:
            self.teste("Creatinina F: max=1.0", ref_f['valor_max'] == 1.0,
                      "1.0", ref_f['valor_max'])
        
        # Test 5: Busca com idade
        ref_tsh = self.gerenciador.buscar_referencia("TSH", None, 70)
        if ref_tsh:
            self.teste("TSH com idade 70 na faixa correta", 
                      ref_tsh['valor_max'] in [6.8, 7.9])
    
    def testar_classificacao_normal(self):
        """Testa classificação de valores NORMAIS"""
        print("\n" + "="*70)
        print("TESTES: CLASSIFICAÇÃO NORMAL")
        print("="*70)
        
        testes = [
            ("Creatinina", 0.9, "M", 45, "NORMAL"),
            ("Glicemia Jejum", 85.0, None, None, "NORMAL"),
            ("Colesterol Total", 180.0, None, 25, "NORMAL"),
            ("Hemoglobina", 14.0, "F", 35, "NORMAL"),
            ("TSH", 2.5, None, 50, "NORMAL"),
            ("Ureia", 30.0, None, None, "NORMAL"),
        ]
        
        for nome, valor, gen, idade, esperado in testes:
            result = self.gerenciador.classificar_valor(nome, valor, gen, idade)
            self.teste(f"{nome} {valor} → {esperado}", 
                      result['status'] == esperado,
                      esperado, result['status'])
    
    def testar_classificacao_alterado(self):
        """Testa classificação de valores ALTERADOS"""
        print("\n" + "="*70)
        print("TESTES: CLASSIFICAÇÃO ALTERADO")
        print("="*70)
        
        testes = [
            ("Creatinina", 2.0, "M", 45, "ALTERADO"),
            ("Glicemia Jejum", 150.0, None, None, "ALTERADO"),
            ("Colesterol Total", 250.0, None, 25, "ALTERADO"),
            ("TGO/AST", 100.0, None, None, "ALTERADO"),
            ("Hemoglobina", 8.0, "F", 35, "ALTERADO"),
        ]
        
        for nome, valor, gen, idade, esperado in testes:
            result = self.gerenciador.classificar_valor(nome, valor, gen, idade)
            self.teste(f"{nome} {valor} → {esperado}", 
                      result['status'] == esperado,
                      esperado, result['status'])
    
    def testar_valores_qualitativos(self):
        """Testa classificação de valores qualitativos"""
        print("\n" + "="*70)
        print("TESTES: VALORES QUALITATIVOS")
        print("="*70)
        
        testes = [
            ("Proteínas", "Ausentes", "NORMAL"),
            ("Glicose", "Ausente", "NORMAL"),
            ("Hemoglobina", "Presente", "ALTERADO"),
            ("Nitrito", "Não Reagente", "NORMAL"),
            ("Corpos cetônicos", "Ausentes", "NORMAL"),
        ]
        
        for nome, valor, esperado in testes:
            result = self.gerenciador.classificar_valor_qualitativo(nome, valor)
            self.teste(f"{nome}: {valor} → {esperado}", 
                      result['status'] == esperado,
                      esperado, result['status'])
    
    def testar_categoria(self):
        """Testa busca de categoria"""
        print("\n" + "="*70)
        print("TESTES: BUSCA DE CATEGORIA")
        print("="*70)
        
        testes = [
            ("Creatinina", "BIOQUÍMICA"),
            ("Colesterol Total", "LIPIDOGRAMA"),
            ("Hemoglobina", "HEMOGRAMA"),
            ("TSH", "TIREOIDE"),
            ("Proteínas", "URINA"),
        ]
        
        for nome, esperado in testes:
            categoria = self.gerenciador.buscar_categoria(nome)
            self.teste(f"{nome} → {esperado}", 
                      categoria == esperado,
                      esperado, categoria)
    
    def testar_listagens(self):
        """Testa listagens de dados"""
        print("\n" + "="*70)
        print("TESTES: LISTAGENS")
        print("="*70)
        
        # Categorias
        categorias = self.gerenciador.get_categorias()
        self.teste("Existem categorias", len(categorias) > 0,
                  ">0", len(categorias))
        self.teste("BIOQUÍMICA em categorias", "BIOQUÍMICA" in categorias)
        self.teste("HEMOGRAMA em categorias", "HEMOGRAMA" in categorias)
        
        # Exames
        exames = self.gerenciador.get_todos_exames()
        self.teste("Existem exames", len(exames) > 40,
                  ">40", len(exames))
        self.teste("Creatinina em exames", "Creatinina" in exames)
        self.teste("Glicemia Jejum em exames", "Glicemia Jejum" in exames)
    
    def testar_export_json(self):
        """Testa export JSON"""
        print("\n" + "="*70)
        print("TESTES: EXPORT JSON")
        print("="*70)
        
        # Exportar referência
        json_ref = self.gerenciador.exportar_referencia_json("Creatinina")
        
        self.teste("JSON válido", isinstance(json_ref, dict))
        self.teste("JSON tem 'exame'", 'exame' in json_ref)
        self.teste("JSON tem 'categoria'", 'categoria' in json_ref)
        
        # Serializar para string
        try:
            json_str = json.dumps(json_ref, ensure_ascii=False)
            self.teste("JSON serializável", len(json_str) > 10)
        except:
            self.teste("JSON serializável", False)
    
    def testar_casos_extremos(self):
        """Testa casos extremos"""
        print("\n" + "="*70)
        print("TESTES: CASOS EXTREMOS")
        print("="*70)
        
        # Exame não encontrado
        result = self.gerenciador.classificar_valor(
            "EXAME_INEXISTENTE", 100.0
        )
        self.teste("Exame inexistente → INDEFINIDO", 
                  result['status'] == "INDEFINIDO")
        
        # Valor zero
        result = self.gerenciador.classificar_valor(
            "Glicemia Jejum", 0.0
        )
        self.teste("Valor muito baixo → ALTERADO",
                  result['status'] == "ALTERADO")
        
        # Valor negativo (se permitido)
        result = self.gerenciador.classificar_valor(
            "Glicemia Jejum", -50.0
        )
        self.teste("Valor negativo → ALTERADO",
                  result['status'] == "ALTERADO")
    
    def rodar_todos(self):
        """Roda todos os testes"""
        print("\n")
        print("╔" + "="*68 + "╗")
        print("║" + " "*15 + "TESTE GERENCIADOR DE REFERÊNCIAS" + " "*21 + "║")
        print("╚" + "="*68 + "╝")
        
        self.testar_busca_referencia()
        self.testar_classificacao_normal()
        self.testar_classificacao_alterado()
        self.testar_valores_qualitativos()
        self.testar_categoria()
        self.testar_listagens()
        self.testar_export_json()
        self.testar_casos_extremos()
        
        print("\n" + "="*70)
        print("RESULTADO FINAL")
        print("="*70)
        print(f"Total de testes: {self.total_testes}")
        print(f"Passou:          {self.total_passou} ✓")
        print(f"Falhou:          {self.total_falhou} ✗")
        
        if self.total_falhou == 0:
            print("\n✅ TODOS OS TESTES PASSARAM!")
        else:
            print(f"\n⚠️  {self.total_falhou} testes falharam")
        
        print("="*70 + "\n")
        
        self.gerenciador.desconectar()
        
        return self.total_falhou == 0

def main():
    """Função principal"""
    testes = TestesGerenciador()
    sucesso = testes.rodar_todos()
    
    # Retornar código de saída apropriado
    sys.exit(0 if sucesso else 1)

if __name__ == "__main__":
    main()
