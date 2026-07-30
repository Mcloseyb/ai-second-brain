# 🧠 AI Second Brain — AI 协同个人知识库管理系统

> 一个基于 PySide6 + FastAPI 的桌面端个人知识管理应用，集成 RAG 智能问答、多 Agent 协作深度研究、知识图谱可视化。

## 🚀 快速开始

```bash
# 1. 安装后端依赖
cd backend
pip install -r requirements.txt

# 2. 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 填入你的 DEEPSEEK_API_KEY

# 3. 初始化数据库
python ../scripts/init_db.py

# 4. 启动桌面应用
cd ../desktop
pip install -r requirements.txt
python main.py
```

## 📖 文档

- [总体规划报告](docs/PROJECT_PLAN.md)
- [任务跟踪](docs/TODO.md)
- [工程规范](.claude/CLAUDE.md)

## 🛠 技术栈

| 层级 | 技术 |
|------|------|
| 桌面 UI | PySide6 + Qt Designer |
| 后端 API | FastAPI + Uvicorn |
| AI 引擎 | LangChain + LangGraph + DeepSeek |
| 向量数据库 | ChromaDB |
| 关系数据库 | SQLite |
| 打包 | PyInstaller |

## 📊 开发阶段

- [ ] P1 — 基础通信（FastAPI + 流式对话 + 桌面壳）
- [ ] P2 — 笔记系统（CRUD + 标签 + 富文本编辑）
- [ ] P3 — RAG 引擎（文档上传 + 向量检索 + 智能问答）
- [ ] P4 — 工具调用（Function Calling + ReAct Agent）
- [ ] P5 — 多 Agent 协作（LangGraph 编排）
- [ ] P6 — UI 打磨（主题 + 快捷键 + 交互优化）
- [ ] P7 — 知识图谱（ECharts 可视化）
- [ ] P8 — 打包发布（.exe + GitHub）

## 📝 许可

MIT
