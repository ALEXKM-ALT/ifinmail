"""add_scheduling_tables

Revision ID: ed8923dbff01
Revises: c9e8d7f6a5b4
Create Date: 2026-06-12 09:10:14.159132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed8923dbff01'
down_revision: Union[str, Sequence[str], None] = 'c9e8d7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('campaigns',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('campaign_steps',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('delay_days', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('subject', sa.String(length=512), server_default=sa.text("('')"), nullable=False),
    sa.Column('body_text', sa.Text(), server_default=sa.text("('')"), nullable=False),
    sa.Column('body_html', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scheduled_messages',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=True),
    sa.Column('campaign_step_id', sa.Integer(), nullable=True),
    sa.Column('to_addr', sa.String(length=255), nullable=False),
    sa.Column('cc_addr', sa.String(length=255), nullable=True),
    sa.Column('bcc_addr', sa.String(length=255), nullable=True),
    sa.Column('subject', sa.String(length=512), server_default=sa.text("('')"), nullable=False),
    sa.Column('body_text', sa.Text(), server_default=sa.text("('')"), nullable=False),
    sa.Column('body_html', sa.Text(), nullable=True),
    sa.Column('attachment_ids', sa.Text(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('message_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['campaign_step_id'], ['campaign_steps.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scheduled_messages')
    op.drop_table('campaign_steps')
    op.drop_table('campaigns')
