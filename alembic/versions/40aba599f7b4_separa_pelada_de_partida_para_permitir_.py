"""separa pelada de partida para permitir varios jogos

A tabela `partida` acumulava dois papeis: a noite (data, escalacao) e o jogo
(resultado). Com tres times uma noite tem varios resultados, entao os papeis
foram separados: `pelada` e a noite, `partida` passa a ser cada jogo.

Migracao COM DADOS: cada partida antiga vira uma pelada com exatamente um jogo
dentro, montado a partir das duas cores que aparecem nas participacoes daquela
noite. Nenhum historico se perde.

Revision ID: 40aba599f7b4
Revises: 92e8e7270e8f
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "40aba599f7b4"
down_revision: Union[str, None] = "92e8e7270e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conexao = op.get_bind()

    # O que existe hoje, lido antes de qualquer alteracao.
    antigas = conexao.execute(
        sa.text("SELECT id, data, cor_vencedora_id FROM partida ORDER BY data")
    ).fetchall()
    participacoes = conexao.execute(
        sa.text("SELECT id, partida_id, jogador_id, cor_id, posicao FROM participacao")
    ).fetchall()

    op.create_table(
        "pelada",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data"),
    )

    # Uma pelada por partida antiga, mantendo o mesmo id: assim as
    # participacoes continuam apontando para o numero certo.
    for antiga in antigas:
        conexao.execute(
            sa.text("INSERT INTO pelada (id, data) VALUES (:id, :data)"),
            {"id": antiga.id, "data": antiga.data},
        )

    # A partida vira o jogo. Recriada do zero porque quase toda coluna mudou.
    op.drop_table("partida")
    op.create_table(
        "partida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pelada_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("cor_a_id", sa.Integer(), nullable=False),
        sa.Column("cor_b_id", sa.Integer(), nullable=False),
        sa.Column("cor_vencedora_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["pelada_id"], ["pelada.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cor_a_id"], ["cor.id"]),
        sa.ForeignKeyConstraint(["cor_b_id"], ["cor.id"]),
        sa.ForeignKeyConstraint(["cor_vencedora_id"], ["cor.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pelada_id", "ordem", name="uq_ordem_do_jogo"),
    )

    # Um jogo por noite antiga, entre as duas cores que jogaram.
    for antiga in antigas:
        cores = sorted(
            {p.cor_id for p in participacoes if p.partida_id == antiga.id}
        )
        if len(cores) != 2:
            # Noite sem exatamente dois times nao vira jogo: a escalacao fica
            # preservada, mas nao ha confronto que se possa afirmar.
            continue
        conexao.execute(
            sa.text(
                "INSERT INTO partida (pelada_id, ordem, cor_a_id, cor_b_id,"
                " cor_vencedora_id) VALUES (:p, 1, :a, :b, :v)"
            ),
            {"p": antiga.id, "a": cores[0], "b": cores[1],
             "v": antiga.cor_vencedora_id},
        )

    # A participacao passa a pertencer a NOITE, nao ao jogo.
    with op.batch_alter_table("participacao", schema=None) as batch:
        batch.alter_column("partida_id", new_column_name="pelada_id")

    # O batch recria a tabela; as chaves estrangeiras sao redeclaradas aqui
    # apontando para pelada.
    with op.batch_alter_table(
        "participacao",
        schema=None,
        copy_from=sa.Table(
            "participacao",
            sa.MetaData(),
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pelada_id", sa.Integer(), nullable=False),
            sa.Column("jogador_id", sa.Integer(), nullable=False),
            sa.Column("cor_id", sa.Integer(), nullable=False),
            sa.Column("posicao", sa.String(length=10), nullable=True),
            sa.UniqueConstraint("pelada_id", "jogador_id",
                                name="uq_um_time_por_jogador"),
        ),
    ) as batch:
        batch.create_foreign_key("fk_participacao_pelada", "pelada",
                                 ["pelada_id"], ["id"], ondelete="CASCADE")
        batch.create_foreign_key("fk_participacao_jogador", "jogador",
                                 ["jogador_id"], ["id"])
        batch.create_foreign_key("fk_participacao_cor", "cor", ["cor_id"], ["id"])


def downgrade() -> None:
    conexao = op.get_bind()
    peladas = conexao.execute(sa.text("SELECT id, data FROM pelada")).fetchall()
    jogos = conexao.execute(
        sa.text("SELECT pelada_id, cor_vencedora_id FROM partida WHERE ordem = 1")
    ).fetchall()
    vencedor_de = {j.pelada_id: j.cor_vencedora_id for j in jogos}

    with op.batch_alter_table("participacao", schema=None) as batch:
        batch.alter_column("pelada_id", new_column_name="partida_id")

    op.drop_table("partida")
    op.create_table(
        "partida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("cor_vencedora_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["cor_vencedora_id"], ["cor.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data"),
    )
    # So o primeiro jogo de cada noite sobrevive: o modelo antigo nao tem onde
    # guardar os demais.
    for p in peladas:
        conexao.execute(
            sa.text("INSERT INTO partida (id, data, cor_vencedora_id)"
                    " VALUES (:id, :data, :v)"),
            {"id": p.id, "data": p.data, "v": vencedor_de.get(p.id)},
        )
    op.drop_table("pelada")
