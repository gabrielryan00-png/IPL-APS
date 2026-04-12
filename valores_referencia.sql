-- =====================================================
-- BANCO DE DADOS VALORES DE REFERÊNCIA LABORATORIAIS
-- =====================================================

-- Tabela de categorias de exames
CREATE TABLE IF NOT EXISTS categorias_exames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT
);

-- Tabela principal de valores de referência
CREATE TABLE IF NOT EXISTS valores_referencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL,
    nome_exame TEXT NOT NULL,
    genero TEXT,  -- 'M', 'F', 'A' (ambos), NULL = sem distinção
    idade_min INTEGER,  -- idade mínima para faixa etária
    idade_max INTEGER,  -- idade máxima para faixa etária
    valor_min REAL,
    valor_max REAL,
    valor_min_optimismo REAL,  -- valor limítrofe inferior
    valor_max_pessimismo REAL,  -- valor limítrofe superior
    unidade TEXT,
    referencia_texto TEXT,  -- texto original do laudo
    notas TEXT,
    ativo BOOLEAN DEFAULT 1,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (categoria_id) REFERENCES categorias_exames(id),
    UNIQUE(nome_exame, genero, idade_min, idade_max)
);

-- Valores qualitativos (Negativo, Ausente, etc)
CREATE TABLE IF NOT EXISTS valores_qualitativos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL,
    nome_exame TEXT NOT NULL,
    valor_normal TEXT NOT NULL,  -- valores considerados normais
    ativo BOOLEAN DEFAULT 1,
    FOREIGN KEY (categoria_id) REFERENCES categorias_exames(id)
);

-- =====================================================
-- INSERÇÃO DE CATEGORIAS
-- =====================================================

INSERT OR IGNORE INTO categorias_exames (nome, descricao) VALUES
('BIOQUÍMICA', 'Exames bioquímicos gerais'),
('LIPIDOGRAMA', 'Colesterol e triglicérides'),
('ENZIMAS', 'Enzimas hepáticas e musculares'),
('DIABETES', 'Marcadores de diabetes'),
('TIREOIDE', 'Hormônios tireoidianos'),
('HORMÔNIOS', 'Hormônios sexuais e outros'),
('HEMOGRAMA', 'Contagem celular do sangue'),
('LEUCOGRAMA', 'Diferencial de leucócitos'),
('URINA', 'Análise de urina tipo I'),
('SOROLOGIAS', 'Testes sorológicos e outros');

-- =====================================================
-- BIOQUÍMICA
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Ureia', NULL, NULL, NULL, 15.0, 43.0, 'mg/dL', '15 a 43 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Creatinina', 'M', NULL, NULL, 0.6, 1.2, 'mg/dL', '0.6 a 1.2 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Creatinina', 'F', NULL, NULL, 0.5, 1.0, 'mg/dL', '0.5 a 1.0 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'TFGe', NULL, NULL, NULL, 60.0, NULL, 'mL/min/1.73m²', '> 60 mL/min/1.73m²'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Ácido Úrico', 'M', NULL, NULL, 3.5, 7.0, 'mg/dL', '3.5 a 7.0 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Ácido Úrico', 'F', NULL, NULL, 2.5, 6.2, 'mg/dL', '2.5 a 6.2 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Glicemia Jejum', NULL, NULL, NULL, 75.0, 99.0, 'mg/dL', '75 a 99 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Sódio', NULL, NULL, NULL, 137.0, 145.0, 'mmol/L', '137 a 145 mmol/L'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Potássio', NULL, NULL, NULL, 3.5, 5.1, 'mmol/L', '3.5 a 5.1 mmol/L'),
((SELECT id FROM categorias_exames WHERE nome='BIOQUÍMICA'), 'Cálcio Sérico', NULL, NULL, NULL, 8.4, 10.2, 'mg/dL', '8.4 a 10.2 mg/dL');

-- =====================================================
-- LIPIDOGRAMA
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'Colesterol Total', NULL, 20, NULL, NULL, 190.0, 'mg/dL', '< 190 mg/dL (desejável)'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'Colesterol Total', NULL, 0, 19, NULL, 170.0, 'mg/dL', '< 170 mg/dL (desejável)'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'Triglicérides', NULL, 21, NULL, NULL, 150.0, 'mg/dL', 'até 150 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'Triglicérides', NULL, 10, 19, NULL, 90.0, 'mg/dL', 'até 90 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'Triglicérides', NULL, 0, 9, NULL, 75.0, 'mg/dL', 'até 75 mg/dL'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'HDL', NULL, 0, 17, 45.0, NULL, 'mg/dL', '> 45 mg/dL (ideal)'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'HDL', NULL, 18, NULL, 40.0, NULL, 'mg/dL', '> 40 mg/dL (ideal)'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'LDL', NULL, NULL, NULL, NULL, 115.0, 'mg/dL', '< 115 mg/dL (desejável)'),
((SELECT id FROM categorias_exames WHERE nome='LIPIDOGRAMA'), 'VLDL', NULL, NULL, NULL, NULL, 30.0, 'mg/dL', 'até 30 mg/dL');

-- =====================================================
-- ENZIMAS / FÍGADO
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='ENZIMAS'), 'TGO/AST', NULL, NULL, NULL, NULL, 46.0, 'U/L', '< 46 U/L'),
((SELECT id FROM categorias_exames WHERE nome='ENZIMAS'), 'TGP/ALT', 'M', NULL, NULL, NULL, 50.0, 'U/L', '< 50 U/L'),
((SELECT id FROM categorias_exames WHERE nome='ENZIMAS'), 'TGP/ALT', 'F', NULL, NULL, NULL, 35.0, 'U/L', '< 35 U/L'),
((SELECT id FROM categorias_exames WHERE nome='ENZIMAS'), 'CPK', NULL, NULL, NULL, 55.0, 170.0, 'U/L', '55 a 170 U/L'),
((SELECT id FROM categorias_exames WHERE nome='ENZIMAS'), 'Amilase', NULL, NULL, NULL, 30.0, 110.0, 'U/L', '30 a 110 U/L');

-- =====================================================
-- DIABETES
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto, notas) VALUES
((SELECT id FROM categorias_exames WHERE nome='DIABETES'), 'HbA1c', NULL, NULL, NULL, NULL, 5.7, '%', '< 5.7 %', 'Normal'),
((SELECT id FROM categorias_exames WHERE nome='DIABETES'), 'HbA1c', NULL, NULL, NULL, 5.7, 6.4, '%', '5.7 a 6.4 %', 'Pré-diabetes'),
((SELECT id FROM categorias_exames WHERE nome='DIABETES'), 'HbA1c', NULL, NULL, NULL, 6.5, NULL, '%', '≥ 6.5 %', 'Diabetes');

-- =====================================================
-- TIREOIDE
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'TSH', NULL, 20, 59, 0.45, 4.5, 'mUI/L', '0.45 a 4.5 mUI/L'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'TSH', NULL, 60, 69, 0.44, 6.8, 'mUI/L', '0.44 a 6.8 mUI/L'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'TSH', NULL, 70, 80, 0.44, 7.9, 'mUI/L', '0.44 a 7.9 mUI/L'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'T4 Livre', NULL, NULL, NULL, 0.8, 1.8, 'ng/dL', '0.8 a 1.8 ng/dL'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'T4 Total', NULL, NULL, NULL, 4.5, 12.6, 'ug/dL', '4.5 a 12.6 ug/dL'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'T3 Total', NULL, NULL, NULL, 0.76, 2.20, 'ng/mL', '0.76 a 2.20 ng/mL'),
((SELECT id FROM categorias_exames WHERE nome='TIREOIDE'), 'TPO (Anti-TPO)', NULL, NULL, NULL, NULL, 9.0, 'UI/mL', '< 9 UI/mL');

-- =====================================================
-- HORMÔNIOS
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto, notas) VALUES
((SELECT id FROM categorias_exames WHERE nome='HORMÔNIOS'), 'Prolactina', 'F', NULL, NULL, 6.2, 23.4, 'ng/mL', '6.2 a 23.4 ng/mL', 'Feminino reprodutivo'),
((SELECT id FROM categorias_exames WHERE nome='HORMÔNIOS'), 'Prolactina', 'F', NULL, NULL, 4.2, 18.4, 'ng/mL', '4.2 a 18.4 ng/mL', 'Feminino pós-menopáusa'),
((SELECT id FROM categorias_exames WHERE nome='HORMÔNIOS'), 'Prolactina', 'M', NULL, NULL, 4.0, 18.4, 'ng/mL', '4.0 a 18.4 ng/mL', 'Masculino'),
((SELECT id FROM categorias_exames WHERE nome='HORMÔNIOS'), 'PSA', 'M', NULL, NULL, 0.0, 2.5, 'ng/mL', '0 a 2.5 ng/mL', 'Antígeno Específico da Próstata');

-- =====================================================
-- HEMOGRAMA - ADULTO MASCULINO
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Eritrócitos', 'M', 18, NULL, 4.50, 5.50, 'milhões/mm³', '4.50 a 5.50 milhões/mm³'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Hemoglobina', 'M', 18, NULL, 13.0, 17.0, 'g%', '13.0 a 17.0 g%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Hematócrito', 'M', 18, NULL, 40.0, 50.0, '%', '40 a 50%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'VCM', 'M', 18, NULL, 83.0, 100.0, 'u³', '83 a 100 u³'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'HCM', 'M', 18, NULL, 27.0, 32.0, 'pg', '27 a 32 pg'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'CHCM', 'M', 18, NULL, 31.5, 34.5, 'g%', '31.5 a 34.5 g%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'RDW', 'M', 18, NULL, 11.5, 14.0, '%', '11.5 a 14.0%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Leucócitos', 'M', 18, NULL, 3700.0, 9500.0, '/mm³', '3700 a 9500 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Plaquetas', NULL, NULL, NULL, 150000.0, 450000.0, '/mm³', '150.000 a 450.000 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Vol. Plaquetário Médio', NULL, NULL, NULL, 8.1, 12.2, 'fL', '8.1 a 12.2 fL');

-- =====================================================
-- HEMOGRAMA - ADULTO FEMININO
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto) VALUES
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Eritrócitos', 'F', 18, NULL, 3.80, 4.80, 'milhões/mm³', '3.80 a 4.80 milhões/mm³'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Hemoglobina', 'F', 18, NULL, 12.0, 15.0, 'g%', '12.0 a 15.0 g%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Hematócrito', 'F', 18, NULL, 36.0, 46.0, '%', '36 a 46%'),
((SELECT id FROM categorias_exames WHERE nome='HEMOGRAMA'), 'Leucócitos', 'F', 18, NULL, 3900.0, 11100.0, '/mm³', '3900 a 11100 /mm³');

-- =====================================================
-- LEUCOGRAMA (DIFERENCIAL)
-- =====================================================

INSERT OR IGNORE INTO valores_referencia (categoria_id, nome_exame, genero, idade_min, idade_max, valor_min, valor_max, unidade, referencia_texto, notas) VALUES
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Segmentados', NULL, NULL, NULL, 42.0, 70.0, '%', '42 a 70%', 'Percentual / 1800-7000 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Eosinófilos', NULL, NULL, NULL, 1.0, 4.0, '%', '1 a 4%', 'Percentual / 50-600 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Basófilos', NULL, NULL, NULL, 0.0, 1.0, '%', '0 a 1%', 'Percentual / 0-200 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Linfócitos', NULL, NULL, NULL, 20.0, 45.0, '%', '20 a 45%', 'Percentual / 1000-4000 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Monócitos', NULL, NULL, NULL, 2.0, 8.0, '%', '2 a 8%', 'Percentual / 80-1200 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Metamielócitos', NULL, NULL, NULL, 0.0, 1.0, '%', '0 a 1%', 'Percentual / 0-100 /mm³'),
((SELECT id FROM categorias_exames WHERE nome='LEUCOGRAMA'), 'Bastonetes', NULL, NULL, NULL, 0.0, 6.0, '%', '0 a 6%', 'Percentual / 0-1000 /mm³');

-- =====================================================
-- VALORES QUALITATIVOS - URINA
-- =====================================================

INSERT OR IGNORE INTO valores_qualitativos (categoria_id, nome_exame, valor_normal) VALUES
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Proteínas', 'Ausentes'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Glicose', 'Ausente'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Hemoglobina', 'Ausente'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Nitrito', 'Não Reagente'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Corpos cetônicos', 'Ausentes'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Pigmentos biliares', 'Ausentes'),
((SELECT id FROM categorias_exames WHERE nome='URINA'), 'Urobilinogênio', 'Normal');

-- =====================================================
-- VALORES QUALITATIVOS - SOROLOGIAS
-- =====================================================

INSERT OR IGNORE INTO valores_qualitativos (categoria_id, nome_exame, valor_normal) VALUES
((SELECT id FROM categorias_exames WHERE nome='SOROLOGIAS'), 'Anti-HTLV 1 e 2', 'Não Reagente'),
((SELECT id FROM categorias_exames WHERE nome='SOROLOGIAS'), 'Pesquisa Sangue Oculto', 'Negativo');

-- =====================================================
-- ÍNDICES PARA PERFORMANCE
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_valores_ref_nome ON valores_referencia(nome_exame);
CREATE INDEX IF NOT EXISTS idx_valores_ref_genero ON valores_referencia(genero);
CREATE INDEX IF NOT EXISTS idx_valores_ref_categoria ON valores_referencia(categoria_id);
CREATE INDEX IF NOT EXISTS idx_valores_qual_nome ON valores_qualitativos(nome_exame);

-- =====================equals================================================
-- VIEWS ÚTEIS
-- =====================================================

-- View para buscar referência com prioridade de correspondência
CREATE VIEW IF NOT EXISTS v_referenciais AS
SELECT 
    c.nome AS categoria,
    vr.nome_exame,
    vr.genero,
    vr.idade_min,
    vr.idade_max,
    vr.valor_min,
    vr.valor_max,
    vr.unidade,
    vr.referencia_texto
FROM valores_referencia vr
JOIN categorias_exames c ON vr.categoria_id = c.id
WHERE vr.ativo = 1
ORDER BY vr.nome_exame, vr.genero, vr.idade_min;
