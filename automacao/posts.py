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

Para o card ganhar um botão "Ver no X", inclua no corpo uma linha começando com
`X:` seguida do link do tweet. Ela é removida do texto e vira o link do botão:

    X: https://x.com/vvviceversaa/status/123456789

Sem essa linha o card não tem botão — o leitor nunca é mandado para o GitHub.

Feche a Issue para tirar o post do site. Reabra para trazê-lo de volta.
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

RAIZ = Path(__file__).parent
REPO = RAIZ.parent
ARQ_FEED = REPO / "feed.json"

ROTULO = "post"      # só Issues com este rótulo viram publicação
MAX_FEED = 30        # itens mantidos no feed


def log(msg):
    print(f"[viceversa-posts] {msg}", flush=True)


def buscar_issues():
    """Lê as Issues abertas com o rótulo, pela API do GitHub (grátis)."""
    repositorio = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repositorio:
        log("GITHUB_REPOSITORY ausente — rodando fora do Actions?")
        return []

    url = (f"https://api.github.com/repos/{repositorio}/issues"
           f"?state=open&labels={ROTULO}&per_page=50&sort=created&direction=desc")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "viceversa-bot",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        dados = json.loads(r.read().decode("utf-8"))

    # a API devolve pull requests junto com issues; descarta os PRs
    return [i for i in dados if "pull_request" not in i]


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
            req = urllib.request.Request(url, headers={
                "User-Agent": "viceversa-bot",
                "Accept": "image/*,*/*",
                **({"Authorization": f"Bearer {token}"} if token else {}),
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


def separar_link(corpo):
    """Tira a linha 'X: <link>' do corpo e devolve (texto, link)."""
    corpo = corpo or ""
    # as imagens PERMANECEM no texto, na posição original — quem renderiza
    # é o GitHub, e o card reproduz o mesmo resultado do preview da Issue.
    # tira os cabeçalhos do formulário de Issue e os campos vazios
    corpo = re.sub(r"^###\s*Texto do post\s*$", "", corpo, flags=re.I | re.M)
    corpo = re.sub(r"^###\s*Link do post no X.*$", "", corpo, flags=re.I | re.M)
    corpo = re.sub(r"^\s*_No response_\s*$", "", corpo, flags=re.M)
    link = None
    linhas = []
    for linha in corpo.splitlines():
        m = re.match(r"\s*X\s*:\s*(https?://\S+)\s*$", linha, re.I)
        if m and not link:
            link = m.group(1)
        else:
            linhas.append(linha)
    texto = "\n".join(linhas).strip()
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto, link


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
        texto, link = separar_link(issue.get("body"))
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
        # o botão "Ver no X" só existe se houver mesmo um link do X.
        # Sem ele, nenhum botão — nunca apontamos o leitor para o GitHub.
        if link:
            item["link"] = link
        # se a renderização falhar, ainda mostramos a imagem pelo campo antigo
        if "html" not in item:
            imagem = extrair_imagem(issue.get("body"))
            if imagem:
                item["imagem"] = imagem
        itens.append(item)

    ARQ_FEED.write_text(
        json.dumps(itens[:MAX_FEED], ensure_ascii=False, indent=2),
        encoding="utf-8")
    log(f"feed.json escrito com {len(itens[:MAX_FEED])} item(ns).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
