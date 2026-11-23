#!/usr/bin/env python3
"""
VICEVERSA — pôster oficial de Leonida para o site
=================================================
Prepara as imagens do pôster oficial "Visit Leonida" da Rockstar (o mesmo
arquivo de mapa/base/ que o recriar_oficial.py usa) para o site:

  mapa/poster/mapa-2048.webp    só a área do mapa (a moldura), alinhada com o
                                redesenho: é a camada "Pôster oficial" do mapa
  mapa/poster/mapa-grande.webp  a mesma, na resolução do pôster (até 4096 px),
                                para telas grandes
  mapa/poster/inteiro-1600.webp o pôster inteiro, para a seção abaixo do mapa
  mapa/poster/poster.json       tamanhos (o montar.py lê)

A arte é da Rockstar Games: o site mostra com crédito e link para o download
oficial (rockstargames.com/VI/media).

    python mapa/poster_site.py
    python montar.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from recriar_oficial import carregar, moldura  # noqa: E402

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta a Pillow. Rode:  pip install pillow")

PASTA = Path(__file__).parent / "poster"


def salvar(img, nome, largura, qualidade):
    if img.width > largura:
        img = img.resize((largura, round(img.height * largura / img.width)), Image.LANCZOS)
    caminho = PASTA / nome
    img.save(caminho, "WEBP", quality=qualidade, method=6)
    print(f"  ✓ mapa/poster/{nome} ({img.width}×{img.height}, {caminho.stat().st_size // 1024} KB)")
    return {"src": nome, "w": img.width, "h": img.height}


def main():
    rgb, origem = carregar()
    x0, y0, x1, y1 = moldura(rgb)
    PASTA.mkdir(exist_ok=True)
    for velho in PASTA.glob("*.webp"):
        velho.unlink()
    inteiro = Image.fromarray(rgb)
    recorte = inteiro.crop((x0, y0, x1, y1))
    camadas = [salvar(recorte, "mapa-2048.webp", 2048, 80)]
    if recorte.width >= 2300:                      # telas grandes: o máximo que o pôster tem (até 4096 px)
        camadas.append(salvar(recorte, "mapa-grande.webp", min(4096, recorte.width), 78))
    info = {
        "origem": origem,
        "imagem": [inteiro.width, inteiro.height],
        "recorte": [x0, y0, x1, y1],
        "mapa": camadas,
        "inteiro": salvar(inteiro, "inteiro-1600.webp", 1600, 82),
        "credito": "Rockstar Games",
        "download": "https://www.rockstargames.com/VI/media/artwork-wallpapers",
    }
    (PASTA / "poster.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print("  ✓ mapa/poster/poster.json")


if __name__ == "__main__":
    main()
