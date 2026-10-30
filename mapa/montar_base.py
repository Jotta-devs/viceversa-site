#!/usr/bin/env python3
"""
VICEVERSA — mapa de Leonida a partir da arte-base
=================================================

O mapa do site usa a ilustração de Leonida feita pelo VICEVERSA. A imagem
entra no mapa SEM nenhuma alteração: o arquivo original (WebP) é embutido,
byte a byte, dentro de mapa/leonida.svg.
Assim cada detalhe da arte (costas, ruas, prédios, pistas, nuvens) aparece
exatamente como foi desenhado.

O que o script grava
--------------------
- mapa/leonida.svg   a arte-base + a grade de referência do VICEVERSA (A1…H11)
- mapa/leonida.json  tamanho do mapa, grade, zoom máximo e crédito

Os nomes, ícones e textos dos locais NÃO ficam na imagem: o site desenha tudo
por cima, nos três idiomas (mapa/pontos.json).

Uso:
    python mapa/montar_base.py                       # usa a imagem mais recente de mapa/base/
    python mapa/montar_base.py caminho/arte.webp     # ou uma imagem específica
    python mapa/montar_base.py gta-6-map-leonida.svg # ou o SVG exportado (a imagem é extraída)
    python mapa/gerar_previa.py
    python montar.py

Se um dia houver uma versão maior da arte (mais pixels), basta colocá-la em
mapa/base/ e rodar de novo: as posições dos pontos são frações do mapa (0 a 1)
e continuam certas, desde que o enquadramento da arte seja o mesmo.
"""

import base64
import json
import math
import re
import struct
import sys
from pathlib import Path

PASTA = Path(__file__).parent
BASE = PASTA / "base"
SAIDA = PASTA / "leonida.svg"
INFO = PASTA / "leonida.json"

COLUNAS = 8                 # grade de referência: colunas A…H
ZOOM_EXTRA = 1.75           # quanto se pode aproximar além do tamanho real da arte (em níveis de zoom)
CREDITO = {"texto": "VICEVERSA"}
TIPOS = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def tamanho_imagem(dados, tipo):
    """Largura e altura lidas do cabeçalho (sem precisar de bibliotecas)."""
    if tipo == "image/png":
        return struct.unpack(">II", dados[16:24])
    if tipo == "image/webp":
        bloco = dados[12:16]
        if bloco == b"VP8 ":
            l, a = struct.unpack("<HH", dados[26:30])
            return l & 0x3FFF, a & 0x3FFF
        if bloco == b"VP8L":
            b = dados[21:25]
            l = 1 + (((b[1] & 0x3F) << 8) | b[0])
            a = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return l, a
        if bloco == b"VP8X":
            return 1 + int.from_bytes(dados[24:27], "little"), 1 + int.from_bytes(dados[27:30], "little")
    if tipo == "image/jpeg":
        i = 2
        while i < len(dados):
            marca, comp = dados[i + 1], struct.unpack(">H", dados[i + 2:i + 4])[0]
            if 0xC0 <= marca <= 0xCF and marca not in (0xC4, 0xC8, 0xCC):
                a, l = struct.unpack(">HH", dados[i + 5:i + 9])
                return l, a
            i += 2 + comp
    sys.exit("Não consegui ler o tamanho da imagem.")


def carregar(caminho=None):
    if caminho is None:
        candidatos = sorted([p for p in BASE.glob("*") if p.suffix.lower() in TIPOS or p.suffix.lower() == ".svg"],
                            key=lambda p: p.stat().st_mtime)
        if not candidatos:
            sys.exit(f"Nenhuma imagem em {BASE}/ — coloque lá a arte do mapa (webp, png, jpg ou o svg exportado).")
        caminho = candidatos[-1]
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".svg":
        texto = caminho.read_text(encoding="utf-8")
        m = re.search(r'data:(image/[a-z]+);base64,([A-Za-z0-9+/=]+)', texto)
        if not m:
            sys.exit(f"{caminho.name} não tem imagem embutida.")
        return base64.b64decode(m.group(2)), m.group(1), caminho.name
    tipo = TIPOS.get(caminho.suffix.lower())
    if not tipo:
        sys.exit(f"Formato não suportado: {caminho.suffix}")
    return caminho.read_bytes(), tipo, caminho.name


def main():
    dados, tipo, origem = carregar(sys.argv[1] if len(sys.argv) > 1 else None)
    w, h = tamanho_imagem(dados, tipo)
    print(f"Arte-base: {origem} · {w}×{h} px · {len(dados) // 1024} KB")

    # grade de referência do VICEVERSA (A1, B2…), estilo guia de ruas
    celula = w / COLUNAS
    linhas = math.ceil(h / celula - 1e-6)
    g = ['<g class="grade">']
    d = "".join(f"M{i * celula:.2f},0V{h}" for i in range(1, COLUNAS))
    d += "".join(f"M0,{j * celula:.2f}H{w}" for j in range(1, linhas))
    g.append(f'<path fill="none" vector-effect="non-scaling-stroke" d="{d}"/>')
    for i in range(COLUNAS):
        for j in range(linhas):
            g.append(f'<text x="{i * celula + 5:.1f}" y="{j * celula + 18:.1f}">{chr(65 + i)}{j + 1}</text>')
    g.append("</g>")

    b64 = base64.b64encode(dados).decode("ascii")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {w} {h}" data-origem="{origem}">\n'
           f'<image class="c-arte" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="none" '
           f'href="data:{tipo};base64,{b64}"/>\n'
           + "".join(g) + "\n</svg>\n")
    SAIDA.write_text(svg, encoding="utf-8", newline="\n")
    INFO.write_text(json.dumps({"largura": w, "altura": h, "origem": origem, "tipo": "arte",
                                "zoom_extra": ZOOM_EXTRA, "credito": CREDITO,
                                "grade": {"colunas": COLUNAS, "linhas": linhas, "celula": round(celula, 3)}},
                               indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"✓ mapa/leonida.svg ({len(svg) // 1024} KB) e mapa/leonida.json — grade {COLUNAS}×{linhas}")
    print("  Agora rode: python mapa/gerar_previa.py  e  python montar.py")


if __name__ == "__main__":
    main()
