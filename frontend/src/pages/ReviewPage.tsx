/**
 * 温故知新页面 — 学迹 (LearnTrace) V3
 * ============================================
 * 概念簇 + SM-2 四档评分 + 四种复习模式 + 打卡 + 知识点收藏
 */

import { useEffect, useState, useCallback } from 'react'
import { useNotesStore } from '@/stores/notes'
import { reviewApi, notebooksApi } from '@/lib/api'
import type {
  ClusterInfo, ClusterDetail, DueReviewsResponse, ReviewGenerateResponse,
  ReviewGradeResponse, QuizAttempt, StreakInfo, Notebook, KnowledgeBookmark,
} from '@/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Brain, RefreshCw, BookOpen, CheckCircle2, XCircle,
  Target, Loader2, Flame, Zap, Sparkles, AlertCircle,
  BookmarkPlus, Bookmark, Trash2,
} from 'lucide-react'

// ── 常量 ───────────────────────────────────────

const MASTERY_EMOJI: Record<string, string> = { new: '🔴', learning: '🟡', young: '🟢', mature: '🔵' }
const MASTERY_LABEL: Record<string, string> = { new: '新学', learning: '学习', young: '初通', mature: '熟练' }
const SCOPE_META: Record<string, { icon: JSX.Element; label: string; desc: string }> = {
  due: { icon: <BookOpen className="size-3" />, label: '到期复习', desc: '仅出到期笔记的题，计入遗忘曲线' },
  all: { icon: <Zap className="size-3" />, label: '集中突击', desc: '簇内全部笔记混出，不计入曲线' },
  errors: { icon: <AlertCircle className="size-3" />, label: '错题重温', desc: '只出历史错题对应的笔记' },
  new: { icon: <Sparkles className="size-3" />, label: '新知初探', desc: '只出从未复习过的笔记，计入曲线' },
}
const RATING_OPTIONS = [
  { key: 'again', emoji: '🔴', label: 'Again', hint: '完全忘记' },
  { key: 'hard', emoji: '🟠', label: 'Hard', hint: '想了很久' },
  { key: 'good', emoji: '🟢', label: 'Good', hint: '正常答对' },
  { key: 'easy', emoji: '🔵', label: 'Easy', hint: '秒答' },
] as const

const QUIZ_STORAGE_KEY = 'learnTrace_quiz_state'

// ── Quiz 持久化 helper ──────────────────────────

interface StoredQuiz {
  quizId: number
  questions: ReviewGenerateResponse['questions']
  answers: Record<string, string>
  grade: ReviewGradeResponse | null
  scope: string
  clusterId: number
  noteRatings: Record<number, string>
  ratingsSubmitted: boolean
  timestamp: number
}

function saveQuiz(s: StoredQuiz) {
  try { sessionStorage.setItem(QUIZ_STORAGE_KEY, JSON.stringify(s)) } catch {}
}
function loadQuiz(): StoredQuiz | null {
  try {
    const raw = sessionStorage.getItem(QUIZ_STORAGE_KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as StoredQuiz
    if (Date.now() - s.timestamp > 86400000) { sessionStorage.removeItem(QUIZ_STORAGE_KEY); return null }
    return s
  } catch { return null }
}
function clearQuiz() { sessionStorage.removeItem(QUIZ_STORAGE_KEY) }

// ── 主组件 ─────────────────────────────────────

export default function ReviewPage() {
  const storeActiveNbId = useNotesStore((s) => s.activeNotebookId)

  // 知识库
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [selectedNbId, setSelectedNbId] = useState<number | null>(null)

  // 数据
  const [clusters, setClusters] = useState<ClusterInfo[]>([])
  const [dueData, setDueData] = useState<DueReviewsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [reclustering, setReclustering] = useState(false)
  const [streak, setStreak] = useState<StreakInfo | null>(null)
  const [bookmarks, setBookmarks] = useState<KnowledgeBookmark[]>([])

  // 选中簇
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null)
  const [clusterDetail, setClusterDetail] = useState<ClusterDetail | null>(null)

  // 出题确认弹窗
  const [confirmModal, setConfirmModal] = useState<{ clusterId: number; scope: string; count: number } | null>(null)

  // 测验状态
  const [quizScope, setQuizScope] = useState<string>('due')
  const [quizId, setQuizId] = useState<number | null>(null)
  const [questions, setQuestions] = useState<ReviewGenerateResponse['questions']>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [generating, setGenerating] = useState(false)
  const [grade, setGrade] = useState<ReviewGradeResponse | null>(null)
  const [noteRatings, setNoteRatings] = useState<Record<number, string>>({})
  const [ratingsSubmitted, setRatingsSubmitted] = useState(false)

  // 错误提示
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const showError = (msg: string) => { setErrorMsg(msg); setTimeout(() => setErrorMsg(null), 4000) }

  // ── 恢复持久化 Quiz ───────────────────────────

  useEffect(() => {
    const stored = loadQuiz()
    if (stored) {
      setQuizId(stored.quizId)
      setQuestions(stored.questions)
      setAnswers(stored.answers)
      setGrade(stored.grade)
      setQuizScope(stored.scope)
      setSelectedClusterId(stored.clusterId)
      setNoteRatings(stored.noteRatings || {})
      setRatingsSubmitted(stored.ratingsSubmitted || false)
    }
  }, [])

  // ── 初始化笔记本 ─────────────────────────────

  useEffect(() => {
    notebooksApi.list().then(res => {
      const nbs = res.notebooks || []
      setNotebooks(nbs)
      const targetId = storeActiveNbId ?? (nbs.length > 0 ? nbs[0].id : null)
      if (targetId && targetId !== selectedNbId) setSelectedNbId(targetId)
    }).catch(e => showError('加载知识库失败: ' + (e?.message || '')))
  }, [])

  // ── 加载数据 ───────────────────────────────────

  const loadReviewData = useCallback(async (nbId: number) => {
    setLoading(true)
    try {
      const [cRes, dRes, sRes, bRes] = await Promise.all([
        reviewApi.clusters(nbId),
        reviewApi.due(nbId),
        reviewApi.streak(nbId),
        reviewApi.bookmarks(nbId),
      ])
      setClusters(cRes.clusters || [])
      setDueData(dRes)
      setStreak(sRes)
      setBookmarks(bRes.bookmarks || [])
    } catch (e: any) {
      showError('加载失败: ' + (e?.message || '网络错误'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { if (selectedNbId) loadReviewData(selectedNbId) }, [selectedNbId, loadReviewData])

  const switchNotebook = (nbId: number) => {
    setSelectedNbId(nbId)
    setSelectedClusterId(null)
    setClusterDetail(null)
    useNotesStore.getState().setActiveNotebook(nbId)
  }

  // ── 选中簇 ────────────────────────────────────

  const selectCluster = async (clusterId: number) => {
    setSelectedClusterId(clusterId)
    try { setClusterDetail(await reviewApi.clusterDetail(clusterId)) }
    catch (e: any) { showError('加载簇详情失败: ' + (e?.message || '')) }
  }

  // ── 重聚类 ────────────────────────────────────

  const handleRecluster = async () => {
    if (!selectedNbId) { showError('请先选择知识库'); return }
    if (reclustering) return
    setReclustering(true)
    setErrorMsg(null)
    try {
      await reviewApi.recluster(selectedNbId)
      await loadReviewData(selectedNbId)
      setSelectedClusterId(null)
      setClusterDetail(null)
    } catch (e: any) { showError('重聚类失败: ' + (e?.message || '网络错误')) }
    finally { setReclustering(false) }
  }

  // ── 出题确认 → 真正出题 ───────────────────────

  const requestQuiz = (clusterId: number, scope: string, count: number) => {
    setConfirmModal({ clusterId, scope, count })
  }

  const startQuiz = async (clusterId: number, scope: string, count: number) => {
    setConfirmModal(null)
    setGenerating(true)
    setGrade(null); setAnswers({}); setNoteRatings({}); setRatingsSubmitted(false)
    setQuizScope(scope)
    try {
      const res = await reviewApi.generate(clusterId, scope, count)
      setQuizId(res.quiz_id)
      setQuestions(res.questions)
      setSelectedClusterId(clusterId)
      saveQuiz({ quizId: res.quiz_id, questions: res.questions, answers: {},
        grade: null, scope, clusterId, noteRatings: {}, ratingsSubmitted: false, timestamp: Date.now() })
    } catch (e: any) { showError('出题失败: ' + (e?.message || '网络错误')) }
    finally { setGenerating(false) }
  }

  // ── 提交答案 → 然后评分 ────────────────────────

  const submitAnswers = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(
      ([question_id, answer]) => ({ question_id, answer }))
    try {
      const res = await reviewApi.grade(quizId, attempts)
      setGrade(res)
      saveQuiz({ quizId, questions, answers, grade: res, scope: quizScope,
        clusterId: selectedClusterId!, noteRatings, ratingsSubmitted: false, timestamp: Date.now() })
    } catch (e: any) { showError('批改失败: ' + (e?.message || '')) }
  }

  const submitRatings = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(
      ([question_id, answer]) => ({ question_id, answer }))
    const ratings = Object.entries(noteRatings).map(([noteId, rating]) =>
      ({ note_id: Number(noteId), rating }))
    try {
      const res = await reviewApi.grade(quizId, attempts, ratings)
      setGrade(res)
      setRatingsSubmitted(true)
      clearQuiz()
      if (selectedNbId) await loadReviewData(selectedNbId)
    } catch (e: any) { showError('提交评分失败: ' + (e?.message || '')) }
  }

  const backToList = () => {
    clearQuiz()
    setQuizId(null); setQuestions([]); setAnswers({})
    setGrade(null); setNoteRatings({}); setRatingsSubmitted(false)
    if (selectedNbId) loadReviewData(selectedNbId)
  }

  // ── 收藏知识点 ─────────────────────────────────

  const addBookmark = async (noteId: number, question: string, explanation: string, clusterId: number | null) => {
    if (!selectedNbId) return
    try {
      await reviewApi.addBookmark({ notebook_id: selectedNbId, note_id: noteId, question, explanation, cluster_id: clusterId })
      if (selectedNbId) {
        const bRes = await reviewApi.bookmarks(selectedNbId)
        setBookmarks(bRes.bookmarks || [])
      }
    } catch (e: any) { showError('收藏失败: ' + (e?.message || '')) }
  }

  const removeBookmark = async (bmId: number) => {
    try {
      await reviewApi.removeBookmark(bmId)
      setBookmarks(prev => prev.filter(b => b.id !== bmId))
    } catch (e: any) { showError('取消收藏失败: ' + (e?.message || '')) }
  }

  // ── 渲染 ───────────────────────────────────────

  const hasQuiz = questions.length > 0

  return (
    <div className="flex h-full gap-4">
      {/* ========== 左侧栏 ========== */}
      <aside className="w-[240px] shrink-0 border-r pr-2 flex flex-col">
        <div className="flex items-center justify-between mb-2 px-1">
          <h2 className="font-semibold text-sm flex items-center gap-2"><Brain className="size-4" />概念簇</h2>
          <Button variant="ghost" size="sm" className="h-7 text-xs"
            onClick={handleRecluster} disabled={reclustering} title="重新聚类">
            <RefreshCw className={`size-3 ${reclustering ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {clusters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm px-2">
              <Brain className="size-8 mx-auto mb-2 opacity-30" />
              {loading ? '加载中...' : '暂无概念簇，请导入笔记后点击重聚类'}
            </div>
          ) : (
            <div className="space-y-0.5">
              {clusters.map((c) => {
                const dueCount = dueData?.clusters?.find(d => d.cluster_id === c.id)?.due_count || 0
                const mastery = c.mastery
                const selected = selectedClusterId === c.id && !hasQuiz
                return (
                  <button key={c.id} onClick={() => selectCluster(c.id)}
                    className={`w-full text-left px-2 py-2 rounded-md text-sm transition-colors
                      ${selected ? 'bg-primary/10 border border-primary/30' : 'hover:bg-accent border border-transparent'}`}>
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium truncate text-xs">{c.name}</span>
                      {dueCount > 0 && <Badge variant="default" className="text-[10px] h-4 px-1">{dueCount}</Badge>}
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

      {/* ========== 右侧内容 ========== */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* 顶栏：知识库选择 + 打卡 */}
        <div className="px-1 pt-2 pb-1 flex items-center gap-3 flex-wrap">
          <label className="text-xs text-muted-foreground shrink-0">知识库:</label>
          <select className="border rounded-md px-2 py-1 text-xs bg-background max-w-[160px]"
            value={selectedNbId ?? ''}
            onChange={(e) => { const id = Number(e.target.value); if (id) switchNotebook(id) }}>
            {notebooks.length === 0 && <option value="">无可用知识库</option>}
            {notebooks.map(nb => <option key={nb.id} value={nb.id}>{nb.name}</option>)}
          </select>
          {streak && (
            <span className="text-xs flex items-center gap-1 ml-auto">
              <Flame className={`size-3.5 ${streak.current_streak > 0 ? 'text-orange-500' : 'text-muted-foreground'}`} />
              <span className="font-medium">{streak.current_streak}天</span>
              <span className="text-muted-foreground">/ 最长{streak.longest_streak}天</span>
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
          {generating ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="size-6 animate-spin mr-2" /><span className="text-muted-foreground">AI 正在出题...</span></div>
          ) : hasQuiz ? (
            <QuizPanel questions={questions} answers={answers} setAnswers={setAnswers}
              grade={grade} noteRatings={noteRatings} setNoteRatings={setNoteRatings}
              ratingsSubmitted={ratingsSubmitted} scope={quizScope}
              onSubmit={submitAnswers} onSubmitRatings={submitRatings}
              onBack={backToList} onAddBookmark={addBookmark}
              onRetry={() => startQuiz(selectedClusterId!, quizScope, questions.length)}
              selectedClusterId={selectedClusterId} />
          ) : clusterDetail ? (
            <div className="space-y-4 max-w-3xl pr-2">
              <ClusterDetailPanel detail={clusterDetail} dueData={dueData}
                onRequestQuiz={requestQuiz} />
            </div>
          ) : (
            <div className="space-y-4 max-w-3xl pr-2">
              {dueData && dueData.total_due > 0 ? (
                <TodayDuePanel dueData={dueData} clusters={clusters}
                  onSelectCluster={selectCluster} onRequestQuiz={requestQuiz} />
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground py-6 text-center">
                    {loading ? '加载中...' : '🎉 没有到期的复习内容，选中左侧概念簇开始复习'}
                  </p>
                </div>
              )}
              <BookmarkPanel bookmarks={bookmarks} onRemove={removeBookmark}
                onNavigateNote={(noteId) => {
                  const s = useNotesStore.getState()
                  s.openTab(noteId, '')
                  document.querySelector('[data-nav-notes]')?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
                }} />
            </div>
          )}
        </ScrollArea>
      </main>

      {/* ========== 出题确认弹窗 ========== */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setConfirmModal(null)}>
          <div className="bg-background border rounded-lg shadow-xl p-6 max-w-sm w-full mx-4"
            onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-base mb-2">
              {SCOPE_META[confirmModal.scope]?.icon}
              <span className="ml-2">{SCOPE_META[confirmModal.scope]?.label}</span>
            </h3>
            <p className="text-sm text-muted-foreground mb-1">
              {SCOPE_META[confirmModal.scope]?.desc}
            </p>
            <p className="text-sm mb-4">
              从「<strong>{clusters.find(c => c.id === confirmModal.clusterId)?.name || '未知簇'}</strong>」出 {confirmModal.count} 道题
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={() => setConfirmModal(null)}>取消</Button>
              <Button size="sm" onClick={() => startQuiz(confirmModal.clusterId, confirmModal.scope, confirmModal.count)}>
                开始出题
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 簇详情面板 ──────────────────────────────────

function ClusterDetailPanel({ detail, dueData, onRequestQuiz }: {
  detail: ClusterDetail
  dueData: DueReviewsResponse | null
  onRequestQuiz: (clusterId: number, scope: string, count: number) => void
}) {
  const mastery = detail.mastery
  const dueCount = dueData?.clusters?.find(d => d.cluster_id === detail.id)?.due_count || 0
  const masteredRate = mastery && mastery.total > 0
    ? Math.round(((mastery.young + mastery.mature) / mastery.total) * 100) : 0

  return (
    <div className="space-y-4">
      <div className="border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-base">{detail.name}</h3>
          <span className="text-sm text-muted-foreground">{detail.notes?.length || 0} 篇笔记</span>
        </div>
        {mastery && mastery.total > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">掌握度:</span>
              {Object.entries({ new: '🔴', learning: '🟡', young: '🟢', mature: '🔵' }).map(([k, e]) => (
                <span key={k} className="text-xs" title={MASTERY_LABEL[k]}>{e}{(mastery as any)[k]}</span>
              ))}
              <span className="text-xs font-medium text-primary ml-1">{masteredRate}% 初通以上</span>
            </div>
            <div className="flex h-2 rounded-full overflow-hidden bg-muted">
              {mastery.new > 0 && <div className="bg-red-400 h-full" style={{ width: `${(mastery.new / mastery.total) * 100}%` }} />}
              {mastery.learning > 0 && <div className="bg-amber-400 h-full" style={{ width: `${(mastery.learning / mastery.total) * 100}%` }} />}
              {mastery.young > 0 && <div className="bg-green-400 h-full" style={{ width: `${(mastery.young / mastery.total) * 100}%` }} />}
              {mastery.mature > 0 && <div className="bg-blue-400 h-full" style={{ width: `${(mastery.mature / mastery.total) * 100}%` }} />}
            </div>
          </div>
        )}
      </div>

      {detail.notes && detail.notes.length > 0 && (
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-medium mb-2">📋 笔记列表</h4>
          <div className="space-y-1 max-h-[300px] overflow-auto">
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
                    {sm2 ? (isDue ? <span className="text-orange-500 font-medium">今天到期</span> :
                      <span>{sm2.interval_days}天后 · {sm2.ease_factor.toFixed(1)}ef</span>) :
                      <span>待首次复习</span>}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="border rounded-lg p-4">
        <h4 className="text-sm font-medium mb-3">开始复习</h4>
        <div className="grid grid-cols-2 gap-2">
          {(['due', 'all', 'errors', 'new'] as const).map(scope => {
            const info = SCOPE_META[scope]
            return (
              <Button key={scope} variant={scope === 'due' ? 'default' : 'outline'} size="sm"
                onClick={() => onRequestQuiz(detail.id, scope, 10)}
                className="justify-start h-auto py-2">
                <span className="flex items-center gap-1.5">
                  {info.icon}<span>{info.label}</span>
                  {scope === 'due' && dueCount > 0 &&
                    <Badge variant="secondary" className="text-[10px] h-4 px-1">{dueCount}篇</Badge>}
                </span>
              </Button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── 今日待复习 ──────────────────────────────────

function TodayDuePanel({ dueData, clusters, onSelectCluster, onRequestQuiz }: {
  dueData: DueReviewsResponse
  clusters: ClusterInfo[]
  onSelectCluster: (id: number) => void
  onRequestQuiz: (clusterId: number, scope: string, count: number) => void
}) {
  return (
    <section>
      <h3 className="font-semibold text-base flex items-center gap-2 mb-3"><BookOpen className="size-4" />今日待复习</h3>
      <div className="space-y-3">
        {dueData.clusters?.map(dc => (
          <div key={dc.cluster_id} className="border rounded-lg p-4">
            <button className="font-medium text-left hover:text-primary" onClick={() => onSelectCluster(dc.cluster_id)}>
              {dc.cluster_name}</button>
            <span className="text-sm text-muted-foreground ml-2">{dc.due_count}/{dc.note_count} 篇到期</span>
            <div className="flex gap-2 mt-3">
              {(['due', 'all'] as const).map(scope => (
                <Button key={scope} size="sm" variant={scope === 'due' ? 'default' : 'outline'}
                  onClick={() => onRequestQuiz(dc.cluster_id, scope, 10)}>
                  {SCOPE_META[scope].icon}<span className="ml-1">{SCOPE_META[scope].label}</span>
                </Button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── 知识点收藏面板 ──────────────────────────────

function BookmarkPanel({ bookmarks, onRemove, onNavigateNote }: {
  bookmarks: KnowledgeBookmark[]
  onRemove: (id: number) => void
  onNavigateNote: (noteId: number) => void
}) {
  if (bookmarks.length === 0) return null
  return (
    <section>
      <h3 className="font-semibold text-base flex items-center gap-2 mb-3">
        <Bookmark className="size-4" />知识点收藏 ({bookmarks.length})
      </h3>
      <div className="space-y-2">
        {bookmarks.map(bm => (
          <div key={bm.id} className="border rounded-lg p-3 text-sm">
            <p className="mb-1">{bm.question}</p>
            {bm.explanation && <p className="text-xs text-muted-foreground mb-2">{bm.explanation}</p>}
            <div className="flex items-center gap-2">
              <Button variant="link" size="sm" className="h-auto p-0 text-xs"
                onClick={() => onNavigateNote(bm.note_id)}>
                📝 查看笔记
              </Button>
              <Button variant="ghost" size="sm" className="h-6 px-1 text-xs text-muted-foreground"
                onClick={() => onRemove(bm.id)}>
                <Trash2 className="size-3" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── 测验面板 ─────────────────────────────────────

function QuizPanel({ questions, answers, setAnswers, grade, noteRatings, setNoteRatings,
  ratingsSubmitted, scope, onSubmit, onSubmitRatings, onBack, onAddBookmark, onRetry, selectedClusterId }: {
  questions: any[]
  answers: Record<string, string>
  setAnswers: (a: Record<string, string>) => void
  grade: ReviewGradeResponse | null
  noteRatings: Record<number, string>
  setNoteRatings: (r: Record<number, string>) => void
  ratingsSubmitted: boolean
  scope: string
  onSubmit: () => void
  onSubmitRatings: () => void
  onBack: () => void
  onAddBookmark: (noteId: number, question: string, explanation: string, clusterId: number | null) => void
  onRetry: () => void
  selectedClusterId: number | null
}) {
  const unanswered = questions.filter(q => !answers[q.id]).length
  const scopeInfo = SCOPE_META[scope] || SCOPE_META.due
  const [bookmarkedQs, setBookmarkedQs] = useState<Set<string>>(new Set())

  // 收集笔记
  const noteSet = new Map<number, { title: string; correct: number; total: number }>()
  questions.forEach(q => {
    if (q.note_id) {
      const e = noteSet.get(q.note_id) || { title: q.note_title || '未知', correct: 0, total: 0 }
      e.total += 1
      if (grade) { const r = grade.results.find((r: any) => r.question_id === q.id); if (r?.correct) e.correct += 1 }
      noteSet.set(q.note_id, e)
    }
  })

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>← 返回</Button>
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            {scopeInfo.icon} {scopeInfo.label} · {questions.length} 题 · {unanswered} 题未答
          </span>
        </div>
      </div>

      <div className="space-y-6">
        {questions.map((q, i) => {
          const result = grade?.results?.find((r: any) => r.question_id === q.id)
          const isBookmarked = bookmarkedQs.has(q.id)
          return (
            <div key={q.id} className={`border rounded-lg p-4 ${result ? (result.correct ? 'border-green-200 bg-green-50 dark:bg-green-950/20' : 'border-red-200 bg-red-50 dark:bg-red-950/20') : ''}`}>
              <p className="font-medium mb-3"><span className="text-muted-foreground mr-2">{i + 1}.</span>{q.question}</p>
              <div className="grid grid-cols-1 gap-2">
                {(q.options as string[] | undefined)?.map(opt => {
                  const letter = opt.charAt(0)
                  const selected = answers[q.id] === letter
                  const isCorrect = result?.answer === letter
                  const isWrong = grade && selected && !result?.correct
                  return (
                    <button key={letter} disabled={!!grade}
                      onClick={() => setAnswers({ ...answers, [q.id]: letter })}
                      className={`text-left px-3 py-2 rounded-md text-sm border transition-colors
                        ${selected && !grade ? 'bg-primary/10 border-primary' : 'hover:bg-accent border-transparent'}
                        ${isCorrect && grade ? 'bg-green-100 border-green-400 dark:bg-green-900/30' : ''}
                        ${isWrong ? 'bg-red-100 border-red-400 dark:bg-red-900/30' : ''}`}>{opt}</button>
                )
                })}
              </div>
              {result && (
                <div className="mt-3 pt-3 border-t text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    {result.correct ? <CheckCircle2 className="size-4 text-green-600" /> : <XCircle className="size-4 text-red-600" />}
                    <span className={result.correct ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}>
                      {result.correct ? '正确' : `正确答案：${result.answer}`}</span>
                    {/* 收藏按钮 — 错题显示 */}
                    {!result.correct && (
                      <button onClick={() => {
                        onAddBookmark(q.note_id, q.question, result.explanation, selectedClusterId)
                        setBookmarkedQs(prev => new Set([...prev, q.id]))
                      }}
                        disabled={isBookmarked}
                        className="ml-auto text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-accent disabled:opacity-50"
                        title="收藏此知识点">
                        <BookmarkPlus className="size-3.5" />
                        {isBookmarked ? '已收藏' : '收藏知识点'}
                      </button>
                    )}
                  </div>
                  {result.explanation && <p className="text-muted-foreground mt-1">{result.explanation}</p>}
                  {q.note_id && <span className="text-xs text-muted-foreground mt-1 inline-block">📝 来源：{q.note_title || `笔记 #${q.note_id}`}</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!grade && questions.length > 0 && (
        <div className="flex justify-center pt-4">
          <Button size="lg" onClick={onSubmit} disabled={unanswered > 0}>
            提交批改 {unanswered > 0 && `（${unanswered} 题未答）`}</Button>
        </div>
      )}

      {grade && !ratingsSubmitted && noteSet.size > 0 && (
        <div className="border rounded-lg p-6 space-y-4">
          <div className="text-center">
            <div className="text-3xl font-bold mb-1">{grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span></div>
            <p className="text-muted-foreground text-sm">{grade.correct}/{grade.total} 题正确 · {grade.summary}</p>
          </div>
          <Separator />
          <div>
            <h4 className="text-sm font-medium mb-3">对每篇笔记的回忆质量评价：</h4>
            <div className="space-y-3">
              {Array.from(noteSet.entries()).map(([noteId, info]) => (
                <div key={noteId} className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{info.title}</div>
                    <div className="text-xs text-muted-foreground">出题{info.total}道，对{info.correct}道</div>
                  </div>
                  <div className="flex gap-1">
                    {RATING_OPTIONS.map(opt => (
                      <button key={opt.key}
                        onClick={() => setNoteRatings({ ...noteRatings, [noteId]: opt.key })}
                        className={`px-2 py-1 rounded-md text-xs border transition-colors
                          ${noteRatings[noteId] === opt.key ? 'bg-primary/10 border-primary' : 'hover:bg-accent border-transparent'}`}
                        title={opt.hint}>{opt.emoji} {opt.label}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-center pt-2">
            <Button onClick={onSubmitRatings} disabled={Object.keys(noteRatings).length === 0}>确认提交</Button>
          </div>
        </div>
      )}

      {grade && (ratingsSubmitted || noteSet.size === 0) && (
        <div className="border rounded-lg p-6 text-center space-y-3">
          <div className="text-4xl font-bold">{grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span></div>
          <p className="text-muted-foreground">{grade.correct}/{grade.total} 题正确</p>
          <p className="text-sm text-muted-foreground">{grade.summary}</p>
          {grade.updated_states && grade.updated_states.length > 0 && (
            <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
              <div className="font-medium mb-1">SM-2 状态更新：</div>
              {grade.updated_states.map(s => (
                <div key={s.note_id} className="flex items-center justify-center gap-1">
                  <span>{MASTERY_EMOJI[s.mastery_before] || '⚪'}→{MASTERY_EMOJI[s.mastery_after] || '⚪'}</span>
                  <span>{s.rating} · {s.old_interval}d→{s.new_interval}d</span>
                  {s.next_review_at && <span>(下次 {new Date(s.next_review_at).toLocaleDateString('zh-CN')})</span>}
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
