#!/usr/bin/env python3
"""
VICEVERSA — mapa de Leonida redesenhado a partir do mapa oficial da Rockstar
=============================================================================

Base: o pôster oficial "Visit Leonida" que a Rockstar liberou de graça no
lançamento (19/11/2026), em rockstargames.com/VI/media → Artwork →
"Leonida Map - Printable". Coloque o JPG em mapa/base/ (a versão de 5775 px
dá o máximo de detalhe; a de 1882 px também funciona).

A arte da Rockstar NÃO vai para o site. O script lê as cores do pôster e
redesenha tudo em vetor, no estilo do VICEVERSA:

  1. acha a moldura do mapa e tira a legenda, a rosa dos ventos, o selo,
     o título, a grade e os textos (os nomes são desenhados pelo site, nos
     três idiomas, a partir de mapa/pontos.json);
  2. classifica cada pixel: mar, lago/pântano, terra, relevo, campo, areia,
     cidade, prédio, pista de aeroporto, via e ferrovia;
  3. vetoriza cada camada e redesenha as vias como linhas centrais,
     separadas em rodovias, avenidas, ruas e vielas pela largura;
  4. grava mapa/leonida.svg (sem cores: o site pinta pela classe) e
     mapa/leonida.json (tamanho e grade, igual à do pôster: A–M × 1–9).

Uso:
    pip install opencv-python-headless numpy scikit-image sknw networkx
    python mapa/recriar_oficial.py
    python mapa/gerar_previa.py
    python montar.py
"""

import json
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("Faltam bibliotecas. Rode:  pip install opencv-python-headless numpy scikit-image sknw networkx")

PASTA = Path(__file__).parent
BASE = PASTA / "base"
SAIDA = PASTA / "leonida.svg"
INFO = PASTA / "leonida.json"
PONTOS = PASTA / "pontos.json"

COLUNAS, LINHAS = 9, 13          # grade do pôster: colunas 1–9, linhas A–M
MILHA = 1 / 9                    # cada coluna da grade tem 1 milha (escala do pôster: 2 pol = 1 milha)
REF = 1755                       # largura da moldura no pôster de 1882 px: as medidas abaixo usam essa escala

# áreas decorativas do pôster, em frações da moldura (x0, y0, x1, y1): viram mar
DECORACOES = [
    (0.050, 0.028, 0.208, 0.172),   # Visit Leonida + legenda
    (0.095, 0.680, 0.190, 0.752),   # rosa dos ventos
    (0.680, 0.775, 0.960, 0.958),   # selo e "The Great State of Leonida"
]


# rodovias numeradas: pontos por onde cada uma passa (px da moldura de referência, em
# geral a própria placa do pôster). O traçado entre eles segue as vias do mapa, pelo
# caminho mais curto que prefere as faixas mais largas.
ROTAS = {
    "interstate": [
        # I-404: Draper Island → Port Gellhorn → sul de Kelly County → Vice City
        [(470, 668), (520, 700), (505, 760), (530, 840), (553, 912), (551, 1000), (548, 1100), (553, 1205),
         (600, 1245), (645, 1268), (700, 1280), (768, 1282), (836, 1284), (900, 1287), (1000, 1295), (1105, 1292)],
        # I-297: Draper Island → Lummox / Kelly → Millport
        [(470, 668), (555, 662), (610, 648), (690, 642), (723, 639), (768, 625), (814, 607), (859, 600),
         (925, 603), (971, 608), (1005, 621), (1039, 621), (1071, 591), (1107, 571), (1134, 564), (1162, 562),
         (1198, 564), (1230, 573), (1257, 591)],
        # I-97: Millport → Waning Sands → Vice City → Southside
        [(1198, 560), (1255, 618), (1291, 684), (1309, 759), (1323, 805), (1336, 850), (1343, 914), (1332, 957),
         (1314, 994), (1286, 1030), (1268, 1062), (1259, 1089), (1250, 1121), (1232, 1153), (1218, 1180),
         (1209, 1216), (1205, 1253), (1202, 1289), (1198, 1330), (1198, 1368), (1175, 1427), (1157, 1464),
         (1155, 1482), (1148, 1518), (1135, 1564), (1112, 1609), (1094, 1636)],
        # I-397: I-97 → Port Vice City
        [(1198, 1368), (1255, 1370), (1330, 1377), (1420, 1378)],
    ],
    "us": [
        # US-35: Ambrosia → Vice City; e depois Southside → Hamlet → Key Lento
        [(988, 625), (985, 694), (975, 760), (973, 860), (973, 953), (975, 1100), (973, 1200), (973, 1259), (990, 1290)],
        [(1094, 1636), (1030, 1708), (1016, 1776), (1016, 1845), (1030, 1895), (1053, 1935), (1071, 1967), (1080, 2004)],
        # US-183: Kelly County → Capri
        [(686, 905), (705, 942), (723, 996), (732, 1051), (729, 1094), (718, 1160), (686, 1196), (640, 1225),
         (600, 1250), (560, 1285), (530, 1314)],
        # US-82: Capri → Big Pine → Grassrivers
        [(530, 1314), (536, 1350), (555, 1400), (586, 1445), (632, 1477), (677, 1500), (691, 1505), (745, 1509),
         (791, 1527), (836, 1564), (900, 1600)],
        # US-628: I-297 → Grayson → Moreau → Millport
        [(700, 625), (700, 560), (718, 512), (768, 466), (814, 439), (859, 421), (900, 412), (971, 375),
         (1039, 371), (1100, 375), (1145, 416), (1164, 466), (1170, 520)],
        # County Road 62: Gellhorn → Kelly County → Belville
        [(602, 996), (645, 937), (686, 905), (723, 896), (768, 896), (814, 910), (859, 933), (900, 955),
         (973, 983), (1044, 983), (1107, 978), (1198, 970), (1330, 969)],
        # State Route 1A: Corsair Key (pedágio) → Key Lento → Keys → Southwind
        [(1250, 1700), (1234, 1722), (1207, 1776), (1175, 1845), (1134, 1913), (1107, 1940), (1080, 2004),
         (1050, 2012), (1000, 2062), (937, 2112), (887, 2156), (865, 2181), (812, 2206), (762, 2206),
         (706, 2200), (650, 2181), (581, 2169), (537, 2162)],
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
    img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Não consegui ler {caminho.name}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB), caminho.name


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


def tapar(m, maximo):
    return ~limpar(~m, maximo)


def morf(m, op, k, forma=cv2.MORPH_ELLIPSE):
    k = max(1, int(round(k)))
    return cv2.morphologyEx(m.astype(np.uint8), op, cv2.getStructuringElement(forma, (k, k))) > 0


def media_mascarada(v, m, sigma):
    m = m.astype(np.float32)
    num = cv2.GaussianBlur(v.astype(np.float32) * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


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
    V, S = hsv[..., 2], hsv[..., 1]
    claro = (V > 185) & (S < 125)
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
        else:
            janela = max(3, int((21 if r.get("tipo") in ("condado", "cidade") else 11) * k) | 1)
            fundo = cv2.medianBlur(V[y0:y1, x0:x1].astype(np.uint8), janela).astype(np.float32)
            letra = (V[y0:y1, x0:x1] > 226) & (S[y0:y1, x0:x1] < 95)   # creme, branco ou lilás (não areia nem água rasa)
            texto = letra | (caixa < fundo - 22)              # letra clara + contorno/sombra escuros
        juntas = cv2.dilate(texto.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(2 * k)))
        n, lab, _, _ = cv2.connectedComponentsWithStats(juntas, 8)
        nucleo = np.zeros_like(juntas, bool)
        nucleo[max(0, cy0 - y0):max(0, cy1 - y0), max(0, cx0 - x0):max(0, cx1 - x0)] = True
        ok = np.zeros(n, bool)
        ok[np.unique(lab[nucleo & (juntas > 0)])] = True
        ok[0] = False
        sel = ok[lab]
        if r.get("tipo") in ("condado", "cidade"):
            alvo[y0:y1, x0:x1] |= sel                   # nome grande: a mancha toda (contorno incluído)
        else:
            alvo[y0:y1, x0:x1] |= sel & cv2.dilate(texto.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    for e in dados.get("escudos", []):
        x, y = e["x"] * w, e["y"] * h
        r = (20 if e.get("tipo") in ("interstate", "estadual", "pedagio") else 17) * k
        alvo[max(0, int(y - r)):int(y + r), max(0, int(x - r)):int(x + r)] = True
    # grade do pôster: a faixa inteira em volta de cada linha (no mar ela é azul-clara, não branca)
    ox, oy, passo = grade or (0.0, 0.0, w / COLUNAS)
    m = int(round(1.6 * k)) + 1
    for i in range(1, COLUNAS):
        x = int(round(ox + i * passo))
        alvo[:, max(0, x - m):x + m + 1] = True
    for j in range(0, LINHAS + 1):
        y = int(round(oy + j * passo))
        if 0 <= y < h:
            alvo[max(0, y - m):y + m + 1] = True
    return cv2.dilate(alvo.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(1, int(round(k)))) > 0


def apagar_decoracoes(rgb):
    h, w = rgb.shape[:2]
    out = rgb.copy()
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mar = (hsv[..., 0] > 84) & (hsv[..., 0] < 102) & (hsv[..., 1] > 150)
    cor = np.median(rgb[mar], 0).astype(np.uint8) if mar.any() else np.array([0, 174, 202], np.uint8)
    for x0, y0, x1, y1 in DECORACOES:
        out[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = cor
    return out


# ── vetorização ─────────────────────────────────────────────────────
ESCALA = 2


def vetorizar(m, k, suave=1.0, epsilon=0.5, minimo=4.0, casas=1):
    """Máscara → atributo d (com furos), em px da moldura do pôster de referência (1755)."""
    f = ESCALA
    grande = cv2.resize(m.astype(np.float32), None, fx=f, fy=f, interpolation=cv2.INTER_LINEAR)
    if suave > 0:
        grande = cv2.GaussianBlur(grande, (0, 0), suave * f * k / 2)
    binaria = (grande > 0.5).astype(np.uint8)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    esc = 1 / (f * k)
    partes = []
    for c in contornos:
        if abs(cv2.contourArea(c)) * esc * esc < minimo:
            continue
        c = cv2.approxPolyDP(c, epsilon * f * k, True)
        if len(c) < 3:
            continue
        pts = c[:, 0, :] * esc
        partes.append("M" + "L".join(f"{x:.{casas}f},{y:.{casas}f}" for x, y in pts) + "Z")
    return "".join(partes)


def suavizar(pts, voltas=2):
    for _ in range(voltas):
        if len(pts) < 3:
            return pts
        novo = [pts[0]]
        for a, b in zip(pts[:-1], pts[1:]):
            novo.append(0.75 * a + 0.25 * b)
            novo.append(0.25 * a + 0.75 * b)
        novo.append(pts[-1])
        pts = np.array(novo)
    return pts


def linhas_centrais(m, k, meia, classes, minimo, casas=2, epsilon=0.35):
    """Máscara de vias → {classe: d}, separando pela meia-largura média de cada trecho.

    classes: lista (nome, meia_largura_minima) da maior para a menor."""
    from skimage.morphology import skeletonize
    import sknw
    esq = skeletonize(m)
    grafo = sknw.build_sknw(esq.astype(np.uint16), multi=True)
    saida = {nome: [] for nome, _ in classes}
    esc = 1 / k
    for s, e, chave in grafo.edges(keys=True):
        pts = grafo[s][e][chave]["pts"]
        if len(pts) < 2:
            continue
        a = np.vstack([grafo.nodes[s]["o"], pts, grafo.nodes[e]["o"]]).astype(np.float32)
        comprimento = float(np.sum(np.hypot(*np.diff(a, axis=0).T)))
        if comprimento < minimo * k and (grafo.degree(s) == 1 or grafo.degree(e) == 1):
            continue                                # espora curta (resto de texto ou ruído)
        yy = np.clip(a[:, 0].astype(int), 0, meia.shape[0] - 1)
        xx = np.clip(a[:, 1].astype(int), 0, meia.shape[1] - 1)
        largura = float(np.median(meia[yy, xx])) / k
        c = cv2.approxPolyDP(a[:, ::-1].reshape(-1, 1, 2), epsilon * k, False)[:, 0, :]
        c = suavizar(c.astype(np.float32)) * esc
        d = "M" + "L".join(f"{x:.{casas}f},{y:.{casas}f}" for x, y in c)
        for nome, minima in classes:
            if largura >= minima:
                saida[nome].append(d)
                break
    return {n: "".join(v) for n, v in saida.items()}


def tracar_rotas(vias, meia, k, casas=2):
    """Rodovias numeradas (ROTAS): cada trecho entre dois pontos vizinhos segue as vias
    do mapa por um corredor estreito em volta da reta entre eles (caminho mais curto
    que prefere faixas largas). Sem via no corredor, liga em linha reta.
    Devolve {tipo: d} e a máscara dos pixels usados."""
    from skimage.morphology import skeletonize
    import sknw
    import networkx as nx
    esq = skeletonize(vias)
    g = sknw.build_sknw(esq.astype(np.uint16), multi=False)
    ids = list(g.nodes())
    nos = np.array([g.nodes[n]["o"] for n in ids], np.float32) if ids else np.zeros((0, 2), np.float32)
    for s, e in g.edges():
        pts = g[s][e]["pts"]
        yy = np.clip(pts[:, 0], 0, meia.shape[0] - 1); xx = np.clip(pts[:, 1], 0, meia.shape[1] - 1)
        largura = max(0.5, float(np.median(meia[yy, xx])) / k)
        g[s][e]["peso"] = g[s][e]["weight"] / (largura ** 2)
    usados = np.zeros(vias.shape, bool)
    saida = {}
    corredor = 9 * k

    def trecho(p0, p1):
        a_ = np.array([p0[1] * k, p0[0] * k], np.float32)    # (y, x) em px da imagem
        b_ = np.array([p1[1] * k, p1[0] * k], np.float32)
        reta = np.linspace(a_, b_, max(2, int(np.hypot(*(b_ - a_)) / 2)))
        if not len(ids):
            return reta
        ab = b_ - a_
        t_ = np.clip(((nos - a_) @ ab) / max(1e-6, ab @ ab), 0, 1)
        dist = np.hypot(*(nos - (a_ + t_[:, None] * ab)).T)
        perto = [ids[i] for i in np.where(dist <= corredor)[0]]
        if len(perto) < 2:
            return reta
        sub = g.subgraph(perto)
        pp = np.array([g.nodes[n]["o"] for n in perto], np.float32)
        ini = perto[int(np.hypot(*(pp - a_).T).argmin())]
        fim = perto[int(np.hypot(*(pp - b_).T).argmin())]
        if np.hypot(*(g.nodes[ini]["o"] - a_)) > corredor or np.hypot(*(g.nodes[fim]["o"] - b_)) > corredor:
            return reta
        try:
            cam = nx.shortest_path(sub, ini, fim, weight="peso")
        except nx.NetworkXNoPath:
            return reta
        partes = [a_[None]]
        for s, e in zip(cam[:-1], cam[1:]):
            pts = g[s][e]["pts"].astype(np.float32)
            if np.hypot(*(pts[0] - g.nodes[s]["o"])) > np.hypot(*(pts[-1] - g.nodes[s]["o"])):
                pts = pts[::-1]
            partes.append(np.vstack([g.nodes[s]["o"], pts]))
        partes.append(b_[None])
        caminho = np.vstack(partes)
        # o caminho não pode ser muito mais longo que a reta (desvio por ruas laterais)
        comp = float(np.sum(np.hypot(*np.diff(caminho, axis=0).T)))
        if comp > 1.6 * np.hypot(*(b_ - a_)) + 6 * k:
            return reta
        return caminho

    for tipo, rotas in ROTAS.items():
        partes = []
        for rota in rotas:
            arr = np.vstack([trecho(p0, p1) for p0, p1 in zip(rota[:-1], rota[1:])]).astype(np.float32)
            usados[np.clip(arr[:, 0].astype(int), 0, vias.shape[0] - 1),
                   np.clip(arr[:, 1].astype(int), 0, vias.shape[1] - 1)] = True
            c = cv2.approxPolyDP(arr[:, ::-1].reshape(-1, 1, 2), 0.5 * k, False)[:, 0, :]
            c = suavizar(c.astype(np.float32)) / k
            partes.append("M" + "L".join(f"{x:.{casas}f},{y:.{casas}f}" for x, y in c))
        saida[tipo] = "".join(partes)
    usados = cv2.dilate(usados.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=max(2, int(2.5 * k))) > 0
    return saida, usados


# ── principal ───────────────────────────────────────────────────────
def main():
    rgb0, origem = carregar()
    x0, y0, x1, y1 = moldura(rgb0)
    rgb = rgb0[y0:y1, x0:x1].copy()
    h, w = rgb.shape[:2]
    k = w / REF
    W, H = REF, round(h / k, 1)                    # o SVG usa sempre a escala de referência
    print(f"Base: {origem} · moldura {w}×{h} px (escala {k:.2f})")

    rgb = apagar_decoracoes(rgb)
    grade = achar_grade(rgb)
    print("Grade: coluna 1 em x=%.1f, linha A em y=%.1f, célula %.1f px" % grade)
    alvo = mascara_textos(rgb, k, grade)
    limpa = cv2.inpaint(rgb, alvo.astype(np.uint8) * 255, max(3, int(3 * k)), cv2.INPAINT_TELEA)
    a = lambda px: max(2, int(px * k * k))         # área mínima, escalada

    hsv = cv2.cvtColor(limpa, cv2.COLOR_RGB2HSV).astype(np.int16)
    Hh, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lab = cv2.cvtColor(limpa, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[..., 0]

    # ── água: ciano saturado (mar, lagos, rios e canais do pântano) ──
    agua = (Hh >= 90) & (Hh <= 101) & ((S >= 120) | ((S >= 70) & (V >= 200))) & (V >= 110)
    agua = morf(agua, cv2.MORPH_OPEN, 2 * k)
    terra = limpar(tapar(~agua, a(30)), a(12))
    agua = ~terra
    mar = limpar(agua, a(20000))                   # o mar é a grande massa de água ligada às bordas
    lago = agua & ~mar

    # profundidade: o mar é mais claro perto da costa
    claridade = media_mascarada(V, mar, 6 * k)
    dist_costa = cv2.distanceTransform(mar.astype(np.uint8), cv2.DIST_L2, 5) / k
    raso1 = mar & ((claridade >= 222) | (dist_costa < 7))
    raso2 = mar & ((claridade >= 212) | (dist_costa < 22))
    raso3 = mar & ((claridade >= 205) | (dist_costa < 55))

    # ── vias: linhas claras e sem cor, mais claras que o entorno ──
    tam = max(5, int(round(9 * k)) | 1)
    topo = cv2.morphologyEx(L, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tam, tam)))
    branco = (V >= 205) & (S <= 45)
    via = (branco & (topo > 10)) | ((V >= 238) & (S <= 30))
    via &= terra | morf(terra, cv2.MORPH_DILATE, 3 * k)       # pontes entram um pouco na água

    # pistas de aeroporto e pátios: manchas claras largas (não são linhas)
    largas = morf(via, cv2.MORPH_OPEN, 7 * k)
    pista = limpar(largas, a(120)) & terra

    # ferrovias: traço vermelho-escuro fino
    ferro = (((Hh <= 15) | (Hh >= 150)) & (S >= 25) & (V >= 80) & (V <= 175)) & terra
    ferro = limpar(morf(ferro, cv2.MORPH_CLOSE, 2 * k), a(40))

    # ── cidade: cinza azulado, pouca saturação ──
    cinza = (S <= 55) & ((Hh >= 88) | (S <= 25)) & (V >= 120) & (V < 238) & terra & ~agua
    urbana = morf(morf(cinza | via & morf(cinza, cv2.MORPH_DILATE, 4 * k), cv2.MORPH_CLOSE, 5 * k), cv2.MORPH_OPEN, 4 * k)
    urbana = tapar(limpar(urbana, a(260)), a(120)) & terra
    # quarteirões: na cidade, as ruas são cinza-claro e os quarteirões, cinza-azulados;
    # pintar os quarteirões deixa a malha de ruas visível mesmo onde a linha central falha
    quadra = urbana & ~via & ((V < 214) | (S > 24))
    quadra = limpar(morf(quadra, cv2.MORPH_OPEN, max(1, 1.1 * k)), a(3))
    # prédios: telhados azulados, mais escuros que o quarteirão
    predio = quadra & (S >= 45) & (V < 200)
    predio = limpar(morf(predio, cv2.MORPH_OPEN, max(1, 1.2 * k)), a(3))

    # ── areia (praias) e campo (pedreiras, campos de golfe, áreas agrícolas) ──
    areia = (Hh >= 8) & (Hh <= 30) & (S >= 35) & (S <= 140) & (V >= 145) & terra
    areia = limpar(morf(areia, cv2.MORPH_OPEN, 2 * k), a(10))
    campo = (Hh >= 25) & (Hh <= 45) & (S >= 55) & (V >= 80) & (V < 200) & terra & ~areia
    campo = limpar(morf(morf(campo, cv2.MORPH_CLOSE, 3 * k), cv2.MORPH_OPEN, 4 * k), a(400))

    # ── relevo: o sombreado do verde (mais escuro = mais alto / mata) ──
    verde = terra & ~urbana & ~areia & ~agua
    base_verde = verde & (Hh >= 45) & (Hh <= 92)
    relevo = media_mascarada(V, base_verde, 3 * k)
    p35, p15, p5 = np.percentile(relevo[base_verde], [35, 15, 5]) if base_verde.any() else (0, 0, 0)
    colina = verde & (relevo <= p35)
    floresta = verde & (relevo <= p15)
    serra = verde & (relevo <= p5)
    colina = limpar(morf(colina, cv2.MORPH_OPEN, 3 * k), a(60))
    floresta = limpar(morf(floresta, cv2.MORPH_OPEN, 3 * k), a(60))
    serra = limpar(morf(serra, cv2.MORPH_OPEN, 3 * k), a(60))

    # ── vias finais ──
    vias = via & ~pista
    vias = limpar(morf(vias, cv2.MORPH_CLOSE, max(2, 1.5 * k), cv2.MORPH_RECT), a(10))
    meia = cv2.distanceTransform(vias.astype(np.uint8), cv2.DIST_L2, 5)

    camadas = [
        ("raso3", raso3, dict(suave=6, epsilon=1.2, minimo=60)),
        ("raso2", raso2, dict(suave=4, epsilon=1.0, minimo=30)),
        ("raso1", raso1, dict(suave=2.5, epsilon=0.7, minimo=10)),
        ("terra", terra, dict(suave=1.0, epsilon=0.35, minimo=1.5)),
        ("colina", colina, dict(suave=3, epsilon=0.9, minimo=40)),
        ("floresta", floresta, dict(suave=3, epsilon=0.9, minimo=40)),
        ("serra", serra, dict(suave=3, epsilon=0.9, minimo=40)),
        ("campo", campo, dict(suave=1.5, epsilon=0.6, minimo=20)),
        ("areia", areia, dict(suave=1.0, epsilon=0.4, minimo=2)),
        ("urbana", urbana, dict(suave=1.2, epsilon=0.5, minimo=20)),
        ("quadra", quadra, dict(suave=0.5, epsilon=0.35, minimo=0.8)),
        ("predio", predio, dict(suave=0.4, epsilon=0.35, minimo=0.6)),
        ("pista", pista, dict(suave=0.6, epsilon=0.4, minimo=6)),
        ("lago", lago, dict(suave=1.0, epsilon=0.4, minimo=1.5)),
    ]
    paths = []
    for nome, m, opc in camadas:
        d = vetorizar(m, k, **opc)
        paths.append(f'<path class="c-{nome}" fill-rule="evenodd" d="{d}"/>')
        print(f"  {nome:10s} {len(d) / 1024:8.1f} KB")

    # faixas brancas largas (rodovias e avenidas): branco forte com meia-largura ≥ 1,3 px de referência
    forte = vias & (V >= 226) & (S <= 38)
    nucleo = cv2.distanceTransform(forte.astype(np.uint8), cv2.DIST_L2, 5) >= 1.3 * k
    largas_vias = forte & morf(nucleo, cv2.MORPH_DILATE, 2.2 * k)
    largas_vias = limpar(morf(largas_vias, cv2.MORPH_CLOSE, 2 * k), a(30)) & ~pista
    meia_l = cv2.distanceTransform(largas_vias.astype(np.uint8), cv2.DIST_L2, 5)
    # rodovias numeradas: seguem as vias do mapa pelos pontos de ROTAS (placas do pôster)
    rotas, usados = tracar_rotas(vias, meia + largas_vias * 1.5 * k, k)
    resto = vias & ~usados
    tracos = linhas_centrais(resto, k, meia + (largas_vias & ~usados) * 2 * k,
                             [("vias", 1.6), ("ruas", 1.0), ("vielas", 0)], minimo=6)
    tracos["vias-largas"] = rotas.get("interstate", "")
    tracos["rotas"] = rotas.get("us", "")
    for classe in ("vielas", "ruas", "vias", "rotas", "vias-largas"):
        d = tracos[classe]
        paths.append(f'<path class="l-{classe}" fill="none" vector-effect="non-scaling-stroke" '
                     f'stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')
        print(f"  {classe:11s} {len(d) / 1024:8.1f} KB")
    trilhos = linhas_centrais(ferro, k, cv2.distanceTransform(ferro.astype(np.uint8), cv2.DIST_L2, 5),
                              [("ferrovia", 0)], minimo=10)["ferrovia"]
    paths.append(f'<path class="l-ferrovia" fill="none" vector-effect="non-scaling-stroke" d="{trilhos}"/>')
    print(f"  {'ferrovia':11s} {len(trilhos) / 1024:8.1f} KB")

    # grade do pôster (A–M nas linhas, 1–9 nas colunas; células quadradas de 1 milha)
    gx, gy, cel = grade[0] / k, grade[1] / k, grade[2] / k
    g = ['<g class="grade">']
    d = "".join(f"M{gx + i * cel:.1f},0V{H}" for i in range(1, COLUNAS))
    d += "".join(f"M0,{gy + j * cel:.1f}H{W}" for j in range(LINHAS + 1) if 0 < gy + j * cel < H)
    g.append(f'<path fill="none" vector-effect="non-scaling-stroke" d="{d}"/>')
    for i in range(COLUNAS):
        for j in range(LINHAS):
            ty = max(gy + j * cel, 0) + 16
            if ty < H:
                g.append(f'<text x="{gx + i * cel + 5:.1f}" y="{ty:.1f}">{chr(65 + j)}{i + 1}</text>')
    g.append("</g>")
    paths.append("".join(g))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'data-origem="{origem}" shape-rendering="geometricPrecision">\n'
           f'<rect class="c-mar" width="{W}" height="{H}"/>\n' + "\n".join(paths) + "\n</svg>\n")
    SAIDA.write_text(svg, encoding="utf-8")
    INFO.write_text(json.dumps({
        "largura": W, "altura": H, "origem": origem, "fonte": "oficial",
        "recorte": [x0, y0, x1, y1], "imagem": [rgb0.shape[1], rgb0.shape[0]],
        "milha": round(cel, 2),
        "grade": {"colunas": COLUNAS, "linhas": LINHAS, "celula_x": round(cel, 3), "celula_y": round(cel, 3),
                  "origem_x": round(gx, 2), "origem_y": round(gy, 2), "formato": "linha-coluna"}}, indent=2), encoding="utf-8")
    print(f"\nmapa/leonida.svg: {len(svg) / 1024:.0f} KB ({W}×{H}). Agora: python mapa/gerar_previa.py && python montar.py")


if __name__ == "__main__":
    main()
