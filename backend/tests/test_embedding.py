"""
测试 Embedding 服务
---------------
1. 创建一篇 Agent 学习笔记
2. 生成嵌入向量
3. 验证向量维度和有效性
4. 测试批量 embedding + 相似度计算
"""

import asyncio
import sys
sys.path.insert(0, "H:/agent/backend")

from app.core.embedding import embedding_service, BGE_LARGE_ZH_DIM

# ============================================================
# 测试用的 Agent 学习笔记
# ============================================================
AGENT_NOTE = """
# AI Agent 学习笔记

## 什么是 Agent？
AI Agent（智能体）是一种能够自主感知环境、做出决策并执行动作的 AI 系统。
与传统的 LLM 一问一答不同，Agent 具备以下核心能力：

1. **感知（Perception）**：接收用户输入和环境反馈
2. **推理（Reasoning）**：分析任务，拆解为可执行的步骤
3. **行动（Action）**：调用工具（搜索、计算、API 等）执行具体操作
4. **观察（Observation）**：获取工具执行结果，纳入下一步推理

## ReAct 模式
ReAct（Reasoning + Acting）是目前最主流的 Agent 推理范式：
- Thought: 当前我需要做什么？
- Action: 调用哪个工具？参数是什么？
- Observation: 工具返回了什么？
- 循环以上步骤，直到任务完成

## Function Calling
大模型的 Function Calling 能力是 Agent 实现的基础：
1. 定义工具 Schema（函数名、描述、参数 JSON Schema）
2. LLM 判断是否需要调用工具
3. LLM 生成工具调用参数
4. 程序执行工具，返回结果
5. LLM 根据结果继续推理

## 多 Agent 协作
复杂任务可以由多个专业 Agent 协作完成：
- 检索 Agent：负责搜集信息
- 分析 Agent：提取关键数据并对比
- 写作 Agent：生成结构化报告
- 审核 Agent：验证事实准确性和逻辑完整性
"""

RELATED_NOTES = [
    "LangChain 是一个用于构建 LLM 应用的框架，提供了 Agent、Chain、Tool 等抽象",
    "Transformer 自注意力机制是 GPT 系列模型的基础架构",
    "向量数据库（如 ChromaDB）用于存储和检索文本的 Embedding 向量",
    "RAG（检索增强生成）结合了信息检索和文本生成，减少大模型幻觉",
]


async def main():
    print("=" * 60)
    print("🧪 Embedding 服务测试")
    print("=" * 60)
    print(f"模型: {embedding_service.model}")
    print(f"维度: {embedding_service.dim}")
    print(f"API:  {embedding_service.client.base_url}")
    print()

    # ---- 测试 1: 单条文本向量化 ----
    print("📝 测试 1: 单条文本向量化")
    print("-" * 40)
    print(f"输入文本: {AGENT_NOTE[:80]}...")
    print()

    vec = await embedding_service.embed(AGENT_NOTE)

    assert len(vec) == BGE_LARGE_ZH_DIM, f"维度错误: 期望 {BGE_LARGE_ZH_DIM}，实际 {len(vec)}"
    assert any(v != 0.0 for v in vec), "向量全为零！"
    print(f"✅ 向量维度: {len(vec)} ✓")
    print(f"✅ 向量非零: True ✓")
    print(f"   前 5 维: [{', '.join(f'{v:.6f}' for v in vec[:5])}]")
    print(f"   后 5 维: [{', '.join(f'{v:.6f}' for v in vec[-5:])}]")
    print()

    # ---- 测试 2: 批量向量化 ----
    print("📝 测试 2: 批量向量化")
    print("-" * 40)
    texts = [AGENT_NOTE] + RELATED_NOTES
    print(f"文本数量: {len(texts)}")

    vecs = await embedding_service.embed_batch(texts)

    assert len(vecs) == len(texts), f"数量不匹配: 期望 {len(texts)}，实际 {len(vecs)}"
    for i, v in enumerate(vecs):
        assert len(v) == BGE_LARGE_ZH_DIM, f"第 {i} 个向量维度错误"
        assert any(x != 0.0 for x in v), f"第 {i} 个向量全为零！"
    print(f"✅ 全部 {len(vecs)} 条文本向量化成功 ✓")
    print()

    # ---- 测试 3: 语义相似度 ----
    print("📝 测试 3: 语义相似度计算")
    print("-" * 40)

    # Agent 笔记 vs 相关知识
    pairs = [
        ("Agent 笔记 vs LangChain", AGENT_NOTE, RELATED_NOTES[0]),
        ("Agent 笔记 vs Transformer", AGENT_NOTE, RELATED_NOTES[1]),
        ("Agent 笔记 vs 向量数据库", AGENT_NOTE, RELATED_NOTES[2]),
        ("Agent 笔记 vs RAG", AGENT_NOTE, RELATED_NOTES[3]),
    ]

    for label, t1, t2 in pairs:
        sim = await embedding_service.similarity(t1, t2)
        print(f"  {label}: 相似度 = {sim:.4f}")

    # 同一篇笔记 vs 自己 — 应该 ≈1.0
    self_sim = await embedding_service.similarity(AGENT_NOTE, AGENT_NOTE)
    print(f"  笔记 vs 自己: 相似度 = {self_sim:.4f} (期望 ≈1.0) ✓")

    # 不相关内容 vs 笔记
    unrelated = "今天天气真好，适合出去散步和晒太阳"
    unrelated_sim = await embedding_service.similarity(AGENT_NOTE, unrelated)
    print(f"  笔记 vs 无关内容: 相似度 = {unrelated_sim:.4f} (应该较低)")
    print()

    # ---- 总结 ----
    print("=" * 60)
    print("✅ 全部测试通过！Embedding 服务正常工作")
    print("=" * 60)
    print()
    print("📊 BGE-Large-ZH 模型信息:")
    print(f"  - 模型: {embedding_service.model}")
    print(f"  - 向量维度: {BGE_LARGE_ZH_DIM}")
    print(f"  - 适用场景: 中文语义检索、文本相似度、聚类")
    print(f"  - 提供方: SiliconFlow (硅基流动)")


if __name__ == "__main__":
    asyncio.run(main())
