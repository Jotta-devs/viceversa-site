#!/usr/bin/env python3
"""
VICEVERSA — imagem do mapa para as páginas de cada local
=========================================================
O mapa do site é um vetor (mapa/leonida.svg) que o navegador pinta com as
cores do estilo Noite. Este script tira uma "foto" desse vetor, já pintado,
em alta resolução:

    mapa/leonida-noite.webp

O montar.py recorta essa imagem em volta de cada local para a página
/map/<local>/ e para a imagem de compartilhamento do local.

Só precisa rodar de novo quando o mapa mudar (depois do recriar_mapa.py)
ou quando as cores do estilo Noite mudarem em partes/cabeca.html:

    pip install playwright pillow
    python -m playwright install chromium
    python mapa/gerar_previa.py
    python montar.py
"""

import io
import re
import sys
from pathlib import Path

PASTA = Path(__file__).parent
RAIZ = PASTA.parent
SVG = PASTA / "leonida.svg"
SAIDA = PASTA / "leonida-noite.webp"
ESCALA = 3          # 3 px por unidade do mapa: nítido mesmo recortando de perto


def css_noite():
    """As regras do estilo Noite, copiadas de partes/cabeca.html."""
    css = (RAIZ / "partes" / "cabeca.html").read_text(encoding="utf-8")
    regras = re.findall(r"^\s*\.atlas--noite [^{]+\{[^}]*\}", css, re.M)
    if not regras:
        sys.exit("Não achei as cores do estilo Noite em partes/cabeca.html.")
    return "\n".join(regras)


def main():
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
    except ImportError:
        sys.exit("Faltam bibliotecas. Rode:\n  pip install playwright pillow\n"
                 "  python -m playwright install chromium")

    svg = SVG.read_text(encoding="utf-8")
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    largura, altura = float(m.group(1)), float(m.group(2))
    pagina = f"""<!doctype html><html><head><style>
      html,body{{margin:0;background:#07112A}}
      .atlas{{--traco:1}}
      .atlas-vetor svg{{display:block;width:{largura}px;height:{altura}px}}
      .atlas-vetor .grade{{display:none}}
      {css_noite()}
    </style></head><body><div class="atlas atlas--noite"><div class="atlas-vetor">{svg}</div></div></body></html>"""

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        aba = navegador.new_page(viewport={"width": int(largura), "height": int(altura)},
                                 device_scale_factor=ESCALA)
        aba.set_content(pagina, wait_until="load")
        png = aba.screenshot(full_page=False)
        navegador.close()

    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.save(SAIDA, "WEBP", quality=82, method=6)
    print(f"✓ {SAIDA.relative_to(RAIZ)} ({img.width}×{img.height}, {SAIDA.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
