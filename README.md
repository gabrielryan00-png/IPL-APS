# IPL-APS — Sistema Municipal de Prioridade Laboratorial

Sistema de inteligência clínica laboratorial para Atenção Primária à Saúde, desenvolvido para a rede de USFs do município de Suzano/SP.

## O que faz

- **Ingere laudos de exames** automaticamente via Gmail (PDF)
- **Calcula o IPL** (Índice de Prioridade Laboratorial) por paciente — score composto com 7 dimensões clínicas
- **Identifica padrões sinérgicos** (nefropatia diabética, DRC + anemia, síndrome metabólica etc.)
- **Mapeia gaps de cuidado** — exames essenciais ausentes por condição crônica
- **Vigilância territorial** — prevalência de alterações analíticas por USF
- **Multi-USF** — isolamento de dados por território, com controle de acesso por papel

## Arquitetura

```
processaexames.py   →  exames.db (SQLite por USF)
                              ↓
ipl_engine.py       →  cálculo IPL + vigilância territorial
                              ↓
gateway.py          →  API REST (FastAPI + JWT)
                              ↓
iclabs_v5.html      →  dashboard (Triagem · Vigilância · Gaps · Perfil)
```

## Score IPL

Compressão exponencial com 7 componentes:

```
IPL = 100 × (1 − e^{−raw/90})
```

| Componente | Descrição |
|---|---|
| Score laboratorial base | Analitos alterados × fator de magnitude |
| Padrões sinérgicos | Combinações clínicas (21 padrões) |
| Faixa etária | Bônus por decênio ≥ 60 anos |
| Tendência temporal | Velocidade de deterioração |
| Lacuna de coleta | Dias sem exame recente |
| Multimorbidade | Progressão não-linear de condições crônicas |
| Estádio renal | Bônus G3b–G5 pela TFGe CKD-EPI |

## Instalação

```bash
# 1. Clone e entre no diretório
git clone https://github.com/gabrielryan00-png/IPL-APS.git
cd IPL-APS

# 2. Ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 3. Dependências
pip install -r requirements.txt

# 4. Configuração
cp .env.example .env
# Edite .env com suas credenciais

# 5. Banco de referências e autenticação
sqlite3 valores_referencia.db < valores_referencia.sql
python setup_auth.py

# 6. Inicie o gateway
python gateway.py
# Acesse: http://localhost:8080
```

## Variáveis de ambiente

Ver [.env.example](.env.example) para a lista completa.

| Variável | Descrição |
|---|---|
| `GMAIL_EMAIL` | Conta Gmail que recebe os laudos |
| `GMAIL_SENHA` | Senha de app do Gmail |
| `REMETENTE_LAB` | E-mail remetente do laboratório |
| `JWT_SECRET_KEY` | Chave secreta JWT (gerar com `secrets.token_hex(32)`) |
| `DATA_DIR` | Diretório raiz dos dados |
| `AUTH_DB` | Caminho do banco de autenticação |
| `ADMIN_PASSWORD` | Senha do administrador |

## Estrutura de arquivos

```
IPL-APS/
├── gateway.py              # API REST (FastAPI + JWT + multi-USF)
├── ipl_engine.py           # Motor de cálculo IPL
├── iclabs_v5.html          # Dashboard web
├── processaexames.py       # Extrator de laudos PDF via Gmail
├── setup_auth.py           # Inicialização do banco de autenticação
├── gerenciador_referencias.py  # Gerenciador de valores de referência
├── config_gerenciador.py   # Configuração dos analitos
├── utils_analitos.py       # Normalização e utilitários
├── ocr_melhorado.py        # OCR para PDFs sem texto embutido
├── valores_referencia.sql  # Schema + dados dos valores de referência
├── QUERIES_SQL_UTEIS.sql   # Consultas úteis para análise
├── .env.example            # Template de configuração
└── requirements.txt        # Dependências Python
```

## Papéis de acesso

| Papel | Acesso |
|---|---|
| `admin` | Todos os territórios, gestão de usuários e USFs, log de acessos |
| `user` | Apenas o próprio território (usf_id vinculado ao usuário) |

## Requisitos de sistema

- Python 3.10+
- Tesseract OCR (`sudo apt install tesseract-ocr tesseract-ocr-por`)
- Poppler (`sudo apt install poppler-utils`)

---

Secretaria Municipal de Saúde · Suzano/SP
