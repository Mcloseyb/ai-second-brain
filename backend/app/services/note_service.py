"""
笔记业务逻辑层
-------------
API 路由调用此层，此层操作数据库。
分层目的: API 只管参数校验和响应格式，业务逻辑集中在这里。

P3 更新: create/update/delete 已异步化，自动同步向量库。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.note import Note
from app.models.tag import Tag
from app.core.rag_engine import rag_engine

logger = logging.getLogger(__name__)


class NoteService:
    """笔记业务服务"""

    @staticmethod
    async def create(db: Session, title: str, content: str = "", tags: list[str] | None = None) -> Note:
        """创建笔记（自动同步到向量库）"""
        note = Note(
            title=title,
            content=content,
            word_count=len(content.split()) if content else 0,
        )

        if tags:
            note.tags = NoteService._get_or_create_tags(db, tags)

        db.add(note)
        db.commit()
        db.refresh(note)
        logger.info(f"Created note: {note.id} — {note.title}")

        # P3: 自动同步到向量库（失败不影响创建）
        if content and content.strip():
            try:
                await rag_engine.index_note(note.id, note.title, content)
                note.content_hash = Note.compute_content_hash(content)
                note.last_synced_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"笔记 {note.id} 已自动同步到向量库")
            except Exception as e:
                logger.warning(f"笔记 {note.id} 自动同步向量库失败: {e}")

        return note

    @staticmethod
    async def update(db: Session, note_id: int, title: str | None = None,
               content: str | None = None, tags: list[str] | None = None) -> Note | None:
        """更新笔记（内容变化时自动同步向量库）"""
        note = db.query(Note).filter_by(id=note_id).first()
        if not note:
            return None

        content_changed = False

        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
            note.word_count = len(content.split())
            content_changed = True
        if tags is not None:
            note.tags = NoteService._get_or_create_tags(db, tags)

        note.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(note)
        logger.info(f"Updated note: {note.id}")

        # P3: 内容变化时重新同步向量库
        if content_changed and note.content and note.content.strip():
            try:
                await rag_engine.index_note(note.id, note.title, note.content)
                note.content_hash = Note.compute_content_hash(note.content)
                note.last_synced_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"笔记 {note.id} 向量已更新")
            except Exception as e:
                logger.warning(f"笔记 {note.id} 同步向量库失败: {e}")

        return note

    @staticmethod
    async def delete(db: Session, note_id: int) -> bool:
        """删除笔记（同步清理向量库）"""
        note = db.query(Note).filter_by(id=note_id).first()
        if not note:
            return False
        db.delete(note)
        db.commit()
        logger.info(f"Deleted note: {note_id}")

        # P3: 同步清理向量库（失败不影响删除结果）
        try:
            await rag_engine.remove_note(note_id)
            logger.info(f"笔记 {note_id} 已从向量库移除")
        except Exception as e:
            logger.warning(f"清理笔记 {note_id} 向量失败: {e}")

        return True

    @staticmethod
    def get_by_id(db: Session, note_id: int) -> Note | None:
        """获取单个笔记"""
        return db.query(Note).filter_by(id=note_id).first()

    @staticmethod
    def list_notes(
        db: Session,
        search: str | None = None,
        tag: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Note], int]:
        """
        笔记列表（分页 + 搜索 + 标签筛选）

        Returns:
            (notes, total_count)
        """
        query = db.query(Note)

        # 关键词搜索（标题 + 内容）
        if search:
            keyword = f"%{search}%"
            query = query.filter(
                or_(Note.title.ilike(keyword), Note.content.ilike(keyword))
            )

        # 标签筛选
        if tag:
            query = query.filter(Note.tags.any(Tag.name == tag))

        total = query.count()
        notes = (
            query
            .order_by(Note.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return notes, total

    # ============================================================
    # 私有方法
    # ============================================================

    @staticmethod
    def _get_or_create_tags(db: Session, tag_names: list[str]) -> list[Tag]:
        """根据标签名列表获取或创建标签"""
        tags = []
        for name in tag_names:
            name = name.strip().lower()
            if not name:
                continue
            tag = db.query(Tag).filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.add(tag)
                db.flush()
            tags.append(tag)
        return tags


# 服务单例
note_service = NoteService()
