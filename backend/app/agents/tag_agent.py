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

import logging

import jieba
import jieba.analyse

from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.tag import Tag
from app.core.embedding import embedding_service

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
