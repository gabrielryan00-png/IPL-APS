#!/usr/bin/env python3
"""
Anonimiza a imagem 'pacientes_criticos.png' cobrindo os nomes dos pacientes
com blocos sólidos e substituindo por labels genéricos (PACIENTE 1, PACIENTE 2...).

Uso:
    python anonimizar_print_pacientes.py

Entrada esperada:  docs/screenshots/pacientes_criticos_original.png
Saída gerada:      docs/screenshots/pacientes_criticos.png
"""

from PIL import Image, ImageDraw, ImageFont
import sys
import os

INPUT  = os.path.join(os.path.dirname(__file__), "screenshots", "pacientes_criticos_original.png")
OUTPUT = os.path.join(os.path.dirname(__file__), "screenshots", "pacientes_criticos.png")

# Coordenadas aproximadas (x0, y0, x1, y1) de cada nome na imagem original.
# Ajuste caso a resolução do seu print seja diferente.
# Captura feita em ~1008×~272 px (área da lista de pacientes).
# Cada linha tem ~40px de altura; nomes ocupam a coluna esquerda (~0 a ~380px).
NAME_BOXES = [
    (14,  14,  380,  38),   # linha 1
    (14,  58,  380,  82),   # linha 2
    (14, 102,  380, 126),   # linha 3
    (14, 146,  380, 170),   # linha 4
    (14, 190,  380, 214),   # linha 5
    (14, 234,  380, 258),   # linha 6
    (14, 278,  380, 302),   # linha 7 (se existir)
    (14, 322,  380, 346),   # linha 8 (se existir)
]

BG_COLOR   = (20, 20, 30)    # cor de fundo igual ao painel escuro
TEXT_COLOR = (90, 90, 110)   # cinza discreto para o label


def anonimizar(input_path: str, output_path: str) -> None:
    if not os.path.exists(input_path):
        print(f"[ERRO] Arquivo não encontrado: {input_path}")
        print("Salve o print como 'pacientes_criticos_original.png' na pasta docs/screenshots/")
        sys.exit(1)

    img  = Image.open(input_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    w, h = img.size
    for i, (x0, y0, x1, y1) in enumerate(NAME_BOXES, start=1):
        if y1 > h:
            break
        draw.rectangle([x0, y0, x1, y1], fill=BG_COLOR)
        draw.text((x0 + 4, y0 + 2), f"PACIENTE {i}", fill=TEXT_COLOR, font=font)

    img.save(output_path)
    print(f"[OK] Imagem anonimizada salva em: {output_path}")


if __name__ == "__main__":
    anonimizar(INPUT, OUTPUT)
