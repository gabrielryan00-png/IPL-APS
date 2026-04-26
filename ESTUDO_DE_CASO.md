# Estudo de Caso — IPL-APS na USF Vila Amorim
## Sistema Municipal de Prioridade Laboratorial · Suzano/SP

> **Declaração de anonimização:** todos os dados apresentados neste documento são
> estritamente agregados e anonimizados. Nenhum registro individual, nome,
> data de nascimento, número de prontuário ou qualquer combinação de atributos
> capaz de identificar um paciente é divulgado. O conjunto de dados destina-se
> exclusivamente a fins acadêmicos, de pesquisa e de saúde pública, em conformidade
> com a Lei Geral de Proteção de Dados (LGPD — Lei nº 13.709/2018) e com a
> Resolução CNS nº 510/2016.

---

## 1. Contexto

A **Unidade de Saúde da Família (USF) Vila Amorim** integra a rede de Atenção
Primária à Saúde (APS) do município de Suzano/SP. A partir de dezembro de 2025,
passou a ser o território-piloto para validação do sistema **IPL-APS** — um
mecanismo de inteligência clínico-laboratorial que ingere laudos de exames
digitais via e-mail, calcula um score de prioridade por paciente e gera
alertas de vigilância territorial.

O objetivo deste estudo de caso é documentar os achados do período inicial de
operação (dezembro/2025 – abril/2026), avaliar a distribuição epidemiológica
das alterações laboratoriais e discutir o potencial do sistema como ferramenta
de apoio à triagem na APS.

---

## 2. Metodologia de Coleta e Processamento

| Etapa | Descrição |
|---|---|
| **Ingestão** | Laudos em PDF recebidos por e-mail institucional; leitura via OCR (Tesseract + pdfminer) |
| **Estruturação** | Extração de analito, valor, unidade, referência e status por expressões regulares clínicas |
| **Persistência** | Banco SQLite local por USF; deduplicação por paciente × analito × data de exame |
| **Cálculo IPL** | Score composto de 7 dimensões (laboratorial, tendência, crônicas, TFG, lacuna analítica, padrões sinérgicos, bônus clínico) |
| **Anonimização** | Para este documento: todas as métricas são agregadas; nenhum dado individual é exposto |

### Score IPL-APS — Dimensões e pesos

```
Score bruto = Σ(7 componentes)
IPL final   = 100 × (1 − e^{−score_bruto / 90})   [compressão exponencial]
```

| Componente | Descrição |
|---|---|
| Score laboratorial base | Peso por analito × magnitude do desvio da referência |
| Componente de tendência | Velocidade de deterioração entre coletas consecutivas |
| Componente de crônicos | Condições crônicas inferidas (DM2, DRC, DLP, Tireoidopatia etc.) |
| Componente TFG | Bônus proporcional à queda da taxa de filtração glomerular |
| Bônus de padrões sinérgicos | Nefropatia diabética, DRC+anemia, síndrome metabólica etc. |
| Lacuna analítica | Exames essenciais ausentes dado o perfil de crônicas |
| Tendência dominante | Piora global integrada entre grupos fisiopatológicos |

---

## 3. Caracterização do Território — Dados Agregados

### 3.1 Volumetria geral

| Indicador | Valor |
|---|---|
| Pacientes cadastrados | **1.357** |
| Pacientes com ≥ 1 exame processado | **1.337** (98,5 %) |
| Pacientes com acompanhamento longitudinal (≥ 2 coletas) | **98** (7,3 %) |
| Total de laudos PDF processados | **1.454** |
| Total de resultados de analitos registrados | **70.243** |
| Resultados com status ALTERADO | **9.036** (12,9 %) |
| Média de analitos por paciente | **52,5** (mín 1 · máx 204) |
| Médicos solicitantes distintos | **83** |

### 3.2 Distribuição etária da população cadastrada

| Faixa etária | Pacientes | % |
|---|---|---|
| < 18 anos | 140 | 10,3 % |
| 18–39 anos | 276 | 20,4 % |
| 40–59 anos | 421 | 31,1 % |
| 60–79 anos | 450 | 33,2 % |
| ≥ 80 anos | 68 | 5,0 % |

> **Achado:** 64,3 % da população cadastrada tem 40 anos ou mais — perfil
> esperado para uma USF com carga elevada de doenças crônicas não transmissíveis
> (DCNT). A faixa 60–79 anos é a mais numerosa, reforçando a demanda por
> rastreamento ativo de comorbidades.

### 3.3 Volume mensal de processamento

| Mês | Laudos processados | Pacientes atendidos |
|---|---|---|
| Dez/2025 | 13.067 | 277 |
| Jan/2026 | 1.219 | 23 |
| Fev/2026 | 9.232 | 199 |
| Mar/2026 | 28.861 | 553 |
| Abr/2026 (parcial) | 17.864 | 362 |

> **Nota:** a queda abrupta em janeiro/2026 reflete o período de recesso municipal
> e a adaptação inicial da equipe ao fluxo de encaminhamento eletrônico de laudos.
> A retomada em fevereiro e o pico em março confirmam a adoção crescente do sistema.

---

## 4. Perfil Epidemiológico — Alterações Laboratoriais

### 4.1 Taxa de alteração por analito (principais marcadores clínicos)

A tabela abaixo apresenta os analitos com maior prevalência de resultado ALTERADO,
ordenados pela taxa de alteração. Apenas analitos com ≥ 50 registros são incluídos.

| Analito | Total | Alterados | Taxa |
|---|---|---|---|
| Glicose Média Estimada (GME) | 961 | 658 | **68,5 %** |
| Hemoglobina Glicada (HbA1c) | 893 | 600 | **67,2 %** |
| Taxa de Filtração Glomerular estimada (TFGe) | 114 | 69 | **60,5 %** |
| Triglicérides | 981 | 406 | **41,4 %** |
| Glicemia de Jejum | 1.073 | 392 | **36,5 %** |
| Creatinoquinase (CPK) | 714 | 230 | **32,2 %** |
| VLDL | 958 | 271 | **28,3 %** |
| GGT | 66 | 18 | **27,3 %** |
| Urina — Densidade | 981 | 261 | **26,6 %** |
| Pesquisa de Sangue Oculto nas Fezes | 92 | 22 | **23,9 %** |
| Ferritina | 243 | 52 | **21,4 %** |
| Ureia | 958 | 183 | **19,1 %** |
| Ácido Úrico | 835 | 153 | **18,3 %** |
| Creatinina | 960 | 103 | **10,7 %** |
| LDL-Colesterol | 981 | 92 | **9,4 %** |
| Colesterol Total | 980 | 49 | **5,0 %** |
| HDL-Colesterol | 976 | 33 | **3,4 %** |

### 4.2 Interpretação clínica dos achados

#### Metabolismo glicídico — sinal de alerta prioritário

A taxa de alteração de HbA1c (67,2 %) e GME (68,5 %) é consideravelmente superior
à prevalência nacional de Diabetes Mellitus tipo 2 estimada pelo DATASUS (~10–15 %
na população adulta geral). Esse dado, no entanto, não representa prevalência
populacional bruta: reflete a **população que já foi encaminhada para coleta**,
o que gera viés de seleção — pacientes com sintomas ou fatores de risco têm maior
probabilidade de terem exames solicitados.

Ainda assim, a magnitude do valor (2 em cada 3 exames de HbA1c alterados) sugere
que o perfil de glicemia descompensada na USF Vila Amorim é expressivo e merece
protocolo de rastreamento ativo e intensificação do seguimento.

#### Dislipidemia — padrão de hipertrigliceridemia predominante

O VLDL apresenta 28,3 % de alteração contra apenas 9,4 % de LDL e 3,4 % de HDL,
caracterizando um padrão de **dislipidemia aterogênica com hipertrigliceridemia
predominante** — frequentemente associado a resistência insulínica e síndrome
metabólica, consistente com os dados glicídicos.

#### Função renal — TFGe como marcador sensível

Com 60,5 % de TFGe alterada em 114 registros, há indicativo relevante de Doença
Renal Crônica (DRC) em estágio inicial ou moderado. A creatinina isolada (10,7 %)
subestima a disfunção renal — a TFGe, calculada pela equação CKD-EPI 2021 e
incorporada ao pipeline de OCR, é mais sensível para estágios G2–G3.

#### Ferritina e anemia ferropriva

21,4 % dos registros de ferritina apresentam alteração. Associada ao perfil etário
(33,2 % com 60–79 anos), levanta hipótese de anemia ferropriva subestimada,
demandando rastreamento integrado com hemograma.

---

## 5. Discussão

### 5.1 Viabilidade da abordagem baseada em laudos digitais

A ingestão automática de PDFs por e-mail mostrou-se operacionalmente viável:
**1.454 laudos processados em 5 meses** sem intervenção manual na etapa de
extração. A principal limitação identificada foi a variabilidade de layout entre
laboratórios parceiros, que impacta a precisão do OCR para alguns analitos de
menor frequência.

### 5.2 Score IPL como ferramenta de triagem

O score composto IPL-APS permite ordenar a fila de acompanhamento sem depender
exclusivamente do julgamento subjetivo do profissional. A compressão exponencial
adotada (100 × (1 − e^{−x/90})) evita o efeito de "teto artificial": pacientes
com múltiplas comorbidades severas continuam sendo diferenciados entre si,
preservando a sensibilidade clínica do score mesmo em populações de alta carga.

### 5.3 Limitações do estudo

| Limitação | Impacto | Mitigação |
|---|---|---|
| Viés de seleção | Pacientes com exames = já encaminhados | Comparar com cadastro total da USF |
| Cobertura longitudinal baixa (7,3 %) | Dificulta análise de tendências | Ampliar período de coleta |
| Variabilidade de layout de laudos | OCR falha em ~3–5 % dos campos | Dicionário de padrões em expansão |
| Ausência de CID no laudo | Impede validação diagnóstica formal | Integração com prontuário eletrônico |
| Dados de jan/2026 incompletos | Subestima volume do período | Recesso e adaptação operacional |

### 5.4 Implicações para a gestão municipal

Os achados reforçam três prioridades para a rede de APS de Suzano:

1. **Linha de cuidado DM2/Pré-DM** — alta taxa de HbA1c alterada justifica
   rastreamento populacional ativo e protocolo de estratificação de risco glicêmico.

2. **Vigilância renal integrada** — a discrepância entre TFGe (60,5 %) e creatinina
   (10,7 %) como marcadores de alteração aponta para uso prioritário da TFGe como
   critério de encaminhamento para nefrologia.

3. **Dislipidemia aterogênica** — o padrão VLDL/triglicérides predominante,
   combinado à presença de DM2, sugere síndrome metabólica como cluster frequente
   neste território, demandando abordagem multidisciplinar.

---

## 6. Aspectos Éticos e de Privacidade

| Aspecto | Medida adotada |
|---|---|
| Identificação de pacientes | Nenhum dado individual é exposto; todas as métricas são agregadas |
| Base legal LGPD | Art. 7º, III (execução de política pública) e Art. 13 (dados anonimizados para pesquisa) |
| Resolução CNS 510/2016 | Pesquisa com dados secundários anônimos — dispensada de CEP por força do Art. 1º, §único, V |
| Controle de acesso ao sistema | Autenticação JWT por papel (admin/user), isolamento de banco por USF |
| Retenção de dados | Dados brutos permanecem no servidor local da Secretaria Municipal de Saúde |
| Publicação | Apenas métricas agregadas sem possibilidade de re-identificação |

---

## 7. Conclusão

O piloto na USF Vila Amorim demonstrou que a ingestão automatizada de laudos
laboratoriais digitais, combinada a um score de prioridade multidimensional, é
tecnicamente viável no contexto da APS municipal brasileira com infraestrutura
mínima (um servidor local, acesso a e-mail institucional e banco de dados SQLite).

Os achados epidemiológicos — especialmente a alta prevalência de marcadores
glicídicos e renais alterados — fornecem subsídios concretos para a gestão da
linha de cuidado de DCNT no município, podendo orientar a alocação de recursos,
a definição de metas de produção e o planejamento de campanhas de rastreamento.

A próxima fase do projeto prevê a expansão para demais USFs da rede, validação
clínica do score IPL contra desfechos de internação e hospitalização, e
integração com o prontuário eletrônico municipal (e-SUS/PEC).

---

## Referências metodológicas

- Kidney Disease: Improving Global Outcomes (KDIGO). *CKD Work Group*. Kidney Int Suppl, 2013.
- American Diabetes Association. *Standards of Medical Care in Diabetes*, 2024.
- Sociedade Brasileira de Cardiologia. *IV Diretriz Brasileira sobre Dislipidemias*, 2020.
- FEBRASGO. *Protocolo de Rastreamento de Anemia Ferropriva*, 2022.
- Ministério da Saúde. *Estratégia de Saúde da Família — Guia Prático*, 2023.
- Brasil. *Lei Geral de Proteção de Dados Pessoais* (Lei nº 13.709/2018).
- Conselho Nacional de Saúde. *Resolução nº 510*, de 7 de abril de 2016.

---

*Documento gerado em abril de 2026 · IPL-APS v2.0 · Secretaria Municipal de Saúde — Suzano/SP*
*Dados anonimizados · Uso exclusivamente acadêmico e de saúde pública*
