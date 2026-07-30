# AI Second Brain — 总体规划报告

> **版本**: v1.0  
> **创建日期**: 2026-07-30  
> **最后更新**: 2026-07-30  
> **状态**: 规划阶段 → 准备启动 P1

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [技术选型说明](#3-技术选型说明)
4. [数据库设计](#4-数据库设计)
5. [API 接口设计](#5-api-接口设计)
6. [RAG 引擎设计](#6-rag-引擎设计)
7. [多 Agent 系统设计](#7-多-agent-系统设计)
8. [桌面 UI 设计](#8-桌面-ui-设计)
9. [分阶段开发计划](#9-分阶段开发计划)
10. [打包与部署](#10-打包与部署)
11. [面试要点汇总](#11-面试要点汇总)

---

## 1. 项目概述

### 1.1 项目定位

AI 协同个人知识库管理系统是一个**桌面应用程序**，核心定位是 **AI 驱动的知识互联笔记系统**：
- 管理学习笔记，AI 自动打标签 + 发现关联
- 语义搜索自己的知识库（RAG）
- 智能双向链接 — 打开笔记自动显示相关内容
- AI 出题自测 — 检验学习效果
- 知识图谱可视化 + 学习回顾

### 1.2 核心价值

| 用户痛点 | 解决方案 |
|----------|---------|
| 笔记写了很多，找不到 | RAG 语义搜索 + 混合检索 |
| 写标签太麻烦 | AI 自动分析内容推荐标签 |
| 知识孤岛，各学各的 | 智能双向链接 — 自动发现关联笔记 |
| 学完不知道掌握没 | AI 出题自测 + 批改解析 |
| 不知道自己学了多少 | 知识图谱 + 周报总结 |

### 1.3 最终交付物

1. 一个 `.exe` 可执行文件，双击即用
2. 完整的 GitHub 开源仓库（代码 + 文档）
3. 演示视频
4. 简历描述 + 面试问答准备

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    ai-second-brain.exe                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │                PySide6 桌面层                      │   │
│  │                                                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐│   │
│  │  │ 智能笔记  │ │ 知识问答  │ │ 深度研究  │ │ 看板 ││   │
│  │  │ 富文本编辑│ │ RAG对话  │ │多Agent   │ │知识图谱││   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────┘│   │
│  │                                                   │   │
│  │  通信层：httpx.AsyncClient + SSE Stream           │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │ HTTP (localhost:8000)              │
│  ┌──────────────────┴───────────────────────────────┐   │
│  │                 FastAPI 后端层                     │   │
│  │                                                   │   │
│  │  API 路由 ──→ Service 业务层 ──→ 数据访问层       │   │
│  │       │              │              │             │   │
│  │       ▼              ▼              ▼             │   │
│  │  参数校验      业务编排       SQLAlchemy ORM       │   │
│  │  Pydantic      RAG/Agent      CRUD 操作           │   │
│  │                                                   │   │
│  │  ┌──────────────────────────────────────┐        │   │
│  │  │           AI 引擎                     │        │   │
│  │  │  ├─ LLM 调用 (DeepSeek API)          │        │   │
│  │  │  ├─ RAG 引擎 (ChromaDB + Embedding)  │        │   │
│  │  │  ├─ Agent 编排 (LangGraph)           │        │   │
│  │  │  └─ 工具系统 (搜索/计算/文件)         │        │   │
│  │  └──────────────────────────────────────┘        │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                   │
│  ┌──────────────────┴───────────────────────────────┐   │
│  │                  数据层                            │   │
│  │  ├─ SQLite (data/app.db)                          │   │
│  │  │   ├─ notes 表                                  │   │
│  │  │   ├─ documents 表                              │   │
│  │  │   ├─ conversations 表                          │   │
│  │  │   ├─ messages 表                               │   │
│  │  │   └─ tags 表 + note_tags 多对多                │   │
│  │  ├─ ChromaDB (data/chroma_db/)                    │   │
│  │  │   └─ document_chunks collection                │   │
│  │  └─ 文件系统 (data/uploads/)                       │   │
│  │      └─ 原始文档 PDF/DOCX/MD/TXT                  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 数据流

#### 基础对话流
```
用户输入问题
    → 桌面端 httpx POST /api/chat
    → FastAPI chat.py
    → core/llm.py 调用 DeepSeek
    → SSE 流式返回给桌面端
    → 桌面端实时渲染 Markdown
```

#### RAG 问答流
```
用户上传文档
    → POST /api/documents/upload
    → document_parser.py 解析文本
    → rag_engine.py 切片(500tokens/块)
    → embedding.py 向量化
    → ChromaDB 存储

用户提问（基于文档）
    → POST /api/rag/query
    → rag_engine.py：问题向量化 → ChromaDB.search(Top-5) → BM25关键词检索
    → 混合加权排序 → LLM 重排序过滤
    → 拼接 Context + 问题 → LLM 生成回答
    → SSE 流式返回（含引用来源）
```

#### 多 Agent 深度研究流
```
用户提交研究主题
    → POST /api/research/start
    → orchestrator.py 启动 LangGraph 工作流
    
    Step 1 — 检索 Agent (Retriever)
        ├ 工具: web_search, vector_search, note_search
        └ 产出: 相关资料列表
    
    Step 2 — 分析 Agent (Analyst)
        ├ 输入: 检索 Agent 的结果
        ├ 工具: calculator
        └ 产出: 结构化分析对比表
    
    Step 3 — 写作 Agent (Writer)
        ├ 输入: 分析 Agent 的结果
        └ 产出: 报告 Markdown 初稿
    
    Step 4 — 审核 Agent (Reviewer)
        ├ 输入: 写作 Agent 的初稿 + 原始资料
        ├ 检查: 事实准确性、逻辑完整性、格式规范
        └ 输出: 通过 / 需修改（附修改意见）
    
    如果审核未通过 → 回到 Step 3 重写
    如果审核通过 → SSE 推送最终报告给桌面端
```

---

## 3. 技术选型说明

### 3.1 为什么选 PySide6 而不是 Electron？

| 对比维度 | PySide6 | Electron |
|---------|---------|----------|
| 开发语言 | Python（一致） | JS + HTML + CSS（要新学） |
| 打包体积 | ~80MB | ~200MB+ |
| 内存占用 | ~100MB | ~300MB+ |
| 学习成本 | 低（你已有 Python 基础） | 高（全新语言栈） |
| 与后端集成 | 嵌入式，同一进程 | 独立进程，IPC 通信 |
| 简历价值 | 高（企业桌面软件） | 高（跨平台桌面应用） |
| 适合场景 | 单平台（Windows）专业桌面软件 | 跨平台桌面应用 |

### 3.2 为什么选 LangChain + LangGraph 而不是自己写？

| 对比维度 | LangChain/LangGraph | 自己写 |
|---------|-------------------|--------|
| Agent 编排 | 内置 StateGraph 状态图 | 需要自己实现 FSM |
| 工具定义 | @tool 装饰器，标准接口 | 需要自己定义协议 |
| Prompt 管理 | ChatPromptTemplate | 字符串拼接 |
| LLM 切换 | 一行代码换模型 | 改 API 调用 |
| 社区生态 | 大量参考案例 | 无 |
| 面试价值 | 业界标准，高频考点 | 能聊但不够标准化 |

**但**，P1 阶段我们**不用 LangChain**。P1 先用原生 OpenAI SDK 手写调用，让你理解底层原理。P3/P4 再引入 LangChain，这样你能讲清楚"LangChain 帮我解决了什么"。

### 3.3 为什么选 ChromaDB 而不是 FAISS/Pinecone？

| 对比维度 | ChromaDB | FAISS | Pinecone |
|---------|----------|-------|----------|
| 部署 | 嵌入式，pip install 即用 | 嵌入式 | 云服务 |
| 持久化 | ✅ 内置 | ❌ 需手动 | 自动 |
| 元数据过滤 | ✅ | ❌ | ✅ |
| Python 友好度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 学习成本 | 低 | 中 | 低（但要钱） |
| 面试价值 | 社区流行 | 经典算法 | 企业级 |

ChromaDB 最适合：开发零配置，面试聊得深（基于 HNSW 算法的近似最近邻搜索）。

---

## 4. 数据库设计

### 4.1 ER 图（逻辑）

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│   notes  │       │  note_tags   │       │   tags   │
├──────────┤       ├──────────────┤       ├──────────┤
│ id (PK)  │──┐    │ note_id (FK) │    ┌──│ id (PK)  │
│ title    │  └────│ tag_id (FK)  │────┘  │ name     │
│ content  │       └──────────────┘       │ color    │
│ format   │                              └──────────┘
│ created  │
│ updated  │       ┌──────────────┐
└──────────┘       │  documents   │
                   ├──────────────┤
                   │ id (PK)      │
                   │ filename     │
                   │ file_path    │
                   │ file_type    │
                   │ file_size    │
                   │ chunk_count  │
                   │ status       │
                   │ created      │
                   └──────────────┘

┌──────────────┐       ┌──────────────┐
│ conversations│       │   messages   │
├──────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK)      │
│ title        │  └────│ conv_id (FK) │
│ created      │       │ role         │
│ updated      │       │ content      │
└──────────────┘       │ tokens       │
                       │ created      │
                       └──────────────┘
```

### 4.2 表结构详细定义

#### notes 表
```sql
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    format      TEXT NOT NULL DEFAULT 'markdown',  -- 'markdown' | 'richtext'
    word_count  INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### tags 表
```sql
CREATE TABLE tags (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    color   TEXT DEFAULT '#3B82F6'
);
```

#### note_tags 表（多对多关联）
```sql
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);
```

#### documents 表
```sql
CREATE TABLE documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    file_type   TEXT NOT NULL,       -- 'pdf' | 'docx' | 'md' | 'txt'
    file_size   INTEGER,             -- bytes
    chunk_count INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'processing', -- 'processing' | 'ready' | 'error'
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### conversations 表
```sql
CREATE TABLE conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT DEFAULT '新对话',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### messages 表
```sql
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,     -- 'user' | 'assistant' | 'system'
    content         TEXT NOT NULL,
    tokens          INTEGER DEFAULT 0,
    sources         TEXT,              -- JSON: [{doc_id, chunk_id, text}]
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. API 接口设计

### 5.1 接口总览

| 方法 | 路径 | 说明 | 阶段 |
|------|------|------|------|
| `POST` | `/api/chat` | 基础对话（SSE 流式） | P1 |
| `GET` | `/api/conversations` | 对话列表 | P1 |
| `POST` | `/api/conversations` | 创建新对话 | P1 |
| `GET` | `/api/conversations/{id}/messages` | 获取对话历史 | P1 |
| `POST` | `/api/notes` | 创建笔记 | P2 |
| `GET` | `/api/notes` | 笔记列表（分页+搜索） | P2 |
| `GET` | `/api/notes/{id}` | 获取笔记详情 | P2 |
| `PUT` | `/api/notes/{id}` | 更新笔记 | P2 |
| `DELETE` | `/api/notes/{id}` | 删除笔记 | P2 |
| `POST` | `/api/notes/{id}/tags` | 添加标签 | P2 |
| `GET` | `/api/tags` | 标签列表 | P2 |
| `POST` | `/api/documents/upload` | 上传文档 | P3 |
| `GET` | `/api/documents` | 文档列表 | P3 |
| `DELETE` | `/api/documents/{id}` | 删除文档 | P3 |
| `POST` | `/api/rag/query` | RAG 问答（SSE） | P3 |
| `POST` | `/api/chat/tool` | 工具调用对话（SSE） | P4 |
| `POST` | `/api/research/start` | 启动深度研究（SSE） | P5 |
| `GET` | `/api/research/{id}/status` | 研究任务状态 | P5 |
| `GET` | `/api/dashboard/stats` | 统计数据 | P7 |
| `GET` | `/api/dashboard/graph` | 知识图谱数据 | P7 |

### 5.2 关键接口详情

#### POST /api/chat （SSE 流式）

**请求**:
```json
{
  "conversation_id": 1,
  "message": "你好，帮我总结一下最近关于Transformer的笔记"
}
```

**响应（SSE 事件流）**:
```
data: {"type": "thinking", "content": "正在检索相关笔记..."}

data: {"type": "token", "content": "根据"}

data: {"type": "token", "content": "你的"}

data: {"type": "token", "content": "笔记..."}

data: {"type": "done", "message_id": 42, "tokens": 156}
```

#### POST /api/rag/query （RAG 问答）

**请求**:
```json
{
  "question": "特斯拉的4680电池有什么优势？",
  "document_ids": [1, 3],
  "top_k": 5
}
```

**响应（SSE 事件流）**:
```
data: {"type": "retrieving", "message": "正在检索相关文档片段..."}

data: {"type": "sources", "sources": [{"doc_id": 1, "filename": "特斯拉财报.pdf", "chunk_text": "...", "score": 0.92}]}

data: {"type": "token", "content": "4680"}

data: {"type": "token", "content": "电池..."}

data: {"type": "done", "answer": "完整回答...", "sources": [...]}
```

#### POST /api/research/start （深度研究）

**请求**:
```json
{
  "topic": "对比2024年特斯拉和比亚迪的市场策略",
  "use_web_search": true,
  "use_knowledge_base": true,
  "document_ids": [1, 2, 3]
}
```

**响应（SSE 事件流）**:
```
data: {"type": "agent_status", "agent": "retriever", "status": "running", "message": "检索Agent开始工作..."}

data: {"type": "agent_log", "agent": "retriever", "action": "web_search", "input": "特斯拉 2024 市场策略"}

data: {"type": "agent_log", "agent": "retriever", "observation": "找到 8 条相关结果"}

data: {"type": "agent_status", "agent": "retriever", "status": "done", "result": "共找到15份资料"}

data: {"type": "agent_status", "agent": "analyst", "status": "running", "message": "分析Agent正在提取关键信息..."}

data: {"type": "agent_status", "agent": "writer", "status": "running", "message": "写作Agent正在生成报告..."}

data: {"type": "token", "content": "# 2024年特斯拉与比亚迪市场策略对比报告\n\n"}

data: {"type": "agent_status", "agent": "reviewer", "status": "running"}

data: {"type": "agent_status", "agent": "reviewer", "status": "done", "verdict": "passed"}

data: {"type": "done", "report": "完整报告..."}
```

---

## 6. RAG 引擎设计

### 6.1 文档处理管道

```
原始文档
    │
    ▼
[1] 文档解析 (document_parser.py)
    ├─ PDF: PyMuPDF (fitz)
    ├─ DOCX: python-docx
    ├─ MD: 直接读取
    └─ TXT: 直接读取（自动检测编码）
    │
    ▼
[2] 文本清洗
    ├─ 去除多余空白/换行
    ├─ 保留段落结构
    └─ 提取表格/图片说明文字
    │
    ▼
[3] 智能切片 (rag_engine.py)
    ├─ RecursiveCharacterTextSplitter
    ├─ chunk_size = 500 tokens
    ├─ chunk_overlap = 50 tokens
    └─ 按段落/句子边界切分（保留语义完整性）
    │
    ▼
[4] 向量化 (embedding.py)
    ├─ 模型: text-embedding-3-small (via DeepSeek API)
    ├─ 维度: 1536
    ├─ 批量: 每批 20 个 chunk
    └─ 重试: 单条失败重试 3 次
    │
    ▼
[5] 存储 (ChromaDB)
    ├─ collection: document_chunks
    ├─ metadata: {doc_id, chunk_index, filename, page}
    └─ 持久化: data/chroma_db/
```

### 6.2 检索管道

```
用户问题
    │
    ▼
[1] 问题向量化
    │
    ▼
[2] 混合检索
    ├─ 语义检索: ChromaDB.query(embedding, top_k=10)
    └─ 关键词检索: BM25 (rank_bm25)
    │
    ▼
[3] 加权融合 (Reciprocal Rank Fusion)
    ├─ 语义: 权重 0.7
    ├─ BM25: 权重 0.3
    └─ 取 Top-5
    │
    ▼
[4] LLM 重排序
    ├─ 对5个结果逐一判断相关性
    └─ 过滤不相关内容（score < 0.7）
    │
    ▼
[5] 构建 Prompt
    ├─ System: "你是一个知识助手，请根据以下资料回答问题..."
    ├─ Context: [拼接过滤后的 chunk]
    ├─ User Question
    └─ 引用格式要求
    │
    ▼
[6] LLM 生成回答
    └─ SSE 流式返回
```

---

## 7. 多 Agent 系统设计

### 7.1 Agent 角色定义

#### 检索 Agent（Retriever）
```
System Prompt 要点:
- 角色: 资深信息检索专家
- 能力: 知道去哪里找什么信息，用什么关键词最有效
- 工具: web_search, vector_search, note_search
- 输出: 结构化资料列表，每项含 {title, source, relevance, summary, url}
- 约束: 不做分析，只做检索和初步筛选
```

#### 分析 Agent（Analyst）
```
System Prompt 要点:
- 角色: 资深商业/技术分析师
- 能力: 从原始资料提取关键数据，做对比分析，发现模式
- 工具: calculator（仅当需要计算时）
- 输入: 检索Agent的资料列表
- 输出: 结构化对比表 {维度, 公司A, 公司B, 数据来源}
- 约束: 只基于给定资料分析，不做主观判断
```

#### 写作 Agent（Writer）
```
System Prompt 要点:
- 角色: 专业报告撰写人
- 能力: 将分析要点转化为流畅、专业的报告
- 工具: 无（纯文本生成）
- 输入: 分析Agent的对比表
- 输出: Markdown格式报告
- 风格: 专业但易读，有数据支撑，有逻辑结构
- 约束: 必须标注数据来源
```

#### 审核 Agent（Reviewer）
```
System Prompt 要点:
- 角色: 严格的质量审核专家
- 能力: 发现事实错误、逻辑漏洞、格式问题
- 工具: 可回查原始资料
- 输入: 报告初稿 + 原始资料列表
- 输出: {verdict: "pass"|"revise", issues: [{severity, description, suggestion}]}
- 约束: 只看事实准确性，不看文风喜好
```

### 7.2 LangGraph 编排

```python
# orchestrator.py — 用 LangGraph 定义工作流

from langgraph.graph import StateGraph, END

class ResearchState(TypedDict):
    topic: str
    retrieved_docs: list
    analysis: dict
    draft: str
    review: dict
    final_report: str
    retry_count: int

def build_research_graph():
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("retrieve", retriever_agent.run)
    workflow.add_node("analyze", analyst_agent.run)
    workflow.add_node("write", writer_agent.run)
    workflow.add_node("review", reviewer_agent.run)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "analyze")
    workflow.add_edge("analyze", "write")
    workflow.add_edge("write", "review")
    
    # 条件分支: 审核不通过 → 返回重写（最多3次）
    workflow.add_conditional_edges(
        "review",
        decide_next,
        {
            "pass": END,
            "revise": "write",
            "fail": "fallback"  # 3次仍然不通过 → 降级处理
        }
    )
    
    return workflow.compile()
```

---

## 8. 桌面 UI 设计

### 8.1 主窗口布局

```
┌─────────────────────────────────────────────────────────┐
│  🧠 AI Second Brain              ─ □ ×                   │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐   │
│  │  [📝 智能笔记] [💬 知识问答] [🔬 深度研究] [📊 看板] │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │                                                    │   │
│  │              当前页面的内容区域                      │   │
│  │                                                    │   │
│  │                                                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  🟢 后端服务运行中  |  DeepSeek API 已连接  |  笔记: 42  │
└─────────────────────────────────────────────────────────┘
```

### 8.2 四个页面详细设计

#### 页面 1：智能笔记

```
┌──────┬────────────────────────────────────────────────┐
│📁目录│                                                │
│      │  ┌──────────────────────────────────────┐     │
│ ├工作 │  │ # Transformer架构详解                 │     │
│ ├学习 │  │                                      │     │
│ │├AI  │  │ [Markdown 富文本编辑器]               │     │
│ │├编程│  │ - 工具栏: 粗体/斜体/标题/列表/代码块  │     │
│ ├项目 │  │ - 实时预览 / 编辑模式切换              │     │
│ ──── │  │ - Ctrl+S 自动保存                      │     │
│ 🏷标签│  │                                      │     │
│ ├NLP  │  └──────────────────────────────────────┘     │
│ ├Python│                                               │
│ └Agent│  ─── AI 建议栏 ──────────────────────────     │
│      │  ┌──────────────────────────────────────┐     │
│      │  │ 🤖 智能建议:                           │     │
│      │  │ ├ 这篇和「注意力机制详解」高度相关       │     │
│      │  │ ├ 建议标签: #Transformer #深度学习      │     │
│      │  │ └ 📋 [自动生成摘要]                    │     │
│      │  └──────────────────────────────────────┘     │
└──────┴────────────────────────────────────────────────┘
```

#### 页面 2：知识问答

```
┌────────────────────────────────────────────────────────┐
│  📎 已索引文档:                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 📄 特斯拉2024Q4财报.pdf  [就绪]  [删除]         │   │
│  │ 📄 比亚迪2024年报.pdf    [就绪]  [删除]         │   │
│  │ 📄 新能源行业趋势.docx   [就绪]  [删除]         │   │
│  └─────────────────────────────────────────────────┘   │
│  [+ 上传新文档]                                        │
│ ────────────────────────────────────────────────────── │
│                                                         │
│  👤 你: 特斯拉和比亚迪的电池技术路线有什么不同？        │
│                                                         │
│  🤖 AI:                                                │
│  根据你上传的财报和年报，两家公司的电池技术路线         │
│  差异如下：                                            │
│                                                         │
│  ### 1. 电池类型                                        │
│  特斯拉主推 **4680 大圆柱电池**，优点是...              │
│  [来源: 特斯拉Q4财报 P12]                               │
│                                                         │
│  ### 2. 供应链策略                                      │
│  比亚迪采用 **垂直整合** 模式...                        │
│  [来源: 比亚迪2024年报 P28]                             │
│                                                         │
│  📎 引用 3 个文档片段  ✅ 可信度: 高                    │
│ ────────────────────────────────────────────────────── │
│  ┌─────────────────────────────────────┐ [发送] ────   │
│  └─────────────────────────────────────┘               │
└────────────────────────────────────────────────────────┘
```

#### 页面 3：深度研究

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  研究主题：                                            │
│  ┌──────────────────────────────────────────────┐      │
│  │ 对比分析2024年新能源汽车市场的主流技术路线    │      │
│  └──────────────────────────────────────────────┘      │
│  ☑ 联网搜索最新信息  ☑ 使用本地知识库  [开始研究]      │
│                                                        │
│ ─────────── 研究进度 ────────────────────────────     │
│                                                        │
│  ┌──────────────────────────────────────────────┐      │
│  │                                                │      │
│  │  🔍 检索Agent  ████████████  ✅ 完成           │      │
│  │      找到 15 篇相关资料，其中 8 篇高相关        │      │
│  │                                                │      │
│  │  📊 分析Agent  ████████████  ✅ 完成           │      │
│  │      提取 6 个关键维度，形成对比分析表           │      │
│  │                                                │      │
│  │  ✍️ 写作Agent  ██████░░░░░░  🔄 生成中...      │      │
│  │      正在撰写第 3 部分：竞争格局分析             │      │
│  │                                                │      │
│  │  🔍 审核Agent  ░░░░░░░░░░░░  ⏳ 等待中         │      │
│  │                                                │      │
│  └──────────────────────────────────────────────┘      │
│                                                        │
│ ─────────── 生成报告（实时流式） ────────────────     │
│                                                        │
│  ┌──────────────────────────────────────────────┐      │
│  │ # 2024年新能源汽车主流技术路线对比分析         │      │
│  │                                                │      │
│  │ ## 一、研究背景与方法                           │      │
│  │ 本研究基于 15 篇行业报告及企业财报...           │      │
│  │                                                │      │
│  │ ## 二、主流技术路线概览                         │      │
│  │ 2024年新能源汽车市场的技术路线可归纳为...      │      │
│  │                                                │      │
│  │ ... (流式生成中)                                │      │
│  └──────────────────────────────────────────────┘      │
│                                               [导出]   │
└────────────────────────────────────────────────────────┘
```

#### 页面 4：个人看板

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│  ┌──────────┬──────────┬──────────┬──────────────┐    │
│  │ 📝 总笔记 │ 📄 文档  │ 💬 对话  │ 🔬 研究报告  │    │
│  │   42     │   12     │   156    │     8        │    │
│  └──────────┴──────────┴──────────┴──────────────┘    │
│                                                        │
│  ┌────────── 知识图谱 ──────────┐  ┌── 本周统计 ──┐   │
│  │                              │  │               │   │
│  │    [NLP]────[Transformer]   │  │ 新增笔记: +5  │   │
│  │      │           │           │  │ AI对话: 23次  │   │
│  │   [BERT]      [GPT]         │  │ 上传文档: 3份 │   │
│  │      │           │           │  │ 研究任务: 1次 │   │
│  │  [预训练]    [RLHF]         │  │               │   │
│  │      │           │           │  └───────────────┘   │
│  │  [微调]     [对齐]          │                       │
│  │                              │  ┌── 热门标签 ──┐   │
│  │  ○ 节点 = 标签               │  │               │   │
│  │  ─ 连线 = 笔记关联           │  │ #Python (12)  │   │
│  │  大小 = 笔记数量             │  │ #NLP (8)      │   │
│  └──────────────────────────────┘  │ #Agent (6)    │   │
│                                    └───────────────┘   │
└────────────────────────────────────────────────────────┘
```

---

## 9. 分阶段开发计划

### 阶段总览

| 阶段 | 名称 | 核心内容 | 预计时间 | 产出 |
|------|------|---------|---------|------|
| **P1** | 基础通信 | FastAPI + LLM 对话 + SSE 流式 + 桌面壳 | ✅ 已完成 | 能聊天的桌面应用 |
| **P2** | 笔记系统 | CRUD + SQLite + 标签 + 编辑器 | ✅ 已完成 | 完整的笔记管理 |
| **P3** | RAG 笔记检索 | Embedding + ChromaDB + 语义搜索笔记 | 3-4天 | 语义搜索知识库 |
| **P4** | AI 自动标签 | Function Calling + ReAct Agent 推荐标签 | 3-4天 | Agent 自主推荐标签 |
| **P5** | 智能双向链接 | Embedding 相似度 + 关联笔记发现 | 3-4天 | 知识互联 |
| **P6** | AI 出题自测 | Few-shot 题目生成 + AI 批改 | 3-4天 | 学习检验 |
| **P7** | 真实知识图谱 | 用真实笔记数据驱动图谱 | 2-3天 | 知识结构可视化 |
| **P8** | 知识回顾总结 | 本周小结 + 学习时间线 | 2-3天 | 学习复盘 |
| **P9** | 打磨打包 | PyInstaller + 测试 + README | 2-3天 | .exe + GitHub Release |

### P1 详细计划：基础通信（3-4天）

**目标**: 后端能对话，桌面端能显示

```
任务1.1: 项目初始化
├─ 创建目录结构
├─ 编写 requirements.txt
├─ 创建 .env.example 和 config.py
└─ 初始化 Git 仓库 + .gitignore

任务1.2: 后端 — 基础对话 API
├─ FastAPI 应用入口 (main.py)
├─ core/llm.py: OpenAI SDK 封装 DeepSeek 调用
├─ api/chat.py: POST /api/chat SSE 流式对话
├─ core/memory.py: 简单滑动窗口记忆（保留最近10轮）
├─ models/conversation.py + models/message.py
└─ 测试: curl 请求验证流式输出

任务1.3: 桌面端 — 最简窗口
├─ desktop/main.py: 启动后端 + 创建 QMainWindow
├─ desktop/main_window.py: 主窗口布局
├─ desktop/pages/chat_page.py: 最简单的聊天界面
│   ├─ QTextEdit (输入框)
│   ├─ QPushButton (发送)
│   └─ QTextBrowser (显示 AI 回复)
├─ desktop/services/api_client.py: httpx 封装
└─ desktop/services/sse_client.py: SSE 流处理
```

### P2 详细计划：笔记系统（3-4天）

**目标**: 完整的笔记 CRUD + 数据库

```
任务2.1: 数据库模型 + 初始化
├─ models/note.py + models/tag.py
├─ SQLAlchemy 引擎配置
├─ Alembic 初始化 + 首次迁移
└─ 种子数据脚本

任务2.2: 笔记 API
├─ api/notes.py: CRUD 接口
├─ services/note_service.py: 业务逻辑
├─ Pydantic Schema 定义
└─ 分页 + 搜索 + 按标签筛选

任务2.3: 桌面端 — 笔记页面
├─ pages/notes_page.py: 布局（目录树+编辑器）
├─ widgets/note_tree.py: 笔记树形列表
├─ widgets/markdown_editor.py: Markdown 编辑组件
│   ├─ 语法高亮
│   ├─ Ctrl+S 保存
│   └─ 实时预览切换
├─ widgets/tag_cloud.py: 标签管理
└─ API 对接 + 错误处理
```

### P3 详细计划：RAG 引擎（4-5天）

**目标**: 上传文档 → 智能问答

```
任务3.1: 文档处理管道
├─ core/document_parser.py: PDF/DOCX/MD/TXT 解析
├─ core/rag_engine.py: 文本切片 + 混合检索
├─ core/embedding.py: DeepSeek Embedding API 调用
├─ ChromaDB 集成（collection 管理）
└─ models/document.py

任务3.2: RAG API
├─ api/documents.py: 文档上传/列表/删除
├─ api/rag.py: POST /api/rag/query SSE 流式
├─ services/rag_service.py: RAG 业务编排
└─ 引用来源追踪

任务3.3: 桌面端 — 知识问答页面
├─ pages/chat_page.py: 升级为 RAG 对话模式
├─ 文档管理区域（上传/列表/删除）
├─ 对话中显示引用来源
└─ 可信度指示器
```

### P4 详细计划：工具调用（3-4天）

**目标**: Agent 能自主选择调用工具

```
任务4.1: 工具定义
├─ tools/web_search.py: DuckDuckGo 搜索封装
├─ tools/calculator.py: 数学表达式计算
├─ tools/file_ops.py: 文件读写
└─ tools/note_search.py: 本地笔记搜索

任务4.2: ReAct Agent
├─ agents/base.py: Agent 基类（ReAct 循环）
├─ api/chat.py: /api/chat/tool 工具调用对话
├─ 工具选择推理 → 执行 → 观察 → 循环
└─ 工具调用日志 + 错误处理

任务4.3: 桌面端适配
├─ 聊天页面增加工具调用状态显示
├─ Agent 思考过程可视化
└─ 工具调用结果展示
```

### P5 详细计划：多Agent协作（4-5天）

**目标**: 4个Agent协作完成深度研究

```
任务5.1: Agent 定义
├─ agents/retriever.py: 检索Agent + System Prompt
├─ agents/analyst.py: 分析Agent
├─ agents/writer.py: 写作Agent
├─ agents/reviewer.py: 审核Agent
└─ 每个Agent的独立 System Prompt 模板

任务5.2: LangGraph 编排
├─ agents/orchestrator.py: StateGraph 工作流
├─ 条件分支（审核→重写/通过）
├─ SSE 实时推送每个Agent的状态
└─ 降级处理（3次审核不通过 → 简单LLM生成）

任务5.3: API + 桌面端
├─ api/research.py: /api/research/start SSE
├─ pages/research_page.py: 深度研究界面
├─ widgets/agent_status.py: Agent 状态可视化组件
└─ 实时报告流式显示
```

### P6 详细计划：UI 打磨（3-4天）

**目标**: 专业的桌面应用体验

```
任务6.1: 样式系统
├─ resources/styles/theme.qss: 全局 QSS 主题
├─ 深色/浅色主题切换
├─ 统一字体、颜色、间距
└─ 图标资源（使用 Qt 内置图标 + 自定义 SVG）

任务6.2: 交互优化
├─ 快捷键系统（Ctrl+N 新笔记, Ctrl+K 搜索等）
├─ QStatusBar 状态提示
├─ 加载动画 / 骨架屏
├─ 错误提示对话框
└─ 右键菜单

任务6.3: 富文本编辑器增强
├─ Markdown 工具栏完善
├─ 代码块语法高亮
├─ 图片粘贴支持
└─ 自动保存 + 草稿恢复
```

### P7 详细计划：知识图谱（2-3天）

**目标**: 可视化知识结构

```
任务7.1: 后端 — 图谱数据 API
├─ api/dashboard.py: GET /api/dashboard/graph
├─ 计算标签共现关系
├─ 计算节点权重（笔记数/引用数）
└─ 返回 JSON 格式的图数据（nodes + edges）

任务7.2: 桌面端 — 图谱可视化
├─ widgets/knowledge_graph.py
│   ├─ PySide6-WebEngine 加载 ECharts
│   ├─ 力导向图 / 关系图
│   └─ 点击节点跳转相关笔记
├─ pages/dashboard_page.py: 统计卡片 + 图谱
└─ 本周统计 / 热门标签 等卡片组件
```

### P8 详细计划：打包发布（2-3天）

**目标**: 生成 .exe，发布到 GitHub

```
任务8.1: PyInstaller 打包
├─ scripts/build_exe.py: PyInstaller 配置
├─ .spec 文件优化（排除不需要的 Qt 模块）
├─ 测试 .exe 在裸机 Windows 上的运行
└─ 解决打包常见问题（路径、动态库）

任务8.2: 测试完善
├─ 后端 API 单元测试（pytest）
├─ 核心逻辑测试（RAG、Agent）
├─ 桌面端手动测试清单
└─ Bug 修复

任务8.3: 文档 + 发布
├─ README.md: 功能介绍 + 安装指南 + 截图
├─ 演示视频录制（OBS / ScreenToGif）
├─ GitHub 仓库创建 + Push
├─ 简历描述撰写
└─ 面试问答准备文档
```

---

## 10. 打包与部署

### 10.1 PyInstaller 打包策略

```
打包方案: 单目录模式（onedir）
├─ 包含: Python 解释器 + 所有依赖 + 资源文件
├─ 输出: dist/ai-second-brain/ 目录
│   ├─ ai-second-brain.exe    ← 双击启动
│   ├─ _internal/              ← Python + 依赖
│   └─ resources/              ← 图标/样式
└─ 后续可用 Inno Setup 打包成安装程序

关键配置:
- --hidden-import: chromadb, pydantic, sqlalchemy
- --add-data: 包含 QSS 样式文件和图标
- --exclude-module: PySide6 不需要的模块（减小体积）
- 目标大小: < 150MB
```

### 10.2 Docker 开发环境

```yaml
# docker-compose.yml（仅开发时使用，方便环境隔离）
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./data:/app/data"]
    env_file: .env
    
  # 注意: 桌面端不在 Docker 里运行，在宿主机直接运行
```

---

## 11. 面试要点汇总

### 11.1 项目介绍话术（30秒版）

> "我独立开发了一个 **AI 协同个人知识库管理系统**，是一个用 PySide6 构建的桌面应用。核心功能包括：基于 RAG 的私有文档智能问答、多 Agent 协作的深度研究系统（自动检索→分析→写作→审核）、以及知识图谱可视化。后端用 FastAPI，AI 引擎用 LangChain + LangGraph，数据库用 SQLite + ChromaDB。整个项目我深入理解每一个环节的原理。"

### 11.2 面试高频问题准备清单

| 类别 | 问题 | 对应代码 |
|------|------|---------|
| **RAG** | RAG 的原理是什么？你是怎么实现的？ | `core/rag_engine.py` |
| **RAG** | 怎么处理文档切片？切片大小怎么定的？ | `rag_engine.py` chunk参数 |
| **RAG** | 检索怎么做的？混合检索是什么？ | `rag_engine.py` 检索函数 |
| **RAG** | RAG 有哪些优化手段？ | 混合检索 + 重排序 |
| **RAG** | 向量数据库的原理？为什么选 ChromaDB？ | HNSW 算法 |
| **Agent** | Agent 和普通 LLM 调用有什么区别？ | `agents/base.py` |
| **Agent** | Function Calling 的流程是怎样的？ | `api/chat.py` tool模式 |
| **Agent** | ReAct 模式是什么？ | `agents/base.py` ReAct循环 |
| **Agent** | 多 Agent 怎么协作？怎么保证质量？ | `agents/orchestrator.py` |
| **Agent** | LangGraph 在项目里怎么用的？ | StateGraph 工作流 |
| **架构** | 前后端怎么通信的？ | httpx + SSE |
| **架构** | 为什么用 PySide6？和 Electron 比？ | 技术选型 |
| **架构** | 流式输出怎么实现的？ | SSE (Server-Sent Events) |
| **数据库** | 数据库怎么设计的？为什么用 SQLite？ | ER 图 + 表结构 |
| **部署** | 怎么打包成 .exe 的？遇到过什么问题？ | PyInstaller |
| **通用** | 项目里最大的挑战是什么？ | 准备一个具体故事 |
| **通用** | 如果重新做，你会怎么改进？ | 架构优化方向 |

### 11.3 项目亮点提炼（用于简历）

```
简历技能描述:
- 独立设计并实现基于 RAG（检索增强生成）的智能知识库问答系统，
  支持 PDF/DOCX 等多格式文档解析、语义向量检索、混合检索与重排序
- 实现基于 LangGraph 的多 Agent 协作深度研究系统，
  包含检索→分析→写作→审核四阶段流水线，支持自动纠错与重写
- 使用 PySide6 + FastAPI 构建前后端分离架构，
  通过 SSE 实现流式 AI 输出，支持 ReAct 模式的工具调用
- 集成 ChromaDB 向量数据库 + SQLite 关系数据库，
  实现知识图谱可视化（ECharts）
```

---

## 附录 A：依赖清单

### backend/requirements.txt
```
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.12

# Database
sqlalchemy==2.0.35
alembic==1.13.2

# AI / LLM
openai==1.55.0
langchain==0.3.0
langgraph==0.2.0
chromadb==0.5.20
tiktoken==0.7.0

# Document Parsing
PyMuPDF==1.24.0
python-docx==1.1.0

# Utilities
python-dotenv==1.0.1
pydantic==2.9.0
httpx==0.27.0
rank-bm25==0.2.2

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0
```

### desktop/requirements.txt
```
# Backend (复用)
-e ../backend

# UI
PySide6==6.7.0
PySide6-WebEngine==6.7.0

# Async Bridge
qasync==0.27.0

# HTTP Client
httpx==0.27.0
httpx-sse==0.4.0
```

---

## 附录 B：Git 标签规划

```
phase-1  — 基础通信完成
phase-2  — 笔记系统完成
phase-3  — RAG 引擎完成
phase-4  — 工具调用完成
phase-5  — 多 Agent 完成
phase-6  — UI 打磨完成
phase-7  — 知识图谱完成
phase-8  — 打包发布完成
v1.0.0   — 最终发布版本
```
