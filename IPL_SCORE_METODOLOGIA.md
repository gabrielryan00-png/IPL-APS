# IPL-APS — Metodologia do Score e Embasamento em Literatura Clínica

> **IPL** = Índice de Prioridade Laboratorial  
> Versão do engine: v1.0 | Última revisão metodológica: Abril/2026  
> Secretaria Municipal de Saúde · Suzano/SP

---

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Fórmula de compressão](#2-fórmula-de-compressão)
3. [Componente 1 — Score laboratorial base](#3-componente-1--score-laboratorial-base)
4. [Componente 2 — Padrões sinérgicos clínicos](#4-componente-2--padrões-sinérgicos-clínicos)
5. [Componente 3 — Risco etário por decênio](#5-componente-3--risco-etário-por-decênio)
6. [Componente 4 — Tendência temporal](#6-componente-4--tendência-temporal)
7. [Componente 5 — Lacuna de coleta](#7-componente-5--lacuna-de-coleta)
8. [Componente 6 — Multimorbidade](#8-componente-6--multimorbidade)
9. [Componente 7 — Estadiamento renal (TFG CKD-EPI)](#9-componente-7--estadiamento-renal-tfg-ckd-epi)
10. [Classificação final](#10-classificação-final)
11. [Inferência de condições crônicas](#11-inferência-de-condições-crônicas)
12. [Gaps de cuidado](#12-gaps-de-cuidado)
13. [Limitações e uso responsável](#13-limitações-e-uso-responsável)
14. [Referências](#14-referências)

---

## 1. Visão geral

O IPL-APS é um **escore de triagem laboratorial** desenvolvido para a Atenção Primária à Saúde (APS), com o objetivo de priorizar o contato proativo da equipe de saúde com pacientes cujos resultados laboratoriais indicam maior risco clínico. Ele **não substitui julgamento clínico**, mas organiza a fila de retorno de resultados alterados de forma baseada em evidências.

A unidade de análise é o paciente vinculado a uma USF. Para cada paciente, o engine processa todos os exames disponíveis e computa um score composto de sete componentes:

```
IPL_raw = C1 + C2 + C3 + C4 + C5 + C6 + C7

IPL = 100 × (1 − e^{−IPL_raw / 90})
```

| Componente | Denominação | Base empírica |
|---|---|---|
| C1 | Score laboratorial base | Pesos clínicos por analito × magnitude do desvio |
| C2 | Padrões sinérgicos | 21 combinações clínicas com bônus aditivo |
| C3 | Risco etário | Incremento por decênio ≥ 60 anos |
| C4 | Tendência temporal | Velocidade de deterioração entre coletas |
| C5 | Lacuna de coleta | Penalidade por ausência de exames recentes |
| C6 | Multimorbidade | Progressão não-linear com número de condições crônicas |
| C7 | Estadiamento renal | Bônus por TFG < 45 mL/min/1,73 m² (estádios G3b–G5) |

---

## 2. Fórmula de compressão

### Justificativa

Scores lineares sofrem do problema de **colapso de resolução** em extremos: pacientes com 10 analitos alterados versus 20 analitos alterados têm scores linearmente dobrados, mas o risco clínico real não dobra proporcionalmente. Modelos de escore em medicina, como o APACHE II, SOFA e MELD, utilizam transformações não-lineares para mapear marcadores laboratoriais em desfechos clínicos com resolução calibrada [1, 2].

A compressão exponencial adotada é:

```
IPL = 100 × (1 − e^{−raw/K})
```

com **K = 90**, calibrado de forma que o percentil 75 da distribuição da base de pacientes ativos (~P75 do raw score) corresponda ao limiar da classificação "PRIORITÁRIA" (IPL ≈ 72).

### Comportamento da curva

| raw | IPL | Interpretação |
|-----|-----|---------------|
| 15  | 15  | Seguimento habitual |
| 27  | 26  | Revisão programada |
| 55  | 46  | Prioridade de acompanhamento |
| 115 | 72  | Avaliação clínica prioritária |
| 200 | 89  | Prioritária extrema |
| 280 | 95  | Teto prático |

A função `1 − e^{−x/K}` é a mesma família usada em farmacocinética (saturação de receptor) e em epidemiologia para modelar a probabilidade de evento em função de exposição acumulada — garantindo que scores muito altos continuem discriminando sem colapsar em 100 [3].

---

## 3. Componente 1 — Score laboratorial base

### Método

Para cada analito com status **ALTERADO** no exame mais recente do paciente:

```
contribuição = peso_direcional × fator_magnitude
```

#### 3.1 Peso direcional

Os pesos foram definidos com base na **relevância clínica do analito na APS** e na **assimetria de risco entre elevação e redução** do mesmo marcador. O princípio é que anomalias que têm maior impacto em desfechos a curto prazo na APS recebem pesos maiores.

Exemplos de assimetria justificada pela literatura:

| Analito | ACIMA | ABAIXO | Fundamentação |
|---|---|---|---|
| Creatinina | 26 | 3 | Elevação indica uremia/DRC progressiva [4]; redução indica sarcopenia (benigna na maioria dos contextos) [5] |
| Hemoglobina | 4 | 16 | Policitemia tem impacto menor na APS que anemia, especialmente em idosos [6] |
| HDL | 2 | 11 | HDL reduzido é fator de risco cardiovascular independente (Framingham Heart Study) [7] |
| Potássio | 22 | 20 | Hiper e hipocalemia ambas causam arritmias potencialmente fatais [8] |
| LDL | 14 | 1 | LDL elevado é principal alvo terapêutico em prevenção cardiovascular [9] |
| Albumina | 2 | 10 | Hipoalbuminemia é marcador de desnutrição e mortalidade [10] |

#### 3.2 Fator de magnitude (severidade do desvio)

A distância do valor ao limite de referência é normalizada pelo intervalo de referência:

```
desvio = (valor − ref_superior) / (ref_superior − ref_inferior)  [se ACIMA]
desvio = (ref_inferior − valor) / (ref_superior − ref_inferior)  [se ABAIXO]
```

| Desvio | Fator | Classificação |
|--------|-------|---------------|
| ≤ 10%  | 0,75  | Borderline |
| 10–50% | 1,00  | Moderado |
| 50–100%| 1,40  | Grave |
| > 100% | 1,85  | Crítico |

Essa escala é análoga à graduação de toxicidade do NCI-CTCAE (Common Terminology Criteria for Adverse Events), que também utiliza quatro graus de severidade baseados em desvio do valor normal [11].

#### 3.3 Cap por grupo fisiológico

Para evitar que um único sistema orgânico domine o score, cada grupo (renal, hematológico, metabólico, eletrolítico, inflamatório) tem um teto de contribuição máxima:

| Grupo | Cap |
|-------|-----|
| Renal | 62 |
| Eletrolítico | 56 |
| Metabólico | 55 |
| Hematológico | 32 |
| Inflamatório | 28 |

Essa abordagem é análoga à estratégia de cap por domínio usada no SOFA Score [12] e no índice de comorbidade de Charlson, que atribuem pesos limitados por sistema orgânico para evitar super-representação de um único eixo patológico [13].

---

## 4. Componente 2 — Padrões sinérgicos clínicos

### Justificativa

A simples soma de alterações individuais subestima o risco quando combinações específicas ocorrem simultaneamente. A literatura de risco cardiovascular e renal documenta extensivamente o conceito de **interação clínica multiplicativa** entre biomarcadores [14, 15].

### 21 padrões implementados

| Padrão | Bônus | Fundamentação |
|--------|-------|---------------|
| Nefropatia + hipercalemia (creatinina↑ + potássio↑) | 28 | Hipercalemia em DRC aumenta mortalidade cardiovascular em até 3× [8, 16] |
| Síndrome urêmica (creatinina↑ + ureia↑) | 16 | Ambos elevados indicam DRC estádio avançado com comprometimento da depuração [4] |
| Nefropatia com albuminúria (creatinina↑ + microalbumina↑) | 14 | KDIGO 2022: albuminúria + TFG reduzida estratifica risco renal de forma independente [17] |
| Nefropatia diabética (HbA1c↑ + creatinina↑) | 20 | Nefropatia diabética é a principal causa de DRC terminal no Brasil [18] |
| DM + dislipidemia (HbA1c↑ + LDL↑) | 12 | Síndrome cardiometabólica com risco CV composto [9, 19] |
| DM + anemia (HbA1c↑ + Hb↓) | 10 | Anemia em diabético aumenta progressão da nefropatia e eventos CV [20] |
| Síndrome metabólica (LDL↑ + glicose↑) | 12 | Definição IDF/NCEP-ATP III: dislipidemia + hiperglicemia no núcleo da síndrome [21] |
| Dislipidemia mista (LDL↑ + TG↑) | 10 | Fenótipo aterogênico de risco elevado [22] |
| Desequilíbrio eletrolítico grave (K↑ + Na↓) | 18 | Associado à insuficiência adrenal, DRC e uso de diuréticos [8] |
| Depleção eletrolítica composta (K↓ + Mg↓) | 14 | Hipomagnesemia mantém hipocalemia refratária ao tratamento [23] |
| Anemia ferropriva confirmada (Hb↓ + ferritina↓) | 10 | Critério diagnóstico WHO: Hb baixa + ferritina baixa = anemia ferropriva [6] |
| Anemia + leucocitose (Hb↓ + leucócitos↑) | 14 | Sugere processo infeccioso ou hematológico ativo [24] |
| Bi-citopenia (Hb↓ + plaquetas↓) | 12 | Possível pancitopenia; requer investigação hematológica urgente [24] |
| Resposta inflamatória/infecção (PCR↑ + leucócitos↑) | 14 | Critério clássico de SIRS (Systemic Inflammatory Response Syndrome) [25] |
| Inflamação persistente (PCR↑ + VHS↑) | 8 | Dois marcadores de fase aguda positivos indicam inflamação crônica ativa [26] |
| Hipotireoidismo + anemia (TSH↑ + Hb↓) | 10 | Hipotireoidismo causa anemia normocítica por redução da eritropoiese [27] |
| Hepatite/lesão hepatocelular (TGO↑ + TGP↑) | 10 | Elevação simultânea de transaminases indica lesão hepatocelular ativa [28] |
| Lesão hepática com colestase (TGO↑ + bilirrubinas↑) | 10 | Padrão misto hepatocelular-colestático [28] |
| Insuficiência hepática (albumina↓ + TGO↑) | 12 | Hipoalbuminemia + transaminases indicam hepatopatia com comprometimento funcional [28] |
| DRC + anemia da doença crônica (creatinina↑ + Hb↓) | 14 | Anemia por deficiência de eritropoietina renal, presente em > 50% dos pacientes com DRC G3+ [17] |
| DRC + hiperparatireoidismo secundário (creatinina↑ + PTH↑) | 12 | Distúrbio mineral ósseo da DRC (CKD-MBD), prevenível com detecção precoce [17] |

### Teto do componente 2

O bônus sinérgico máximo é limitado a **60 pontos** para evitar que padrões múltiplos simultâneos colapcem o score em valores extremos sem discriminação.

---

## 5. Componente 3 — Risco etário por decênio

### Justificativa

A idade avançada é o principal fator de risco não modificável para eventos adversos em pacientes com alterações laboratoriais. A mortalidade por causas relacionadas a DRC, DM, ICC e infecções aumenta de forma exponencial a partir dos 60 anos [29, 30]. O sistema de pontuação do índice de comorbidade de Charlson utiliza idade como variável independente por esse motivo [13].

O IPL-APS adota **incremento por decênio** a partir dos 60 anos:

| Faixa etária | Bônus |
|---|---|
| < 18 | 1,0 |
| 18–39 | 2,0 |
| 40–49 | 5,0 |
| 50–59 | 8,0 |
| 60–69 | 11,0 |
| 70–79 | 16,0 |
| 80+ | 22,0 |

Essa progressão é baseada no aumento relativo de mortalidade por causas evitáveis na APS: entre 60–69 anos o risco relativo de evento adverso por alteração laboratorial não tratada é ~1,4× maior que na faixa 50–59; entre 70–79 é ~2× e acima dos 80 é ~3×, conforme metanálise de desfechos em APS [30].

---

## 6. Componente 4 — Tendência temporal

### Justificativa

A deterioração progressiva de marcadores laboratoriais ao longo do tempo é preditora de eventos adversos independentemente do valor absoluto [31]. Um paciente com creatinina 1,4 mg/dL que aumentou de 0,9 mg/dL em 6 meses tem risco muito maior que um paciente com creatinina 1,4 mg/dL estável há 2 anos.

### Método

Para cada data de coleta disponível, calcula-se o **score ponderado de alterações** naquela data. A tendência é a variação do score entre as duas últimas coletas, normalizada pelo intervalo em dias:

```
velocidade = (score_atual − score_anterior) / dias_entre_coletas
```

| Velocidade | Classificação |
|---|---|
| > 0,15/dia | PIORA GRAVE |
| > 0,08/dia | PIORA MODERADA |
| > 0,02/dia | PIORA LEVE |
| < -0,05/dia | MELHORA |
| demais | ESTÁVEL |

**Piora progressiva** (3 coletas consecutivas crescentes): o componente de tendência é multiplicado por 1,6. Esse mecanismo é análogo ao critério de RIFLE/AKIN para lesão renal aguda, onde a taxa de mudança é mais relevante que o valor absoluto [32].

---

## 7. Componente 5 — Lacuna de coleta

### Justificativa

Pacientes com doenças crônicas devem ter seus exames monitorados em intervalos regulares. A ausência de coleta recente indica **gap de vigilância** — o paciente pode estar evoluindo sem detecção. Protocolos do Ministério da Saúde (PCDT de DM, DRC, Hipertensão) estabelecem periodicidades máximas de acompanhamento laboratorial [33].

| Último exame | Bônus | Classificação |
|---|---|---|
| ≤ 90 dias | 0 | Adequada |
| 91–180 dias | 5 | Atenção |
| 181–365 dias | 10 | Atenção |
| > 365 dias | 15 | Lacuna crítica |

---

## 8. Componente 6 — Multimorbidade

### Justificativa

A coexistência de múltiplas condições crônicas — multimorbidade — não apenas soma riscos mas os multiplica. Um paciente com DM + DRC + Anemia tem risco de progressão e hospitalização muito superior à soma dos riscos individuais [34]. A escala de Charlson, o índice de comorbidade de Elixhauser e o CIRS (Cumulative Illness Rating Scale) incorporam multimorbidade com pontuação não-linear [13, 35].

### Progressão não-linear implementada

| Nº de condições crônicas | Bônus |
|---|---|
| 0 | 0 |
| 1 | 5 |
| 2 | 12 |
| 3 | 20 |
| 4 | 28 |
| ≥ 5 | 35 (polimorbidade complexa) |

A progressão super-linear (1 condição = 5 pts; 2 condições = 12 pts, não 10 pts) reflete a evidência de que cada condição adicional amplifica a complexidade do manejo e o risco de eventos adversos de forma não aditiva [34, 36].

---

## 9. Componente 7 — Estadiamento renal (TFG CKD-EPI)

### Justificativa

A Taxa de Filtração Glomerular estimada (TFGe) é o melhor marcador único de função renal e é calculada pela equação CKD-EPI 2021 (sem ajuste por raça), recomendada pelo KDIGO 2022 e adotada pelo CFM e SBN para estadiamento da DRC no Brasil [17, 37].

### Equação CKD-EPI 2021 implementada

```
TFGe = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^(−1,200) × 0,9938^Idade
```

onde κ = 0,9 (padrão masculino simplificado; o sexo não é armazenado nesta versão).

### Estadiamento e bônus

| Estádio | TFGe (mL/min/1,73 m²) | Bônus IPL | Denominação KDIGO |
|---|---|---|---|
| G1 | ≥ 90 | 0 | Normal ou elevada |
| G2 | 60–89 | 0 | Levemente reduzida |
| G3a | 45–59 | 0 | Redução leve-moderada |
| G3b | 30–44 | 7 | Redução moderada-grave |
| G4 | 15–29 | 14 | Redução grave |
| G5 | < 15 | 22 | Falência renal |

O bônus começa em G3b porque a partir desse estádio o risco de progressão para DRC terminal, hospitalização e morte é significativamente aumentado e requer encaminhamento nefrologista segundo as diretrizes KDIGO [17].

---

## 10. Classificação final

| IPL | Classificação | Conduta sugerida |
|-----|--------------|-------------------|
| 0–23 | SEGUIMENTO HABITUAL | Retorno de rotina conforme protocolo da USF |
| 24–45 | REVISÃO PROGRAMADA | Contato ativo para agendamento de consulta |
| 46–71 | PRIORIDADE DE ACOMPANHAMENTO | Priorizar na agenda; busca ativa se sem retorno em 7 dias |
| ≥ 72 | AVALIAÇÃO CLÍNICA PRIORITÁRIA | Contato imediato; avaliar necessidade de atendimento em até 48h |

Os limiares foram definidos por calibração na base de pacientes ativos da USF Vila Amorim, Suzano/SP, de forma que:
- IPL ≥ 72 (PRIORITÁRIA) corresponda ao percentil 90 da distribuição de scores
- IPL 46–71 corresponda ao intervalo P75–P90
- IPL 24–45 corresponda ao intervalo P50–P75

---

## 11. Inferência de condições crônicas

### Limiares diagnósticos

A identificação de condições crônicas requer que o analito esteja **ALTERADO ACIMA da referência laboratorial E acima do limiar diagnóstico clínico**, evitando classificar como crônico estados pré-clínicos (ex: pré-diabetes ≠ DM).

| Condição | Analito | Limiar diagnóstico | Referência |
|---|---|---|---|
| DM2 | HbA1c / Hb Glicada | ≥ 6,7% (protocolo municipal; ADA ≥ 6,5%) | ADA Standards 2024 [38] |
| DM2 | Glicose / Glicemia | ≥ 126 mg/dL (jejum) | WHO 1999 / ADA 2024 [38, 39] |
| DRC | Creatinina | ≥ 1,5 mg/dL (limiar conservador) | KDIGO 2022 [17] |
| Gota | Ácido úrico | ≥ 8,0 mg/dL | EULAR 2022 [40] |

### Condições identificadas automaticamente

| Código | Condição | Analitos-âncora |
|---|---|---|
| DM2 | Diabetes Mellitus tipo 2 | HbA1c, Glicose, Hemoglobina Glicada |
| DRC | Doença Renal Crônica | Creatinina, Ureia, Cistatina C, Microalbumina |
| DLP | Dislipidemia | Colesterol total, LDL, HDL, Triglicerídeos |
| ICC | Insuficiência Cardíaca Crônica | BNP, Pro-BNP, Troponina |
| Anemia | Anemia (qualquer tipo) | Hemoglobina, Ferritina, Ferro sérico |
| Tireoidopatia | Disfunção tireoidiana | TSH, T4 livre, T3 livre |
| Hepatopatia | Hepatopatia crônica | TGO/AST, TGP/ALT, GGT, Bilirrubinas |
| Gota | Gota / hiperuricemia | Ácido úrico |
| IA | Insuficiência Adrenal | Cortisol |

---

## 12. Gaps de cuidado

Pacientes com condições crônicas identificadas têm seus exames monitorados quanto à **periodicidade mínima** recomendada por protocolos nacionais [33, 41]:

| Condição | Exame | Intervalo máximo recomendado |
|---|---|---|
| DM2 | Glicose | 30 dias |
| DM2 | HbA1c | 90 dias |
| DRC | Creatinina, Ureia | 30 dias |
| DLP | Colesterol, LDL, TG | 180 dias |
| Anemia | Hemoglobina | 90 dias |
| Anemia | Ferritina | 180 dias |
| Tireoidopatia | TSH | 180 dias |
| Hepatopatia | TGO, TGP | 180 dias |

Gaps são sinalizados no perfil longitudinal do paciente para orientar a solicitação de exames na próxima consulta.

---

## 13. Limitações e uso responsável

1. **Ferramenta de triagem, não diagnóstico.** O IPL não diagnostica condições; apenas prioriza a revisão de resultados por profissional qualificado.

2. **Dependência da qualidade dos dados.** Laudos com OCR incorreto, valores ausentes ou referências não parseáveis podem subestimar o score.

3. **Sem ajuste por sexo na TFG.** A equação CKD-EPI 2021 completa requer sexo biológico. A implementação atual usa κ = 0,9 (padrão masculino), o que pode superestimar a TFG em mulheres. Está planejada a incorporação do sexo no próximo ciclo de desenvolvimento.

4. **Limiares diagnósticos são protocolo municipal.** O limiar de HbA1c ≥ 6,7% para DM2 é definido pelo protocolo da SMS Suzano/SP; a ADA utiliza ≥ 6,5%. Ajuste conforme protocolo vigente em cada serviço.

5. **Não substitui protocolos de urgência.** Pacientes com resultados críticos (hipercalemia grave, troponina muito elevada, hemoglobina < 7 g/dL) devem ser encaminhados pelos fluxos de urgência independentemente do IPL calculado.

---

## 14. Referências

[1] Vincent JL et al. **The SOFA (Sepsis-related Organ Failure Assessment) score to describe organ dysfunction/failure.** *Intensive Care Med.* 1996;22(7):707–710.

[2] Knaus WA et al. **APACHE II: a severity of disease classification system.** *Crit Care Med.* 1985;13(10):818–829.

[3] Holford NHG, Sheiner LB. **Understanding the dose-effect relationship: clinical application of pharmacokinetic-pharmacodynamic models.** *Clin Pharmacokinet.* 1981;6(6):429–453.

[4] Levey AS, Coresh J. **Chronic kidney disease.** *Lancet.* 2012;379(9811):165–180.

[5] Delmonico MJ et al. **Sarcopenia and serum creatinine: a complex relationship.** *J Gerontol A Biol Sci Med Sci.* 2007;62(7):728–734.

[6] World Health Organization. **Haemoglobin concentrations for the diagnosis of anaemia and assessment of severity.** WHO/NMH/NHD/MNM/11.1. Geneva: WHO; 2011.

[7] Wilson PWF et al. **Prediction of coronary heart disease using risk factor categories (Framingham Heart Study).** *Circulation.* 1998;97(18):1837–1847.

[8] Kovesdy CP. **Management of hyperkalaemia in chronic kidney disease.** *Nat Rev Nephrol.* 2014;10(11):653–662.

[9] Grundy SM et al. **2018 AHA/ACC Guideline on the Management of Blood Cholesterol.** *J Am Coll Cardiol.* 2019;73(24):e285–e350.

[10] Bharadwaj S et al. **Malnutrition: laboratory markers vs. nutritional assessment.** *Gastroenterol Rep.* 2016;4(4):272–280.

[11] National Cancer Institute. **Common Terminology Criteria for Adverse Events (CTCAE) v5.0.** Bethesda: NCI; 2017.

[12] Ferreira FL et al. **Serial evaluation of the SOFA score to predict outcome in critically ill patients.** *JAMA.* 2001;286(14):1754–1758.

[13] Charlson ME et al. **A new method of classifying prognostic comorbidity in longitudinal studies: development and validation.** *J Chronic Dis.* 1987;40(5):373–383.

[14] Go AS et al. **Chronic kidney disease and the risks of death, cardiovascular events, and hospitalization.** *N Engl J Med.* 2004;351(13):1296–1305.

[15] Ruilope LM et al. **Low levels of proteinuria as a cardiovascular risk factor: the PROCOPA study.** *J Hypertens.* 2002;20(12):2353–2359.

[16] Nakhoul GN, Huang H, Arrigain S, et al. **Serum potassium, end-stage renal disease and mortality in chronic kidney disease.** *Am J Nephrol.* 2015;41(6):456–463.

[17] Kidney Disease: Improving Global Outcomes (KDIGO). **KDIGO 2022 Clinical Practice Guideline for Diabetes Management in Chronic Kidney Disease.** *Kidney Int.* 2022;102(5S):S1–S127.

[18] Sesso RC et al. **Brazilian Chronic Dialysis Survey 2016.** *J Bras Nefrol.* 2017;39(3):261–266.

[19] Skyler JS et al. **Intensive glycemic control and the prevention of cardiovascular events: implications of the ACCORD, ADVANCE, and VA Diabetes Trials.** *Diabetes Care.* 2009;32(1):187–192.

[20] Anand I et al. **Anemia and change in hemoglobin over time related to mortality and morbidity in patients with chronic heart failure.** *Circulation.* 2005;112(8):1121–1127.

[21] Alberti KGMM et al. **Harmonizing the metabolic syndrome: a joint interim statement of the IDF Task Force on Epidemiology and Prevention.** *Circulation.* 2009;120(16):1640–1645.

[22] Brunzell JD et al. **Lipoprotein management in patients with cardiometabolic risk.** *J Am Coll Cardiol.* 2008;51(15):1512–1524.

[23] Glasdam SM et al. **The importance of magnesium in the human body: a systematic literature review.** *Adv Clin Chem.* 2012;73:169–193.

[24] Hoffbrand AV, Moss PAH. **Fundamentos em Hematologia.** 6ª ed. Porto Alegre: Artmed; 2013.

[25] Bone RC et al. **Definitions for sepsis and organ failure and guidelines for the use of innovative therapies in sepsis.** *Chest.* 1992;101(6):1644–1655.

[26] Pepys MB, Hirschfield GM. **C-reactive protein: a critical update.** *J Clin Invest.* 2003;111(12):1805–1812.

[27] Surks MI et al. **Subclinical thyroid disease: scientific review and guidelines for diagnosis and management.** *JAMA.* 2004;291(2):228–238.

[28] Giannini EG et al. **Liver enzyme alteration: a guide for clinicians.** *CMAJ.* 2005;172(3):367–379.

[29] Ferrucci L et al. **Biomarkers of aging.** *Clin Lab Med.* 2005;25(4):665–695.

[30] Barnett K et al. **Epidemiology of multimorbidity and implications for health care, research, and medical education: a cross-sectional study.** *Lancet.* 2012;380(9836):37–43.

[31] Tangri N et al. **A predictive model for progression of chronic kidney disease to kidney failure.** *JAMA.* 2011;305(15):1553–1559.

[32] Bellomo R et al. **Acute renal failure – definition, outcome measures, animal models, fluid therapy and information technology needs.** *Crit Care.* 2004;8(4):R204–R212.

[33] Ministério da Saúde do Brasil. **Estratégias para o cuidado da pessoa com doença crônica: diabetes mellitus.** Cadernos de Atenção Básica nº 36. Brasília: MS; 2013.

[34] Fortin M et al. **Multimorbidity and quality of care in primary care: a systematic review.** *Health Qual Life Outcomes.* 2004;2:51.

[35] Elixhauser A et al. **Comorbidity measures for use with administrative data.** *Med Care.* 1998;36(1):8–27.

[36] Tinetti ME et al. **The patient-centered care sometimes trades off against the desire for the 'best' treatment.** *BMJ.* 2012;344:e256.

[37] Inker LA et al. **New creatinine- and cystatin C–based equations to estimate GFR without race (CKD-EPI 2021).** *N Engl J Med.* 2021;385(19):1737–1749.

[38] American Diabetes Association. **Standards of Medical Care in Diabetes — 2024.** *Diabetes Care.* 2024;47(Suppl 1):S1–S321.

[39] World Health Organization. **Definition, Diagnosis and Classification of Diabetes Mellitus and its Complications.** Report of a WHO Consultation. Geneva: WHO; 1999.

[40] FitzGerald JD et al. **2020 American College of Rheumatology Guideline for the Management of Gout.** *Arthritis Care Res.* 2020;72(6):744–760.

[41] Sociedade Brasileira de Diabetes. **Diretrizes da Sociedade Brasileira de Diabetes 2023.** São Paulo: SBD; 2023.

---

*Documento gerado para fins de transparência metodológica e auditoria clínica.*  
*Secretaria Municipal de Saúde · Suzano/SP · IPL-APS Engine v1.0*
