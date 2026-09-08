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
automacao/           o robô que busca notícias, escreve com IA e posta no X
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
