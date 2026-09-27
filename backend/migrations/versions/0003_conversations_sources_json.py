"""conversations : source (texte) → sources (liste JSON d'objets structurés).

Chaque élément : {"document", "title", "page", "section"} — lus dans la
metadata des chunks récupérés, jamais dans le texte généré par le LLM.

Migration des données : une ancienne valeur `source` non vide devient
[{"document": source, "title": null, "page": null, "section": null}].

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_conversations = sa.table(
    "conversations",
    sa.column("id", sa.Integer),
    sa.column("source", sa.String),
    sa.column("sources", sa.JSON),
)


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(_conversations.c.id, _conversations.c.source)
        .where(_conversations.c.source.isnot(None), _conversations.c.source != "")
    ).all()
    for row_id, source in rows:
        bind.execute(
            _conversations.update()
            .where(_conversations.c.id == row_id)
            .values(sources=[{"document": source, "title": None, "page": None, "section": None}])
        )

    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("source")


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("source", sa.String(255), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.select(_conversations.c.id, _conversations.c.sources)).all()
    for row_id, sources in rows:
        if sources:
            bind.execute(
                _conversations.update()
                .where(_conversations.c.id == row_id)
                .values(source=str(sources[0].get("document", ""))[:255])
            )

    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("sources")
