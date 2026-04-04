"""Add tags, bookmarks, and user role

Revision ID: 004
Revises: 003_custody_audit
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa


revision = '004_tags_bookmarks_rbac'
down_revision = '003_custody_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column to users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('role', sa.String(20), server_default='analyst', nullable=True)
        )

    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('color', sa.String(7), server_default='#6C63FF'),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create message_tags junction table
    op.create_table(
        'message_tags',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('messages.id'), nullable=False, index=True),
        sa.Column('tag_id', sa.String(36), sa.ForeignKey('tags.id'), nullable=False, index=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create message_bookmarks table
    op.create_table(
        'message_bookmarks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('messages.id'), nullable=False, index=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('message_bookmarks')
    op.drop_table('message_tags')
    op.drop_table('tags')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('role')
