"""
API Endpoints - Tags e Bookmarks de mensagens.
"""
import uuid
import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth import get_current_user, UserInfo
from app.models import Tag, MessageTag, MessageBookmark

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tags", tags=["tags"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field(default="#6C63FF", max_length=7)


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    owner_id: Optional[str] = None
    created_at: Optional[str] = None


class TagListResponse(BaseModel):
    tags: List[TagResponse]


class MessageTagCreate(BaseModel):
    message_id: str
    tag_id: str


class BookmarkCreate(BaseModel):
    message_id: str
    conversation_id: str
    note: Optional[str] = Field(default=None, max_length=500)


class BookmarkResponse(BaseModel):
    id: str
    message_id: str
    conversation_id: str
    user_id: str
    note: Optional[str] = None
    created_at: Optional[str] = None


class BookmarkListResponse(BaseModel):
    bookmarks: List[BookmarkResponse]


# ─── Tag Endpoints ───────────────────────────────────────────────────────────

@router.get("/", response_model=TagListResponse)
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Lista todas as tags do usuario."""
    stmt = select(Tag).where(Tag.owner_id == current_user.id)
    result = await db.execute(stmt)
    tags = result.scalars().all()
    return TagListResponse(
        tags=[
            TagResponse(
                id=t.id, name=t.name, color=t.color,
                owner_id=t.owner_id,
                created_at=t.created_at.isoformat() if t.created_at else None,
            )
            for t in tags
        ]
    )


@router.post("/", response_model=TagResponse)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Cria uma nova tag."""
    tag = Tag(
        name=data.name,
        color=data.color,
        owner_id=current_user.id,
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return TagResponse(
        id=tag.id, name=tag.name, color=tag.color,
        owner_id=tag.owner_id,
        created_at=tag.created_at.isoformat() if tag.created_at else None,
    )


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Remove uma tag."""
    stmt = select(Tag).where(Tag.id == tag_id, Tag.owner_id == current_user.id)
    result = await db.execute(stmt)
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Tag nao encontrada")
    await db.execute(delete(MessageTag).where(MessageTag.tag_id == tag_id))
    await db.delete(tag)
    await db.commit()
    return {"message": "Tag removida"}


@router.post("/message", response_model=dict)
async def tag_message(
    data: MessageTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Aplica uma tag a uma mensagem."""
    # Check if already tagged
    stmt = select(MessageTag).where(
        MessageTag.message_id == data.message_id,
        MessageTag.tag_id == data.tag_id,
    )
    exists = (await db.execute(stmt)).scalar_one_or_none()
    if exists:
        return {"message": "Tag ja aplicada"}

    mt = MessageTag(
        message_id=data.message_id,
        tag_id=data.tag_id,
        created_by=current_user.id,
    )
    db.add(mt)
    await db.commit()
    return {"message": "Tag aplicada"}


@router.delete("/message/{message_id}/{tag_id}")
async def untag_message(
    message_id: str,
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Remove uma tag de uma mensagem."""
    await db.execute(
        delete(MessageTag).where(
            MessageTag.message_id == message_id,
            MessageTag.tag_id == tag_id,
        )
    )
    await db.commit()
    return {"message": "Tag removida da mensagem"}


# ─── Bookmark Endpoints ─────────────────────────────────────────────────────

@router.post("/bookmarks", response_model=BookmarkResponse)
async def create_bookmark(
    data: BookmarkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Marca uma mensagem como favorita."""
    # Check if already bookmarked
    stmt = select(MessageBookmark).where(
        MessageBookmark.message_id == data.message_id,
        MessageBookmark.user_id == current_user.id,
    )
    exists = (await db.execute(stmt)).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Mensagem ja marcada")

    bookmark = MessageBookmark(
        message_id=data.message_id,
        conversation_id=data.conversation_id,
        user_id=current_user.id,
        note=data.note,
    )
    db.add(bookmark)
    await db.commit()
    await db.refresh(bookmark)
    return BookmarkResponse(
        id=bookmark.id,
        message_id=bookmark.message_id,
        conversation_id=bookmark.conversation_id,
        user_id=bookmark.user_id,
        note=bookmark.note,
        created_at=bookmark.created_at.isoformat() if bookmark.created_at else None,
    )


@router.get("/bookmarks/{conversation_id}", response_model=BookmarkListResponse)
async def list_bookmarks(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Lista bookmarks de uma conversa."""
    stmt = select(MessageBookmark).where(
        MessageBookmark.conversation_id == conversation_id,
        MessageBookmark.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    bookmarks = result.scalars().all()
    return BookmarkListResponse(
        bookmarks=[
            BookmarkResponse(
                id=b.id,
                message_id=b.message_id,
                conversation_id=b.conversation_id,
                user_id=b.user_id,
                note=b.note,
                created_at=b.created_at.isoformat() if b.created_at else None,
            )
            for b in bookmarks
        ]
    )


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Remove um bookmark."""
    stmt = select(MessageBookmark).where(
        MessageBookmark.id == bookmark_id,
        MessageBookmark.user_id == current_user.id,
    )
    bookmark = (await db.execute(stmt)).scalar_one_or_none()
    if not bookmark:
        raise HTTPException(404, "Bookmark nao encontrado")
    await db.delete(bookmark)
    await db.commit()
    return {"message": "Bookmark removido"}
