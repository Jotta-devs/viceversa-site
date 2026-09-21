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

import html as html_lib
import json
import re
import shutil
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timedelta, timezone
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


# ── notícias (feed.json) ────────────────────────────────────────────
LANCAMENTO = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)   # 19/11 00:00 em Brasília
PASTA_POSTS = "news"          # cada notícia vira /news/<slug>/ (os posts são escritos em inglês)
MESES = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "pt-BR": ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"],
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
}


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


def data_post(p):
    for campo, formato in (("criado", "%Y-%m-%dT%H:%M:%SZ"), ("data", "%d/%m/%Y %H:%M UTC")):
        try:
            return datetime.strptime(p.get(campo, ""), formato).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def data_legivel(quando, codigo):
    if not quando:
        return ""
    mes = MESES[codigo][quando.month - 1]
    if codigo == "en":
        return f"{mes} {quando.day}, {quando.year}"
    return f"{quando.day} {mes} {quando.year}"


def primeira_imagem(p):
    m = re.search(r'<img[^>]+src="([^"]+)"', p.get("html", ""), re.I)
    src = m.group(1) if m else p.get("imagem")
    if not src:
        return None
    if src.startswith("/"):
        return DOMINIO + src
    return src if src.startswith(("http://", "https://")) else None


def carregar_posts():
    """Lê feed.json e prepara cada notícia (slug, datas, resumo, imagem)."""
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
        corpo = texto_puro(p.get("html") or p.get("texto") or "")
        quando = data_post(p)
        # o slug junta título + começo do texto: títulos curtos ("Confirmed!")
        # sozinhos não dizem nada ao Google
        palavras = " ".join(corpo.split()[:8])
        # a data de criação da Issue não muda quando o post é editado: mantém o endereço estável
        prefixo = quando.strftime("%Y%m%d") if quando else ""
        slug = slugificar(f"{prefixo} {titulo} {palavras}")
        base, n = slug, 2
        while slug in usados:
            slug, n = f"{base}-{n}", n + 1
        usados.add(slug)
        html_corpo = p.get("html") or "".join(
            f"<p>{esc(par)}</p>" for par in (p.get("texto") or "").split("\n\n") if par.strip())
        # imagens preguiçosas: o texto aparece antes, a página fica mais leve
        html_corpo = re.sub(r"<img(?![^>]*loading=)", '<img loading="lazy" decoding="async"', html_corpo)
        posts.append({
            "titulo": titulo,
            "slug": slug,
            "quando": quando,
            "resumo": resumo(corpo),
            "descricao": resumo(corpo, 155),
            "imagem": primeira_imagem(p),
            "html": html_corpo,
            "link_x": p.get("link") if re.match(r"^https?://(x|twitter)\.com/", p.get("link") or "") else None,
        })
    posts.sort(key=lambda q: q["quando"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return posts


def url_post(post):
    return f"{DOMINIO}/{PASTA_POSTS}/{post['slug']}/"


def link_post(post, prefixo):
    return f"{prefixo}{PASTA_POSTS}/{post['slug']}/"


def cartao_feed(post, prefixo, codigo, textos):
    """Card do Plantão (página de notícias): miniatura, resumo e link para a matéria."""
    link = link_post(post, prefixo)
    thumb = ""
    if post["imagem"]:
        thumb = (f'<a class="post-auto__thumb" href="{link}" tabindex="-1" aria-hidden="true">'
                 f'<img src="{esc(post["imagem"])}" alt="" loading="lazy" decoding="async"></a>')
    acoes = f'<a href="{link}">{textos.get("ul04", "")}</a>'
    if post["link_x"]:
        acoes += f'<a href="{esc(post["link_x"])}" target="_blank" rel="noopener">{textos.get("fd01", "")}</a>'
    classe = "post-auto post-auto--img" if thumb else "post-auto"
    iso = post["quando"].isoformat() if post["quando"] else ""
    return (f'      <article class="{classe}">{thumb}'
            f'<time datetime="{iso}">{data_legivel(post["quando"], codigo)}</time>'
            f'<h4><a href="{link}">{esc(post["titulo"])}</a></h4>'
            f'<p>{esc(post["resumo"])}</p>'
            f'<div class="post-auto__acoes">{acoes}</div></article>')


def cartao_home(post, prefixo, codigo, textos, destaque=False):
    link = link_post(post, prefixo)
    img = (f'<img class="noticia__img" src="{esc(post["imagem"])}" alt="" loading="lazy" decoding="async">'
           if post["imagem"] else "")
    classe = "noticia revela tilt" + (" noticia--destaque" if destaque else "")
    return (f'    <article class="{classe}"><a class="noticia-link" href="{link}">{img}'
            f'<span class="noticia__risco"></span>'
            f'<span class="noticia__meta">{data_legivel(post["quando"], codigo)}</span>'
            f'<h3>{esc(post["titulo"])}</h3><p>{esc(post["resumo"])}</p>'
            f'<span class="noticia__ler">{textos.get("ul04", "")}</span></a></article>')


def contagem():
    falta = LANCAMENTO - datetime.now(timezone.utc)
    if falta.total_seconds() <= 0:
        return "00", "00", "00"
    return (str(falta.days),
            str(falta.seconds // 3600).zfill(2),
            str(falta.seconds % 3600 // 60).zfill(2))


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


def jsonld_artigo(post, textos_en):
    obj = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": post["titulo"][:110],
        "description": post["descricao"],
        "mainEntityOfPage": url_post(post),
        "url": url_post(post),
        "inLanguage": "en",
        "author": {"@type": "Organization", "name": "VICEVERSA", "url": DOMINIO + "/"},
        "publisher": {"@type": "Organization", "name": "VICEVERSA",
                      "logo": {"@type": "ImageObject", "url": DOMINIO + "/og-image-en.png"}},
        "image": [post["imagem"] or DOMINIO + "/og-image-en.png"],
    }
    if post["quando"]:
        obj["datePublished"] = obj["dateModified"] = post["quando"].isoformat()
    migalhas = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "VICEVERSA", "item": DOMINIO + "/"},
            {"@type": "ListItem", "position": 2, "name": textos_en.get("nav02", "News"),
             "item": url("en", "noticias")},
            {"@type": "ListItem", "position": 3, "name": post["titulo"], "item": url_post(post)},
        ]}
    return jsonld(obj) + "\n" + jsonld(migalhas)


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


def montar_pagina(cabeca, rodape, corpo, base, textos, cod, pagina_nav, rel, extras):
    """Junta cabeça + corpo + rodapé e troca os marcadores.

    rel         caminho da página a partir da raiz ("" para a home em inglês)
    pagina_nav  qual item do menu fica marcado (home, noticias, mapa)
    extras      marcadores gerados (conteúdo das notícias etc.) — trocados por último,
                para que o texto de um post nunca seja confundido com um marcador
    """
    hl, locale = IDIOMAS[cod][1], IDIOMAS[cod][2]
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
    canonical = f"{DOMINIO}/" + (f"{rel}/" if rel else "")

    padrao = {
        "__ogtype__": "website",
        "__ogimage_url__": DOMINIO + "/og-image-%s.png" % cod.split("-")[0],
        "__hreflang__": bloco_hreflang(pagina_nav),
        "__jsonld_extra__": "",
    }
    padrao.update({k: v for k, v in extras.items() if k in padrao})

    html = (html
            .replace("{{__lang__}}", hl)
            .replace("{{__locale__}}", locale)
            .replace("{{__canonical__}}", canonical)
            .replace("{{__siteroot__}}", url(cod, "home"))
            .replace("{{__base_url__}}", DOMINIO + "/")
            .replace("{{__base__}}", prefixo)
            .replace("{{__ogimage__}}", "og-image-%s.png" % cod.split("-")[0])
            .replace("{{__ebookcapa__}}", "ebook-capa-%s.png" % cod.split("-")[0])
            .replace("{{__seletor__}}",
                     '  <nav class="seletor-idioma" aria-label="Idioma / Language">\n    '
                     + "\n    ".join(links_idioma(cod, pagina_nav, prefixo)) + "\n  </nav>")
            .replace("{{__idiomas_menu__}}", "".join(links_idioma(cod, pagina_nav, prefixo)))
            .replace("{{__ebook_link__}}", IDIOMAS[cod][5])
            .replace("{{__home__}}", (prefixo + (casa + "/" if casa else "")) or "./")
            .replace("{{__news__}}", prefixo + caminho(cod, "noticias") + "/")
            .replace("{{__map__}}", prefixo + caminho(cod, "mapa") + "/")
            .replace("{{__at_home__}}", atual["home"])
            .replace("{{__at_news__}}", atual["noticias"])
            .replace("{{__at_map__}}", atual["mapa"]))

    m = re.search(r'<div class="footer-social">([\s\S]*?)</div>', html)
    html = html.replace("{{__social_menu__}}",
                        '<div class="menu-social">%s</div>' % m.group(1) if m else "")

    # marcadores gerados: primeiro os de estrutura, por último o conteúdo dos posts
    for chave, valor in list(padrao.items()) + [(k, v) for k, v in extras.items() if k not in padrao]:
        html = html.replace("{{%s}}" % chave, valor(prefixo) if callable(valor) else valor)

    restantes = set(re.findall(r"\{\{__[^}]+\}\}|\{\{[a-z]+\d+\}\}", html))
    if restantes:
        print(f"  ! {rel or '/'}: marcadores não substituídos: {restantes}")

    destino = SAIDA / rel if rel else SAIDA
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "index.html").write_text(html, encoding="utf-8")
    return faltando


def montar():
    cabeca = (PARTES / "cabeca.html").read_text(encoding="utf-8")
    rodape = (PARTES / "rodape.html").read_text(encoding="utf-8")
    base = json.loads((PASTA_IDIOMAS / "pt-BR.json").read_text(encoding="utf-8"))
    posts = carregar_posts()
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
    textos_por_idioma = {}
    for cod, (pasta, hl, locale, rotulo, padrao, link_ebook) in IDIOMAS.items():
        arq = PASTA_IDIOMAS / f"{cod}.json"
        if not arq.exists():
            print(f"  ! idiomas/{cod}.json ausente — pulando {cod}")
            continue
        textos = dict(base)
        textos.update(json.loads(arq.read_text(encoding="utf-8")))
        textos_por_idioma[cod] = textos

        for pagina, (arquivo, _) in PAGINAS_SITE.items():
            corpo = (PAGINAS / arquivo).read_text(encoding="utf-8")
            rel = caminho(cod, pagina)
            extras = extras_comuns(posts, cod, textos)
            if pagina == "home":
                extras["__cd_dias__"] = dias
                extras["__cd_horas__"] = horas
                extras["__cd_min__"] = minutos
                extras["__jsonld_extra__"] = jsonld_faq(textos)
                extras["__ultimas_home__"] = lambda pref, cod=cod, textos=textos: (
                    "\n".join(cartao_home(p, pref, cod, textos, destaque=(i == 0))
                              for i, p in enumerate(posts[:4]))
                    or f'    <p class="feed-vazio">{textos.get("t124", "")}</p>')
            if pagina == "noticias":
                extras["__feed_html__"] = lambda pref, cod=cod, textos=textos: (
                    "\n".join(cartao_feed(p, pref, cod, textos) for p in posts[:30])
                    or f'      <p class="feed-vazio">{textos.get("t124", "")}</p>')
            faltando = montar_pagina(cabeca, rodape, corpo, base, textos, cod, pagina, rel, extras)
            total += 1
            aviso = f" ({len(faltando)} sem tradução)" if faltando else ""
            print(f"  ✓ {(rel + '/' if rel else '')}index.html{aviso}")

    # uma página por notícia, em /news/<slug>/ (os posts são escritos em inglês)
    corpo_post = (PAGINAS / "noticia.html").read_text(encoding="utf-8")
    textos_en = textos_por_idioma.get("en", base)
    for i, post in enumerate(posts):
        outros = [q for q in posts if q is not post][:5]
        rel = f"{PASTA_POSTS}/{post['slug']}"
        endereco = url_post(post)
        titulo_q = urllib.parse.quote(post["titulo"])
        extras = extras_comuns(posts, "en", textos_en)
        textos = dict(textos_en)
        # título, descrição e cartões de compartilhamento próprios de cada notícia
        textos.update({
            "t001": esc(f"{post['titulo']} — GTA VI | VICEVERSA"),
            "meta_desc": esc(post["descricao"]),
            "og_title": esc(post["titulo"]), "tw_title": esc(post["titulo"]),
            "og_desc": esc(post["descricao"]), "tw_desc": esc(post["descricao"]),
            "og_alt": esc(post["titulo"]),
        })
        extras.update({
            "__ogtype__": "article",
            "__ogimage_url__": esc(post["imagem"]) if post["imagem"] else DOMINIO + "/og-image-en.png",
            "__hreflang__": f'<link rel="alternate" hreflang="en" href="{endereco}">',
            "__jsonld_extra__": jsonld_artigo(post, textos_en),
            "__art_titulo__": esc(post["titulo"]),
            "__art_data__": data_legivel(post["quando"], "en"),
            "__art_iso__": post["quando"].isoformat() if post["quando"] else "",
            "__art_share_url__": urllib.parse.quote(endereco, safe=""),
            "__art_share_titulo__": titulo_q,
            "__art_share_txt__": urllib.parse.quote(f"{post['titulo']} {endereco}"),
            "__art_link_x__": (f'<a class="painel__link" href="{esc(post["link_x"])}" target="_blank" '
                               f'rel="noopener">{textos_en.get("fd01", "")}</a>') if post["link_x"] else "",
            "__art_relacionadas__": lambda pref, outros=outros: "\n".join(
                f'      <li><a href="{link_post(q, pref)}"><time>{data_legivel(q["quando"], "en")}</time>'
                f'{esc(q["titulo"])}</a></li>' for q in outros),
            "__art_html__": post["html"],
        })
        montar_pagina(cabeca, rodape, corpo_post, base, textos, "en", "noticias", rel, extras)
        total += 1
    if posts:
        print(f"  ✓ {PASTA_POSTS}/<slug>/index.html ({len(posts)} notícia(s) com página própria)")

    for nome in ESTATICOS:
        if (RAIZ / nome).exists():
            shutil.copy(RAIZ / nome, SAIDA / nome)

    # imagens dos posts, baixadas pelo automacao/posts.py
    midia = RAIZ / "midia"
    if midia.is_dir():
        shutil.copytree(midia, SAIDA / "midia", dirs_exist_ok=True)
        print(f"  ✓ midia/ ({len(list(midia.iterdir()))} arquivo(s))")

    # sitemap com lastmod: diz ao Google o que mudou e quando
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
        mod = post["quando"].strftime("%Y-%m-%d") if post["quando"] else hoje
        urls += f"\n  <url><loc>{url_post(post)}</loc><lastmod>{mod}</lastmod></url>"
    (SAIDA / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + urls + "\n</urlset>\n", encoding="utf-8")
    (SAIDA / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}/sitemap.xml\n", encoding="utf-8")

    print(f"\n{total} páginas geradas em docs/. Faça commit e push.")


def extras_comuns(posts, cod, textos):
    """Faixa do topo e barra "última notícia", presentes em todas as páginas."""
    if not posts:
        return {"__ticker_posts__": "",
                "__ultima_titulo__": textos.get("t009", ""),
                "__ultima_link__": lambda pref, cod=cod: pref + caminho(cod, "noticias") + "/"}
    ultima = posts[0]
    return {
        "__ticker_posts__": "\n    ".join(f"<span>◆ {esc(p['titulo'])}</span>" for p in posts[:3]),
        "__ultima_titulo__": esc(ultima["titulo"]),
        "__ultima_link__": lambda pref, ultima=ultima: link_post(ultima, pref),
    }


if __name__ == "__main__":
    sys.exit(montar())
