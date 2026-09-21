# VICEVERSA — versões em vários idiomas

## Por que esta abordagem (e não as outras)

Há três formas de fazer um site multilíngue. A escolha aqui não foi por gosto:

**1. Trocar o texto por JavaScript, num arquivo só.** É a mais fácil e a pior para você.
O Google indexa apenas o idioma que vem no HTML; as outras versões não existem para a
busca. Num site de notícias, que vive de busca, isso joga fora o motivo de traduzir.

**2. Copiar o HTML e traduzir na mão, um arquivo por idioma.** Ótimo para SEO, péssimo
para manter: cada notícia nova tem que ser editada em três lugares, e é questão de tempo
até as versões saírem de sincronia.

**3. Uma fonte só + gerador (o que está montado aqui).** Você edita o texto em um arquivo
de idioma; o script gera as três páginas estáticas, cada uma com URL, `lang`, canonical e
metadados próprios. SEO da opção 2 com a manutenção da opção 1.

## Como está organizado

```
template.html          o site com {{marcadores}} no lugar dos textos — mexa só no visual
idiomas/pt-BR.json     os textos em português (também é a rede de segurança) (idioma principal do site)
idiomas/pt-BR.json     os textos em português (também é a rede de segurança)
idiomas/es.json        os textos em espanhol
montar.py              o gerador
site/                  ← o que você publica
   index.html          INGLÊS (raiz — idioma principal)
   pt/index.html       português
   es/index.html       espanhol
   sitemap.xml, robots.txt, imagens
```

## O dia a dia

**Publicar uma notícia nova:** abra `idiomas/pt-BR.json`, edite o texto da chave
correspondente, faça o mesmo em `en.json` e `es.json`, rode `python3 montar.py` e suba a
pasta `site/`. Chave sem tradução cai automaticamente para o português — o site nunca
quebra, no máximo aparece um trecho em pt.

**Mudar o layout, cores, animações:** mexa no `template.html`. Nunca edite os arquivos
dentro de `site/` — eles são regenerados e você perde as alterações.

**Trocar qual idioma fica na raiz:** no `montar.py`, quem tiver pasta `""` e `True` no
final é o idioma padrão. Hoje é o inglês. Só um idioma pode ocupar a raiz.

**Adicionar um idioma:** copie `idiomas/en.json`, traduza, salve como `fr.json` e
acrescente uma linha em `IDIOMAS`, dentro do `montar.py`:

```python
"fr": ("fr", "fr", "fr_FR", "FR", False),
#      pasta  hreflang  og:locale  rótulo  é o padrão?
```

**Trocar textos no HTML e re-extrair:** se você editar textos direto no `viceversa.html`,
rode `python3 montar.py --extrair` para regerar o template e o `pt-BR.json`. Atenção: isso
renumera as chaves, então as traduções de en/es precisam ser reconferidas. No dia a dia é
melhor editar os JSON.

## O que já está resolvido

- `<html lang>` correto em cada versão
- `hreflang` cruzado entre as três + `x-default` apontando para o inglês
- Imagem de compartilhamento própria por idioma (`og-image-en/pt/es.png`)
- `canonical`, `og:locale`, título e descrição próprios por idioma
- Seletor PT/EN/ES no menu, com `aria-current` na versão ativa
- Caminhos relativos ajustados (`../ebook-capa.png` nas subpastas)
- `sitemap.xml` com as alternâncias declaradas e `robots.txt`

## Antes de publicar

1. No `montar.py`, troque `DOMINIO` pelo endereço real. Sem isso, o `hreflang` e o
   `canonical` apontam para o lugar errado e o Google ignora as versões traduzidas.
2. Rode `python3 montar.py` e publique **o conteúdo de `site/`** na raiz do servidor.
3. No Google Search Console, envie `sitemap.xml` uma vez.

## Duas decisões que valem sua atenção

**Preços.** Nas versões em inglês e espanhol usei os preços internacionais do jogo
(US$ 79,99 / 99,99 e 79,99 € / 99,99 €), porque um leitor de fora não se orienta por reais.
Confira os valores da sua região antes de publicar.

**O ebook é em português.** Ele aparece nas três versões, mas nas traduções o aviso diz
claramente que o livro está escrito em português do Brasil e que a cobrança é em reais.
Vender sem avisar isso geraria reembolso e reclamação. Se preferir, você pode escondê-lo
nas versões en/es — ou, melhor, traduzir o ebook: pelo próprio Capítulo 13 do seu livro, o
RPM em inglês é cerca de 18 vezes o brasileiro, e o mesmo raciocínio vale para o produto.

**Sem redirecionamento automático.** O site não força o idioma pelo navegador de
propósito: redirecionamento automático atrapalha o rastreamento do Google e irrita quem
quer ler no idioma original. O seletor no menu resolve, e o `hreflang` faz o buscador
entregar a versão certa para cada pessoa.


## Por que o inglês na raiz

Não é só preferência: o endereço raiz é o que recebe a maior parte dos links e da
autoridade de busca, e o `x-default` diz ao Google qual versão mostrar para quem não se
encaixa em nenhum idioma listado. Com o inglês na raiz, o público internacional — que
pelo Capítulo 13 do seu ebook vale cerca de 18 vezes mais por visita — cai direto na
versão certa, sem redirecionamento.

O português não perdeu nada: continua completo em `/pt/`, com `hreflang` próprio. Quem
busca em português no Google continua recebendo a página em português.
