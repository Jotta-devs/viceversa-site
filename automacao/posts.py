"""
VICEVERSA — posts a partir de Issues do GitHub
===============================================
Transforma Issues rotuladas como "post" nos itens do painel de notícias do site.

    você abre uma Issue  ->  workflow roda  ->  feed.json  ->  site atualizado

Custo: ZERO. Não usa a API do X (que cobra por leitura), não usa IA. Fala apenas
com a própria API do GitHub, usando o GITHUB_TOKEN que o Actions fornece de graça
em todo workflow. Actions é gratuito e ilimitado em repositório público.

Como escrever um post
---------------------
Abra uma Issue no repositório com o rótulo `post`:

    Título da Issue  ->  título do card no site
    Corpo da Issue   ->  texto do card

O formulário "Novo post" também tem campos opcionais de título e texto em
português e em espanhol. Quando preenchidos, a notícia ganha página própria em
/pt/noticias/... e /es/noticias/..., ligada à versão em inglês.

O link do tweet (campo "Link do post no X", ou uma linha `X: https://...` no
texto) vira o botão "Ver no X" do card. Sem link, não há botão — o leitor nunca
é mandado para o GitHub.

Feche a Issue para tirar o post do site. Reabra para trazê-lo de volta.

Todas as Issues abertas entram no feed, sem limite: cada notícia tem página
própria e endereço permanente, e apagar as antigas quebraria links já
indexados pelo Google e compartilhados nas redes.
"""

import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from formulario import ler_post

RAIZ = Path(__file__).parent
REPO = RAIZ.parent
ARQ_FEED = REPO / "feed.json"

ROTULO = "post"      # só Issues com este rótulo viram publicação


def log(msg):
    print(f"[viceversa-posts] {msg}", flush=True)


def buscar_issues():
    """Lê as Issues abertas com o rótulo, pela API do GitHub (grátis)."""
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repositorio:
        log("GITHUB_REPOSITORY ausente — rodando fora do Actions?")
        return []

    # a API entrega no máximo 100 por página: percorre todas
    todas, pagina = [], 1
    while True:
        url = (f"https://api.github.com/repos/{repositorio}/issues"
               f"?state=open&labels={ROTULO}&per_page=100&page={pagina}"
               f"&sort=created&direction=desc")
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "viceversa-bot",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            dados = json.loads(r.read().decode("utf-8"))
        todas.extend(dados)
        if len(dados) < 100 or pagina >= 50:
            break
        pagina += 1

    # a API devolve pull requests junto com issues; descarta os PRs
    return [i for i in todas if "pull_request" not in i]


TAGS_PERMITIDAS = {
    "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "del", "ins", "mark",
    "code", "pre", "blockquote", "ul", "ol", "li", "a", "img",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td", "sup", "sub", "span", "div",
}


def sanitizar(html):
    """Remove o que não deve rodar numa página pública.

    O conteúdo vem de colaboradores de confiança, mas Markdown aceita HTML
    embutido — sem esta limpeza, uma Issue conseguiria injetar script no site.
    """
    # blocos executáveis inteiros, com conteúdo
    html = re.sub(r"<(script|style|iframe|object|embed|form)\b[\s\S]*?</\1\s*>",
                  "", html, flags=re.I)
    html = re.sub(r"<(script|style|iframe|object|embed|form)\b[^>]*/?>", "", html, flags=re.I)
    # atributos de evento (onclick, onerror...) e URLs javascript:
    html = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html, flags=re.I)
    html = re.sub(r"(href|src)\s*=\s*([\"']?)\s*javascript:[^\"'>\s]*\2",
                  r'\1="#"', html, flags=re.I)

    # qualquer tag fora da lista vira texto (mantém o conteúdo, tira a marcação)
    def filtrar(m):
        tag = m.group(1).lower()
        return m.group(0) if tag in TAGS_PERMITIDAS else ""
    html = re.sub(r"</?([a-zA-Z][\w-]*)\b[^>]*>", filtrar, html)
    return html.strip()


def absolutizar(html):
    """Converte URLs relativas em absolutas apontando para o GitHub.

    Sem isto, um src="/user-attachments/..." faria o navegador procurar a
    imagem em vvviceversa.com/user-attachments/... — que não existe (404).
    """
    def corrigir(m):
        atributo, aspas, url = m.group(1), m.group(2), m.group(3)
        if url.startswith(("http://", "https://", "#", "data:", "mailto:")):
            return m.group(0)
        if url.startswith("//"):
            return f'{atributo}={aspas}https:{url}{aspas}'
        if url.startswith("/"):
            return f'{atributo}={aspas}https://github.com{url}{aspas}'
        # caminho solto (nome de arquivo): assume anexo de Issue
        return f'{atributo}={aspas}https://github.com/user-attachments/assets/{url}{aspas}'

    return re.sub(r'(src|href)=(["\'])([^"\']*)\2', corrigir, html, flags=re.I)


PASTA_MIDIA = REPO / "midia"
EXTENSOES = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
             "image/webp": ".webp", "image/avif": ".avif"}


def baixar_imagens(html, token):
    """Baixa as imagens e passa a servi-las do próprio site.

    As imagens anexadas em Issues ficam em URLs ASSINADAS e TEMPORÁRIAS
    (private-user-images.githubusercontent.com/...?jwt=...). Elas funcionam por
    algumas horas e depois retornam 404 — por isso não dá para apontar o site
    para elas. Aqui elas são baixadas enquanto o link ainda é válido e salvas
    em midia/, que o montar.py copia para o site publicado.
    """
    PASTA_MIDIA.mkdir(exist_ok=True)

    def trocar(m):
        url = m.group(2)
        if url.startswith("/midia/"):
            return m.group(0)                       # já foi baixada antes
        if not url.startswith(("http://", "https://")):
            return m.group(0)
        try:
            # SEM cabeçalho Authorization, de propósito: o github.com redireciona
            # para uma URL da S3 que já vem assinada, e o Python repassaria o
            # token no redirecionamento. A S3 recusa (HTTP 400) quando recebe
            # dois mecanismos de autenticação juntos. Anônimo funciona: os anexos
            # de Issues de repositório público são acessíveis sem login.
            req = urllib.request.Request(url, headers={
                "User-Agent": "viceversa-bot",
                "Accept": "image/*,*/*",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                dados = r.read()
                tipo = (r.headers.get("Content-Type") or "").split(";")[0].strip()
        except Exception as exc:
            log(f"não consegui baixar uma imagem ({exc}); mantendo a URL original.")
            return m.group(0)

        if not dados:
            return m.group(0)
        ext = EXTENSOES.get(tipo, "")
        if not ext:
            ext = os.path.splitext(urllib.parse.urlparse(url).path)[1][:5] or ".img"
        nome = hashlib.sha1(dados).hexdigest()[:16] + ext
        destino = PASTA_MIDIA / nome
        if not destino.exists():
            destino.write_bytes(dados)
            log(f"imagem salva: midia/{nome} ({len(dados)//1024} KB)")
        # caminho absoluto a partir da raiz do site: funciona em qualquer página
        return f'{m.group(1)}="/midia/{nome}"'

    return re.sub(r'(src)="([^"]*)"', trocar, html, flags=re.I)


def renderizar_markdown(texto, repositorio, token):
    """Converte para HTML usando o MESMO renderizador do preview do GitHub."""
    if not texto.strip():
        return ""
    # modo "markdown" (e não "gfm" com context): o modo gfm reescreve URLs que
    # apontam para o github.com, deixando-as relativas — e aí o navegador
    # procura a imagem no domínio do site, resultando em 404.
    corpo = json.dumps({"text": texto, "mode": "markdown"}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/markdown", data=corpo, method="POST", headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "viceversa-bot",
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        })
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    # baixa as imagens ENQUANTO os links assinados ainda são válidos
    return sanitizar(baixar_imagens(absolutizar(html), token))


def extrair_imagem(corpo):
    """Pega a primeira imagem anexada na Issue (markdown ou <img>)."""
    corpo = corpo or ""
    m = re.search(r"!\[[^\]]*\]\((https?://[^\s)]+)\)", corpo)
    if not m:
        m = re.search(r'<img[^>]+src="(https?://[^"]+)"', corpo, re.I)
    return m.group(1) if m else None


def main():
    repositorio = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN")
    try:
        issues = buscar_issues()
    except Exception as exc:
        log(f"não consegui ler as Issues: {exc}")
        return 1

    log(f"{len(issues)} Issue(s) com o rótulo '{ROTULO}'.")

    itens = []
    for issue in issues:
        campos = ler_post(issue.get("body"))
        texto = campos["texto"]
        if not texto:
            log(f"Issue #{issue['number']} sem corpo; pulando.")
            continue
        criado = issue.get("created_at", "")
        try:
            quando = datetime.strptime(criado, "%Y-%m-%dT%H:%M:%SZ")
            data = quando.strftime("%d/%m/%Y %H:%M UTC")
        except ValueError:
            data = criado

        item = {
            "data": data,
            "criado": criado,
            "atualizado": issue.get("updated_at", ""),
            "titulo": (issue.get("title") or "").strip(),
            "texto": texto,          # versão em texto puro (reserva)
        }
        # HTML igual ao preview da Issue: parágrafos, negrito, listas,
        # títulos e as imagens na posição original.
        try:
            html = renderizar_markdown(texto, repositorio, token)
            if html:
                item["html"] = html
        except Exception as exc:
            log(f"Issue #{issue['number']}: falha ao renderizar ({exc}); "
                "usando texto puro.")

        # versões traduzidas (opcionais): só entram se tiverem título E texto
        for sufixo in ("pt", "es"):
            titulo_tr = campos[f"titulo_{sufixo}"]
            texto_tr = campos[f"texto_{sufixo}"]
            if not (titulo_tr and texto_tr):
                continue
            item[f"titulo_{sufixo}"] = titulo_tr
            item[f"texto_{sufixo}"] = texto_tr
            try:
                html_tr = renderizar_markdown(texto_tr, repositorio, token)
                if html_tr:
                    item[f"html_{sufixo}"] = html_tr
            except Exception as exc:
                log(f"Issue #{issue['number']}: falha ao renderizar {sufixo} ({exc}).")

        # o botão "Ver no X" só existe se houver mesmo um link do X.
        # Sem ele, nenhum botão — nunca apontamos o leitor para o GitHub.
        if campos["link"]:
            item["link"] = campos["link"]
        # se a renderização falhar, ainda mostramos a imagem pelo campo antigo
        if "html" not in item:
            imagem = extrair_imagem(texto)
            if imagem:
                item["imagem"] = imagem
        itens.append(item)

    # proteção: se a API respondeu sem nenhuma Issue mas o site tinha posts,
    # é mais provável um problema (rótulo renomeado, falha temporária) do que
    # todos os posts terem sido fechados de uma vez. Mantém o feed atual.
    if not itens and ARQ_FEED.exists():
        try:
            anteriores = json.loads(ARQ_FEED.read_text(encoding="utf-8"))
        except ValueError:
            anteriores = []
        if anteriores:
            log("nenhuma Issue encontrada, mas o feed tinha posts; mantendo o feed atual. "
                "Se você fechou todos os posts de propósito, apague o conteúdo do feed.json à mão.")
            return 0

    ARQ_FEED.write_text(
        json.dumps(itens, ensure_ascii=False, indent=2),
        encoding="utf-8")
    log(f"feed.json escrito com {len(itens)} item(ns).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
