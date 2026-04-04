"""Initial schema - baseline for all existing tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(100), server_default=''),
        sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Conversations table (without owner_id - added in 002)
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), unique=True, nullable=False, index=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('upload_path', sa.String(512), nullable=False),
        sa.Column('extract_path', sa.String(512), nullable=False),
        sa.Column('status', sa.Enum('pending', 'uploading', 'parsing', 'processing', 'completed', 'failed', name='processingstatus'), nullable=False),
        sa.Column('progress', sa.Float(), server_default='0.0'),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column('conversation_name', sa.String(255), nullable=True),
        sa.Column('participants', sa.JSON(), nullable=True),
        sa.Column('total_messages', sa.Integer(), server_default='0'),
        sa.Column('total_media', sa.Integer(), server_default='0'),
        sa.Column('date_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('date_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('sentiment_overall', sa.Enum('positive', 'negative', 'neutral', 'mixed', name='sentimenttype'), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('topics', sa.JSON(), nullable=True),
        sa.Column('word_frequency', sa.JSON(), nullable=True),
        sa.Column('key_moments', sa.JSON(), nullable=True),
        sa.Column('contradictions', sa.JSON(), nullable=True),
        sa.Column('vector_store_path', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('sender', sa.String(255), nullable=False),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('media_type', sa.Enum('text', 'image', 'audio', 'video', 'document', 'sticker', 'contact', 'location', 'deleted', name='mediatype'), nullable=False),
        sa.Column('media_filename', sa.String(512), nullable=True),
        sa.Column('media_path', sa.String(512), nullable=True),
        sa.Column('media_url', sa.String(512), nullable=True),
        sa.Column('media_metadata', sa.JSON(), nullable=True),
        sa.Column('transcription', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.Enum('positive', 'negative', 'neutral', 'mixed', name='sentimenttype'), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('is_key_moment', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('processing_status', sa.Enum('pending', 'uploading', 'parsing', 'processing', 'completed', 'failed', name='processingstatus'), nullable=False),
        sa.Column('agent_id', sa.String(50), nullable=True),
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Chat messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Agent jobs table
    op.create_table(
        'agent_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('agent_id', sa.String(50), nullable=False),
        sa.Column('message_id', sa.String(36), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('status', sa.Enum('pending', 'uploading', 'parsing', 'processing', 'completed', 'failed', name='processingstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('agent_jobs')
    op.drop_table('chat_messages')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS processingstatus')
    op.execute('DROP TYPE IF EXISTS sentimenttype')
    op.execute('DROP TYPE IF EXISTS mediatype')
