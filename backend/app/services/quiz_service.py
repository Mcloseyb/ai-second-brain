"""
出题自测业务层（P6）
-------------------
功能:
  - collect_notes:  按知识库 + 文件夹（递归）收集出题笔记
  - generate_quiz:  LLM 生成题目（5 选择 + 2 简答），持久化到 Quiz 表
  - grade_quiz:     批改（选择 exact match / 简答 LLM 对比），结果持久化

设计:
  - 出题范围: 整个知识库（folder=None）或某文件夹（folder="AI/Agent"）
    选择文件夹等价于选择该文件夹及其所有子文件夹下的全部笔记（递归）。
  - 内容聚合: 笔记正文可能很长，截断到可控长度再喂给 LLM，
    避免超出上下文窗口（每篇标题 + 前 500 字，最多 15 篇，总量 ≤ 8000 字）。
"""

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.quiz import Quiz
from app.core.llm import llm_service

logger = logging.getLogger(__name__)

# 出题参数
MAX_NOTES = 15            # 最多取前 N 篇（按最近更新）
PER_NOTE_CHARS = 500      # 每篇正文截断长度
MAX_TOTAL_CHARS = 8000    # 聚合内容总长度上限
DEFAULT_QUESTION_COUNT = 7  # 5 选择 + 2 简答

# Prompt 模板
GENERATE_SYSTEM_PROMPT = (
    "你是一位出题专家，擅长根据学习笔记出高质量自测题，帮助用户检验掌握程度。"
    "你只输出严格的 JSON，不输出任何其他文字。"
)

GENERATE_USER_PROMPT = """根据以下笔记内容，为用户生成一套自测题。

## 笔记内容
{content}

## 要求
生成 {choice_count} 道单选题 + {short_count} 道简答题。

严格按以下 JSON 数组格式输出（不要 markdown 代码块，不要前后缀文字）：
[
  {{"type":"choice","question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"...解析..."}},
  {{"type":"short","question":"...","answer":"参考答案...","explanation":"...解析...","key_points":["关键词1","关键词2"]}}
]

规则：
- 单选题必须有 4 个选项，选项要有干扰性，答案只能是 A/B/C/D 中的一个字母
- 简答题的参考答案要包含关键要点，key_points 提炼 2-4 个采分点
- 题目应覆盖不同笔记，避免集中在某一篇
- 题目难度适中，重点考察笔记中的核心概念与易错点"""

GRADE_SYSTEM_PROMPT = (
    "你是一位严格的批改老师。请根据参考答案评价用户的简答题作答，"
    "输出严格的 JSON，不输出任何其他文字。"
)

GRADE_USER_PROMPT = """请批改以下简答题作答。

题目：{question}
参考答案：{answer}
关键采分点：{key_points}

用户作答：{user_answer}

按以下 JSON 对象格式输出（不要 markdown 代码块）：
{{"correct": true或false, "score": 0到10的整数, "comment": "针对性点评，指出对错原因与不足"}}

评分规则：
- 用户作答覆盖了大部分采分点 → correct=true，score 7-10
- 作答相关但明显不完整 → correct=false，score 4-6
- 作答无关或错误 → correct=false，score 0-3"""


class QuizService:
    """出题自测服务"""

    # ============================================================
    # 收集出题笔记（递归文件夹）
    # ============================================================
    def collect_notes(self, db: Session, notebook_id: int, folder: str | None) -> list[Note]:
        """
        收集出题范围内的笔记（含标题+正文）

        folder=None → 知识库下全部笔记
        folder="AI" → folder 为 "AI" 或 "AI/..." 的笔记（含子文件夹，递归）
        """
        query = db.query(Note).filter_by(notebook_id=notebook_id)
        if folder:
            f = folder.strip().strip("/")
            if f:
                # 与 notebooks.py 文件夹筛选同模式：folder == x OR folder LIKE x/%
                query = query.filter(
                    (Note.folder == f) | Note.folder.startswith(f + "/")
                )
        # 只出有正文的笔记，最近更新的优先
        query = query.filter(
            Note.content.isnot(None), Note.content != ""
        ).order_by(Note.updated_at.desc())
        return query.all()

    # ============================================================
    # 生成题目
    # ============================================================
    def _build_aggregated_content(self, notes: list[Note]) -> str:
        """把笔记聚合成一段可控长度的文本（标题 + 前 500 字）"""
        parts: list[str] = []
        budget = MAX_TOTAL_CHARS
        for note in notes[:MAX_NOTES]:
            title = (note.title or "").strip() or "无标题"
            body = (note.content or "").strip()
            if body:
                body = body[:PER_NOTE_CHARS]
            part = f"### 笔记：{title}\n{body}\n"
            # 截断到总预算
            if len(part) > budget:
                part = part[:budget]
            parts.append(part)
            budget -= len(part)
            if budget <= 0:
                break
        return "\n".join(parts)

    def _parse_llm_json(self, raw: str) -> Any:
        """解析 LLM 输出的 JSON（容忍 markdown 代码块包裹）"""
        text = raw.strip()
        # 去掉 ```json ... ``` 代码块
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        # 提取第一个 [ 到最后一个 ]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        return json.loads(text)

    def _normalize_questions(self, raw_list: list[dict]) -> list[dict]:
        """校验并规整题目结构，保证每个字段都存在"""
        questions: list[dict] = []
        for i, q in enumerate(raw_list, start=1):
            qtype = q.get("type", "")
            base = {
                "id": f"q{i}",
                "type": qtype,
                "question": (q.get("question") or "").strip(),
                "explanation": (q.get("explanation") or "").strip(),
            }
            if qtype == "choice":
                options = q.get("options") or []
                # 只保留 4 个选项
                options = [str(o).strip() for o in options[:4]]
                if len(options) != 4:
                    continue
                answer = (q.get("answer") or "").strip().upper()
                if answer not in ("A", "B", "C", "D"):
                    continue
                base["options"] = options
                base["answer"] = answer
            elif qtype == "short":
                base["answer"] = (q.get("answer") or "").strip()
                base["key_points"] = [str(k).strip() for k in (q.get("key_points") or [])][:4]
                if not base["answer"]:
                    continue
            else:
                continue
            questions.append(base)
        return questions

    async def generate_quiz(
        self,
        db: Session,
        notebook_id: int,
        folder: str | None = None,
        count: int = DEFAULT_QUESTION_COUNT,
    ) -> Quiz:
        """
        生成一套自测题并持久化

        Args:
            notebook_id: 知识库 ID
            folder: 文件夹路径；None = 整个知识库
            count: 题目总数（默认 7 = 5 选择 + 2 简答）

        Returns:
            Quiz 对象（含完整题目与答案）

        Raises:
            ValueError: 范围内没有可出题的笔记 / LLM 输出解析失败
        """
        notes = self.collect_notes(db, notebook_id, folder)
        if not notes:
            raise ValueError("该范围内没有可出题的笔记")

        content = self._build_aggregated_content(notes)

        # 5 选择 + 2 简答（题目总数由 count 分配: 约 70% 选择 / 30% 简答）
        choice_count = max(1, round(count * 0.7))
        short_count = max(1, count - choice_count)

        user_prompt = GENERATE_USER_PROMPT.format(
            content=content,
            choice_count=choice_count,
            short_count=short_count,
        )
        raw = await llm_service.chat(
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=4096,
        )
        if not raw or raw.startswith("[错误]"):
            raise ValueError("AI 出题失败，请稍后重试")

        try:
            raw_list = self._parse_llm_json(raw)
            if not isinstance(raw_list, list):
                raise ValueError("LLM 输出不是数组")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"解析出题 JSON 失败: {e}\n{raw[:500]}")
            raise ValueError("AI 出题失败，请重试") from e

        questions = self._normalize_questions(raw_list)
        if not questions:
            raise ValueError("AI 生成题目格式不合法，请重试")

        quiz = Quiz(
            notebook_id=notebook_id,
            folder=folder,
            note_count=len(notes),
            questions_json=json.dumps(questions, ensure_ascii=False),
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        logger.info(
            f"生成测验 Quiz#{quiz.id}: 知识库 {notebook_id} "
            f"folder={folder or '(全部)'} 覆盖 {len(notes)} 篇笔记 → {len(questions)} 题"
        )
        return quiz

    # ============================================================
    # 批改
    # ============================================================
    def _grade_choice(self, q: dict, user_answer: str) -> dict:
        """选择题 exact match（选项字母，忽略大小写与前后空格）"""
        ua = (user_answer or "").strip().upper()
        correct = ua == q["answer"]
        return {
            "correct": correct,
            "user_answer": (user_answer or "").strip(),
            "answer": q["answer"],
            "explanation": q.get("explanation", ""),
            "comment": None,
        }

    async def _grade_short(self, q: dict, user_answer: str) -> dict:
        """简答题 — LLM 对比参考答案打分"""
        prompt = GRADE_USER_PROMPT.format(
            question=q.get("question", ""),
            answer=q.get("answer", ""),
            key_points="、".join(q.get("key_points") or []),
            user_answer=(user_answer or "").strip() or "（未作答）",
        )
        raw = await llm_service.chat(
            messages=[
                {"role": "system", "content": GRADE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        # LLM 失败 → 判为待复习，不阻塞整次批改
        if not raw or raw.startswith("[错误]"):
            logger.warning(f"批改简答题 {q['id']} 失败: {raw}")
            return {
                "correct": False,
                "user_answer": (user_answer or "").strip(),
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "comment": "AI 批改暂不可用，请对照参考答案自行检查",
            }
        try:
            result = self._parse_llm_json(raw)
            if not isinstance(result, dict):
                raise ValueError("不是对象")
            return {
                "correct": bool(result.get("correct")),
                "user_answer": (user_answer or "").strip(),
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "comment": str(result.get("comment") or ""),
                "score": int(result.get("score") or 0),
            }
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"解析批改 JSON 失败，原始输出: {raw[:300]}")
            return {
                "correct": False,
                "user_answer": (user_answer or "").strip(),
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "comment": "批改结果解析失败，请对照参考答案自行检查",
            }

    def _build_summary(self, results: list[dict], total: int, correct: int) -> str:
        """生成总体评价 + 复习建议（纯规则，不调 LLM）"""
        ratio = correct / total if total else 0
        if ratio >= 0.85:
            return "掌握得很扎实！继续保持，可以尝试更难的知识点。"
        if ratio >= 0.6:
            return "整体不错，但还有几个知识点需要巩固。建议重点复习做错的题目对应的笔记。"
        if ratio >= 0.4:
            return "需要加强复习。建议重读相关笔记，并针对错题做第二轮自测。"
        return "基础还不牢固，建议从头系统复习这部分笔记，再重新自测。"

    async def grade_quiz(
        self,
        db: Session,
        quiz_id: int,
        user_answers: list[dict],
    ) -> dict:
        """
        批改一套测验

        Args:
            quiz_id: Quiz 记录 ID
            user_answers: [{"question_id": "q1", "answer": "A"}, ...]

        Returns:
            grade 结果 dict（同时持久化到 Quiz.grade_json）
        """
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            raise ValueError("测验不存在")

        questions = json.loads(quiz.questions_json or "[]")
        answer_map = {
            a.get("question_id"): (a.get("answer") or "").strip()
            for a in user_answers
        }

        results: list[dict] = []
        for q in questions:
            ua = answer_map.get(q["id"], "")
            if q["type"] == "choice":
                result = self._grade_choice(q, ua)
            else:
                result = await self._grade_short(q, ua)
            # 每个结果带回 question_id，前端按题匹配
            result["question_id"] = q["id"]
            results.append(result)

        total = len(results)
        correct = sum(1 for r in results if r["correct"])
        # 简答按 correct 计；score 字段仅简答批改有（选择没有，前端可忽略）
        score = round(correct / total * 100, 1) if total else 0.0
        summary = self._build_summary(results, total, correct)

        grade = {
            "total": total,
            "correct": correct,
            "score": score,
            "summary": summary,
            "results": results,
        }
        quiz.grade_json = json.dumps(grade, ensure_ascii=False)
        db.commit()
        logger.info(f"批改测验 Quiz#{quiz_id}: {correct}/{total} 正确 (得分 {score})")
        return grade


# 服务单例
quiz_service = QuizService()
