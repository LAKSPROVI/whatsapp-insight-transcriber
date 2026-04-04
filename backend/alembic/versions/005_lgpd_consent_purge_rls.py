"""LGPD compliance: consent tracking, data retention, RLS policies

Revision ID: 005
Revises: 004_tags_bookmarks_rbac
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa


revision = '005_lgpd_consent_purge_rls'
down_revision = '004_tags_bookmarks_rbac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Consent tracking table ─────────────────────────────
    op.create_table(
        'user_consents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('consent_type', sa.String(50), nullable=False),  # upload_processing, data_retention, ai_analysis
        sa.Column('granted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ── 2. Add consent_id to conversations ────────────────────
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.add_column(
            sa.Column('consent_id', sa.String(36), nullable=True)
        )
        batch_op.add_column(
            sa.Column('retention_expires_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column('pii_redacted', sa.Boolean(), server_default='false', nullable=True)
        )

    # ── 3. Privacy policy acceptance on users ─────────────────
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('privacy_policy_accepted_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column('privacy_policy_version', sa.String(20), nullable=True)
        )

    # ── 4. PostgreSQL RLS policies (only on PostgreSQL) ──────
    # Enable RLS on conversations table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$;
    """)

    # Policy: users can only see their own conversations
    op.execute("""
        DO $$ BEGIN
            CREATE POLICY conversations_owner_policy ON conversations
                USING (owner_id = current_setting('app.current_user_id', true)::text
                       OR current_setting('app.current_user_role', true) = 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Enable RLS on messages via conversation ownership
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE POLICY messages_owner_policy ON messages
                USING (
                    conversation_id IN (
                        SELECT id FROM conversations
                        WHERE owner_id = current_setting('app.current_user_id', true)::text
                              OR current_setting('app.current_user_role', true) = 'admin'
                    )
                );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Enable RLS on audit_logs (admin only)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
        EXCEPTION WHEN OTHERS THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE POLICY audit_logs_admin_policy ON audit_logs
                USING (current_setting('app.current_user_role', true) = 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS audit_logs_admin_policy ON audit_logs")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS messages_owner_policy ON messages")
    op.execute("ALTER TABLE messages DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS conversations_owner_policy ON conversations")
    op.execute("ALTER TABLE conversations DISABLE ROW LEVEL SECURITY")

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('privacy_policy_version')
        batch_op.drop_column('privacy_policy_accepted_at')

    with op.batch_alter_table('conversations') as batch_op:
        batch_op.drop_column('pii_redacted')
        batch_op.drop_column('retention_expires_at')
        batch_op.drop_column('consent_id')

    op.drop_table('user_consents')
