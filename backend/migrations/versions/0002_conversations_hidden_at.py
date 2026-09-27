"""conversations : soft reset (hidden_at) + index de lecture de l'historique.

hidden_at != NULL : l'échange est masqué du chat et du contexte LLM après un
reset, mais reste visible dans l'historique admin.

L'index composite (chat_id, created_at) sert la requête « N derniers échanges
visibles d'un chat », exécutée à chaque question.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_conversations_chat_id_created_at",
        "conversations",
        ["chat_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_chat_id_created_at", table_name="conversations")
    op.drop_column("conversations", "hidden_at")
