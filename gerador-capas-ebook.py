"""
Traduz o texto da capa do ebook mantendo a arte original intacta.

A arte (sol, cifrão, palmeiras, skyline, grade) vem do arquivo original em
português. Apenas a faixa de texto do topo é reconstruída e reescrita no
idioma alvo, nas mesmas posições medidas na capa original:

    edição   .... y 82-91,  centro x 312
    título   .... 3 linhas, topos em y 125 / 164 / 202, centro x 314
    subtítulo ... 2 linhas, topos em y 260 / 282, centro x 314
"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import random

ORIGINAL = "/mnt/user-data/uploads/ebook-capa.png"
F = "/usr/share/fonts/truetype/dejavu/"

Y_LIMPA_TOPO, Y_LIMPA_BASE = 60, 308      # linhas sem texto, usadas de referência
X_INI, X_FIM = 8, 612


def limpar_bordas(a):
    """A extração do PDF deixou uma borda branca no topo e à esquerda."""
    for x in range(7):
        a[:, x] = a[:, 7]
    for y in range(7):
        a[y, :] = a[7, :]
    return a


def reconstruir_fundo(a):
    """Interpola verticalmente entre duas linhas limpas, coluna a coluna."""
    topo = a[Y_LIMPA_TOPO].astype(float)
    base = a[Y_LIMPA_BASE].astype(float)
    alt = Y_LIMPA_BASE - Y_LIMPA_TOPO
    for y in range(Y_LIMPA_TOPO + 1, Y_LIMPA_BASE):
        t = (y - Y_LIMPA_TOPO) / alt
        linha = topo * (1 - t) + base * t
        a[y, X_INI:X_FIM] = linha[X_INI:X_FIM].round().astype(int)
    return a


def repor_estrelas(d, semente=11):
    rnd = random.Random(semente)
    for _ in range(26):
        x = rnd.randint(X_INI + 6, X_FIM - 6)
        y = rnd.randint(Y_LIMPA_TOPO + 6, Y_LIMPA_BASE - 8)
        b = rnd.randint(120, 215)
        d.point((x, y), fill=(b, b, b))
        if rnd.random() < .3:
            d.point((x + 1, y), fill=(b - 40, b - 40, b - 40))


def centrar(d, txt, fonte, cx, y, cor, espaco=0):
    if espaco:
        larg = sum(d.textlength(c, font=fonte) + espaco for c in txt) - espaco
        x = cx - larg / 2
        for c in txt:
            d.text((x, y), c, font=fonte, fill=cor)
            x += d.textlength(c, font=fonte) + espaco
    else:
        d.text((cx - d.textlength(txt, font=fonte) / 2, y), txt, font=fonte, fill=cor)


def quebrar(d, texto, fonte, largura):
    linhas, atual = [], ""
    for p in texto.split():
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def ajustar_fonte(d, linhas, caminho, largura, inicial=35, minimo=24):
    """Diminui a fonte até a linha mais larga caber."""
    tam = inicial
    while tam > minimo:
        f = ImageFont.truetype(caminho, tam)
        if max(d.textlength(l, font=f) for l in linhas) <= largura:
            return f
        tam -= 1
    return ImageFont.truetype(caminho, minimo)


def gerar(edicao, linhas_titulo, cifras, subtitulo, saida):
    im = Image.open(ORIGINAL).convert("RGB")
    a = np.array(im).astype(int)
    a = limpar_bordas(a)
    a = reconstruir_fundo(a)
    im = Image.fromarray(a.astype("uint8"))
    d = ImageDraw.Draw(im)
    repor_estrelas(d)

    CX = 314
    BRANCO = (255, 255, 255)
    CIANO = (93, 213, 226)
    LAVANDA = (214, 200, 232)

    # edição
    f_ed = ImageFont.truetype(F + "DejaVuSansMono-Bold.ttf", 13)
    centrar(d, edicao, f_ed, CX, 79, CIANO, espaco=6)

    # título: até 3 linhas; a última leva o $$$ em ciano
    f_tit = ajustar_fonte(d, [l + (" " + cifras if i == len(linhas_titulo) - 1 else "")
                              for i, l in enumerate(linhas_titulo)],
                          F + "DejaVuSans-Bold.ttf", 372)
    topos = [125, 164, 203][:len(linhas_titulo)]
    for i, (ln, y) in enumerate(zip(linhas_titulo, topos)):
        if i == len(linhas_titulo) - 1 and cifras:
            lw = d.textlength(ln + " ", font=f_tit) + d.textlength(cifras, font=f_tit)
            x = CX - lw / 2
            d.text((x, y), ln, font=f_tit, fill=BRANCO)
            d.text((x + d.textlength(ln + " ", font=f_tit), y), cifras, font=f_tit, fill=CIANO)
        else:
            centrar(d, ln, f_tit, CX, y, BRANCO)

    # subtítulo
    linhas_sub = subtitulo if isinstance(subtitulo, list) else quebrar(
        d, subtitulo, ImageFont.truetype(F + "DejaVuSansCondensed.ttf", 15), 330)
    f_sub = ajustar_fonte(d, linhas_sub, F + "DejaVuSansCondensed.ttf", 336, 15, 11)
    for i, ln in enumerate(linhas_sub[:2]):
        centrar(d, ln, f_sub, CX, 259 + i * 22, LAVANDA)

    im.save(saida, "PNG", optimize=True)
    print("gerado:", saida)


if __name__ == "__main__":
    base = "/home/claude/i18n/"
    gerar("EDIÇÃO 2026",
          ["COMO GTA VI VAI", "MUDAR A SUA", "VIDA"], "$$$",
          ["O manual para transformar o maior lançamento da década",
           "em uma carreira de criador de conteúdo"],
          base + "ebook-capa-pt.png")
    gerar("2026 EDITION",
          ["HOW GTA VI WILL", "CHANGE YOUR", "LIFE"], "$$$",
          ["The playbook for turning the biggest launch of the decade",
           "into a content creator career"],
          base + "ebook-capa-en.png")
    gerar("EDICIÓN 2026",
          ["CÓMO GTA VI VA A", "CAMBIAR TU", "VIDA"], "$$$",
          ["El manual para convertir el mayor lanzamiento de la década",
           "en una carrera de creador de contenido"],
          base + "ebook-capa-es.png")
