"""
笔记库 API — 笔记本管理 + 文件夹树
"""
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notebook import Notebook
from app.models.note import Note

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


# ============================================================
# Schema
# ============================================================

class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class NotebookRename(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


# ============================================================
# CRUD
# ============================================================

@router.get("")
async def list_notebooks(db: Session = Depends(get_db)):
    """获取所有笔记库（含笔记数量）"""
    notebooks = db.query(Notebook).order_by(Notebook.updated_at.desc()).all()
    return {"notebooks": [n.to_dict(include_stats=True) for n in notebooks]}


@router.post("", status_code=201)
async def create_notebook(data: NotebookCreate, db: Session = Depends(get_db)):
    """创建新笔记库"""
    nb = Notebook(name=data.name)
    db.add(nb)
    db.commit()
    db.refresh(nb)
    logger.info(f"笔记库已创建: {nb.name} (id={nb.id})")
    return {"notebook": nb.to_dict()}


@router.delete("/{notebook_id}")
async def delete_notebook(notebook_id: int, db: Session = Depends(get_db)):
    """删除笔记库（级联删除其中所有笔记）"""
    nb = db.query(Notebook).filter_by(id=notebook_id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="笔记库不存在")
    name = nb.name
    db.delete(nb)
    db.commit()
    logger.info(f"笔记库已删除: {name} (id={notebook_id})")
    return {"ok": True}


@router.put("/{notebook_id}")
async def rename_notebook(notebook_id: int, data: NotebookRename, db: Session = Depends(get_db)):
    """重命名笔记库"""
    nb = db.query(Notebook).filter_by(id=notebook_id).first()
    if not nb:
        raise HTTPException(status_code=404, detail="笔记库不存在")
    nb.name = data.name
    db.commit()
    return {"notebook": nb.to_dict()}


# ============================================================
# 文件夹树
# ============================================================

@router.get("/{notebook_id}/folders")
async def get_folder_tree(notebook_id: int, db: Session = Depends(get_db)):
    """
    获取指定笔记库的文件夹树 + 笔记列表
    参考 Obsidian/Notion 的侧边栏结构：

    返回格式:
    {
      "folders": [
        {
          "name": "AI",
          "path": "AI",
          "children": [
            { "name": "Agent", "path": "AI/Agent", "children": [] }
          ]
        }
      ],
      "root_notes": [
        { "id": 1, "title": "未分类笔记", ... }
      ]
    }
    """
    notes = (
        db.query(Note)
        .filter_by(notebook_id=notebook_id)
        .order_by(Note.updated_at.desc())
        .all()
    )

    # 构建文件夹树（笔记挂在文件夹节点内，类似 Windows 资源管理器）
    tree: dict[str, dict] = {}  # path → folder node
    root_notes: list[dict] = []

    for note in notes:
        folder_path = (note.folder or "").strip().strip("/")
        note_dict = note.to_dict(include_content=False)

        if not folder_path:
            root_notes.append(note_dict)
            continue

        # 确保所有父节点存在
        parts = folder_path.split("/")
        current_path = ""
        for part in parts:
            parent_path = current_path
            current_path = f"{current_path}/{part}" if current_path else part

            if current_path not in tree:
                node = {
                    "name": part,
                    "path": current_path,
                    "note_count": 0,
                    "notes": [],       # 该文件夹直属的笔记
                    "children": [],    # 子文件夹
                }
                tree[current_path] = node
                if parent_path and parent_path in tree:
                    if node not in tree[parent_path]["children"]:
                        tree[parent_path]["children"].append(node)

        # 笔记挂在直属文件夹下
        if current_path in tree:
            tree[current_path]["note_count"] += 1
            tree[current_path]["notes"].append(note_dict)

    # 收集根级文件夹
    root_folders = [
        node for path, node in tree.items()
        if "/" not in path
    ]

    return {
        "folders": root_folders,
        "root_notes": root_notes,
        "total": len(notes),
    }


@router.get("/{notebook_id}/notes")
async def list_notebook_notes(
    notebook_id: int,
    folder: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """
    获取指定笔记库和文件夹下的笔记
    folder 为空 → 返回根目录笔记
    folder 为路径 → 递归返回该文件夹及其子文件夹下的所有笔记
    """
    query = db.query(Note).filter_by(notebook_id=notebook_id)

    if folder:
        # 匹配 folder 字段：以 folder/ 开头的笔记（子文件夹笔记也会被包含）
        # e.g. folder="AI" 匹配 "AI", "AI/Agent", "AI/Agent/LangChain"
        query = query.filter(
            (Note.folder == folder) | Note.folder.startswith(folder + "/")
        )
    else:
        # 根目录：folder 为空字符串
        query = query.filter((Note.folder == "") | (Note.folder.is_(None)))

    total = query.count()
    notes = (
        query
        .order_by(Note.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "notes": [n.to_dict(include_content=False) for n in notes],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/notes/{note_id}/move")
async def move_note(
    note_id: int,
    folder: str = "",
    db: Session = Depends(get_db),
):
    """移动笔记到指定文件夹"""
    note = db.query(Note).filter_by(id=note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    note.folder = folder.strip()
    db.commit()
    logger.info(f"笔记 {note_id} 已移动到: {folder or '根目录'}")
    return {"note": note.to_dict(include_content=False)}
