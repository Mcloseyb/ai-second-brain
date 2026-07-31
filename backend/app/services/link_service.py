"""
链接业务逻辑层 — 智能双向链接（P5）
-----------------------------------
功能:
  - get_related_notes: 语义相关笔记（实时向量搜索，零 token）
  - detect_title_links: 扫描正文检测其他笔记标题 → 建议链接
  - record_links:      记录显式链接到 note_links 表
  - get_linked_from:   引用某笔记的笔记列表（反向链接）

设计: 语义相关是实时计算的（RAGEngine.search），不落库；
      标题检测 / 手动确认的显式链接才写入 note_links 表，
      供"Linked from"计数与知识图谱(P7)使用。
"""

import logging

from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.note_link import NoteLink
from app.core.rag_engine import rag_engine

logger = logging.getLogger(__name__)

# 语义相关度阈值（低于此值视为不相关）
RELATED_THRESHOLD = 0.40
# 标题检测最小长度（避免单字误报）
MIN_TITLE_LENGTH = 2


class LinkService:
    """双向链接服务"""

    # ============================================================
    # 语义相关笔记（P5.1.1 / 5.1.2）
    # ============================================================
    async def get_related_notes(
        self,
        db: Session,
        note_id: int,
        top_k: int = 5,
    ) -> list[dict]:
        """
        返回与指定笔记语义最相关的 Top-K 笔记

        方案: 用笔记标题+正文作为查询，走 ChromaDB 语义检索
        （每篇笔记一条向量，cosine 距离），排除自身，限定同笔记库。

        Returns:
            [{note_id, title, text, similarity, folder, word_count, tags}, ...]
        """
        note = db.query(Note).filter_by(id=note_id).first()
        if not note or not (note.content or "").strip():
            return []

        # 语义检索（纯语义，不混 BM25 —— 双向链接重语义）
        query_text = f"{note.title}\n{note.content[:2000]}"
        try:
            results = await rag_engine.search(
                query=query_text,
                top_k=top_k * 2,          # 多取一些，过滤自身后仍有余量
                threshold=RELATED_THRESHOLD,
                hybrid=False,
            )
        except Exception as e:
            logger.error(f"语义检索相关笔记失败: {e}")
            return []

        related: list[dict] = []
        seen: set[int] = set()
        for r in results:
            nid = r["note_id"]
            # 排除自身 / 已出现 / 非同一笔记库
            if nid == note_id or nid in seen:
                continue
            other = db.query(Note).filter_by(id=nid).first()
            if not other:
                continue
            if note.notebook_id and other.notebook_id != note.notebook_id:
                continue

            related.append({
                "note_id": nid,
                "title": r["title"] or other.title,
                "text": r.get("text", "")[:200],
                "similarity": r["similarity"],
                "folder": other.folder,
                "word_count": other.word_count,
                "tags": [t.to_dict() for t in other.tags] if other.tags else [],
                "updated_at": other.updated_at.isoformat() if other.updated_at else None,
            })
            seen.add(nid)
            if len(related) >= top_k:
                break

        return related

    # ============================================================
    # 正文标题检测（P5.1.3）
    # ============================================================
    def detect_title_links(self, db: Session, note_id: int) -> list[dict]:
        """
        扫描笔记正文，检测是否包含其他笔记的标题

        命中即视为"潜在引用"，前端展示建议，用户确认后 record_links 落库。

        Returns:
            [{target_note_id, title, count}, ...] count = 标题在正文出现次数
        """
        note = db.query(Note).filter_by(id=note_id).first()
        if not note or not note.content:
            return []

        content = note.content
        # 排除当前笔记库外的笔记（只统计本库）
        query = db.query(Note).filter(Note.id != note_id)
        if note.notebook_id:
            query = query.filter(Note.notebook_id == note.notebook_id)
        other_notes = query.all()

        hits: list[dict] = []
        for other in other_notes:
            title = (other.title or "").strip()
            if len(title) < MIN_TITLE_LENGTH:
                continue
            count = content.count(title)
            if count > 0:
                hits.append({
                    "target_note_id": other.id,
                    "title": title,
                    "count": count,
                })

        return hits

    # ============================================================
    # 记录显式链接（P5.1.4）
    # ============================================================
    def record_links(
        self,
        db: Session,
        source_id: int,
        target_ids: list[int],
        link_type: str = "title",
    ) -> dict:
        """
        批量记录链接（幂等: 已存在的 (source, target, type) 跳过）

        Args:
            source_id: 来源笔记
            target_ids: 目标笔记列表
            link_type: "title"（自动检测）| "manual"（手动确认）

        Returns:
            {"recorded": n, "skipped": m}
        """
        recorded = 0
        skipped = 0
        for target_id in target_ids:
            if target_id == source_id:
                skipped += 1
                continue
            exists = (
                db.query(NoteLink)
                .filter_by(
                    source_note_id=source_id,
                    target_note_id=target_id,
                    link_type=link_type,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            db.add(NoteLink(
                source_note_id=source_id,
                target_note_id=target_id,
                link_type=link_type,
            ))
            recorded += 1

        if recorded:
            db.commit()
            logger.info(f"记录 {recorded} 条链接: 笔记 {source_id} → {target_ids}")
        return {"recorded": recorded, "skipped": skipped}

    # ============================================================
    # 反向链接（Linked from）
    # ============================================================
    def get_linked_from(self, db: Session, note_id: int) -> list[dict]:
        """
        返回引用了指定笔记的其他笔记（反向链接）

        note_links.target_note_id == note_id 的来源笔记。

        Returns:
            [{id, title, folder, word_count, tags, link_type, created_at}, ...]
        """
        links = (
            db.query(NoteLink)
            .filter_by(target_note_id=note_id)
            .order_by(NoteLink.created_at.desc())
            .all()
        )
        result: list[dict] = []
        for link in links:
            source = db.query(Note).filter_by(id=link.source_note_id).first()
            if not source:
                continue
            item = source.to_dict(include_content=False)
            item["link_type"] = link.link_type
            item["link_created_at"] = (
                link.created_at.isoformat() if link.created_at else None
            )
            result.append(item)
        return result


# 服务单例
link_service = LinkService()
