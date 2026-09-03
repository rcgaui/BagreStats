# BagreStats — decisões de projeto

Registro do que foi decidido e **por quê**, para não reabrir discussão fechada.

## Domínio

Uma pelada por rodada, com data livre — nada no código assume dia da semana.
Dois times, uma única partida que dura a noite toda. Os times são batidos no dia: **o elenco muda toda semana**.

Consequência central: **time não é uma entidade permanente, a cor é só a
etiqueta daquele dia.** Por isso a estatística acumula no *jogador*, nunca no
time. O confronto entre cores existe, mas é decorativo — e isso é assumido.

## As quatro tabelas

| Tabela | Papel |
|---|---|
| `jogador` | id fixo + apelido editável |
| `cor` | as cores disponíveis, com código hexadecimal |
| `partida` | uma pelada. `cor_vencedora_id` vazio = empate |
| `participacao` | liga jogador + partida + cor |

Decisões que sustentam isso:

- **Jogador é id, não texto.** Renomear "Digo" para "Rodrigo" não quebra o
  histórico. Texto livre fragmentaria a estatística com "Rodrigo"/"rodrigo".
- **Empate é a ausência de vencedor**, não uma coluna própria. Um dado, um lugar.
- **Derrota não é gravada.** É derivada: perdeu quem não é o vencedor. Guardar
  os dois abriria espaço para contradição.
- **As duas cores da noite saem das participações**, não de colunas na partida.
- **`UNIQUE(partida_id, jogador_id)`** impede o mesmo jogador nos dois times.
  Regra no banco, não no código: não depende de ninguém lembrar de conferir.

## Ranking

Pontos corridos: 3 pela vitória, 1 pelo empate. O aproveitamento (% dos pontos
possíveis) aparece como coluna, porque sai das mesmas contagens e custa zero.

## O que ficou de fora, de propósito

- **Gols e artilharia** — exigiria anotar durante o jogo. É o custo que mata
  sistema pessoal. Sem gols, não há nota de desempenho estilo SofaScore.
- **Posição em campo** — não alimenta nenhuma estatística atual. Entra junto
  com a tela de formação, se ela existir, como coluna nova (migração barata).
- **Login e hospedagem** — fase 2. Hoje roda local, um usuário.
- **Postgres e Docker** — SQLite resolve 52 linhas por ano. O gatilho para
  trocar é o dia de hospedar, e a troca é uma linha do `.env` mais um script,
  porque o SQLAlchemy fala com os dois.
- **Várias peladas (multi-grupo)** — possível, e o modelo atual não atrapalha:
  seria uma coluna `pelada_id` nas tabelas e um filtro em toda consulta. Não se
  constrói agora para não pagar por meses a complexidade de dez grupos tendo um.

## Ordem de construção

1. Pasta, git, FastAPI de pé ✅
2. Tabelas + primeira migração ✅
3. Carga do `PELADA.xlsx` ✅
4. Classificação ✅
5. Lançar pelada ✅
6. Perfil, duplas, fregueses, confronto de cores ✅
