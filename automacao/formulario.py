"""
VICEVERSA — leitura do formulário "Novo post"
==============================================
Uma Issue criada pelo formulário chega com o corpo dividido em seções:

    ### Texto do post
    <texto em inglês>

    ### Título em português (opcional)
    <título>

    ### Texto em português (opcional)
    <texto>
    ...

Este módulo separa essas seções. É usado pelo posts.py (site) e pelo
botao-x.py (X), para que os dois leiam a Issue do mesmo jeito.

Issues antigas, escritas sem o formulário (sem nenhum "### "), continuam
funcionando: o corpo inteiro vira o texto principal.
"""

import re
import unicodedata

VAZIO = re.compile(r"^\s*_No response_\s*$", re.M)
ROTULOS = re.compile(
    r"^###[ \t]+("
    r"texto do post|link do post no x|status da not[ií]cia"
    r"|t[ií]tulo em portugu[eê]s|texto em portugu[eê]s"
    r"|t[ií]tulo e[nm] espa[nñ](?:ol|hol)|texto e[nm] espa[nñ](?:ol|hol)"
    r")[^\n]*$", re.I | re.M)


def _normalizar(rotulo):
    t = unicodedata.normalize("NFKD", rotulo).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


def ler_secoes(corpo):
    """Devolve {rotulo_normalizado: valor} para cada seção '### Rótulo'."""
    corpo = (corpo or "").replace("\r\n", "\n")
    # só os rótulos do formulário contam como seção: um "### Título" escrito
    # dentro do próprio texto continua fazendo parte do texto
    partes = re.split(ROTULOS, corpo)
    if len(partes) == 1:
        return {"texto do post": corpo.strip()}
    secoes = {}
    antes = partes[0].strip()
    if antes:
        secoes["texto do post"] = antes
    for i in range(1, len(partes) - 1, 2):
        valor = VAZIO.sub("", partes[i + 1]).strip()
        secoes[_normalizar(partes[i])] = valor
    return secoes


def campo(secoes, *comecos):
    """Primeira seção cujo rótulo começa com um dos prefixos dados."""
    for chave, valor in secoes.items():
        if any(chave.startswith(_normalizar(c)) for c in comecos):
            return valor
    return ""


# selo da notícia: o valor do formulário (ou o rótulo da Issue) vira uma destas chaves
STATUS = {
    "confirmado": "confirmado", "confirmed": "confirmado", "oficial": "confirmado",
    "rumor": "rumor", "rumores": "rumor",
    "vazamento": "vazamento", "vazado": "vazamento", "leak": "vazamento",
    "filtracion": "vazamento",
}


def ler_status(valor):
    """'Confirmado (oficial...)' -> 'confirmado'; qualquer outra coisa -> ''."""
    t = _normalizar(valor or "")
    m = re.match(r"[a-z]+", t)
    return STATUS.get(m.group(0), "") if m else ""


def ler_post(corpo):
    """Extrai os campos do post já limpos.

    Devolve dict com: texto, link, status, titulo_pt, texto_pt, titulo_es, texto_es.
    """
    s = ler_secoes(corpo)
    texto = campo(s, "texto do post")
    link = campo(s, "link do post no x").strip()

    # compatibilidade: uma linha "X: https://x.com/..." dentro do texto
    linhas = []
    for linha in texto.splitlines():
        m = re.match(r"\s*X\s*:\s*(https?://\S+)\s*$", linha, re.I)
        if m and not link:
            link = m.group(1)
        else:
            linhas.append(linha)
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()

    if not re.match(r"^https?://(www\.)?(x|twitter)\.com/", link or "", re.I):
        link = ""

    return {
        "texto": texto,
        "link": link,
        "status": ler_status(campo(s, "status da noticia")),
        "titulo_pt": campo(s, "titulo em portugues").strip(),
        "texto_pt": campo(s, "texto em portugues").strip(),
        "titulo_es": campo(s, "titulo en espanol", "titulo em espanhol").strip(),
        "texto_es": campo(s, "texto en espanol", "texto em espanhol").strip(),
    }
