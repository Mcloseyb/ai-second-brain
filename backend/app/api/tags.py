"""
标签 API
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tag import Tag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6B9FFF")


class TagMerge(BaseModel):
    from_name: str = Field(..., min_length=1, max_length=100, description="被合并的标签名")
    to_name: str = Field(..., min_length=1, max_length=100, description="保留的标签名")


@router.get("")
async def list_tags(db: Session = Depends(get_db)):
    """标签列表"""
    tags = db.query(Tag).order_by(Tag.name).all()
    return {"tags": [t.to_dict() for t in tags]}


@router.post("", status_code=201)
async def create_tag(data: TagCreate, db: Session = Depends(get_db)):
    """创建标签"""
    existing = db.query(Tag).filter_by(name=data.name.strip().lower()).first()
    if existing:
        return {"tag": existing.to_dict()}

    tag = Tag(name=data.name.strip().lower(), color=data.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"tag": tag.to_dict()}


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """删除标签"""
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"ok": True}


@router.post("/merge")
async def merge_tags(data: TagMerge, db: Session = Depends(get_db)):
    """
    合并两个标签（from → to）
    from 标签关联的所有笔记转移到 to 标签，然后删除 from。
    幂等: 两标签相同或不存在时安全返回。
    """
    from_tag = db.query(Tag).filter_by(name=data.from_name.strip().lower()).first()
    to_tag = db.query(Tag).filter_by(name=data.to_name.strip().lower()).first()

    if not from_tag or not to_tag:
        raise HTTPException(status_code=404, detail="合并的标签不存在")
    if from_tag.id == to_tag.id:
        return {"ok": True, "merged": 0, "from": from_tag.name, "to": to_tag.name}

    from_name = from_tag.name
    to_name = to_tag.name
    # from 的笔记挂到 to（避免重复）
    moved = 0
    for note in list(from_tag.notes):
        if to_tag not in note.tags:
            note.tags.append(to_tag)
            moved += 1
    db.delete(from_tag)
    db.commit()

    logger.info(f"标签合并: {from_name} → {to_name}, 迁移 {moved} 篇笔记")
    return {"ok": True, "merged": moved, "from": from_name, "to": to_name}
