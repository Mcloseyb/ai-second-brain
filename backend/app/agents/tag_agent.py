"""
Tag Agent — AI 自动标签推荐（P4 简易版）
=========================================
技术方案: jieba TF-IDF 关键词提取 + Embedding 语义匹配已有标签
特点: 零 LLM token（纯规则 + Embedding API，一次批量请求）

流程:
  1. jieba 分词 + TF-IDF 提取 Top-12 候选关键词
  2. 关键词 + 已有标签名一次批量 Embedding
  3. 每个关键词与所有标签算余弦相似度
  4. 相似度 > 阈值(0.75) → 推荐复用该已有标签
  5. 否则 → 建议新建标签（TF-IDF 权重折算分数）
  6. 多关键词命中同一标签取最高分 → 排序 → 输出 Top-5

返回结构（供前端渲染）:
  {
    "note_id": 1,
    "suggestions": [
      {"tag": "深度学习", "type": "existing", "tag_id": 3,
       "keyword": "神经网络", "score": 0.82},
      {"tag": "transformer", "type": "new", "tag_id": null,
       "keyword": "transformer", "score": 0.62}
    ]
  }
"""

import json
import logging
import re

import jieba
import jieba.analyse

from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.tag import Tag
from app.core.embedding import embedding_service
from app.agents.base import ToolDefinition, build_agent

logger = logging.getLogger(__name__)

# ---- 可调参数 ----
TOP_TAGS = 5            # 最终推荐标签数
TOP_KEYWORDS = 12       # 候选关键词池（略多于推荐数）
EXISTING_THRESHOLD = 0.75  # 关键词与已有标签的复用阈值
MAX_TAG_LENGTH = 20     # 建议新建标签的最大长度
NEW_TAG_SCORE_MIN = 0.5 # 新建标签分数下限
NEW_TAG_SCORE_MAX = 0.7 # 新建标签分数上限（保证排在复用标签之后）

# 关键词提取词性: 名词 / 动名词 / 其他名词 / 地名 / 机构名 / 英文
KEYWORD_POS = ("n", "vn", "nz", "ns", "nt", "eng")

# 常用停用词（出现即过滤，避免推荐"我们/可以"这类无意义标签）
STOPWORDS = {
    "这个", "那个", "一个", "一些", "这些", "那些", "以及", "进行", "可以",
    "我们", "你们", "他们", "自己", "什么", "怎么", "为什么", "因为", "所以",
    "但是", "而且", "如果", "没有", "就是", "不是", "还是", "还有", "相关",
    "主要", "关于", "对于", "通过", "需要", "使用", "这个", "之间", "其中",
    "以及", "并且", "或者", "然后", "这样", "那样", "之后", "之前", "时候",
    "问题", "内容", "方法", "方式", "情况", "部分", "可能", "以及", "这种",
    "一种", "方面", "由于", "因此", "此外", "同时", "如何", "如下",
}


class TagAgent:
    """标签推荐 Agent — 简易版（jieba TF-IDF + Embedding）"""

    def __init__(self) -> None:
        # 首次使用自动加载 jieba 词典
        jieba.initialize()

    # ============================================================
    # 主入口
    # ============================================================
    async def suggest_tags(self, db: Session, note: Note) -> list[dict]:
        """
        为指定笔记推荐标签

        Args:
            db: 数据库 session
            note: 目标笔记（含 title / content / tags）

        Returns:
            list[dict]: 标签建议列表（已排序，最多 TOP_TAGS 条）
        """
        text = f"{note.title or ''}\n{note.content or ''}".strip()
        if not text:
            logger.info(f"笔记 {note.id} 内容为空，跳过标签推荐")
            return []

        # 1. 提取候选关键词
        keywords = self._extract_keywords(text)
        if not keywords:
            logger.info(f"笔记 {note.id} 未提取到关键词")
            return []

        # 2. 已有标签（排除笔记已打过的标签，避免重复推荐）
        existing_tags = (
            db.query(Tag)
            .filter(~Tag.notes.any(Note.id == note.id))
            .order_by(Tag.created_at.asc())
            .all()
        )

        # 3. 关键词 ↔ 标签语义匹配
        suggestions = await self._match_keywords(keywords, existing_tags)
        if not suggestions:
            logger.warning(f"笔记 {note.id} 标签匹配失败（Embedding 可能不可用）")
            return []

        # 4. 去重（多关键词命中同一标签保留最高分）+ 排序 + 截断
        deduped = self._dedupe(suggestions)
        result = deduped[:TOP_TAGS]

        logger.info(
            f"笔记 {note.id} 推荐 {len(result)} 个标签: "
            f"{', '.join(s['tag'] for s in result)}"
        )
        return result

    # ============================================================
    # 关键词提取
    # ============================================================
    def _extract_keywords(self, text: str) -> list[str]:
        """jieba TF-IDF 提取关键词，过滤停用词与过短/过长的词"""
        pairs = jieba.analyse.extract_tags(
            text,
            topK=TOP_KEYWORDS,
            allowPOS=KEYWORD_POS,
            withWeight=True,
        )
        keywords: list[str] = []
        for word, _weight in pairs:
            w = word.strip()
            if not w:
                continue
            if w in STOPWORDS or w.lower() in STOPWORDS:
                continue
            if len(w) < 2:
                continue
            if len(w) > MAX_TAG_LENGTH:
                continue
            keywords.append(w)
            if len(keywords) >= TOP_KEYWORDS:
                break
        return keywords

    # ============================================================
    # Embedding 匹配
    # ============================================================
    async def _match_keywords(
        self,
        keywords: list[str],
        existing_tags: list[Tag],
    ) -> list[dict]:
        """
        关键词与已有标签批量语义匹配

        - 关键词 + 标签名一次 Embedding（单次 API 调用）
        - 每个关键词取与之最相似的标签，超过阈值 → 复用
        - 未命中任何标签的关键词 → 建议新建
        """
        if not existing_tags:
            # 无已有标签 → 全部建议新建
            return [
                {
                    "tag": kw,
                    "type": "new",
                    "tag_id": None,
                    "keyword": kw,
                    "score": NEW_TAG_SCORE_MAX,
                }
                for kw in keywords
            ]

        # 一次批量 Embedding: 前段关键词，后段标签名
        tag_names = [t.name for t in existing_tags]
        try:
            vecs = await embedding_service.embed_batch([*keywords, *tag_names])
        except Exception as e:
            logger.error(f"Embedding 批量调用失败: {e}")
            # 降级: 退化为子串匹配（关键词出现在标签名中 或 反向）
            return self._fallback_substring(keywords, existing_tags)

        keyword_vecs = vecs[: len(keywords)]
        tag_vecs = vecs[len(keywords):]
        cos = embedding_service._cosine_similarity

        # 每个关键词 → (最相似标签, 相似度)
        results: list[dict] = []
        for i, kw in enumerate(keywords):
            best_tag: Tag | None = None
            best_sim = 0.0
            for j, tag in enumerate(existing_tags):
                sim = cos(keyword_vecs[i], tag_vecs[j])
                if sim > best_sim:
                    best_sim = sim
                    best_tag = tag

            if best_tag and best_sim >= EXISTING_THRESHOLD:
                results.append({
                    "tag": best_tag.name,
                    "type": "existing",
                    "tag_id": best_tag.id,
                    "keyword": kw,
                    "score": round(best_sim, 3),
                })
            else:
                results.append({
                    "tag": kw,
                    "type": "new",
                    "tag_id": None,
                    "keyword": kw,
                    "score": NEW_TAG_SCORE_MIN,
                })

        return results

    # ============================================================
    # 降级方案: Embedding 不可用时用子串匹配
    # ============================================================
    @staticmethod
    def _fallback_substring(
        keywords: list[str],
        existing_tags: list[Tag],
    ) -> list[dict]:
        """关键词出现在标签名中 / 标签名出现在关键词中 → 视为复用"""
        results: list[dict] = []
        for kw in keywords:
            matched: Tag | None = None
            for tag in existing_tags:
                if kw in tag.name or tag.name in kw:
                    matched = tag
                    break
            if matched:
                results.append({
                    "tag": matched.name,
                    "type": "existing",
                    "tag_id": matched.id,
                    "keyword": kw,
                    "score": 0.8,
                })
            else:
                results.append({
                    "tag": kw,
                    "type": "new",
                    "tag_id": None,
                    "keyword": kw,
                    "score": NEW_TAG_SCORE_MIN,
                })
        return results

    # ============================================================
    # 去重排序
    # ============================================================
    @staticmethod
    def _dedupe(suggestions: list[dict]) -> list[dict]:
        """
        多个关键词命中同一标签时保留最高分。
        排序规则: 复用标签按分数降序 → 新建标签按分数降序。
        """
        best_by_tag: dict[str, dict] = {}
        for s in suggestions:
            key = s["tag"]
            if key not in best_by_tag or s["score"] > best_by_tag[key]["score"]:
                best_by_tag[key] = s

        result = list(best_by_tag.values())
        # existing 在前（分数高），new 在后
        result.sort(key=lambda s: (0 if s["type"] == "existing" else 1, -s["score"]))
        return result


# 全局单例
tag_agent = TagAgent()


# ============================================================
# 完整版（Function Calling）— 标签推荐 System Prompt
# ============================================================

TAG_AGENT_SYSTEM_PROMPT = """你是笔记标签推荐助手。根据笔记内容与已有标签体系，推荐最合适的 3-5 个标签。

工作流程:
1. 先调用 suggest_tags 工具获取候选标签分析（关键词 + 已有标签语义匹配结果）
2. 综合候选与你对内容的理解，确定最终推荐标签
3. 需要建新标签时调用 create_tag；发现已有标签语义重复时调用 merge_tags

规则:
- 优先复用已有标签（type="existing"），避免创建语义重复的新标签
- 标签应简洁具体（2-8 个中文字符或 2-3 个英文单词），覆盖笔记核心主题
- 推荐 3-5 个，按重要性排序
- 如果已有标签明确多余或重复，最多给出 1 条合并建议

最终输出必须且只能是一个 JSON 数组（不要输出解释文字、不要用 markdown 代码块）:
[{"name": "标签名", "type": "existing" 或 "new", "reason": "一句话推荐理由"}]"""


def _parse_llm_json(content: str) -> list | None:
    """从 LLM 输出中解析 JSON 数组（容忍 ```json 包裹 / 前后解释文字）"""
    if not content:
        return None
    text = content.strip()
    # 去掉 markdown 代码块包裹
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 直接解析
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        pass
    # 回退: 提取第一个 JSON 数组
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_suggestion(item: object) -> dict | None:
    """规范化 LLM 输出的单条推荐，字段与简易版保持一致"""
    if not isinstance(item, dict):
        return None
    name = str(item.get("name", "")).strip()
    if not name or len(name) > 30:
        return None
    typ = "existing" if str(item.get("type", "")).strip() == "existing" else "new"
    return {
        "tag": name,
        "type": typ,
        "tag_id": None,          # 由 suggest_tags_llm 补查
        "keyword": "",
        "score": 0.8 if typ == "existing" else 0.5,
        "reason": str(item.get("reason", "")).strip(),
    }


# ============================================================
# TagAgent 完整版方法（挂到类上）
# ============================================================

async def suggest_tags_llm(self: TagAgent, db: Session, note: Note) -> dict:
    """
    完整版标签推荐 — Function Calling + LLM 决策

    相比简易版（jieba+Embedding 直接输出）:
      - jieba+Embedding 只提供候选分析（suggest_tags 工具）
      - LLM 综合候选与内容理解输出最终推荐，推荐理由更合理
      - 可调用 create_tag 创建新标签、merge_tags 收集合并建议

    Returns:
        {
          "note_id": ...,
          "mode": "llm",
          "suggestions": [{tag, type, tag_id, keyword, score, reason}, ...],
          "merge_suggestions": [{from, to, reason}, ...],
          "steps": [{tool, observation}, ...],
          "error": 降级说明（如有）
        }
    """
    text = f"{note.title or ''}\n{note.content or ''}".strip()
    if not text:
        logger.info(f"笔记 {note.id} 内容为空，跳过 LLM 标签推荐")
        return {"note_id": note.id, "mode": "llm", "suggestions": [], "merge_suggestions": [], "steps": []}

    # ---- 定义工具（闭包绑定 db，每个请求独立） ----
    async def suggest_tags_tool(content: str, existing_tags: list[str] | None = None) -> list:
        """基于笔记内容提取候选标签：jieba 关键词 + 与已有标签的语义匹配"""
        if not content:
            return []
        keywords = self._extract_keywords(content)
        tag_objs: list[Tag] = []
        for name in existing_tags or []:
            tag = db.query(Tag).filter_by(name=str(name).strip().lower()).first()
            if tag and tag not in tag_objs:
                tag_objs.append(tag)
        return await self._match_keywords(keywords, tag_objs)

    async def create_tag_tool(name: str) -> dict:
        """创建新标签（已存在则返回已存在）"""
        clean = str(name).strip().lower()
        if not clean or len(clean) > 30:
            return {"ok": False, "reason": "标签名不合法"}
        existing = db.query(Tag).filter_by(name=clean).first()
        if existing:
            return {"ok": True, "tag_id": existing.id, "existed": True}
        tag = Tag(name=clean)
        db.add(tag)
        db.commit()
        logger.info(f"完整版创建标签: {clean} (id={tag.id})")
        return {"ok": True, "tag_id": tag.id, "existed": False}

    async def merge_tags_tool(from_name: str, to_name: str) -> dict:
        """检查两个标签是否语义重复，返回合并建议（不自动执行，由用户确认）"""
        clean_from = str(from_name).strip().lower()
        clean_to = str(to_name).strip().lower()
        if clean_from == clean_to:
            return {"action": "none", "reason": "两个标签相同，无需合并"}
        f = db.query(Tag).filter_by(name=clean_from).first()
        t = db.query(Tag).filter_by(name=clean_to).first()
        if not f or not t:
            return {"action": "none", "reason": "标签不存在，无法合并"}
        return {
            "action": "merge",
            "from": clean_from,
            "to": clean_to,
            "reason": f"「{clean_from}」与「{clean_to}」语义重复",
        }

    # ---- 组装 Agent ----
    registry_tools = [
        ToolDefinition(
            name="suggest_tags",
            description="基于笔记内容提取候选标签：jieba 关键词 + 与已有标签的 Embedding 语义匹配。返回候选标签列表，每个含 tag(标签名), type(existing/new), score(相关度), keyword(来源关键词)。",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "笔记正文内容"},
                    "existing_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "已有标签名列表，用于语义匹配（可选）",
                    },
                },
                "required": ["content"],
            },
            func=suggest_tags_tool,
        ),
        ToolDefinition(
            name="create_tag",
            description="创建一个新标签。当笔记包含现有标签体系未覆盖的核心主题时调用。标签名会转为小写。",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "新标签名"}},
                "required": ["name"],
            },
            func=create_tag_tool,
        ),
        ToolDefinition(
            name="merge_tags",
            description="检查两个已有标签是否语义重复。返回合并建议（from 合并到 to），不会自动执行，最终由用户确认。",
            parameters={
                "type": "object",
                "properties": {
                    "from_name": {"type": "string", "description": "被合并的标签名"},
                    "to_name": {"type": "string", "description": "保留的标签名"},
                },
                "required": ["from_name", "to_name"],
            },
            func=merge_tags_tool,
        ),
    ]

    agent = build_agent(
        name="tag_agent",
        description="标签推荐",
        system_prompt=TAG_AGENT_SYSTEM_PROMPT,
        tools=registry_tools,
        max_steps=4,
    )

    existing_names = [t.name for t in note.tags]
    user_input = (
        f"笔记标题: {note.title}\n"
        f"笔记正文:\n{note.content[:4000]}\n"
        f"已有标签: {json.dumps(existing_names, ensure_ascii=False)}"
    )

    output = await agent.run(user_input)

    # ---- 解析结果 ----
    merge_suggestions: list[dict] = []
    for step in output.steps:
        if step.tool == "merge_tags" and step.observation:
            try:
                obs = json.loads(step.observation)
                if isinstance(obs, dict) and obs.get("action") == "merge":
                    merge_suggestions.append({
                        "from": obs["from"],
                        "to": obs["to"],
                        "reason": obs.get("reason", ""),
                    })
            except json.JSONDecodeError:
                continue

    suggestions: list[dict] = []
    raw = _parse_llm_json(output.content)
    if raw:
        for item in raw:
            sug = _normalize_suggestion(item)
            if not sug:
                continue
            # existing → 补 tag_id；new → 查库避免与已有标签重复
            if sug["type"] == "existing":
                tag = db.query(Tag).filter_by(name=sug["tag"].lower()).first()
                sug["tag_id"] = tag.id if tag else None
            else:
                tag = db.query(Tag).filter_by(name=sug["tag"].lower()).first()
                if tag:
                    sug["type"] = "existing"
                    sug["tag_id"] = tag.id
                sug["score"] = round(sug["score"] + len(sug["reason"]) / 100, 3)
            suggestions.append(sug)
            if len(suggestions) >= 5:
                break
        # 已有标签优先展示，按 type 排序
        suggestions.sort(key=lambda s: (0 if s["type"] == "existing" else 1, -s["score"]))
    else:
        logger.warning(f"笔记 {note.id} LLM 输出无法解析，降级到简易版")
        suggestions = await self.suggest_tags(db, note)
        return {
            "note_id": note.id,
            "mode": "llm",
            "suggestions": suggestions,
            "merge_suggestions": merge_suggestions,
            "steps": [{"tool": s.tool, "observation": s.observation} for s in output.steps],
            "error": "LLM 输出解析失败，已降级为简易版推荐",
        }

    logger.info(
        f"笔记 {note.id} 完整版推荐 {len(suggestions)} 标签, "
        f"{len(merge_suggestions)} 条合并建议"
    )
    return {
        "note_id": note.id,
        "mode": "llm",
        "suggestions": suggestions,
        "merge_suggestions": merge_suggestions,
        "steps": [{"tool": s.tool, "observation": s.observation} for s in output.steps],
    }


# 挂载到 TagAgent 类
TagAgent.suggest_tags_llm = suggest_tags_llm
