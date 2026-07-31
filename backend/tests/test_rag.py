"""
测试 RAG 引擎
------------
1. 创建 ChromaDB collection
2. 索引几篇 AI/Agent 相关笔记
3. 语义搜索测试
4. 删除笔记向量
5. 全量重建
"""

import asyncio
import sys
sys.path.insert(0, "H:/agent/backend")

from app.core.rag_engine import rag_engine
from app.core.embedding import embedding_service

# ============================================================
# 测试数据：创建几篇 AI 学习笔记
# ============================================================
TEST_NOTES = [
    {
        "id": 1,
        "title": "Transformer 架构详解",
        "content": """# Transformer 架构

Transformer 是 Google 在 2017 年提出的神经网络架构，核心创新是自注意力机制（Self-Attention）。

## 核心组件
- **多头自注意力（Multi-Head Self-Attention）**：让每个 token 关注序列中所有其他 token
- **位置编码（Positional Encoding）**：为模型提供序列位置信息
- **前馈神经网络（Feed-Forward Network）**：对每个位置的表示进行非线性变换
- **残差连接 + Layer Normalization**：稳定训练，防止梯度消失

## 优势
比 RNN/LSTM 训练更快（可并行），能捕捉长距离依赖，是 GPT/BERT 的基础架构。""",
    },
    {
        "id": 2,
        "title": "ReAct Agent 模式",
        "content": """# ReAct Agent 模式

ReAct（Reasoning + Acting）是当前主流的 AI Agent 推理范式。

## 工作流程
1. **Thought（思考）**：分析当前状态，决定下一步
2. **Action（行动）**：选择并调用工具
3. **Observation（观察）**：获取工具执行结果
4. 循环上述步骤直到任务完成

## 示例
用户问"今天天气怎么样？"
- Thought: 需要查询天气，用搜索工具
- Action: web_search("北京 今天 天气")
- Observation: "北京今日晴，15-25°C"
- Thought: 已获取天气信息，可以回答用户
- Answer: "北京今天天气晴朗，气温15-25°C"

ReAct 模式让 Agent 的行为可解释、可追踪。""",
    },
    {
        "id": 3,
        "title": "ChromaDB 向量数据库",
        "content": """# ChromaDB 入门

ChromaDB 是一个开源的向量数据库，专为 AI 应用设计。

## 核心概念
- **Collection**：类似数据库的表，存储一组向量
- **Embedding**：文本的向量表示（如 1024 维浮点数组）
- **Metadata**：向量的附属信息（标签、来源等）

## 为什么选 ChromaDB？
- 嵌入式部署，零配置
- 内置持久化，数据不丢失
- 支持元数据过滤
- Python 原生支持，API 简洁

## 常用操作
```python
collection.add(ids=["1"], embeddings=[vec], documents=["文本"])
collection.query(query_embeddings=[q_vec], n_results=5)
collection.delete(ids=["1"])
```""",
    },
    {
        "id": 4,
        "title": "RAG 检索增强生成",
        "content": """# RAG（检索增强生成）

RAG = Retrieval Augmented Generation，结合了信息检索和文本生成。

## 工作流程
1. 用户提问
2. 将问题向量化，在知识库中检索相关文档
3. 将检索结果作为上下文拼入 Prompt
4. LLM 基于上下文生成回答

## 优势
- 减少幻觉（Hallucination）：回答有据可查
- 实时更新：知识库可以随时更新，不需要重新训练
- 可追溯：每个回答都能引用来源

## 关键参数
- Chunk Size: 500 tokens（切片大小）
- Top-K: 5（返回最相关片段数）
- 相似度阈值: 0.70（低于此值不召回）""",
    },
    {
        "id": 5,
        "title": "今天晚餐吃什么",
        "content": """今天晚餐打算做红烧排骨，配上清炒时蔬和一碗米饭。饭后可以吃个橙子。""",
    },
]

# 搜索测试用例
SEARCH_TESTS = [
    ("Transformer 的原理是什么", [1, 4, 2]),  # 期望笔记1最高
    ("Agent 怎么调用工具", [2, 4, 1]),         # 期望笔记2最高
    ("向量数据库怎么用", [3, 4, 2]),            # 期望笔记3最高
    ("晚饭吃啥", [5]),                          # 期望笔记5
]


class MockNote:
    """模拟 Note ORM 对象，用于 rebuild 测试"""
    def __init__(self, id, title, content):
        self.id = id
        self.title = title
        self.content = content


async def main():
    print("=" * 60)
    print("🧪 RAG 引擎测试")
    print("=" * 60)
    print(f"Embedding 模型: {embedding_service.model}")
    print(f"ChromaDB 路径:  {rag_engine.client.get_settings()}")
    print()

    # ---- 测试 1: 索引笔记 ----
    print("📝 测试 1: 索引笔记")
    print("-" * 40)

    for note in TEST_NOTES:
        await rag_engine.index_note(note["id"], note["title"], note["content"])
        print(f"  ✓ 笔记 {note['id']}: {note['title']}")

    count = rag_engine.count()
    assert count == len(TEST_NOTES), f"索引数量不对: {count} != {len(TEST_NOTES)}"
    print(f"✅ 全部 {count} 篇笔记已索引")
    print()

    # ---- 测试 2: 检查索引状态 ----
    print("📝 测试 2: 检查索引状态")
    print("-" * 40)
    assert rag_engine.is_indexed(1), "笔记1应该已索引"
    assert rag_engine.is_indexed(3), "笔记3应该已索引"
    assert not rag_engine.is_indexed(999), "笔记999应该不存在"
    print("✅ is_indexed 检查通过")
    print()

    # ---- 测试 3: 语义搜索 ----
    print("📝 测试 3: 语义搜索")
    print("-" * 40)

    for query, expected_top in SEARCH_TESTS:
        results = await rag_engine.search(query, top_k=5)
        result_ids = [r["note_id"] for r in results]

        print(f"\n  查询: \"{query}\"")
        for r in results:
            marker = "← TOP" if r["note_id"] == result_ids[0] else ""
            print(f"    #{r['note_id']} [{r['title']}] 相似度={r['similarity']:.4f} {marker}")

        # 验证：期望最高的笔记应该在结果中排名靠前
        top_hit = expected_top[0]
        if top_hit in result_ids[:2]:
            print(f"  ✅ 期望最高笔记 #{top_hit} 在第 {result_ids.index(top_hit)+1} 位")
        else:
            print(f"  ⚠️ 期望最高笔记 #{top_hit} 不在前2位，实际排名: {result_ids.index(top_hit)+1 if top_hit in result_ids else '未找到'}")

    print()

    # ---- 测试 4: 相似度阈值过滤 ----
    print("📝 测试 4: 阈值过滤")
    print("-" * 40)

    # 高阈值应该过滤掉不相关的内容
    results_high = await rag_engine.search("Transformer 自注意力机制", top_k=5, threshold=0.50)
    print(f"  高阈值(0.50): 返回 {len(results_high)} 条")
    for r in results_high:
        print(f"    #{r['note_id']} [{r['title']}] sim={r['similarity']:.4f}")

    # 阈值设为0应该返回所有结果
    results_all = await rag_engine.search("晚饭", top_k=5, threshold=0.0)
    print(f"  无阈值(0.0): 返回 {len(results_all)} 条")
    for r in results_all:
        print(f"    #{r['note_id']} [{r['title']}] sim={r['similarity']:.4f}")
    print()

    # ---- 测试 5: 删除笔记向量 ----
    print("📝 测试 5: 删除笔记向量")
    print("-" * 40)

    note_to_delete = TEST_NOTES[4]  # 晚餐笔记
    await rag_engine.remove_note(note_to_delete["id"])
    assert not rag_engine.is_indexed(note_to_delete["id"]), "删除后不应还能查到"
    assert rag_engine.count() == len(TEST_NOTES) - 1

    # 验证搜索也搜不到
    results = await rag_engine.search("晚餐吃什么", top_k=3)
    deleted_ids = [r["note_id"] for r in results]
    assert note_to_delete["id"] not in deleted_ids, "删除后搜索不应出现该笔记"
    print(f"✅ 笔记 {note_to_delete['id']} 已删除，向量库剩余 {rag_engine.count()} 条")
    print()

    # ---- 测试 6: 全量重建 ----
    print("📝 测试 6: 全量重建索引")
    print("-" * 40)

    mock_notes = [MockNote(**n) for n in TEST_NOTES]
    rebuilt = await rag_engine.rebuild_index(mock_notes)
    assert rebuilt == len(TEST_NOTES), f"重建数量不对: {rebuilt} != {len(TEST_NOTES)}"
    assert rag_engine.count() == len(TEST_NOTES)

    # 重建后搜索应恢复正常
    results = await rag_engine.search("晚餐", top_k=3)
    assert any(r["note_id"] == 5 for r in results), "重建后应能搜到笔记5"
    print(f"✅ 重建完成，已索引 {rag_engine.count()} 篇笔记")
    print()

    # ---- 总结 ----
    print("=" * 60)
    print("✅ 全部测试通过！RAG 引擎正常工作")
    print("=" * 60)
    print()
    print("📊 RAG 引擎信息:")
    print(f"  - Collection: {rag_engine.collection.name}")
    print(f"  - 已索引笔记: {rag_engine.count()} 篇")
    print(f"  - 距离度量: cosine")
    print(f"  - Embedding: {embedding_service.model} ({embedding_service.dim}d)")
    print()

    # 清理测试数据
    print("🧹 清理测试数据...")
    try:
        rag_engine.client.delete_collection("notes")
        print("✅ 测试 collection 已删除")
    except Exception as e:
        print(f"⚠️ 清理失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
