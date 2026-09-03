# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Usuário único hoje: o dono da pelada, que registra e consulta sozinho. Ele
lança a partida **no computador, em casa, depois** que a pelada aconteceu —
não na quadra, não no calor do jogo.

Os ~18 jogadores da pelada são o público futuro, não o atual. A fase 2 prevista
é cada um com login próprio e o dono como administrador. Isso está
explicitamente adiado: nada hoje deve pagar o custo dessa fase.

## Product Purpose

Substituir a planilha que registrava a pelada (data, vencedor e quem jogou de
cada lado) por um sistema que responde o que a planilha não respondia: quem
mais ganha, com quem cada um joga melhor, quem é freguês de quem, quem está há
mais tempo sem perder.

Sucesso é duplo e nessa ordem: **a pelada continuar sendo lançada toda semana**,
e os números serem consultados por vontade própria. Um sistema bonito que para
de ser alimentado no terceiro sábado falhou.

## Positioning

Numa pelada os times são batidos no dia — o elenco muda toda semana. Logo
**time não é entidade permanente: a cor do colete é só a etiqueta daquela
noite.** Toda a estatística acumula no *jogador*, nunca no time.

É isso que um app genérico de liga ou campeonato não consegue copiar
honestamente: eles assumem times estáveis com elenco e identidade. Aqui a única
identidade durável é a pessoa.

## Operating Context

- Uma pelada por rodada, normalmente quinta-feira, mas **a data é livre** —
  nada no produto assume dia da semana.
- Dois times, **uma única partida** que dura a noite toda. Não são vários jogos
  somados: é um jogo só.
- Times sorteados no dia. Cores usuais: preto contra branco (coletes), mas
  outras cores podem ser cadastradas e usadas.
- A pelada registrada foi 9 contra 9, mas isso **não é regra**: faltou gente,
  joga 8 contra 8, e o sistema aceita times desiguais e vagas vazias.
- A escalação é montada numa formação fixa — goleiro, zagueiro, dois laterais,
  dois meio-campos e um atacante — mais reservas, que começam em duas vagas e
  podem ser acrescentadas.
- Roda localmente hoje (servidor local, um usuário). Hospedagem é fase 2, e é
  o mesmo momento em que login e banco de servidor passam a fazer sentido.

## Capabilities and Constraints

**Registra:** data, as duas cores da noite, quem jogou de cada lado, a vaga que
cada um ocupou, e o resultado (cor vencedora, ou vazio para empate).

**Calcula:** classificação por pontos corridos (3 vitória / 1 empate / 0
derrota) com aproveitamento em %, presença, sequência sem perder, estatística
de dupla (com quem se vence mais), freguês (contra quem se vence mais) e
confronto entre cores.

**Deliberadamente fora, e não deve ser reintroduzido sem decisão explícita:**

- **Gols e artilharia.** Exigiriam anotar durante o jogo — o atrito que mata
  sistema pessoal. Consequência direta: **não existe nota de desempenho por
  jogador**, e nenhuma tela pode sugerir que exista.
- **Login e autenticação.** Fase 2.
- **Várias peladas / multi-grupo.** Possível no modelo, não construído.

**Restrições e regras que o produto garante:**

- O mesmo jogador não pode ser escalado nos dois times (regra no banco).
- Uma pelada por data.
- Empate é a *ausência* de vencedor, não um valor próprio. Derrota é derivada,
  nunca armazenada.
- O jogador é identificado por id, não por texto: renomear apelido preserva
  todo o histórico.
- A posição em campo passou a ser gravada junto com a tela de escalação.
  Peladas registradas antes disso não têm posição, e isso é permanente.

**Terminologia do produto** (usar exatamente, não traduzir nem "melhorar"):
pelada, jogador, apelido, cor / colete, partida, participação, escalação,
reserva, dupla, freguês, aproveitamento, sequência sem perder, confronto.

## Brand Commitments

- **Nome:** BagreStats. "Bagre" é perna de pau — o nome é auto-deboche
  assumido.
- **Voz confirmada:** série com pitadas. Estrutura e números levados a sério;
  humor pontual em lugares específicos, como estado vazio, sequência ruim e o
  confronto de cores. Não é um app de zoeira, e também não é corporativo.
- **Referência nomeada pelo usuário:** SofaScore, citada como o modelo do que
  ele quer acompanhar. Registrada como referência dele, sem expansão.

## Evidence on Hand

**Dado real existente:** 18 jogadores cadastrados (apelidos reais do grupo) e
**uma única pelada registrada** — 27/08/2026, 9 contra 9, vitória do preto.

**Ausências que trabalho futuro não pode fabricar:**

- Não existe histórico longo. Gráficos de evolução hoje têm **um ponto**. A
  interface precisa lidar com isso honestamente, sem simular série temporal.
- Não existem gols, assistências, cartões nem notas — nenhuma tela pode exibir
  ou insinuar esses números.
- Não existem fotos de jogadores, escudos nem logotipo. Identidade visual de
  jogador hoje é derivada do próprio apelido.
- Não existe temporada, divisão, campeonato nem calendário de jogos futuros.

**Localização:** repositório público em github.com/rcgaui/BagreStats. Os dados
reais vivem apenas no banco local, fora do repositório.

## Product Principles

1. **Registro barato acima de dado rico.** Entre mais informação e menos
   atrito no lançamento semanal, o produto escolhe menos atrito — foi assim que
   gols ficaram de fora.
2. **A estatística é da pessoa.** Time é etiqueta do dia; o jogador é a única
   identidade que dura.
3. **Nunca inventar número.** O que não é coletado não aparece, nem
   aproximado, nem sugerido. Pouco histórico se admite, não se disfarça.
4. **Um fato, um lugar.** Nada de guardar duas vezes o que pode ser derivado —
   é o que impede o sistema de se contradizer.
5. **Não pagar hoje pela fase 2.** Login, hospedagem e múltiplas peladas são
   futuros aceitos, mas não custeados agora.
