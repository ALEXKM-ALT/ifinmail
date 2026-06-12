"""add domain verification columns

Revision ID: c9e8d7f6a5b4
Revises: d3e4f5a6b7c8
Create Date: 2026-06-12 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e8d7f6a5b4'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('domains', sa.Column('verification_token', sa.String(length=64), nullable=True))
    op.add_column('domains', sa.Column('spf_ok', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('domains', sa.Column('dkim_ok', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('domains', sa.Column('dmarc_ok', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('domains', sa.Column('mx_ok', sa.Integer(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('domains', 'mx_ok')
    op.drop_column('domains', 'dmarc_ok')
    op.drop_column('domains', 'dkim_ok')
    op.drop_column('domains', 'spf_ok')
    op.drop_column('domains', 'verification_token')
