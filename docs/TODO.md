# AI Second Brain — 任务跟踪清单

> **状态说明**  
> `[ ]` 待办 `[~]` 进行中 `[x]` 已完成 `[!]` 阻塞  
> **每轮对话结束时更新本文件**

---

## 整体进度

| 阶段 | 主题 | 状态 | 完成度 | 核心交付 |
|------|------|------|--------|---------|
| P1 | 基础通信 | ✅ | 12/12 | SSE流式对话 |
| P2 | 笔记系统 | ✅ | 10/10 | CRUD + 编辑器 |
| **P3** | **文档导入+RAG检索** | **⏳ 当前** | **16/17** | 语义搜索自己的笔记 |
| P4 | AI 自动标签 | ⏳ | 0/8 | Function Calling Agent |
| P5 | 智能双向链接 | ⏳ | 0/8 | 自动发现关联笔记 |
| P6 | AI 出题自测 | ⏳ | 0/7 | 根据笔记生成题目 |
| P7 | 真实知识图谱 | ⏳ | 0/6 | 标签+语义双驱图谱 |
| P8 | 知识回顾总结 | ⏳ | 0/5 | 周报 + 学习路径 |
| P9 | 打磨打包 | ⏳ | 0/8 | .exe + GitHub Release |

**前端重构** — 2026-07-31 完成: Vue 3 → React 18 + TypeScript + Tailwind + shadcn/ui
- 四大页面全部迁移: 智能笔记 / 知识问答 / 深度研究 / 数据看板
- Vditor Markdown 编辑器 / ECharts 知识图谱 / SSE 流式对话
- Zustand 状态管理 / QWebChannel Qt 桥接 / 浅色深色主题切换
- 打包输出 `frontend/dist/`，desktop 已适配新路径

**暂存池（做完 P9 后再考虑）**: 知识缺口发现 / 学习路径时间线 / 概念成熟度追踪 / AI 学习伙伴

---

## P1 — 基础通信 ✅

<details>
<summary>12/12 已完成</summary>

- [x] 创建目录结构 / requirements / .gitignore
- [x] FastAPI 入口 + CORS
- [x] LLM 调用封装 (DeepSeek SSE + 重试)
- [x] 滑动窗口对话记忆
- [x] POST /api/chat SSE 流式
- [x] Message + Conversation 模型
- [x] PySide6 桌面窗口 + qasync
- [x] httpx API 客户端 + SSE 解析
- [x] 聊天页面（深色气泡流式显示）
- [x] curl 测试通过
- [x] Notion 风格侧边栏
- [x] GitHub 推送
</details>

---

## P2 — 笔记系统 ✅

<details>
<summary>10/10 已完成</summary>

- [x] Note + Tag 模型（多对多）
- [x] SQLAlchemy 引擎 (已在 P1 做)
- [x] 建表（init_db 导入全部模型）
- [x] POST/GET/PUT/DELETE /api/notes
- [x] 分页 + 搜索 + 标签筛选
- [x] GET/POST /api/tags
- [x] note_service.py 业务层
- [x] 笔记页面（左右分栏）
- [x] 笔记列表树 + Markdown 编辑器
- [x] Ctrl+S 保存 + 新建笔记
</details>

---

## P3 — 文档导入 + RAG 笔记检索

> **三大模块: ① 文档导入(md/docx/pdf→笔记) → ② 增量同步(MD5 变更检测) → ③ 语义搜索(自然语言搜笔记)**

### 3.0 文档导入 + 同步框架 ✅
- [x] 3.0.1 POST /api/documents/import — 上传文件导入为笔记
- [x] 3.0.2 POST /api/documents/import-from-path — 本地路径导入
- [x] 3.0.3 core/document_parser.py — md/docx/pdf/txt → Markdown
- [x] 3.0.4 SyncService — 全量/增量/单篇同步 + MD5 变更检测
- [x] 3.0.5 POST /api/sync/now — 手动触发同步
- [x] 3.0.6 定时自动同步 — lifespan 后台协程 + 开关 API

### 3.1 后端 — Embedding + 向量存储
- [x] 3.1.1 实现 core/embedding.py（SiliconFlow BAAI/bge-large-zh-v1.5）
- [x] 3.1.2 实现 core/rag_engine.py（笔记文本向量化 + ChromaDB 存储）
- [x] 3.1.3 笔记保存时自动同步到向量库（note_service 中触发）
- [x] 3.1.4 笔记删除时同步清理向量库
- [x] 3.1.5 启动时把已有笔记全量索引一遍

### 3.2 API
- [x] 3.2.1 POST /api/notes/search — 语义搜索笔记（返回 Top-K + 相似度分数）
- [x] 3.2.2 搜索时显示摘录片段（返回存储的前 2000 字符文本）
- [ ] 3.2.3 实现混合检索（语义 0.7 + BM25 关键词 0.3）

### 3.3 前端
- [x] 3.3.1 Chat 页面接入笔记搜索 — 开关「搜索知识库」，自动检索+注入上下文
- [x] 3.3.2 搜索结果展示（笔记标题 + 匹配片段 + 相似度，点击跳转）
- [x] 3.3.0 前端 API 客户端 — notesApi.search() 已就绪

---

## P4 — AI 自动标签（预计 3-4 天）

> **写完笔记 Ctrl+S → AI 自动分析 → 推荐 3-5 个标签 → 一键采纳**  
> **Agent 核心流程: 接收分析任务 → 调用 Embedding 工具 → 对比已有标签 → 输出推荐**

### 4.1 Function Calling 基础设施
- [ ] 4.1.1 实现 agents/base.py — ReAct Agent 基类
- [ ] 4.1.2 实现工具注册机制 ToolRegistry
- [ ] 4.1.3 定义标签推荐工具 suggest_tags(content, existing_tags)
- [ ] 4.1.4 实现标签推荐 System Prompt

### 4.2 API
- [ ] 4.2.1 POST /api/notes/{id}/auto-tag — 返回推荐标签列表
- [ ] 4.2.2 POST /api/notes/{id}/tags — 批量应用标签

### 4.3 前端
- [ ] 4.3.1 保存笔记后自动弹窗"AI 推荐了 3 个标签"
- [ ] 4.3.2 一键采纳 / 手动调整 / 忽略

---

## P5 — 智能双向链接（预计 3-4 天）

> **打开一篇笔记 → 右侧出现 "Related Notes" → 基于语义相似度自动发现**

### 5.1 后端
- [ ] 5.1.1 实现笔记相似度计算（Embedding 余弦相似度）
- [ ] 5.1.2 GET /api/notes/{id}/related — 返回最相关的 Top-5 笔记
- [ ] 5.1.3 正文内自动检测其他笔记标题 → 建议生成超链接
- [ ] 5.1.4 记录笔记间的引用关系（note_links 表: source_id → target_id）

### 5.2 前端
- [ ] 5.2.1 笔记页右侧增加 "Related Notes" 面板
- [ ] 5.2.2 打开笔记时自动加载关联列表
- [ ] 5.2.3 笔记正文中自动高亮已链接的笔记标题
- [ ] 5.2.4 被引用笔记底部显示 "Linked from: X篇笔记"

---

## P6 — AI 出题自测（预计 3-4 天）

> **选中几篇笔记 → "出题" → AI 生成 5 道选择题 + 2 道简答题**  
> **答完 → AI 批改 → 告诉哪里掌握得好、哪里需要复习**

### 6.1 后端
- [ ] 6.1.1 POST /api/quiz/generate — 基于笔记内容生成题目
- [ ] 6.1.2 POST /api/quiz/grade — 批改答案 + 解析
- [ ] 6.1.3 Prompt 模板设计（Few-shot 生成题目）
- [ ] 6.1.4 题目 + 成绩存储到数据库

### 6.2 前端
- [ ] 6.2.1 笔记页面 "Generate Quiz" 按钮
- [ ] 6.2.2 答题界面（选择题 + 简答）
- [ ] 6.2.3 批改结果展示（对错 + 解析 + 复习建议）

---

## P7 — 真实知识图谱（预计 2-3 天）

> **用真实笔记数据驱动图谱（不再用假数据）**  
> **标签共现 = 连线 / 语义相似 = 连线粗细**

### 7.1 后端
- [ ] 7.1.1 GET /api/dashboard/stats — 统计数据（笔记数/标签数/关联数）
- [ ] 7.1.2 GET /api/dashboard/graph — 图谱数据（nodes: 笔记标题, edges: 标签共现/语义相似）
- [ ] 7.1.3 计算节点权重（笔记字数/引用次数）

### 7.2 前端
- [ ] 7.2.1 graph_page 接入真实 API 数据
- [ ] 7.2.2 点击图谱节点 → 打开对应笔记
- [ ] 7.2.3 图谱筛选（按标签/时间/关联强度）

---

## P8 — 知识回顾总结（预计 2-3 天）

> **"本周你学了什么" → AI 分析本周笔记 → 生成小结**  
> **时间线视图 → 看到自己的学习成长轨迹**

### 8.1 后端
- [ ] 8.1.1 POST /api/summary/weekly — 本周知识小结
- [ ] 8.1.2 按标签聚类 → 按时间排序 → AI 生成总结
- [ ] 8.1.3 GET /api/timeline — 学习时间线数据

### 8.2 前端
- [ ] 8.2.1 Dashboard 页面替换为真实统计
- [ ] 8.2.2 本周小结卡片 + 学习时间线

---

## P9 — 打磨 + 打包（预计 2-3 天）

- [ ] 9.1 全局 UI 细节打磨（间距/动画/反馈）
- [ ] 9.2 PyInstaller 打包成 .exe
- [ ] 9.3 单元测试覆盖核心 API
- [ ] 9.4 README + 演示 GIF + 简历描述
- [ ] 9.5 GitHub Release v1.0.0

---

## 暂存池

| 功能 | 说明 |
|------|------|
| 知识缺口发现 | AI 分析薄弱环节，推荐学习方向 |
| 学习路径时间线 | 可视化学习成长轨迹 |
| 概念成熟度追踪 | 每个标签有掌握度分数 |
| AI 学习伙伴 | 对话式复习提问 + 纠正补充 |

---

## 更新记录

| 日期 | 更新 |
|------|------|
| 2026-07-30 | 初始创建 |
| 2026-07-30 晚 | 方向调整：从"多Agent写报告"改为"知识互联笔记系统" |
| 2026-07-31 | P3.1.3~3.2.1 完成：笔记自动向量化闭环 + 语义搜索 API；P3 14/17 |
