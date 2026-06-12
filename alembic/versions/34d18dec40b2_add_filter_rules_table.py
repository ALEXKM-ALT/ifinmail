"""add_filter_rules_table

Revision ID: 34d18dec40b2
Revises: ed8923dbff01
Create Date: 2026-06-12 09:24:23.820045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34d18dec40b2'
down_revision: Union[str, Sequence[str], None] = 'ed8923dbff01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('filter_rules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('mailbox_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), server_default=sa.text("('')"), nullable=False),
    sa.Column('enabled', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('match_logic', sa.String(length=8), server_default=sa.text("'all'"), nullable=False),
    sa.Column('conditions', sa.Text(), nullable=False),
    sa.Column('actions', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['mailbox_id'], ['mailboxes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('filter_rules')
