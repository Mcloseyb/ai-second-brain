/**
 * 温故知新页面 — 学迹 (LearnTrace) V2
 * ============================================
 * 概念簇语义聚类 + SM-2 四档评分 + 四种复习模式 + 连续打卡 + 交互日历
 */

import { useEffect, useState, useCallback, Fragment } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotesStore } from '@/stores/notes'
import { reviewApi, notebooksApi } from '@/lib/api'
import type {
  ClusterInfo, ClusterDetail, DueReviewsResponse, ReviewGenerateResponse,
  ReviewGradeResponse, QuizAttempt, StreakInfo, CalendarDayDetail, Notebook,
} from '@/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Brain, RefreshCw, BookOpen, Calendar, ChevronRight,
  CheckCircle2, XCircle, Target, Loader2, Flame, Zap,
  Sparkles, AlertCircle,
} from 'lucide-react'

// ── 常量 ───────────────────────────────────────────

const MASTERY_EMOJI: Record<string, string> = { new: '🔴', learning: '🟡', young: '🟢', mature: '🔵' }
const MASTERY_LABEL: Record<string, string> = { new: '新学', learning: '学习', young: '初通', mature: '熟练' }
const SCOPE_LABELS: Record<string, { icon: JSX.Element; label: string }> = {
  due: { icon: <BookOpen className="size-3" />, label: '到期复习' },
  all: { icon: <Zap className="size-3" />, label: '集中突击' },
  errors: { icon: <AlertCircle className="size-3" />, label: '错题重温' },
  new: { icon: <Sparkles className="size-3" />, label: '新知初探' },
}
const RATING_OPTIONS = [
  { key: 'again', emoji: '🔴', label: 'Again', hint: '完全忘记' },
  { key: 'hard', emoji: '🟠', label: 'Hard', hint: '想了很久' },
  { key: 'good', emoji: '🟢', label: 'Good', hint: '正常答对' },
  { key: 'easy', emoji: '🔵', label: 'Easy', hint: '秒答' },
] as const

// ── 主组件 ───────────────────────────────────────

export default function ReviewPage() {
  const navigate = useNavigate()
  const activeNotebookId = useNotesStore((s) => s.activeNotebookId)

  // 数据状态
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [selectedNbId, setSelectedNbId] = useState<number | null>(null)
  const [clusters, setClusters] = useState<ClusterInfo[]>([])
  const [dueData, setDueData] = useState<DueReviewsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [reclustering, setReclustering] = useState(false)
  const [streak, setStreak] = useState<StreakInfo | null>(null)

  // 选中簇
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null)
  const [clusterDetail, setClusterDetail] = useState<ClusterDetail | null>(null)

  // 测验状态
  const [quizScope, setQuizScope] = useState<string>('due')
  const [quizId, setQuizId] = useState<number | null>(null)
  const [questions, setQuestions] = useState<ReviewGenerateResponse['questions']>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [generating, setGenerating] = useState(false)
  const [grade, setGrade] = useState<ReviewGradeResponse | null>(null)

  // 四档评分
  const [noteRatings, setNoteRatings] = useState<Record<number, string>>({})
  const [ratingsSubmitted, setRatingsSubmitted] = useState(false)

  // 日历弹出
  const [dayDetail, setDayDetail] = useState<CalendarDayDetail | null>(null)
  const [dayPopoverDate, setDayPopoverDate] = useState<string | null>(null)
  const [dayLoading, setDayLoading] = useState(false)

  // 错误提示
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const showError = (msg: string) => { setErrorMsg(msg); setTimeout(() => setErrorMsg(null), 4000) }

  // ── 初始化：加载笔记本列表 ─────────────────────

  useEffect(() => {
    notebooksApi.list().then(res => {
      const nbs = res.notebooks || []
      setNotebooks(nbs)
      // 优先用 store 里已选中的，否则用第一个
      const storeId = useNotesStore.getState().activeNotebookId
      const targetId = storeId ?? (nbs.length > 0 ? nbs[0].id : null)
      if (targetId && targetId !== selectedNbId) {
        setSelectedNbId(targetId)
      }
    }).catch(e => showError('加载知识库列表失败: ' + (e?.message || '')))
  }, [])

  // ── 加载数据 ───────────────────────────────────

  const loadReviewData = useCallback(async (nbId: number) => {
    setLoading(true)
    try {
      const [cRes, dRes, sRes] = await Promise.all([
        reviewApi.clusters(nbId),
        reviewApi.due(nbId),
        reviewApi.streak(nbId),
      ])
      setClusters(cRes.clusters || [])
      setDueData(dRes)
      setStreak(sRes)
    } catch (e: any) {
      showError('加载失败: ' + (e?.message || '网络错误'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedNbId) loadReviewData(selectedNbId)
  }, [selectedNbId, loadReviewData])

  // ── 切换知识库 ─────────────────────────────────

  const switchNotebook = (nbId: number) => {
    setSelectedNbId(nbId)
    setSelectedClusterId(null)
    setClusterDetail(null)
    // 同步到 store
    useNotesStore.getState().setActiveNotebook(nbId)
  }

  // ── 选中簇 ─────────────────────────────────────

  const selectCluster = async (clusterId: number) => {
    setSelectedClusterId(clusterId)
    try {
      const detail = await reviewApi.clusterDetail(clusterId)
      setClusterDetail(detail)
    } catch (e: any) {
      showError('加载簇详情失败: ' + (e?.message || '网络错误'))
    }
  }

  // ── 重聚类 ─────────────────────────────────────

  const handleRecluster = async () => {
    if (!selectedNbId) {
      showError('请先选择知识库')
      return
    }
    if (reclustering) return
    setReclustering(true)
    setErrorMsg(null)
    try {
      await reviewApi.recluster(selectedNbId)
      await loadReviewData(selectedNbId)
      setSelectedClusterId(null)
      setClusterDetail(null)
    } catch (e: any) {
      showError('重聚类失败: ' + (e?.message || '网络错误'))
    } finally {
      setReclustering(false)
    }
  }

  // ── 开始测验 ───────────────────────────────────

  const startQuiz = async (clusterId: number, scope: string = 'due', count: number = 10) => {
    setGenerating(true)
    setGrade(null)
    setAnswers({})
    setNoteRatings({})
    setRatingsSubmitted(false)
    setQuizScope(scope)
    try {
      const res = await reviewApi.generate(clusterId, scope, count)
      setQuizId(res.quiz_id)
      setQuestions(res.questions)
    } catch (e) {
      console.error('生成测验失败:', e)
    } finally {
      setGenerating(false)
    }
  }

  // ── 提交答案 ───────────────────────────────────

  const submitAnswers = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(
      ([question_id, answer]) => ({ question_id, answer })
    )
    try {
      const res = await reviewApi.grade(quizId, attempts)
      setGrade(res)
    } catch (e) {
      console.error('批改失败:', e)
    }
  }

  // ── 提交评分 ───────────────────────────────────

  const submitRatings = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(
      ([question_id, answer]) => ({ question_id, answer })
    )
    const ratings = Object.entries(noteRatings).map(([noteId, rating]) => ({
      note_id: Number(noteId),
      rating,
    }))
    try {
      const res = await reviewApi.grade(quizId, attempts, ratings)
      setGrade(res)
      setRatingsSubmitted(true)
      // 刷新数据和打卡
      if (selectedNbId) await loadReviewData(selectedNbId)
    } catch (e) {
      console.error('提交评分失败:', e)
    }
  }

  // ── 返回列表 ───────────────────────────────────

  const backToList = () => {
    setQuizId(null)
    setQuestions([])
    setAnswers({})
    setGrade(null)
    setNoteRatings({})
    setRatingsSubmitted(false)
    if (selectedNbId) loadReviewData(selectedNbId)
  }

  // ── 日历点击 ───────────────────────────────────

  const handleDayClick = async (dateStr: string) => {
    if (!selectedNbId) return
    if (dayPopoverDate === dateStr) {
      setDayPopoverDate(null)
      setDayDetail(null)
      return
    }
    setDayPopoverDate(dateStr)
    setDayLoading(true)
    try {
      const detail = await reviewApi.calendarDay(selectedNbId, dateStr)
      setDayDetail(detail)
    } catch (e) {
      console.error('加载日历详情失败:', e)
    } finally {
      setDayLoading(false)
    }
  }

  // ── 渲染 ───────────────────────────────────────

  const hasQuiz = questions.length > 0

  return (
    <div className="flex h-full gap-4">
      {/* ========== 左侧簇列表 ========== */}
      <aside className="w-[240px] shrink-0 border-r pr-2 flex flex-col">
        <div className="flex items-center justify-between mb-2 px-1">
          <h2 className="font-semibold text-sm flex items-center gap-2">
            <Brain className="size-4" /> 概念簇
          </h2>
          <Button
            variant="ghost" size="sm" className="h-7 text-xs"
            onClick={handleRecluster} disabled={reclustering}
          >
            <RefreshCw className={`size-3 ${reclustering ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {clusters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm px-2">
              <Brain className="size-8 mx-auto mb-2 opacity-30" />
              {loading ? '加载中...' : '暂无概念簇，请先导入笔记后聚类'}
            </div>
          ) : (
            <div className="space-y-0.5">
              {clusters.map((c) => {
                const dueInfo = dueData?.clusters?.find(d => d.cluster_id === c.id)
                const dueCount = dueInfo?.due_count || 0
                const mastery = c.mastery
                const selected = selectedClusterId === c.id
                return (
                  <button
                    key={c.id}
                    onClick={() => selectCluster(c.id)}
                    className={`w-full text-left px-2 py-2 rounded-md text-sm transition-colors
                      ${selected ? 'bg-primary/10 border border-primary/30' : 'hover:bg-accent border border-transparent'}
                    `}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium truncate text-xs">{c.name}</span>
                      <div className="flex items-center gap-1 shrink-0">
                        {dueCount > 0 && (
                          <Badge variant="default" className="text-[10px] h-4 px-1 leading-none">
                            {dueCount}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {mastery && mastery.total > 0 && (
                      <div className="flex items-center gap-1 mt-1">
                        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden flex">
                          {mastery.new > 0 && <div className="bg-red-400 h-full" style={{ width: `${(mastery.new / mastery.total) * 100}%` }} />}
                          {mastery.learning > 0 && <div className="bg-amber-400 h-full" style={{ width: `${(mastery.learning / mastery.total) * 100}%` }} />}
                          {mastery.young > 0 && <div className="bg-green-400 h-full" style={{ width: `${(mastery.young / mastery.total) * 100}%` }} />}
                          {mastery.mature > 0 && <div className="bg-blue-400 h-full" style={{ width: `${(mastery.mature / mastery.total) * 100}%` }} />}
                        </div>
                        <span className="text-[10px] text-muted-foreground">{c.note_count}篇</span>
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </ScrollArea>
        <div className="pt-2 border-t">
          <Button variant="outline" size="sm" className="w-full text-xs h-7"
            onClick={handleRecluster} disabled={reclustering}>
            <RefreshCw className={`size-3 mr-1 ${reclustering ? 'animate-spin' : ''}`} />
            {reclustering ? '聚类中...' : '重聚类'}
          </Button>
        </div>
      </aside>

      {/* ========== 右侧内容区 ========== */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* 知识库选择器 + 错误提示 */}
        <div className="px-1 pt-2 pb-1 flex items-center gap-2 flex-wrap">
          <label className="text-xs text-muted-foreground shrink-0">知识库:</label>
          <select
            className="border rounded-md px-2 py-1 text-xs bg-background max-w-[180px]"
            value={selectedNbId ?? ''}
            onChange={(e) => {
              const id = Number(e.target.value)
              if (id) switchNotebook(id)
            }}
          >
            {notebooks.length === 0 && (
              <option value="">无可用知识库</option>
            )}
            {notebooks.map((nb) => (
              <option key={nb.id} value={nb.id}>{nb.name}</option>
            ))}
          </select>
          {selectedNbId && notebooks.length > 0 && (
            <span className="text-[10px] text-muted-foreground">
              ({notebooks.find(n => n.id === selectedNbId)?.note_count || 0} 篇笔记)
            </span>
          )}
        </div>
        {errorMsg && (
          <div className="mx-1 mb-1 px-3 py-2 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-md text-sm text-red-700 dark:text-red-400 flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{errorMsg}</span>
            <button className="ml-auto shrink-0 hover:opacity-70" onClick={() => setErrorMsg(null)}>✕</button>
          </div>
        )}
        <ScrollArea className="flex-1">
          {hasQuiz ? (
            /* ─── 测验界面 ─── */
            <QuizPanel
              questions={questions}
              answers={answers}
              setAnswers={setAnswers}
              grade={grade}
              generating={generating}
              noteRatings={noteRatings}
              setNoteRatings={setNoteRatings}
              ratingsSubmitted={ratingsSubmitted}
              onSubmit={submitAnswers}
              onSubmitRatings={submitRatings}
              onBack={backToList}
              onRetry={() => startQuiz(selectedClusterId!, quizScope)}
              scope={quizScope}
            />
          ) : (
            /* ─── 浏览界面 ─── */
            <div className="space-y-4 max-w-3xl pr-2">
              {/* 🔥 打卡 + 📅 迷你日历 */}
              <TopBar
                streak={streak}
                notebookId={selectedNbId}
                onDayClick={handleDayClick}
                dayPopoverDate={dayPopoverDate}
                dayDetail={dayDetail}
                dayLoading={dayLoading}
              />

              <Separator />

              {clusterDetail ? (
                /* ─── 簇详情 ─── */
                <ClusterDetailPanel
                  detail={clusterDetail}
                  dueData={dueData}
                  onStartQuiz={(scope) => startQuiz(clusterDetail.id, scope)}
                  generating={generating}
                />
              ) : (
                /* ─── 默认：今日待复习 ─── */
                <TodayDuePanel
                  dueData={dueData}
                  clusters={clusters}
                  onSelectCluster={selectCluster}
                  onStartQuiz={startQuiz}
                  generating={generating}
                />
              )}
            </div>
          )}
        </ScrollArea>
      </main>
    </div>
  )
}

// ── 顶部栏：打卡 + 日历 ──────────────────────────

function TopBar({
  streak, notebookId, onDayClick,
  dayPopoverDate, dayDetail, dayLoading,
}: {
  streak: StreakInfo | null
  notebookId: number | null
  onDayClick: (date: string) => void
  dayPopoverDate: string | null
  dayDetail: CalendarDayDetail | null
  dayLoading: boolean
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      {/* 打卡 */}
      <div className="flex items-center gap-2 text-sm">
        <Flame className={`size-4 ${(streak?.current_streak || 0) > 0 ? 'text-orange-500' : 'text-muted-foreground'}`} />
        <span className="font-medium">{(streak?.current_streak || 0)} 天</span>
        <span className="text-muted-foreground text-xs">
          最长 {streak?.longest_streak || 0} 天
        </span>
      </div>

      {/* 迷你日历 */}
      <MiniCalendar
        notebookId={notebookId}
        onDayClick={onDayClick}
        selectedDate={dayPopoverDate}
        dayDetail={dayDetail}
        dayLoading={dayLoading}
      />
    </div>
  )
}

// ── 迷你日历组件 ─────────────────────────────────

function MiniCalendar({
  notebookId, onDayClick, selectedDate, dayDetail, dayLoading,
}: {
  notebookId: number | null
  onDayClick: (date: string) => void
  selectedDate: string | null
  dayDetail: CalendarDayDetail | null
  dayLoading: boolean
}) {
  const [calData, setCalData] = useState<{
    days: Array<{ date: string; count: number; score_avg: number }>
    total_reviews: number
  } | null>(null)

  useEffect(() => {
    if (!notebookId) return
    const now = new Date()
    reviewApi.calendar(notebookId, now.getFullYear(), now.getMonth() + 1)
      .then(setCalData)
      .catch(console.error)
  }, [notebookId])

  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth()
  const today = `${year}-${String(month + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstDay = new Date(year, month, 1).getDay()

  const dayMap: Record<string, number> = {}
  calData?.days.forEach((d) => { dayMap[d.date] = d.count })

  const weekDays = ['一', '二', '三', '四', '五', '六', '日']

  return (
    <div className="relative">
      <div className="text-xs text-muted-foreground mb-1 text-center">
        {year}年{month + 1}月 · {calData?.total_reviews || 0}次
      </div>
      <div className="grid grid-cols-7 gap-0.5 text-center">
        {weekDays.map((d) => (
          <div key={d} className="text-[10px] text-muted-foreground w-6 h-4 flex items-center justify-center">{d}</div>
        ))}
        {Array.from({ length: (firstDay + 6) % 7 }).map((_, i) => (
          <div key={`empty-${i}`} className="w-6 h-6" />
        ))}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const day = i + 1
          const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
          const count = dayMap[dateStr] || 0
          const isToday = dateStr === today
          const isSelected = dateStr === selectedDate
          const intensity = count === 0
            ? 'bg-muted/40'
            : count <= 2 ? 'bg-green-200 dark:bg-green-900'
            : count <= 5 ? 'bg-green-400 dark:bg-green-700'
            : 'bg-green-600 dark:bg-green-400'
          return (
            <button
              key={day}
              onClick={() => onDayClick(dateStr)}
              className={`w-6 h-6 rounded-sm flex items-center justify-center text-[10px]
                ${intensity} ${isToday ? 'ring-1 ring-primary' : ''} ${isSelected ? 'ring-2 ring-primary' : ''}
                hover:opacity-80 transition-opacity`}
              title={`${dateStr}: ${count} 次`}
            >
              {day}
            </button>
          )
        })}
      </div>

      {/* 日期详情 Popover */}
      {selectedDate && (
        <div className="absolute top-full right-0 mt-1 z-50 w-64 bg-popover border rounded-lg shadow-lg p-3">
          <div className="text-sm font-medium mb-2">{selectedDate}</div>
          {dayLoading ? (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            </div>
          ) : dayDetail && dayDetail.reviews.length > 0 ? (
            <div className="space-y-0.5 max-h-48 overflow-auto">
              <div className="text-xs text-muted-foreground mb-2">
                {dayDetail.total_questions}题 · 正确{dayDetail.correct_count}题 · {dayDetail.score}分
              </div>
              {dayDetail.reviews.map((r, i) => (
                <div key={i} className="text-xs flex items-center justify-between py-0.5">
                  <span className="truncate flex-1 mr-2">{r.note_title}</span>
                  <span className="text-muted-foreground shrink-0">
                    {r.correct} · {RATING_OPTIONS.find(o => o.key === r.rating)?.emoji || r.rating}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground py-3 text-center">无复习记录</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 簇详情面板 ──────────────────────────────────

function ClusterDetailPanel({
  detail, dueData, onStartQuiz, generating,
}: {
  detail: ClusterDetail
  dueData: DueReviewsResponse | null
  onStartQuiz: (scope: string) => void
  generating: boolean
}) {
  const mastery = detail.mastery
  const dueCount = dueData?.clusters?.find(d => d.cluster_id === detail.id)?.due_count || 0
  const masteredRate = mastery && mastery.total > 0
    ? Math.round(((mastery.young + mastery.mature) / mastery.total) * 100)
    : 0

  return (
    <div className="space-y-4">
      {/* 标题 + 掌握度概览 */}
      <div className="border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-base">{detail.name}</h3>
          <span className="text-sm text-muted-foreground">{detail.notes?.length || 0} 篇笔记</span>
        </div>

        {mastery && mastery.total > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">掌握度:</span>
              <div className="flex items-center gap-1">
                {Object.entries({ new: '🔴', learning: '🟡', young: '🟢', mature: '🔵' }).map(([k, e]) => (
                  <span key={k} className="text-xs" title={MASTERY_LABEL[k]}>
                    {e}{(mastery as any)[k]}
                  </span>
                ))}
              </div>
              <span className="text-xs font-medium text-primary ml-1">{masteredRate}% 初通以上</span>
            </div>
            <div className="flex h-2 rounded-full overflow-hidden bg-muted">
              {mastery.new > 0 && <div className="bg-red-400 h-full" style={{ width: `${(mastery.new/mastery.total)*100}%` }} />}
              {mastery.learning > 0 && <div className="bg-amber-400 h-full" style={{ width: `${(mastery.learning/mastery.total)*100}%` }} />}
              {mastery.young > 0 && <div className="bg-green-400 h-full" style={{ width: `${(mastery.young/mastery.total)*100}%` }} />}
              {mastery.mature > 0 && <div className="bg-blue-400 h-full" style={{ width: `${(mastery.mature/mastery.total)*100}%` }} />}
            </div>
          </div>
        )}
      </div>

      {/* 笔记列表 + SM-2 状态 */}
      {detail.notes && detail.notes.length > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-medium mb-2">📋 笔记列表</h4>
          <div className="space-y-1 max-h-[400px] overflow-auto">
            {detail.notes.map((n) => {
              const sm2 = n.sm2
              const nextReview = sm2?.next_review_at ? new Date(sm2.next_review_at) : null
              const isDue = nextReview && nextReview <= new Date()
              return (
                <div key={n.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-accent text-sm">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span title={MASTERY_LABEL[n.mastery]}>{MASTERY_EMOJI[n.mastery]}</span>
                    <span className="truncate">{n.title}</span>
                  </div>
                  <div className="text-xs text-muted-foreground shrink-0 ml-2 text-right">
                    {sm2 ? (
                      isDue ? (
                        <span className="text-orange-500 font-medium">今天到期</span>
                      ) : (
                        <span>
                          {sm2.interval_days}天后 · {sm2.ease_factor.toFixed(1)}ef
                        </span>
                      )
                    ) : (
                      <span>待首次复习</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 复习按钮 */}
      <div className="border rounded-lg p-4">
        <h4 className="text-sm font-medium mb-3">开始复习</h4>
        <div className="grid grid-cols-2 gap-2">
          {(
            [
              { scope: 'due', count: dueCount > 0 ? Math.min(dueCount * 2, 10) : 10 },
              { scope: 'all', count: 10 },
              { scope: 'errors', count: 10 },
              { scope: 'new', count: 10 },
            ] as const
          ).map(({ scope, count }) => {
            const info = SCOPE_LABELS[scope]
            const scopeDueCount = scope === 'due' ? dueCount : null
            return (
              <Button
                key={scope}
                variant={scope === 'due' ? 'default' : 'outline'}
                size="sm"
                onClick={() => onStartQuiz(scope)}
                disabled={generating}
                className="justify-start h-auto py-2"
              >
                <span className="flex items-center gap-1.5">
                  {info.icon}
                  <span>{info.label}</span>
                  {scopeDueCount != null && scopeDueCount > 0 && (
                    <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-0.5">{scopeDueCount}篇</Badge>
                  )}
                </span>
              </Button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── 今日待复习面板（未选簇时） ──────────────────

function TodayDuePanel({
  dueData, clusters, onSelectCluster, onStartQuiz, generating,
}: {
  dueData: DueReviewsResponse | null
  clusters: ClusterInfo[]
  onSelectCluster: (id: number) => void
  onStartQuiz: (clusterId: number, scope: string) => void
  generating: boolean
}) {
  if (!dueData) return <div className="text-sm text-muted-foreground py-4">加载中...</div>

  return (
    <div className="space-y-4">
      <section>
        <h3 className="font-semibold text-base flex items-center gap-2 mb-3">
          <BookOpen className="size-4" /> 今日待复习
        </h3>
        {dueData.total_due === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            🎉 今天没有到期的复习内容
          </p>
        ) : (
          <div className="space-y-3">
            {dueData.clusters?.map((dc) => (
              <div key={dc.cluster_id} className="border rounded-lg p-4 hover:border-primary/30 transition-colors">
                <button
                  className="font-medium text-left hover:text-primary transition-colors"
                  onClick={() => onSelectCluster(dc.cluster_id)}
                >
                  {dc.cluster_name}
                  <ChevronRight className="size-3 inline ml-1" />
                </button>
                <span className="text-sm text-muted-foreground ml-2">
                  {dc.due_count}/{dc.note_count} 篇到期
                </span>
                <div className="flex gap-2 mt-3">
                  {(['due', 'all'] as const).map((scope) => {
                    const info = SCOPE_LABELS[scope]
                    return (
                      <Button key={scope} size="sm" variant={scope === 'due' ? 'default' : 'outline'}
                        onClick={() => onStartQuiz(dc.cluster_id, scope)}
                        disabled={generating}>
                        {info.icon}
                        <span className="ml-1">{info.label}</span>
                      </Button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

// ── 测验面板 ──────────────────────────────────────

function QuizPanel({
  questions, answers, setAnswers, grade, generating,
  noteRatings, setNoteRatings, ratingsSubmitted,
  onSubmit, onSubmitRatings, onBack, onRetry, scope,
}: {
  questions: any[]
  answers: Record<string, string>
  setAnswers: (a: Record<string, string>) => void
  grade: ReviewGradeResponse | null
  generating: boolean
  noteRatings: Record<number, string>
  setNoteRatings: (r: Record<number, string>) => void
  ratingsSubmitted: boolean
  onSubmit: () => void
  onSubmitRatings: () => void
  onBack: () => void
  onRetry: () => void
  scope: string
}) {
  const unanswered = questions.filter((q) => !answers[q.id]).length
  const scopeInfo = SCOPE_LABELS[scope] || SCOPE_LABELS.due

  // 收集涉及的笔记
  const noteSet = new Map<number, { title: string; correct: number; total: number }>()
  questions.forEach((q) => {
    if (q.note_id) {
      const existing = noteSet.get(q.note_id) || { title: q.note_title || '未知', correct: 0, total: 0 }
      existing.total += 1
      if (grade) {
        const result = grade.results.find(r => r.question_id === q.id)
        if (result?.correct) existing.correct += 1
      }
      noteSet.set(q.note_id, existing)
    }
  })

  return (
    <div className="max-w-3xl space-y-4">
      {/* 顶栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>← 返回</Button>
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            {scopeInfo.icon} {scopeInfo.label} · {questions.length} 题 · {unanswered} 题未答
          </span>
        </div>
      </div>

      {generating && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin mr-2" />
          <span className="text-muted-foreground">AI 正在出题...</span>
        </div>
      )}

      {/* 题目列表 */}
      <div className="space-y-6">
        {questions.map((q, i) => {
          const result = grade?.results?.find((r) => r.question_id === q.id)
          return (
            <div
              key={q.id}
              className={`border rounded-lg p-4 ${
                result ? (result.correct ? 'border-green-200 bg-green-50 dark:bg-green-950/20' : 'border-red-200 bg-red-50 dark:bg-red-950/20')
                : ''
              }`}
            >
              <p className="font-medium mb-3">
                <span className="text-muted-foreground mr-2">{i + 1}.</span>
                {q.question}
              </p>

              <div className="grid grid-cols-1 gap-2">
                {(q.options as string[] | undefined)?.map((opt) => {
                  const letter = opt.charAt(0)
                  const selected = answers[q.id] === letter
                  const isCorrectAnswer = result?.answer === letter
                  const isWrongSelected = grade && selected && !result?.correct

                  return (
                    <button
                      key={letter}
                      disabled={!!grade}
                      onClick={() => setAnswers({ ...answers, [q.id]: letter })}
                      className={`text-left px-3 py-2 rounded-md text-sm border transition-colors
                        ${selected && !grade ? 'bg-primary/10 border-primary' : 'hover:bg-accent border-transparent'}
                        ${isCorrectAnswer && grade ? 'bg-green-100 border-green-400 dark:bg-green-900/30' : ''}
                        ${isWrongSelected ? 'bg-red-100 border-red-400 dark:bg-red-900/30' : ''}
                      `}
                    >
                      {opt}
                    </button>
                  )
                })}
              </div>

              {/* 批改结果 */}
              {result && (
                <div className="mt-3 pt-3 border-t text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    {result.correct ? (
                      <CheckCircle2 className="size-4 text-green-600" />
                    ) : (
                      <XCircle className="size-4 text-red-600" />
                    )}
                    <span className={result.correct ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}>
                      {result.correct ? '回答正确' : `正确答案：${result.answer}`}
                    </span>
                  </div>
                  {result.explanation && (
                    <p className="text-muted-foreground mt-1">{result.explanation}</p>
                  )}
                  {q.note_id && (
                    <span className="text-xs text-muted-foreground mt-1 inline-block">
                      📝 来源：{q.note_title || `笔记 #${q.note_id}`}
                    </span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* 提交按钮 */}
      {questions.length > 0 && !grade && (
        <div className="flex justify-center pt-4">
          <Button size="lg" onClick={onSubmit} disabled={unanswered > 0}>
            提交批改 {unanswered > 0 && `（${unanswered} 题未答）`}
          </Button>
        </div>
      )}

      {/* 批改结果 + 评分 */}
      {grade && !ratingsSubmitted && noteSet.size > 0 && (
        <div className="border rounded-lg p-6 space-y-4">
          <div className="text-center">
            <div className="text-3xl font-bold mb-1">
              {grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span>
            </div>
            <p className="text-muted-foreground text-sm">
              {grade.correct}/{grade.total} 题正确 · {grade.summary}
            </p>
          </div>

          <Separator />

          <div>
            <h4 className="text-sm font-medium mb-3">对每篇笔记的回忆质量评价：</h4>
            <div className="space-y-3">
              {Array.from(noteSet.entries()).map(([noteId, info]) => (
                <div key={noteId} className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{info.title}</div>
                    <div className="text-xs text-muted-foreground">
                      出题{info.total}道，对{info.correct}道
                    </div>
                  </div>
                  <div className="flex gap-1">
                    {RATING_OPTIONS.map((opt) => (
                      <button
                        key={opt.key}
                        onClick={() => setNoteRatings({ ...noteRatings, [noteId]: opt.key })}
                        className={`px-2 py-1 rounded-md text-xs border transition-colors
                          ${noteRatings[noteId] === opt.key
                            ? 'bg-primary/10 border-primary'
                            : 'hover:bg-accent border-transparent'
                          }`}
                        title={opt.hint}
                      >
                        {opt.emoji} {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-center pt-2">
            <Button onClick={onSubmitRatings} disabled={Object.keys(noteRatings).length === 0}>
              确认提交
            </Button>
          </div>
        </div>
      )}

      {/* 最终结果（评分已提交） */}
      {grade && (ratingsSubmitted || noteSet.size === 0) && (
        <div className="border rounded-lg p-6 text-center space-y-3">
          <div className="text-4xl font-bold">
            {grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span>
          </div>
          <p className="text-muted-foreground">{grade.correct}/{grade.total} 题正确</p>
          <p className="text-sm text-muted-foreground">{grade.summary}</p>

          {grade.updated_states && grade.updated_states.length > 0 && (
            <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
              <div className="font-medium mb-1">SM-2 状态更新：</div>
              {grade.updated_states.map((s) => (
                <div key={s.note_id} className="flex items-center justify-center gap-1">
                  <span>{MASTERY_EMOJI[s.mastery_before] || '⚪'}</span>
                  <span>→</span>
                  <span>{MASTERY_EMOJI[s.mastery_after] || '⚪'}</span>
                  <span className="ml-1">
                    {s.rating} · {s.old_interval}d → {s.new_interval}d
                  </span>
                  {s.next_review_at && (
                    <span className="text-muted-foreground">
                      (下次 {new Date(s.next_review_at).toLocaleDateString('zh-CN')})
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-center gap-3 pt-2">
            <Button onClick={onBack} variant="outline">返回列表</Button>
            <Button onClick={onRetry}>再做一套</Button>
          </div>
        </div>
      )}
    </div>
  )
}
