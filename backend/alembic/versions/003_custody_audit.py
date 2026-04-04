"""Add custody chain, integrity certificates, and enhanced audit columns

Revision ID: 003
Revises: 002_add_owner_id
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '003_custody_audit'
down_revision = '002_add_owner_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create custody_chain table
    op.create_table(
        'custody_chain',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prev_hash', sa.String(64), nullable=False),
        sa.Column('current_hash', sa.String(64), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create integrity_certificates table
    op.create_table(
        'integrity_certificates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False, index=True),
        sa.Column('cert_type', sa.String(50), server_default='INTEGRITY'),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('issuer_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('zip_hash', sa.String(64), nullable=True),
        sa.Column('merkle_root', sa.String(64), nullable=True),
        sa.Column('file_manifest', sa.Text(), nullable=True),
        sa.Column('chain_valid', sa.Boolean(), server_default='0'),
        sa.Column('signature', sa.String(128), nullable=True),
        sa.Column('algorithm', sa.String(20), server_default='SHA-256'),
        sa.Column('cert_metadata', sa.Text(), nullable=True),
    )

    # Add new columns to audit_logs for hash chain support
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.add_column(sa.Column('user_agent', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('request_id', sa.String(36), nullable=True))
        batch_op.add_column(sa.Column('prev_hash', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('event_hash', sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.drop_column('event_hash')
        batch_op.drop_column('prev_hash')
        batch_op.drop_column('request_id')
        batch_op.drop_column('user_agent')

    op.drop_table('integrity_certificates')
    op.drop_table('custody_chain')
