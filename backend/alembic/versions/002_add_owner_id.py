"""Add owner_id to conversations and create audit_logs table

Revision ID: 002_add_owner_id
Revises: 001_initial
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002_add_owner_id'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add owner_id column to conversations
    op.add_column('conversations', sa.Column('owner_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_conversations_owner_id',
        'conversations', 'users',
        ['owner_id'], ['id'],
    )
    op.create_index('ix_conversations_owner_id', 'conversations', ['owner_id'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_index('ix_conversations_owner_id', table_name='conversations')
    op.drop_constraint('fk_conversations_owner_id', 'conversations', type_='foreignkey')
    op.drop_column('conversations', 'owner_id')
