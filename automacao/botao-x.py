"""
VICEVERSA — botão de publicação no X
=====================================
Comenta na Issue com um link que abre a caixa de publicação do X já preenchida
com o texto. Quem escreve revisa e clica em Post: um clique, sem copiar e colar.

Custo: ZERO. Não usa a API do X (que é paga desde fevereiro de 2026). Usa o
endpoint público de intenção — o mesmo dos botões "Post" espalhados pela web —
e a API do GitHub, com o token gratuito do Actions.

Nada é publicado automaticamente. A pessoa sempre revisa antes de postar.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

LIMITE_X = 280
MARCA = "<!-- viceversa-botao-x -->"   # identifica o comentário do robô


def log(msg):
    print(f"[viceversa-botao] {msg}", flush=True)


def evento():
    caminho = os.environ.get("GITHUB_EVENT_PATH")
    if not caminho or not Path(caminho).exists():
        return {}
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def montar_texto(titulo, corpo):
    """Título + texto, sem URLs (que no X viram links encurtados e ocupam espaço)."""
    corpo = corpo or ""
    # remove a seção do formulário com o link do X e quaisquer URLs
    corpo = re.sub(r"###\s*Link do post no X.*?(?=###|\Z)", "", corpo, flags=re.S | re.I)
    corpo = re.sub(r"###\s*Texto do post\s*", "", corpo, flags=re.I)
    corpo = re.sub(r"^\s*_No response_\s*$", "", corpo, flags=re.M)
    corpo = re.sub(r"^\s*X\s*:\s*https?://\S+\s*$", "", corpo, flags=re.I | re.M)
    corpo = re.sub(r"https?://\S+", "", corpo)
    corpo = re.sub(r"\n{3,}", "\n\n", corpo).strip()

    titulo = (titulo or "").strip()
    return f"{titulo}\n\n{corpo}".strip() if corpo else titulo


def comentar(repositorio, numero, corpo, token):
    url = f"https://api.github.com/repos/{repositorio}/issues/{numero}/comments"
    dados = json.dumps({"body": corpo}).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method="POST", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "viceversa-bot",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def comentario_existente(repositorio, numero, token):
    """Evita empilhar um botão a cada edição da Issue."""
    url = f"https://api.github.com/repos/{repositorio}/issues/{numero}/comments?per_page=100"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "viceversa-bot",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        for c in json.loads(r.read().decode("utf-8")):
            if MARCA in (c.get("body") or ""):
                return c["id"]
    return None


def atualizar(repositorio, id_comentario, corpo, token):
    url = f"https://api.github.com/repos/{repositorio}/issues/comments/{id_comentario}"
    dados = json.dumps({"body": corpo}).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method="PATCH", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "viceversa-bot",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    ev = evento()
    issue = ev.get("issue")
    if not issue:
        log("não foi um evento de Issue; nada a fazer.")
        return 0

    rotulos = {r.get("name") for r in issue.get("labels", [])}
    if "post" not in rotulos:
        log("Issue sem o rótulo 'post'; ignorando.")
        return 0

    repositorio = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    numero = issue.get("number")
    if not (repositorio and token and numero):
        log("faltam variáveis do ambiente do Actions.")
        return 0

    texto = montar_texto(issue.get("title"), issue.get("body"))
    if not texto:
        log("Issue sem texto; nada a publicar.")
        return 0

    # o link de intenção do X não carrega imagem: se houver uma na Issue,
    # a pessoa precisa anexá-la à mão na caixa de publicação
    corpo_bruto = issue.get("body") or ""
    tem_imagem = bool(re.search(r"!\[[^\]]*\]\(https?://", corpo_bruto)
                      or re.search(r"<img[^>]+src=", corpo_bruto, re.I))

    sobra = LIMITE_X - len(texto)
    link = "https://x.com/intent/post?text=" + urllib.parse.quote(texto, safe="")

    if sobra >= 0:
        aviso = f"Cabe no X, com **{sobra}** caracteres de sobra."
    else:
        aviso = (f"⚠️ **Passou {abs(sobra)} caracteres do limite do X.** "
                 "O X vai cortar ou recusar — encurte o título ou o texto e "
                 "salve a Issue; este botão se atualiza sozinho.")

    lembrete_imagem = ("\n\n📎 **Esta Issue tem imagem.** O link abre só com o texto — "
                       "baixe a imagem acima e arraste para a caixa do X antes de publicar. "
                       "No site ela já aparece sozinha." if tem_imagem else "")

    corpo = f"""{MARCA}
### Publicar no X

**[→ Abrir o X com este post pronto]({link})**

O link abre a caixa de publicação já preenchida. Revise e clique em **Post**.{lembrete_imagem}

{aviso}

<details><summary>Texto que será publicado</summary>

```
{texto}
```
</details>

*Depois de publicar, cole o link do tweet no campo "Link do post no X" da Issue
para o card do site apontar para ele.*
"""

    try:
        existente = comentario_existente(repositorio, numero, token)
        if existente:
            atualizar(repositorio, existente, corpo, token)
            log(f"botão atualizado na Issue #{numero} ({len(texto)} chars).")
        else:
            comentar(repositorio, numero, corpo, token)
            log(f"botão criado na Issue #{numero} ({len(texto)} chars).")
    except Exception as exc:
        log(f"não consegui comentar: {exc}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
