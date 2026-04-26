# IPL-APS — Demonstração Visual do Sistema

> Capturas de tela do ambiente de produção da **USF Vila Amorim · Suzano/SP** (abril/2026).
> Todos os dados de pacientes individuais foram anonimizados. Métricas agregadas
> seguem a política de privacidade descrita no `ESTUDO_DE_CASO.md`.

---

## 1. Painel do Território

Visão geral da USF: totais de pacientes, distribuição por nível de prioridade IPL,
condições crônicas prevalentes e top alterações laboratoriais do território.

![Painel do Território](screenshots/painel_territorio.png)

### O que está sendo exibido

| Elemento | Descrição |
|---|---|
| **Pacientes** | Total de pacientes com ≥ 1 exame processado no território |
| **Alta Prioridade** | Pacientes nas faixas "Prioridade Acompanhamento" e "Avaliação Prioritária" |
| **Gaps de Cuidado** | Pacientes com ≥ 1 exame essencial vencido dado seu perfil de crônicos |
| **IPL Médio** | Média do score composto de todos os pacientes ativos |
| **Distribuição de Prioridade** | Barra proporcional em 4 faixas (Seguimento Habitual → Avaliação Prioritária) |
| **Condições Crônicas** | DM2, Anemia, Gota, DRC, Tireoidopatia, Hepatopatia, DLP com contagem absoluta |
| **Top Alterações** | Analitos com maior taxa de resultado ALTERADO na última coleta de cada paciente |

---

## 2. Vigilância Analítica do Território

Prevalência de alterações por analito — considera apenas a **última coleta** de cada
paciente, evitando dupla contagem. Exibe somente analitos com ≥ 67 pacientes testados.

![Vigilância Analítica](screenshots/vigilancia_analitica.png)

### Classificação de padrão

| Rótulo | Critério |
|---|---|
| **CRÍTICO** | Prevalência ≥ 50 % |
| **PREVALENTE** | Prevalência ≥ 20 % |
| *(sem rótulo)* | Prevalência < 20 % |

Os analitos mais críticos neste território: GME (68,6 %), HbA1c (67,1 %),
TFGe (60,2 %) e Monócitos (50,8 %) — padrão compatível com síndrome
metabólica + DRC em população predominantemente idosa.

---

## 3. Triagem IPL-APS — Lista de Pacientes Críticos

Fila ordenada por score IPL decrescente. Exibe analito crítico dominante,
dias desde a última coleta, número de gaps de cuidado e tendência clínica.
**Nomes anonimizados — apenas scores e indicadores clínicos preservados.**

![Pacientes Críticos — Anonimizados](screenshots/pacientes_criticos.png)

### Como ler a lista

| Coluna | Significado |
|---|---|
| Analito (subtítulo) | Analito que mais contribuiu para o score IPL do paciente |
| `Xd sem coleta` | Dias desde a última coleta registrada |
| Score (vermelho) | IPL final: `100 × (1 − e^{−score_bruto/90})` |
| Badge de gaps | Quantidade de exames essenciais vencidos |
| Badge de tendência | MELHORA / PIORA GRAVE / SEM HISTÓRICO ANTERIOR |

---

## 4. Resumo Clínico de Triagem — Perfil Individual

Detalhe de um paciente (dados clínicos, sem identificação). Exibe os exames
alterados que compõem o score, condições crônicas inferidas, lacuna analítica
e tendência global.

![Resumo Clínico](screenshots/resumo_clinico_triagem.png)

### Painel de exames alterados

Cada card mostra: analito · valor medido · referência · grupo fisiopatológico ·
pontuação parcial (+PT). A cor do card indica magnitude do desvio:

- **Vermelho** → desvio crítico
- **Amarelo** → desvio moderado  
- **Verde-escuro** → desvio leve

### Condições crônicas inferidas

O engine infere condições crônicas a partir de combinações de analitos alterados
(sem CID, sem prontuário). Exemplo: DM2 ← HbA1c ↑ + GME ↑; DRC ← Creatinina ↑
+ TFGe ↓; Anemia ← Hemoglobina ↓.

---

## 5. Lacuna Analítica — Exames Essenciais

Detalhe dos exames que deveriam ter sido coletados dado o perfil de crônicos
do paciente, mas estão vencidos ou nunca foram realizados.

![Lacuna Analítica](screenshots/lacuna_analitica.png)

### Como a lacuna é calculada

Para cada condição crônica inferida, o sistema mantém um dicionário de
analitos essenciais com intervalo máximo de recoleta (ex.: Glicose a cada 30 d
para DM2, HbA1c a cada 90 d). Um gap é gerado quando:

```
dias_desde_última_coleta > intervalo_esperado
```

O badge **LACUNA CRÍTICA** é exibido quando há ≥ 1 gap de prioridade alta.

---

## Arquitetura resumida do fluxo

```
PDF (e-mail)
    │
    ▼
OCR (Tesseract + pdfminer)
    │  extração: analito · valor · unidade · referência · status
    ▼
SQLite (por USF)
    │  deduplicação: paciente × analito × data_exame
    ▼
IPL Engine  ─────────────────────────────────────────────────
    │  Σ(7 componentes)                                      │
    │  compressão exponencial: 100×(1−e^{−x/90})             │
    ▼                                                        ▼
Score IPL por paciente                          Gaps de cuidado
    │                                                        │
    └──────────────┬─────────────────────────────────────────┘
                   ▼
            Painel Web (iclabs_v5.html)
            ├─ Painel do Território
            ├─ Triagem IPL-APS
            ├─ Vigilância Analítica
            ├─ Gaps de Cuidado
            └─ Perfil Longitudinal por Paciente
```

---

## Reprodução das capturas

As imagens deste documento foram capturadas com o servidor local em execução:

```bash
python servidor_ipl.py          # inicia na porta 8080
# abre http://localhost:8080 no navegador
```

Para regenerar a imagem anonimizada de pacientes:

```bash
# coloque o print original em docs/screenshots/pacientes_criticos_original.png
python docs/anonimizar_print_pacientes.py
```

---

*IPL-APS v5.1 · USF Vila Amorim · Suzano/SP · Abril/2026*  
*Dados anonimizados · Uso exclusivamente acadêmico e de saúde pública*
