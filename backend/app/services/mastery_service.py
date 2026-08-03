"""
掌握度业务服务 — S1 知识进阶
=============================
概念 CRUD、相关笔记查找、评估对话管理、评分更新。
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.mastery import ConceptMastery, MasterySession
from app.models.note import Note
from app.models.tag import Tag
from app.core.rag_engine import rag_engine

logger = logging.getLogger(__name__)


class MasteryService:
    """掌握度追踪业务逻辑"""

    # ============================================================
    # 概念管理
    # ============================================================

    def get_or_create_concept(
        self, db: Session, concept_name: str, notebook_id: int
    ) -> ConceptMastery:
        """获取或创建概念掌握度记录"""
        concept = (
            db.query(ConceptMastery)
            .filter(
                and_(
                    ConceptMastery.concept_name == concept_name,
                    ConceptMastery.notebook_id == notebook_id,
                )
            )
            .first()
        )
        if not concept:
            concept = ConceptMastery(
                concept_name=concept_name,
                notebook_id=notebook_id,
            )
            db.add(concept)
            db.commit()
            db.refresh(concept)
            logger.info(f"创建概念掌握度: {concept_name} (notebook={notebook_id})")
        return concept

    def get_concepts(
        self, db: Session, notebook_id: int
    ) -> list[ConceptMastery]:
        """获取笔记库下所有概念的掌握度列表"""
        return (
            db.query(ConceptMastery)
            .filter(ConceptMastery.notebook_id == notebook_id)
            .order_by(ConceptMastery.updated_at.desc())
            .all()
        )

    def get_concept_detail(
        self, db: Session, concept_name: str, notebook_id: int
    ) -> ConceptMastery | None:
        """获取单个概念详情（含评估历史）"""
        return (
            db.query(ConceptMastery)
            .filter(
                and_(
                    ConceptMastery.concept_name == concept_name,
                    ConceptMastery.notebook_id == notebook_id,
                )
            )
            .first()
        )

    # ============================================================
    # 相关笔记查找
    # ============================================================

    async def find_related_notes(
        self, db: Session, concept_name: str, notebook_id: int
    ) -> list[dict]:
        """
        查找与该概念相关的笔记。
        优先级: ① 标签名精确匹配 → ② 语义搜索
        """
        notes: list[Note] = []

        # 1. 标签匹配 — 查找 name == concept_name 的标签下所有笔记
        tag = db.query(Tag).filter(Tag.name == concept_name.lower()).first()
        if tag:
            tagged_notes = [
                n for n in tag.notes
                if n.notebook_id == notebook_id
                and n.deleted_at is None
                and n.content
                and n.content.strip()
            ]
            notes.extend(tagged_notes)
            logger.info(
                f"标签匹配: concept='{concept_name}' → tag='{tag.name}' → {len(tagged_notes)} 篇笔记"
            )

        # 2. 标签匹配不足 → 语义搜索补充
        if len(notes) < 3:
            try:
                search_results = await rag_engine.search(
                    query=concept_name,
                    top_k=8,
                    threshold=0.0,
                    hybrid=False,  # 纯语义搜索概念相关笔记
                )
                existing_ids = {n.id for n in notes}
                for r in search_results:
                    if r["note_id"] not in existing_ids:
                        note = db.query(Note).get(r["note_id"])
                        if (
                            note
                            and note.deleted_at is None
                            and note.notebook_id == notebook_id
                        ):
                            notes.append(note)
                            existing_ids.add(note.id)
                    if len(notes) >= 8:
                        break
                logger.info(
                    f"语义搜索: concept='{concept_name}' → 补充 {len(notes) - (len(tagged_notes) if tag else 0)} 篇"
                )
            except Exception as e:
                logger.warning(f"语义搜索失败（不影响评估）: {e}")

        # 去重 + 截断（最多 8 篇，避免 context 过长）
        seen = set()
        result = []
        for n in notes[:8]:
            if n.id not in seen:
                seen.add(n.id)
                content = (n.content or "")[:2000]
                result.append({
                    "id": n.id,
                    "title": n.title,
                    "content": content,
                    "folder": n.folder or "",
                })

        return result

    # ============================================================
    # 评估对话管理
    # ============================================================

    def create_session(
        self, db: Session, concept_name: str, notebook_id: int, messages: list[dict]
    ) -> MasterySession:
        """创建新的评估对话"""
        session = MasterySession(
            concept_name=concept_name,
            notebook_id=notebook_id,
        )
        session.set_messages(messages)
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info(f"创建评估对话: session={session.id} concept='{concept_name}'")
        return session

    def save_session_messages(
        self, db: Session, session: MasterySession, messages: list[dict]
    ) -> None:
        """保存对话消息到 session"""
        session.set_messages(messages)
        db.commit()
        logger.debug(f"保存对话: session={session.id} messages={len(messages)}")

    def complete_session(
        self,
        db: Session,
        session: MasterySession,
        score: float,
        summary: str,
        strengths: list[str],
        weaknesses: list[str],
    ) -> ConceptMastery:
        """
        完成评估 — 更新 session 评分 + 更新 concept 掌握度。

        Returns:
            更新后的 ConceptMastery
        """
        # 更新 session
        session.final_score = score
        session.summary = summary
        db.commit()

        # 更新 concept mastery
        concept = self.get_or_create_concept(
            db, session.concept_name, session.notebook_id
        )

        # 新评分 = 加权平均（历史评分权重 0.3，新评分权重 0.7）
        if concept.assessment_count > 0:
            concept.mastery_score = round(
                concept.mastery_score * 0.3 + score * 0.7, 1
            )
        else:
            concept.mastery_score = score

        concept.assessment_count += 1
        concept.last_assessed_at = datetime.now(timezone.utc)
        concept.strengths = json.dumps(strengths, ensure_ascii=False)
        concept.weaknesses = json.dumps(weaknesses, ensure_ascii=False)
        db.commit()

        logger.info(
            f"评估完成: concept='{concept.concept_name}' "
            f"score={concept.mastery_score} (new={score}) "
            f"count={concept.assessment_count}"
        )
        return concept

    def get_sessions(
        self,
        db: Session,
        notebook_id: int,
        concept_name: str | None = None,
        limit: int = 20,
    ) -> list[MasterySession]:
        """获取评估历史"""
        q = db.query(MasterySession).filter(
            MasterySession.notebook_id == notebook_id
        )
        if concept_name:
            q = q.filter(MasterySession.concept_name == concept_name)
        return q.order_by(MasterySession.created_at.desc()).limit(limit).all()


# 全局单例
mastery_service = MasteryService()
