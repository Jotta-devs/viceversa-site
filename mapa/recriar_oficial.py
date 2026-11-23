#!/usr/bin/env python3
"""
VICEVERSA — mapa de Leonida a partir do mapa oficial da Rockstar
================================================================

Base: o pôster oficial "Visit Leonida" que a Rockstar liberou de graça no
lançamento (19/11/2026), em rockstargames.com/VI/media → Ilustrações
("Baixar tudo"). Coloque o JPG em mapa/base/ (a versão de 5775 px dá o
máximo de detalhe; a de 2805 px, do site da Rockstar, também funciona).

O traçado é 100% o do pôster: nada é redesenhado à mão nem aproximado.
O script

  1. acha a moldura do mapa e tira a legenda, a rosa dos ventos, o selo,
     a grade e os textos impressos (os nomes são escritos pelo site, nos três
     idiomas, a partir de mapa/pontos.json);
  2. troca as cores do pôster, pixel a pixel, pelas do estilo do site (Dia,
     claro como um mapa de navegação, e Noite), com uma tabela de cores 3D:
     cada tom do pôster (mar, raso, verde com relevo, cidade, rua, ferrovia,
     areia) vira o tom equivalente da paleta, mantendo o antialiasing;
  3. grava mapa/leonida-dia.webp e mapa/leonida-noite.webp (na resolução
     do pôster, até 4096 px) e versões de 2048 px para o celular, além de
     mapa/leonida.json (tamanho e grade, igual à do pôster: A–M × 1–9).

Uso:
    pip install opencv-python-headless numpy pillow
    python mapa/recriar_oficial.py
    python mapa/poster_site.py      # camada e seção com o pôster original
    python montar.py
"""

import json
import os
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("Faltam bibliotecas. Rode:  pip install opencv-python-headless numpy pillow")

PASTA = Path(__file__).parent
BASE = PASTA / "base"
INFO = PASTA / "leonida.json"
PONTOS = PASTA / "pontos.json"

COLUNAS, LINHAS = 9, 13          # grade do pôster: colunas 1–9, linhas A–M (células de 1 milha)
REF = 1755                       # largura de referência da moldura: as coordenadas do site usam essa escala

# áreas decorativas do pôster, em frações da moldura (x0, y0, x1, y1): viram mar
DECORACOES = [
    (0.050, 0.028, 0.208, 0.172),   # Visit Leonida + legenda
    (0.095, 0.680, 0.190, 0.752),   # rosa dos ventos
    (0.680, 0.775, 0.960, 0.958),   # selo e "The Great State of Leonida"
]

# tons do pôster (RGB) → tons do site. Cada pixel vira a mistura dos tons do site
# dos tons do pôster mais próximos (em Lab), então bordas e relevo continuam suaves.
PALETAS = {
    "dia": [
        ((1, 174, 202), (158, 195, 247)), ((0, 158, 184), (150, 189, 243)),        # mar
        ((40, 184, 208), (170, 203, 248)), ((100, 196, 213), (184, 212, 250)),     # raso e lagos
        ((150, 210, 222), (198, 222, 251)),
        ((127, 174, 168), (232, 240, 224)), ((88, 154, 136), (221, 233, 209)),     # verde, do baixo ao alto
        ((70, 143, 114), (208, 226, 192)), ((55, 123, 96), (192, 215, 172)),
        ((33, 100, 74), (174, 202, 152)), ((20, 130, 110), (190, 221, 172)),
        ((114, 140, 113), (226, 231, 207)),                                        # campo
        ((200, 186, 150), (246, 236, 200)), ((229, 235, 210), (250, 245, 224)),    # areia
        ((159, 172, 182), (214, 218, 226)), ((130, 150, 160), (199, 205, 216)),    # quarteirões
        ((190, 205, 210), (246, 247, 250)), ((215, 225, 228), (252, 252, 253)),    # ruas
        ((250, 251, 251), (255, 255, 255)),                                        # rodovias e avenidas
        ((116, 103, 101), (169, 155, 181)), ((150, 60, 60), (169, 155, 181)),      # ferrovias
        ((85, 89, 94), (205, 208, 215)),                                           # sombras
    ],
    "noite": [
        ((1, 174, 202), (23, 38, 60)), ((0, 158, 184), (21, 35, 56)),
        ((40, 184, 208), (27, 45, 69)), ((100, 196, 213), (31, 52, 78)),
        ((150, 210, 222), (35, 58, 86)),
        ((127, 174, 168), (40, 51, 64)), ((88, 154, 136), (37, 49, 61)),
        ((70, 143, 114), (35, 52, 58)), ((55, 123, 96), (33, 55, 54)),
        ((33, 100, 74), (30, 56, 50)), ((20, 130, 110), (32, 58, 52)),
        ((114, 140, 113), (44, 52, 60)),
        ((200, 186, 150), (62, 61, 58)), ((229, 235, 210), (70, 69, 65)),
        ((159, 172, 182), (45, 55, 70)), ((130, 150, 160), (40, 49, 63)),
        ((190, 205, 210), (70, 80, 96)), ((215, 225, 228), (84, 94, 110)),
        ((250, 251, 251), (104, 114, 130)),
        ((116, 103, 101), (106, 92, 128)), ((150, 60, 60), (106, 92, 128)),
        ((85, 89, 94), (48, 57, 72)),
    ],
}


# ── utilidades ──────────────────────────────────────────────────────
def carregar():
    imagens = sorted([p for p in BASE.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                      and "leonida" in p.name.lower() and "satelite" not in p.name.lower()],
                     key=lambda p: p.stat().st_size)
    if not imagens:
        sys.exit(f"Coloque o mapa oficial (Leonida_Map_Poster*.jpg) em {BASE}/")
    caminho = imagens[-1]                         # a maior: mais detalhe
    # o pôster para impressão vem em CMYK com perfil de cor (GRACoL): converte para sRGB pelo perfil,
    # senão as cores saem trocadas
    import io
    from PIL import ImageCms
    Image.MAX_IMAGE_PIXELS = None
    try:
        img = Image.open(caminho)
        perfil = img.info.get("icc_profile")
        if perfil and img.mode != "RGB":
            img = ImageCms.profileToProfile(img, ImageCms.ImageCmsProfile(io.BytesIO(perfil)),
                                            ImageCms.createProfile("sRGB"), outputMode="RGB", renderingIntent=0)
        img = img.convert("RGB")
    except OSError:
        sys.exit(f"Não consegui ler {caminho.name}")
    return np.asarray(img).copy(), caminho.name


def moldura(rgb):
    """A moldura escura do mapa: linhas quase inteiras de pixels escuros."""
    g = rgb.astype(np.float32).mean(2)
    h, w = g.shape
    escuro = g < 95
    cols = escuro[int(h * .1):int(h * .9)].mean(0)
    rows = escuro[:, int(w * .1):int(w * .9)].mean(1)
    xs = np.where(cols > .85)[0]
    ys = np.where(rows > .85)[0]
    esq = xs[xs < w * .2]; dir_ = xs[xs > w * .8]
    top = ys[ys < h * .2]; bai = ys[ys > h * .8]
    if not (len(esq) and len(dir_) and len(top) and len(bai)):
        sys.exit("Não achei a moldura do mapa no pôster.")
    return int(esq.max()) + 1, int(top.max()) + 1, int(dir_.min()), int(bai.min())


def limpar(m, minimo):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    ok = np.zeros(n, bool)
    ok[1:] = st[1:, cv2.CC_STAT_AREA] >= minimo
    return ok[lab]


# ── limpeza do pôster ───────────────────────────────────────────────
def achar_grade(rgb):
    """Onde estão as linhas da grade no pôster: (x da coluna 1, y da linha A, lado da célula), em px.

    As células são quadradas (1 milha). As 9 colunas ocupam a largura da moldura,
    mas as 13 linhas passam da altura: as linhas A e M ficam cortadas pela moldura.
    As linhas da grade são finas e claras; o pico da média de brilho acha cada uma."""
    h, w = rgb.shape[:2]
    V = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[..., 2].astype(np.float32)
    passo0 = w / COLUNAS
    raio = int(passo0 * 0.12)

    def picos(perfil, n, inicio):
        alta = perfil - cv2.blur(perfil.reshape(-1, 1), (1, 31)).ravel()
        achados = []
        for i in range(1, n):
            c = int(round(inicio + i * passo0))
            a, b = max(0, c - raio), min(len(perfil), c + raio + 1)
            if b - a < 3:
                continue
            j = a + int(np.argmax(alta[a:b]))
            if alta[j] > 6:
                achados.append((i, j))
        return achados

    cols = picos(V.mean(0), COLUNAS, 0)
    lins = picos(V.mean(1), LINHAS, (h - LINHAS * passo0) / 2)
    # reta única (mesmo passo nos dois eixos): pos = origem + i * passo
    A, B = [], []
    for i, x in cols:
        A.append([i, 1, 0]); B.append(x)
    for j, y in lins:
        A.append([j, 0, 1]); B.append(y)
    if len(cols) < 3 or len(lins) < 3:
        return 0.0, (h - LINHAS * passo0) / 2, passo0
    passo, ox, oy = np.linalg.lstsq(np.array(A, float), np.array(B, float), rcond=None)[0]
    return float(ox), float(oy), float(passo)


def mascara_textos(rgb, k, grade=None):
    """Textos, escudos e linhas da grade → máscara para inpaint.

    Os nomes estão em mapa/pontos.json (rótulos oficiais, com posição); em
    volta de cada um, o texto claro e o contorno escuro saem. A grade é uma
    linha clara fina nas divisas das células."""
    h, w = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.int16)
    Hh, V, S = hsv[..., 0], hsv[..., 2], hsv[..., 1]
    alvo = np.zeros((h, w), bool)
    try:
        dados = json.loads(PONTOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    tam = {"condado": (30, 46), "oceano": (15, 26), "cidade": (17, 30), "vila": (11, 15), "bairro": (11, 15),
           "regiao": (11, 30), "ilha": (11, 30), "agua": (10, 16), "parque": (11, 30), "poi": (9, 26)}
    duas_linhas = {"port-gellhorn", "watson-bay", "waning-sands", "mile-zero-air-station"}
    # nomes que no site são o próprio marcador da região (não estão em "rotulos")
    regioes = {"vice-city": ("cidade", "Vice City"), "port-gellhorn": ("cidade", "Port Gellhorn"),
               "ambrosia": ("cidade", "Ambrosia"), "grassrivers": ("cidade", "Grassrivers"),
               "mount-kalaga": ("parque", "Mount Kalaga National Park")}
    extras = [{"id": p["id"], "tipo": regioes[p["id"]][0], "nome": {"en": regioes[p["id"]][1]}, "x": p["x"], "y": p["y"]}
              for p in dados.get("pontos", []) if p.get("id") in regioes]
    for r in dados.get("rotulos", []) + extras:
        nome = r.get("nome", {}).get("en", "") if isinstance(r.get("nome"), dict) else str(r.get("nome", ""))
        cw, lh = tam.get(r.get("tipo"), (11, 16))
        letras = len(nome)
        if r.get("id") in duas_linhas:
            letras, lh = max(len(p) for p in nome.split()) + 2, lh * 2
        larg = min(letras, 22 if r.get("tipo") in ("regiao", "ilha", "parque", "poi") else 40) * cw * 0.78 + 14
        x, y = r["x"] * w, r["y"] * h
        # caixa central (onde o texto com certeza está) e uma caixa maior para pegar as letras inteiras
        cx0, cx1 = int(x - larg / 2 * k), int(x + larg / 2 * k)
        cy0, cy1 = int(y - lh * 0.6 * k), int(y + lh * 0.6 * k)
        x0, x1 = max(0, int(x - larg * 0.8 * k)), min(w, int(x + larg * 0.8 * k))
        y0, y1 = max(0, int(y - lh * 1.1 * k)), min(h, int(y + lh * 1.1 * k))
        if x1 <= x0 or y1 <= y0:
            continue
        caixa = V[y0:y1, x0:x1].astype(np.float32)
        if r.get("tipo") in ("agua", "oceano"):
            fundo = cv2.medianBlur(V[y0:y1, x0:x1].astype(np.uint8), max(3, int(9 * k) | 1)).astype(np.float32)
            texto = caixa < fundo - 12                 # nome da água: texto mais escuro que o mar
            alvo[y0:y1, x0:x1] |= cv2.dilate(texto.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            continue
        # só os pixels das letras: creme (bairros, cidades, condados), lilás claro (lugares)
        # ou branco grosso com contorno escuro (nomes grandes); as ruas por baixo ficam
        hh, ss, vv = Hh[y0:y1, x0:x1], S[y0:y1, x0:x1], V[y0:y1, x0:x1]
        creme = ((hh >= 12) & (hh <= 45) & (ss >= 25) & (ss <= 58) & (vv >= 200)) | ((hh >= 12) & (hh <= 40) & (ss >= 35) & (vv >= 218))
        lilas = (hh >= 105) & (hh <= 165) & (ss >= 10) & (ss <= 70) & (vv >= 212)
        trilho = ((hh <= 15) | (hh >= 166)) & (ss >= 35)                     # ferrovia: vermelho-escuro
        escuro = (vv < 135) & ((ss < 80) | ((hh >= 112) & (hh <= 165))) & ~trilho   # contorno cinza ou roxo
        branco = (vv >= 236) & (ss <= 26)
        perto_escuro = cv2.dilate(escuro.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(2.5 * k))) > 0
        grosso = cv2.distanceTransform(branco.astype(np.uint8), cv2.DIST_L2, 3) >= 1.6 * k
        grosso = cv2.dilate(grosso.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(1.7 * k))) > 0
        # letras brancas grandes: traço grosso com contorno escuro (o miolo fica longe do contorno)
        perto_escuro_largo = cv2.dilate(escuro.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(5 * k))) > 0
        branco_fino = (vv >= 200) & (ss <= 58) & perto_escuro          # letras claras (branco, lilás) com contorno
        corpo = creme | (lilas & perto_escuro) | (branco & grosso & perto_escuro_largo) | branco_fino
        if r.get("tipo") in ("condado", "cidade"):
            corpo |= branco & grosso                                     # nomes grandes sem contorno
        corpo = limpar(corpo, max(2, int(1.5 * k * k)))
        # só o que está na caixa central (com folga), para não pegar letreiros vizinhos
        nucleo = np.zeros_like(corpo)
        nucleo[max(0, cy0 - y0 - int(4 * k)):max(0, cy1 - y0 + int(4 * k)), max(0, cx0 - x0 - int(10 * k)):max(0, cx1 - x0 + int(10 * k))] = True
        # o nome inteiro: letras ligadas (pelo contorno) a alguma letra da caixa central
        juntas = cv2.dilate(corpo.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(1.2 * k)))
        n, lab, _, _ = cv2.connectedComponentsWithStats(juntas, 8)
        ok = np.zeros(n, bool); ok[np.unique(lab[nucleo & (juntas > 0)])] = True; ok[0] = False
        corpo &= ok[lab]
        # contorno/sombra: escuro, ou bem mais escuro que o entorno (sobre a água ele é azul-escuro)
        fundo = cv2.medianBlur(vv.astype(np.uint8), max(3, int(11 * k) | 1)).astype(np.int16)
        sombra = escuro | (vv < fundo - 28)
        contorno = sombra & (cv2.dilate(corpo.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(3 * k))) > 0)
        sel = cv2.dilate((corpo | contorno).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        alvo[y0:y1, x0:x1] |= sel
    for e in dados.get("escudos", []):
        x, y = e["x"] * w, e["y"] * h
        r = (20 if e.get("tipo") in ("interstate", "estadual", "pedagio") else 17) * k
        alvo[max(0, int(y - r)):int(y + r), max(0, int(x - r)):int(x + r)] = True
    alvo = cv2.dilate(alvo.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(round(k)))) > 0
    # grade do pôster: só a faixa estreita da linha (no mar ela é azul-clara, não branca)
    ox, oy, passo = grade or (0.0, 0.0, w / COLUNAS)
    m = int(round(1.4 * k)) + 1
    for i in range(1, COLUNAS):
        x = int(round(ox + i * passo))
        alvo[:, max(0, x - m):x + m + 1] = True
    for j in range(0, LINHAS + 1):
        y = int(round(oy + j * passo))
        if 0 <= y < h:
            alvo[max(0, y - m):y + m + 1] = True
    return alvo


def apagar_decoracoes(rgb):
    h, w = rgb.shape[:2]
    out = rgb.copy()
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mar = (hsv[..., 0] > 84) & (hsv[..., 0] < 102) & (hsv[..., 1] > 150)
    cor = np.median(rgb[mar], 0).astype(np.uint8) if mar.any() else np.array([0, 174, 202], np.uint8)
    for x0, y0, x1, y1 in DECORACOES:
        out[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = cor
    return out


# ── cores ───────────────────────────────────────────────────────────
def _lab(cores):
    c = np.asarray(cores, np.uint8).reshape(-1, 1, 3)
    return cv2.cvtColor(c, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32) * [100 / 255, 1, 1] - [0, 128, 128]


def tabela(pares, sigma=7.0, dura=False):
    """Tabela de cores 3D (64³): para cada cor, a mistura dos tons do site dos tons do pôster
    mais próximos (dura=True: só o mais próximo, para as áreas reconstruídas sob os textos)."""
    origem = _lab([p[0] for p in pares])
    destino = np.float32([p[1] for p in pares])
    g = np.arange(2, 256, 4)
    grade = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    d2 = ((_lab(grade)[:, None, :] - origem[None]) ** 2).sum(-1)
    if dura:
        peso = np.eye(len(pares), dtype=np.float32)[d2.argmin(1)]
    else:
        peso = np.exp(-(d2 - d2.min(1, keepdims=True)) / (2 * sigma * sigma))
        peso /= peso.sum(1, keepdims=True)
    return np.clip(peso @ destino, 0, 255).astype(np.uint8)


def aplicar(img, tab):
    i = (img[..., 0] >> 2).astype(np.int32) * 4096 + (img[..., 1] >> 2).astype(np.int32) * 64 + (img[..., 2] >> 2)
    return tab[i]


def salvar(img, nome, largura, qualidade=82):
    im = Image.fromarray(img)
    if im.width > largura:
        im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
    im.save(PASTA / nome, "WEBP", quality=qualidade, method=6)
    print(f"  ✓ mapa/{nome} ({im.width}×{im.height}, {(PASTA / nome).stat().st_size // 1024} KB)")
    return {"src": nome, "w": im.width, "h": im.height}


# ── principal ───────────────────────────────────────────────────────
def main():
    rgb0, origem = carregar()
    x0, y0, x1, y1 = moldura(rgb0)
    rgb = rgb0[y0:y1, x0:x1].copy()
    h, w = rgb.shape[:2]
    k = w / REF
    W, H = REF, round(h / k, 1)                    # o site usa sempre a escala de referência
    print(f"Base: {origem} · moldura {w}×{h} px (escala {k:.2f})")

    rgb = apagar_decoracoes(rgb)
    grade = achar_grade(rgb)
    print("Grade: coluna 1 em x=%.1f, linha A em y=%.1f, célula %.1f px" % grade)
    alvo = mascara_textos(rgb, k, grade)
    limpa = cv2.inpaint(rgb, alvo.astype(np.uint8) * 255, max(3, int(3 * k)), cv2.INPAINT_TELEA)
    if os.environ.get("VV_DEBUG"):
        np.savez_compressed(os.environ["VV_DEBUG"], limpa=limpa, alvo=alvo)

    camadas = {}
    for estilo, pares in PALETAS.items():
        img = aplicar(limpa, tabela(pares))
        # sob os textos apagados, a cor reconstruída vira o tom mais próximo da paleta (sem borrão)
        duro = cv2.medianBlur(aplicar(limpa, tabela(pares, dura=True)), 3)
        img[alvo] = duro[alvo]
        camadas[estilo] = [salvar(img, f"leonida-{estilo}-2048.webp", 2048)]
        if w > 2300:
            camadas[estilo].append(salvar(img, f"leonida-{estilo}.webp", min(4096, w)))
        else:
            camadas[estilo].append(salvar(img, f"leonida-{estilo}.webp", w))

    gx, gy, cel = grade[0] / k, grade[1] / k, grade[2] / k
    INFO.write_text(json.dumps({
        "largura": W, "altura": H, "origem": origem, "fonte": "oficial",
        "recorte": [x0, y0, x1, y1], "imagem": [rgb0.shape[1], rgb0.shape[0]],
        "milha": round(cel, 2),
        "mar": {e: "#%02X%02X%02X" % p[0][1] for e, p in PALETAS.items()},
        "camadas": camadas,
        "grade": {"colunas": COLUNAS, "linhas": LINHAS, "celula_x": round(cel, 3), "celula_y": round(cel, 3),
                  "origem_x": round(gx, 2), "origem_y": round(gy, 2), "formato": "linha-coluna"}}, indent=2),
        encoding="utf-8")
    print(f"\nmapa/leonida.json ({W}×{H}). Agora: python mapa/poster_site.py && python montar.py")


if __name__ == "__main__":
    main()
