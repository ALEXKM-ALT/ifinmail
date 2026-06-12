"""add org alias provisioning (multi-target aliases)

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-12 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_aliases_source", table_name="aliases")
    op.create_index("ix_aliases_source", "aliases", ["source"], unique=False)
    op.create_unique_constraint("uq_alias_source_target", "aliases", ["source", "target"])


def downgrade() -> None:
    op.drop_constraint("uq_alias_source_target", "aliases", type_="unique")
    op.drop_index("ix_aliases_source", table_name="aliases")
    op.create_index("ix_aliases_source", "aliases", ["source"], unique=True)
