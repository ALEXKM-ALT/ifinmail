"""add admin fields and tables

Revision ID: f5d8e2c1a4b3
Revises: 401194956f3d
Create Date: 2026-06-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5d8e2c1a4b3'
down_revision: Union[str, Sequence[str], None] = '401194956f3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('first_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('storage_limit', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('quota_warning_sent', sa.Integer(), server_default=sa.text('0'), nullable=False))

    op.add_column('mailboxes', sa.Column('plan', sa.String(length=32), nullable=True))

    op.create_table('security_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_security_events_event_type'), 'security_events', ['event_type'], unique=False)

    op.create_table('backups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('backups')
    op.drop_index(op.f('ix_security_events_event_type'), table_name='security_events')
    op.drop_table('security_events')
    op.drop_column('mailboxes', 'plan')
    op.drop_column('users', 'quota_warning_sent')
    op.drop_column('users', 'storage_limit')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
