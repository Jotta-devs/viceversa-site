#!/usr/bin/env python3
"""
VICEVERSA — gerador de cards para o Instagram (1080 × 1350)
===========================================================
Cria os posts do feed na identidade do VICEVERSA (noite roxa, magenta,
laranja e turquesa, sol synthwave, Bebas Neue + IBM Plex Mono).

Três modelos:

    noticia    foto no topo + título grande + selo (rumor, vazamento...)
    contagem   "faltam N dias para GTA 6", com a conta feita sozinha
    siga       card de chamada "segue o VICEVERSA", com o sol e a grade

Jeitos de usar
--------------
1) Janela (mais fácil): dê dois cliques no arquivo ou rode sem nada

       python cards_instagram.py

   Escolha a imagem, escreva o texto, veja a prévia ao vivo e clique em
   "Salvar card".

2) Linha de comando:

       python cards_instagram.py noticia --imagem foto.jpg \\
           --titulo "Vem coisa nova amanhã?! *Vários criadores* receberam pacotes da Rockstar" \\
           --selo rumor

       python cards_instagram.py contagem --imagem logo.jpg
       python cards_instagram.py siga --imagem personagens.jpg

   Rode  python cards_instagram.py noticia -h  para ver todas as opções.

Dicas de texto
--------------
* Palavras entre *asteriscos* ganham o degradê magenta → laranja.
* Uma barra vertical  |  (ou Enter, na janela) força a quebra de linha.
* O título diminui sozinho até caber; "GTA 6" nunca é separado.

Os cards vão para a pasta cards-instagram/ (ou para onde --saida mandar).
Precisa do Pillow:  pip install pillow
As fontes ficam em fontes/ (licença SIL OFL).
"""

import argparse
import datetime as dt
import random
import re
import sys
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:
    sys.exit("Este programa precisa do Pillow. Instale com:  pip install pillow")


# ── configuração: mude aqui os padrões da marca ─────────────────────
RAIZ = Path(__file__).resolve().parent
FONTES = RAIZ / "fontes"
PASTA_SAIDA = RAIZ / "cards-instagram"

LARGURA, ALTURA = 1080, 1350          # formato retrato do feed do Instagram
MARGEM = 72

HANDLE = "@vvviceversaa"
RODAPE = "LEIA MAIS NO VICEVERSA"
LANCAMENTO = dt.date(2026, 11, 19)    # data de lançamento usada na contagem
CHAMADA = "QUER FICAR POR DENTRO|DE TUDO SOBRE GTA 6?!"
SEGUE = "ENTÃO SEGUE O"
SLOGAN = "NOTÍCIAS, MAPA E CURIOSIDADES|DE GTA VI"

# cores do site
NOITE = (18, 7, 32)
CREME = (255, 243, 228)
MAGENTA = (255, 61, 138)
LARANJA = (255, 138, 61)
AMARELO = (255, 214, 102)
TURQUESA = (47, 230, 200)
LILAS = (182, 156, 255)
CINZA = (214, 204, 196)
DESTAQUE = [MAGENTA, LARANJA]         # degradê das palavras entre *asteriscos*

SELOS = {
    "confirmado": ("CONFIRMADO", TURQUESA),
    "oficial": ("OFICIAL", TURQUESA),
    "rumor": ("RUMOR", LARANJA),
    "vazamento": ("VAZAMENTO", MAGENTA),
    "urgente": ("URGENTE", MAGENTA),
    "off": ("FORA DO GTA 6", LILAS),
}

BEBAS = "BebasNeue-Regular.ttf"
MONO = "IBMPlexMono-Medium.ttf"
NBSP = " "
QUEBRA = None                          # marcador de quebra de linha forçada
MESES = "JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ".split()


# ── utilidades de desenho ───────────────────────────────────────────
_fontes = {}


def fonte(nome, tamanho):
    chave = (nome, tamanho)
    if chave not in _fontes:
        caminho = FONTES / nome
        if not caminho.exists():
            sys.exit(f"Fonte não encontrada: {caminho}\n"
                     "Deixe este arquivo na raiz do repositório, ao lado da pasta fontes/.")
        _fontes[chave] = ImageFont.truetype(str(caminho), tamanho)
    return _fontes[chave]


def altura_maiuscula(fnt):
    """Altura das maiúsculas (sem acento) acima da linha de base."""
    return -fnt.getbbox("H", anchor="ls")[1]


def degrade(largura, altura, cores, vertical=False):
    """Degradê com várias paradas, horizontal ou vertical."""
    largura, altura = max(1, round(largura)), max(1, round(altura))
    n = altura if vertical else largura
    faixa = Image.new("RGB", (1, n) if vertical else (n, 1))
    px = faixa.load()
    partes = len(cores) - 1
    for i in range(n):
        t = i / max(1, n - 1) * partes
        s = min(int(t), partes - 1)
        f = t - s
        a, b = cores[s], cores[s + 1]
        px[(0, i) if vertical else (i, 0)] = tuple(round(x + (y - x) * f) for x, y in zip(a, b))
    return faixa.resize((largura, altura))


def brilho(img, mascara, cor, raio, forca=1.0):
    """Brilho neon (modo 'screen') em volta do que estiver na máscara."""
    m = mascara.filter(ImageFilter.GaussianBlur(raio))
    if forca != 1.0:
        m = m.point(lambda v: min(255, round(v * forca)))
    camada = Image.composite(Image.new("RGB", img.size, cor), Image.new("RGB", img.size), m)
    img.paste(ImageChops.screen(img, camada))


def sombra(img, mascara, raio=12, forca=0.75, deslocamento=6):
    m = mascara.filter(ImageFilter.GaussianBlur(raio)).point(lambda v: round(v * forca))
    img.paste(Image.new("RGB", img.size, (6, 2, 12)), (0, deslocamento), m)


def pintar(img, mascara, cores, caixa=None, vertical=False):
    """Pinta a máscara com uma cor sólida ou com um degradê dentro de `caixa`."""
    if isinstance(cores, tuple):
        img.paste(Image.new("RGB", img.size, cores), (0, 0), mascara)
        return
    x0, y0, x1, y1 = (round(v) for v in caixa)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 <= x0 or y1 <= y0:
        return
    img.paste(degrade(x1 - x0, y1 - y0, cores, vertical), (x0, y0), mascara.crop((x0, y0, x1, y1)))


def largura_espacada(texto, fnt, espaco):
    return sum(fnt.getlength(c) for c in texto) + espaco * max(0, len(texto) - 1)


def texto_espacado(draw, x, y, texto, fnt, cor, espaco):
    """Texto com espaçamento entre letras (o Pillow não tem 'tracking')."""
    for c in texto:
        draw.text((x, y), c, font=fnt, fill=cor, anchor="ls")
        x += fnt.getlength(c) + espaco
    return x


def _circulo_suave(tamanho, caixa, preenchimento=255, escala=4):
    """Máscara com círculo antisserrilhado (desenha 4× maior e reduz)."""
    grande = Image.new("L", (tamanho[0] * escala, tamanho[1] * escala))
    ImageDraw.Draw(grande).ellipse([v * escala for v in caixa], fill=preenchimento)
    return grande.resize(tamanho, Image.LANCZOS)


# ── texto rico: *destaque*, quebra forçada e "GTA 6" inseparável ────
def palavras(texto):
    """Lista de palavras; cada palavra é uma lista de pedaços (texto, destaque)."""
    texto = texto.replace("\r", "").replace("|", "\n").upper()
    texto = re.sub(r"\bGTA\s+(6|VI)\b", f"GTA{NBSP}\\1", texto)
    saida, atual, buf, dest = [], [], "", False

    def fecha_pedaco():
        nonlocal buf
        if buf:
            atual.append((buf, dest))
            buf = ""

    def fecha_palavra():
        nonlocal atual
        fecha_pedaco()
        if atual:
            saida.append(atual)
            atual = []

    for c in texto:
        if c == "*":
            fecha_pedaco()
            dest = not dest
        elif c == "\n":
            fecha_palavra()
            if saida and saida[-1] is not QUEBRA:
                saida.append(QUEBRA)
        elif c.isspace() and c != NBSP:
            fecha_palavra()
        else:
            buf += c
    fecha_palavra()
    while saida and saida[-1] is QUEBRA:
        saida.pop()
    return saida


def _larg_palavra(p, fnt):
    return sum(fnt.getlength(t) for t, _ in p)


def _larg_linha(linha, fnt):
    return sum(_larg_palavra(p, fnt) for p in linha) + fnt.getlength(" ") * max(0, len(linha) - 1)


def quebrar(lista, fnt, largura_max):
    linhas, larg = [[]], 0
    espaco = fnt.getlength(" ")
    for p in lista:
        if p is QUEBRA:
            linhas.append([])
            larg = 0
            continue
        lp = _larg_palavra(p, fnt)
        if linhas[-1] and larg + espaco + lp > largura_max:
            linhas.append([p])
            larg = lp
        else:
            larg = lp if not linhas[-1] else larg + espaco + lp
            linhas[-1].append(p)
    return [l for l in linhas if l]


def ajustar(texto, largura_max, altura_max, max_linhas, maior, menor, entrelinha=0.96):
    """Maior tamanho de Bebas em que o texto cabe na caixa."""
    lista = palavras(texto)
    for tam in range(maior, menor - 1, -2):
        fnt = fonte(BEBAS, tam)
        linhas = quebrar(lista, fnt, largura_max)
        lh = round(tam * entrelinha)
        alt = altura_maiuscula(fnt) + lh * (len(linhas) - 1)
        if (len(linhas) <= max_linhas and alt <= altura_max
                and all(_larg_linha(l, fnt) <= largura_max for l in linhas)):
            return fnt, linhas, lh
    # não coube nem no menor tamanho: corta com reticências
    fnt = fonte(BEBAS, menor)
    linhas = quebrar(lista, fnt, largura_max)[:max_linhas]
    ultima = linhas[-1]
    while len(ultima) > 1 and _larg_linha(ultima + [[("…", False)]], fnt) > largura_max:
        ultima.pop()
    ultima[-1] = ultima[-1] + [("…", ultima[-1][-1][1])]
    return fnt, linhas, round(menor * entrelinha)


def altura_bloco(fnt, linhas, lh):
    return altura_maiuscula(fnt) + lh * (len(linhas) - 1)


def altura_primeira(fnt, linhas):
    """Quanto a 1ª linha sobe acima da base, contando acentos (É, Ã...)."""
    texto = " ".join("".join(t for t, _ in p) for p in linhas[0]) if linhas else "H"
    return max(altura_maiuscula(fnt), -fnt.getbbox(texto or "H", anchor="ls")[1])


def desenhar_bloco(img, fnt, linhas, lh, x, base_primeira, largura, cor=CREME,
                   cores_dest=DESTAQUE, alinhar="esquerda", brilho_dest=None, com_sombra=True):
    """Desenha as linhas; pedaços em destaque ganham degradê por trecho contínuo."""
    normal = Image.new("L", img.size)
    dest = Image.new("L", img.size)
    dn, dd = ImageDraw.Draw(normal), ImageDraw.Draw(dest)
    espaco = fnt.getlength(" ")
    cap = altura_maiuscula(fnt)
    trechos = []                                   # (x0, x1, y_topo, y_base)
    for i, linha in enumerate(linhas):
        yb = base_primeira + i * lh
        lw = _larg_linha(linha, fnt)
        cx = x if alinhar == "esquerda" else x + (largura - lw) / 2
        aberto = None
        for j, p in enumerate(linha):
            if j:
                cx += espaco
            for t, e in p:
                w = fnt.getlength(t)
                (dd if e else dn).text((cx, yb), t.replace(NBSP, " "), font=fnt, fill=255, anchor="ls")
                if e:
                    if aberto is None:
                        aberto = [cx, cx + w]
                    else:
                        aberto[1] = cx + w
                elif aberto is not None:
                    trechos.append((*aberto, yb - cap * 1.35, yb + 4))
                    aberto = None
                cx += w
        if aberto is not None:
            trechos.append((*aberto, yb - cap * 1.35, yb + 4))
    if com_sombra:
        sombra(img, ImageChops.lighter(normal, dest))
    if brilho_dest:
        brilho(img, dest, brilho_dest, 18, 0.9)
    pintar(img, normal, cor)
    for x0, x1, y0, y1 in trechos:
        pintar(img, dest, cores_dest, (x0 - 2, y0, x1 + 2, y1))


# ── peças da marca ──────────────────────────────────────────────────
def marca(img, x, base, tamanho, alinhar="esquerda", brilhar=True):
    """Logotipo VICEVERSA: VICE em creme, VERSA em degradê. Devolve a largura."""
    f = fonte(BEBAS, tamanho)
    lv, lt = f.getlength("VICE"), f.getlength("VICEVERSA")
    if alinhar == "direita":
        x -= lt
    elif alinhar == "centro":
        x -= lt / 2
    m_vice, m_versa = Image.new("L", img.size), Image.new("L", img.size)
    ImageDraw.Draw(m_vice).text((x, base), "VICE", font=f, fill=255, anchor="ls")
    ImageDraw.Draw(m_versa).text((x + lv, base), "VERSA", font=f, fill=255, anchor="ls")
    if brilhar:
        brilho(img, m_versa, MAGENTA, max(4, tamanho // 6), 0.8)
    pintar(img, m_vice, CREME)
    cap = altura_maiuscula(f)
    pintar(img, m_versa, [MAGENTA, LARANJA], (x + lv, base - cap - 4, x + lt + 4, base + 4))
    return lt


def sol(diametro, faixas=True):
    """Sol synthwave: devolve (imagem em degradê, máscara com as faixas)."""
    grad = degrade(diametro, diametro, [AMARELO, LARANJA, MAGENTA], vertical=True)
    m = _circulo_suave((diametro, diametro), (0, 0, diametro, diametro))
    if faixas:
        d = ImageDraw.Draw(m)
        y, k = diametro * 0.5, 0
        while y < diametro:
            vao = diametro * (0.014 + 0.011 * k)
            d.rectangle((0, round(y), diametro, round(y + vao)), fill=0)
            y += vao + diametro * max(0.03, 0.075 - 0.008 * k)
            k += 1
    return grad, m


def cena_synthwave(largura, altura, horizonte, sol_cx=None, sol_raio=260, semente=11):
    """Céu da noite, estrelas, sol listrado e chão com a grade neon."""
    sol_cx = largura / 2 if sol_cx is None else sol_cx
    img = Image.new("RGB", (largura, altura), NOITE)
    img.paste(degrade(largura, horizonte, [NOITE, (36, 10, 60), (92, 20, 90), (168, 42, 112)],
                      vertical=True), (0, 0))

    # estrelas
    d = ImageDraw.Draw(img)
    rnd = random.Random(semente)
    for _ in range(110):
        x, y = rnd.randrange(largura), rnd.randrange(max(1, int(horizonte * 0.7)))
        b = rnd.randint(80, 200)
        s = rnd.choice((1, 1, 1, 2, 2, 3))
        d.ellipse((x, y, x + s, y + s), fill=(b, round(b * 0.9), b))

    # sol e seu brilho
    cy = horizonte - sol_raio * 0.3
    halo = Image.new("L", img.size)
    ImageDraw.Draw(halo).ellipse((sol_cx - sol_raio * 1.45, cy - sol_raio * 1.45,
                                  sol_cx + sol_raio * 1.45, cy + sol_raio * 1.45), fill=150)
    brilho(img, halo, (255, 70, 120), sol_raio * 0.55)
    grad, m = sol(sol_raio * 2)
    topo_sol = round(cy - sol_raio)
    corte = horizonte - topo_sol
    if corte < m.height:
        m.paste(0, (0, max(0, corte), m.width, m.height))
    img.paste(grad, (round(sol_cx - sol_raio), topo_sol), m)

    # chão e grade em perspectiva
    img.paste(degrade(largura, altura - horizonte, [(24, 8, 40), (10, 4, 20)], vertical=True),
              (0, horizonte))
    horiz, vert = Image.new("L", img.size), Image.new("L", img.size)
    dh, dv = ImageDraw.Draw(horiz), ImageDraw.Draw(vert)
    n = 16
    for k in range(1, n + 1):
        t = (k / n) ** 2.2
        y = horizonte + t * (altura - horizonte)
        dh.line((0, y, largura, y), fill=round(70 + 185 * t), width=2 if t > 0.25 else 1)
    for i in range(-16, 17):
        dv.line((sol_cx + i * 10, horizonte, sol_cx + i * largura / 6.5, altura), fill=200, width=2)
    fade = Image.new("L", img.size)
    fade.paste(degrade(largura, altura - horizonte, [(40,) * 3, (255,) * 3], vertical=True).convert("L"),
               (0, horizonte))
    vert = ImageChops.multiply(vert, fade)
    pintar(img, vert.point(lambda v: round(v * 0.55)), TURQUESA)
    pintar(img, horiz, MAGENTA)
    brilho(img, horiz, MAGENTA, 6, 0.6)

    # linha do horizonte
    linha = Image.new("L", img.size)
    ImageDraw.Draw(linha).line((0, horizonte, largura, horizonte), fill=255, width=3)
    brilho(img, linha, LARANJA, 10, 1.4)
    pintar(img, linha, (255, 226, 190))
    return img


def barra_inferior(img, altura=12):
    img.paste(degrade(img.width, altura, [TURQUESA, MAGENTA, LARANJA]), (0, img.height - altura))


def rodape(img, texto=RODAPE, handle=HANDLE):
    """Rodapé: solzinho + chamada à esquerda, @ à direita. Devolve o topo."""
    d = ImageDraw.Draw(img)
    f = fonte(MONO, 24)
    base = img.height - 12 - 44
    cap = altura_maiuscula(f)
    # ícone: mini sol listrado
    r = 17
    grad, m = sol(r * 2)
    img.paste(grad, (MARGEM, base - cap // 2 - r), m)
    x = MARGEM + r * 2 + 18
    texto = (texto or "").upper()
    handle = handle or ""
    espaco = 4
    lh = largura_espacada(handle, f, 2) if handle else 0
    disponivel = img.width - MARGEM - x - (lh + 30 if handle else 0)
    while texto and largura_espacada(texto, f, espaco) > disponivel:
        espaco -= 1
        if espaco < 0:
            texto, espaco = texto[:-2] + "…", 0
    texto_espacado(d, x, base, texto, f, CINZA, espaco)
    if handle:
        texto_espacado(d, img.width - MARGEM - lh, base, handle, f, TURQUESA, 2)
    return base - cap


def divisoria(img, y):
    """Duas linhas em 'degrau' (como um traço de neon) + logotipo à direita."""
    f_tam = 60
    larg_marca = fonte(BEBAS, f_tam).getlength("VICEVERSA")
    fim = img.width - MARGEM - larg_marca - 30
    q = round(fim * 0.44)
    m = Image.new("L", img.size)
    d = ImageDraw.Draw(m)
    d.line([(0, y), (q, y), (q + 14, y + 14), (fim, y + 14)], fill=255, width=3, joint="curve")
    d.line([(0, y + 14), (q - 26, y + 14), (q - 12, y + 28), (fim - 70, y + 28)], fill=255,
           width=3, joint="curve")
    brilho(img, m, MAGENTA, 8, 0.9)
    pintar(img, m, [TURQUESA, MAGENTA, LARANJA], (0, y - 4, fim + 4, y + 32))
    cap = altura_maiuscula(fonte(BEBAS, f_tam))
    marca(img, img.width - MARGEM, y + 14 + cap / 2, f_tam, alinhar="direita")


def selo(img, x, y_topo, rotulo, cor):
    f = fonte(MONO, 24)
    rotulo = rotulo.upper()
    alt = 52
    larg = round(largura_espacada(rotulo, f, 3)) + 78
    caixa = (x, y_topo, x + larg, y_topo + alt)
    m = Image.new("L", img.size)
    ImageDraw.Draw(m).rounded_rectangle(caixa, radius=alt // 2, fill=220)
    img.paste(Image.new("RGB", img.size, NOITE), (0, 0), m)
    borda = Image.new("L", img.size)
    ImageDraw.Draw(borda).rounded_rectangle(caixa, radius=alt // 2, outline=255, width=3)
    brilho(img, borda, cor, 8, 0.7)
    pintar(img, borda, cor)
    ponto = Image.new("L", img.size)
    cy = y_topo + alt // 2
    ImageDraw.Draw(ponto).ellipse((x + 22, cy - 7, x + 36, cy + 7), fill=255)
    brilho(img, ponto, cor, 6, 1.2)
    pintar(img, ponto, cor)
    texto_espacado(ImageDraw.Draw(img), x + 50, cy + altura_maiuscula(f) / 2, rotulo, f, cor, 3)
    return alt


def caixa_texto(img, texto, cx, y_topo, tamanho, fundo=(MAGENTA, LARANJA), cor=NOITE, pad=(26, 16)):
    """Rótulo em caixa com degradê (as faixas de chamada do card 'siga')."""
    f = fonte(BEBAS, tamanho)
    texto = texto.upper().strip()
    cap = altura_maiuscula(f)
    larg = f.getlength(texto) + pad[0] * 2
    alt = cap + pad[1] * 2
    x0 = round(cx - larg / 2)
    sombra_m = Image.new("L", img.size)
    ImageDraw.Draw(sombra_m).rectangle((x0, y_topo, x0 + larg, y_topo + alt), fill=255)
    brilho(img, sombra_m, MAGENTA, 22, 0.55)
    img.paste(degrade(larg, alt, list(fundo)), (x0, y_topo))
    ImageDraw.Draw(img).text((cx, y_topo + pad[1] + cap), texto, font=f, fill=cor, anchor="ms")
    return round(alt)


# ── fundo com foto ──────────────────────────────────────────────────
def abrir_foto(caminho):
    with Image.open(caminho) as f:
        return ImageOps.exif_transpose(f).convert("RGB")


def fundo_foto(caminho, altura_area, foco=(0.5, 0.4), modo="cobrir"):
    """Foto ocupando o topo do card até `altura_area`."""
    tam = (LARGURA, max(1, round(altura_area)))
    foto = abrir_foto(caminho)
    if modo == "inteira":
        # foto inteira, sem cortes, sobre uma versão desfocada dela mesma
        area = ImageOps.fit(foto, tam, Image.LANCZOS, centering=foco).filter(ImageFilter.GaussianBlur(38))
        area = Image.blend(area, Image.new("RGB", tam, NOITE), 0.45)
        cont = ImageOps.contain(foto, (tam[0], max(1, tam[1] - 160)), Image.LANCZOS)
        area.paste(cont, ((tam[0] - cont.width) // 2, max(0, (tam[1] - 160 - cont.height) // 2)))
    else:
        area = ImageOps.fit(foto, tam, Image.LANCZOS, centering=foco)
    img = Image.new("RGB", (LARGURA, ALTURA), NOITE)
    img.paste(area, (0, 0))
    return img


def veu(img, y_ini, y_fim, forte=250, topo=70):
    """Escurece a foto: leve no topo, total a partir de y_fim (onde fica o texto)."""
    m = Image.new("L", img.size)
    for y in range(img.height):
        a = topo * max(0.0, 1 - y / 240)
        if y >= y_fim:
            b = forte
        elif y > y_ini:
            t = (y - y_ini) / (y_fim - y_ini)
            b = forte * t * t * (3 - 2 * t)
        else:
            b = 0
        m.paste(round(max(a, b, 18)), (0, y, img.width, y + 1))
    return Image.composite(Image.new("RGB", img.size, NOITE), img, m)


def grade_rodape(img, altura=300):
    """Grade neon discreta no pé do card, sumindo para cima."""
    horizonte = img.height - altura
    m = Image.new("L", img.size)
    d = ImageDraw.Draw(m)
    for k in range(1, 9):
        t = (k / 8) ** 2
        y = horizonte + t * altura
        d.line((0, y, img.width, y), fill=round(30 + 60 * t), width=2)
    cx = img.width / 2
    for i in range(-12, 13):
        d.line((cx + i * 40, horizonte, cx + i * img.width / 5, img.height), fill=45, width=2)
    fade = Image.new("L", img.size)
    fade.paste(degrade(img.width, altura, [(0,) * 3, (255,) * 3], vertical=True).convert("L"),
               (0, horizonte))
    pintar(img, ImageChops.multiply(m, fade), MAGENTA)


def brilho_canto(img):
    """Brilho magenta/laranja difuso, como no topo do site."""
    m = Image.new("L", img.size)
    d = ImageDraw.Draw(m)
    d.ellipse((img.width * 0.55, img.height * 0.62, img.width * 1.35, img.height * 1.2), fill=70)
    brilho(img, m, MAGENTA, 140)
    m = Image.new("L", img.size)
    ImageDraw.Draw(m).ellipse((-img.width * 0.4, img.height * 0.8, img.width * 0.45, img.height * 1.3), fill=60)
    brilho(img, m, LARANJA, 140)


def _base_com_foto(imagem, y_texto, foco, modo):
    """Foto (ou cena synthwave) + véu + detalhes do fundo."""
    y_fim_foto = y_texto + 40
    if imagem:
        img = fundo_foto(imagem, y_fim_foto, foco, modo)
        img = veu(img, max(120, y_texto - 300), y_texto + 20)
    else:
        horizonte = max(420, min(y_texto - 110, 820))
        img = Image.new("RGB", (LARGURA, ALTURA), NOITE)
        img.paste(cena_synthwave(LARGURA, y_fim_foto, horizonte, sol_raio=min(250, horizonte // 3)), (0, 0))
        img = veu(img, max(120, y_texto - 170), y_texto + 20, topo=0)
    brilho_canto(img)
    grade_rodape(img)
    return img


# ── os três modelos ─────────────────────────────────────────────────
def card_noticia(titulo, imagem=None, selo_tipo=None, selo_texto="", foco=(0.5, 0.4),
                 modo_imagem="cobrir", rodape_texto=RODAPE, handle=HANDLE):
    largura = LARGURA - 2 * MARGEM
    y_rodape = ALTURA - 12 - 44 - altura_maiuscula(fonte(MONO, 24))
    base_ultima = y_rodape - 58
    fnt, linhas, lh = ajustar(titulo or " ", largura, 540, 6, 132, 60)
    base_primeira = base_ultima - lh * (len(linhas) - 1)
    topo = base_primeira - altura_primeira(fnt, linhas)

    rotulo, cor = None, None
    if selo_tipo and selo_tipo in SELOS:
        rotulo, cor = SELOS[selo_tipo]
        rotulo = selo_texto or rotulo
    y_selo = topo - 30 - 52 if rotulo else None
    y_div = (y_selo if rotulo else topo) - 44 - 28

    img = _base_com_foto(imagem, y_div, foco, modo_imagem)
    divisoria(img, y_div)
    if rotulo:
        selo(img, MARGEM, y_selo, rotulo, cor)
    desenhar_bloco(img, fnt, linhas, lh, MARGEM, base_primeira, largura)
    rodape(img, rodape_texto, handle)
    barra_inferior(img)
    return img


def dias_restantes(lancamento=LANCAMENTO, hoje=None):
    return (lancamento - (hoje or dt.date.today())).days


def card_contagem(imagem=None, lancamento=LANCAMENTO, hoje=None, dias=None, texto="",
                  foco=(0.5, 0.4), modo_imagem="cobrir", rodape_texto=RODAPE, handle=HANDLE):
    n = dias_restantes(lancamento, hoje) if dias is None else dias
    if n > 1:
        chamada, numero, linha = "FALTAM EXATAMENTE", f"{n} DIAS", "PARA GTA 6"
    elif n == 1:
        chamada, numero, linha = "É AMANHÃ! FALTA SÓ", "1 DIA", "PARA GTA 6"
    elif n == 0:
        chamada, numero, linha = "CHEGOU O DIA", "É HOJE", "GTA 6 JÁ ESTÁ ENTRE NÓS"
    else:
        chamada, numero, linha = "GTA 6 FOI LANÇADO HÁ", f"{-n} DIA{'S' if n < -1 else ''}", "E VOCÊ, JÁ ZEROU?"
    linha = texto or linha
    data_txt = f"{lancamento.day:02d} · {MESES[lancamento.month - 1]} · {lancamento.year}"

    largura = LARGURA - 2 * MARGEM
    f_mono = fonte(MONO, 24)
    y_rodape = ALTURA - 12 - 44 - altura_maiuscula(f_mono)

    # linha de baixo + selo com a data
    f_data = fonte(MONO, 26)
    larg_chip = round(largura_espacada(data_txt, f_data, 4)) + 56
    f_lin, l_lin, lh_lin = ajustar(linha, largura - larg_chip - 30, 110, 1, 104, 48)
    base_linha = y_rodape - 58
    # número gigante
    f_num, l_num, lh_num = ajustar(f"*{numero}*", largura, 330, 1, 330, 120)
    base_num = base_linha - altura_maiuscula(f_lin) - 34
    topo_num = base_num - altura_primeira(f_num, l_num)
    # chamada em mono
    f_cham = fonte(MONO, 32)
    base_cham = topo_num - 40
    y_div = base_cham - altura_maiuscula(f_cham) - 44 - 28

    img = _base_com_foto(imagem, y_div, foco, modo_imagem)
    divisoria(img, y_div)
    d = ImageDraw.Draw(img)
    esp = 8
    while largura_espacada(chamada, f_cham, esp) > largura and esp > 0:
        esp -= 1
    texto_espacado(d, MARGEM, base_cham, chamada, f_cham, TURQUESA, esp)
    desenhar_bloco(img, f_num, l_num, lh_num, MARGEM, base_num, largura, brilho_dest=MAGENTA)
    desenhar_bloco(img, f_lin, l_lin, lh_lin, MARGEM, base_linha, largura)

    # chip da data, alinhado à direita na linha de baixo
    alt = 54
    y_chip = round(base_linha - altura_maiuscula(f_lin) / 2 - alt / 2)
    caixa = (LARGURA - MARGEM - larg_chip, y_chip, LARGURA - MARGEM, y_chip + alt)
    m = Image.new("L", img.size)
    ImageDraw.Draw(m).rounded_rectangle(caixa, radius=alt // 2, outline=255, width=3)
    brilho(img, m, MAGENTA, 8, 0.8)
    pintar(img, m, MAGENTA)
    texto_espacado(ImageDraw.Draw(img), caixa[0] + 28, y_chip + alt / 2 + altura_maiuscula(f_data) / 2,
                   data_txt, f_data, LARANJA, 4)

    rodape(img, rodape_texto, handle)
    barra_inferior(img)
    return img


def card_siga(imagem=None, chamada=CHAMADA, segue=SEGUE, slogan=SLOGAN, handle=HANDLE,
              foco=(0.5, 0.3)):
    # parte de baixo primeiro: @, faixas do slogan e horizonte
    f_handle = fonte(MONO, 34)
    base_handle = ALTURA - 12 - 52
    linhas_slogan = [l for l in (slogan or "").replace("\n", "|").split("|") if l.strip()]
    alt_faixa = altura_maiuscula(fonte(BEBAS, 62)) + 30
    topo_slogan = base_handle - altura_maiuscula(f_handle) - 44 - len(linhas_slogan) * (alt_faixa + 10)
    horizonte = topo_slogan - 46

    img = cena_synthwave(LARGURA, ALTURA, horizonte, sol_raio=290)

    # foto opcional, clarinha, se misturando ao céu (como os personagens do Flow)
    if imagem:
        foto = ImageOps.fit(abrir_foto(imagem), (LARGURA, horizonte), Image.LANCZOS, centering=foco)
        m = degrade(LARGURA, horizonte, [(120,) * 3, (95,) * 3, (0,) * 3], vertical=True).convert("L")
        camada = Image.new("RGB", img.size)
        camada.paste(foto, (0, 0))
        mascara = Image.new("L", img.size)
        mascara.paste(m, (0, 0))
        img = Image.composite(ImageChops.screen(img, camada), img, mascara)

    # topo: faixas da chamada
    y = 92
    for l in [l for l in (chamada or "").replace("\n", "|").split("|") if l.strip()]:
        y += caixa_texto(img, l, LARGURA / 2, y, 78) + 12
    # "então segue o"
    d = ImageDraw.Draw(img)
    f_seg = fonte(MONO, 32)
    y += 50
    seg = (segue or "").upper()
    if seg:
        w = largura_espacada(seg, f_seg, 10)
        texto_espacado(d, (LARGURA - w) / 2, y + altura_maiuscula(f_seg), seg, f_seg, CREME, 10)
        y += altura_maiuscula(f_seg) + 36

    # logotipo gigante empilhado: VICE / VERSA
    espaco = horizonte - 30 - y
    tam = 330
    while tam > 120:
        f = fonte(BEBAS, tam)
        cap = altura_maiuscula(f)
        if cap * 2 + tam * 0.12 <= espaco and f.getlength("VERSA") <= LARGURA - 2 * MARGEM:
            break
        tam -= 4
    f = fonte(BEBAS, tam)
    cap = altura_maiuscula(f)
    b1 = y + cap
    b2 = b1 + cap + round(tam * 0.12)
    m1, m2 = Image.new("L", img.size), Image.new("L", img.size)
    ImageDraw.Draw(m1).text((LARGURA / 2, b1), "VICE", font=f, fill=255, anchor="ms",
                            stroke_width=2, stroke_fill=255)
    ImageDraw.Draw(m2).text((LARGURA / 2, b2), "VERSA", font=f, fill=255, anchor="ms",
                            stroke_width=2, stroke_fill=255)
    sombra(img, ImageChops.lighter(m1, m2), 18, 0.8, 10)
    brilho(img, m1, MAGENTA, 26, 0.6)
    brilho(img, m2, LARANJA, 30, 0.9)
    pintar(img, m1, CREME)
    lv = f.getlength("VERSA")
    pintar(img, m2, [MAGENTA, LARANJA], (LARGURA / 2 - lv / 2 - 4, b2 - cap - 6, LARGURA / 2 + lv / 2 + 4, b2 + 6))
    # contorno fino no VERSA para destacar do sol
    borda = m2.filter(ImageFilter.MaxFilter(3))
    borda = ImageChops.subtract(borda, m2)
    pintar(img, borda, NOITE)

    # faixas do slogan e @
    y = topo_slogan
    for l in linhas_slogan:
        y += caixa_texto(img, l, LARGURA / 2, y, 62, fundo=(TURQUESA, LILAS)) + 10
    if handle:
        d = ImageDraw.Draw(img)
        w = largura_espacada(handle, f_handle, 4)
        texto_espacado(d, (LARGURA - w) / 2, base_handle, handle, f_handle, CREME, 4)
    barra_inferior(img)
    return img


def gerar(tipo, **op):
    if tipo == "noticia":
        return card_noticia(op.get("titulo", ""), op.get("imagem"), op.get("selo"), op.get("selo_texto", ""),
                            op.get("foco", (0.5, 0.4)), op.get("modo_imagem", "cobrir"),
                            op.get("rodape", RODAPE), op.get("handle", HANDLE))
    if tipo == "contagem":
        return card_contagem(op.get("imagem"), op.get("lancamento", LANCAMENTO), op.get("hoje"),
                             op.get("dias"), op.get("texto", ""), op.get("foco", (0.5, 0.4)),
                             op.get("modo_imagem", "cobrir"), op.get("rodape", RODAPE), op.get("handle", HANDLE))
    if tipo == "siga":
        return card_siga(op.get("imagem"), op.get("chamada", CHAMADA), op.get("segue", SEGUE),
                         op.get("slogan", SLOGAN), op.get("handle", HANDLE), op.get("foco", (0.5, 0.3)))
    raise ValueError(f"tipo desconhecido: {tipo}")


# ── salvar ──────────────────────────────────────────────────────────
def slug(texto, limite=40):
    t = unicodedata.normalize("NFKD", texto.replace("*", "").replace("|", " "))
    t = re.sub(r"[^a-z0-9]+", "-", t.encode("ascii", "ignore").decode().lower()).strip("-")
    return t[:limite].rstrip("-") or "card"


def nome_padrao(tipo, texto=""):
    agora = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return PASTA_SAIDA / f"{tipo}-{slug(texto or tipo)}-{agora}.png"


def salvar(img, destino):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix.lower() in (".jpg", ".jpeg"):
        img.save(destino, "JPEG", quality=95, subsampling=0, optimize=True)
    else:
        if not destino.suffix:
            destino = destino.with_suffix(".png")
        img.save(destino, optimize=True)
    return destino


def ler_data(texto):
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            pass
    raise ValueError(f"data inválida: {texto!r} (use 19/11/2026 ou 2026-11-19)")


# ── janela (tkinter, já vem com o Python no Windows) ────────────────
def abrir_janela():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        from PIL import ImageTk
    except ImportError as erro:
        sys.exit(f"A janela precisa do tkinter ({erro}). Use a linha de comando: "
                 "python cards_instagram.py noticia -h")
    try:                                    # texto nítido em telas com zoom no Windows
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    raiz = tk.Tk()
    raiz.title("VICEVERSA — cards para o Instagram (1080 × 1350)")
    raiz.configure(bg="#120720")
    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    fundo, texto_cor = "#120720", "#fff3e4"
    estilo.configure(".", background=fundo, foreground=texto_cor, fieldbackground="#24123a")
    estilo.configure("TLabel", background=fundo, foreground=texto_cor)
    estilo.configure("Dica.TLabel", foreground="#b69cff", font=("Segoe UI", 8))
    estilo.configure("TRadiobutton", background=fundo, foreground=texto_cor)
    estilo.configure("TButton", background="#ff3d8a", foreground="#120720", padding=6)
    estilo.map("TButton", background=[("active", "#ff8a3d")])
    estilo.configure("TEntry", foreground=texto_cor, fieldbackground="#24123a", insertcolor=texto_cor)
    estilo.configure("TCombobox", foreground=texto_cor, fieldbackground="#24123a", arrowcolor=texto_cor)
    estilo.map("TCombobox", fieldbackground=[("readonly", "#24123a")], foreground=[("readonly", texto_cor)])

    v = {
        "tipo": tk.StringVar(value="noticia"),
        "imagem": tk.StringVar(value=""),
        "modo": tk.StringVar(value="cobrir"),
        "fx": tk.DoubleVar(value=0.5),
        "fy": tk.DoubleVar(value=0.4),
        "selo": tk.StringVar(value="nenhum"),
        "selo_texto": tk.StringVar(value=""),
        "rodape": tk.StringVar(value=RODAPE),
        "handle": tk.StringVar(value=HANDLE),
        "data": tk.StringVar(value=LANCAMENTO.strftime("%d/%m/%Y")),
        "segue": tk.StringVar(value=SEGUE),
    }

    form = ttk.Frame(raiz, padding=14)
    form.grid(row=0, column=0, sticky="ns")
    previa = tk.Label(raiz, bg="#0b0414", bd=0)
    previa.grid(row=0, column=1, padx=(0, 14), pady=14)

    linha = [0]
    grupos = {}

    def add(widget, grupo=None, **grid):
        widget.grid(**{"row": linha[0], "column": 0, "sticky": "we", "pady": (0, 6), **grid})
        linha[0] += 1
        if grupo:
            for g in grupo.split():
                grupos.setdefault(g, []).append(widget)
        return widget

    add(ttk.Label(form, text="Modelo", font=("Segoe UI", 10, "bold")))
    tipos = ttk.Frame(form)
    for valor, nome in (("noticia", "Notícia"), ("contagem", "Contagem"), ("siga", "Siga o VICEVERSA")):
        ttk.Radiobutton(tipos, text=nome, value=valor, variable=v["tipo"]).pack(side="left", padx=(0, 10))
    add(tipos)

    add(ttk.Label(form, text="Imagem", font=("Segoe UI", 10, "bold")))
    caixa_img = ttk.Frame(form)
    ttk.Button(caixa_img, text="Escolher…", command=lambda: escolher()).pack(side="left")
    ttk.Button(caixa_img, text="Sem imagem", command=lambda: v["imagem"].set("")).pack(side="left", padx=6)
    add(caixa_img)
    rotulo_img = add(ttk.Label(form, text="(nenhuma — usa o sol synthwave)", style="Dica.TLabel", wraplength=330))
    modos = ttk.Frame(form)
    ttk.Radiobutton(modos, text="Preencher (corta)", value="cobrir", variable=v["modo"]).pack(side="left")
    ttk.Radiobutton(modos, text="Imagem inteira", value="inteira", variable=v["modo"]).pack(side="left", padx=10)
    add(modos, "noticia contagem")
    focos = ttk.Frame(form)
    ttk.Label(focos, text="Enquadrar  ↔").pack(side="left")
    ttk.Scale(focos, from_=0, to=1, variable=v["fx"], length=110).pack(side="left", padx=4)
    ttk.Label(focos, text="↕").pack(side="left")
    ttk.Scale(focos, from_=0, to=1, variable=v["fy"], length=110).pack(side="left", padx=4)
    add(focos)

    rotulo_titulo = add(ttk.Label(form, text="", font=("Segoe UI", 10, "bold")))
    campo_titulo = tk.Text(form, width=44, height=5, wrap="word", bg="#24123a", fg=texto_cor,
                           insertbackground=texto_cor, relief="flat", font=("Segoe UI", 10))
    add(campo_titulo)
    campo_titulo.insert("1.0", "Vem coisa nova amanhã?! *Vários criadores* receberam pacotes especiais "
                               "da Rockstar com roupas e acessórios de GTA 6")
    dica_titulo = add(ttk.Label(form, text="", style="Dica.TLabel", wraplength=330))

    add(ttk.Label(form, text="Selo"), "noticia")
    selos = ttk.Frame(form)
    ttk.Combobox(selos, textvariable=v["selo"], values=["nenhum", *SELOS], state="readonly",
                 width=14).pack(side="left")
    ttk.Label(selos, text="  texto:").pack(side="left")
    ttk.Entry(selos, textvariable=v["selo_texto"], width=18).pack(side="left")
    add(selos, "noticia")

    add(ttk.Label(form, text="Data de lançamento (dd/mm/aaaa)"), "contagem")
    add(ttk.Entry(form, textvariable=v["data"]), "contagem")

    add(ttk.Label(form, text="Frase do meio"), "siga")
    add(ttk.Entry(form, textvariable=v["segue"]), "siga")
    add(ttk.Label(form, text="Slogan (uma faixa por linha)"), "siga")
    campo_slogan = tk.Text(form, width=44, height=2, wrap="word", bg="#24123a", fg=texto_cor,
                           insertbackground=texto_cor, relief="flat", font=("Segoe UI", 10))
    campo_slogan.insert("1.0", SLOGAN.replace("|", "\n"))
    add(campo_slogan, "siga")

    add(ttk.Label(form, text="Rodapé"), "noticia contagem")
    add(ttk.Entry(form, textvariable=v["rodape"]), "noticia contagem")
    add(ttk.Label(form, text="@ do perfil"))
    add(ttk.Entry(form, textvariable=v["handle"]))

    botoes = ttk.Frame(form)
    ttk.Button(botoes, text="Salvar card", command=lambda: salvar_card()).pack(side="left")
    ttk.Button(botoes, text="Abrir pasta", command=lambda: abrir_pasta()).pack(side="left", padx=6)
    add(botoes, pady=(10, 0))
    status = add(ttk.Label(form, text="", style="Dica.TLabel", wraplength=330))

    textos = {"noticia": "", "contagem": "", "siga": CHAMADA.replace("|", "\n")}
    ultimo_tipo = ["noticia"]
    textos["noticia"] = campo_titulo.get("1.0", "end-1c")

    def ajustar_formulario(*_):
        tipo = v["tipo"].get()
        # guarda o texto de cada modelo ao trocar
        textos[ultimo_tipo[0]] = campo_titulo.get("1.0", "end-1c")
        if tipo != ultimo_tipo[0]:
            campo_titulo.delete("1.0", "end")
            campo_titulo.insert("1.0", textos[tipo])
            ultimo_tipo[0] = tipo
        visiveis = set(grupos.get(tipo, []))
        for ws in grupos.values():
            for w in ws:
                w.grid() if w in visiveis else w.grid_remove()
        rotulo_titulo.config(text={"noticia": "Título",
                                   "contagem": "Linha de baixo (vazio = automático)",
                                   "siga": "Chamada do topo (uma faixa por linha)"}[tipo])
        dica_titulo.config(text={"noticia": "Use *asteriscos* para o degradê e Enter para quebrar a linha. "
                                            "O tamanho da letra se ajusta sozinho.",
                                 "contagem": f"Hoje faltam {dias_restantes(data_lancamento())} dias. "
                                             "Ex.: PARA GTA 6 · A CONTAGEM CONTINUA",
                                 "siga": "Cada linha vira uma faixa em degradê."}[tipo])
        agendar()

    def data_lancamento():
        try:
            return ler_data(v["data"].get())
        except ValueError:
            return LANCAMENTO

    def escolher():
        caminho = filedialog.askopenfilename(
            title="Escolha a imagem do post",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"), ("Todos", "*.*")])
        if caminho:
            v["imagem"].set(caminho)

    def opcoes():
        tipo = v["tipo"].get()
        texto = campo_titulo.get("1.0", "end-1c").strip()
        op = dict(imagem=v["imagem"].get() or None, foco=(v["fx"].get(), v["fy"].get()),
                  modo_imagem=v["modo"].get(), rodape=v["rodape"].get(), handle=v["handle"].get())
        if tipo == "noticia":
            op.update(titulo=texto or "Escreva o título", selo=None if v["selo"].get() == "nenhum" else v["selo"].get(),
                      selo_texto=v["selo_texto"].get().strip())
        elif tipo == "contagem":
            op.update(lancamento=data_lancamento(), texto=texto)
        else:
            op.update(chamada=texto, segue=v["segue"].get(), slogan=campo_slogan.get("1.0", "end-1c"))
        return tipo, texto, op

    pendente = [None]
    atual = {"img": None, "foto": None}

    def agendar(*_):
        if pendente[0]:
            raiz.after_cancel(pendente[0])
        pendente[0] = raiz.after(250, atualizar)

    def atualizar():
        pendente[0] = None
        caminho = v["imagem"].get()
        rotulo_img.config(text=Path(caminho).name if caminho else "(nenhuma — usa o sol synthwave)")
        try:
            tipo, _, op = opcoes()
            img = gerar(tipo, **op)
        except Exception as erro:          # imagem inválida, etc.
            status.config(text=f"Não deu para gerar a prévia: {erro}")
            return
        atual["img"] = img
        alt = max(400, min(700, raiz.winfo_screenheight() - 160))
        mini = img.resize((round(alt * LARGURA / ALTURA), alt), Image.LANCZOS)
        atual["foto"] = ImageTk.PhotoImage(mini)
        previa.config(image=atual["foto"])
        status.config(text="")

    def salvar_card():
        if atual["img"] is None:
            atualizar()
        tipo, texto, _ = opcoes()
        sugestao = nome_padrao(tipo, texto)
        sugestao.parent.mkdir(parents=True, exist_ok=True)
        caminho = filedialog.asksaveasfilename(
            title="Salvar card", initialdir=str(sugestao.parent), initialfile=sugestao.name,
            defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if caminho:
            destino = salvar(atual["img"], caminho)
            status.config(text=f"Salvo: {destino}")

    def abrir_pasta():
        import os
        import subprocess
        PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(PASTA_SAIDA)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(PASTA_SAIDA)])
            else:
                subprocess.Popen(["xdg-open", str(PASTA_SAIDA)])
        except Exception as erro:
            messagebox.showinfo("Pasta", f"{PASTA_SAIDA}\n({erro})")

    v["tipo"].trace_add("write", ajustar_formulario)
    for nome, var in v.items():
        if nome != "tipo":
            var.trace_add("write", agendar)
    campo_titulo.bind("<KeyRelease>", agendar)
    campo_slogan.bind("<KeyRelease>", agendar)
    ajustar_formulario()
    raiz.mainloop()


# ── linha de comando ────────────────────────────────────────────────
EXEMPLOS = """
exemplos:
  python cards_instagram.py
      abre a janela com prévia ao vivo

  python cards_instagram.py noticia --imagem foto.jpg --selo rumor \\
      --titulo "Vem coisa nova amanhã?! *Vários criadores* receberam pacotes da Rockstar"

  python cards_instagram.py contagem --imagem logo-gta6.jpg
  python cards_instagram.py contagem --lancamento 19/11/2026 --saida faltam.png

  python cards_instagram.py siga --imagem personagens.jpg \\
      --chamada "Quer ficar por dentro|de tudo sobre GTA 6?!"

texto: *asteriscos* = degradê magenta→laranja;  |  = quebra de linha
"""


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="cards_instagram.py",
        description="Gera cards 1080×1350 para o Instagram na identidade do VICEVERSA.",
        epilog=EXEMPLOS, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="tipo", metavar="{noticia,contagem,siga,janela}")

    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--imagem", help="foto/arte do post (jpg, png, webp)")
    comum.add_argument("--saida", help="arquivo de saída (.png ou .jpg); padrão: cards-instagram/")
    comum.add_argument("--handle", default=HANDLE, help=f"@ do perfil (padrão: {HANDLE})")
    comum.add_argument("--foco-x", type=float, default=0.5, help="enquadramento horizontal da foto, 0 a 1")
    comum.add_argument("--foco-y", type=float, default=None, help="enquadramento vertical da foto, 0 a 1")
    foto = argparse.ArgumentParser(add_help=False)
    foto.add_argument("--modo-imagem", choices=("cobrir", "inteira"), default="cobrir",
                      help="cobrir = preenche e corta; inteira = mostra a foto toda")
    foto.add_argument("--rodape", default=RODAPE, help=f"texto do rodapé (padrão: {RODAPE})")

    n = sub.add_parser("noticia", parents=[comum, foto], help="card de notícia",
                       formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EXEMPLOS)
    n.add_argument("--titulo", required=True, help="texto do post; *asteriscos* destacam, | quebra a linha")
    n.add_argument("--selo", choices=list(SELOS), help="etiqueta acima do título")
    n.add_argument("--selo-texto", default="", help="troca o texto da etiqueta (ex.: 'VIA INSIDER')")

    c = sub.add_parser("contagem", parents=[comum, foto], help="faltam N dias para GTA 6")
    c.add_argument("--lancamento", default=LANCAMENTO.strftime("%d/%m/%Y"), help="data de lançamento")
    c.add_argument("--hoje", help="data de referência (padrão: hoje)")
    c.add_argument("--dias", type=int, help="força o número de dias")
    c.add_argument("--texto", default="", help="troca a linha de baixo (padrão: PARA GTA 6)")

    s = sub.add_parser("siga", parents=[comum], help="card 'segue o VICEVERSA'")
    s.add_argument("--chamada", default=CHAMADA, help="faixas do topo, separadas por |")
    s.add_argument("--segue", default=SEGUE, help="frase acima do logotipo")
    s.add_argument("--slogan", default=SLOGAN, help="faixas de baixo, separadas por |")

    sub.add_parser("janela", help="abre a janela com prévia (o mesmo que rodar sem nada)")

    a = p.parse_args(argv)
    if a.tipo in (None, "janela"):
        abrir_janela()
        return

    foco = (a.foco_x, a.foco_y if a.foco_y is not None else (0.3 if a.tipo == "siga" else 0.4))
    op = dict(imagem=a.imagem, foco=foco, handle=a.handle)
    if a.imagem and not Path(a.imagem).exists():
        p.error(f"imagem não encontrada: {a.imagem}")
    if a.tipo == "noticia":
        op.update(titulo=a.titulo, selo=a.selo, selo_texto=a.selo_texto, modo_imagem=a.modo_imagem, rodape=a.rodape)
        texto = a.titulo
    elif a.tipo == "contagem":
        try:
            op.update(lancamento=ler_data(a.lancamento), hoje=ler_data(a.hoje) if a.hoje else None)
        except ValueError as erro:
            p.error(str(erro))
        op.update(dias=a.dias, texto=a.texto, modo_imagem=a.modo_imagem, rodape=a.rodape)
        texto = f"{dias_restantes(op['lancamento'], op['hoje']) if a.dias is None else a.dias}-dias"
    else:
        op.update(chamada=a.chamada, segue=a.segue, slogan=a.slogan)
        texto = "segue"
    img = gerar(a.tipo, **op)
    destino = salvar(img, a.saida or nome_padrao(a.tipo, texto))
    print(f"Card salvo em: {destino}")


if __name__ == "__main__":
    main()
