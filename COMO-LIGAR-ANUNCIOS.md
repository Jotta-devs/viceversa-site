# Anúncios — status atual

## ✅ Já feito

- **Tag de verificação/Auto ads do Google** instalada no `<head>` de todas as 9 páginas
  (`partes/cabeca.html`), com o ID de editor `ca-pub-4263183130382993`.
- **`ads.txt`** atualizado com `google.com, pub-4263183130382993, DIRECT, f08c47fec0942fa0`.
- **`ad_cliente`** preenchido nos três `idiomas/*.json`.

Isso já é suficiente para o Google **rastrear e verificar** o site, e para o **Auto ads**
funcionar assim que a conta for aprovada — o Auto ads decide sozinho onde inserir anúncios
na página, sem precisar dos blocos manuais abaixo.

## ⏳ Falta — os 3 blocos manuais

O site também tem três espaços **reservados e desenhados** (entre as manchetes e o mapa,
antes do plantão e antes do FAQ) para blocos de anúncio manuais — que dão mais controle
sobre onde o anúncio aparece do que o Auto ads sozinho. Eles ficam **invisíveis** até
receberem um ID de bloco real, então não atrapalham em nada enquanto isso não acontece.

Para ativá-los, depois que a conta for aprovada:

1. No AdSense, crie 3 blocos do tipo "display responsivo". Cada um gera um ID de bloco
   (`data-ad-slot`).
2. Preencha `ad_slot_a`, `ad_slot_b` e `ad_slot_c` nos três `idiomas/*.json` com esses IDs.
3. Rode `python3 montar.py` e publique.

## Aguardando a análise do Google

A aprovação costuma levar de alguns dias a algumas semanas. Enquanto isso, o site já está
funcionando normalmente — a tag no `<head>` não trava nada, é `async`.

## Obrigatório: consentimento

Para tráfego da Europa e do Reino Unido, o Google exige uma CMP **certificada** —
um banner caseiro não serve e resulta em anúncios bloqueados. Use a CMP gratuita do
próprio Google: painel do AdSense → Privacidade e mensagens → Mensagem de consentimento
da UE. Ative antes de divulgar as versões em inglês e espanhol.

Para o Brasil, a LGPD pede aviso sobre cookies. A mesma ferramenta do Google cobre isso.

## Regras que derrubam contas

- **Nunca clique nos próprios anúncios**, nem peça para amigos clicarem — nem "para testar".
  O Google detecta e banir é permanente. Isso vale a partir de agora: a tag já está ativa.
- **Não coloque anúncio demais.** Três slots já é o limite saudável para esta página.
- **Rotule sempre** — o rótulo "Publicidade" já está implementado em cada slot.
- **Nada de conteúdo vazado.** Anúncio em página com material pirateado encerra a conta
  e ainda te expõe ao takedown da Take-Two.

## Se o AdSense recusar

Alternativas que aceitam sites menores: **Ezoic** (sem mínimo de tráfego, mas injeta mais
scripts e pesa mais) e **Adsterra** ou **PropellerAds** (aceitam quase todo mundo, pagam
melhor, mas os formatos são agressivos — pop-under, redirecionamento — e queimam a
confiança do leitor). Eu só usaria essas duas como último recurso.

Quando o site passar de ~50 mil sessões/mês, vale migrar para **Mediavine** ou
**Raptive**: os RPMs são de 2 a 5 vezes maiores que os do AdSense.
