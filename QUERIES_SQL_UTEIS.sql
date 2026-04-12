-- =====================================================
-- QUERIES SQL ÚTEIS - valores_referencia.db
-- =====================================================
-- Copia estas queries no seu cliente SQLite para análises rápidas

-- =====================================================
-- 1. EXPLORAÇÃO BÁSICA
-- =====================================================

-- Ver todas as categorias
SELECT id, nome, COUNT(*) as total_exames 
FROM categorias_exames 
LEFT JOIN valores_referencia ON categorias_exames.id = categoria_id
GROUP BY id
ORDER BY nome;

-- Ver todos os exames cadastrados
SELECT nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade
FROM valores_referencia 
WHERE ativo = 1
ORDER BY nome_exame, genero;

-- Ver um exame específico com todas as faixas
SELECT * 
FROM valores_referencia 
WHERE UPPER(nome_exame) LIKE '%CREATININA%'
AND ativo = 1;

-- =====================================================
-- 2. CONSULTAS POR GÊNERO
-- =====================================================

-- Exames que diferem por gênero (M vs F)
SELECT nome_exame, 
       MAX(CASE WHEN genero='M' THEN valor_max ELSE NULL END) as max_M,
       MAX(CASE WHEN genero='F' THEN valor_max ELSE NULL END) as max_F
FROM valores_referencia
WHERE ativo = 1
GROUP BY nome_exame
HAVING MAX(CASE WHEN genero='M' THEN valor_max END) != 
       MAX(CASE WHEN genero='F' THEN valor_max END)
AND COUNT(DISTINCT genero) > 1;

-- Exames específicos para homens
SELECT nome_exame, valor_min, valor_max, unidade
FROM valores_referencia
WHERE genero = 'M' 
AND ativo = 1
ORDER BY nome_exame;

-- Exames específicos para mulheres
SELECT nome_exame, valor_min, valor_max, unidade
FROM valores_referencia
WHERE genero = 'F' 
AND ativo = 1
ORDER BY nome_exame;

-- =====================================================
-- 3. CONSULTAS POR IDADE
-- =====================================================

-- Exames com faixa etária definida
SELECT nome_exame, idade_min, idade_max, valor_min, valor_max, unidade
FROM valores_referencia
WHERE idade_min IS NOT NULL 
OR idade_max IS NOT NULL
AND ativo = 1
ORDER BY nome_exame, idade_min;

-- Referência de TSH por faixa etária
SELECT idade_min, idade_max, valor_min, valor_max, referencia_texto
FROM valores_referencia
WHERE UPPER(nome_exame) = 'TSH'
AND ativo = 1
ORDER BY idade_min;

-- Colesterol por faixa etária
SELECT nome_exame, idade_min, idade_max, valor_max, unidade
FROM valores_referencia
WHERE UPPER(nome_exame) LIKE '%COLESTEROL%'
AND ativo = 1
ORDER BY idade_min;

-- =====================================================
-- 4. CONSULTAS POR CATEGORIA
-- =====================================================

-- Todos os exames de LIPIDOGRAMA
SELECT vr.nome_exame, vr.genero, vr.valor_min, vr.valor_max, vr.unidade
FROM valores_referencia vr
JOIN categorias_exames c ON vr.categoria_id = c.id
WHERE c.nome = 'LIPIDOGRAMA'
AND vr.ativo = 1
ORDER BY vr.nome_exame;

-- Todos os exames de HEMOGRAMA
SELECT vr.nome_exame, vr.genero, vr.valor_min, vr.valor_max, vr.unidade
FROM valores_referencia vr
JOIN categorias_exames c ON vr.categoria_id = c.id
WHERE c.nome = 'HEMOGRAMA'
AND vr.ativo = 1
ORDER BY vr.nome_exame;

-- Todos os exames da categoria BIOQUÍMICA com unidadeS
SELECT DISTINCT vr.unidade, COUNT(*) as total
FROM valores_referencia vr
JOIN categorias_exames c ON vr.categoria_id = c.id
WHERE c.nome = 'BIOQUÍMICA'
GROUP BY vr.unidade;

-- =====================================================
-- 5. VALORES QUALITATIVOS
-- =====================================================

-- Listar todos os valores qualitativos
SELECT vq.nome_exame, vq.valor_normal, c.nome as categoria
FROM valores_qualitativos vq
JOIN categorias_exames c ON vq.categoria_id = c.id
WHERE vq.ativo = 1
ORDER BY c.nome, vq.nome_exame;

-- Valores normais de urina
SELECT nome_exame, valor_normal
FROM valores_qualitativos
WHERE categoria_id = (SELECT id FROM categorias_exames WHERE nome = 'URINA')
AND ativo = 1;

-- =====================================================
-- 6. ANÁLISES DE LIMITES
-- =====================================================

-- Exames com apenas limite mínimo
SELECT nome_exame, valor_min, valor_max, unidade, referencia_texto
FROM valores_referencia
WHERE valor_min IS NOT NULL 
AND valor_max IS NULL
AND ativo = 1
ORDER BY nome_exame;

-- Exames com apenas limite máximo
SELECT nome_exame, valor_min, valor_max, unidade, referencia_texto
FROM valores_referencia
WHERE valor_min IS NULL 
AND valor_max IS NOT NULL
AND ativo = 1
ORDER BY nome_exame;

-- Exames com amplitude (MAX - MIN) maior que 10
SELECT nome_exame, valor_min, valor_max, (valor_max - valor_min) as amplitude, unidade
FROM valores_referencia
WHERE valor_max > valor_min
AND (valor_max - valor_min) > 10
AND ativo = 1
ORDER BY amplitude DESC;

-- =====================================================
-- 7. BUSCA AVANÇADA
-- =====================================================

-- Buscar por padrão no nome (case-insensitive)
SELECT nome_exame, genero, valor_min, valor_max, unidade
FROM valores_referencia
WHERE UPPER(nome_exame) LIKE '%GLICO%'
AND ativo = 1;

-- Buscar por unidade específica
SELECT nome_exame, valor_min, valor_max, genero, unidade
FROM valores_referencia
WHERE unidade = 'mg/dL'
AND ativo = 1
ORDER BY nome_exame;

-- Buscar por categoria E unidade
SELECT vr.nome_exame, vr.valor_min, vr.valor_max, c.nome as categoria, vr.unidade
FROM valores_referencia vr
JOIN categorias_exames c ON vr.categoria_id = c.id
WHERE c.nome = 'HEMOGRAMA'
AND vr.unidade IN ('g%', 'milhões/mm³', '/mm³')
AND vr.ativo = 1;

-- =====================================================
-- 8. ESTATÍSTICAS
-- =====================================================

-- Total de exames por categoria
SELECT c.nome as categoria, COUNT(vr.id) as total
FROM categorias_exames c
LEFT JOIN valores_referencia vr ON c.id = vr.categoria_id AND vr.ativo = 1
GROUP BY c.id, c.nome
ORDER BY total DESC;

-- Distribuição de unidades
SELECT unidade, COUNT(*) as total
FROM valores_referencia
WHERE ativo = 1
GROUP BY unidade
ORDER BY total DESC;

-- Distribuição por gênero
SELECT genero, COUNT(*) as total
FROM valores_referencia
WHERE ativo = 1
GROUP BY genero
ORDER BY genero;

-- Quantos exames têm faixa etária definida
SELECT 
    COUNT(*) as total_exames,
    SUM(CASE WHEN idade_min IS NOT NULL OR idade_max IS NOT NULL THEN 1 ELSE 0 END) as com_faixa_etaria,
    ROUND(100.0 * SUM(CASE WHEN idade_min IS NOT NULL OR idade_max IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as percentual
FROM valores_referencia
WHERE ativo = 1;

-- =====================================================
-- 9. MAINTENANCE / LIMPEZA
-- =====================================================

-- Desativar exame específico (soft delete)
UPDATE valores_referencia SET ativo = 0
WHERE UPPER(nome_exame) = 'NOME_DO_EXAME';

-- Reativar exame
UPDATE valores_referencia SET ativo = 1
WHERE UPPER(nome_exame) = 'NOME_DO_EXAME';

-- Visualizar inativos
SELECT nome_exame, referencia_texto
FROM valores_referencia
WHERE ativo = 0;

-- Deletar dados insensivelmente (CUIDADO!)
DELETE FROM valores_referencia
WHERE UPPER(nome_exame) = 'EXAME_ERRADO'
AND ativo = 1;

-- =====================================================
-- 10. QUERIES PARA DEBUG
-- =====================================================

-- Verifique integridade referencial
SELECT 'Categorias sem exames' as tipo,
       COUNT(*) as problema
FROM categorias_exames c
WHERE NOT EXISTS (
    SELECT 1 FROM valores_referencia vr 
    WHERE vr.categoria_id = c.id
);

-- Check de duplicatas
SELECT nome_exame, genero, idade_min, idade_max, COUNT(*) as duplicatas
FROM valores_referencia
WHERE ativo = 1
GROUP BY nome_exame, genero, idade_min, idade_max
HAVING COUNT(*) > 1;

-- Valores com inconsistências (min > max)
SELECT nome_exame, valor_min, valor_max
FROM valores_referencia
WHERE valor_min > valor_max
AND valor_min IS NOT NULL
AND valor_max IS NOT NULL;

-- =====================================================
-- 11. EXPORT / BACKUP
-- =====================================================

-- Export simples em CSV-like format (copie o resultado)
SELECT nome_exame || ' | ' || 
       COALESCE(genero, 'A') || ' | ' ||
       COALESCE(CAST(idade_min AS TEXT), '-') || '-' ||
       COALESCE(CAST(idade_max AS TEXT), '-') || ' | ' ||
       COALESCE(CAST(valor_min AS TEXT), 'N/A') || ' a ' ||
       COALESCE(CAST(valor_max AS TEXT), 'N/A') || ' | ' ||
       unidade
FROM valores_referencia
WHERE ativo = 1
ORDER BY nome_exame;

-- =====================================================
-- 12. COMO RODAR ESTAS QUERIES
-- =====================================================

/*
Opção 1: Via linha de comando
$ sqlite3 valores_referencia.db "SELECT * FROM categorias_exames;"

Opção 2: Interativo
$ sqlite3 valores_referencia.db
sqlite> SELECT * FROM categorias_exames;
sqlite> .exit

Opção 3: Python
from gerenciador_referencias import GerenciadorReferencias
g = GerenciadorReferencias()
cursor = g.conexao.cursor()
cursor.execute("SELECT * FROM categorias_exames")
print(cursor.fetchall())
g.desconectar()
*/
