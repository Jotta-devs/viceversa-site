#!/usr/bin/env python3
"""
VICEVERSA — gerador do site (multipágina, multi-idioma)
========================================================

Monta cada página a partir de:
    partes/cabeca.html  +  paginas/<pagina>.html  +  partes/rodape.html
trocando os {{marcadores}} pelos textos de idiomas/<codigo>.json.

    python3 montar.py

Resultado (inglês na raiz):
    site/index.html        site/news/          site/map/
    site/pt/               site/pt/noticias/   site/pt/mapa/
    site/es/               site/es/noticias/   site/es/mapa/

Para mudar textos edite os JSON — nunca a pasta docs/, que é apagada e regerada.
"""

import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
PARTES = RAIZ / "partes"
PAGINAS = RAIZ / "paginas"
PASTA_IDIOMAS = RAIZ / "idiomas"
SAIDA = RAIZ / "docs"   # o GitHub Pages serve a raiz ou /docs
ESTATICOS = ["ebook-capa-en.png", "ebook-capa-pt.png", "ebook-capa-es.png",
             "og-image-en.png", "og-image-pt.png", "og-image-es.png",
             "feed.json", "ads.txt"]

# ── troque pelo endereço real antes de publicar ─────────────────────
DOMINIO = "https://vvviceversa.com"

IDIOMAS = {
    # código: (pasta, hreflang, og:locale, rótulo, é o padrão?, checkout do ebook)
    "en":    ("",   "en",    "en_US", "EN", True,  "https://pay.kiwify.com/eLDJK0v"),
    "pt-BR": ("pt", "pt-BR", "pt_BR", "PT", False, "https://pay.kiwify.com.br/f6pNg7O"),
    "es":    ("es", "es",    "es_ES", "ES", False, "https://pay.kiwify.com/0xSU59u"),
}

# página: (arquivo em paginas/, slug por idioma)
PAGINAS_SITE = {
    "home":     ("home.html",     {"en": "",     "pt-BR": "",         "es": ""}),
    "noticias": ("noticias.html", {"en": "news", "pt-BR": "noticias", "es": "noticias"}),
    "mapa":     ("mapa.html",     {"en": "map",  "pt-BR": "mapa",     "es": "mapa"}),
}


def caminho(codigo, pagina):
    pasta = IDIOMAS[codigo][0]
    slug = PAGINAS_SITE[pagina][1][codigo]
    return "/".join(p for p in (pasta, slug) if p)


def url(codigo, pagina):
    c = caminho(codigo, pagina)
    return f"{DOMINIO}/" + (f"{c}/" if c else "")


def profundidade(codigo, pagina):
    c = caminho(codigo, pagina)
    return len(c.split("/")) if c else 0


def bloco_hreflang(pagina):
    linhas = []
    for cod, (_, hl, _, _, padrao, _) in IDIOMAS.items():
        linhas.append(f'<link rel="alternate" hreflang="{hl}" href="{url(cod, pagina)}">')
        if padrao:
            linhas.append(f'<link rel="alternate" hreflang="x-default" href="{url(cod, pagina)}">')
    return "\n".join(linhas)


def links_idioma(atual, pagina, prefixo, classe_ativa="idioma-atual"):
    itens = []
    for cod, (_, hl, _, rotulo, _, _) in IDIOMAS.items():
        c = caminho(cod, pagina)
        destino = prefixo + (c + "/" if c else "")
        destino = destino or "./"
        classe = classe_ativa if cod == atual else ""
        aria = ' aria-current="true"' if cod == atual else ""
        itens.append(f'<a class="{classe}" href="{destino}" hreflang="{hl}" lang="{hl}"{aria}>{rotulo}</a>')
    return itens


def montar():
    cabeca = (PARTES / "cabeca.html").read_text(encoding="utf-8")
    rodape = (PARTES / "rodape.html").read_text(encoding="utf-8")
    base = json.loads((PASTA_IDIOMAS / "pt-BR.json").read_text(encoding="utf-8"))

    # o GitHub grava docs/CNAME ao configurar o domínio personalizado;
    # a pasta é recriada a cada geração, então o arquivo é preservado à mão.
    cname = None
    if (SAIDA / "CNAME").exists():
        cname = (SAIDA / "CNAME").read_text(encoding="utf-8")

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    SAIDA.mkdir()

    if cname:
        (SAIDA / "CNAME").write_text(cname, encoding="utf-8")
    # desliga o Jekyll: o site é estático e não precisa de processamento
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")

    total = 0
    for cod, (pasta, hl, locale, rotulo, padrao, link_ebook) in IDIOMAS.items():
        arq = PASTA_IDIOMAS / f"{cod}.json"
        if not arq.exists():
            print(f"  ! idiomas/{cod}.json ausente — pulando {cod}")
            continue
        textos = dict(base)
        textos.update(json.loads(arq.read_text(encoding="utf-8")))

        for pagina, (arquivo, _) in PAGINAS_SITE.items():
            corpo = (PAGINAS / arquivo).read_text(encoding="utf-8")
            html = cabeca + "\n" + corpo + "\n" + rodape

            faltando = []
            for chave in base:
                marcador = "{{%s}}" % chave
                if marcador in html:
                    valor = textos.get(chave)
                    if valor is None:
                        faltando.append(chave)
                        valor = base[chave]
                    html = html.replace(marcador, valor)

            prefixo = "../" * profundidade(cod, pagina)
            atual = {p: (' aria-current="page"' if p == pagina else "") for p in PAGINAS_SITE}
            casa = caminho(cod, "home")

            html = (html
                    .replace("{{__lang__}}", hl)
                    .replace("{{__locale__}}", locale)
                    .replace("{{__canonical__}}", url(cod, pagina))
                    .replace("{{__siteroot__}}", url(cod, "home"))
                    .replace("{{__base_url__}}", DOMINIO + "/")
                    .replace("{{__base__}}", prefixo)
                    .replace("{{__ogimage__}}", "og-image-%s.png" % cod.split("-")[0])
                    .replace("{{__ebookcapa__}}", "ebook-capa-%s.png" % cod.split("-")[0])
                    .replace("{{__hreflang__}}", bloco_hreflang(pagina))
                    .replace("{{__seletor__}}",
                             '  <nav class="seletor-idioma" aria-label="Idioma / Language">\n    '
                             + "\n    ".join(links_idioma(cod, pagina, prefixo)) + "\n  </nav>")
                    .replace("{{__idiomas_menu__}}", "".join(links_idioma(cod, pagina, prefixo)))
                    .replace("{{__ebook_link__}}", link_ebook)
                    .replace("{{__home__}}", (prefixo + (casa + "/" if casa else "")) or "./")
                    .replace("{{__news__}}", prefixo + caminho(cod, "noticias") + "/")
                    .replace("{{__map__}}", prefixo + caminho(cod, "mapa") + "/")
                    .replace("{{__at_home__}}", atual["home"])
                    .replace("{{__at_news__}}", atual["noticias"])
                    .replace("{{__at_map__}}", atual["mapa"]))

            m = re.search(r'<div class="footer-social">([\s\S]*?)</div>', html)
            html = html.replace("{{__social_menu__}}",
                                '<div class="menu-social">%s</div>' % m.group(1) if m else "")

            restantes = set(re.findall(r"\{\{[^}]+\}\}", html))
            if restantes:
                print(f"  ! {cod}/{pagina}: marcadores não substituídos: {restantes}")

            c = caminho(cod, pagina)
            destino = SAIDA / c if c else SAIDA
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "index.html").write_text(html, encoding="utf-8")
            total += 1
            aviso = f" ({len(faltando)} sem tradução)" if faltando else ""
            print(f"  ✓ {(c + '/' if c else '')}index.html{aviso}")

    for nome in ESTATICOS:
        if (RAIZ / nome).exists():
            shutil.copy(RAIZ / nome, SAIDA / nome)

    urls = ""
    for cod in IDIOMAS:
        for pagina in PAGINAS_SITE:
            alt = "".join(
                f'\n    <xhtml:link rel="alternate" hreflang="{IDIOMAS[o][1]}" href="{url(o, pagina)}"/>'
                for o in IDIOMAS)
            urls += f"\n  <url><loc>{url(cod, pagina)}</loc>{alt}\n  </url>"
    (SAIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + urls + "\n</urlset>\n", encoding="utf-8")
    (SAIDA / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}/sitemap.xml\n", encoding="utf-8")

    print(f"\n{total} páginas geradas em docs/. Faça commit e push.")


if __name__ == "__main__":
    sys.exit(montar())
