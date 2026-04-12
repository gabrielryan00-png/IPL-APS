import os
import re
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
import pandas as pd
from typing import Dict, List, Union

# ---------------- CONFIGURAÇÃO ----------------
PASTA_EXAMES = "exames"
RELATORIO = "relatorio_exames.xlsx"

# ---------------- FUNÇÕES DE EXTRAÇÃO DE TEXTO ----------------

def extrai_texto_pdf(pdf_path: str) -> str:
    """Tenta extrair texto direto do PDF."""
    texto = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                t = pagina.extract_text()
                if t:
                    texto += t + "\n"
    except Exception as e:
        print(f"Erro ao extrair texto de {pdf_path}: {e}")
    return texto.strip()

def extrai_texto_ocr(pdf_path: str) -> str:
    """Se PDF for escaneado, converte para imagem e aplica OCR."""
    texto = ""
    try:
        imagens = convert_from_path(pdf_path)
        for img in imagens:
            texto += pytesseract.image_to_string(img, lang='por') + "\n"
    except Exception as e:
        print(f"Erro no OCR de {pdf_path}: {e}")
    return texto.strip()

def ler_pdf(pdf_path: str) -> str:
    """Lê PDF tentando extração direta primeiro, depois OCR se necessário."""
    texto = extrai_texto_pdf(pdf_path)
    if len(texto) < 100:
        print(f"  → OCR...")
        texto = extrai_texto_ocr(pdf_path)
    return texto

# ---------------- EXTRAÇÃO DE METADADOS ----------------

def extrair_nome_paciente_universal(texto: str) -> str:
    """Extrai o nome do paciente de múltiplos layouts."""

    # Layout 1: Nome : NOME COMPLETO
    match = re.search(
        r'Nome\s*:\s*([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)(?:\s+(?:Invalid|S\s*e\s*x\s*o|Sexo|CPF|RG)|$)',
        texto,
        re.IGNORECASE
    )
    if match:
        nome = match.group(1).strip()
        nome = re.sub(r'\s+(Invalid|barcode|data|CPF).*', '', nome, flags=re.IGNORECASE)
        if len(nome) > 3 and len(nome.split()) >= 2:
            return nome

    # Layout 2: N.Pedido NOME N. Registro
    match = re.search(
        r'N\.?\s*Pedido\s+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][A-ZÀÁÂÃÉÊÍÓÔÕÚÇ\s]+?)\s+N\.\s*Registro',
        texto,
        re.IGNORECASE
    )
    if match:
        nome = match.group(1).strip()
        nome = re.sub(r'\d+', '', nome).strip()
        if len(nome) > 3:
            return nome

    return ""

def extrair_metadados(texto: str) -> Dict[str, str]:
    """Extrai metadados do paciente."""
    metadados = {}

    # Nome
    nome_paciente = extrair_nome_paciente_universal(texto)
    if nome_paciente:
        metadados['Paciente'] = nome_paciente

    # Pedido
    match_pedido = re.search(r'(?:N\.?\s*Pedido|Pedido)[:\s]+(\d+)', texto, re.IGNORECASE)
    if match_pedido:
        metadados['Pedido'] = match_pedido.group(1)

    # Data de Nascimento
    match_nasc = re.search(
        r'(?:Dt\.?\s*Nasc|Data\s*Nascimento|Nascimento)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})',
        texto,
        re.IGNORECASE
    )
    if match_nasc:
        metadados['Dt Nasc'] = match_nasc.group(1)

    # Médico
    match_medico = re.search(
        r'Solicitante[:\s]+([A-ZÀ-Ü][A-Za-zà-ÿ\s\.]+?)(?:\s+Data|\n)',
        texto,
        re.IGNORECASE
    )
    if match_medico:
        metadados['Medico'] = match_medico.group(1).strip()

    return metadados

# ---------------- FUNÇÕES DE EXTRAÇÃO DE EXAMES ----------------

def normalizar_valor(valor_str: str) -> Union[float, str]:
    """Converte para float ou mantém como string se qualitativo."""
    if not valor_str or not isinstance(valor_str, str):
        return valor_str

    valor_str = valor_str.strip().replace(',', '.')

    valores_qualitativos = [
        'REAGENTE', 'NAO REAGENTE', 'NÃO REAGENTE', 'NEGATIVO', 'POSITIVO',
        'AUSENTE', 'PRESENTE', 'DETECTADO', 'NAO DETECTADO', 'NÃO DETECTADO',
        'NORMAL', 'ALTERADO', 'AUSENTES', 'RAROS', 'NUMEROSOS', 'INCONTÁVEIS'
    ]

    valor_upper = valor_str.upper()
    for val_qual in valores_qualitativos:
        if val_qual in valor_upper:
            return valor_str

    try:
        valor_limpo = re.sub(r'[^\d\.\-]', '', valor_str)
        if valor_limpo and valor_limpo not in ['.', '-', '.-']:
            return float(valor_limpo)
    except ValueError:
        pass

    return valor_str

def e_analito_observacao(linha: str) -> bool:
    """
    Identifica se o analito é apenas uma observação/alteração morfológica
    que deve ser ignorada.
    """
    observacoes = [
        'MICROCITOSE', 'MACROCITOSE', 'ANISOCITOSE', 'POIQUILOCITOSE',
        'HIPOCROMIA', 'POLICROMASIA', 'DISCRETA', 'MODERADA', 'ACENTUADA',
        'LEVE', 'INTENSA', 'OCASIONAL', 'RAROS', 'NUMEROSOS',
        'VALORES DE', 'SÉRIE BRANCA', 'SÉRIE VERMELHA'
    ]

    linha_upper = linha.upper().strip()

    for obs in observacoes:
        if obs in linha_upper:
            return True

    return False

def e_nome_exame_valido(linha: str) -> bool:
    """Valida se é realmente nome de exame principal."""

    if e_analito_observacao(linha):
        return False

    termos_invalidos = [
        'VALORES', 'RESULTADO', 'AUTENTICIDADE', 'EVOLUÇÃO', 'REFERÊNCIA',
        'UNIDADE', 'MÉTODO', 'MATERIAL', 'LAUDO', 'PÁGINA', 'LABORATÓRIO',
        'PREFEITURA', 'MUNICIPAL', 'DIETA', 'ASSOCIAÇÃO',
        'REQUER', 'CORRELAÇÃO', 'DADOS CLÍNICOS', 'EPIDEMIOLÓGICOS',
        'LIBERADO', 'RESPONSÁVEL', 'EXAMES COLETADOS', 'ANÁLISE',
        'ERITROGRAMA', 'LEUCOGRAMA', 'PEDIDO', 'CPF', 'SOLICITANTE',
        'DESTINO', 'ORIGEM', 'EMISSÃO', 'CNES', 'GRAVIDAS', 'GRÁVIDAS',
        'DATA', 'NOTAS', 'FL.:', 'TRIMESTRE'
    ]

    linha_upper = linha.upper().strip()

    for termo in termos_invalidos:
        if termo in linha_upper:
            return False

    if re.match(r'^[\.\:\-\=\*\_\+]+$', linha):
        return False

    if len(linha.strip()) < 3 or len(linha) > 70:
        return False

    if linha.count(' ') > 10:
        return False

    if re.match(r'^\d', linha):
        return False

    return True

def extrair_resultado_referencia(bloco_texto: str) -> Dict[str, Union[str, float]]:
    """Extrai valor e referência do bloco."""
    dados = {
        'valor': '',
        'unidade': '',
        'ref_inf': '',
        'ref_sup': '',
        'referencia_texto': ''
    }

    match_resultado = re.search(
        r'Resultado[:\s]*(?:\n)?\s*([\d,\.]+)\s+([a-zA-Zµ°/%²³]+(?:/[a-zA-Z]+)?)',
        bloco_texto,
        re.IGNORECASE
    )

    if not match_resultado:
        match_resultado = re.search(
            r'^\s*([\d,\.]+)\s+(mg/dL|g/dL|g/L|g%|mmol/L|mUI/L|U/L|ng/mL|ug/dL|pg/mL|fL|u3|%|/mm³|mil/mm³|milhoes/mm³|x10³/µL|mm³)\s*$',
            bloco_texto,
            re.MULTILINE | re.IGNORECASE
        )

    # Resultado qualitativo
    if not match_resultado:
        match_qualitativo = re.search(
            r'Resultado[:\s]+([A-ZÀÁÂÃÉÊÍÓÔÕÚÇÃÕ][A-Za-zà-ÿ\s]+?)(?:\n|Refer|Obs|Método|Material)',
            bloco_texto,
            re.IGNORECASE
        )
        if match_qualitativo:
            dados['valor'] = match_qualitativo.group(1).strip()
            match_ref_texto = re.search(
                r'(?:Refer[eê]ncia|Valor.*refer[eê]ncia)[:\s]+([A-ZÀ-Ü][a-zà-ÿ\s]+?)(?:\n|$)',
                bloco_texto,
                re.IGNORECASE
            )
            if match_ref_texto:
                dados['referencia_texto'] = match_ref_texto.group(1).strip()
            return dados

    if match_resultado:
        dados['valor'] = normalizar_valor(match_resultado.group(1))
        if len(match_resultado.groups()) > 1:
            dados['unidade'] = match_resultado.group(2).strip()

    match_ref_range = re.search(
        r'(?:De|Refer[eê]ncia)[:\s]*([\d,\.]+)\s*(?:a|até|-)\s*([\d,\.]+)',
        bloco_texto,
        re.IGNORECASE
    )

    if match_ref_range:
        try:
            dados['ref_inf'] = float(match_ref_range.group(1).replace(',', '.'))
            dados['ref_sup'] = float(match_ref_range.group(2).replace(',', '.'))
        except ValueError:
            pass

    return dados

def determinar_status(valor: Union[float, str], ref_inf: Union[float, str],
                     ref_sup: Union[float, str], ref_texto: str) -> str:
    """Determina o status do exame."""
    if ref_texto and isinstance(valor, str):
        valor_upper = valor.upper()
        ref_upper = ref_texto.upper()
        if valor_upper == ref_upper or 'NORMAL' in ref_upper:
            return "NORMAL"
        else:
            return "[ALTERADO]"

    if isinstance(valor, (int, float)) and isinstance(ref_inf, (int, float)) and isinstance(ref_sup, (int, float)):
        if valor < ref_inf:
            return "[ALTERADO] ABAIXO"
        elif valor > ref_sup:
            return "[ALTERADO] ACIMA"
        else:
            return "NORMAL"

    return "N/A"

def extrair_exames(texto: str) -> List[Dict[str, Union[str, float]]]:
    """Extrai todos os exames do texto."""
    exames = []
    linhas = texto.split('\n')

    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()

        if linha and (linha.isupper() or (linha[0].isupper() and len(linha) > 3)):
            if e_nome_exame_valido(linha):
                nome_exame = linha

                fim_bloco = min(i + 20, len(linhas))
                bloco = '\n'.join(linhas[i:fim_bloco])

                dados = extrair_resultado_referencia(bloco)

                if dados['valor'] and dados['valor'] != '':
                    status = determinar_status(
                        dados['valor'],
                        dados['ref_inf'],
                        dados['ref_sup'],
                        dados['referencia_texto']
                    )

                    if dados['ref_inf'] and dados['ref_sup']:
                        referencia = f"{dados['ref_inf']} - {dados['ref_sup']}"
                    elif dados['referencia_texto']:
                        referencia = dados['referencia_texto']
                    else:
                        referencia = ""

                    exames.append({
                        "Analito": nome_exame,
                        "Valor": dados['valor'],
                        "Unidade": dados['unidade'],
                        "Referencia": referencia,
                        "Status": status
                    })

        i += 1

    return exames

# ---------------- PROCESSAMENTO PRINCIPAL ----------------

def processar_exames() -> List[Dict]:
    """Processa todos os PDFs."""
    todos_resultados = []

    if not os.path.exists(PASTA_EXAMES):
        print(f"Erro: Pasta '{PASTA_EXAMES}' não encontrada!")
        return todos_resultados

    arquivos_pdf = [f for f in os.listdir(PASTA_EXAMES) if f.lower().endswith(".pdf")]

    if not arquivos_pdf:
        print(f"Nenhum arquivo PDF encontrado em '{PASTA_EXAMES}'")
        return todos_resultados

    print(f"Encontrados {len(arquivos_pdf)} arquivos PDF\n")

    for arquivo in arquivos_pdf:
        caminho = os.path.join(PASTA_EXAMES, arquivo)
        print(f"📄 {arquivo}")

        try:
            texto = ler_pdf(caminho)

            if not texto or len(texto) < 50:
                print(f"  ⚠️  Texto insuficiente")
                continue

            metadados = extrair_metadados(texto)
            paciente = metadados.get('Paciente', 'NOME NÃO IDENTIFICADO')
            print(f"  👤 {paciente}")

            exames = extrair_exames(texto)
            print(f"  🔬 {len(exames)} exames")

            for exame in exames:
                resultado_final = {**metadados, **exame, "Arquivo": arquivo}
                todos_resultados.append(resultado_final)

                status_emoji = "🔴" if "[ALTERADO]" in exame['Status'] else "✅"
                print(f"     {status_emoji} {exame['Analito']}: {exame['Valor']} {exame['Unidade']}")

        except Exception as e:
            print(f"  ❌ Erro: {e}")

        print()

    return todos_resultados


# =========================
# 🔥 RELATÓRIO COM FILTRO
# =========================
def gerar_relatorio(resultados: List[Dict]) -> None:
    """Gera relatório Excel no layout customizado + aba de pendências + filtros."""
    if not resultados:
        print("⚠️  Nenhum exame processado")
        return

    try:
        df = pd.DataFrame(resultados)

        # ----------------------------
        # 1) LAYOUT CUSTOMIZADO
        # ----------------------------
        colunas_ordem = [
            'Arquivo',
            'Paciente',
            'Pedido',
            'Dt Nasc',
            'Medico',
            'Analito',
            'Valor',
            'Unidade',
            'Referencia',
            'Status'
        ]

        colunas_disponiveis = [col for col in colunas_ordem if col in df.columns]
        df = df[colunas_disponiveis]

        # ----------------------------
        # 2) COLUNAS DE FILTRO/ANÁLISE
        # ----------------------------
        df["Pendencia"] = "NÃO"
        df["Motivo"] = ""

        # Regra 1: Exame alterado
        cond_alterado = df["Status"].astype(str).str.contains("ALTERADO", na=False)
        df.loc[cond_alterado, "Pendencia"] = "SIM"
        df.loc[cond_alterado, "Motivo"] = "Exame alterado"

        # Regra 2: Sem referência
        cond_sem_ref = df["Referencia"].isna() | (df["Referencia"].astype(str).str.strip() == "")
        df.loc[cond_sem_ref, "Pendencia"] = "SIM"
        df.loc[cond_sem_ref & (df["Motivo"] == ""), "Motivo"] = "Sem referência"
        df.loc[cond_sem_ref & (df["Motivo"] != ""), "Motivo"] += " | Sem referência"

        # Regra 3: Sem valor
        cond_sem_valor = df["Valor"].isna() | (df["Valor"].astype(str).str.strip() == "")
        df.loc[cond_sem_valor, "Pendencia"] = "SIM"
        df.loc[cond_sem_valor & (df["Motivo"] == ""), "Motivo"] = "Sem valor"
        df.loc[cond_sem_valor & (df["Motivo"] != ""), "Motivo"] += " | Sem valor"

        # Regra 4: Paciente não identificado
        if "Paciente" in df.columns:
            cond_paciente_ruim = df["Paciente"].astype(str).str.contains("NOME NÃO IDENTIFICADO", na=False)
            df.loc[cond_paciente_ruim, "Pendencia"] = "SIM"
            df.loc[cond_paciente_ruim & (df["Motivo"] == ""), "Motivo"] = "Paciente não identificado"
            df.loc[cond_paciente_ruim & (df["Motivo"] != ""), "Motivo"] += " | Paciente não identificado"

        # ----------------------------
        # 3) ABA SÓ DE PENDÊNCIAS
        # ----------------------------
        df_pendencias = df[df["Pendencia"] == "SIM"].copy()

        # ----------------------------
        # 4) SALVAR COM 2 ABAS + FILTRO
        # ----------------------------
        with pd.ExcelWriter(RELATORIO, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="exames")
            df_pendencias.to_excel(writer, index=False, sheet_name="pendencias")

            # Ajustes no Excel (filtro + congelar linha)
            for sheet_name in ["exames", "pendencias"]:
                ws = writer.book[sheet_name]

                # Congelar primeira linha
                ws.freeze_panes = "A2"

                # Aplicar filtro automático no cabeçalho
                max_col = ws.max_column
                max_row = ws.max_row
                ws.auto_filter.ref = ws.dimensions

                # Ajustar largura das colunas
                for col_idx in range(1, max_col + 1):
                    col_letter = ws.cell(row=1, column=col_idx).column_letter
                    ws.column_dimensions[col_letter].width = 18

        # ----------------------------
        # 5) ESTATÍSTICAS
        # ----------------------------
        total_exames = len(df)
        alterados = len(df[df['Status'].astype(str).str.contains('ALTERADO', na=False)])
        pendencias = len(df_pendencias)
        pacientes_unicos = df['Paciente'].nunique() if 'Paciente' in df.columns else 0

        print("=" * 60)
        print(f"✅ Relatório: {RELATORIO}")
        print(f"👥 Pacientes: {pacientes_unicos}")
        print(f"📊 Exames: {total_exames}")
        print(f"⚠️  Pendências: {pendencias}")
        if total_exames > 0:
            print(f"🔴 Alterados: {alterados} ({alterados/total_exames*100:.1f}%)")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Erro ao gerar relatório: {e}")

# ---------------- EXECUÇÃO ----------------

if __name__ == "__main__":
    print("=" * 60)
    print("🔬 EXTRATOR DE EXAMES - PREFEITURA DE SUZANO")
    print("   Layout Customizado (sem Sexo e Origem)")
    print("=" * 60)
    print()

    resultados = processar_exames()
    gerar_relatorio(resultados)

