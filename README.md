# VICEVERSA

Portal de fãs de GTA VI em três idiomas — notícias, mapa interativo de Leonida e
venda do ebook. Site estático, sem framework.

**No ar em:** https://vvviceversa.com

---

## Como o repositório funciona

Você **nunca edita o site direto**. Edita a fonte, roda um comando, e o site é regerado.

```
montar.py            o gerador — junta tudo e escreve em docs/
imagens_og.py        desenha a imagem de compartilhamento de cada notícia (usa o Pillow)
fontes/              fontes usadas nessas imagens (Bebas Neue e IBM Plex Mono, licença OFL)
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

### Selo: Confirmado, Rumor ou Vazamento

O formulário "Novo post" tem o campo obrigatório **Status da notícia**. Ele vira um
selo colorido no card (home e notícias), no topo da página da notícia e na imagem de
compartilhamento. Rumor e Vazamento também ganham uma faixa de aviso logo abaixo da
capa. O que cada selo significa está explicado na Política editorial.

Para trocar o selo depois (um rumor que foi confirmado, por exemplo) ou marcar posts
antigos, adicione na Issue o rótulo `confirmado`, `rumor` ou `vazamento`. **O rótulo
tem prioridade sobre o campo do formulário.** O robô cria esses três rótulos no
repositório na primeira vez que roda. Notícia sem selo continua funcionando, só não
mostra o selo.

### Página da notícia

- **Capa:** a primeira imagem do texto, quando está sozinha num parágrafo, sobe para
  o topo, logo abaixo do título.
- **Tempo de leitura** ao lado da data.
- **Leia a seguir:** card grande com a notícia anterior, logo depois dos botões de
  compartilhar.
- **Canais:** no fim de toda notícia, e no meio das mais longas (5 blocos de texto ou
  mais), um convite para seguir o site. Os canais ficam em `CANAIS`, no começo do
  `montar.py`: hoje só o X está preenchido. Quando criar o canal do WhatsApp ou do
  Telegram, cole o link ali e rode `python3 montar.py`.
- **Imagem de compartilhamento:** cada notícia ganha uma arte 1200×630 em
  `docs/og/`, com a foto, o selo, o título e a data, no visual do site. É ela que
  aparece quando alguém manda o link no WhatsApp, X, Facebook ou Discord. Precisa do
  Pillow (`pip install pillow`); o robô já instala. Sem ele, o site sai normalmente e
  o compartilhamento usa a foto da notícia.

### Fotos das notícias mais leves

Ao baixar as imagens das Issues, o robô reduz as fotos para no máximo 1600 px de
largura e converte para WebP (`automacao/posts.py`, função `otimizar`). As capturas
dos trailers chegam em 4K: cada uma caía de ~900 KB para ~80 KB. Se o WebP não
ajudar (imagem pequena que já é leve), fica o arquivo original. GIF animado não é
convertido.

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

## Eventos do Google Analytics

Além das visitas, o site registra no GA4 o que o leitor faz (`partes/rodape.html`,
função `evento`):

| Evento | Quando |
|---|---|
| `share` | compartilhou uma notícia (`method`: whatsapp, x, telegram, facebook, copiar_link, nativo) ou copiou o link de um local do mapa |
| `seguir_canal` | clicou para seguir um canal (`canal`: x, whatsapp, telegram; `local`: meio ou fim da notícia) |
| `leia_seguir` | abriu a notícia sugerida em "Leia a seguir" |
| `clique_relacionada` | abriu uma notícia da lista "Leia também" |
| `leitura_completa` | chegou ao fim do texto da notícia, depois de pelo menos 10 s na página |
| `clique_ebook` | clicou para comprar o ebook (`local`: seção da página) |
| `clique_rede` | clicou num perfil do VICEVERSA (`rede`: x, instagram, tiktok, youtube...) |
| `troca_idioma` | trocou de idioma |
| `mapa_local`, `mapa_estilo`, `mapa_grade`, `mapa_tela_cheia`, `search` | uso do mapa (abrir local, estilo Noite/Dia, grade, tela cheia, busca) |

Os eventos aparecem em GA4 → Relatórios → Engajamento → Eventos (em até 24 h; na
hora, em Tempo real). Para ver os parâmetros (`method`, `canal`, `local`...) nos
relatórios, cadastre-os em Administrador → Definições personalizadas → Criar
dimensão personalizada (escopo: evento). Vale marcar `clique_ebook` e
`seguir_canal` como **eventos principais** (Administrador → Eventos) para
acompanhá-los como conversões.

## Mapa de Leonida

A página `/map/` (e `/pt/mapa/`, `/es/mapa/`) mostra Leonida **recriada em
vetor, no estilo do VICEVERSA**, a partir de uma imagem-base do mapa de
Leonida.

```
mapa/base/            a imagem-base do mapa (só no seu computador — fica fora do Git)
mapa/recriar_mapa.py  redesenha o mapa em vetor → mapa/leonida.svg, mapa/leonida.json
mapa/pontos.json      pontos clicáveis (regiões, marcos, trailers, vida real) e rótulos
mapa/gerar_previa.py  "foto" do mapa no estilo Noite → mapa/leonida-noite.webp
mapa/leonida-noite.webp  usada para recortar a imagem de cada página de local
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

**Uma página para cada local.** Todo ponto do `mapa/pontos.json` que tem nome
ganha uma página própria, nos 3 idiomas: `/map/vice-beach/`, `/pt/mapa/vice-beach/`,
`/es/mapa/vice-beach/`. O título segue a busca que as pessoas fazem ("Onde fica
Vice Beach em GTA 6") e a página traz o recorte do mapa com o local marcado, o
quadrante, a inspiração na vida real, a descrição, os locais mais próximos e as
notícias que citam o local. O endereço usa o `id` do ponto: **não mude o `id` de um
ponto que já existe**, senão o link antigo quebra. A página do mapa lista todos os
locais embaixo (o Google precisa desses links para achar as páginas), o painel do
mapa ganhou o botão "Ver página do local" e as páginas entram no `sitemap.xml`.

Quanto mais completa a descrição (`desc` no `pontos.json`, ou os textos `m…` em
`idiomas/*.json` para os pontos com `ficha`), melhor a página se sai no Google.

O recorte vem de `mapa/leonida-noite.webp`. Quando o mapa mudar (depois do
`recriar_mapa.py`) ou as cores do estilo Noite mudarem, refaça essa imagem:

```bash
pip install playwright pillow
python -m playwright install chromium
python mapa/gerar_previa.py
python montar.py
```

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
