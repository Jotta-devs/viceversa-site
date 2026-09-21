# Como publicar — guia para quem escreve

## O fluxo, em 4 passos

1. **Issues → New issue → "Novo post"**
2. Preencha o **título** (vira o título do card e a primeira linha do post no X)
   e o **texto**.
3. *Submit new issue*. Em ~1 minuto o card aparece no site, e o robô responde
   na própria Issue com um botão **"Abrir o X com este post pronto"**.
4. Clique no botão. O X abre com o texto **já preenchido** — revise e clique em
   **Post**.

Você escreve uma vez. O site é automático; o X é um clique.

### Depois de publicar no X

Volte na Issue, clique em editar e cole o link do tweet no campo
**"Link do post no X"**. O card do site passa a apontar para o tweet.
Esse passo é opcional — sem ele, o card aponta para a própria Issue.

## Limite de caracteres

O X aceita 280 caracteres. O robô soma título + texto e avisa no comentário:

- *"Cabe no X, com N caracteres de sobra"* → tudo certo.
- *"⚠️ Passou N caracteres do limite"* → encurte e salve a Issue. O botão se
  atualiza sozinho, não precisa abrir outra.

Links não entram no post do X: URLs são removidas automaticamente, porque no X
elas viram links encurtados e comem o espaço do texto.

## Corrigir, tirar do ar

- **Editar** a Issue atualiza o card do site e o botão do X.
  (Um post já publicado no X não muda — o X não permite editar.)
- **Fechar** a Issue tira o card do site.
- **Reabrir** traz de volta.

## Custo: zero

Nada aqui usa API paga. O botão usa o endpoint público de intenção do X — o
mesmo dos botões "Post" espalhados pela web — e o resto usa a API do GitHub com
o token gratuito do Actions.

**Por que não é totalmente automático?** Porque a API do X é paga por uso desde
fevereiro de 2026, e o antigo plano gratuito está fechado para contas novas.
Publicar automaticamente custaria cerca de US$ 0,015 por post. Se um dia quiser
eliminar o clique, dá para ligar isso — mas aí passa a ter fatura.

Um efeito colateral bom do clique: alguém sempre revisa antes de ir ao ar.

## Se o botão não aparecer

Aba **Actions** → última execução → passo **"Gerar o botão de publicação no X"**.

- Se disser *"Issue sem o rótulo 'post'"*, faltou o rótulo. Use sempre o
  formulário "Novo post", que já aplica o rótulo sozinho.
- Se der erro de permissão, confira **Settings → Actions → General →
  Workflow permissions → "Read and write permissions"**.
