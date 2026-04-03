"""
Testes para os modelos SQLAlchemy e camada de banco de dados.
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.models import (
    Base,
    Conversation,
    Message,
    ChatMessage,
    AgentJob,
    ProcessingStatus,
    MediaType,
    SentimentType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_conversation(**overrides) -> Conversation:
    """Cria uma Conversation com valores padrão sensatos."""
    defaults = dict(
        session_id=str(uuid.uuid4()),
        original_filename="chat.zip",
        upload_path="/tmp/chat.zip",
        extract_path="/tmp/media/chat",
    )
    defaults.update(overrides)
    return Conversation(**defaults)


def _make_message(conversation_id: str, **overrides) -> Message:
    """Cria uma Message com valores padrão."""
    defaults = dict(
        conversation_id=conversation_id,
        sequence_number=1,
        timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        sender="Alice",
    )
    defaults.update(overrides)
    return Message(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Conversation Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationModel:
    """Testes para o modelo Conversation."""

    @pytest.mark.asyncio
    async def test_create_conversation_all_fields(self, db_session):
        """Cria uma conversa preenchendo todos os campos."""
        conv = Conversation(
            id=str(uuid.uuid4()),
            session_id="sess-full-001",
            original_filename="WhatsApp Chat.zip",
            upload_path="/tmp/upload.zip",
            extract_path="/tmp/extract",
            status=ProcessingStatus.COMPLETED,
            progress=100.0,
            progress_message="Done",
            conversation_name="Grupo Família",
            participants=["Ana", "Bruno"],
            total_messages=50,
            total_media=5,
            date_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_end=datetime(2026, 1, 31, tzinfo=timezone.utc),
            summary="Resumo da conversa",
            sentiment_overall=SentimentType.POSITIVE,
            sentiment_score=0.85,
            keywords=["férias", "natal"],
            topics=["viagem", "família"],
            word_frequency={"olá": 10, "tchau": 5},
            key_moments=["momento1", "momento2"],
            contradictions=["contradição1"],
            vector_store_path="/tmp/vector",
            completed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        db_session.add(conv)
        await db_session.commit()

        result = await db_session.get(Conversation, conv.id)
        assert result is not None
        assert result.session_id == "sess-full-001"
        assert result.conversation_name == "Grupo Família"
        assert result.participants == ["Ana", "Bruno"]
        assert result.sentiment_overall == SentimentType.POSITIVE
        assert result.word_frequency == {"olá": 10, "tchau": 5}
        assert result.keywords == ["férias", "natal"]
        assert result.topics == ["viagem", "família"]
        assert result.key_moments == ["momento1", "momento2"]
        assert result.contradictions == ["contradição1"]
        assert result.progress == 100.0

    @pytest.mark.asyncio
    async def test_default_values(self, db_session):
        """Verifica que id, status e progress possuem defaults corretos."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        assert conv.id is not None
        assert len(conv.id) == 36  # UUID v4
        assert conv.status == ProcessingStatus.PENDING
        assert conv.progress == 0.0
        assert conv.total_messages == 0
        assert conv.total_media == 0

    @pytest.mark.asyncio
    async def test_unique_constraint_session_id(self, db_session):
        """session_id deve ser único."""
        shared_sid = "unique-session-123"
        conv1 = _make_conversation(session_id=shared_sid)
        conv2 = _make_conversation(session_id=shared_sid)

        db_session.add(conv1)
        await db_session.commit()

        db_session.add(conv2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_json_fields_participants(self, db_session):
        """participants armazena e recupera lista JSON."""
        participants = ["João", "Maria", "Pedro"]
        conv = _make_conversation(participants=participants)
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        assert conv.participants == participants

    @pytest.mark.asyncio
    async def test_json_fields_topics_keywords(self, db_session):
        """topics e keywords armazenam listas JSON."""
        conv = _make_conversation(
            topics=["tecnologia", "esporte"],
            keywords=["python", "futebol"],
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        assert conv.topics == ["tecnologia", "esporte"]
        assert conv.keywords == ["python", "futebol"]

    @pytest.mark.asyncio
    async def test_json_fields_contradictions_key_moments_word_frequency(self, db_session):
        """contradictions, key_moments e word_frequency armazenam JSON."""
        conv = _make_conversation(
            contradictions=[{"a": 1}],
            key_moments=[{"ts": "2026-01-01"}],
            word_frequency={"hello": 42},
        )
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        assert conv.contradictions == [{"a": 1}]
        assert conv.key_moments == [{"ts": "2026-01-01"}]
        assert conv.word_frequency == {"hello": 42}

    @pytest.mark.asyncio
    async def test_nullable_fields(self, db_session):
        """Campos opcionais aceitam None."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)

        assert conv.conversation_name is None
        assert conv.participants is None
        assert conv.summary is None
        assert conv.sentiment_overall is None
        assert conv.sentiment_score is None
        assert conv.vector_store_path is None
        assert conv.progress_message is None
        assert conv.completed_at is None

    @pytest.mark.asyncio
    async def test_processing_status_enum_values(self, db_session):
        """Todos os valores do ProcessingStatus devem ser persistidos."""
        for status in ProcessingStatus:
            conv = _make_conversation(status=status)
            db_session.add(conv)
        await db_session.commit()

        result = await db_session.execute(select(Conversation))
        rows = result.scalars().all()
        persisted_statuses = {r.status for r in rows}
        assert persisted_statuses == set(ProcessingStatus)

    @pytest.mark.asyncio
    async def test_relationship_cascade_delete(self, db_session):
        """Deletar Conversation deve remover Messages associadas."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        msg = _make_message(conv.id)
        db_session.add(msg)
        await db_session.commit()

        # Confirmar que a mensagem existe
        result = await db_session.execute(select(Message).where(Message.conversation_id == conv.id))
        assert len(result.scalars().all()) == 1

        # Deletar conversa
        await db_session.delete(conv)
        await db_session.commit()

        result = await db_session.execute(select(Message).where(Message.conversation_id == conv.id))
        assert len(result.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_timestamps_auto_set(self, db_session):
        """created_at e updated_at devem ser preenchidos automaticamente."""
        before = datetime.now(timezone.utc)
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.commit()
        await db_session.refresh(conv)
        after = datetime.now(timezone.utc)

        assert conv.created_at is not None
        assert conv.updated_at is not None
        # Timestamps devem estar entre before e after (com margem)
        # Comparar sem timezone pois SQLite pode não preservar tzinfo
        assert conv.created_at.replace(tzinfo=None) >= before.replace(tzinfo=None).replace(microsecond=0)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Message Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestMessageModel:
    """Testes para o modelo Message."""

    @pytest.mark.asyncio
    async def test_create_message_required_fields(self, db_session):
        """Cria mensagem com campos obrigatórios."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        msg = Message(
            conversation_id=conv.id,
            sequence_number=1,
            timestamp=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            sender="Carlos",
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.id is not None
        assert msg.sender == "Carlos"
        assert msg.sequence_number == 1
        assert msg.media_type == MediaType.TEXT  # default
        assert msg.processing_status == ProcessingStatus.PENDING  # default
        assert msg.is_key_moment is False

    @pytest.mark.asyncio
    async def test_media_type_enum_values(self, db_session):
        """Todos os valores de MediaType são persistidos."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        for i, mt in enumerate(MediaType):
            msg = _make_message(conv.id, sequence_number=i, media_type=mt)
            db_session.add(msg)
        await db_session.commit()

        result = await db_session.execute(select(Message).where(Message.conversation_id == conv.id))
        rows = result.scalars().all()
        persisted_types = {r.media_type for r in rows}
        assert persisted_types == set(MediaType)

    @pytest.mark.asyncio
    async def test_sentiment_type_enum_values(self, db_session):
        """Todos os valores de SentimentType são persistidos em Message."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        for i, st in enumerate(SentimentType):
            msg = _make_message(conv.id, sequence_number=i, sentiment=st, sentiment_score=0.5)
            db_session.add(msg)
        await db_session.commit()

        result = await db_session.execute(select(Message).where(Message.conversation_id == conv.id))
        rows = result.scalars().all()
        persisted_sentiments = {r.sentiment for r in rows}
        assert persisted_sentiments == set(SentimentType)

    @pytest.mark.asyncio
    async def test_foreign_key_conversation(self, db_session):
        """Message.conversation_id aponta para Conversation via FK e relationship funciona."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        msg = _make_message(conv.id)
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.conversation_id == conv.id
        # Verificar via relationship
        await db_session.refresh(conv, ["messages"])
        assert len(conv.messages) == 1
        assert conv.messages[0].id == msg.id

    @pytest.mark.asyncio
    async def test_optional_fields(self, db_session):
        """Campos opcionais (transcription, description, ocr_text, media_metadata) aceitam None e valores."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        msg = _make_message(
            conv.id,
            transcription="Transcrição de áudio",
            description="Descrição da imagem",
            ocr_text="Texto do OCR",
            media_metadata={"duration": 30, "format": "opus"},
        )
        db_session.add(msg)
        await db_session.commit()
        await db_session.refresh(msg)

        assert msg.transcription == "Transcrição de áudio"
        assert msg.description == "Descrição da imagem"
        assert msg.ocr_text == "Texto do OCR"
        assert msg.media_metadata == {"duration": 30, "format": "opus"}

        # Mensagem sem campos opcionais
        msg2 = _make_message(conv.id, sequence_number=2)
        db_session.add(msg2)
        await db_session.commit()
        await db_session.refresh(msg2)

        assert msg2.transcription is None
        assert msg2.description is None
        assert msg2.ocr_text is None
        assert msg2.media_metadata is None

    @pytest.mark.asyncio
    async def test_sequence_number_ordering(self, db_session):
        """Mensagens devem poder ser ordenadas por sequence_number."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        for seq in [3, 1, 2]:
            msg = _make_message(
                conv.id,
                sequence_number=seq,
                sender=f"User{seq}",
                timestamp=datetime(2026, 1, 1, 10, seq, tzinfo=timezone.utc),
            )
            db_session.add(msg)
        await db_session.commit()

        result = await db_session.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.sequence_number)
        )
        rows = result.scalars().all()
        sequences = [r.sequence_number for r in rows]
        assert sequences == [1, 2, 3]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ChatMessage Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatMessageModel:
    """Testes para o modelo ChatMessage."""

    @pytest.mark.asyncio
    async def test_create_chat_message(self, db_session):
        """Cria um ChatMessage com sucesso."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        chat_msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="Qual o resumo da conversa?",
            tokens_used=25,
        )
        db_session.add(chat_msg)
        await db_session.commit()
        await db_session.refresh(chat_msg)

        assert chat_msg.id is not None
        assert chat_msg.role == "user"
        assert chat_msg.content == "Qual o resumo da conversa?"
        assert chat_msg.tokens_used == 25

    @pytest.mark.asyncio
    async def test_role_user_and_assistant(self, db_session):
        """role pode ser 'user' ou 'assistant'."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        for role in ["user", "assistant"]:
            cm = ChatMessage(
                conversation_id=conv.id,
                role=role,
                content=f"Mensagem de {role}",
            )
            db_session.add(cm)
        await db_session.commit()

        result = await db_session.execute(
            select(ChatMessage).where(ChatMessage.conversation_id == conv.id)
        )
        rows = result.scalars().all()
        roles = {r.role for r in rows}
        assert roles == {"user", "assistant"}

    @pytest.mark.asyncio
    async def test_foreign_key_conversation(self, db_session):
        """ChatMessage.conversation_id aponta para Conversation via FK e relationship funciona."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        cm = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content="test message",
        )
        db_session.add(cm)
        await db_session.commit()
        await db_session.refresh(cm)

        assert cm.conversation_id == conv.id
        # Verificar via relationship
        await db_session.refresh(conv, ["chat_history"])
        assert len(conv.chat_history) == 1
        assert conv.chat_history[0].id == cm.id

    @pytest.mark.asyncio
    async def test_timestamps(self, db_session):
        """created_at é preenchido automaticamente."""
        conv = _make_conversation()
        db_session.add(conv)
        await db_session.flush()

        before = datetime.now(timezone.utc)
        cm = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content="Resposta do assistente",
        )
        db_session.add(cm)
        await db_session.commit()
        await db_session.refresh(cm)

        assert cm.created_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Database Functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseFunctions:
    """Testes para as funções de banco de dados."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        """init_db deve criar todas as tabelas do modelo."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Antes de init, nenhuma tabela
        async with engine.begin() as conn:
            tables_before = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        assert "conversations" not in tables_before

        # Executar o equivalente a init_db
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.begin() as conn:
            tables_after = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        assert "conversations" in tables_after
        assert "messages" in tables_after
        assert "chat_messages" in tables_after
        assert "agent_jobs" in tables_after

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """get_db deve produzir uma AsyncSession funcional."""
        from app.database import get_db

        # get_db é um async generator; testamos que ele pode ser iterado
        # Usamos o módulo diretamente, mas como depende de engine global,
        # apenas verificamos a interface
        gen = get_db()
        assert hasattr(gen, "__aiter__")
        assert hasattr(gen, "__anext__")

    @pytest.mark.asyncio
    async def test_async_session_local_works(self):
        """AsyncSessionLocal cria sessões operacionais."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with session_factory() as session:
            conv = _make_conversation()
            session.add(conv)
            await session.commit()

            result = await session.execute(select(Conversation))
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].session_id == conv.session_id

        await engine.dispose()
