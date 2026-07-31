"""
测试同步服务
----------
1. 首次全量同步 → 全部 synced
2. 再次同步 → 全部 skipped（无变更）
3. 修改笔记后同步 → 仅修改的 synced
4. get_pending / get_status 验证
"""

import asyncio
import sys
sys.path.insert(0, "H:/agent/backend")

from app.database import SessionLocal, init_db
from app.services.note_service import note_service
from app.services.sync_service import sync_service
from app.core.rag_engine import rag_engine

# 测试笔记
TEST_NOTES = [
    ("Transformer 架构", "# Transformer\n\n自注意力机制是核心创新。"),
    ("ReAct Agent", "# ReAct\n\nReasoning + Acting 模式的 Agent。"),
    ("Python 异步", "# asyncio\n\nasync/await 是 Python 异步编程的基础。"),
]


async def main():
    print("=" * 60)
    print("🧪 同步服务测试")
    print("=" * 60)

    # 初始化数据库
    init_db()
    db = SessionLocal()

    try:
        # ---- 准备: 创建测试笔记 ----
        print("\n📝 准备: 创建测试笔记")
        print("-" * 40)
        for title, content in TEST_NOTES:
            note = note_service.create(db, title=title, content=content)
            print(f"  ✓ 笔记 {note.id}: {title}")

        # ---- 测试 1: 首次全量同步 ----
        print("\n📝 测试 1: 首次全量同步")
        print("-" * 40)
        report = await sync_service.sync_all(db)
        print(f"  total={report.total} synced={report.synced} skipped={report.skipped} failed={report.failed}")
        assert report.synced == 3, f"首次同步应全部 synced，实际 {report.synced}"
        assert report.skipped == 0
        assert report.failed == 0
        assert rag_engine.count() == 3, f"ChromaDB 应有 3 条，实际 {rag_engine.count()}"
        print("  ✅ 3 篇全部同步到向量库")

        # ---- 测试 2: 无变更时跳过 ----
        print("\n📝 测试 2: 再次同步（无变更 → 全部跳过）")
        print("-" * 40)
        report2 = await sync_service.sync_all(db)
        print(f"  total={report2.total} synced={report2.synced} skipped={report2.skipped} failed={report2.failed}")
        assert report2.skipped == 3, f"无变更应全部 skipped，实际 {report2.skipped}"
        assert report2.synced == 0
        print("  ✅ 3 篇全部跳过（内容未变化）")

        # ---- 测试 3: 修改后增量同步 ----
        print("\n📝 测试 3: 修改笔记 → 增量同步")
        print("-" * 40)
        # 修改笔记 1
        note1 = note_service.get_by_id(db, 1)
        old_hash = note1.content_hash
        note_service.update(db, 1, content="# Transformer 详解\n\n新增内容：多头注意力的数学原理。")
        db.commit()

        report3 = await sync_service.sync_all(db)
        print(f"  total={report3.total} synced={report3.synced} skipped={report3.skipped} failed={report3.failed}")
        assert report3.synced == 1, f"应只有 1 篇更新，实际 {report3.synced}"
        assert report3.skipped == 2, f"应跳过 2 篇未变更，实际 {report3.skipped}"

        # 验证 hash 已更新
        db.refresh(note1)
        assert note1.content_hash != old_hash, "哈希应已更新"
        assert note1.last_synced_at is not None, "last_synced_at 应已设置"
        print("  ✅ 仅笔记 1 被重新同步，其余跳过")

        # ---- 测试 4: get_pending ----
        print("\n📝 测试 4: get_pending（待同步列表）")
        print("-" * 40)
        pending = sync_service.get_pending(db)
        print(f"  待同步: {len(pending)} 篇")
        assert len(pending) == 0, f"所有笔记应已同步，实际 {len(pending)} 篇待同步"

        # 手动改掉 hash 模拟未同步
        note2 = note_service.get_by_id(db, 2)
        note2.content_hash = "broken_hash"
        db.commit()
        pending2 = sync_service.get_pending(db)
        assert len(pending2) == 1, f"hash 不匹配应有 1 篇待同步，实际 {len(pending2)}"
        print("  ✅ 检测到 1 篇哈希不匹配的笔记")

        # ---- 测试 5: get_status ----
        print("\n📝 测试 5: get_status（同步状态概览）")
        print("-" * 40)
        status = sync_service.get_status(db)
        print(f"  {status}")
        assert status["total_notes"] == 3
        print("  ✅ 状态概览正确")

        # ---- 测试 6: 单篇同步 ----
        print("\n📝 测试 6: sync_note（单篇同步）")
        print("-" * 40)
        result = await sync_service.sync_note(db, 2)
        print(f"  note_id={result.note_id} status={result.status} detail={result.detail}")
        assert result.status == "synced"
        print("  ✅ 单篇同步成功")

        # ---- 测试 7: 不存在的笔记 ----
        print("\n📝 测试 7: 同步不存在的笔记")
        print("-" * 40)
        result = await sync_service.sync_note(db, 99999)
        assert result.status == "error"
        print(f"  ✅ 笔记不存在 → {result.status}: {result.detail}")

        print("\n" + "=" * 60)
        print("✅ 全部测试通过！同步服务正常工作")
        print("=" * 60)

    finally:
        db.close()

        # 清理 ChromaDB 测试数据
        try:
            rag_engine.client.delete_collection("notes")
            print("🧹 ChromaDB 测试 collection 已清理")
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
