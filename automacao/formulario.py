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
    r"texto do post|link do post no x|link do v[ií]deo|status da not[ií]cia|assunto"
    r"|mat[eé]ria completa|fontes?\b"
    r"|t[ií]tulo em portugu[eê]s|texto em portugu[eê]s"
    r"|t[ií]tulo e[nm] espa[nñ](?:ol|hol)|texto e[nm] espa[nñ](?:ol|hol)"
    r"|aprofundamento \(ingl[eê]s\)|aprofundamento em portugu[eê]s|aprofundamento e[nm] espa[nñ](?:ol|hol)"
    r"|legenda \(ingl[eê]s\)|legenda em portugu[eê]s|legenda e[nm] espa[nñ](?:ol|hol)"
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


# link do YouTube: watch?v=, youtu.be/, Shorts, /embed/, /live/ e o domínio
# youtube-nocookie. O ID do vídeo tem sempre 11 caracteres.
YOUTUBE = re.compile(
    r"^https?://(?:www\.|m\.|music\.)?(?:youtube(?:-nocookie)?\.com/"
    r"(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/|live/|v/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", re.I)


def _segundos(valor):
    """'90', '90s', '1m30s', '1h2m3s' -> segundos (0 se não der para ler)."""
    valor = (valor or "").strip().lower()
    if valor.isdigit():
        return int(valor)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", valor)
    if not (m and any(m.groups())):
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def ler_video(valor):
    """Link do YouTube -> {"id", "inicio", "vertical"}; {} se não for um link válido."""
    for url in re.findall(r"https?://\S+", valor or ""):
        url = url.rstrip(").,;>")
        m = YOUTUBE.match(url)
        if not m:
            continue
        t = re.search(r"[?&#](?:t|start)=([0-9hms]+)", url, re.I)
        return {"id": m.group(1), "inicio": _segundos(t.group(1)) if t else 0,
                "vertical": "/shorts/" in url.lower()}
    return {}


def ler_assunto(valor):
    """'Off — outro jogo ou assunto' -> True; 'GTA 6' ou vazio -> False."""
    return _normalizar(valor or "").startswith("off")


# aprofundamento: o campo vem com quatro subtítulos (#### Contexto, #### O que
# se sabe, #### O que ainda não se sabe, #### Análise). A ordem dos testes
# importa: "não se sabe" precisa ser visto antes de "se sabe".
PARTES_APROFUNDAMENTO = (
    ("unknown", r"n[aã]o se sabe|no se sabe|don.?t know|do not know|not known|unknown|ainda n[aã]o|a[uú]n no"),
    ("known", r"se sabe|we know|known|confirmad"),
    ("context", r"context"),
    ("take", r"an[aá]lis|take|opini"),
)


def ler_aprofundamento(texto):
    """'#### Contexto ... #### Análise ...' -> {"context": [...], "known": [...], ...}.

    Contexto e análise viram parágrafos (separados por linha em branco); o que
    se sabe e o que não se sabe viram itens de lista (linhas com "- "). As
    instruções do modelo (comentários <!-- -->) e itens vazios são ignorados.
    Devolve {} quando o campo está vazio.
    """
    texto = re.sub(r"<!--.*?-->", "", (texto or "").replace("\r\n", "\n"), flags=re.S)
    blocos = re.split(r"^#{2,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", texto, flags=re.M)
    resultado = {}
    for i in range(1, len(blocos) - 1, 2):
        titulo = _normalizar(blocos[i])
        chave = next((k for k, padrao in PARTES_APROFUNDAMENTO if re.search(padrao, titulo)), None)
        if not chave:
            continue
        corpo = blocos[i + 1].strip()
        if chave in ("known", "unknown"):
            itens = [re.sub(r"^\s*[-*•]\s*", "", l).strip() for l in corpo.splitlines()]
            valores = [t for t in itens if t]
        else:
            valores = [" ".join(p.split()) for p in re.split(r"\n\s*\n", corpo) if p.strip()]
        if valores:
            resultado[chave] = resultado.get(chave, []) + valores
    return resultado


def ler_video_avulso(corpo):
    """Formulário "Novo vídeo" (só vídeo, sem notícia): link, legenda e traduções."""
    s = ler_secoes(corpo)
    video_bruto = campo(s, "link do video").strip()
    return {
        "video": ler_video(video_bruto),
        "video_bruto": video_bruto,
        "legenda": campo(s, "legenda (ingles", "legenda em ingles").strip(),
        "titulo_pt": campo(s, "titulo em portugues").strip(),
        "legenda_pt": campo(s, "legenda em portugues").strip(),
        "titulo_es": campo(s, "titulo en espanol", "titulo em espanhol").strip(),
        "legenda_es": campo(s, "legenda en espanol", "legenda em espanhol").strip(),
    }


TIPOS_COLECIONAVEL = {
    "carta colecionavel": "carta", "ponto waink": "wink", "meteorito": "meteorito",
    "naufragio de kenton": "tesouro", "revista ou livro": "revista",
}
POSICAO = re.compile(r'"?x"?\s*[:=]\s*(0?\.\d+|[01](?:\.0+)?)\s*[,;]?\s*"?y"?\s*[:=]\s*(0?\.\d+|[01](?:\.0+)?)', re.I)


def ler_colecionavel(corpo):
    """Formulário "Novo colecionável": tipo, posição (x, y em frações do mapa), onde fica e tesouros.

    Devolve None se faltar o tipo ou a posição."""
    corpo = (corpo or "").replace("\r\n", "\n")
    partes = re.split(r"^###[ \t]+([^\n]+)$", corpo, flags=re.M)
    s = {}
    for i in range(1, len(partes) - 1, 2):
        s[_normalizar(partes[i])] = VAZIO.sub("", partes[i + 1]).strip()
    tipo = TIPOS_COLECIONAVEL.get(_normalizar(s.get("tipo", "")))
    m = POSICAO.search(s.get("posicao no mapa", ""))
    if not (tipo and m):
        return None
    x, y = float(m.group(1)), float(m.group(2))
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    local = {"en": s.get("onde fica (ingles)", "")}
    for cod, chave in (("pt-BR", "onde fica (portugues)"), ("es", "onde fica (espanhol)")):
        if s.get(chave):
            local[cod] = s[chave]
    tesouros = [re.sub(r"^\s*[-*•]\s*", "", l).strip() for l in s.get("tesouros do naufragio", "").splitlines()]
    return {"tipo": tipo, "x": round(x, 5), "y": round(y, 5), "local": local,
            "itens": [t for t in tesouros if t]}


def ler_post(corpo):
    """Extrai os campos do post já limpos.

    Devolve dict com: texto, materia, fontes, link, video, video_bruto, status,
    off, titulo_pt, texto_pt, titulo_es, texto_es, aprofundamento.
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

    # matéria completa (site): se vier preenchida, é ela que vai para a página da
    # notícia; o "Texto do post" continua sendo o texto curto do X
    materia = campo(s, "materia completa").strip()
    fontes = [u.rstrip(").,;") for u in re.findall(r"https?://[^\s<>\"']+", campo(s, "fonte"))]
    video_bruto = campo(s, "link do video").strip()

    return {
        # vídeo do YouTube (campo "Link do vídeo"): toca no topo da matéria e
        # entra na página Vídeos. video_bruto serve para avisar link inválido.
        "video": ler_video(video_bruto),
        "video_bruto": video_bruto,
        "texto": texto,
        "materia": materia,
        "fontes": fontes,
        "link": link,
        "status": ler_status(campo(s, "status da noticia")),
        # categoria "off": notícia que não é sobre GTA 6 (outro jogo, indústria...)
        "off": ler_assunto(campo(s, "assunto")),
        "titulo_pt": campo(s, "titulo em portugues").strip(),
        "texto_pt": campo(s, "texto em portugues").strip(),
        "titulo_es": campo(s, "titulo en espanol", "titulo em espanhol").strip(),
        "texto_es": campo(s, "texto en espanol", "texto em espanhol").strip(),
        # contexto, o que se sabe, o que não se sabe e análise, por idioma
        "aprofundamento": {
            cod: dados for cod, dados in (
                ("en", ler_aprofundamento(campo(s, "aprofundamento (ingles", "aprofundamento em ingles"))),
                ("pt-BR", ler_aprofundamento(campo(s, "aprofundamento em portugues"))),
                ("es", ler_aprofundamento(campo(s, "aprofundamento en espanol", "aprofundamento em espanhol"))),
            ) if dados
        },
    }
