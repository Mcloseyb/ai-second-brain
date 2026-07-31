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
| **P3** | **文档导入+RAG检索** | **✅** | **17/17** | 语义搜索 + BM25 混合检索 |
| P4 | AI 自动标签 | ✅ | 8/8 | 简易版 + 完整版(Function Calling) |
| P5 | 智能双向链接 | ✅ | 8/8 | 语义相关 + 反向链接 + 正文标题高亮 |
| P6 | AI 出题自测 | ✅ | 7/7 | 知识库/文件夹出题 + AI 批改 |
| P7 | 真实知识图谱 | ✅ | 6/6 | 语义互联图谱（用户约束） |
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
- [x] 3.2.3 实现混合检索（语义 0.7 + BM25 关键词 0.3）— jieba 分词 + BM25Okapi + 加权融合

### 3.3 前端
- [x] 3.3.1 Chat 页面接入笔记搜索 — 开关「搜索知识库」，自动检索+注入上下文
- [x] 3.3.2 搜索结果展示（笔记标题 + 匹配片段 + 相似度，点击跳转）
- [x] 3.3.0 前端 API 客户端 — notesApi.search() 已就绪

---

## P4 — AI 自动标签（预计 3-4 天）

> **写完笔记 Ctrl+S → AI 自动分析 → 推荐 3-5 个标签 → 一键采纳**  
> **Agent 核心流程: 接收分析任务 → 调用 Embedding 工具 → 对比已有标签 → 输出推荐**

### 4.0 简易版 ✅（零 LLM token）
> 技术方案: jieba TF-IDF 关键词提取 + Embedding 语义匹配已有标签，单次批量 Embedding。
> 相似度 > 0.75 → 复用已有标签；否则建议新建。多关键词命中同一标签保留最高分，排序输出 Top-5。

- [x] 4.0.1 实现 agents/tag_agent.py — TagAgent（jieba 提取 Top-12 关键词 + Embedding 余弦匹配）
- [x] 4.0.2 Embedding 失败降级 — 退化为子串匹配，不影响推荐
- [x] 4.0.3 POST /api/notes/{id}/auto-tag — 返回推荐标签列表（type: existing/new + 分数）
- [x] 4.0.4 前端 TagSuggestBar — 保存后自动弹出推荐条（单个采纳 / 全部采纳 / 忽略）
- [x] 4.0.5 采纳标签通过现有 updateNote 批量应用（合并去重）

### 4.1 Function Calling 基础设施 ✅
- [x] 4.1.1 实现 agents/base.py — ReAct Agent 基类（ToolDefinition/AgentStep/AgentOutput）
- [x] 4.1.2 实现工具注册机制 ToolRegistry（register/schemas/execute）
- [x] 4.1.3 定义标签推荐工具 suggest_tags + create_tag + merge_tags（闭包绑定 db）
- [x] 4.1.4 实现标签推荐 System Prompt（完整版 LLM 决策）

### 4.2 API
- [x] 4.2.1 POST /api/notes/{id}/auto-tag — mode=simple（简易版）/ mode=llm（完整版）
- [x] 4.2.2 批量应用标签 — 通过 PUT /api/notes/{id} 的 tags 数组实现（无需独立端点）
- [x] 4.2.3 POST /api/tags/merge — 合并重复标签（from→to，笔记自动迁移）

### 4.3 前端
- [x] 4.3.1 保存笔记后自动弹窗"AI 推荐了 3 个标签"
- [x] 4.3.2 一键采纳 / 手动调整 / 忽略
- [x] 4.3.3 "AI 打标签"按钮触发完整版 + 推荐理由展示 + merge 建议一键合并

---

## P5 — 智能双向链接（预计 3-4 天）

> **打开一篇笔记 → 右侧出现 "Related Notes" → 基于语义相似度自动发现**

### 5.1 后端
- [x] 5.1.1 笔记相似度计算 — 复用 rag_engine.search 纯语义检索（Embedding 余弦，零 token）
- [x] 5.1.2 GET /api/notes/{id}/related — 语义 Top-5（排除自身 + 同笔记库过滤）
- [x] 5.1.3 GET /api/notes/{id}/title-links — 正文检测其他笔记标题（count 命中）
- [x] 5.1.4 note_links 表（source/target/link_type 唯一约束）+ POST /links 落库 + linked-from 查询

### 5.2 前端
- [x] 5.2.1 笔记页右侧 "Related Notes" 面板（可折叠 36px/280px）
- [x] 5.2.2 打开笔记时自动加载关联列表（related + linked-from 并行）
- [x] 5.2.3 笔记正文自动高亮已链接的笔记标题（Vditor DOM 包裹 + 输入/切换时重应用）
- [x] 5.2.4 被引用笔记显示 "Linked from: X篇笔记"（可展开列表）

---

## P6 — AI 出题自测（预计 3-4 天）

> **选择知识库 / 知识库内文件夹 → "出题" → AI 生成 5 道选择题 + 2 道简答题**  
> **答完 → AI 批改 → 告诉哪里掌握得好、哪里需要复习**  
> **出题范围：选择文件夹 = 该文件夹 + 所有子文件夹下的全部笔记（递归）**

### 6.1 后端
- [x] 6.1.1 POST /api/quiz/generate — 基于笔记内容生成题目（notebook_id + folder 可选）
- [x] 6.1.2 POST /api/quiz/grade — 批改答案 + 解析（选择 exact match / 简答 LLM）
- [x] 6.1.3 Prompt 模板设计（Few-shot 生成题目）
- [x] 6.1.4 题目 + 成绩存储到数据库（Quiz 表：questions_json / grade_json）

### 6.2 前端
- [x] 6.2.1 出题自测页面（替换原"深度研究"页）— 范围选择 + "生成题目"按钮
- [x] 6.2.2 答题界面（选择题 + 简答）
- [x] 6.2.3 批改结果展示（对错 + 解析 + 评分 + 复习建议）

> 说明：原「深度研究」页面为占位空壳（无真实后端），已替换为「出题自测」页面（路由 `/quiz`）。

---

## P7 — 真实知识图谱（预计 2-3 天）

> **用真实笔记数据驱动图谱（不再用假数据）**  
> **连线以语义互联为主导**：两篇笔记 Embedding 余弦相似度 > 阈值即连线（强度=相似度）。
> 标签共现不用于连线（用户明确约束），仅可选作为节点的分类着色。

### 7.1 后端
- [x] 7.1.1 GET /api/dashboard/stats — 统计数据（笔记数/标签数/关联数）
- [x] 7.1.2 GET /api/dashboard/graph — 图谱数据（nodes: 笔记标题, edges: 语义相似度 > 阈值连线）
- [x] 7.1.3 计算节点权重（笔记字数/引用次数）

### 7.2 前端
- [x] 7.2.1 graph_page 接入真实 API 数据
- [x] 7.2.2 点击图谱节点 → 打开对应笔记
- [x] 7.2.3 图谱筛选（按标签/关联强度）

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
| 2026-07-31 | P3.2.3 混合检索完成，P3 全绿 17/17；笔记库/文件夹树/右键菜单完成 |
| 2026-07-31 | P4 简易版完成（4/8）：jieba TF-IDF + Embedding 标签推荐 Agent + auto-tag API + 前端 TagSuggestBar |
| 2026-07-31 | P4 完整版完成（8/8）：ReAct Agent 基类 + ToolRegistry + Function Calling 标签推荐 + merge 去重合并 |
| 2026-07-31 | P5 完成（7/8）：语义相关 + 标题检测 + note_links 落库 + Related Notes 面板 + Linked from |
| 2026-07-31 | P5 全部完成（8/8）：正文标题自动高亮（Vditor DOM 包裹）；P7 图谱约束=语义互联 |
| 2026-07-31 | P6 全部完成（7/7）：深度研究页 → AI 出题自测页（知识库/文件夹递归出题 + 答题 + AI 批改） |
| 2026-07-31 | P7 全部完成（6/6）：真实知识图谱 — 语义互联连线（Embedding 余弦），标签仅着色；看板真实 API + 强度/标签筛选 + 节点跳转 |
| 2026-07-31 | P7 图谱精简：删除热门标签卡片；连线改 Top-K 邻居（默认 K=3，滑块 1~5 可调）+ 悬停节点临时亮出全量语义关联 |
| 2026-07-31 | 图谱稳定化：悬停显边改独立叠加系列（layout:'none' 按主图坐标绘制），不再触发力导向重新布局（节点不跳动）；数据看板只保留知识图谱栏目（删除统计卡片） |
| 2026-07-31 | 图谱重构为「无连线语义聚类」：不画连线；KMeans（纯 numpy）按 Embedding 分簇同簇同色；力导向布局聚簇后固定；关联次数定节点大小；点击高亮关联、再次点击打开笔记（簇数 2~6 可调） |
| 2026-07-31 | 图谱升级「云朵视图」：每簇笔记一朵云，云朵中央显示 Agent（LLM）按簇内容起的主题名；相关云朵用线互联；坐标全部前端计算（layout:'none'）固定不抖动、禁止拖拽；云朵内笔记默认无名，点云朵才展开；文字颜色与圆圈区分、深色适配；点击笔记高亮关联、再点打开 |
