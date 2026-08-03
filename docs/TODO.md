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
| P3 | 文档导入+RAG检索 | ✅ | 17/17 | 语义搜索 + BM25 混合检索 |
| P4 | AI 自动标签 | ✅ | 8/8 | 简易版 + 完整版(Function Calling) |
| P5 | 智能双向链接 | ✅ | 8/8 | 语义相关 + 反向链接 + 正文标题高亮 |
| P6 | AI 出题自测 | ✅ | 7/7 | 出题 + 批改（→ S2 温故知新复用） |
| P7 | 知识图谱 | ✅ | 6/6 | 云朵语义聚类（→ S3 知识结构复用） |
| **S1** | **知识进阶** | **⏳** | **0/10** | **Agent 对话评估掌握度 ← 当前** |
| S2 | 温故知新 | ⏳ | 0/8 | 间隔复习 + 自由出题（复用 P6） |
| S3 | 知识结构 | ⏳ | 0/8 | 概念提取 + 依赖图 + 笔记图谱（复用 P7） |
| S4 | 打磨打包 | ⏳ | 0/6 | .exe + GitHub Release |

**页面精简**: 6 页面 → 6 页面（删数据看板，加 S1/S2/S3，合并 P6/P7）
```
📝 智能笔记  💬 知识问答  🔄 温故知新  🎯 知识进阶  🗺️ 知识结构  🗑️ 回收站
```

---

## P1-P5 — 已完成 ✅

<details>
<summary>P1-P5 全部完成 (55/55)</summary>

### P1 — 基础通信 ✅
- [x] 创建目录结构 / requirements / .gitignore
- [x] FastAPI 入口 + CORS
- [x] LLM 调用封装 (DeepSeek SSE + 重试)
- [x] 滑动窗口对话记忆
- [x] POST /api/chat SSE 流式
- [x] Message + Conversation 模型
- [x] PySide6 桌面窗口 + qasync
- [x] httpx API 客户端 + SSE 解析
- [x] 聊天页面（深色气泡流式显示）
- [x] Notion 风格侧边栏
- [x] GitHub 推送

### P2 — 笔记系统 ✅
- [x] Note + Tag 模型（多对多）
- [x] SQLAlchemy 引擎
- [x] 建表（init_db 导入全部模型）
- [x] POST/GET/PUT/DELETE /api/notes
- [x] 分页 + 搜索 + 标签筛选
- [x] GET/POST /api/tags
- [x] note_service.py 业务层
- [x] 笔记页面（左右分栏）
- [x] 笔记列表树 + Markdown 编辑器
- [x] Ctrl+S 保存 + 新建笔记

### P3 — 文档导入 + RAG ✅
- [x] 文档解析 (md/docx/pdf/txt → Markdown)
- [x] 上传导入 / 路径导入 / 解析预览 API
- [x] Embedding 服务 (SiliconFlow BAAI/bge-large-zh-v1.5)
- [x] ChromaDB 向量存储 + 自动同步
- [x] MD5 哈希变更检测 + 定时后台同步
- [x] 语义搜索 API (POST /api/notes/search)
- [x] 混合检索 (语义 0.7 + BM25 0.3 + jieba 分词)
- [x] 知识问答页接入搜索（搜索知识库开关）
- [x] 搜索结果展示 + 笔记跳转

### P4 — AI 自动标签 ✅
- [x] TagAgent (jieba TF-IDF + Embedding 匹配)
- [x] 简易版 (零 token) + 完整版 (Function Calling + LLM)
- [x] ReAct Agent 基类 + ToolRegistry 工具注册机制
- [x] auto-tag API (mode=simple/llm) + suggest-tags API
- [x] TagSuggestBar 前端推荐条（采纳/忽略/合并）
- [x] 标签合并去重 (POST /api/tags/merge)
- [x] 限制 3 个标签 + 仅首次保存推荐

### P5 — 智能双向链接 ✅
- [x] 语义相关笔记 API (GET /api/notes/{id}/related)
- [x] 标题检测 API (正文包含其他笔记标题)
- [x] note_links 表 + 显式链接记录
- [x] 反向链接查询 (linked-from)
- [x] RelatedNotesPanel 右侧面板（可折叠）
- [x] 正文标题自动高亮（Vditor DOM 包裹）

### P6 — AI 出题自测 ✅（→ S2 复用）
- [x] POST /api/quiz/generate — 知识库/文件夹出题
- [x] POST /api/quiz/grade — AI 批改 + 解析
- [x] Quiz 页面（范围选择 + 答题 + 批改结果）

### P7 — 知识图谱 ✅（→ S3 复用）
- [x] 语义聚类 (KMeans + Embedding) → 云朵视图
- [x] Agent 给每簇起名 + 簇间连线
- [x] 聚焦效果（展开放大、其余淡出）
- [x] 统计数据 API (GET /api/dashboard/stats)

</details>

---

## S1 — 知识进阶 🎯（当前）

> **Agent 对话式评估掌握度**。用户选一个标签/主题，Agent 通过提问 + 追问判断理解深度，
> 不是做选择题，而是开放式对话，让用户用自己的话解释概念。

### 1.0 数据模型
- [ ] 1.0.1 `ConceptMastery` 表 — 概念掌握度记录（concept_name, mastery_score 0-100, last_assessed, assessment_count, strengths[], weaknesses[]）
- [ ] 1.0.2 `MasterySession` 表 — 评估对话记录（concept, messages JSON, final_score, created_at）
- [ ] 1.0.3 数据库迁移 — Alembic 或 manual ALTER TABLE

### 1.1 MasteryAgent（核心）
- [ ] 1.1.1 System Prompt 设计 — 学习教练角色，引导用户用自己的话解释，追问笔记没有的内容
- [ ] 1.1.2 工具定义: `get_concept_notes` — 读取该标签下的笔记内容（注入 context）
- [ ] 1.1.3 工具定义: `get_mastery_status` — 查询当前概念掌握度
- [ ] 1.1.4 工具定义: `update_mastery` — 评估结束后写入掌握度 + 强弱项
- [ ] 1.1.5 ReAct 循环实现 — ask → user replies → evaluate → follow-up → … → final score

### 1.2 API
- [ ] 1.2.1 `POST /api/mastery/assess` — SSE 流式评估对话（传入 concept/tag，返回 token 流）
- [ ] 1.2.2 `GET /api/mastery/concepts` — 所有已评估概念的掌握度列表
- [ ] 1.2.3 `GET /api/mastery/concepts/{name}` — 单个概念详情（评分历史、强弱项、最近对话）
- [ ] 1.2.4 `GET /api/mastery/sessions` — 评估历史列表

### 1.3 前端
- [ ] 1.3.1 MasteryPage 页面 — 概念掌握度卡片网格 + 开始评估入口
- [ ] 1.3.2 ConceptCard 组件 — 掌握度圆环 + 强弱项标签 + 最近评估时间
- [ ] 1.3.3 AssessmentChat 组件 — 对话式评估界面（类 Chat 但 Agent 主导提问）
- [ ] 1.3.4 路由 `/mastery` + 侧边栏入口（🎯 知识进阶）

### 1.4 测试
- [ ] 1.4.1 后端: test_mastery_agent.py — Agent 评估流程单元测试
- [ ] 1.4.2 后端: test_mastery_api.py — API 端点集成测试
- [ ] 1.4.3 前端: 掌握度卡片渲染 / 评估对话流

---

## S2 — 温故知新 🔄（预计 3-4 天）

> **间隔重复 + 自由出题**。系统按遗忘曲线自动安排复习时间，到时间提醒；
> 也可手动选范围自由出题。底层复用 P6 出题 + 批改引擎。

### 2.1 数据模型
- [ ] 2.1.1 `ReviewSchedule` 表 — 复习计划（note_id/concept, next_review_at, interval_days, ease_factor, consecutive_correct, consecutive_wrong）
- [ ] 2.1.2 `ReviewLog` 表 — 复习记录（schedule_id, score, reviewed_at）

### 2.2 ReviewAgent
- [ ] 2.2.1 SM-2 间隔重复算法实现（ease factor 调整 + 间隔计算）
- [ ] 2.2.2 复习内容生成 — 复用 P6 出题 + 新增"口述总结"题型
- [ ] 2.2.3 复习提醒机制 — GET /api/review/due（今日待复习列表）

### 2.3 API
- [ ] 2.3.1 `GET /api/review/due` — 今日待复习列表（按优先级排序）
- [ ] 2.3.2 `POST /api/review/start` — 开始一次复习（生成题目 SSE）
- [ ] 2.3.3 `POST /api/review/complete` — 完成复习记录（更新 SM-2 状态 + 联动掌握度）
- [ ] 2.3.4 `GET /api/review/calendar` — 复习日历数据（月度热力图）
- [ ] 2.3.5 `POST /api/review/schedule` — 手动添加到复习计划

### 2.4 前端
- [ ] 2.4.1 ReviewPage 页面 — 今日待复习 + 复习日历 + 自由出题入口
- [ ] 2.4.2 ReviewCard 组件 — 待复习项（标题、间隔天数、优先级指示）
- [ ] 2.4.3 ReviewCalendar 组件 — 月度复习热力图
- [ ] 2.4.4 复用 QuizPage 的答题界面（自由出题模式）
- [ ] 2.4.5 路由 `/review` + 侧边栏入口（🔄 温故知新）

---

## S3 — 知识结构 🗺️（预计 3-4 天）

> **概念提取 + 前置依赖 + 学习路径**。从笔记中自动提取细粒度概念，
> 推断前置依赖关系，可视化知识结构。复用 P7 图谱。

### 3.1 ConceptAgent
- [ ] 3.1.1 概念提取 — LLM 从标签对应的笔记中提取关键概念（比标签更细）
- [ ] 3.1.2 前置依赖推断 — LLM 分析概念间"得先懂 A 才能学 B"的关系
- [ ] 3.1.3 学习路径生成 — 基于掌握度 + 依赖图推荐下一步学习方向
- [ ] 3.1.4 概念关联到笔记 — 哪些笔记涉及这个概念

### 3.2 API
- [ ] 3.2.1 `GET /api/structure/concepts` — 概念列表（含掌握度 + 依赖关系）
- [ ] 3.2.2 `GET /api/structure/graph` — 概念依赖图数据（nodes + edges + mastery）
- [ ] 3.2.3 `GET /api/structure/path` — 推荐学习路径（从当前掌握度出发）
- [ ] 3.2.4 `POST /api/structure/extract` — 触发概念提取（对指定标签）
- [ ] 3.2.5 `GET /api/structure/stats` — 全局知识统计（原 dashboard stats）

### 3.3 前端
- [ ] 3.3.1 StructurePage 页面 — 概念地图 + 笔记图谱 + 统计概览
- [ ] 3.3.2 ConceptMap 组件 — ECharts 概念依赖有向图（节点=概念，边=前置依赖）
- [ ] 3.3.3 NoteGraph 组件 — 复用 P7 云朵聚类图谱（第二个 tab/视图）
- [ ] 3.3.4 LearningPath 组件 — 推荐学习路径时间线
- [ ] 3.3.5 StatsOverview 组件 — 全局统计卡片
- [ ] 3.3.6 路由 `/structure` + 侧边栏入口（🗺️ 知识结构）

---

## S4 — 打磨 + 打包

- [ ] 4.1 全局 UI 细节打磨（间距/动画/反馈）
- [ ] 4.2 PyInstaller 打包成 .exe
- [ ] 4.3 单元测试覆盖核心 API
- [ ] 4.4 README + 演示 GIF + 简历描述
- [ ] 4.5 GitHub Release v1.0.0

---

## 更新记录

| 日期 | 更新 |
|------|------|
| 2026-07-30 | 初始创建 |
| 2026-07-31 | P3~P7 大量完成，详见 git log |
| 2026-08-03 | 前端 UI 打磨：回收站、标签页、Markdown 渲染、侧边栏精简、删除确认 |
| 2026-08-03 | **重大重规划**：P6 出题自测/P7 知识图谱/P8 知识回顾 → S1 知识进阶/S2 温故知新/S3 知识结构。三板块共享掌握度模型，Agent 驱动学习评估 |
