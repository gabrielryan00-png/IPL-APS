
import os
import re
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
import imapclient
import pyzmail
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ---------------- CONFIGURAÇÃO ----------------
EMAIL         = os.getenv("GMAIL_EMAIL",    "")
SENHA_APP     = os.getenv("GMAIL_SENHA",    "")
REMETENTE_LAB = os.getenv("REMETENTE_LAB",  "")
_DATA_DIR     = os.getenv("DATA_DIR",       ".")
PASTA_EXAMES  = os.path.join(_DATA_DIR, "exames")
RELATORIO     = os.path.join(_DATA_DIR, "relatorio_exames.xlsx")

if not os.path.exists(PASTA_EXAMES):
    os.makedirs(PASTA_EXAMES)

# ---------------- CONEXÃO COM GMAIL ----------------
try:
    imap = imapclient.IMAPClient('imap.gmail.com', ssl=True)
    imap.login(EMAIL, SENHA_APP)
    imap.select_folder('INBOX')

    # Filtro: Não lidos, do remetente específico e recebidos a partir de HOJE
    hoje = date.today()
    uids = imap.search(['UNSEEN', 'FROM', REMETENTE_LAB, 'SINCE', hoje])
    print(f"{len(uids)} novos exames encontrados desde {hoje.strftime('%d/%m/%Y')}.")

    # ---------------- BAIXAR ANEXOS PDF ----------------
    for uid in uids:
        raw_message = imap.fetch([uid], ['BODY[]'])
        message = pyzmail.PyzMessage.factory(raw_message[uid][b'BODY[]'])
        for part in message.mailparts:
            if part.filename and part.filename.lower().endswith('.pdf'):
                filepath = os.path.join(PASTA_EXAMES, part.filename)
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload())
                print(f"Baixado: {part.filename}")
    
    imap.logout()
except Exception as e:
    print(f"Erro na conexão com e-mail: {e}")

# ---------------- FUNÇÕES PARA PROCESSAR PDF ----------------
def extrai_texto_pdf(pdf_path):
    texto = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            page_text = pagina.extract_text()
            if page_text:
                texto += page_text + "\n"
    return texto.strip()

def extrai_texto_ocr(pdf_path):
    texto = ""
    imagens = convert_from_path(pdf_path)
    for img in imagens:
        texto += pytesseract.image_to_string(img, lang='por') + "\n"
    return texto.strip()

def ler_pdf(pdf_path):
    try:
        texto = extrai_texto_pdf(pdf_path)
        if len(texto) < 100:  # PDF muito curto provavelmente é imagem/escaneado
            texto = extrai_texto_ocr(pdf_path)
        return texto
    except Exception as e:
        print(f"Erro ao ler PDF {pdf_path}: {e}")
        return ""

def extrair_metadados(texto):
    metadados = {}
    patterns = {
        'Pedido': r"Pedido[:\s]*([A-Za-z0-9-]+)",
        'Paciente': r"Paciente[:\s]*([A-Za-z\s]+)",
        'CPF': r"CPF[:\s]*([\d\.]+-?\d+)",
        'Medico': r"Médico[:\s]*([A-Za-z\s]+)",
        'Origem': r"Origem[:\s]*([A-Za-z\s]+)",
        'DataCadastro': r"Data de Cadastro[:\s]*(\d{2}/\d{2}/\d{4})",
        'DataEmissao': r"Data de Emissão[:\s]*(\d{2}/\d{2}/\d{4})",
        'HoraEmissao': r"Hora[:\s]*(\d{2}:\d{2})"
    }
    for chave, regex in patterns.items():
        m = re.search(regex, texto)
        if m:
            metadados[chave] = m.group(1).strip()
    return metadados

def extrair_exames(texto):
    exames = []
    # Regex para capturar Analito, Valor, Unidade, Referência e Observação
    padrao = re.compile(r"([A-ZÀ-ÿ\s]+)\s+([\d,\.]+)\s*([a-zA-Z%/µmol/dL]*)\s+([\d,\.]+\s*-\s*[\d,\.]+)\s*(.*)?")
    
    for match in padrao.findall(texto):
        analito, valor, unidade, referencia, observacao = match
        try:
            valor_num = float(valor.replace(',', '.'))
            limites = referencia.replace(',', '.').split('-')
            limite_inferior = float(limites[0].strip())
            limite_superior = float(limites[1].strip())
            
            if valor_num < limite_inferior:
                status = "[ALTERADO] ABAIXO"
            elif valor_num > limite_superior:
                status = "[ALTERADO] ACIMA"
            else:
                status = "NORMAL"
                
            exames.append({
                "Analito": analito.strip(),
                "Valor": valor_num,
                "Unidade": unidade.strip(),
                "Referencia": referencia.strip(),
                "Status": status,
                "Observacao": observacao.strip()
            })
        except (ValueError, IndexError):
            continue 
    return exames

# ---------------- PROCESSAMENTO DOS ARQUIVOS ----------------
todos_resultados = []

if os.path.exists(PASTA_EXAMES):
    arquivos = [f for f in os.listdir(PASTA_EXAMES) if f.lower().endswith(".pdf")]
    for arquivo in arquivos:
        caminho = os.path.join(PASTA_EXAMES, arquivo)
        print(f"Processando {arquivo}...")
        texto_completo = ler_pdf(caminho)
        
        if not texto_completo:
            continue
            
        metadados = extrair_metadados(texto_completo)
        lista_exames = extrair_exames(texto_completo)
        
        for exame in lista_exames:
            # Combina os dados do paciente com os dados do exame
            resultado_final = {**metadados, **exame, "Arquivo": arquivo}
            todos_resultados.append(resultado_final)

# ---------------- GERAR RELATÓRIO ----------------
if todos_resultados:
    df = pd.DataFrame(todos_resultados)
    df.to_excel(RELATORIO, index=False)
    print(f"\nSucesso! Relatório gerado: {RELATORIO}")
else:
    print("\nNenhum dado extraído para o relatório.")
