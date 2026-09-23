#!/usr/bin/env python3
"""
VICEVERSA — fatia o mapa em "tiles" para o visualizador com zoom
=================================================================

O mapa de Leonida exibido em /map/ é o "YANIS GTA VI Community Map", da
Mapping Community (map.stateofleonida.net), usado com autorização do autor.
A imagem NÃO é alterada: este script só a divide em quadradinhos de 256 px
em vários níveis de zoom, para o navegador carregar apenas o pedaço que está
na tela (é o que deixa o zoom rápido no celular).

Como usar
---------
1. Coloque a imagem do mapa (PNG ou JPG, a maior resolução que tiver) em
   mapa/base/. Se houver mais de uma, vale a mais recente.
2. Rode:

       pip install pillow          # só na primeira vez
       python mapa/gerar_tiles.py

3. Rode python montar.py e publique.

Saída: mapa/tiles/{z}/{x}/{y}.webp e mapa/tiles/info.json (tamanho da
imagem e zoom máximo, lido pelo montar.py).

Quando chegar uma versão nova do mapa (V17, V18...), é só trocar o arquivo em
mapa/base/ e repetir os passos. Se o enquadramento da imagem mudar, confira as
posições dos pontos em mapa/pontos.json abrindo /map/?editar=1 no site.
"""

import json
import math
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta a biblioteca Pillow. Rode:  pip install pillow")

Image.MAX_IMAGE_PIXELS = None          # mapas grandes passam do limite padrão

PASTA = Path(__file__).parent
BASE = PASTA / "base"
SAIDA = PASTA / "tiles"
TILE = 256
QUALIDADE = 82


def main():
    imagens = sorted(
        [p for p in BASE.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
        key=lambda p: p.stat().st_mtime)
    if not imagens:
        sys.exit(f"Nenhuma imagem em {BASE}/ — coloque o PNG do mapa lá.")
    origem = imagens[-1]
    print(f"Imagem: {origem.name}")

    img = Image.open(origem).convert("RGBA")
    w, h = img.size
    zmax = max(0, math.ceil(math.log2(max(w, h) / TILE)))
    print(f"Tamanho: {w}×{h} px · zoom 0 a {zmax}")

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    total = 0
    for z in range(zmax, -1, -1):
        escala = 2 ** (z - zmax)
        lw, lh = max(1, round(w * escala)), max(1, round(h * escala))
        nivel = img if escala == 1 else img.resize((lw, lh), Image.LANCZOS)
        colunas, linhas = math.ceil(lw / TILE), math.ceil(lh / TILE)
        for x in range(colunas):
            pasta = SAIDA / str(z) / str(x)
            pasta.mkdir(parents=True, exist_ok=True)
            for y in range(linhas):
                caixa = (x * TILE, y * TILE, min((x + 1) * TILE, lw), min((y + 1) * TILE, lh))
                pedaco = nivel.crop(caixa)
                if pedaco.size != (TILE, TILE):
                    # borda da imagem: completa com transparente
                    cheio = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
                    cheio.paste(pedaco, (0, 0))
                    pedaco = cheio
                pedaco.save(pasta / f"{y}.webp", "WEBP", quality=QUALIDADE, method=5)
                total += 1
        print(f"  zoom {z}: {colunas}×{linhas} tiles")

    # cor do fundo (o "mar" no canto da imagem): pinta a área além das bordas
    r, g, b, _ = img.getpixel((w - 2, 2))
    (SAIDA / "info.json").write_text(json.dumps({
        "largura": w, "altura": h, "zoom_max": zmax, "tile": TILE,
        "origem": origem.name, "fundo": f"#{r:02X}{g:02X}{b:02X}",
    }, indent=2), encoding="utf-8")
    tamanho = sum(p.stat().st_size for p in SAIDA.rglob("*.webp")) / 1024 / 1024
    print(f"\n{total} tiles ({tamanho:.1f} MB) em mapa/tiles/. Agora rode: python montar.py")


if __name__ == "__main__":
    main()
