#!/usr/bin/env python3
"""
VICEVERSA — recria o mapa de Leonida em vetor, no estilo do site
=================================================================

Parte de uma imagem-base do mapa de Leonida (a mais recente em mapa/base/) e
redesenha tudo no estilo do VICEVERSA.

O que o script faz
------------------
1. Recorta só a área do mapa (sem a coluna de legenda e créditos).
2. Apaga a grade de referência e os textos do original (os nossos nomes são
   desenhados pelo site, nos três idiomas).
3. Classifica cada pixel pela cor (espaço de cor Lab): água, terra, pântano,
   área urbana, vias e prédios, areia/área industrial.
4. Monta as camadas no nosso estilo:
     - mar em 4 profundidades (a partir dos tons de azul do original);
     - relevo em 3 níveis (a partir do sombreado de altitude);
     - areia (junto da água) e áreas industriais/agrícolas (no interior);
     - cidades, quarteirões e prédios;
     - rodovias, estradas e ruas redesenhadas como linhas centrais.
5. Grava mapa/leonida.svg. As cores NÃO ficam no arquivo: cada camada tem uma
   classe e o site pinta com a paleta escolhida (Noite ou Dia).

Uso:
    pip install opencv-python-headless numpy
    python mapa/recriar_mapa.py
    python montar.py

Com uma imagem maior em mapa/base/ (a versão em alta resolução), o resultado
fica proporcionalmente mais detalhado — as medidas abaixo estão em pixels da
imagem de 2048 px de largura e o script converte para o tamanho real.
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
COLUNAS = 8                             # grade de referência do VICEVERSA: colunas A, B, C…

# ── ajustes da imagem V16 (em pixels da versão de 2048 px de largura) ──
REF = 2048
RECORTE = (586, 0, 2048, 1951)          # x0, y0, x1, y1 — só o mapa, sem a legenda
PASSO_GRADE = 97.45                     # espaçamento da grade do original (é apagada)
ESCALA = 3                              # ampliação antes de vetorizar: curvas mais suaves
CASAS = 1                               # casas decimais no SVG

# cores de referência do original (legenda "Terrain" e "Features")
CLASSES = {
    "agua":    ["#2C67A3", "#2E7DB5", "#2F89BE", "#3199CB", "#38A9D9", "#76C4CE", "#255184", "#55A5B3"],
    "verde":   ["#C0D788", "#B4CA7B", "#9BB16B", "#A9BF73"],
    "pantano": ["#87C8A3"],
    "urbana":  ["#D7DBD9", "#BAC5B9", "#C9CECB"],
    "via":     ["#757D67", "#545C44", "#9C9F9A", "#6B6F6A"],
    "amarela": ["#E7DC90", "#EDE3A0"],
}

MEIA_RODOVIA = 2.2      # meia-largura média (px na imagem de 2048) a partir da qual a via é rodovia
VIZ = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


# ── utilidades ──────────────────────────────────────────────────────
def hex_rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def carregar():
    imagens = sorted([p for p in BASE.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")],
                     key=lambda p: p.stat().st_mtime)
    if not imagens:
        sys.exit(f"Nenhuma imagem em {BASE}/")
    img = cv2.cvtColor(cv2.imread(str(imagens[-1])), cv2.COLOR_BGR2RGB)
    return img, imagens[-1].name


def limpar(mascara, minimo):
    """Tira manchas menores que `minimo` pixels."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mascara.astype(np.uint8), 8)
    manter = np.zeros(n, bool)
    manter[1:] = stats[1:, cv2.CC_STAT_AREA] >= minimo
    return manter[lab]


def tapar_furos(mascara, maximo):
    """Preenche furos menores que `maximo` pixels."""
    return ~limpar(~mascara, maximo)


def fechar(m, k):
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)) > 0


def abrir(m, k):
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)) > 0


def media_mascarada(valor, mascara, sigma):
    """Média borrada de `valor` só onde `mascara` é verdadeira (ignora o resto)."""
    m = mascara.astype(np.float32)
    num = cv2.GaussianBlur(valor.astype(np.float32) * m, (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)
    return num / np.maximum(den, 1e-3)


# ── limpeza do original ─────────────────────────────────────────────
def apagar_grade_e_textos(img, k):
    """Máscara da grade do original e dos textos (brancos e vermelhos) → inpaint."""
    h, w = img.shape[:2]
    g = img.astype(np.float32).mean(2)
    dx = g - (np.roll(g, 3, 1) + np.roll(g, -3, 1)) / 2
    dy = g - (np.roll(g, 3, 0) + np.roll(g, -3, 0)) / 2
    alvo = np.zeros((h, w), bool)
    passo = PASSO_GRADE * k
    for i in range(1, int(w / passo) + 1):
        c = int(round(i * passo - 1.5 * k))
        faixa = range(max(1, c - 3), min(w - 1, c + 4))
        x = max(faixa, key=lambda x: (dx[:, x] < -5).mean())
        if (dx[:, x] < -5).mean() > 0.2:
            alvo[:, x - 1:x + 2] |= dx[:, x - 1:x + 2] < -2
    for j in range(1, int(h / passo) + 1):
        c = int(round(j * passo))
        faixa = range(max(1, c - 3), min(h - 1, c + 4))
        y = max(faixa, key=lambda y: (dy[y] < -5).mean())
        if (dy[y] < -5).mean() > 0.2:
            alvo[y - 1:y + 2] |= dy[y - 1:y + 2] < -2

    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.int32)
    branco = img.min(2) > 228
    vermelho = (img[..., 0] > 150) & (img[..., 1] < 130) & (img[..., 2] < 140) & (hsv[..., 1] > 90)
    texto = cv2.dilate((branco | vermelho).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    alvo |= texto
    limpa = cv2.inpaint(img, alvo.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
    return cv2.medianBlur(limpa, 3)


def classificar(rgb):
    nomes, cores = [], []
    for nome, lista in CLASSES.items():
        for c in lista:
            nomes.append(nome)
            cores.append(hex_rgb(c))
    ref = cv2.cvtColor(np.array(cores, np.uint8).reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    rotulo = np.empty(len(lab), np.int32)
    for i in range(0, len(lab), 300_000):        # em blocos, para não estourar a memória
        d = ((lab[i:i + 300_000, None] - ref[None]) ** 2).sum(-1)
        rotulo[i:i + 300_000] = d.argmin(-1)
    rotulo = rotulo.reshape(rgb.shape[:2])
    return {nome: np.isin(rotulo, [j for j, n in enumerate(nomes) if n == nome]) for nome in CLASSES}


# ── vetorização ─────────────────────────────────────────────────────
def vetorizar(mascara, suave=1.2, epsilon=0.6, minimo=4.0):
    """Máscara → atributo d de <path> (com furos), em pixels da imagem recortada."""
    grande = cv2.resize(mascara.astype(np.float32), None, fx=ESCALA, fy=ESCALA, interpolation=cv2.INTER_LINEAR)
    if suave > 0:
        grande = cv2.GaussianBlur(grande, (0, 0), suave * ESCALA / 2)
    binaria = (grande > 0.5).astype(np.uint8)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    partes = []
    for c in contornos:
        if abs(cv2.contourArea(c)) < minimo * ESCALA * ESCALA:
            continue
        c = cv2.approxPolyDP(c, epsilon * ESCALA, True)
        if len(c) < 3:
            continue
        pts = c[:, 0, :] / ESCALA
        partes.append("M" + "L".join(f"{x:.{CASAS}f},{y:.{CASAS}f}" for x, y in pts) + "Z")
    return "".join(partes)


def esqueleto(mascara):
    """Afina a máscara até 1 pixel de largura (linha central das vias)."""
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


def linhas(mascara, meia_largura, urbana, k, minimo=3, epsilon=0.45):
    """Máscara de vias → três paths: rodovias, estradas (campo) e ruas (cidade)."""
    rodovias, estradas, ruas = [], [], []
    for linha in tracar(esqueleto(mascara)):
        if len(linha) < minimo:
            continue
        arr = np.array(linha, np.float32)
        yy, xx = arr[:, 0].astype(int), arr[:, 1].astype(int)
        largura = float(np.mean(meia_largura[yy, xx])) / k
        na_cidade = float(np.mean(urbana[yy, xx])) > 0.5
        c = cv2.approxPolyDP(arr[:, ::-1].reshape(-1, 1, 2), epsilon * k, False)[:, 0, :]
        c = suavizar(c.astype(np.float32))
        d = "M" + "L".join(f"{x:.{CASAS}f},{y:.{CASAS}f}" for x, y in c)
        # na cidade as ruas se juntam em manchas; lá a rodovia precisa ser mais larga e comprida
        exigida, comprimento = (MEIA_RODOVIA + 0.5, 14 * k) if na_cidade else (MEIA_RODOVIA, 8 * k)
        if largura >= exigida and len(linha) >= comprimento:
            rodovias.append(d)
        elif na_cidade:
            ruas.append(d)
        else:
            estradas.append(d)
    return "".join(rodovias), "".join(estradas), "".join(ruas)


# ── principal ───────────────────────────────────────────────────────
def main():
    img, origem = carregar()
    h0, w0 = img.shape[:2]
    k = w0 / REF                                   # imagem maior que a referência → escala as medidas
    x0, y0, x1, y1 = [int(round(v * k)) for v in RECORTE]
    x1, y1 = min(x1, w0), min(y1, h0)
    img = img[y0:y1, x0:x1].copy()
    h, w = img.shape[:2]
    print(f"Imagem: {origem} · mapa recortado {w}×{h} px")

    limpa = apagar_grade_e_textos(img, k)
    m = classificar(limpa)
    a = lambda px: max(2, int(px * k * k))          # área mínima escalada

    # ── terra e água ──
    agua = m["agua"]
    terra = limpar(tapar_furos(~agua, a(6)), a(8))
    agua = ~terra

    # profundidade: o verde do azul cresce do fundo para o raso
    fundo = media_mascarada(limpa[..., 1], agua, 3 * k)
    raso3 = agua & (fundo >= 132)
    raso2 = agua & (fundo >= 150)
    raso1 = agua & (fundo >= 172)

    # ── vias: traços mais escuros que o entorno e sem cor (cinza) ──
    lab = cv2.cvtColor(limpa, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[..., 0]
    croma = np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)
    tam = max(7, int(round(11 * k)) | 1)
    escuro = cv2.morphologyEx(L, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tam, tam)))
    via = ((escuro > 18) & (croma < 32)) | m["via"]
    beira = cv2.dilate(agua.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    via_terra = via & terra
    via_agua = via & agua & ~beira                  # pontes sobre a água

    # ── cidade: quarteirões e prédios ──
    urbana = abrir(fechar(m["urbana"] & terra, 7), 5)
    urbana = limpar(urbana, a(60))
    urbana = tapar_furos(urbana, a(30)) & terra

    # prédios: manchas escuras compactas dentro da cidade (as vias são compridas e finas)
    grosso = abrir(via_terra, 3)
    n, lab_c, stats, _ = cv2.connectedComponentsWithStats(grosso.astype(np.uint8), 8)
    compacto = np.zeros(n, bool)
    for i in range(1, n):
        wb, hb, ar = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
        preenchimento = ar / max(1, wb * hb)
        alongamento = max(wb, hb) / max(1, min(wb, hb))
        compacto[i] = ar >= a(6) and preenchimento > 0.45 and alongamento < 4.5 and max(wb, hb) < 40 * k
    predios = compacto[lab_c] & urbana
    predios = cv2.dilate(predios.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0

    vias = (via_terra & ~predios) | limpar(via_agua, a(12))
    vias = limpar(fechar(vias, 2), a(14))
    meia = cv2.distanceTransform(vias.astype(np.uint8), cv2.DIST_L2, 3)

    # ── relevo, pântano, areia e áreas industriais ──
    verde = (m["verde"] | via) & terra & ~urbana
    relevo = media_mascarada(L, m["verde"] & terra, 3.5 * k)
    alto1 = verde & (relevo <= 206)
    alto2 = verde & (relevo <= 190)
    alto1 = limpar(abrir(alto1, 3), a(40))
    alto2 = limpar(abrir(alto2, 3), a(40))

    pantano = limpar(abrir(m["pantano"] & terra, 2), a(10))

    amarela = limpar(abrir(m["amarela"] & terra, 2), a(6))
    perto_agua = cv2.dilate(agua.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    # areia: manchas amarelas quase inteiras junto da costa; no interior, área industrial/agrícola
    costa = cv2.distanceTransform((~agua).astype(np.uint8), cv2.DIST_L2, 5) <= 14 * k
    n, lab_c, stats, _ = cv2.connectedComponentsWithStats(amarela.astype(np.uint8), 8)
    na_costa = np.bincount(lab_c[costa & amarela], minlength=n) / np.maximum(stats[:, cv2.CC_STAT_AREA], 1)
    eh_areia = (na_costa > 0.6) & (np.bincount(lab_c[perto_agua & amarela], minlength=n) > 0)
    eh_areia[0] = False
    areia = eh_areia[lab_c]
    industrial = amarela & ~areia

    camadas = [
        ("raso3", raso3, dict(suave=4.0, epsilon=1.0, minimo=40)),
        ("raso2", raso2, dict(suave=3.0, epsilon=0.8, minimo=20)),
        ("raso1", raso1, dict(suave=2.0, epsilon=0.6, minimo=8)),
        ("terra", terra, dict(suave=1.0, epsilon=0.4, minimo=2)),
        ("colina", alto1, dict(suave=2.5, epsilon=0.8, minimo=30)),
        ("floresta", alto2, dict(suave=2.5, epsilon=0.8, minimo=30)),
        ("pantano", pantano, dict(suave=1.2, epsilon=0.5, minimo=4)),
        ("industrial", industrial, dict(suave=1.0, epsilon=0.5, minimo=6)),
        ("areia", areia, dict(suave=1.0, epsilon=0.4, minimo=3)),
        ("urbana", urbana, dict(suave=1.2, epsilon=0.5, minimo=20)),
        ("predio", predios, dict(suave=0, epsilon=0.5, minimo=3)),
    ]
    paths = []
    for nome, mascara, opc in camadas:
        d = vetorizar(mascara, **opc)
        paths.append(f'<path class="c-{nome}" fill-rule="evenodd" d="{d}"/>')
        print(f"  {nome:10s} {len(d) / 1024:8.1f} KB")

    # linhas: espessura constante na tela, qualquer que seja o zoom
    rodovias, estradas, ruas = linhas(vias, meia, urbana, k)
    for classe, d in (("ruas", ruas), ("vias", estradas), ("vias-largas", rodovias)):
        paths.append(f'<path class="l-{classe}" fill="none" vector-effect="non-scaling-stroke" '
                     f'stroke-linecap="round" stroke-linejoin="round" d="{d}"/>')
        print(f"  {classe:10s} {len(d) / 1024:8.1f} KB")

    # grade de referência do VICEVERSA (A1, B2…), estilo guia de ruas
    celula = w / COLUNAS
    linhas_grade = int(np.ceil(h / celula))
    g = ['<g class="grade">']
    d = "".join(f"M{i * celula:.1f},0V{h}" for i in range(1, COLUNAS))
    d += "".join(f"M0,{j * celula:.1f}H{w}" for j in range(1, linhas_grade))
    g.append(f'<path fill="none" vector-effect="non-scaling-stroke" d="{d}"/>')
    for i in range(COLUNAS):
        for j in range(linhas_grade):
            g.append(f'<text x="{i * celula + 5:.1f}" y="{j * celula + 16:.1f}">{chr(65 + i)}{j + 1}</text>')
    g.append("</g>")
    paths.append("".join(g))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'data-origem="{origem}" shape-rendering="geometricPrecision">\n'
           f'<rect class="c-mar" width="{w}" height="{h}"/>\n' + "\n".join(paths) + "\n</svg>\n")
    SAIDA.write_text(svg, encoding="utf-8")
    INFO.write_text(json.dumps({"largura": w, "altura": h, "origem": origem,
                                "recorte": [x0, y0, x1, y1], "imagem": [w0, h0],
                                "grade": {"colunas": COLUNAS, "linhas": linhas_grade, "celula": round(celula, 3)}},
                               indent=2), encoding="utf-8")
    print(f"\nmapa/leonida.svg: {len(svg) / 1024:.0f} KB ({w}×{h}). Agora rode: python montar.py")


if __name__ == "__main__":
    main()
