"""
标签 API
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tag import Tag

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6B9FFF")


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
