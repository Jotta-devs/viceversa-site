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

Para apontar o card ao seu tweet, inclua no corpo uma linha começando com `X:`
seguida do link. Ela é removida do texto e vira o link do card:

    X: https://x.com/vvviceversaa/status/123456789

Feche a Issue para tirar o post do site. Reabra para trazê-lo de volta.
"""

import json
import os
import re
import sys
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
    # tira as marcações de imagem do texto: elas viram o campo `imagem`
    corpo = re.sub(r"!\[[^\]]*\]\((https?://[^\s)]+)\)", "", corpo)
    corpo = re.sub(r"<img[^>]*>", "", corpo, flags=re.I)
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
            "texto": texto,
            "link": link or issue.get("html_url"),
        }
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
