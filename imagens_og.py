#!/usr/bin/env python3
"""
VICEVERSA — imagem de compartilhamento de cada notícia
======================================================
Gera a arte 1200×630 que aparece quando alguém compartilha o link da notícia
no WhatsApp, X, Facebook, Telegram, Discord etc.:

    foto da notícia (escurecida) + marca VICEVERSA + selo + título + data

É chamado pelo montar.py, uma imagem por notícia e por idioma, gravadas em
docs/og/<slug>-<idioma>.jpg. Precisa da biblioteca Pillow:

    pip install pillow

Sem o Pillow o site é gerado normalmente e o compartilhamento usa a foto da
notícia, como antes.

As fontes ficam em fontes/ (Bebas Neue e IBM Plex Mono, licença SIL OFL,
que permite redistribuir junto com o site).
"""

import re
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:          # o montar.py confere DISPONIVEL antes de usar
    Image = None

DISPONIVEL = Image is not None

RAIZ = Path(__file__).parent
FONTES = RAIZ / "fontes"
LARGURA, ALTURA = 1200, 630
MARGEM = 64

NOITE = (18, 7, 32)
CREME = (255, 243, 228)
MAGENTA = (255, 61, 138)
LARANJA = (255, 138, 61)
CORES_SELO = {
    "confirmado": (47, 230, 200),
    "rumor": (255, 138, 61),
    "vazamento": (255, 61, 138),
    "regiao": (255, 61, 138),       # locais do mapa: mesmas cores dos pontos
    "marco": (47, 230, 200),
}

_fontes = {}


def fonte(nome, tamanho):
    chave = (nome, tamanho)
    if chave not in _fontes:
        _fontes[chave] = ImageFont.truetype(str(FONTES / nome), tamanho)
    return _fontes[chave]


def _degrade_horizontal(largura, altura, cor_a, cor_b):
    faixa = Image.new("RGB", (largura, 1))
    for x in range(largura):
        t = x / max(1, largura - 1)
        faixa.putpixel((x, 0), tuple(round(a + (b - a) * t) for a, b in zip(cor_a, cor_b)))
    return faixa.resize((largura, altura))


def _fundo(caminho_foto):
    """Foto da notícia recortada em 1200×630, escurecida; sem foto, fundo da marca."""
    base = Image.new("RGB", (LARGURA, ALTURA), NOITE)
    if caminho_foto and Path(caminho_foto).exists():
        try:
            with Image.open(caminho_foto) as foto:
                foto = ImageOps.exif_transpose(foto).convert("RGB")
                base = ImageOps.fit(foto, (LARGURA, ALTURA), Image.LANCZOS, centering=(0.5, 0.4))
        except OSError:
            pass
    else:
        # sem foto: brilho magenta/laranja discreto, como no topo do site
        brilho = Image.new("RGB", (LARGURA, ALTURA), NOITE)
        d = ImageDraw.Draw(brilho)
        d.ellipse((620, -260, 1460, 520), fill=(92, 18, 70))
        d.ellipse((-300, 330, 520, 980), fill=(70, 30, 22))
        base = brilho.filter(ImageFilter.GaussianBlur(120))

    # véu escuro: leve no meio, forte embaixo (onde fica o título) e no topo (marca)
    veu = Image.new("L", (LARGURA, ALTURA))
    for y in range(ALTURA):
        topo = 175 * max(0.0, 1 - y / 190)
        baixo = 250 * max(0.0, (y - 120) / (ALTURA - 120)) ** 0.75
        veu.paste(round(min(250, max(95, topo, baixo))), (0, y, LARGURA, y + 1))
    return Image.composite(Image.new("RGB", base.size, NOITE), base, veu)


def _quebrar(texto, fnt, largura_max):
    linhas, atual = [], ""
    for palavra in texto.split(" "):
        if not palavra:
            continue
        teste = f"{atual} {palavra}".strip()
        if fnt.getlength(teste) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _titulo(texto, largura_max):
    """Maior tamanho de fonte em que o título cabe em até 3 linhas."""
    texto = " ".join(texto.upper().split())
    # "GTA 6" / "GTA VI" nunca se separam (evita um "6" sozinho na última linha)
    texto = re.sub(r"\bGTA (6|VI)\b", "GTA\u00a0\\1", texto)
    for tamanho in range(104, 55, -4):
        fnt = fonte("BebasNeue-Regular.ttf", tamanho)
        linhas = _quebrar(texto, fnt, largura_max)
        if len(linhas) <= 3:
            return fnt, linhas
    # muito longo: corta na terceira linha com reticências
    fnt = fonte("BebasNeue-Regular.ttf", 56)
    linhas = _quebrar(texto, fnt, largura_max)[:3]
    while fnt.getlength(linhas[-1] + "…") > largura_max and " " in linhas[-1]:
        linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
    linhas[-1] += "…"
    return fnt, linhas


def gerar(destino, titulo, rodape, caminho_foto=None, selo=None, selo_texto=""):
    """Grava a arte em `destino` (JPEG).

    selo: confirmado | rumor | vazamento (notícias) ou regiao | marco (locais do mapa).
    """
    img = _fundo(caminho_foto)
    d = ImageDraw.Draw(img)

    # marca: VICE em creme, VERSA com o degradê do site
    f_marca = fonte("BebasNeue-Regular.ttf", 58)
    d.text((MARGEM, 46), "VICE", font=f_marca, fill=CREME)
    x_versa = MARGEM + round(f_marca.getlength("VICE"))
    mascara = Image.new("L", img.size)
    ImageDraw.Draw(mascara).text((x_versa, 46), "VERSA", font=f_marca, fill=255)
    larg_versa = round(f_marca.getlength("VERSA")) + 4
    degrade = Image.new("RGB", img.size)
    degrade.paste(_degrade_horizontal(larg_versa, 80, MAGENTA, LARANJA), (x_versa, 40))
    img.paste(degrade, (0, 0), mascara)

    # rodapé: faixa em degradê + data e endereço
    img.paste(_degrade_horizontal(LARGURA, 10, MAGENTA, LARANJA), (0, ALTURA - 10))
    f_mono = fonte("IBMPlexMono-Medium.ttf", 24)
    y_rodape = ALTURA - 10 - 44 - 24
    d.text((MARGEM, y_rodape), rodape.upper(), font=f_mono, fill=(214, 204, 196))

    # título, de baixo para cima
    f_tit, linhas = _titulo(titulo, LARGURA - 2 * MARGEM)
    altura_linha = round(f_tit.size * 0.98)
    y = y_rodape - 26 - altura_linha * len(linhas)
    for i, linha in enumerate(linhas):
        d.text((MARGEM, y + i * altura_linha), linha.replace("\u00a0", " "), font=f_tit, fill=CREME)

    # selo acima do título
    if selo in CORES_SELO and selo_texto:
        cor = CORES_SELO[selo]
        f_selo = fonte("IBMPlexMono-Medium.ttf", 22)
        rotulo = selo_texto.upper()
        larg = round(f_selo.getlength(rotulo)) + 64
        alt = 44
        y_selo = y - alt - 22
        caixa = (MARGEM, y_selo, MARGEM + larg, y_selo + alt)
        fundo = Image.new("RGB", img.size, NOITE)
        m = Image.new("L", img.size)
        ImageDraw.Draw(m).rounded_rectangle(caixa, radius=alt // 2, fill=210)
        img.paste(fundo, (0, 0), m)
        d.rounded_rectangle(caixa, radius=alt // 2, outline=cor, width=3)
        d.ellipse((MARGEM + 20, y_selo + alt // 2 - 6, MARGEM + 32, y_selo + alt // 2 + 6), fill=cor)
        d.text((MARGEM + 44, y_selo + alt // 2), rotulo, font=f_selo, fill=cor, anchor="lm")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=84, optimize=True, progressive=True)
    return destino


# ── locais do mapa ──────────────────────────────────────────────────
MAR_NOITE = (7, 17, 42)
_mapa_base = {}


def recorte_mapa(previa, destino, fx, fy, largura_unid, altura_mapa, largura_mapa,
                 cor=(47, 230, 200), centro_y=0.5, tamanho=(LARGURA, ALTURA)):
    """Recorta a imagem do mapa em volta do ponto (fx, fy) e marca o local.

    previa        mapa/leonida-noite.webp (o mapa inteiro, já pintado)
    fx, fy        posição do local em frações do mapa (0 a 1)
    largura_unid  quanto do mapa (em unidades do vetor) cabe na largura do recorte
    centro_y      altura em que o marcador fica (0.5 = meio; menos = mais para cima)
    """
    chave = str(previa)
    if chave not in _mapa_base:
        _mapa_base[chave] = Image.open(previa).convert("RGB")
    base = _mapa_base[chave]
    escala = base.width / largura_mapa                   # px da prévia por unidade do mapa
    larg_px = largura_unid * escala
    alt_px = larg_px * tamanho[1] / tamanho[0]
    cx, cy = fx * largura_mapa * escala, fy * altura_mapa * escala
    x0, y0 = cx - larg_px / 2, cy - alt_px * centro_y
    caixa = tuple(round(v) for v in (x0, y0, x0 + larg_px, y0 + alt_px))

    # o que sair da borda do mapa vira mar
    tela = Image.new("RGB", (caixa[2] - caixa[0], caixa[3] - caixa[1]), MAR_NOITE)
    dentro = (max(0, caixa[0]), max(0, caixa[1]), min(base.width, caixa[2]), min(base.height, caixa[3]))
    if dentro[0] < dentro[2] and dentro[1] < dentro[3]:
        tela.paste(base.crop(dentro), (dentro[0] - caixa[0], dentro[1] - caixa[1]))
    img = tela.resize(tamanho, Image.LANCZOS)

    # marcador: brilho, anel e ponto na cor da categoria
    mx, my = tamanho[0] / 2, tamanho[1] * centro_y
    brilho = Image.new("L", tamanho)
    ImageDraw.Draw(brilho).ellipse((mx - 70, my - 70, mx + 70, my + 70), fill=150)
    brilho = brilho.filter(ImageFilter.GaussianBlur(28))
    img = Image.composite(Image.new("RGB", tamanho, cor), img, brilho)
    d = ImageDraw.Draw(img)
    d.ellipse((mx - 30, my - 30, mx + 30, my + 30), outline=cor, width=4)
    d.ellipse((mx - 15, my - 15, mx + 15, my + 15), fill=cor, outline=(255, 243, 228), width=4)

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.suffix == ".webp":
        img.save(destino, "WEBP", quality=80, method=6)
    else:
        img.save(destino, "JPEG", quality=84, optimize=True, progressive=True)
    return destino
