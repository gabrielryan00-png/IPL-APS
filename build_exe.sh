#!/usr/bin/env bash
# build_exe.sh — Gera o executável IPL-APS com PyInstaller
# Uso: bash build_exe.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== IPL-APS Build ==="
echo "Diretório: $SCRIPT_DIR"

# ── Ativa venv ─────────────────────────────────────────────────────────────
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ venv ativado"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✓ .venv ativado"
else
    echo "⚠ Nenhum venv encontrado — usando Python do sistema"
fi

# ── Instala PyInstaller se necessário ──────────────────────────────────────
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Instalando PyInstaller..."
    pip install pyinstaller --quiet
fi

# ── Limpa builds anteriores ────────────────────────────────────────────────
rm -rf build dist __pycache__
echo "✓ Build anterior removido"

# ── Gera o executável ──────────────────────────────────────────────────────
echo "Gerando executável (pode levar 2–5 minutos)..."
pyinstaller ipl_aps.spec --noconfirm

# ── Cria pasta de dados junto ao executável ───────────────────────────────
DIST_DIR="dist/IPL-APS"
mkdir -p "$DIST_DIR/data"
echo "✓ Pasta data/ criada"

# ── Gera .env.example se não existir ──────────────────────────────────────
if [ ! -f "$DIST_DIR/.env.example" ]; then
    cp .env.example "$DIST_DIR/" 2>/dev/null || true
fi

# ── Copia valores_referencia.sql ──────────────────────────────────────────
[ -f "valores_referencia.sql" ] && cp valores_referencia.sql "$DIST_DIR/"

# ── README de distribuição ─────────────────────────────────────────────────
cat > "$DIST_DIR/LEIA-ME.txt" << 'EOF'
IPL-APS — Sistema Municipal de Prioridade Laboratorial
=======================================================

REQUISITOS DO SISTEMA
---------------------
- Linux 64-bit (Ubuntu 20.04+ recomendado) OU Windows 10+
- Tesseract OCR (opcional, para PDFs sem texto embutido):
    Linux:   sudo apt install tesseract-ocr tesseract-ocr-por
    Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Poppler (opcional, para PDFs via pdfplumber):
    Linux:   sudo apt install poppler-utils
    Windows: https://github.com/oschwartz10612/poppler-windows

PRIMEIRO USO
------------
1. Execute IPL-APS  (ou IPL-APS.exe no Windows)
2. Preencha o assistente de configuração:
   - E-mail Gmail + Senha de App
   - Senha do administrador
3. Acesse o dashboard em: http://localhost:8080
   Login: ryan.nascimento  (ou o usuário configurado)

ESTRUTURA DE DADOS
------------------
Os dados ficam na mesma pasta do executável:
  auth.db         — usuários e USFs
  exames.db       — laudos processados (por USF ativa)
  exames/         — PDFs baixados
  .env            — configuração (NÃO compartilhar)

SUPORTE
-------
Secretaria Municipal de Saúde · Suzano/SP
Repositório: https://github.com/gabrielryan00-png/IPL-APS
EOF
echo "✓ LEIA-ME.txt criado"

# ── Resultado ──────────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo " Build concluído!"
echo " Executável: $(pwd)/$DIST_DIR/IPL-APS"
echo " Tamanho:"
du -sh "$DIST_DIR" 2>/dev/null || true
echo "=============================================="
echo ""
echo "Para distribuir: compacte a pasta dist/IPL-APS/"
echo "  tar -czf IPL-APS-linux.tar.gz -C dist IPL-APS"
