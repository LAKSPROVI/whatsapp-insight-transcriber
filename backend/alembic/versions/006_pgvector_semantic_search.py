"""pgvector semantic search: install extension, embeddings table, vector search

Revision ID: 006
Revises: 005_lgpd_consent_purge_rls
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa


revision = '006_pgvector_semantic_search'
down_revision = '005_lgpd_consent_purge_rls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (requires superuser or extension pre-installed)
    op.execute("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'pgvector extension not available - semantic search will be disabled';
        END $$;
    """)

    # Create message embeddings table
    op.execute("""
        CREATE TABLE IF NOT EXISTS message_embeddings (
            id VARCHAR(36) PRIMARY KEY,
            message_id VARCHAR(36) NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            content_text TEXT NOT NULL,
            embedding vector(1536),
            model VARCHAR(50) DEFAULT 'text-embedding-3-small',
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_message_embedding UNIQUE (message_id)
        );
    """)

    # Create index for vector similarity search (IVFFlat for speed)
    op.execute("""
        DO $$ BEGIN
            CREATE INDEX IF NOT EXISTS idx_message_embeddings_vector
                ON message_embeddings
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Could not create vector index - will fallback to sequential scan';
        END $$;
    """)

    # Index for conversation-scoped queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_embeddings_conversation
            ON message_embeddings(conversation_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
