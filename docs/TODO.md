# 学迹 LearnTrace — 任务跟踪清单

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
| P6 | AI 出题自测 | ✅ | 7/7 | 出题 + 批改（后端保留，前端并入温故知新） |
| P7 | 知识图谱 | ✅ | 6/6 | 云朵语义聚类（后端保留，聚类逻辑复用到温故知新） |
| **R1** | **学迹 温故知新 V2** | **✅** | **12/12** | **SM-2 四档评分 + 掌握度分级 + 四种复习模式 + 连续打卡 + 交互日历** |
| R2 | 打磨打包 | ⏳ | 0/6 | .exe + GitHub Release |

**最终页面**（4 主页面）:
```
📝 智能笔记  💬 知识问答  🔄 温故知新  🗑️ 回收站
```

> 原计划 S1(知识进阶)/S2(温故知新)/S3(知识结构) 三阶段已合并为一个统一的温故知新系统。
> 旧 S1 Mastery 代码（开放式对话评估）已从路由和侧边栏移除，代码保留不删。
> 旧 P6 Quiz / P7 Dashboard 页面已从路由和侧边栏移除，后端逻辑保留复用。
> 新增：`concept_clusters` / `cluster_notes` / `note_review_states` / `review_logs` / `user_streaks` 五张表。
> 新增：`services/cluster_service.py` / `services/review_service.py` / `api/review.py` / `models/streak.py`。
> 新增前端：`pages/ReviewPage.tsx`（簇详情 + 四档评分 + 四种模式 + 打卡 + 可交互日历）。

### R1 V2 更新 (2026-08-03)

> **项目更名为「学迹 LearnTrace」**
> V2 核心改进（对标 Anki/墨墨/Duolingo）：
> - **SM-2 四档评分**：Again/Hard/Good/Easy 替代对错二分，per-note 自评驱动遗忘曲线
> - **掌握度分级**：🔴新学 → 🟡学习 → 🟢初通 → 🔵熟练，纯规则计算
> - **四种复习模式**：到期复习 / 集中突击 / 错题重温 / 新知初探（scope=due/all/errors/new）
> - **连续打卡**：`user_streaks` 表，测验完成后自动更新，最长记录
> - **簇详情面板**：点击簇展示笔记列表 + SM-2 状态 + 掌握度分布 + 四种模式按钮
> - **日历缩小+可交互**：24×24 迷你热力图，点击弹出当天复习详情 Popover
> - **ReviewLog.rating**：记录每次自评，日历详情展示每篇笔记的评分

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

## R1 — 温故知新 🔄 ✅

> **P6+P7+S1 三合一重构**。概念簇语义聚类 + SM-2 遗忘曲线调度 + 选择题测验 + 日历热力图。
> 导入笔记 → 自动归簇 + 创建 SM-2 状态 → 到期提醒 → 混合出题 → 批改 → 更新遗忘曲线。

### 1.0 数据模型
- [x] 1.0.1 `ConceptCluster` 表 — 聚类结果持久化（cluster_id, name, embedding 中心向量, note_count）
- [x] 1.0.2 `ClusterNote` 表 — 簇↔笔记映射（cluster_id + note_id 复合主键）
- [x] 1.0.3 `NoteReviewState` 表 — SM-2 遗忘曲线状态（ease_factor, interval_days, repetitions, next_review_at）
- [x] 1.0.4 `ReviewLog` 表 — 复习记录（note_id, cluster_id, quiz_id, correct/total count）

### 1.1 聚类服务
- [x] 1.1.1 `ClusterService` — 从 P7 dashboard.py 提取 KMeans 逻辑
- [x] 1.1.2 增量归类 — 新笔记导入时 Embedding 相似度归入最近簇
- [x] 1.1.3 全量重聚类 — `POST /api/review/clusters/recluster` + Agent 命名
- [x] 1.1.4 新笔记导入自动创建 SM-2 状态 + 尝试归簇（hook 到 note_service.create）

### 1.2 复习服务
- [x] 1.2.1 `ReviewService` — SM-2 算法实现（ease_factor 微调 + 间隔计算）
- [x] 1.2.2 到期查询 — `GET /api/review/due`（next_review_at <= NOW，按簇分组）
- [x] 1.2.3 簇混合出题 — `POST /api/review/generate`（仅选择题，标注 source_note_id）
- [x] 1.2.4 批改 + SM-2 更新 — `POST /api/review/grade`（按笔记汇总正确率 → 更新遗忘状态 + ReviewLog）
- [x] 1.2.5 小测/中测/大测 — 5/10/20 题
- [x] 1.2.6 复习日历 — `GET /api/review/calendar`（月度热力图数据）
- [x] 1.2.7 自由出题 — `POST /api/review/free-generate` + `free-grade`（不计入 SM-2）

### 1.3 前端
- [x] 1.3.1 `ReviewPage` 页面 — 左侧簇列表 + 右侧内容区
- [x] 1.3.2 今日待复习 — 到期笔记按簇分组，一键开始测验
- [x] 1.3.3 测验界面 — 选择题答题 + 批改结果 + 每题来源笔记链接 + SM-2 更新提示
- [x] 1.3.4 自由出题 — 选簇/题量，不计入遗忘曲线
- [x] 1.3.5 复习日历 — 月度热力图
- [x] 1.3.6 路由 `/review` + 侧边栏入口

### 1.4 旧代码清理
- [x] 1.4.1 移除 `/quiz`、`/mastery`、`/dashboard` 路由和侧边栏入口
- [x] 1.4.2 删除 `MasteryPage.tsx`、`DashboardPage.tsx`
- [x] 1.4.3 从 `main.py` 移除 mastery/dashboard router 注册
- [x] 1.4.4 后端保留不删（quiz_service, cluster_service 内部复用）

---

## R2 — 打磨 + 打包

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
| 2026-08-03 | **V2 重构**: 项目更名「学迹 LearnTrace」。SM-2 四档评分、掌握度分级、四种复习模式、连续打卡、簇详情面板、可交互日历 |
