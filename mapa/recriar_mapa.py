#!/usr/bin/env python3
"""
VICEVERSA — recria o mapa de Leonida em vetor, no estilo do site
=================================================================

Base: "YANIS GTA VI Community Map", da Mapping Community (map.stateofleonida.net).
Yanis autorizou o VICEVERSA a modificar o mapa e a recriá-lo no nosso estilo,
com crédito. Guarde o print da autorização.

O que o script faz
------------------
1. Recorta só a área do mapa (sem a coluna de legenda e créditos).
2. Apaga os rótulos de texto do original (os nossos são desenhados pelo site,
   nos três idiomas).
3. Classifica cada pixel pela cor: mar, terra, floresta, área urbana, pântano,
   areia e estradas.
4. Amplia cada camada com suavização e a converte em vetor (SVG), com as
   linhas da costa, das estradas e das cidades redesenhadas.
5. Grava mapa/leonida.svg. As cores NÃO ficam no arquivo: cada camada tem uma
   classe, e o site pinta com a paleta escolhida (Noite ou Dia).

Uso:
    pip install opencv-python-headless numpy
    python mapa/recriar_mapa.py

Com uma imagem maior em mapa/base/ (a versão em alta resolução), o resultado
fica proporcionalmente mais detalhado. Se o layout da imagem mudar, ajuste
RECORTE e ROTULOS abaixo (coordenadas na imagem de 1080 px; o script converte
para o tamanho real da imagem).
"""

import json
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("Faltam bibliotecas. Rode:  pip install opencv-python-headless numpy")

PASTA = Path(__file__).parent
BASE = PASTA / "base"
SAIDA = PASTA / "leonida.svg"
INFO = PASTA / "leonida.json"
ORIGINAL = PASTA / "original.webp"     # o original recortado, para o botão "Original (YANIS)"
LADO_ORIGINAL = 2400                    # maior lado do original.webp (px)
COLUNAS = 8                             # grade de referência: colunas A, B, C…


# ── ajustes da imagem V16 (em pixels da versão de 1080 px) ─────────
REF = 1080                              # largura de referência das coordenadas abaixo
RECORTE = (312, 0, 1080, 1080)          # x0, y0, x1, y1 — só o mapa, sem a legenda
ROTULOS = [                             # caixas de texto do original a apagar
    (610, 259, 740, 279),   # MT. KALAGA NATIONAL PARK
    (462, 354, 540, 375),   # PORT GELLHORN (PANAMA CITY)
    (671, 341, 724, 364),   # AMBROSIA
    (866, 543, 917, 564),   # VICE CITY (MIAMI)
    (645, 813, 712, 833),   # GRASSRIVERS (EVERGLADES)
    (619, 936, 689, 959),   # LEONIDA KEYS (FLORIDA KEYS)
    (738, 908, 772, 918),   # KEY LENTO
    (560, 938, 602, 948),   # rótulo pequeno do aeroporto das Keys
]

# cores de referência do mapa original (legenda "Terrain")
CLASSES = {
    "agua":     ["#2B68A5", "#2183B2", "#1996C1", "#4CABBB", "#7DD0D7"],
    "terra":    ["#BED684", "#C2DC9B"],
    "floresta": ["#A8BC78"],
    "clara":    ["#DFEDAE"],                       # areia (junto da água) ou estrada
    "urbana":   ["#D2DCD6", "#B7C7BC"],
    "branca":   ["#E9F1E6"],                       # ruas e quadras claras
    "pantano":  ["#81C4A5", "#4C8A87"],
}

ESCALA = 4          # ampliação antes de vetorizar: curvas mais suaves
LARGURA_RODOVIA = 1.35   # meia-largura média (px na imagem de 1080) a partir da qual a via é rodovia
AMARELO_RODOVIA = 60     # (R+G)/2 − B médio a partir do qual a via é rodovia (amarela no original)
CASAS = 1           # casas decimais no SVG


VIZ = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def esqueleto(mascara):
    """Afina a máscara até 1 pixel de largura (linha central das estradas)."""
    try:
        return cv2.ximgproc.thinning(mascara.astype(np.uint8) * 255) > 0
    except AttributeError:
        from skimage.morphology import skeletonize
        return skeletonize(mascara)


def tracar(esq):
    """Esqueleto → lista de polilinhas [(y, x), ...] ligando pontas e cruzamentos."""
    ys, xs = np.nonzero(esq)
    pontos = set(zip(ys.tolist(), xs.tolist()))

    def vizinhos(p):
        return [(p[0] + a, p[1] + b) for a, b in VIZ if (p[0] + a, p[1] + b) in pontos]

    grau = {p: len(vizinhos(p)) for p in pontos}
    nos = [p for p, g in grau.items() if g != 2]
    usadas = set()
    linhas = []

    def andar(inicio, prox):
        linha = [inicio, prox]
        usadas.add((inicio, prox)); usadas.add((prox, inicio))
        atual, anterior = prox, inicio
        while grau.get(atual, 0) == 2:
            seguintes = [v for v in vizinhos(atual) if v != anterior and (atual, v) not in usadas]
            if not seguintes:
                break
            anterior, atual = atual, seguintes[0]
            usadas.add((anterior, atual)); usadas.add((atual, anterior))
            linha.append(atual)
        return linha

    for n in nos:
        for v in vizinhos(n):
            if (n, v) not in usadas:
                linhas.append(andar(n, v))
    for p in pontos:                               # anéis sem ponta nem cruzamento
        for v in vizinhos(p):
            if (p, v) not in usadas:
                linhas.append(andar(p, v))
    return linhas


def suavizar(pts, voltas=2):
    """Chaikin: arredonda as quinas mantendo as pontas."""
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


def linhas_svg(mascara, largura_px, fator, amarelo=None, minimo=2, epsilon=0.35):
    """Máscara de estrada → dois paths de linhas (rodovias e vias comuns).

    Rodovia: via mais larga OU mais amarela que as outras (no original, as
    rodovias são amarelas e as estradas comuns, quase brancas)."""
    esq = esqueleto(mascara)
    largas, finas = [], []
    for linha in tracar(esq):
        if len(linha) < minimo:
            continue
        arr = np.array(linha, np.float32)
        largura = float(np.mean([largura_px[int(y), int(x)] for y, x in linha]))
        cor = float(np.mean([amarelo[int(y), int(x)] for y, x in linha])) if amarelo is not None else 0
        rodovia = largura >= LARGURA_RODOVIA or cor >= AMARELO_RODOVIA
        c = cv2.approxPolyDP(arr[:, ::-1].reshape(-1, 1, 2), epsilon, False)[:, 0, :]
        c = suavizar(c.astype(np.float32))
        d = "M" + "L".join(f"{x / fator:.{CASAS}f},{y / fator:.{CASAS}f}" for x, y in c)
        (largas if rodovia else finas).append(d)
    return "".join(largas), "".join(finas)


def hex_rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def carregar():
    imagens = sorted([p for p in BASE.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
                     key=lambda p: p.stat().st_mtime)
    if not imagens:
        sys.exit(f"Nenhuma imagem em {BASE}/")
    img = cv2.cvtColor(cv2.imread(str(imagens[-1])), cv2.COLOR_BGR2RGB)
    return img, imagens[-1].name


def classificar(rgb):
    nomes, cores = [], []
    for nome, lista in CLASSES.items():
        for c in lista:
            nomes.append(nome)
            cores.append(hex_rgb(c))
    cores = np.array(cores, np.float32)
    px = rgb.reshape(-1, 3).astype(np.float32)
    rotulo = np.empty(len(px), np.int32)
    for i in range(0, len(px), 400_000):        # em blocos, para não estourar a memória
        bloco = px[i:i + 400_000]
        d = ((bloco[:, None, :] - cores[None]) ** 2).sum(-1)
        rotulo[i:i + 400_000] = d.argmin(-1)
    rotulo = rotulo.reshape(rgb.shape[:2])
    return {nome: np.isin(rotulo, [j for j, n in enumerate(nomes) if n == nome]) for nome in CLASSES}


def limpar(mascara, minimo):
    """Tira manchas menores que `minimo` pixels."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), 8)
    manter = np.zeros(n, bool)
    manter[1:] = stats[1:, cv2.CC_STAT_AREA] >= minimo
    return manter[lab]


def vetorizar(mascara, fator, suave=1.2, epsilon=0.7, minimo=6.0):
    """Máscara → atributo d de <path> (com furos), em coordenadas da imagem recortada."""
    m = mascara.astype(np.float32)
    grande = cv2.resize(m, None, fx=ESCALA, fy=ESCALA, interpolation=cv2.INTER_LINEAR)
    grande = cv2.GaussianBlur(grande, (0, 0), suave * ESCALA / 2)
    binaria = (grande > 0.5).astype(np.uint8)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    partes = []
    div = ESCALA * fator
    for c in contornos:
        if cv2.contourArea(c) < minimo * ESCALA * ESCALA:
            continue
        c = cv2.approxPolyDP(c, epsilon * ESCALA, True)
        if len(c) < 3:
            continue
        pts = c[:, 0, :] / div
        partes.append("M" + "L".join(f"{x:.{CASAS}f},{y:.{CASAS}f}" for x, y in pts) + "Z")
    return "".join(partes)


def main():
    img, origem = carregar()
    h0, w0 = img.shape[:2]
    k = w0 / REF                                   # imagem maior que a referência → escala as caixas
    x0, y0, x1, y1 = [int(round(v * k)) for v in RECORTE]
    img = img[y0:y1, x0:x1].copy()

    # cópia do original recortado (sem alterações), para quem quiser comparar
    reduz = min(1.0, LADO_ORIGINAL / max(img.shape[:2]))
    copia = cv2.resize(img, None, fx=reduz, fy=reduz, interpolation=cv2.INTER_AREA) if reduz < 1 else img
    cv2.imwrite(str(ORIGINAL), cv2.cvtColor(copia, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_WEBP_QUALITY, 86])

    # 1) apaga os rótulos do original (preenche pelo entorno)
    alvo = np.zeros(img.shape[:2], np.uint8)
    for (a, b, c, d) in ROTULOS:
        alvo[int((b * k) - y0):int((d * k) - y0), int((a * k) - x0):int((c * k) - x0)] = 255
    img = cv2.inpaint(img, alvo, 5 * k, cv2.INPAINT_TELEA)

    # 2) classes de cor
    m = classificar(img)
    h, w = img.shape[:2]
    fator = 1.0                                    # coordenadas finais = pixels da imagem recortada
    area_min = max(4, int(6 * k * k))

    agua = m["agua"]
    terra = limpar(~agua, area_min)
    # rios e lagos: água cercada de terra continua como água (furos na terra)

    # tons claros: areia (manchas largas encostadas na água) ou estrada (linhas finas)
    clara = m["clara"] & terra
    meia = cv2.distanceTransform(clara.astype(np.uint8), cv2.DIST_L2, 3)
    perto_agua = cv2.dilate(agua.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    n, lab, _, _ = cv2.connectedComponentsWithStats(clara.astype(np.uint8), 8)
    grossura = np.zeros(n, np.float32)
    np.maximum.at(grossura, lab.ravel(), meia.ravel())
    toca = np.zeros(n, bool)
    toca[np.unique(lab[perto_agua & clara])] = True
    eh_areia = toca & (grossura > 2.2 * k)
    eh_areia[0] = False
    areia = limpar(eh_areia[lab], area_min)

    # área urbana: cinzas e brancos em manchas (fechamento une as quadras)
    cinza = (m["urbana"] | m["branca"]) & terra
    urbana = cv2.morphologyEx(cinza.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)) > 0
    urbana = cv2.morphologyEx(urbana.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
    urbana = limpar(urbana & terra, int(40 * k * k))

    # estradas (fora das cidades) e ruas (dentro delas), como linhas centrais
    # estradas no campo: claras e brancas fora das cidades; fechamento emenda falhas de 1 px
    vias = (clara | (m["branca"] & terra & ~urbana)) & ~areia
    vias = cv2.morphologyEx(vias.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) > 0
    vias = limpar(vias & terra, int(10 * k * k))
    largura_vias = cv2.distanceTransform(vias.astype(np.uint8), cv2.DIST_L2, 3) / k
    ruas = limpar(m["branca"] & urbana, int(6 * k * k))
    largura_ruas = cv2.distanceTransform(ruas.astype(np.uint8), cv2.DIST_L2, 3) / k

    floresta = limpar(cv2.morphologyEx(m["floresta"].astype(np.uint8), cv2.MORPH_OPEN,
                                       np.ones((2, 2), np.uint8)) > 0, int(12 * k * k)) & terra
    pantano = limpar(m["pantano"] & terra, int(8 * k * k))

    # faixas de água rasa: desenhadas por nós, a partir da distância até a costa
    dist = cv2.distanceTransform((~terra).astype(np.uint8), cv2.DIST_L2, 5)
    dist = cv2.GaussianBlur(dist, (0, 0), 2.5 * k)          # isolinhas suaves, sem "caroços"
    raso1 = ~terra & (dist <= 4 * k)
    raso2 = ~terra & (dist <= 10 * k)

    camadas = [
        ("raso2", raso2, dict(suave=5.0, epsilon=1.2, minimo=40)),
        ("raso1", raso1, dict(suave=3.0, epsilon=0.9, minimo=12)),
        ("terra", terra, dict(suave=1.1, epsilon=0.45, minimo=2)),
        ("floresta", floresta, dict(suave=1.6, epsilon=0.8, minimo=8)),
        ("pantano", pantano, dict(suave=1.2, epsilon=0.6, minimo=4)),
        ("areia", areia, dict(suave=1.0, epsilon=0.5, minimo=2)),
        ("urbana", urbana, dict(suave=1.2, epsilon=0.6, minimo=10)),
    ]
    paths = []
    for nome, mascara, opc in camadas:
        d = vetorizar(mascara, fator, **opc)
        paths.append(f'<path class="c-{nome}" fill-rule="evenodd" d="{d}"/>')
        print(f"  {nome:9s} {len(d) / 1024:7.1f} KB")

    # linhas: espessura constante na tela, qualquer que seja o zoom
    rgbf = cv2.GaussianBlur(img.astype(np.float32), (3, 3), 0)
    amarelo = (rgbf[:, :, 0] + rgbf[:, :, 1]) / 2 - rgbf[:, :, 2]
    for nome, mascara, largura in (("ruas", ruas, largura_ruas), ("vias", vias, largura_vias)):
        largas, finas = linhas_svg(mascara, largura, fator, amarelo if nome == "vias" else None)
        if nome == "ruas":
            finas, largas = finas + largas, ""
        for classe, d in ((f"{nome}", finas), (f"{nome}-largas", largas)):
            if d:
                paths.append(f'<path class="l-{classe}" fill="none" vector-effect="non-scaling-stroke" '
                             f'stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')
                print(f"  {classe:9s} {len(d) / 1024:7.1f} KB")

    # grade de referência (A1, B2…), estilo guia de ruas — ligada e desligada no site
    celula = w / COLUNAS
    linhas_grade = int(np.ceil(h / celula))
    g = [f'<g class="grade">']
    d = "".join(f"M{i * celula:.1f},0V{h}" for i in range(1, COLUNAS))
    d += "".join(f"M0,{j * celula:.1f}H{w}" for j in range(1, linhas_grade))
    g.append(f'<path fill="none" vector-effect="non-scaling-stroke" d="{d}"/>')
    for i in range(COLUNAS):
        for j in range(linhas_grade):
            g.append(f'<text x="{i * celula + 4:.1f}" y="{j * celula + 13:.1f}">{chr(65 + i)}{j + 1}</text>')
    g.append("</g>")
    paths.append("".join(g))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'data-origem="{origem}" shape-rendering="geometricPrecision">\n'
           f'<rect class="c-mar" width="{w}" height="{h}"/>\n' + "\n".join(paths) + "\n</svg>\n")
    SAIDA.write_text(svg, encoding="utf-8")
    INFO.write_text(json.dumps({"largura": w, "altura": h, "origem": origem,
                                "recorte": [x0, y0, x1, y1], "imagem": [w0, h0],
                                "grade": {"colunas": COLUNAS, "linhas": linhas_grade, "celula": round(celula, 3)}},
                               indent=2),
                    encoding="utf-8")
    print(f"\nmapa/leonida.svg: {len(svg) / 1024:.0f} KB ({w}×{h}). Agora rode: python montar.py")


if __name__ == "__main__":
    main()
