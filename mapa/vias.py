"""
VICEVERSA — extração de ruas e estradas do mapa-base, com precisão de subpixel
==============================================================================

Usado pelo recriar_mapa.py. Em vez de "afinar" uma máscara grosseira (o que
deixava ruas tortas, laços dentro dos quarteirões e cruzamentos soltos), aqui:

1. A imagem é ampliada (U vezes) e cada pixel recebe uma nota de "tinta de via":
   escuro em relação ao entorno, cinzento (sem cor) e escuro em termos absolutos.
   Isso separa as vias de prédios (cinza claro), da costa (azul) e do mato (verde).
2. As linhas da grade do original são "costuradas" (a nota é refeita a partir
   dos lados), e os textos (letras brancas com contorno escuro) são anulados.
3. Limiar com histerese: um trecho fraco só entra se estiver ligado a um forte.
4. A máscara vira um grafo (linha central de 1/U de pixel, cruzamentos como nós);
   pontas soltas curtas são podadas, buracos pequenos ligados e componentes
   minúsculos (sujeira, letras) descartados.
5. Cada trecho é suavizado com as pontas presas no cruzamento — as ruas que se
   cruzam continuam se encontrando exatamente no mesmo ponto.
6. Cada trecho é classificado pela largura e pelo contraste no original:
   rodovia, avenida/estrada, rua e viela.
"""

import cv2
import numpy as np

try:
    import networkx as nx
    import sknw
except ImportError:                       # pragma: no cover
    nx = sknw = None

U = 3                                    # ampliação de trabalho (1/3 de pixel)


# ── nota de tinta ──────────────────────────────────────────────────
TINTA = np.array([72, 78, 62], np.float32)       # cinza-oliva das vias no original


def tinta(rgb, u, tol=0.30):
    """Quanto de cada pixel é 'tinta de via' misturada ao fundo local (0..1).

    Cada pixel é tratado como mistura de duas cores: o fundo ao redor (estimado
    com um fechamento morfológico) e a tinta das vias. A fração de tinta é a
    projeção do pixel na reta fundo→tinta; se o pixel fica longe dessa reta
    (água, costa, mato de outra cor), ele não é via.
    """
    p = rgb.astype(np.float32)
    disco = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(7 * u) | 1,) * 2)
    bg = np.stack([cv2.morphologyEx(p[..., i], cv2.MORPH_CLOSE, disco) for i in range(3)], -1)
    v = bg - TINTA
    n2 = np.maximum((v * v).sum(-1), 400.0)
    dpx = bg - p
    a = (dpx * v).sum(-1) / n2
    res = dpx - a[..., None] * v
    r = np.sqrt((res * res).sum(-1) / n2)
    return np.clip(a, 0, 1) * np.clip(1 - r / tol, 0, 1)


def costurar_grade(T, linhas_x, linhas_y, u):
    """Refaz a nota sobre as linhas da grade a partir dos dois lados da linha."""
    T = T.copy()
    d = int(round(2 * u))
    for x in linhas_x:
        a, b = int(round(x * u - 1.5 * u)), int(round(x * u + 1.5 * u))
        a, b = max(d, a), min(T.shape[1] - d - 1, b)
        if b <= a:
            continue
        lado = np.minimum(T[:, a - d], T[:, b + d])
        T[:, a:b + 1] = lado[:, None]
    for y in linhas_y:
        a, b = int(round(y * u - 1.5 * u)), int(round(y * u + 1.5 * u))
        a, b = max(d, a), min(T.shape[0] - d - 1, b)
        if b <= a:
            continue
        lado = np.minimum(T[a - d], T[b + d])
        T[a:b + 1] = lado[None, :]
    return T


def mascara_textos(rgb_1x):
    """Letras dos rótulos: brancas (ou vermelhas) com contorno escuro."""
    hsv = cv2.cvtColor(rgb_1x, cv2.COLOR_RGB2HSV).astype(np.int32)
    branco = rgb_1x.min(2) > 226
    vermelho = (rgb_1x[..., 0] > 150) & (rgb_1x[..., 1] < 130) & (rgb_1x[..., 2] < 140) & (hsv[..., 1] > 90)
    m = (branco | vermelho).astype(np.uint8)
    # texto = muitas manchinhas brancas juntas; isolado (faixa de rodovia) não conta
    densidade = cv2.blur(m.astype(np.float32), (7, 7))
    texto = (m > 0) & (densidade > 0.12)
    return cv2.dilate(texto.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0


def limpar(mascara, minimo):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), 8)
    manter = np.zeros(n, bool)
    manter[1:] = stats[1:, cv2.CC_STAT_AREA] >= minimo
    return manter[lab]


def tapar_furos(mascara, maximo):
    n, lab, stats, _ = cv2.connectedComponentsWithStats((~mascara).astype(np.uint8), 4)
    furo = np.zeros(n, bool)
    furo[1:] = stats[1:, cv2.CC_STAT_AREA] < maximo
    return mascara | furo[lab]


def pontes_tracejadas(Tb, u, k):
    """Pontes sobre a água aparecem tracejadas: liga os traços alinhados."""
    tracos = (Tb > 0.13).astype(np.uint8)
    L = int(round(7 * u * k)) | 1
    unido = np.zeros_like(tracos)
    for ang in range(0, 180, 12):
        se = np.zeros((L, L), np.uint8)
        c = L // 2
        dx, dy = np.cos(np.radians(ang)) * c, np.sin(np.radians(ang)) * c
        cv2.line(se, (int(round(c - dx)), int(round(c - dy))), (int(round(c + dx)), int(round(c + dy))), 1, 1)
        unido |= cv2.morphologyEx(tracos, cv2.MORPH_CLOSE, se)
    n, lab, st, _ = cv2.connectedComponentsWithStats(unido, 8)
    manter = np.zeros(n, bool)
    for i in range(1, n):
        comp = lab == i if st[i, cv2.CC_STAT_AREA] < 4000 * u * u else None
        ys, xs = np.nonzero(lab[st[i, 1]:st[i, 1] + st[i, 3], st[i, 0]:st[i, 0] + st[i, 2]] == i)
        if len(xs) < 10:
            continue
        cov = np.cov(np.vstack([xs, ys]))
        ev = np.sort(np.linalg.eigvalsh(cov))
        comprido = 4 * np.sqrt(max(ev[1], 0))           # ~ comprimento
        fino = 4 * np.sqrt(max(ev[0], 0))
        manter[i] = comprido >= 10 * u * k and comprido >= 4 * fino
    return manter[lab]


def pistas_de_pouso(mascara, u, k):
    """Faixas largas, retas e compridas (pistas de aeroporto): não são vias."""
    d = int(round(4.6 * u * k)) | 1
    grosso = cv2.morphologyEx(mascara.astype(np.uint8), cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(grosso, 8)
    pista = np.zeros(mascara.shape, bool)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < 60 * u * u * k * k:
            continue
        ys, xs = np.nonzero(lab == i)
        (cx, cy), (w, h), ang = cv2.minAreaRect(np.column_stack([xs, ys]).astype(np.float32))
        longo, curto = max(w, h), max(1.0, min(w, h))
        if longo >= 25 * u * k and longo / curto >= 4 and st[i, cv2.CC_STAT_AREA] / (w * h + 1) >= 0.7:
            pista |= lab == i
    return cv2.dilate(pista.astype(np.uint8), np.ones((int(3 * u) | 1,) * 2, np.uint8)) > 0


# ── grafo ──────────────────────────────────────────────────────────
def _comprimento(pts):
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) if len(pts) > 1 else 0.0


def montar_grafo(mascara):
    from skimage.morphology import skeletonize
    esq = skeletonize(mascara)
    g = sknw.build_sknw(esq.astype(np.uint16), multi=True, iso=False, ring=True)
    for s, e, k in g.edges(keys=True):
        pts = g[s][e][k]["pts"].astype(np.float32)
        # liga o trecho exatamente aos centros dos nós
        a, b = g.nodes[s]["o"].astype(np.float32), g.nodes[e]["o"].astype(np.float32)
        if len(pts) and np.linalg.norm(pts[0] - a) > np.linalg.norm(pts[0] - b):
            a, b = b, a
        pts = np.vstack([a, pts, b]) if len(pts) else np.vstack([a, b])
        g[s][e][k]["pts"] = pts
        g[s][e][k]["len"] = _comprimento(pts)
    return g


def podar(g, ponta_max, voltas=4):
    """Remove pontas soltas curtas (rebarbas do afinamento e de prédios colados)."""
    for _ in range(voltas):
        tirar = []
        for s, e, k, d in g.edges(keys=True, data=True):
            gs, ge = g.degree(s), g.degree(e)
            if s != e and min(gs, ge) == 1 and max(gs, ge) >= 3 and d["len"] < ponta_max:
                tirar.append((s, e, k))
        if not tirar:
            break
        for s, e, k in tirar:
            if g.has_edge(s, e, k):
                g.remove_edge(s, e, k)
        g.remove_nodes_from([n for n in list(g.nodes) if g.degree(n) == 0])
        juntar_grau2(g)
    return g


def juntar_grau2(g):
    """Funde trechos encadeados por nós de grau 2 (que não são cruzamentos)."""
    mudou = True
    while mudou:
        mudou = False
        for n in list(g.nodes):
            if n not in g or g.degree(n) != 2:
                continue
            arestas = list(g.edges(n, keys=True, data=True))
            if len(arestas) != 2:
                continue
            (_, a, ka, da), (_, b, kb, db) = arestas
            if a == n or b == n:            # laço
                continue
            pa, pb = da["pts"], db["pts"]
            o = g.nodes[n]["o"]
            if np.linalg.norm(pa[0] - o) < np.linalg.norm(pa[-1] - o):
                pa = pa[::-1]                 # pa termina em n
            if np.linalg.norm(pb[0] - o) > np.linalg.norm(pb[-1] - o):
                pb = pb[::-1]                 # pb começa em n
            pts = np.vstack([pa, pb[1:]])
            g.remove_node(n)
            g.add_edge(a, b, pts=pts, len=_comprimento(pts))
            mudou = True
    return g


def remover_pequenos(g, minimo):
    for comp in list(nx.connected_components(g)):
        total = sum(d["len"] for _, _, d in g.subgraph(comp).edges(data=True))
        if total < minimo:
            g.remove_nodes_from(comp)
    return g


def amostrar(mapa, a, b):
    """Valores de `mapa` ao longo do segmento a→b (coordenadas y, x)."""
    n = max(2, int(np.linalg.norm(b - a)))
    linha = np.linspace(a, b, n)
    yy = np.clip(linha[:, 0].round().astype(int), 0, mapa.shape[0] - 1)
    xx = np.clip(linha[:, 1].round().astype(int), 0, mapa.shape[1] - 1)
    return mapa[yy, xx]


def ligar_pontas(g, u, alcance, cos_min, aceitar, tentativas=6):
    """Liga pontas soltas a outra via à frente, se `aceitar(origem, alvo)` confirmar."""
    pontas = [n for n in g.nodes if g.degree(n) == 1]
    if not pontas:
        return g
    todos, dono = [], []
    for s_, e_, k_, d in g.edges(keys=True, data=True):
        todos.append(d["pts"])
        dono += [(s_, e_, k_)] * len(d["pts"])
    todos = np.vstack(todos)
    from scipy.spatial import cKDTree
    arv = cKDTree(todos)
    novo_id = max(g.nodes) + 1
    for n in pontas:
        if n not in g or g.degree(n) != 1:
            continue
        (_, viz, k, d), = list(g.edges(n, keys=True, data=True))
        pts = d["pts"]
        o = g.nodes[n]["o"].astype(np.float32)
        if np.linalg.norm(pts[0] - o) > np.linalg.norm(pts[-1] - o):
            pts = pts[::-1]
        if len(pts) < 4:
            continue
        direcao = pts[0] - pts[min(len(pts) - 1, int(4 * u))]
        nd = np.linalg.norm(direcao)
        if nd < 1e-3:
            continue
        direcao /= nd
        cand = []
        for i in arv.query_ball_point(o, alcance):
            if dono[i][:2] in ((n, viz), (viz, n)):
                continue
            v = todos[i] - o
            dist = float(np.linalg.norm(v))
            if dist < 1.5 * u:
                continue
            cos = float(v @ direcao) / dist
            if cos >= cos_min:
                cand.append((dist * (2 - cos), i))
        cand.sort()
        escolhido = None
        vistos = set()
        for _, i in cand:
            if dono[i] in vistos:
                continue
            vistos.add(dono[i])
            if aceitar(o, todos[i]):
                escolhido = i
                break
            if len(vistos) >= tentativas:
                break
        if escolhido is None:
            continue
        alvo, (s2, e2, k2) = todos[escolhido], dono[escolhido]
        if not g.has_edge(s2, e2, k2):
            continue
        p2 = g[s2][e2][k2]["pts"]
        j = int(np.argmin(np.linalg.norm(p2 - alvo, axis=1)))
        ini, fim = (s2, e2) if np.linalg.norm(g.nodes[s2]["o"] - p2[0]) <= np.linalg.norm(g.nodes[e2]["o"] - p2[0]) else (e2, s2)
        if j <= 1:
            destino = ini
        elif j >= len(p2) - 2:
            destino = fim
        else:
            destino = novo_id
            novo_id += 1
            g.add_node(destino, o=p2[j].copy())
            g.remove_edge(s2, e2, k2)
            a1, a2 = p2[:j + 1], p2[j:]
            g.add_edge(ini, destino, pts=a1, len=_comprimento(a1))
            g.add_edge(destino, fim, pts=a2, len=_comprimento(a2))
        if destino == n:
            continue
        ponte = np.vstack([o, g.nodes[destino]["o"].astype(np.float32)])
        g.add_edge(n, destino, pts=ponte, len=_comprimento(ponte), ponte=True)
    return g


# ── geometria final ────────────────────────────────────────────────
def suavizar_presa(pts, sigma):
    """Média gaussiana das coordenadas com as duas pontas fixas (espelho ponto-a-ponto)."""
    n = len(pts)
    if n < 4 or sigma <= 0:
        return pts
    r = min(int(3 * sigma), n - 1)
    ini = 2 * pts[0] - pts[r:0:-1]
    fim = 2 * pts[-1] - pts[-2:-r - 2:-1]
    pad = np.vstack([ini, pts, fim])
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    out = np.stack([np.convolve(pad[:, i], k, mode="valid") for i in (0, 1)], 1)
    assert len(out) == n
    out[0], out[-1] = pts[0], pts[-1]
    return out


def simplificar(pts, eps):
    if len(pts) < 3:
        return pts
    c = cv2.approxPolyDP(pts[:, ::-1].reshape(-1, 1, 2).astype(np.float32), eps, False)[:, 0, :]
    return c[:, ::-1]


def caminho_relativo(pts_xy, casas):
    """Polilinha → 'M x,y l dx,dy ...' com coordenadas arredondadas sem acumular erro."""
    q = np.round(pts_xy * 10 ** casas).astype(np.int64)
    keep = np.ones(len(q), bool)
    keep[1:] = np.any(q[1:] != q[:-1], axis=1)
    q = q[keep]
    if len(q) < 2:
        return ""
    f = lambda v: (f"{v / 10 ** casas:.{casas}f}").rstrip("0").rstrip(".") if casas else str(v)

    def par(a, b):
        sb = f(b)
        return f(a) + ("" if sb.startswith("-") else " ") + sb
    partes = ["M" + par(*q[0])]
    d = np.diff(q, axis=0)
    partes.append("l" + " ".join(par(*v) for v in d))
    return "".join(partes)


# ── tracados contínuos (strokes) ───────────────────────────────────
def _tangente(pts, no_xy, passo):
    """Direção de saída do trecho a partir do nó."""
    if np.linalg.norm(pts[0] - no_xy) > np.linalg.norm(pts[-1] - no_xy):
        pts = pts[::-1]
    q = pts[min(len(pts) - 1, passo)] - pts[0]
    n = np.linalg.norm(q)
    return q / n if n > 1e-6 else q


def tracados(g, u, desvio_max=40):
    """Agrupa trechos que seguem 'em frente' nos cruzamentos: cada grupo é uma via."""
    arestas = list(g.edges(keys=True))
    idx = {e: i for i, e in enumerate(arestas)}
    pai = list(range(len(arestas)))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i
    limite = -np.cos(np.radians(desvio_max))
    for n in g.nodes:
        inc = [(s, e, k) if (s, e, k) in idx else (e, s, k) for s, e, k in g.edges(n, keys=True)]
        if len(inc) < 2:
            continue
        o = g.nodes[n]["o"].astype(np.float32)
        tang = {a: _tangente(g.edges[a]["pts"], o, int(4 * u)) for a in inc}
        pares = []
        for i in range(len(inc)):
            for j in range(i + 1, len(inc)):
                c = float(tang[inc[i]] @ tang[inc[j]])        # -1 = seguem em linha reta
                if c <= limite:
                    pares.append((c, inc[i], inc[j]))
        usados = set()
        for c, a1, a2 in sorted(pares):
            if a1 in usados or a2 in usados:
                continue
            usados.update((a1, a2))
            pai[raiz(idx[a1])] = raiz(idx[a2])
    grupos = {}
    for e, i in idx.items():
        grupos.setdefault(raiz(i), []).append(e)
    return list(grupos.values())


def encadear(g, grupo):
    """Ordena os trechos de um traçado em polilinhas contínuas (uma por via)."""
    restantes = {e: g.edges[e]["liso"] for e in grupo}
    cadeias = []

    def tirar_que_toca(ponta):
        for e2, p2 in restantes.items():
            if np.linalg.norm(p2[0] - ponta) < 0.05:
                del restantes[e2]
                return p2                      # começa na ponta
            if np.linalg.norm(p2[-1] - ponta) < 0.05:
                del restantes[e2]
                return p2[::-1]
        return None

    while restantes:
        _, pts = restantes.popitem()
        cadeia = [pts]
        while (prox := tirar_que_toca(cadeia[-1][-1])) is not None:     # para a frente
            cadeia.append(prox[1:])
        while (ant := tirar_que_toca(cadeia[0][0])) is not None:        # para trás
            cadeia.insert(0, ant[::-1][:-1])
        cadeias.append(np.vstack(cadeia))
    return cadeias


# ── principal ──────────────────────────────────────────────────────
def extrair(rgb_1x, urbana_1x, agua_1x, grade_x, grade_y, k=1.0, casas=2, relatorio=None):
    """Retorna dict classe → atributo d do <path> (coordenadas em px do recorte)."""
    if sknw is None:
        raise SystemExit("Faltam bibliotecas. Rode:  pip install sknw networkx scipy scikit-image")
    u = U
    big = cv2.resize(rgb_1x, None, fx=u, fy=u, interpolation=cv2.INTER_CUBIC)
    big = cv2.GaussianBlur(big, (0, 0), 0.35 * u)
    T = tinta(big, u)
    _lab = cv2.cvtColor(big, cv2.COLOR_RGB2LAB).astype(np.float32)
    Cr = np.hypot(_lab[..., 1] - 128, _lab[..., 2] - 128)
    Lmin = cv2.erode(cv2.cvtColor(big, cv2.COLOR_RGB2LAB)[..., 0].astype(np.float32) * 100 / 255,
                     np.ones((int(u) | 1,) * 2, np.uint8))           # tom do miolo da linha
    T = costurar_grade(T, grade_x, grade_y, u)
    texto = cv2.resize(mascara_textos(rgb_1x).astype(np.uint8), (T.shape[1], T.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    T[texto] = 0

    from skimage.filters import apply_hysteresis_threshold
    forte, fraco = 0.5, 0.25
    mascara = apply_hysteresis_threshold(T, fraco, forte)
    agua_u = cv2.resize(agua_1x.astype(np.uint8), (T.shape[1], T.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    Tb = cv2.GaussianBlur(T, (0, 0), 0.6 * u)
    mascara = cv2.morphologyEx(mascara.astype(np.uint8), cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))) > 0
    # furinhos (faixas brancas da rodovia, ruído de JPEG) não viram laços
    mascara = tapar_furos(mascara, int(6 * u * u * k * k))
    mascara = limpar(mascara, int(10 * u * u * k * k))
    meia = cv2.distanceTransform(mascara.astype(np.uint8), cv2.DIST_L2, 5)
    pista = pistas_de_pouso(mascara, u, k)
    fraca = T > 0.12

    g = montar_grafo(mascara)
    juntar_grau2(g)
    podar(g, ponta_max=3.0 * u * k)
    # falhas curtas (texto, grade, JPEG): basta haver algum sinal de via no meio
    g = ligar_pontas(g, u, 4.0 * u * k, 0.8, lambda a, b: amostrar(fraca, a, b).mean() >= 0.5)
    # pontes: a via chega à beira d'água e continua tracejada até a outra margem
    def eh_ponte(a, b):
        na_agua = amostrar(agua_u, a, b)
        sinal = amostrar(Tb, a, b)
        return na_agua.mean() >= 0.35 and (sinal > 0.08).mean() >= 0.78 and sinal.mean() >= 0.17
    g = ligar_pontas(g, u, 70.0 * u * k, 0.94, eh_ponte, tentativas=4)
    juntar_grau2(g)
    podar(g, ponta_max=2.0 * u * k, voltas=2)
    remover_pequenos(g, minimo=9.0 * u * k)

    urb = cv2.resize(urbana_1x.astype(np.uint8), (T.shape[1], T.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    agua = cv2.resize(agua_1x.astype(np.uint8), (T.shape[1], T.shape[0]), interpolation=cv2.INTER_NEAREST) > 0

    # medidas de cada trecho + geometria final (suavizada com as pontas presas nos nós)
    for s_, e_, kk, d in list(g.edges(keys=True, data=True)):
        pts = d["pts"]
        yy = np.clip(pts[:, 0].round().astype(int), 0, T.shape[0] - 1)
        xx = np.clip(pts[:, 1].round().astype(int), 0, T.shape[1] - 1)
        d["largura"] = 2 * float(np.median(meia[yy, xx])) / (u * k)      # px do original
        d["contraste"] = float(np.median(T[yy, xx]))
        d["tom"] = float(np.median(Lmin[yy, xx]))
        d["croma"] = float(np.median(Cr[yy, xx]))
        d["pista"] = float(pista[yy, xx].mean())
        d["cidade"] = float(urb[yy, xx].mean())
        d["agua"] = float(agua[yy, xx].mean())
        d["comp"] = d["len"] / (u * k)
        liso = suavizar_presa(pts, sigma=1.3 * u)
        d["liso"] = simplificar(liso, eps=0.2 * u * k)

    classes = {"rodovias": [], "avenidas": [], "ruas": [], "vielas": []}
    medidas = []
    componente = {}
    for i, comp_nos in enumerate(nx.connected_components(g)):
        for n in comp_nos:
            componente[n] = i
    arestas_por_comp = {}
    for s_, e_ in g.edges():
        arestas_por_comp[componente[s_]] = arestas_por_comp.get(componente[s_], 0) + 1
    for grupo in tracados(g, u):
        ds = [g.edges[e] for e in grupo]
        peso = np.array([max(x["comp"], 1e-3) for x in ds])
        def media(chave):
            return float(np.average([x[chave] for x in ds], weights=peso))
        comp = float(peso.sum())
        largura, contraste, cidade, na_agua = media("largura"), media("contraste"), media("cidade"), media("agua")
        tom, na_pista, croma = media("tom"), media("pista"), media("croma")
        # pista de pouso isolada: um traço reto, solto, sem ligação com nenhuma via
        cadeias = encadear(g, grupo)
        isolado = arestas_por_comp[componente[grupo[0][0]]] <= len(grupo) + 1 and len(cadeias) == 1
        c0 = cadeias[0]
        reto = np.linalg.norm(c0[-1] - c0[0]) / max(_comprimento(c0), 1e-3) > 0.985
        if isolado and reto and largura >= 2.2 and comp >= 20:
            continue
        if na_pista > 0.5 or (largura > 6.5 and na_agua < 0.5):
            continue                                   # pistas de aeroporto, pátios: não são vias
        # no campo a via comum é cinza-oliva (com cor); a rodovia é cinza neutro e mais clara
        rural_cinza = cidade < 0.5 and croma <= 21 and tom >= 45 and comp >= 20 and largura >= 1.6
        larga_cinza = largura >= 2.7 and tom >= 45 and comp >= 25
        if rural_cinza or larga_cinza or (largura >= 3.3 and comp >= 25):
            cls = "rodovias"                           # cinza médio e larga: rodovia
        elif cidade < 0.5 or largura >= 2.4 or comp >= 140 or na_agua > 0.5:
            cls = "avenidas"
        elif contraste < 0.42 and comp < 30:
            cls = "vielas"
        else:
            cls = "ruas"
        for cadeia in cadeias:
            xy = cadeia[:, ::-1] / u                    # (x, y) em px do recorte
            classes[cls].append(caminho_relativo(xy, casas))
        medidas.append((cls, largura, contraste, comp, tom, croma, cidade, cadeias[0][len(cadeias[0]) // 2] / u))

    if relatorio is not None:
        relatorio["trechos"] = len(medidas)
        for c in classes:
            sel = [m for m in medidas if m[0] == c]
            relatorio[c] = {"trechos": len(sel), "km_px": round(sum(m[3] for m in sel))}
        relatorio["medidas"] = medidas
    return {c: "".join(v) for c, v in classes.items()}, mascara
