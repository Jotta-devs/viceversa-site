#!/usr/bin/env python3
"""
VICEVERSA — gerador do site (multipágina, multi-idioma)
========================================================

Monta cada página a partir de:
    partes/cabeca.html  +  paginas/<pagina>.html  +  partes/rodape.html
trocando os {{marcadores}} pelos textos de idiomas/<codigo>.json.

    python3 montar.py

Resultado (inglês na raiz), dentro de docs/:
    index.html              news/               map/          about/ contact/ ...
    pt/                     pt/noticias/        pt/mapa/      pt/sobre/ ...
    es/                     es/noticias/        es/mapa/      es/sobre/ ...
    news/<slug>/            uma página por notícia (feed.json)
    pt/noticias/<slug>/     versão em português, quando a Issue tem tradução
    es/noticias/<slug>/     versão em espanhol, idem
    feed.xml, pt/feed.xml, es/feed.xml      RSS por idioma
    sitemap.xml, news-sitemap.xml, robots.txt

Para mudar textos edite os JSON (e institucional/ para as páginas Sobre,
Contato, Privacidade e Política editorial) — nunca a pasta docs/, que é
apagada e regerada.
"""

import html as html_lib
import json
import re
import shutil
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

RAIZ = Path(__file__).parent
PARTES = RAIZ / "partes"
PAGINAS = RAIZ / "paginas"
PASTA_IDIOMAS = RAIZ / "idiomas"
PASTA_INSTITUCIONAL = RAIZ / "institucional"
PASTA_MAPA = RAIZ / "mapa"          # imagem-base, vetor e pontos do mapa de Leonida
PASTA_VENDOR = RAIZ / "vendor"      # bibliotecas de terceiros servidas pelo próprio site (Leaflet)
SAIDA = RAIZ / "docs"   # o GitHub Pages serve a raiz ou /docs
ESTATICOS = ["ebook-capa-en.png", "ebook-capa-pt.png", "ebook-capa-es.png",
             "og-image-en.png", "og-image-pt.png", "og-image-es.png",
             "feed.json", "ads.txt"]

# ── troque pelo endereço real antes de publicar ─────────────────────
DOMINIO = "https://vvviceversa.com"
NOME_SITE = "VICEVERSA"

IDIOMAS = {
    # código: (pasta, hreflang, og:locale, rótulo, é o padrão?, checkout do ebook)
    "en":    ("",   "en",    "en_US", "EN", True,  "https://pay.kiwify.com/eLDJK0v"),
    "pt-BR": ("pt", "pt-BR", "pt_BR", "PT", False, "https://pay.kiwify.com.br/f6pNg7O"),
    "es":    ("es", "es",    "es_ES", "ES", False, "https://pay.kiwify.com/0xSU59u"),
}
# sufixo usado no feed.json para as traduções (titulo_pt, html_es...)
SUFIXO_POST = {"pt-BR": "pt", "es": "es"}
# idioma no formato do Google Notícias
IDIOMA_NEWS = {"en": "en", "pt-BR": "pt", "es": "es"}

# página: (arquivo em paginas/, slug por idioma)
PAGINAS_SITE = {
    "home":        ("home.html",          {"en": "",                 "pt-BR": "",                   "es": ""}),
    "noticias":    ("noticias.html",      {"en": "news",             "pt-BR": "noticias",           "es": "noticias"}),
    "mapa":        ("mapa.html",          {"en": "map",              "pt-BR": "mapa",               "es": "mapa"}),
    "sobre":       ("institucional.html", {"en": "about",            "pt-BR": "sobre",              "es": "sobre"}),
    "contato":     ("institucional.html", {"en": "contact",          "pt-BR": "contato",            "es": "contacto"}),
    "privacidade": ("institucional.html", {"en": "privacy",          "pt-BR": "privacidade",        "es": "privacidad"}),
    "editorial":   ("institucional.html", {"en": "editorial-policy", "pt-BR": "politica-editorial", "es": "politica-editorial"}),
}
INSTITUCIONAIS = ("sobre", "contato", "privacidade", "editorial")

LANCAMENTO = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)   # 19/11 00:00 em Brasília
CARDS_NOTICIAS = 20     # cards completos na página de notícias; o resto vai para o arquivo
MESES = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "pt-BR": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
}


# ── caminhos ────────────────────────────────────────────────────────
def caminho(codigo, pagina):
    pasta = IDIOMAS[codigo][0]
    slug = PAGINAS_SITE[pagina][1][codigo]
    return "/".join(p for p in (pasta, slug) if p)


def url(codigo, pagina):
    c = caminho(codigo, pagina)
    return f"{DOMINIO}/" + (f"{c}/" if c else "")


def url_rel(rel):
    return f"{DOMINIO}/" + (f"{rel}/" if rel else "")


# ── utilidades de texto ─────────────────────────────────────────────
def esc(texto):
    return html_lib.escape(texto or "", quote=True)


def texto_puro(html):
    t = re.sub(r"<[^>]+>", " ", html or "")
    t = html_lib.unescape(t)
    t = re.sub(r"https?://\S+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def resumo(texto, limite=155):
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return corte + "…"


def slugificar(texto, limite=70):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    if len(t) > limite:
        t = t[:limite].rsplit("-", 1)[0]
    return t or "post"


def ler_data(valor, formato):
    try:
        return datetime.strptime(valor or "", formato).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def data_legivel(quando, codigo):
    if not quando:
        return ""
    mes = MESES[codigo][quando.month - 1]
    if codigo == "en":
        return f"{mes} {quando.day}, {quando.year}"
    return f"{quando.day} {mes} {quando.year}"


def imagem_absoluta(src):
    if not src:
        return None
    if src.startswith("/"):
        return DOMINIO + src
    return src if src.startswith(("http://", "https://")) else None


def primeira_imagem(html):
    m = re.search(r'<img[^>]+src="([^"]+)"', html or "", re.I)
    return imagem_absoluta(m.group(1)) if m else None


def html_de_texto(texto):
    return "".join(f"<p>{esc(par)}</p>" for par in (texto or "").split("\n\n") if par.strip())


def preparar_html(html):
    # imagens preguiçosas: o texto aparece antes, a página fica mais leve
    return re.sub(r"<img(?![^>]*loading=)", '<img loading="lazy" decoding="async"', html or "")


# ── notícias (feed.json) ────────────────────────────────────────────
def carregar_posts():
    """Lê feed.json e prepara cada notícia com suas versões por idioma.

    Cada post fica assim:
        slug, quando, atualizado, imagem, link_x
        versoes = {"en": {...}, "pt-BR": {...}?, "es": {...}?}
    onde cada versão tem titulo, html, resumo, descricao, imagem.
    O inglês (título da Issue + "Texto do post") sempre existe; português e
    espanhol só quando a Issue traz título E texto traduzidos.
    """
    arq = RAIZ / "feed.json"
    try:
        brutos = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(brutos, list):
        return []

    posts, usados = [], set()
    for p in brutos:
        titulo = (p.get("titulo") or "").strip()
        if not titulo:
            continue
        html_en = p.get("html") or html_de_texto(p.get("texto"))
        corpo = texto_puro(html_en)
        quando = ler_data(p.get("criado"), "%Y-%m-%dT%H:%M:%SZ") or ler_data(p.get("data"), "%d/%m/%Y %H:%M UTC")
        atualizado = ler_data(p.get("atualizado"), "%Y-%m-%dT%H:%M:%SZ") or quando

        # o slug junta data + título + começo do texto em inglês: títulos curtos
        # ("Confirmed!") sozinhos não dizem nada ao Google. A data de criação da
        # Issue nunca muda, e o mesmo slug serve às três línguas.
        palavras = " ".join(corpo.split()[:8])
        prefixo = quando.strftime("%Y%m%d") if quando else ""
        slug = slugificar(f"{prefixo} {titulo} {palavras}")
        base, n = slug, 2
        while slug in usados:
            slug, n = f"{base}-{n}", n + 1
        usados.add(slug)

        imagem = primeira_imagem(html_en) or imagem_absoluta(p.get("imagem"))
        versoes = {"en": {"titulo": titulo, "html": preparar_html(html_en),
                          "resumo": resumo(corpo), "descricao": resumo(corpo, 155)}}

        for cod, suf in SUFIXO_POST.items():
            t_tr = (p.get(f"titulo_{suf}") or "").strip()
            h_tr = p.get(f"html_{suf}") or html_de_texto(p.get(f"texto_{suf}"))
            if not (t_tr and texto_puro(h_tr)):
                continue
            # tradução sem imagem: reaproveita a imagem principal no topo
            if imagem and "<img" not in h_tr:
                h_tr = f'<p><img src="{esc(imagem)}" alt=""></p>\n' + h_tr
            c_tr = texto_puro(h_tr)
            versoes[cod] = {"titulo": t_tr, "html": preparar_html(h_tr),
                            "resumo": resumo(c_tr), "descricao": resumo(c_tr, 155)}

        link = p.get("link") or ""
        posts.append({
            "slug": slug,
            "quando": quando,
            "atualizado": atualizado,
            "imagem": imagem,
            "link_x": link if re.match(r"^https?://(www\.)?(x|twitter)\.com/", link) else None,
            "versoes": versoes,
        })
    posts.sort(key=lambda q: q["quando"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return posts


def versao(post, cod):
    """(código efetivo, versão): a do idioma pedido ou, se não houver, a inglesa."""
    if cod in post["versoes"]:
        return cod, post["versoes"][cod]
    return "en", post["versoes"]["en"]


def rel_post(post, cod):
    efetivo, _ = versao(post, cod)
    return f"{caminho(efetivo, 'noticias')}/{post['slug']}"


def url_post(post, cod):
    return url_rel(rel_post(post, cod))


def link_post(post, cod, prefixo):
    return f"{prefixo}{rel_post(post, cod)}/"


def atributo_lang(post, cod):
    """lang="en" num card em inglês dentro de página pt/es (leitor de tela pronuncia certo)."""
    efetivo, _ = versao(post, cod)
    return f' lang="{IDIOMAS[efetivo][1]}"' if efetivo != cod else ""


def cartao_feed(post, prefixo, cod, textos):
    """Card do Plantão (página de notícias): miniatura, resumo e link para a matéria."""
    _, v = versao(post, cod)
    link = link_post(post, cod, prefixo)
    thumb = ""
    if post["imagem"]:
        thumb = (f'<a class="post-auto__thumb" href="{link}" tabindex="-1" aria-hidden="true">'
                 f'<img src="{esc(post["imagem"])}" alt="" loading="lazy" decoding="async"></a>')
    acoes = f'<a href="{link}">{textos.get("ul04", "")}</a>'
    if post["link_x"]:
        acoes += f'<a href="{esc(post["link_x"])}" target="_blank" rel="noopener">{textos.get("fd01", "")}</a>'
    classe = "post-auto post-auto--img" if thumb else "post-auto"
    iso = post["quando"].isoformat() if post["quando"] else ""
    return (f'      <article class="{classe}"{atributo_lang(post, cod)}>{thumb}'
            f'<time datetime="{iso}">{data_legivel(post["quando"], cod)}</time>'
            f'<h4><a href="{link}">{esc(v["titulo"])}</a></h4>'
            f'<p>{esc(v["resumo"])}</p>'
            f'<div class="post-auto__acoes">{acoes}</div></article>')


def cartao_home(post, prefixo, cod, textos, destaque=False):
    _, v = versao(post, cod)
    link = link_post(post, cod, prefixo)
    img = (f'<img class="noticia__img" src="{esc(post["imagem"])}" alt="" loading="lazy" decoding="async">'
           if post["imagem"] else "")
    classe = "noticia revela tilt" + (" noticia--destaque" if destaque else "")
    return (f'    <article class="{classe}"{atributo_lang(post, cod)}><a class="noticia-link" href="{link}">{img}'
            f'<span class="noticia__risco"></span>'
            f'<span class="noticia__meta">{data_legivel(post["quando"], cod)}</span>'
            f'<h3>{esc(v["titulo"])}</h3><p>{esc(v["resumo"])}</p>'
            f'<span class="noticia__ler">{textos.get("ul04", "")}</span></a></article>')


def item_lista(post, prefixo, cod):
    _, v = versao(post, cod)
    return (f'      <li{atributo_lang(post, cod)}><a href="{link_post(post, cod, prefixo)}">'
            f'<time>{data_legivel(post["quando"], cod)}</time>{esc(v["titulo"])}</a></li>')


def arquivo_html(posts, prefixo, cod, textos):
    """Lista compacta das notícias mais antigas: nenhuma sai do site."""
    antigos = posts[CARDS_NOTICIAS:]
    if not antigos:
        return ""
    itens = "\n".join(item_lista(p, prefixo, cod) for p in antigos)
    return (f'    <div class="arquivo">\n      <p class="painel__titulo">{textos.get("ar09", "")}</p>\n'
            f'      <ul class="artigo__relacionadas">\n{itens}\n      </ul>\n    </div>')


def contagem():
    falta = LANCAMENTO - datetime.now(timezone.utc)
    if falta.total_seconds() <= 0:
        return "00", "00", "00"
    return (str(falta.days),
            str(falta.seconds // 3600).zfill(2),
            str(falta.seconds % 3600 // 60).zfill(2))


# ── dados estruturados ──────────────────────────────────────────────
def jsonld(obj):
    corpo = json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{corpo}\n</script>'


def jsonld_faq(textos):
    perguntas = []
    for i in range(134, 148, 2):
        q, a = textos.get(f"t{i}"), textos.get(f"t{i + 1}")
        if q and a:
            perguntas.append({"@type": "Question", "name": texto_puro(q),
                              "acceptedAnswer": {"@type": "Answer", "text": texto_puro(a)}})
    if not perguntas:
        return ""
    return jsonld({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": perguntas})


def organizacao(cod):
    return {"@type": "Organization", "name": NOME_SITE, "url": url(cod, "sobre"),
            "logo": {"@type": "ImageObject", "url": DOMINIO + "/og-image-en.png"}}


def jsonld_artigo(post, cod, textos):
    _, v = versao(post, cod)
    endereco = url_post(post, cod)
    obj = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": v["titulo"][:110],
        "description": v["descricao"],
        "mainEntityOfPage": endereco,
        "url": endereco,
        "inLanguage": IDIOMAS[cod][1],
        "author": organizacao(cod),
        "publisher": organizacao(cod),
        "image": [post["imagem"] or DOMINIO + "/og-image-en.png"],
    }
    if post["quando"]:
        obj["datePublished"] = post["quando"].isoformat()
        obj["dateModified"] = (post["atualizado"] or post["quando"]).isoformat()
    migalhas = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": NOME_SITE, "item": url(cod, "home")},
            {"@type": "ListItem", "position": 2, "name": textos.get("nav02", "News"),
             "item": url(cod, "noticias")},
            {"@type": "ListItem", "position": 3, "name": v["titulo"], "item": endereco},
        ]}
    return jsonld(obj) + "\n" + jsonld(migalhas)


# ── idioma: hreflang e seletor ──────────────────────────────────────
def bloco_hreflang(alternativas):
    """alternativas: {codigo: rel}. Só versões que existem de verdade entram."""
    linhas = []
    for cod, rel in alternativas.items():
        hl, padrao = IDIOMAS[cod][1], IDIOMAS[cod][4]
        linhas.append(f'<link rel="alternate" hreflang="{hl}" href="{url_rel(rel)}">')
        if padrao:
            linhas.append(f'<link rel="alternate" hreflang="x-default" href="{url_rel(rel)}">')
    return "\n".join(linhas)


def links_idioma(atual, alternativas, prefixo, classe_ativa="idioma-atual"):
    itens = []
    for cod, (_, hl, _, rotulo, _, _) in IDIOMAS.items():
        rel = alternativas.get(cod)
        if rel is None:               # sem tradução: leva à página de notícias do idioma
            rel = caminho(cod, "noticias")
        destino = (prefixo + (rel + "/" if rel else "")) or "./"
        classe = classe_ativa if cod == atual else ""
        aria = ' aria-current="true"' if cod == atual else ""
        itens.append(f'<a class="{classe}" href="{destino}" hreflang="{hl}" lang="{hl}"{aria}>{rotulo}</a>')
    return itens


def alternativas_pagina(pagina):
    return {cod: caminho(cod, pagina) for cod in IDIOMAS}


def alternativas_post(post):
    return {cod: rel_post(post, cod) for cod in IDIOMAS if cod in post["versoes"]}


# ── montagem de uma página ──────────────────────────────────────────
def montar_pagina(cabeca, rodape, corpo, base, textos, cod, pagina_nav, rel, extras,
                  alternativas=None):
    """Junta cabeça + corpo + rodapé e troca os marcadores.

    rel           caminho da página a partir da raiz ("" para a home em inglês)
    pagina_nav    qual item do menu fica marcado (home, noticias, mapa)
    extras        marcadores gerados (conteúdo das notícias etc.) — trocados por último,
                  para que o texto de um post nunca seja confundido com um marcador
    alternativas  {codigo: rel} das versões em outros idiomas (padrão: a mesma página)
    """
    hl, locale = IDIOMAS[cod][1], IDIOMAS[cod][2]
    alternativas = alternativas or alternativas_pagina(pagina_nav)
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

    prefixo = "../" * (len(rel.split("/")) if rel else 0)
    atual = {p: (' aria-current="page"' if p == pagina_nav else "") for p in PAGINAS_SITE}
    casa = caminho(cod, "home")

    padrao = {
        "__ogtype__": "website",
        "__ogimage_url__": DOMINIO + "/og-image-%s.png" % cod.split("-")[0],
        "__hreflang__": bloco_hreflang(alternativas),
        "__jsonld_extra__": "",
    }
    padrao.update({k: v for k, v in extras.items() if k in padrao})

    pasta = IDIOMAS[cod][0]
    rss = f"{DOMINIO}/" + (f"{pasta}/" if pasta else "") + "feed.xml"

    html = (html
            .replace("{{__lang__}}", hl)
            .replace("{{__locale__}}", locale)
            .replace("{{__canonical__}}", url_rel(rel))
            .replace("{{__siteroot__}}", url(cod, "home"))
            .replace("{{__rss__}}", rss)
            .replace("{{__base_url__}}", DOMINIO + "/")
            .replace("{{__base__}}", prefixo)
            .replace("{{__ogimage__}}", "og-image-%s.png" % cod.split("-")[0])
            .replace("{{__ebookcapa__}}", "ebook-capa-%s.png" % cod.split("-")[0])
            .replace("{{__seletor__}}",
                     '  <nav class="seletor-idioma" aria-label="Idioma / Language">\n    '
                     + "\n    ".join(links_idioma(cod, alternativas, prefixo)) + "\n  </nav>")
            .replace("{{__idiomas_menu__}}", "".join(links_idioma(cod, alternativas, prefixo)))
            .replace("{{__ebook_link__}}", IDIOMAS[cod][5])
            .replace("{{__home__}}", (prefixo + (casa + "/" if casa else "")) or "./")
            .replace("{{__news__}}", prefixo + caminho(cod, "noticias") + "/")
            .replace("{{__map__}}", prefixo + caminho(cod, "mapa") + "/")
            .replace("{{__at_home__}}", atual["home"])
            .replace("{{__at_news__}}", atual["noticias"])
            .replace("{{__at_map__}}", atual["mapa"]))
    for pagina in INSTITUCIONAIS:
        html = html.replace("{{__link_%s__}}" % pagina, prefixo + caminho(cod, pagina) + "/")

    m = re.search(r'<div class="footer-social">([\s\S]*?)</div>', html)
    html = html.replace("{{__social_menu__}}",
                        '<div class="menu-social">%s</div>' % m.group(1) if m else "")

    # marcadores gerados: primeiro os de estrutura, por último o conteúdo dos posts
    for chave, valor in list(padrao.items()) + [(k, v) for k, v in extras.items() if k not in padrao]:
        html = html.replace("{{%s}}" % chave, valor(prefixo) if callable(valor) else valor)

    # bloco de anúncio sem ID (data-ad-slot vazio) sairia como uma caixa tracejada
    # vazia na página: some do HTML até o bloco ser criado no AdSense
    html = re.sub(r'<div class="anuncio[^"]*" data-anuncio="\w+">(?:(?!</div>).)*?'
                  r'data-ad-slot=""(?:(?!</div>).)*?</div>\s*', "", html, flags=re.S)

    restantes = set(re.findall(r"\{\{__[^}]+\}\}|\{\{[a-z]+\d+\}\}|\{\{inst_[^}]+\}\}", html))
    if restantes:
        print(f"  ! {rel or '/'}: marcadores não substituídos: {restantes}")

    destino = SAIDA / rel if rel else SAIDA
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "index.html").write_text(html, encoding="utf-8")
    return faltando


def extras_comuns(posts, cod, textos):
    """Faixa do topo e barra "última notícia", presentes em todas as páginas."""
    if not posts:
        return {"__ticker_posts__": "",
                "__ultima_titulo__": textos.get("t009", ""),
                "__ultima_link__": lambda pref, cod=cod: pref + caminho(cod, "noticias") + "/"}
    ultima = posts[0]
    return {
        "__ticker_posts__": "\n    ".join(
            f"<span>◆ {esc(versao(p, cod)[1]['titulo'])}</span>" for p in posts[:3]),
        "__ultima_titulo__": esc(versao(ultima, cod)[1]["titulo"]),
        "__ultima_link__": lambda pref, ultima=ultima, cod=cod: link_post(ultima, cod, pref),
    }


# ── RSS e sitemaps ──────────────────────────────────────────────────
def data_rss(quando):
    return format_datetime(quando or datetime.now(timezone.utc))


def gerar_rss(posts, cod, textos):
    """feed.xml do idioma: versões traduzidas quando existem, senão a inglesa."""
    itens = []
    for post in posts[:50]:
        efetivo, v = versao(post, cod)
        link = url_post(post, cod)
        imagem = ""
        if post["imagem"]:
            imagem = f'\n      <media:content url="{esc(post["imagem"])}" medium="image"/>'
        conteudo = v["html"].replace("]]>", "]]]]><![CDATA[>")
        itens.append(f"""    <item>
      <title>{esc(v["titulo"])}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{data_rss(post["quando"])}</pubDate>
      <dc:creator>{NOME_SITE}</dc:creator>
      <dc:language>{IDIOMAS[efetivo][1]}</dc:language>
      <description>{esc(v["resumo"])}</description>
      <content:encoded><![CDATA[{conteudo}]]></content:encoded>{imagem}
    </item>""")
    pasta = IDIOMAS[cod][0]
    proprio = f"{DOMINIO}/" + (f"{pasta}/" if pasta else "") + "feed.xml"
    ultimo = data_rss(posts[0]["quando"]) if posts else data_rss(None)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>{esc(textos.get("t001", NOME_SITE))}</title>
    <link>{url(cod, "noticias")}</link>
    <description>{esc(textos.get("meta_desc", ""))}</description>
    <language>{IDIOMAS[cod][1]}</language>
    <lastBuildDate>{ultimo}</lastBuildDate>
    <atom:link href="{proprio}" rel="self" type="application/rss+xml"/>
    <image><url>{DOMINIO}/og-image-{cod.split("-")[0]}.png</url><title>{NOME_SITE}</title><link>{url(cod, "home")}</link></image>
{chr(10).join(itens)}
  </channel>
</rss>
"""


def gerar_news_sitemap(posts):
    """Sitemap do Google Notícias: só matérias das últimas 48 horas (regra do Google)."""
    limite = datetime.now(timezone.utc) - timedelta(hours=48)
    urls = []
    for post in posts:
        if not post["quando"] or post["quando"] < limite:
            continue
        for cod in post["versoes"]:
            v = post["versoes"][cod]
            urls.append(f"""  <url>
    <loc>{url_post(post, cod)}</loc>
    <news:news>
      <news:publication><news:name>{NOME_SITE}</news:name><news:language>{IDIOMA_NEWS[cod]}</news:language></news:publication>
      <news:publication_date>{post["quando"].isoformat()}</news:publication_date>
      <news:title>{esc(v["titulo"])}</news:title>
    </news:news>
  </url>""")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
            + "\n".join(urls) + ("\n" if urls else "") + "</urlset>\n")


def gerar_sitemap(posts, hoje):
    ultima = posts[0]["quando"].strftime("%Y-%m-%d") if posts and posts[0]["quando"] else hoje
    urls = ""
    for cod in IDIOMAS:
        for pagina in PAGINAS_SITE:
            alt = "".join(
                f'\n    <xhtml:link rel="alternate" hreflang="{IDIOMAS[o][1]}" href="{url(o, pagina)}"/>'
                for o in IDIOMAS)
            mod = ultima if pagina in ("home", "noticias") else hoje
            urls += f"\n  <url><loc>{url(cod, pagina)}</loc><lastmod>{mod}</lastmod>{alt}\n  </url>"
    for post in posts:
        mod = (post["atualizado"] or post["quando"])
        mod = mod.strftime("%Y-%m-%d") if mod else hoje
        alternativas = alternativas_post(post)
        for cod in post["versoes"]:
            alt = ""
            if len(alternativas) > 1:
                alt = "".join(
                    f'\n    <xhtml:link rel="alternate" hreflang="{IDIOMAS[o][1]}" href="{url_rel(r)}"/>'
                    for o, r in alternativas.items())
            urls += f"\n  <url><loc>{url_post(post, cod)}</loc><lastmod>{mod}</lastmod>{alt}\n  </url>"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + urls + "\n</urlset>\n")



# ── mapa de Leonida ─────────────────────────────────────────────────
def carregar_mapa():
    """Lê o mapa recriado (mapa/leonida.svg + leonida.json) e mapa/pontos.json."""
    try:
        info = json.loads((PASTA_MAPA / "leonida.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("  ! mapa/leonida.json ausente — rode: python mapa/recriar_mapa.py")
        return None
    if not (PASTA_MAPA / "leonida.svg").exists():
        print("  ! mapa/leonida.svg ausente — rode: python mapa/recriar_mapa.py")
        return None
    try:
        dados = json.loads((PASTA_MAPA / "pontos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  ! mapa/pontos.json inválido ({exc}) — mapa sem pontos")
        dados = {}
    return {"info": info, "pontos": dados.get("pontos", []), "rotulos": dados.get("rotulos", [])}


def texto_idioma(valor, cod):
    """Campo de ponto: texto simples ou {"en": ..., "pt-BR": ..., "es": ...}."""
    if isinstance(valor, dict):
        return valor.get(cod) or valor.get("en") or next(iter(valor.values()), "")
    return valor or ""


def config_mapa(mapa, cod, textos, prefixo):
    pontos = []
    for p in mapa["pontos"]:
        try:
            item = {"id": str(p["id"]), "cat": p.get("cat", "marco"),
                    "x": float(p["x"]), "y": float(p["y"])}
        except (KeyError, TypeError, ValueError):
            print(f"  ! ponto do mapa ignorado (faltam id/x/y): {p}")
            continue
        if p.get("ficha"):
            item["ficha"] = p["ficha"]
        for campo in ("nome", "real", "desc"):
            if p.get(campo):
                item[campo] = texto_idioma(p[campo], cod)
        if p.get("tags"):
            item["tags"] = [texto_idioma(t, cod) for t in p["tags"]]
        if p.get("video"):
            item["video"] = str(p["video"])
            item["t"] = int(p.get("t") or 0)
        pontos.append(item)
    rotulos = []
    for r in mapa["rotulos"]:
        try:
            rotulos.append({"id": str(r["id"]), "tipo": r.get("tipo", "agua"),
                            "x": float(r["x"]), "y": float(r["y"]),
                            "nome": texto_idioma(r.get("nome"), cod)})
        except (KeyError, TypeError, ValueError):
            print(f"  ! rótulo do mapa ignorado (faltam id/x/y): {r}")
    versao = int((PASTA_MAPA / "leonida.svg").stat().st_mtime)     # evita cache velho após atualizar
    config = {
        "info": mapa["info"],
        "svg": f"{prefixo}map-data/leonida.svg?v={versao}",
        "pontos": pontos,
        "rotulos": rotulos,
        "textos": {"video": textos.get("mp06", ""), "copiar": textos.get("mp07", ""),
                   "copiado": textos.get("mp08", ""), "nada": textos.get("mp09", ""),
                   "editar": textos.get("mp12", ""), "quadrante": textos.get("mp19", "")},
    }
    return json.dumps(config, ensure_ascii=False).replace("</", "<\\/")


# ── o gerador ───────────────────────────────────────────────────────
def montar():
    cabeca = (PARTES / "cabeca.html").read_text(encoding="utf-8")
    rodape = (PARTES / "rodape.html").read_text(encoding="utf-8")
    base = json.loads((PASTA_IDIOMAS / "pt-BR.json").read_text(encoding="utf-8"))
    corpo_post = (PAGINAS / "noticia.html").read_text(encoding="utf-8")
    posts = carregar_posts()
    mapa = carregar_mapa()
    dias, horas, minutos = contagem()
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

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
    paginas_post = 0
    for cod, (pasta, hl, locale, rotulo, padrao, link_ebook) in IDIOMAS.items():
        arq = PASTA_IDIOMAS / f"{cod}.json"
        if not arq.exists():
            print(f"  ! idiomas/{cod}.json ausente — pulando {cod}")
            continue
        textos = dict(base)
        textos.update(json.loads(arq.read_text(encoding="utf-8")))

        # ── páginas fixas ──
        for pagina, (arquivo, _) in PAGINAS_SITE.items():
            corpo = (PAGINAS / arquivo).read_text(encoding="utf-8")
            rel = caminho(cod, pagina)
            extras = extras_comuns(posts, cod, textos)
            textos_pagina = textos
            if pagina == "home":
                extras["__cd_dias__"] = dias
                extras["__cd_horas__"] = horas
                extras["__cd_min__"] = minutos
                extras["__jsonld_extra__"] = jsonld_faq(textos)
                extras["__ultimas_home__"] = lambda pref, cod=cod, textos=textos: (
                    "\n".join(cartao_home(p, pref, cod, textos, destaque=(i == 0))
                              for i, p in enumerate(posts[:4]))
                    or f'    <p class="feed-vazio">{textos.get("t124", "")}</p>')
            elif pagina == "noticias":
                extras["__feed_html__"] = lambda pref, cod=cod, textos=textos: (
                    "\n".join(cartao_feed(p, pref, cod, textos) for p in posts[:CARDS_NOTICIAS])
                    or f'      <p class="feed-vazio">{textos.get("t124", "")}</p>')
                extras["__arquivo_html__"] = lambda pref, cod=cod, textos=textos: arquivo_html(
                    posts, pref, cod, textos)
            elif pagina == "mapa":
                extras["__mapa_config__"] = (
                    lambda pref, cod=cod, textos=textos: config_mapa(mapa, cod, textos, pref)
                    if mapa else "null")
            elif pagina in INSTITUCIONAIS:
                fonte = PASTA_INSTITUCIONAL / cod / f"{pagina}.html"
                if not fonte.exists():
                    fonte = PASTA_INSTITUCIONAL / "pt-BR" / f"{pagina}.html"
                titulo = textos.get(f"inst_{pagina}_t", pagina)
                descricao = textos.get(f"inst_{pagina}_d", "")
                textos_pagina = dict(textos)
                textos_pagina.update({
                    "t001": esc(f"{titulo} — {NOME_SITE}"),
                    "meta_desc": esc(descricao), "og_desc": esc(descricao), "tw_desc": esc(descricao),
                    "og_title": esc(f"{titulo} — {NOME_SITE}"), "tw_title": esc(f"{titulo} — {NOME_SITE}"),
                })
                extras["__inst_titulo__"] = esc(titulo)
                extras["__inst_html__"] = fonte.read_text(encoding="utf-8")
            faltando = montar_pagina(cabeca, rodape, corpo, base, textos_pagina, cod, pagina, rel, extras)
            total += 1
            aviso = f" ({len(faltando)} sem tradução)" if faltando else ""
            print(f"  ✓ {(rel + '/' if rel else '')}index.html{aviso}")

        # ── uma página por notícia, só nos idiomas em que ela existe ──
        for post in posts:
            if cod not in post["versoes"]:
                continue
            v = post["versoes"][cod]
            rel = rel_post(post, cod)
            endereco = url_post(post, cod)
            mesmo_idioma = [q for q in posts if q is not post and cod in q["versoes"]]
            outros = (mesmo_idioma + [q for q in posts if q is not post and cod not in q["versoes"]])[:5]
            extras = extras_comuns(posts, cod, textos)
            textos_post = dict(textos)
            # título, descrição e cartões de compartilhamento próprios de cada notícia
            textos_post.update({
                "t001": esc(f"{v['titulo']} — GTA VI | {NOME_SITE}"),
                "meta_desc": esc(v["descricao"]),
                "og_title": esc(v["titulo"]), "tw_title": esc(v["titulo"]),
                "og_desc": esc(v["descricao"]), "tw_desc": esc(v["descricao"]),
                "og_alt": esc(v["titulo"]),
            })
            extras.update({
                "__ogtype__": "article",
                "__ogimage_url__": esc(post["imagem"]) if post["imagem"] else DOMINIO + "/og-image-%s.png" % cod.split("-")[0],
                "__jsonld_extra__": jsonld_artigo(post, cod, textos),
                "__art_titulo__": esc(v["titulo"]),
                "__art_data__": data_legivel(post["quando"], cod),
                "__art_iso__": post["quando"].isoformat() if post["quando"] else "",
                "__art_share_url__": urllib.parse.quote(endereco, safe=""),
                "__art_share_titulo__": urllib.parse.quote(v["titulo"]),
                "__art_share_txt__": urllib.parse.quote(f"{v['titulo']} {endereco}"),
                "__art_link_x__": (f'<a class="painel__link" href="{esc(post["link_x"])}" target="_blank" '
                                   f'rel="noopener">{textos.get("fd01", "")}</a>') if post["link_x"] else "",
                "__art_relacionadas__": lambda pref, outros=outros, cod=cod: "\n".join(
                    item_lista(q, pref, cod) for q in outros),
                "__art_html__": v["html"],
            })
            montar_pagina(cabeca, rodape, corpo_post, base, textos_post, cod, "noticias", rel, extras,
                          alternativas=alternativas_post(post))
            total += 1
            paginas_post += 1

        # ── RSS do idioma ──
        destino_rss = SAIDA / pasta if pasta else SAIDA
        destino_rss.mkdir(parents=True, exist_ok=True)
        (destino_rss / "feed.xml").write_text(gerar_rss(posts, cod, textos), encoding="utf-8")

    if posts:
        traduzidas = sum(1 for p in posts for c in p["versoes"] if c != "en")
        print(f"  ✓ {paginas_post} página(s) de notícia ({len(posts)} em inglês, {traduzidas} traduzida(s))")
    print("  ✓ feed.xml, pt/feed.xml, es/feed.xml")

    for nome in ESTATICOS:
        if (RAIZ / nome).exists():
            shutil.copy(RAIZ / nome, SAIDA / nome)

    # mapa de Leonida recriado (vetor), e bibliotecas do próprio site
    if mapa:
        (SAIDA / "map-data").mkdir(exist_ok=True)
        if (PASTA_MAPA / "leonida.svg").exists():
            shutil.copy(PASTA_MAPA / "leonida.svg", SAIDA / "map-data" / "leonida.svg")
        velho = SAIDA / "map-data" / "original.webp"
        if velho.exists():
            velho.unlink()     # não usamos mais a visualização "Original"
        print("  ✓ map-data/ (mapa recriado)")
    if PASTA_VENDOR.is_dir():
        shutil.copytree(PASTA_VENDOR, SAIDA / "vendor")

    # imagens dos posts, baixadas pelo automacao/posts.py
    midia = RAIZ / "midia"
    if midia.is_dir():
        shutil.copytree(midia, SAIDA / "midia", dirs_exist_ok=True)
        print(f"  ✓ midia/ ({len(list(midia.iterdir()))} arquivo(s))")

    # sitemaps: o geral (com lastmod) e o do Google Notícias (últimas 48 h)
    (SAIDA / "sitemap.xml").write_text(gerar_sitemap(posts, hoje), encoding="utf-8")
    (SAIDA / "news-sitemap.xml").write_text(gerar_news_sitemap(posts), encoding="utf-8")
    (SAIDA / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}/sitemap.xml\n"
        f"Sitemap: {DOMINIO}/news-sitemap.xml\n", encoding="utf-8")
    print("  ✓ sitemap.xml, news-sitemap.xml, robots.txt")

    print(f"\n{total} páginas geradas em docs/. Faça commit e push.")


if __name__ == "__main__":
    sys.exit(montar())
