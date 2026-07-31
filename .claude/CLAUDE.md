# AI 协同个人知识库管理系统 — 项目工程规则

> **规则文件** — 每次新对话开始时自动加载本文件。
> 本文件定义项目的全局工程规范、约定和约束。

---

## 0. 环境要求与激活

| 项目 | 版本 | 说明 |
|------|------|------|
| **Python** | **3.12.x (64-bit)** | 必须！已安装于 `C:\Users\HP\AppData\Local\Programs\Python\Python312\python.exe` |
| **虚拟环境** | `.venv/` | **每次开发前必须先激活**: `.venv\Scripts\activate` |
| **Node.js** | 24.16.0 | 已安装 |
| **pnpm** | 11.13.1 | 已安装 |
| **Docker** | 29.6.2 | 已安装 |
| **Git** | 2.44.0 | 已安装 |

> ⚠️ **重要**: 当前目录的 `.venv/` 是用 Python 3.12 创建的虚拟环境。
> 所有 Python 命令必须在激活 venv 后运行，否则会用到系统默认的 Python 3.9（32位），
> 导致 `tiktoken` 和 `chromadb` 安装失败。

---

## 0.5 会话恢复（每次打开 Claude Code 先读这里）

### 当前状态

| 项目 | 值 |
|------|-----|
| 已完成阶段 | P1 基础通信 ✅, P2 笔记系统 ✅ |
| 已完成 P3 子任务 | 3.1.1 Embedding ✅, 3.1.2 RAG 引擎 ✅ |
| 当前阶段 | **P3 — 文档导入 + 增量同步** |
| 当前任务 | S1: Note 模型扩展 |
| GitHub | https://github.com/Mcloseyb/ai-second-brain |
| 上次会话 | 2026-07-31，完成 Embedding + RAG 引擎 + 方案重设计 |

### P3 重规划要点

| 决策 | 选择 |
|------|------|
| 文件来源 | 导入模式（存 DB）+ 文件引用模式（存路径），两种并存 |
| 文档格式 | md / docx / pdf → 清洗为 Markdown 存储 |
| 文件夹 | Note.folder 字符串路径，如 `"AI/Agent"` |
| 标签推荐 | jieba TF-IDF + Embedding 匹配（零 LLM token） |
| MD 编辑器 | Vditor (QWebEngine 嵌入) 替换 QTextEdit |
| 变更检测 | MD5 哈希对比，只同步修改过的笔记 |
| 同步触发 | 导入时立即 / 每 30min 定时 / 手动按钮 |

### 恢复工作命令

```bash
cd H:\agent
.venv\Scripts\activate

# 如果后端没跑，启动它:
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 桌面端:
python desktop\main.py
```

### 恢复步骤

1. **读取** `docs/TODO.md` — P3 第一个未勾选的任务就是当前任务
2. **读取** `docs/PROJECT_PLAN.md` — 第 9 节确认技术方案
3. **开始写代码**

### 路线速览

```
P1 ✅  基础通信         P2 ✅  笔记系统
P3 ⏳  文档导入+同步     P3.5 ⏳ 标签推荐+MD编辑器升级
P4 ⏳  Tag Agent        P5 ⏳  Link Agent
P6 ⏳  Quiz Agent       P7 ⏳  知识图谱
P8 ⏳  Review Agent     P9 ⏳  打包 .exe
P? ⏳  Research Agent   P? ⏳  Knowledge Agent
```

---

## 0. 必读文档（每次会话必须加载）

在每次对话开始时，**必须先读取以下文档以获取最新状态**：

| 优先级 | 文件路径 | 说明 |
|--------|---------|------|
| 🔴 必读 | `docs/PROJECT_PLAN.md` | 总体规划报告 — 架构、技术栈、设计决策 |
| 🔴 必读 | `docs/TODO.md` | 任务跟踪清单 — 当前进度、待办事项 |
| 🟡 按需 | `docs/CHANGELOG.md` | 变更日志 — 记录每次重大修改 |

**规则**：每轮对话结束时，必须更新 `docs/TODO.md` 反映最新进度。

---

## 1. 项目身份

| 属性 | 值 |
|------|-----|
| **项目名称** | AI 协同个人知识库管理系统 |
| **英文名** | AI Second Brain — Collaborative Knowledge Management |
| **项目代号** | `ai-second-brain` |
| **项目根目录** | `H:\agent` |
| **Git 仓库** | 待创建 |
| **开发模式** | 渐进式 — 8 个阶段，每阶段独立可运行 |

---

## 2. 项目一句话描述

做一个**个人知识管理桌面应用（.exe）**，用 AI Agent 帮助用户：
- 📖 自动整理笔记（总结、打标签、关联已有内容）
- 📚 基于私有文档的智能问答（RAG 检索增强生成）
- 🔬 多 Agent 协作深度研究（检索→分析→写作→审核）
- 📊 知识图谱可视化（看自己的知识结构）

---

## 3. 架构总览

```
┌─────────────────────────────────────────────────┐
│            PySide6 桌面客户端（前端）              │
│  4 个页面：智能笔记 | 知识问答 | 深度研究 | 看板  │
│  Qt Designer 拖界面 + httpx 异步调 API           │
└──────────────────┬──────────────────────────────┘
                   │ HTTP REST + SSE (httpx)
┌──────────────────┴──────────────────────────────┐
│               FastAPI 后端 (本地嵌入式)            │
│  ├─ api/     路由层（REST + SSE 流式）           │
│  ├─ core/    LLM / RAG / Memory 核心引擎        │
│  ├─ agents/  多 Agent 定义与编排                 │
│  ├─ tools/   工具集（搜索/计算/文件）             │
│  ├─ models/  SQLAlchemy ORM 模型                │
│  └─ services/ 业务服务层                         │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────┐
│                 数据层 (嵌入式)                    │
│  ├─ SQLite     结构化数据（笔记/用户/对话）        │
│  ├─ ChromaDB   向量数据（文档索引）               │
│  └─ 文件系统    原始文件存储                      │
└─────────────────────────────────────────────────┘
```

**核心特性**：前端（PySide6）和后端（FastAPI）通过 HTTP 通信，完全解耦。
如果以后要换成 React 前端或 Web 版，后端一行代码不用改。

---

## 4. 技术栈（锁定版本）

### 桌面 UI（PySide6）
| 技术 | 版本 | 用途 |
|------|------|------|
| PySide6 | 6.6+ | Qt for Python，桌面 UI 框架 |
| PySide6-WebEngine | 6.6+ | 内嵌浏览器（知识图谱用 ECharts） |
| Qt Designer | 自带 | 可视化拖拽 UI 设计 |
| httpx | 0.27+ | 异步 HTTP 客户端（调用后端 API） |
| qasync | 0.27+ | Qt 事件循环与 asyncio 桥接 |

### 后端（FastAPI）
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.9.0（已安装） | 后端语言 |
| FastAPI | 0.111+ | 异步 Web API 框架 |
| SQLAlchemy | 2.0 | ORM |
| Alembic | 1.13 | 数据库迁移 |
| Pydantic | 2.x | 数据校验 |
| Uvicorn | 0.29+ | ASGI 服务器 |

### AI / Agent 引擎
| 技术 | 版本 | 用途 |
|------|------|------|
| LangChain | 0.2+ | Agent 框架（LCEL 链式编排） |
| LangGraph | 0.1+ | 多 Agent 状态图编排 |
| OpenAI SDK | 1.x | LLM API（兼容 DeepSeek） |
| ChromaDB | 0.5+ | 向量数据库（嵌入式模式） |
| tiktoken | 0.7+ | Token 计算 |

### 数据与存储
| 技术 | 用途 |
|------|------|
| SQLite（开发/生产统一） | 关系数据库 — 笔记、用户、对话记录 |
| ChromaDB（持久化模式） | 向量存储 — 文档 Embedding 索引 |
| 本地文件系统 | 用户上传的原始文档（PDF/Word/MD 等） |

### 打包与部署
| 技术 | 用途 |
|------|------|
| PyInstaller | 打包成单个 .exe |
| Inno Setup（可选） | 制作 Windows 安装包 |
| Docker + docker-compose | 开发环境容器化（可选） |
| Git + GitHub | 版本管理 |

---

## 5. 目录结构规范

```
H:\agent\                              # 项目根目录
├── .claude\                           # Claude Code 配置
│   ├── CLAUDE.md                      # 本文件 — 工程规则
│   └── settings.local.json           # 本地权限配置
│
├── docs\                              # 项目文档
│   ├── PROJECT_PLAN.md                # 总体规划报告
│   ├── TODO.md                        # 任务跟踪
│   └── CHANGELOG.md                   # 变更日志
│
├── backend\                           # Python 后端服务
│   ├── app\
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 入口 + 生命周期
│   │   ├── config.py                  # 配置管理（读 .env）
│   │   │
│   │   ├── api\                       # API 路由层
│   │   │   ├── __init__.py
│   │   │   ├── notes.py               # 笔记 CRUD API
│   │   │   ├── chat.py                # 对话 API（SSE 流式）
│   │   │   ├── rag.py                 # RAG 问答 API
│   │   │   ├── research.py            # 深度研究 API（SSE）
│   │   │   ├── documents.py           # 文档管理 API
│   │   │   └── dashboard.py           # 统计数据 API
│   │   │
│   │   ├── core\                      # 核心引擎
│   │   │   ├── __init__.py
│   │   │   ├── llm.py                 # LLM 调用统一封装
│   │   │   ├── memory.py              # 对话记忆管理
│   │   │   ├── rag_engine.py          # RAG 引擎（切片+嵌入+检索）
│   │   │   ├── embedding.py           # Embedding 服务
│   │   │   └── document_parser.py     # 文档解析（PDF/Word/MD）
│   │   │
│   │   ├── agents\                    # Agent 定义
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # Agent 基类
│   │   │   ├── retriever.py           # 检索 Agent
│   │   │   ├── analyst.py             # 分析 Agent
│   │   │   ├── writer.py              # 写作 Agent
│   │   │   ├── reviewer.py            # 审核 Agent
│   │   │   └── orchestrator.py        # Agent 编排器（LangGraph）
│   │   │
│   │   ├── tools\                     # Agent 工具集
│   │   │   ├── __init__.py
│   │   │   ├── web_search.py          # 联网搜索工具
│   │   │   ├── calculator.py          # 计算工具
│   │   │   ├── file_ops.py            # 文件操作工具
│   │   │   └── note_search.py         # 笔记搜索工具
│   │   │
│   │   ├── models\                    # SQLAlchemy 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── note.py                # 笔记表
│   │   │   ├── document.py            # 文档表
│   │   │   ├── conversation.py        # 对话记录表
│   │   │   └── tag.py                 # 标签表
│   │   │
│   │   └── services\                  # 业务逻辑层
│   │       ├── __init__.py
│   │       ├── note_service.py        # 笔记业务
│   │       ├── rag_service.py         # RAG 业务
│   │       └── research_service.py    # 深度研究业务
│   │
│   ├── tests\                         # 单元测试
│   │   ├── __init__.py
│   │   ├── test_notes.py
│   │   ├── test_rag.py
│   │   └── test_agents.py
│   │
│   ├── alembic\                       # 数据库迁移
│   │   ├── env.py
│   │   └── versions\
│   │
│   ├── requirements.txt               # Python 依赖
│   ├── Dockerfile                     # 后端容器
│   └── .env.example                   # 环境变量模板
│
├── desktop\                           # PySide6 桌面客户端
│   ├── __init__.py
│   ├── main.py                        # 桌面应用入口
│   ├── main_window.py                 # 主窗口（Tab 切换）
│   │
│   ├── pages\                         # 4 个页面
│   │   ├── __init__.py
│   │   ├── notes_page.py              # 智能笔记页
│   │   ├── chat_page.py               # 知识问答页
│   │   ├── research_page.py           # 深度研究页
│   │   └── dashboard_page.py          # 个人看板页
│   │
│   ├── widgets\                       # 自定义组件
│   │   ├── __init__.py
│   │   ├── markdown_editor.py         # Markdown 编辑器
│   │   ├── chat_bubble.py             # 聊天气泡
│   │   ├── agent_status.py            # Agent 状态显示
│   │   ├── note_tree.py               # 笔记树形列表
│   │   ├── tag_cloud.py               # 标签云
│   │   └── knowledge_graph.py         # 知识图谱（ECharts）
│   │
│   ├── services\                      # API 调用封装
│   │   ├── __init__.py
│   │   ├── api_client.py              # httpx 异步客户端封装
│   │   └── sse_client.py              # SSE 流式客户端
│   │
│   ├── resources\                     # UI 资源
│   │   ├── icons\                     # 图标
│   │   ├── styles\                    # QSS 样式表
│   │   │   └── theme.qss              # 主主题
│   │   └── ui_files\                  # Qt Designer .ui 文件
│   │
│   └── requirements.txt               # 桌面端依赖
│
├── scripts\                           # 工具脚本
│   ├── build_exe.py                   # PyInstaller 打包脚本
│   └── init_db.py                     # 初始化数据库
│
├── data\                              # 运行时数据（不提交 git）
│   ├── app.db                         # SQLite 数据库
│   ├── chroma_db\                     # ChromaDB 持久化
│   └── uploads\                       # 用户上传文件
│
├── docker-compose.yml                 # 开发环境容器
├── .gitignore
├── .env.example
├── Makefile                           # 常用命令快捷方式
└── README.md
```

---

## 6. 编码规范

### Python 通用规范
- **风格**: 严格遵循 PEP 8，用 `black` 自动格式化
- **类型注解**: 所有函数参数和返回值必须有类型注解
- **命名**: 
  - 变量/函数/方法：蛇形命名 `snake_case`
  - 类名：帕斯卡命名 `PascalCase`
  - 常量：全大写 `UPPER_SNAKE_CASE`
  - 私有：前缀单下划线 `_private`
- **文件组织**: 每个模块一个文件，`__init__.py` 只做 re-export
- **错误处理**: 使用 FastAPI 的 HTTPException + 全局异常处理中间件
- **日志**: 使用 `logging` 模块，禁止 `print()`
- **环境变量**: 通过 `config.py` 统一读取，禁止代码中硬编码密钥/URL

### 后端（FastAPI）规范
- **异步优先**: 所有 API 路由使用 `async def`
- **路由分离**: 每个资源一个路由文件，注册到 `main.py`
- **Pydantic 模型**: 请求/响应必须有 Schema 定义
- **数据库操作**: 通过 Service 层，API 路由不直接操作 ORM
- **分页**: 列表接口必须支持分页（offset/limit）

### 桌面端（PySide6）规范
- **UI 与逻辑分离**: `.ui` 文件通过 Qt Designer 设计，Python 中 load 后绑定逻辑
- **信号槽命名**: `on_<widget>_<signal>` 格式，如 `on_send_btn_clicked`
- **异步 UI**: 所有网络请求用 `httpx.AsyncClient` + `qasync`，禁止阻塞主线程
- **长耗时操作**: 使用 `QThread` 或 `asyncio.create_task`，禁止在主线程等待
- **QSS 主题**: 样式统一写在 `theme.qss`，不散落在代码中
- **API 调用**: 统一通过 `desktop/services/api_client.py` 发请求，不直接调 httpx

### 通用
- **注释语言**: 注释用中文，函数名/变量名用英文
- **Git 提交**: Conventional Commits 格式
  - `feat(scope): 描述` — 新功能
  - `fix(scope): 描述` — 修 bug
  - `docs(scope): 描述` — 文档
  - `refactor(scope): 描述` — 重构
  - `test(scope): 描述` — 测试
- **分支**: `main` 主分支，每阶段打 tag：`phase-1`, `phase-2`, ...

---

## 7. LLM / Agent 开发约定

### API 调用规范
- **统一入口**: 所有 LLM 调用必须通过 `core/llm.py` 的封装函数
- **模型选择**: 
  - 默认对话：`deepseek-chat`
  - 复杂推理（分析/审核）：`deepseek-chat`（temperature=0.3）
  - 工具调用：`deepseek-chat`（temperature=0）
- **重试机制**: 调用失败自动重试 3 次，间隔 2s，指数退避
- **Token 限制**: 每次调用前用 tiktoken 估算 token 数，超限自动截断

### Agent 设计原则
- **单一职责**: 每个 Agent 只做一件事，职责明确
- **角色 Prompt**: 每个 Agent 有独立的 System Prompt，定义角色、能力、边界、输出格式
- **工具权限**: 每个 Agent 只能调用其授权的工具
- **可观测性**: 每个 Agent 的 Thought-Action-Observation 过程必须记日志
- **流式输出**: 所有 Agent 输出支持 SSE 流式推送给客户端
- **错误兜底**: Agent 连续 3 次调用失败 → 降级为简单 LLM 回答

### RAG 参数标准
| 参数 | 默认值 | 说明 |
|------|--------|------|
| Chunk Size | 500 tokens | 文档切片大小 |
| Chunk Overlap | 50 tokens | 切片重叠量 |
| Embedding 模型 | `text-embedding-3-small` | 向量化模型 |
| Top-K 检索 | 5 | 返回最相关片段数 |
| 相似度阈值 | 0.70 | 低于此值不召回 |
| 混合检索权重 | 语义 0.7 + BM25 0.3 | 加权融合 |
| 重排序 | LLM 相关性过滤 | 检索后处理 |

---

## 8. 开发流程 SOP

### 每轮对话标准流程
1. **读状态**: 读取 `docs/TODO.md` 和 `docs/PROJECT_PLAN.md`
2. **选任务**: 从 TODO 中选下一个待做任务
3. **做任务**: 写代码 → 运行验证 → 确认可工作
4. **更新 TODO**: 标记完成 `[x]`，记录实际产出
5. **更新 PLAN**: 如有架构变更，同步更新规划文档
6. **报告**: 向用户汇报完成情况 + 下一步做什么

### Git 提交节奏
- 每完成一个可运行的小功能 → commit
- 每阶段所有任务完成 → tag + push
- **每完成一个子任务必须 commit**，保持提交历史细粒度可追溯
- **每次 commit 后尝试 `git push`**，网络不通则记录到下一次一起推
- 提交信息示例:
  ```
  feat(backend): 实现笔记创建 API — POST /api/notes
  feat(desktop): 添加笔记编辑器页面的基础布局
  fix(rag): 修复 PDF 解析中文编码问题
  ```

---

## 9. 环境变量

```bash
# ============================================
# .env.example — 复制为 .env 后填入实际值
# ============================================

# --- LLM API ---
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# --- 数据库 ---
DATABASE_URL=sqlite:///./data/app.db

# --- ChromaDB ---
CHROMA_PERSIST_DIRECTORY=./data/chroma_db

# --- 文件上传 ---
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE_MB=50

# --- 应用配置 ---
APP_NAME=AI Second Brain
APP_VERSION=0.1.0
DEBUG=true
HOST=127.0.0.1
PORT=8000
```

---

## 10. 关键约束

1. **渐进式开发**: 每阶段产出必须可运行、可演示，禁止一口气写完全部再调试
2. **先跑通再优化**: 先实现核心流程，后续阶段再优化性能
3. **全部异步**: AI 调用/文件操作/网络请求一律 async
4. **前后端解耦**: 桌面端通过 HTTP 调 API，后端不依赖前端
5. **可面试讲解**: 每写完一个模块，你要能讲清楚"为什么这样设计"
6. **禁止 print**: 后端用 `logging`，桌面端用 `logging` + QStatusBar
7. **类型注解全覆盖**: 不给面试官留下"你们 Python 没类型"的话柄

---

---

## 12. 会话工作规范（铁律）

> **以下规则适用于每次对话，不得违反。**

1. **先出方案再动手**：任何文件修改、执行 shell 命令前，优先输出完整执行方案；大规模改动主动使用 `/plan` 生成计划表给用户审核，没有确认不直接改动代码。

2. **最小改动原则**：修改代码遵循最小改动原则，不随意重构无关代码、不删除原有业务逻辑。每改一行都要能说清楚"为什么"。

3. **四件套不遗漏**：新增功能必须同步考虑：**参数校验**（Pydantic / 边界判断）、**异常捕获**（try/except + 有意义的错误信息）、**日志输出**（logger.info/warning/error，禁止 print）、**边界条件**（空值/超长/并发/特殊字符）。

4. **遵循现有代码风格**：如果项目有已有规范 → 严格遵循；如果缺少规范 → 使用行业通用最佳实践（PEP 8、12 Factor App、RESTful API 设计）。命名、注释语言、文件组织方式全部对齐现有代码。

5. **技术选型先对比**：出现技术选择时，主动列出方案优劣对比（至少 2 个选项），标注各自适用场景和 trade-off，不自行盲目选型。"够用不折腾"优先于"先进但复杂"。

6. **分阶段交付**：不一次性生成超大批量文件，每阶段完成主动同步进度。每完成一个独立可运行的小功能 → 汇报 → 确认 → 下一步。

7. **不懂就问**：如果看不懂项目结构、不清楚业务约定、不确定实现方式，优先向用户提问，不猜测实现。宁可多问一句，不要写错一行。

---

## 13. Agent 架构规范

### 13.1 核心定义

> **Agent ≠ LLM 对话。Agent = 角色(System Prompt) + 工具(Tools) + 推理(ReAct Loop) + 记忆(Context Window)**

每个 Agent 是一个**独立的业务处理单元**，不负责 UI、不直接操作数据库（通过 Service 层）、不越界处理其他 Agent 的职责。

### 13.2 设计原则

1. **专用职责拆分**：一个 Agent 只解决一类业务目标，禁止"超级 Agent"大包大揽。拆分粒度：一个 Agent = 一个业务闭环。
2. **基础底座共享**：Chat Agent 为基础通信底座，所有其他 Agent 共享同一套基础设施：向量库（ChromaDB）、文档数据库（SQLite）、LLM 统一接口（`core/llm.py`）、Embedding 服务（`core/embedding.py`）。
3. **执行顺序约束**：
   - **基础数据流水线**（必须按序）: `Import Agent → Tag Agent → Link Agent`
   - **上层应用**（按需触发）: `Research Agent` / `Quiz Agent` / `Review Agent` / `Knowledge Agent`
   - 上层应用依赖流水线的产出（已向量化的笔记 + 标签 + 链接关系）
4. **调度编排**：基于 LangGraph 实现 Agent 路由和多步流转。支持串行流水线（Import→Tag→Link）、并行任务（多个 Quiz 同时生成）、条件分支（按内容类型路由到不同 Agent）。
5. **输出可审计**：每个 Agent 的执行过程记录结构化日志（日志级别 INFO），包含：Agent 名称、输入摘要、关键决策点、工具调用记录、输出摘要、耗时。方便调试和面试讲解。

### 13.3 Agent 全景图

```
┌──────────────────────────────────────────────────────────────────┐
│                    基础层 Base Layer                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │ Chat Agent  │  │ LLM Service  │  │ 共享基础设施          │     │
│  │ (P1 ✅)     │  │ Embedding    │  │ SQLite / ChromaDB     │     │
│  │ 对话+上下文  │  │ RAG Engine   │  │ DocumentParser       │     │
│  └──────┬──────┘  └──────────────┘  └──────────────────────┘     │
├─────────┼────────────────────────────────────────────────────────┤
│         │          数据流水线 Data Pipeline (串行)                 │
│         ├──────► Import Agent (P3) ──► 导入+向量化                │
│         ├──────► Tag Agent   (P3.5) ──► 推荐标签+去重             │
│         └──────► Link Agent  (P5)   ──► 双向链接+相似度            │
├──────────────────────────────────────────────────────────────────┤
│                    上层应用 Application Layer (按需)               │
│  ┌──────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │Research Agent│  │ Quiz Agent │  │Review Agent│  │Knowledge  │ │
│  │ (P? 深度研究) │  │ (P6 出题)  │  │ (P8 回顾)  │  │Agent (P?) │ │
│  │ 多Agent协作   │  │ 自测+批改  │  │ 周报+时间线 │  │ 缺口+路径 │ │
│  └──────────────┘  └────────────┘  └────────────┘  └───────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 13.4 各 Agent 详细规格

#### Chat Agent（基础底座）— P1 ✅
| 属性 | 值 |
|------|-----|
| 触发 | 用户在聊天页面发送消息 |
| 输入 | 消息文本 + 对话历史（滑动窗口 20 轮） |
| 工具 | 无（纯 LLM 回复）；P3 后可接入 RAG |
| 输出 | SSE 流式回复 |
| LLM | `deepseek-chat`（默认） |
| Token | 中（~1K-4K/轮） |
| 文件 | `core/llm.py`, `api/chat.py` |

#### Import Agent（导入助手）— P3 进行中
| 属性 | 值 |
|------|-----|
| 触发 | 用户导入文件（上传或拖入） |
| 输入 | 文件路径 / 文件字节 + 文件名 |
| 工具 | `DocumentParser（md/docx/pdf→Markdown）`, `EmbeddingService`, `RAGEngine.index_note()` |
| 输出 | 已入库的 Note + 向量已同步确认 |
| Token | **零**（规则引擎 + Embedding API，无 LLM 调用） |
| 文件 | `core/document_parser.py`, `api/documents.py`, `services/sync_service.py` |
| 审计日志 | 文件名、格式、解析耗时、字数、向量化结果 |

#### Tag Agent（标签管家）— P3.5（简易）/ P4（完整）
| 属性 | P3.5 简易版 | P4 完整版 |
|------|------------|----------|
| 触发 | Import Agent 完成后自动 | 手动点击"AI 打标签" |
| 输入 | 笔记内容 + 已有标签列表 | 笔记内容 + 已有标签体系 |
| 工具 | jieba 分词 + TF-IDF + Embedding 相似度匹配 | `suggest_tags()`, `create_tag()`, `merge_tags()` |
| 输出 | 推荐 3-5 个标签（用户确认） | 推荐 + 新标签创建 + 去重合并建议 |
| Token | **零** | 低（~500/篇） |
| LLM | 无 | `deepseek-chat`, temperature=0 |
| 文件 | `agents/tag_agent.py` | `agents/tag_agent.py` + Function Calling |

#### Link Agent（关联发现）— P5
| 属性 | 值 |
|------|-----|
| 触发 | Tag Agent 完成后自动 |
| 输入 | 新笔记向量 + 已有笔记向量池 |
| 工具 | `RAGEngine.search()`, `EmbeddingService.similarity()` |
| 输出 | Top-5 关联笔记 + 双向链接建议 |
| Token | **零**（纯 Embedding 相似度计算） |
| 文件 | `agents/link_agent.py` |

#### Research Agent（深度研究）— P?
| 属性 | 值 |
|------|-----|
| 触发 | 用户在深度研究页面提交研究主题 |
| 输入 | 研究主题 + 参数（范围/深度） |
| 工具 | 4 个子 Agent（Retriever/Analyst/Writer/Reviewer）各自独立工具集 |
| 编排 | LangGraph 状态图：`Retriever → Analyst → Writer → Reviewer → 最终输出` |
| 输出 | SSE 流式报告（逐步展示每个 Agent 的进度） |
| Token | **高**（4 次 LLM 调用 + 工具调用） |
| LLM | `deepseek-chat`（Retriever/Writer）, temperature=0.3（Analyst/Reviewer） |
| 文件 | `agents/retriever.py`, `agents/analyst.py`, `agents/writer.py`, `agents/reviewer.py`, `agents/orchestrator.py` |

#### Quiz Agent（出题助手）— P6
| 属性 | 值 |
|------|-----|
| 触发 | 用户选中笔记 → "生成题目" |
| 输入 | 笔记内容 + 题目类型（选择/简答） + 难度 |
| 工具 | `generate_questions()`, `grade_answers()` |
| 输出 | 题目列表 → 用户作答 → 批改结果 + 复习建议 |
| Token | **中**（生成 ~500，批改 ~300） |
| 文件 | `agents/quiz_agent.py` |

#### Review Agent（回顾助手）— P8
| 属性 | 值 |
|------|-----|
| 触发 | 用户点击"本周总结" / 每周定时 |
| 输入 | 本周笔记列表 + 标签分布 + 学习时长 |
| 工具 | `RAGEngine.search()`, LLM 总结 |
| 输出 | 周报（学了什么 + 时间分布 + 推荐复习） |
| Token | **中**（总结 ~1000） |
| 文件 | `agents/review_agent.py` |

#### Knowledge Agent（知识导航）— P?（暂存）
| 属性 | 值 |
|------|-----|
| 触发 | 用户点击"知识分析" |
| 输入 | 全量笔记 + 标签体系 + 学习历史 |
| 工具 | 聚类分析、缺口检测、路径规划 |
| 输出 | 知识缺口报告 + 推荐学习路径 + 概念成熟度评估 |
| Token | **高**（全量分析） |
| 文件 | `agents/knowledge_agent.py` |

### 13.5 Agent 通用实现规范

```python
# 每个 Agent 的标准结构（基类: agents/base.py）
class BaseAgent:
    name: str                    # Agent 唯一标识
    description: str             # 一句话描述
    system_prompt: str           # System Prompt 模板
    tools: list[Callable]        # 可调用的工具列表（Function Calling schema）
    max_retries: int = 3         # 单步 Tool Call 最大重试次数

    async def run(self, input: AgentInput) -> AgentOutput:
        """执行 Agent 任务，遵循 ReAct 循环"""
        # 1. 组装 messages: [system_prompt, ...context, user_input]
        # 2. ReAct loop:
        #    while not done and steps < max_steps:
        #        response = await llm.chat(messages, tools=self.tools)
        #        if response has tool_calls → execute → append observation
        #        else → done = True
        # 3. 记录审计日志
        # 4. 返回 AgentOutput
        ...

class AgentOutput:
    agent_name: str
    content: str                  # 最终输出文本
    steps: list[AgentStep]        # 执行步骤记录（审计用）
    tool_calls: list[ToolCall]   # 工具调用记录
    tokens_used: int              # Token 消耗统计
    elapsed_ms: int               # 耗时（毫秒）
```

### 13.6 调度规则

| 场景 | 调度方式 | Agent 序列 |
|------|---------|-----------|
| 用户导入文件 | LangGraph 串行流水线 | Import → Tag (P3.5) → Link (P5) |
| 用户手动打标签 | 单独触发 | Tag Agent 独立运行 |
| 用户点击"出题" | 单独触发 | Quiz Agent 独立运行 |
| 用户提交深度研究 | LangGraph 条件图 | Retriever → Analyst → Writer → Reviewer（含条件回退） |
| 每周自动总结 | 定时触发 | Review Agent |

### 13.7 开发优先级

```
当前 P3:  Import Agent（数据流水线第一环，零 LLM token）
下一步:   Tag Agent P3.5（简易版，零 token）
之后:     Chat Agent 接入 RAG（基于已索引的向量库）
          Link Agent P5
          上层 Agent 按需开发
```
