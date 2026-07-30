# AI Second Brain — 任务跟踪清单

> **状态说明**  
> `[ ]` 待办  
> `[~]` 进行中  
> `[x]` 已完成  
> `[!]` 遇到阻塞  

---

## 📊 整体进度

| 阶段 | 状态 | 完成度 | 开始时间 | 完成时间 |
|------|------|--------|---------|---------|
| P1 基础通信 | ⏳ 准备中 | 0/12 | - | - |
| P2 笔记系统 | ⏳ 未开始 | 0/10 | - | - |
| P3 RAG引擎 | ⏳ 未开始 | 0/12 | - | - |
| P4 工具调用 | ⏳ 未开始 | 0/9 | - | - |
| P5 多Agent | ⏳ 未开始 | 0/10 | - | - |
| P6 UI打磨 | ⏳ 未开始 | 0/10 | - | - |
| P7 知识图谱 | ⏳ 未开始 | 0/6 | - | - |
| P8 打包发布 | ⏳ 未开始 | 0/8 | - | - |

---

## P1 — 基础通信（预计 3-4 天）

> **目标**: FastAPI 后端能对话，PySide6 桌面壳能显示 AI 回复  
> **可演示**: 打开桌面窗口，输入文字，看到 AI 流式回复

### 1.1 项目初始化
- [x] 1.1.1 创建完整目录结构（backend/ desktop/ docs/ data/ scripts/）
- [ ] 1.1.2 编写 backend/requirements.txt
- [ ] 1.1.3 编写 desktop/requirements.txt
- [x] 1.1.4 创建 .env.example + backend/app/config.py（环境变量管理）
- [x] 1.1.5 创建 .gitignore（排除 data/ .env __pycache__/ 等）
- [x] 1.1.6 `git init` + 首次 commit

### 1.2 后端 — 基础对话 API
- [ ] 1.2.1 创建 backend/app/main.py（FastAPI 入口 + CORS + 生命周期）
- [ ] 1.2.2 实现 backend/app/core/llm.py（OpenAI SDK 封装 DeepSeek 调用）
- [ ] 1.2.3 实现 backend/app/core/memory.py（滑动窗口记忆，保留最近 10 轮）
- [ ] 1.2.4 实现 backend/app/api/chat.py — `POST /api/chat`（SSE 流式输出）
- [ ] 1.2.5 创建 Message + Conversation 数据模型
- [ ] 1.2.6 用 curl 测试接口：确认流式输出正常

### 1.3 桌面端 — 最简窗口
- [ ] 1.3.1 创建 desktop/main.py（启动后端子进程 + QApplication）
- [ ] 1.3.2 创建 desktop/main_window.py（主窗口框架 + QTabWidget）
- [ ] 1.3.3 实现 desktop/services/api_client.py（httpx.AsyncClient 封装）
- [ ] 1.3.4 实现 desktop/services/sse_client.py（SSE 流式解析 + 信号回调）
- [ ] 1.3.5 实现 desktop/pages/chat_page.py（输入框 + 发送按钮 + 消息显示区）
- [ ] 1.3.6 端到端测试：桌面输入 → 后端 API → AI 回复 → 桌面显示

---

## P2 — 笔记系统（预计 3-4 天）

> **目标**: 完整的笔记 CRUD，SQLite 数据库，桌面端富文本编辑  
> **可演示**: 创建笔记 → 编辑 → 打标签 → 搜索 → 删除

### 2.1 数据库模型
- [ ] 2.1.1 实现 Note + Tag 模型（SQLAlchemy ORM）
- [ ] 2.1.2 配置 SQLAlchemy 引擎 + Session 管理
- [ ] 2.1.3 初始化 Alembic + 生成首次迁移脚本
- [ ] 2.1.4 编写 scripts/init_db.py（创建所有表）

### 2.2 笔记 API
- [ ] 2.2.1 实现 api/notes.py — CRUD 完整接口（5 个端点）
- [ ] 2.2.2 实现 services/note_service.py（业务逻辑层）
- [ ] 2.2.3 定义 Pydantic Schema（NoteCreate/NoteUpdate/NoteResponse）
- [ ] 2.2.4 实现分页 + 搜索 + 按标签筛选
- [ ] 2.2.5 实现 api/tags.py（标签列表 + 创建）

### 2.3 桌面端 — 笔记页面
- [ ] 2.3.1 实现 pages/notes_page.py（左右分栏：目录树 + 编辑器）
- [ ] 2.3.2 实现 widgets/note_tree.py（笔记树形列表，支持文件夹分组）
- [ ] 2.3.3 实现 widgets/markdown_editor.py（基础编辑 + 语法高亮）
- [ ] 2.3.4 实现 Ctrl+S 自动保存 + 保存状态提示
- [ ] 2.3.5 对接笔记 API（创建/读取/更新/删除）

---

## P3 — RAG 引擎（预计 4-5 天）

> **目标**: 上传文档 → 切片 → 向量化 → ChromaDB → 智能问答  
> **可演示**: 拖入三份 PDF，基于文档提问，AI 回答并标注来源

### 3.1 文档处理管道
- [ ] 3.1.1 实现 core/document_parser.py（PDF→PyMuPDF, DOCX→python-docx, MD/TXT）
- [ ] 3.1.2 实现文本清洗（去多余空白、保留段落结构）
- [ ] 3.1.3 实现 core/rag_engine.py — 语义切片（RecursiveCharacterTextSplitter）
- [ ] 3.1.4 实现 core/embedding.py（DeepSeek Embedding API + 批量处理 + 重试）
- [ ] 3.1.5 集成 ChromaDB（collection 管理 + 持久化存储）

### 3.2 RAG API
- [ ] 3.2.1 实现 api/documents.py（上传/列表/删除文档）
- [ ] 3.2.2 实现 api/rag.py — `POST /api/rag/query` SSE 流式
- [ ] 3.2.3 实现混合检索（语义向量 0.7 + BM25 0.3 + RRF 融合）
- [ ] 3.2.4 实现 LLM 重排序（对检索结果做相关性过滤）
- [ ] 3.2.5 实现 services/rag_service.py（RAG 业务编排）
- [ ] 3.2.6 在响应中标注引用来源（doc_name + page + chunk_text）

### 3.3 桌面端 — 知识问答页面
- [ ] 3.3.1 升级 pages/chat_page.py → 知识问答模式
- [ ] 3.3.2 添加文档管理区（拖拽上传 + 文档列表 + 删除）
- [ ] 3.3.3 在对话气泡中显示引用来源标注
- [ ] 3.3.4 添加可信度指示器（绿色=高，黄色=中，红色=低）

---

## P4 — 工具调用（预计 3-4 天）

> **目标**: Agent 能自主决定调用哪个工具解决问题  
> **可演示**: 问"搜索Python最新特性"→ Agent 调搜索 → 返回结果 → 总结

### 4.1 工具定义
- [ ] 4.1.1 实现 tools/web_search.py（DuckDuckGo 搜索）
- [ ] 4.1.2 实现 tools/calculator.py（安全数学表达式求值）
- [ ] 4.1.3 实现 tools/note_search.py（本地笔记全文搜索）
- [ ] 4.1.4 定义工具注册机制（Tool Registry）

### 4.2 ReAct Agent
- [ ] 4.2.1 实现 agents/base.py — ReAct 循环（Thought→Action→Observation→...→Answer）
- [ ] 4.2.2 实现 api/chat.py — `POST /api/chat/tool` 工具调用对话（SSE）
- [ ] 4.2.3 实现工具选择日志 + 调用过程可视化
- [ ] 4.2.4 实现错误处理（工具调用失败 → 重试 → 降级）

### 4.3 桌面端适配
- [ ] 4.3.1 聊天页面增加工具调用状态显示（"🔍 正在搜索..."）
- [ ] 4.3.2 Agent 思考过程的 Thought → Action → Observation 可视化
- [ ] 4.3.3 工具调用结果的 Markdown 美化展示

---

## P5 — 多 Agent 协作（预计 4-5 天）

> **目标**: 4 个 Agent 协同完成深度研究报告  
> **可演示**: 输入主题 → 4 个 Agent 依次工作 → 实时查看进度 → 输出完整报告

### 5.1 Agent 定义
- [ ] 5.1.1 实现 agents/retriever.py（检索 Agent + System Prompt）
- [ ] 5.1.2 实现 agents/analyst.py（分析 Agent + System Prompt）
- [ ] 5.1.3 实现 agents/writer.py（写作 Agent + System Prompt）
- [ ] 5.1.4 实现 agents/reviewer.py（审核 Agent + System Prompt）
- [ ] 5.1.5 每个 Agent 的独立 System Prompt 模板文件

### 5.2 LangGraph 编排
- [ ] 5.2.1 实现 agents/orchestrator.py — StateGraph 工作流定义
- [ ] 5.2.2 实现条件分支（审核通过 → 结束 / 不通过 → 回到写作 / 3次失败 → 降级）
- [ ] 5.2.3 实现 SSE 实时推送每个 Agent 的状态变化
- [ ] 5.2.4 编写编排器单元测试

### 5.3 API + 桌面端
- [ ] 5.3.1 实现 api/research.py — `POST /api/research/start` SSE
- [ ] 5.3.2 实现 pages/research_page.py（研究主题输入 + 进度 + 报告显示）
- [ ] 5.3.3 实现 widgets/agent_status.py（Agent 状态可视化组件 — 4列进度条）
- [ ] 5.3.4 实现研究结果导出为 Markdown 文件

---

## P6 — UI 打磨（预计 3-4 天）

> **目标**: 专业的桌面应用视觉和交互体验  
> **可演示**: 美观的界面、快捷键、主题切换、流畅操作

### 6.1 样式系统
- [ ] 6.1.1 编写 resources/styles/theme.qss（全局 QSS 主题）
- [ ] 6.1.2 实现深色/浅色主题切换
- [ ] 6.1.3 统一字体、颜色、间距规范
- [ ] 6.1.4 整理图标资源

### 6.2 交互优化
- [ ] 6.2.1 实现全局快捷键系统（Ctrl+N/K/S 等）
- [ ] 6.2.2 QStatusBar 状态提示（后端连接状态、保存状态）
- [ ] 6.2.3 加载动画（QMovie / 自定义 spinner）
- [ ] 6.2.4 错误提示对话框（网络错误、API 错误、文件错误）

### 6.3 编辑器增强
- [ ] 6.3.1 Markdown 工具栏（粗体/斜体/标题/列表/代码块/链接）
- [ ] 6.3.2 代码块语法高亮
- [ ] 6.3.3 图片粘贴支持（本地保存 + 引用路径）
- [ ] 6.3.4 自动保存草稿 + 异常退出恢复

---

## P7 — 知识图谱（预计 2-3 天）

> **目标**: 可视化展示知识结构  
> **可演示**: 看板页面展示统计卡片 + 知识图谱力导向图

### 7.1 后端 — 图谱数据
- [ ] 7.1.1 实现 api/dashboard.py — `GET /api/dashboard/stats`（统计数据）
- [ ] 7.1.2 实现 api/dashboard.py — `GET /api/dashboard/graph`（图谱数据 JSON）
- [ ] 7.1.3 计算标签共现关系 + 节点权重

### 7.2 桌面端 — 可视化
- [ ] 7.2.1 实现 widgets/knowledge_graph.py（PySide6-WebEngine + ECharts 力导向图）
- [ ] 7.2.2 实现 pages/dashboard_page.py（统计卡片 + 图谱 + 热门标签）
- [ ] 7.2.3 实现点击图谱节点 → 跳转相关笔记列表
- [ ] 7.2.4 图谱交互（缩放/拖拽/高亮关联）

---

## P8 — 打包发布（预计 2-3 天）

> **目标**: 生成可独立运行的 .exe，发布到 GitHub  
> **可演示**: 别人电脑上双击 .exe 就能用

### 8.1 打包
- [ ] 8.1.1 编写 scripts/build_exe.py（PyInstaller 配置）
- [ ] 8.1.2 编写 .spec 文件（精确控制打包内容）
- [ ] 8.1.3 在干净 Windows 环境测试 .exe 运行
- [ ] 8.1.4 解决 PyInstaller 常见问题（路径、动态库、chromadb）

### 8.2 测试
- [ ] 8.2.1 编写后端 API 单元测试（pytest）（覆盖核心接口）
- [ ] 8.2.2 编写 RAG 管道测试
- [ ] 8.2.3 编写 Agent 编排测试
- [ ] 8.2.4 桌面端手动测试清单 + Bug 修复

### 8.3 发布
- [ ] 8.3.1 编写 README.md（功能介绍 + 安装 + 截图/GIF）
- [ ] 8.3.2 录制演示视频（展示 4 个页面的完整功能）
- [ ] 8.3.3 创建 GitHub 仓库 + Push 代码
- [ ] 8.3.4 编写简历描述 + 面试问答准备文档

---

## 📝 更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-07-30 | 初始创建，规划 8 个阶段 89 个任务 |
