"""
复习服务 — 温故知新
====================
SM-2 四档评分 + 掌握度 + 出题 + 批改 + 打卡 + 日历
"""

import json
import logging
from datetime import datetime, date, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.quiz import Quiz
from app.models.cluster import ConceptCluster, ClusterNote
from app.models.review import NoteReviewState, ReviewLog
from app.models.streak import UserStreak
from app.core.llm import llm_service

logger = logging.getLogger(__name__)

# ── 出题参数 ────────────────────────────────────────

MAX_NOTES = 15
PER_NOTE_CHARS = 500
MAX_TOTAL_CHARS = 8000

# 默认题量
DEFAULT_COUNT = 10
MAX_COUNT = 30

# ── Prompt 模板 ─────────────────────────────────────

GENERATE_CHOICE_SYSTEM = (
    "你是一位出题专家，擅长根据学习笔记出高质量选择题，帮助用户检验掌握程度。"
    "你只输出严格的 JSON，不输出任何其他文字。"
)

GENERATE_CHOICE_USER = """根据以下笔记内容，为用户生成一套自测题。

## 笔记内容
{content}

## 要求
生成 {count} 道单选题。每题必须标注来源笔记 ID（note_id 字段）。

严格按以下 JSON 数组格式输出（不要 markdown 代码块，不要前后缀文字）：
[
  {{"type":"choice","question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"...解析...","note_id": 1}}
]

规则：
- 单选题必须有 4 个选项，选项要有干扰性，答案只能是 A/B/C/D 中的一个字母
- note_id 必须是题目来源笔记的真实 ID（从上面的"笔记内容"里找）
- 题目应覆盖不同笔记，避免集中在某一篇
- 题目难度适中，重点考察笔记中的核心概念与易错点"""


# ── 掌握度分级（纯规则） ────────────────────────────

def mastery_level(state: NoteReviewState) -> str:
    """
    根据 SM-2 状态判定笔记掌握度

    🔴 new      — 尚未复习过
    🟡 learning — 刚开始复习，间隔短
    🟢 young    — 已有一定复习次数，进入中期记忆
    🔵 mature   — 长期记忆固化
    """
    if not state or state.repetitions == 0:
        return "new"
    interval = state.interval_days or 0
    if state.repetitions <= 2 and interval < 7:
        return "learning"
    if state.repetitions >= 5 and interval > 30:
        return "mature"
    return "young"


def mastery_emoji(level: str) -> str:
    return {"new": "🔴", "learning": "🟡", "young": "🟢", "mature": "🔵"}.get(level, "⚪")


def mastery_label(level: str) -> str:
    return {"new": "新学", "learning": "学习", "young": "初通", "mature": "熟练"}.get(level, "未知")


# ── ReviewService ───────────────────────────────────

class ReviewService:
    """复习调度 + 出题 + 批改 + 打卡"""

    # ============================================================
    # SM-2 四档评分算法
    # ============================================================

    def _sm2_update(self, state: NoteReviewState, rating: str) -> None:
        """
        SM-2 遗忘曲线更新（四档评分）

        rating: "again" | "hard" | "good" | "easy"

        - Again: 完全忘了/答错 → 重置间隔，惩罚 ease
        - Hard:  想了很久才答对 → 小幅延长，略降 ease
        - Good:  正常答对 → 标准 SM-2 增长
        - Easy:  秒答，滚瓜烂熟 → 加速延长，奖励 ease
        """
        state.last_review_at = datetime.utcnow()

        if rating == "again":
            state.repetitions = 0
            state.interval_days = 1
            state.ease_factor = max(1.3, state.ease_factor - 0.20)

        elif rating == "hard":
            state.interval_days = max(1, round(state.interval_days * 1.2))
            state.ease_factor = max(1.3, state.ease_factor - 0.15)
            state.repetitions += 1

        elif rating == "good":
            if state.repetitions == 0:
                state.interval_days = 1
            elif state.repetitions == 1:
                state.interval_days = 6
            else:
                state.interval_days = round(state.interval_days * state.ease_factor)
            state.repetitions += 1

        elif rating == "easy":
            state.ease_factor += 0.15
            if state.repetitions == 0:
                state.interval_days = 4
            elif state.repetitions == 1:
                state.interval_days = 10
            else:
                state.interval_days = round(
                    state.interval_days * state.ease_factor * 1.3
                )
            state.repetitions += 1

        else:
            logger.warning(f"未知评分: {rating}，fallback 为 good")
            return self._sm2_update(state, "good")

        state.next_review_at = datetime.utcnow() + timedelta(days=state.interval_days)

        logger.info(
            f"SM-2 更新 笔记#{state.note_id}: rating={rating} "
            f"→ interval={state.interval_days}d, reps={state.repetitions}, ef={state.ease_factor:.2f}"
        )

    # ── 兼容旧接口：用正确率推断评分（无 ratings 时 fallback） ──

    def _rating_from_scores(self, correct_count: int, total_count: int) -> str:
        """将旧的对错统计映射为四档评分"""
        if total_count == 0:
            return "good"
        rate = correct_count / total_count
        if rate >= 1.0:
            return "easy"
        if rate >= 0.75:
            return "good"
        if rate >= 0.4:
            return "hard"
        return "again"

    # ============================================================
    # 冷启动：新笔记导入时创建初始 SM-2 状态
    # ============================================================

    def ensure_review_state(self, db: Session, note_id: int) -> NoteReviewState:
        """
        确保笔记有 SM-2 状态记录（新笔记 next_review_at=NOW() = 立即可复习）
        """
        state = db.query(NoteReviewState).filter_by(note_id=note_id).first()
        if not state:
            state = NoteReviewState(
                note_id=note_id,
                ease_factor=2.5,
                interval_days=0,
                repetitions=0,
                next_review_at=datetime.utcnow(),  # 立即到期
            )
            db.add(state)
            db.commit()
            db.refresh(state)
            logger.info(f"笔记 {note_id} SM-2 状态初始化（立即到期）")
        return state

    # ============================================================
    # 掌握度聚合
    # ============================================================

    def cluster_mastery(self, db: Session, cluster_id: int) -> dict:
        """统计簇内各掌握度等级的笔记数量"""
        cluster_notes = db.query(ClusterNote).filter_by(cluster_id=cluster_id).all()
        if not cluster_notes:
            return {"new": 0, "learning": 0, "young": 0, "mature": 0, "total": 0}

        note_ids = [cn.note_id for cn in cluster_notes]
        states = db.query(NoteReviewState).filter(
            NoteReviewState.note_id.in_(note_ids)
        ).all()
        state_map = {s.note_id: s for s in states}

        counts = {"new": 0, "learning": 0, "young": 0, "mature": 0}
        for nid in note_ids:
            s = state_map.get(nid)
            level = mastery_level(s) if s else "new"
            counts[level] += 1

        counts["total"] = len(note_ids)
        return counts

    # ============================================================
    # 到期查询（按簇分组）
    # ============================================================

    def get_due_reviews(self, db: Session, notebook_id: int) -> dict:
        """
        获取今日到期的笔记，按簇分组。
        """
        now = datetime.utcnow()
        due_states = (
            db.query(NoteReviewState)
            .filter(
                NoteReviewState.next_review_at <= now,
                NoteReviewState.next_review_at.isnot(None),
            )
            .all()
        )

        if not due_states:
            return {"clusters": [], "orphans": [], "total_due": 0}

        note_ids = [s.note_id for s in due_states]
        notes = db.query(Note).filter(
            Note.id.in_(note_ids),
            Note.notebook_id == notebook_id,
            Note.deleted_at.is_(None),
        ).all()
        note_map = {n.id: n for n in notes}
        state_map = {s.note_id: s for s in due_states}

        cluster_notes = (
            db.query(ClusterNote).filter(ClusterNote.note_id.in_(note_ids)).all()
        )
        clusters = (
            db.query(ConceptCluster)
            .filter_by(notebook_id=notebook_id)
            .filter(ConceptCluster.note_count > 0)
            .all()
        )
        cluster_map = {c.id: c for c in clusters}

        note_to_cluster: dict[int, int] = {}
        for cn in cluster_notes:
            if cn.note_id in note_to_cluster:
                continue
            note_to_cluster[cn.note_id] = cn.cluster_id

        cluster_groups: dict[int, list[dict]] = defaultdict(list)
        orphan_notes: list[dict] = []

        for state in due_states:
            note = note_map.get(state.note_id)
            if not note:
                continue
            item = {
                "note_id": state.note_id,
                "note_title": note.title or "无标题",
                "state": state.to_dict(),
                "mastery": mastery_level(state),
            }
            cid = note_to_cluster.get(state.note_id)
            if cid is not None and cid in cluster_map:
                cluster_groups[cid].append(item)
            else:
                orphan_notes.append(item)

        cluster_list = []
        for cid, notes_in_cluster in cluster_groups.items():
            c = cluster_map[cid]
            cluster_list.append({
                "cluster_id": c.id,
                "cluster_name": c.name,
                "note_count": c.note_count,
                "due_count": len(notes_in_cluster),
                "notes": notes_in_cluster,
            })

        cluster_list.sort(key=lambda x: x["due_count"], reverse=True)

        return {
            "clusters": cluster_list,
            "orphans": orphan_notes,
            "total_due": len([s for s in due_states if s.note_id in note_map]),
        }

    # ============================================================
    # 出题（支持四种 scope 模式）
    # ============================================================

    def _collect_notes_for_scope(
        self,
        db: Session,
        cluster_id: int,
        scope: str = "due",
    ) -> list[Note]:
        """
        根据 scope 收集笔记：
        - due:    仅到期笔记（SM-2 调度）
        - all:    簇内全部笔记（集中突击）
        - errors: 该簇历史答错的笔记（错题重温）
        - new:    从未复习过的笔记（新知初探）
        """
        cluster = db.query(ConceptCluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise ValueError("簇不存在")

        cluster_notes = db.query(ClusterNote).filter_by(cluster_id=cluster_id).all()
        all_note_ids = [cn.note_id for cn in cluster_notes]
        if not all_note_ids:
            raise ValueError("该簇下没有笔记")

        if scope == "due":
            now = datetime.utcnow()
            due_states = (
                db.query(NoteReviewState)
                .filter(
                    NoteReviewState.note_id.in_(all_note_ids),
                    NoteReviewState.next_review_at <= now,
                    NoteReviewState.next_review_at.isnot(None),
                )
                .all()
            )
            due_ids = {s.note_id for s in due_states}
            target_ids = [nid for nid in all_note_ids if nid in due_ids]
            if not target_ids:
                raise ValueError("该簇暂无到期笔记")

        elif scope == "all":
            target_ids = all_note_ids

        elif scope == "errors":
            # 查找该簇历史 ReviewLog 中正确率 < 100% 的笔记
            logs = (
                db.query(ReviewLog)
                .filter(
                    ReviewLog.note_id.in_(all_note_ids),
                    ReviewLog.correct_count < ReviewLog.total_count,
                )
                .all()
            )
            error_ids = {log.note_id for log in logs}
            target_ids = [nid for nid in all_note_ids if nid in error_ids]
            if not target_ids:
                raise ValueError("该簇暂无错题记录")

        elif scope == "new":
            # 从未复习过的笔记
            states = (
                db.query(NoteReviewState)
                .filter(NoteReviewState.note_id.in_(all_note_ids))
                .all()
            )
            reviewed_ids = {s.note_id for s in states if s.repetitions > 0}
            target_ids = [nid for nid in all_note_ids if nid not in reviewed_ids]
            if not target_ids:
                raise ValueError("该簇没有新笔记")

        else:
            raise ValueError(f"未知 scope: {scope}")

        notes = db.query(Note).filter(
            Note.id.in_(target_ids),
            Note.deleted_at.is_(None),
        ).order_by(Note.updated_at.desc()).all()

        if not notes:
            raise ValueError("该范围内没有可出题的笔记")

        return notes

    def _build_aggregated_content_with_ids(self, notes: list[Note]) -> tuple[str, dict[int, str]]:
        """聚合笔记内容，返回 (文本, {note_id: title})"""
        parts: list[str] = []
        id_to_title: dict[int, str] = {}
        budget = MAX_TOTAL_CHARS
        for note in notes[:MAX_NOTES]:
            title = (note.title or "").strip() or "无标题"
            body = (note.content or "").strip()
            if body:
                body = body[:PER_NOTE_CHARS]
            part = f"### 笔记 {note.id}：{title}\n{body}\n"
            if len(part) > budget:
                part = part[:budget]
            parts.append(part)
            id_to_title[note.id] = title
            budget -= len(part)
            if budget <= 0:
                break
        return "\n".join(parts), id_to_title

    def _parse_llm_json(self, raw: str):
        """解析 LLM 输出的 JSON（容忍 markdown 代码块包裹）"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
        return json.loads(text)

    def _normalize_choice_questions(self, raw_list: list[dict], valid_note_ids: set[int]) -> list[dict]:
        """校验选择题，保留 note_id"""
        questions: list[dict] = []
        for i, q in enumerate(raw_list, start=1):
            if q.get("type") != "choice":
                continue
            options = q.get("options") or []
            options = [str(o).strip() for o in options[:4]]
            if len(options) != 4:
                continue
            answer = (q.get("answer") or "").strip().upper()
            if answer not in ("A", "B", "C", "D"):
                continue
            note_id = q.get("note_id")
            try:
                note_id = int(note_id)
            except (TypeError, ValueError):
                note_id = None
            if note_id not in valid_note_ids:
                continue
            questions.append({
                "id": f"q{i}",
                "type": "choice",
                "question": (q.get("question") or "").strip(),
                "options": options,
                "answer": answer,
                "explanation": (q.get("explanation") or "").strip(),
                "note_id": note_id,
            })
        return questions

    async def generate_review_quiz(
        self,
        db: Session,
        cluster_id: int,
        scope: str = "due",
        count: int = DEFAULT_COUNT,
    ) -> Quiz:
        """
        从指定簇生成复习测验

        Args:
            cluster_id: 概念簇 ID
            scope: "due" | "all" | "errors" | "new"
            count: 题目数量（优先级低于 scope 的可用笔记数）
        """
        count = max(5, min(count, MAX_COUNT))
        cluster = db.query(ConceptCluster).filter_by(id=cluster_id).first()
        if not cluster:
            raise ValueError("簇不存在")

        notes = self._collect_notes_for_scope(db, cluster_id, scope)

        content, id_to_title = self._build_aggregated_content_with_ids(notes)

        user_prompt = GENERATE_CHOICE_USER.format(
            content=content,
            count=min(count, len(notes) * 5),  # 最多每篇出5题
        )
        raw = await llm_service.chat(
            messages=[
                {"role": "system", "content": GENERATE_CHOICE_SYSTEM},
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

        valid_note_ids = {n.id for n in notes}
        questions = self._normalize_choice_questions(raw_list, valid_note_ids)
        if not questions:
            raise ValueError("AI 生成题目格式不合法，请重试")

        for q in questions:
            q["note_title"] = id_to_title.get(q["note_id"], "未知笔记")

        quiz = Quiz(
            notebook_id=cluster.notebook_id,
            folder=None,
            note_count=len(notes),
            questions_json=json.dumps(questions, ensure_ascii=False),
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        scope_labels = {"due": "到期复习", "all": "集中突击", "errors": "错题重温", "new": "新知初探"}
        logger.info(
            f"生成测验 Quiz#{quiz.id}: 簇「{cluster.name}」"
            f" {scope_labels.get(scope, scope)} → {len(questions)} 题"
        )
        return quiz

    # ============================================================
    # 批改 + SM-2 更新 + ReviewLog + 打卡
    # ============================================================

    async def grade_review_quiz(
        self,
        db: Session,
        quiz_id: int,
        user_answers: list[dict],
        ratings: list[dict] | None = None,
    ) -> dict:
        """
        批改复习测验：
        1. 选择题 exact match
        2. 按笔记汇总正确率
        3. 用 ratings（或推导）更新 SM-2
        4. 写入 ReviewLog
        5. 更新打卡
        """
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            raise ValueError("测验不存在")

        questions = json.loads(quiz.questions_json or "[]")
        answer_map = {
            a.get("question_id"): (a.get("answer") or "").strip().upper()
            for a in user_answers
        }

        # ── 批改每道题 ──
        results = []
        for q in questions:
            ua = answer_map.get(q["id"], "")
            correct = ua == q.get("answer", "").upper()
            results.append({
                "question_id": q["id"],
                "correct": correct,
                "user_answer": ua,
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "note_id": q.get("note_id"),
                "note_title": q.get("note_title", ""),
            })

        # ── 按笔记汇总正确率 ──
        note_stats: dict[int, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
        for r in results:
            nid = r["note_id"]
            if nid is not None:
                note_stats[nid]["correct"] += 1 if r["correct"] else 0
                note_stats[nid]["total"] += 1

        # ── 构建评分映射 ──
        rating_map: dict[int, str] = {}
        if ratings:
            for r in ratings:
                nid = r.get("note_id")
                rating = r.get("rating", "").lower()
                if nid is not None and rating in ("again", "hard", "good", "easy"):
                    rating_map[nid] = rating

        # ── 更新 SM-2 + 写 ReviewLog ──
        updated_states: list[dict] = []
        for nid, stats in note_stats.items():
            state = db.query(NoteReviewState).filter_by(note_id=nid).first()
            if not state:
                state = self.ensure_review_state(db, nid)

            old_interval = state.interval_days
            old_level = mastery_level(state)

            # 确定评分：优先用用户自评，否则用正确率推导
            rating = rating_map.get(nid)
            if rating is None:
                rating = self._rating_from_scores(stats["correct"], stats["total"])

            self._sm2_update(state, rating)
            db.add(state)

            new_level = mastery_level(state)

            # 写 ReviewLog（含评分）
            log = ReviewLog(
                note_id=nid,
                cluster_id=None,
                quiz_id=quiz_id,
                correct_count=stats["correct"],
                total_count=stats["total"],
                rating=rating,
            )
            db.add(log)

            updated_states.append({
                "note_id": nid,
                "correct": f"{stats['correct']}/{stats['total']}",
                "rating": rating,
                "old_interval": old_interval,
                "new_interval": state.interval_days,
                "next_review_at": state.next_review_at.isoformat() if state.next_review_at else None,
                "mastery_before": old_level,
                "mastery_after": new_level,
            })

        # ── 保存错题 ──
        from app.models.wrong_question import WrongQuestion
        cn_map_wq: dict[int, int] = {}
        all_nids_wq = list(note_stats.keys())
        if all_nids_wq:
            cns_wq = db.query(ClusterNote).filter(ClusterNote.note_id.in_(all_nids_wq)).all()
            for cn in cns_wq:
                if cn.note_id not in cn_map_wq:
                    cn_map_wq[cn.note_id] = cn.cluster_id
        questions_raw = json.loads(quiz.questions_json or "[]")
        for r in results:
            if not r["correct"]:
                q_src = next((q for q in questions_raw if q.get("id") == r["question_id"]), None)
                if q_src:
                    wq = WrongQuestion(
                        notebook_id=quiz.notebook_id,
                        note_id=r.get("note_id") or 0,
                        cluster_id=cn_map_wq.get(r.get("note_id")),
                        quiz_id=quiz_id,
                        question_json=json.dumps(q_src, ensure_ascii=False),
                        user_answer=r["user_answer"],
                    )
                    db.add(wq)

        db.commit()

        # ── 更新打卡 ──
        self._update_streak(db, quiz.notebook_id)

        # ── 总体统计 ──
        total = len(results)
        correct_total = sum(1 for r in results if r["correct"])
        score = round(correct_total / total * 100, 1) if total else 0.0
        summary = self._build_review_summary(correct_total, total)

        grade = {
            "total": total,
            "correct": correct_total,
            "score": score,
            "summary": summary,
            "results": results,
            "updated_states": updated_states,
        }
        quiz.grade_json = json.dumps(grade, ensure_ascii=False)
        db.commit()
        logger.info(
            f"批改测验 Quiz#{quiz_id}: {correct_total}/{total} 正确 ({score}%), "
            f"更新 {len(updated_states)} 篇笔记 SM-2 状态"
        )
        return grade

    def _build_review_summary(self, correct: int, total: int) -> str:
        """复习评价"""
        ratio = correct / total if total else 0
        if ratio >= 0.85:
            return "掌握得很扎实！所有笔记的复习间隔已延长。"
        if ratio >= 0.6:
            return "整体不错。答错的题目对应的笔记会安排近期重新复习。"
        if ratio >= 0.4:
            return "需要加强复习。答错的笔记已重置为 1 天后复习。"
        return "基础还不牢固。所有相关笔记已重置为 1 天后复习，建议重读后再测。"

    # ============================================================
    # 打卡
    # ============================================================

    def _update_streak(self, db: Session, notebook_id: int) -> None:
        """测验批改完成后更新连续打卡"""
        streak = db.query(UserStreak).filter_by(notebook_id=notebook_id).first()
        if not streak:
            streak = UserStreak(notebook_id=notebook_id, current_streak=0, longest_streak=0)
            db.add(streak)

        today = date.today()

        if streak.last_review_date is None:
            streak.current_streak = 1
        elif streak.last_review_date == today:
            pass  # 今天已打过卡，不重复
        elif streak.last_review_date == today - timedelta(days=1):
            streak.current_streak += 1  # 连续
        else:
            streak.current_streak = 1  # 断开，重新开始

        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_review_date = today
        db.commit()
        logger.info(
            f"打卡更新 笔记库#{notebook_id}: streak={streak.current_streak}, "
            f"longest={streak.longest_streak}"
        )

    def get_streak(self, db: Session, notebook_id: int) -> dict:
        """获取打卡状态"""
        streak = db.query(UserStreak).filter_by(notebook_id=notebook_id).first()
        if not streak:
            return {"current_streak": 0, "longest_streak": 0, "last_review_date": None}
        return streak.to_dict()

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self, db: Session, notebook_id: int) -> dict:
        """聚合统计数据"""
        states = (
            db.query(NoteReviewState)
            .join(Note, NoteReviewState.note_id == Note.id)
            .filter(Note.notebook_id == notebook_id, Note.deleted_at.is_(None))
            .all()
        )
        by_mastery = {"new": 0, "learning": 0, "young": 0, "mature": 0}
        for s in states:
            by_mastery[mastery_level(s)] += 1
        total = sum(by_mastery.values())

        # 最近 7 天复习量
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = (
            db.query(ReviewLog)
            .filter(ReviewLog.created_at >= week_ago)
            .all()
        )
        reviewed_note_ids = set(log.note_id for log in recent_logs)
        notes_in_nb = db.query(Note).filter(
            Note.notebook_id == notebook_id, Note.deleted_at.is_(None)
        ).all()
        nb_note_ids = {n.id for n in notes_in_nb}
        recent_review_count = len(reviewed_note_ids & nb_note_ids)

        # 簇排行
        clusters = db.query(ConceptCluster).filter_by(notebook_id=notebook_id).all()
        cluster_list = []
        for c in clusters:
            m = self.cluster_mastery(db, c.id)
            cluster_list.append({
                "id": c.id, "name": c.name, "note_count": c.note_count,
                "mastery": m,
                "mastered_pct": round(((m["young"] + m["mature"]) / max(m["total"], 1)) * 100),
            })
        cluster_list.sort(key=lambda x: x["mastered_pct"])

        return {
            "total_notes": total,
            "by_mastery": by_mastery,
            "recent_reviews_7d": recent_review_count,
            "clusters": cluster_list,
        }

    # ============================================================
    # 错题管理
    # ============================================================

    def get_wrong_questions(self, db: Session, notebook_id: int,
                            cluster_id: int | None = None,
                            limit: int = 50) -> list[dict]:
        """获取未重温的错题"""
        from app.models.wrong_question import WrongQuestion
        q = db.query(WrongQuestion).filter_by(notebook_id=notebook_id, reviewed=False)
        if cluster_id is not None:
            q = q.filter_by(cluster_id=cluster_id)
        wqs = q.order_by(WrongQuestion.created_at.desc()).limit(limit).all()
        return [wq.to_dict() for wq in wqs]

    def mark_wrong_reviewed(self, db: Session, ids: list[int]) -> int:
        """标记错题已重温"""
        from app.models.wrong_question import WrongQuestion
        count = db.query(WrongQuestion).filter(WrongQuestion.id.in_(ids)).update(
            {"reviewed": True}, synchronize_session=False
        )
        db.commit()
        return count

    # ============================================================
    # 自由出题（不计入 SM-2）
    # ============================================================

    async def generate_free_quiz(
        self,
        db: Session,
        notebook_id: int,
        cluster_id: int | None = None,
        folder: str | None = None,
        count: int = 10,
    ) -> Quiz:
        """自由出题模式（不计入 SM-2）"""
        if cluster_id is not None:
            cluster = db.query(ConceptCluster).filter_by(id=cluster_id).first()
            if not cluster:
                raise ValueError("簇不存在")
            cluster_notes = db.query(ClusterNote).filter_by(cluster_id=cluster_id).all()
            note_ids = [cn.note_id for cn in cluster_notes]
            notes = db.query(Note).filter(
                Note.id.in_(note_ids),
                Note.deleted_at.is_(None),
            ).all()
        else:
            from app.services.quiz_service import quiz_service as qs
            notes = qs.collect_notes(db, notebook_id, folder)

        if not notes:
            raise ValueError("该范围内没有可出题的笔记")

        content, id_to_title = self._build_aggregated_content_with_ids(notes)

        user_prompt = GENERATE_CHOICE_USER.format(content=content, count=count)
        raw = await llm_service.chat(
            messages=[
                {"role": "system", "content": GENERATE_CHOICE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=4096,
        )
        if not raw or raw.startswith("[错误]"):
            raise ValueError("AI 出题失败")

        raw_list = self._parse_llm_json(raw)
        valid_note_ids = {n.id for n in notes}
        questions = self._normalize_choice_questions(raw_list, valid_note_ids)
        for q in questions:
            q["note_title"] = id_to_title.get(q["note_id"], "未知笔记")

        quiz = Quiz(
            notebook_id=notebook_id,
            folder=folder,
            note_count=len(notes),
            questions_json=json.dumps(questions, ensure_ascii=False),
        )
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        return quiz

    async def grade_free_quiz(
        self,
        db: Session,
        quiz_id: int,
        user_answers: list[dict],
    ) -> dict:
        """自由出题批改（不更新 SM-2，不打卡）"""
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz:
            raise ValueError("测验不存在")

        questions = json.loads(quiz.questions_json or "[]")
        answer_map = {
            a.get("question_id"): (a.get("answer") or "").strip().upper()
            for a in user_answers
        }

        results = []
        for q in questions:
            ua = answer_map.get(q["id"], "")
            correct = ua == q.get("answer", "").upper()
            results.append({
                "question_id": q["id"],
                "correct": correct,
                "user_answer": ua,
                "answer": q.get("answer", ""),
                "explanation": q.get("explanation", ""),
                "note_id": q.get("note_id"),
                "note_title": q.get("note_title", ""),
            })

        total = len(results)
        correct_total = sum(1 for r in results if r["correct"])
        score = round(correct_total / total * 100, 1) if total else 0.0
        summary = self._build_review_summary(correct_total, total)

        grade = {
            "total": total,
            "correct": correct_total,
            "score": score,
            "summary": summary,
            "results": results,
        }
        quiz.grade_json = json.dumps(grade, ensure_ascii=False)
        db.commit()
        return grade


# 全局单例
review_service = ReviewService()
