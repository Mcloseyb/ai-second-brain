"""
概念簇数据模型 — 温故知新
=========================
ConceptCluster: Agent 语义聚类结果（持久化 P7 KMeans）
ClusterNote:    簇与笔记的多对多映射
"""

import json
import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from app.database import Base

logger = logging.getLogger(__name__)


class ConceptCluster(Base):
    """概念簇 — 由 Agent 对笔记做语义聚类 + 命名得来"""

    __tablename__ = "concept_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(200), nullable=False)
    # Agent 命名的簇名，如 "神经网络基础"、"训练技巧"；聚类失败时 fallback 为 "簇N"

    embedding = Column(Text, nullable=True)
    # 簇中心向量 JSON；None = 聚类时未计算

    note_count = Column(Integer, default=0, nullable=False)
    # 簇内笔记数量（冗余，方便排序和展示）

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self, include_notes: bool = False) -> dict:
        result = {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "name": self.name,
            "note_count": self.note_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_notes and hasattr(self, "notes"):
            result["notes"] = [
                {"cluster_id": self.id, "note_id": cn.note_id}
                for cn in self.notes
            ]
        return result

    def get_embedding(self) -> list[float] | None:
        """解析簇中心向量"""
        if not self.embedding:
            return None
        try:
            return json.loads(self.embedding)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_embedding(self, vec: list[float]) -> None:
        """序列化簇中心向量"""
        self.embedding = json.dumps(vec, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<ConceptCluster(id={self.id}, name='{self.name}', notes={self.note_count})>"


class ClusterNote(Base):
    """簇与笔记的映射关系（一对一：一篇笔记只属于一个簇）"""

    __tablename__ = "cluster_notes"

    cluster_id = Column(Integer, ForeignKey("concept_clusters.id", ondelete="CASCADE"),
                        primary_key=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"),
                     primary_key=True)

    def __repr__(self) -> str:
        return f"<ClusterNote(cluster={self.cluster_id}, note={self.note_id})>"
