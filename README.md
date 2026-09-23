# VICEVERSA

Portal de fãs de GTA VI em três idiomas — notícias, mapa interativo de Leonida e
venda do ebook. Site estático, sem framework.

**No ar em:** https://vvviceversa.com

---

## Como o repositório funciona

Você **nunca edita o site direto**. Edita a fonte, roda um comando, e o site é regerado.

```
montar.py            o gerador — junta tudo e escreve em docs/
partes/cabeca.html   <head>, CSS, ticker, barra de anúncio e a navbar
partes/rodape.html   rodapé e todo o JavaScript
paginas/*.html       o miolo de cada página (home, noticias, mapa)
idiomas/*.json       TODOS os textos, um arquivo por idioma
*.png                imagens de origem (capas do ebook e capas de compartilhamento)
gerador-capas-ebook.py  refaz as capas traduzidas a partir de ebook-capa-original.png
automacao/           o robô que transforma Issues em notícias e prepara o post do X
institucional/       textos de Sobre, Contato, Privacidade e Política editorial
docs/                ← O SITE GERADO. É esta pasta que vai ao ar. Não edite à mão.
```

### O ciclo de trabalho

```bash
# 1. edite o que quiser em idiomas/, partes/ ou paginas/
# 2. regere o site
python3 montar.py
# 3. publique
git add -A
git commit -m "atualiza manchetes"
git push
```

Em cerca de um minuto o GitHub Pages publica a nova versão.

---

## Configuração inicial (só uma vez)

1. **Domínio.** Já configurado: `DOMINIO = "https://vvviceversa.com"` no `montar.py`.
   Se um dia mudar de endereço, troque essa linha e rode `python3 montar.py`.

2. **GitHub Pages.** Settings → Pages → Source: *Deploy from a branch* → branch `main`,
   pasta **`/docs`** → Save.

3. **Domínio próprio.** Settings → Pages → Custom domain: digite o domínio e salve.
   O GitHub cria um arquivo `CNAME` dentro de `docs/`. **Não apague esse arquivo** — se
   ele sumir, o domínio para de funcionar. Ele sobrevive ao `montar.py`? Não: a pasta
   `docs/` é apagada a cada geração. Por isso o gerador já o preserva automaticamente
   (veja a seção seguinte).

4. **Robô (opcional).** Settings → Secrets and variables → Actions, cadastre
   `ANTHROPIC_API_KEY`, `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN` e `X_ACCESS_SECRET`.
   Detalhes em `automacao/LEIA-ME-AUTOMACAO.md`.

---

## Cuidado com o arquivo CNAME

`montar.py` apaga e recria a pasta `docs/`. Se o GitHub tiver criado um `docs/CNAME`
(domínio personalizado), ele é preservado automaticamente pelo gerador. Depois de
configurar o domínio, confira uma vez se `docs/CNAME` continua no repositório após rodar
`python3 montar.py`.

---

## Notícias com página própria

Cada post do `feed.json` (as Issues com o rótulo `post`) vira uma página em
`/news/<data-titulo>/`, com título, descrição, imagem de compartilhamento, dados
estruturados `NewsArticle` e botões de WhatsApp, X, Telegram, Facebook e copiar link.
O `montar.py` também:

- escreve os cards do Plantão direto no HTML (antes eram montados por JavaScript e o
  Google via "Nada publicado ainda");
- mostra as 4 últimas notícias na home, logo abaixo do contador;
- coloca a notícia mais recente na barra do topo e as 3 últimas na faixa rolante;
- grava o contador já com os dias restantes no HTML;
- gera o `FAQPage` da home e o `sitemap.xml` com `lastmod` e todas as notícias.

Tudo se atualiza sozinho a cada Issue publicada, editada ou fechada.

### Notícias em português e espanhol

O formulário "Novo post" tem campos opcionais de título e texto em português e
em espanhol. Preenchidos (título **e** texto), a notícia ganha também
`/pt/noticias/<slug>/` e `/es/noticias/<slug>/`, ligadas entre si por `hreflang`.
Sem tradução, as páginas em pt/es mostram o card da versão em inglês.

### Arquivo permanente

Todas as Issues abertas com o rótulo `post` ficam no site, sem limite. As 20 mais
recentes aparecem como cards na página de notícias; as demais, numa lista
"Arquivo" logo abaixo. **Fechar a Issue ainda tira a notícia do ar** — faça isso
só para posts errados, nunca para "limpar" os antigos: o link deixaria de funcionar.

### Google Notícias, RSS e páginas institucionais

- `feed.xml`, `pt/feed.xml`, `es/feed.xml` — RSS por idioma (use no Google
  Notícias, Flipboard, newsletters e automações).
- `news-sitemap.xml` — só as notícias das últimas 48 horas, no formato do Google
  Notícias. Já está declarado no `robots.txt`.
- Sobre, Contato, Política editorial e Privacidade, nos três idiomas. O texto fica
  em `institucional/<idioma>/<página>.html` — edite ali e rode `python3 montar.py`.
  Para colocar um e-mail de contato, acrescente-o em `institucional/*/contato.html`.
- Blocos de anúncio sem ID (`ad_slot_a/b/c` vazios) não aparecem mais no HTML;
  surgem sozinhos quando os IDs forem preenchidos.

**Depois de publicar, uma vez só:** no Google Search Console envie `sitemap.xml` e
`news-sitemap.xml`; no Google Publisher Center (publishercenter.google.com)
cadastre o site e aponte os três `feed.xml`.

## Mapa de Leonida

A página `/map/` (e `/pt/mapa/`, `/es/mapa/`) mostra Leonida **recriada em
vetor, no estilo do VICEVERSA**, a partir de uma imagem-base do mapa de
Leonida.

```
mapa/base/            a imagem-base do mapa (só no seu computador — fica fora do Git)
mapa/recriar_mapa.py  redesenha o mapa em vetor → mapa/leonida.svg, mapa/leonida.json
mapa/pontos.json      pontos clicáveis (regiões, marcos, trailers, vida real) e rótulos
vendor/leaflet/       a biblioteca do mapa (Leaflet, licença BSD), servida pelo próprio site
```

O vetor traz: mar em 4 profundidades, relevo em 3 níveis, pântanos, praias,
áreas industriais, cidades com quarteirões e prédios, e a rede de vias
redesenhada em rodovias, estradas e ruas (as ruas e os prédios ganham destaque
ao aproximar). Em cima disso o site oferece os estilos **Noite** e **Dia** (as
cores estão em `partes/cabeca.html`, seção "ATLAS recriado"), **grade de
referência** A1…H11, nomes das regiões e locais nos três idiomas, busca, link
direto para cada local e tela cheia.

Nos locais, a tag "Nome descritivo" marca nomes dados por nós (ex.: "Ilha
portuária") e "Nome especulativo" marca apelidos da comunidade que a Rockstar
não confirmou (em vermelho no mapa original).

**Refazer com a versão em alta resolução ou uma versão nova (V17…):**

```bash
# coloque a imagem (PNG ou JPG) em mapa/base/ — vale a mais recente; pode apagar as antigas
pip install opencv-python-headless numpy     # só na primeira vez
python mapa/recriar_mapa.py
python montar.py
```

O script está calibrado para o pôster V16 (legenda à esquerda, mapa à direita);
com uma imagem maior do mesmo pôster ele escala tudo sozinho. Se o layout for
outro, ajuste `RECORTE` e `PASSO_GRADE` no começo do `recriar_mapa.py`. Os
textos e a grade do original são apagados automaticamente.

**Adicionar ou ajustar pontos:** abra `/map/?editar=1` no site, clique no lugar
exato — a posição `"x": …, "y": …` é copiada — e cole em `mapa/pontos.json`.
Pontos de trailer podem levar `"video"` (id do YouTube) e `"t"` (segundo da cena).

## O robô

`.github/workflows/plantao.yml` roda a cada 6 horas: busca notícias de GTA VI em feeds
RSS, escreve os posts com IA, publica no X, grava o resumo em `feed.json`, regera o site
e faz commit. Para desligar temporariamente, troque `PUBLICAR_NO_X` para `"0"` ou
desative o workflow na aba Actions.

---

## Aviso

Site de fãs, sem afiliação com a Rockstar Games ou a Take-Two Interactive. Nenhuma arte
oficial é reproduzida: o skyline, as palmeiras e o mapa de Leonida são ilustrações
próprias, geradas por código.
