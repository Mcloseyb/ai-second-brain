/**
 * 温故知新 — 学迹 LearnTrace V4
 * ============================================
 */

import { useEffect, useState, useCallback } from 'react'
import { useNotesStore } from '@/stores/notes'
import { reviewApi, notebooksApi } from '@/lib/api'
import type {
  ClusterInfo, ClusterDetail, DueReviewsResponse, ReviewGenerateResponse,
  ReviewGradeResponse, QuizAttempt, StreakInfo, Notebook, KnowledgeBookmark,
  ReviewStats, WrongQuestion,
} from '@/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Brain, RefreshCw, BookOpen, CheckCircle2, XCircle,
  Loader2, Flame, Zap, Sparkles, AlertCircle,
  BookmarkPlus, Bookmark, Trash2, BarChart3, ChevronRight,
} from 'lucide-react'

// ── 常量 ───────────────────────────────────────

const MASTERY_COLORS: Record<string, string> = {
  new: 'text-red-600 bg-red-50 dark:bg-red-950/30',
  learning: 'text-amber-600 bg-amber-50 dark:bg-amber-950/30',
  young: 'text-green-600 bg-green-50 dark:bg-green-950/30',
  mature: 'text-blue-600 bg-blue-50 dark:bg-blue-950/30',
}
const MASTERY_LABEL: Record<string, string> = { new: '新学', learning: '学习', young: '初通', mature: '熟练' }
const MASTERY_ORDER = ['new', 'learning', 'young', 'mature']
const SCOPE_META: Record<string, { icon: JSX.Element; label: string; desc: string }> = {
  due: { icon: <BookOpen className="size-3" />, label: '到期复习', desc: '仅出到期笔记的题，计入遗忘曲线' },
  all: { icon: <Zap className="size-3" />, label: '集中突击', desc: '簇内全部笔记混出，不计入曲线' },
  errors: { icon: <AlertCircle className="size-3" />, label: '错题重温', desc: '重做之前答错的原题' },
  new: { icon: <Sparkles className="size-3" />, label: '新知初探', desc: '只出从未复习过的笔记，计入曲线' },
}
const RATING_OPTIONS = [
  { key: 'again', color: 'text-red-600 bg-red-50 border-red-300', label: 'Again', hint: '完全忘记' },
  { key: 'hard', color: 'text-amber-600 bg-amber-50 border-amber-300', label: 'Hard', hint: '想了很久' },
  { key: 'good', color: 'text-green-600 bg-green-50 border-green-300', label: 'Good', hint: '正常答对' },
  { key: 'easy', color: 'text-blue-600 bg-blue-50 border-blue-300', label: 'Easy', hint: '秒答' },
] as const

const QUIZ_KEY = 'learnTrace_quiz'

// ── Quiz 持久化 ─────────────────────────────────

interface StoredQuiz {
  quizId: number; questions: any[]; answers: Record<string,string>
  grade: ReviewGradeResponse|null; scope: string; clusterId: number
  noteRatings: Record<number,string>; ratingsSubmitted: boolean; timestamp: number
}
function saveQuiz(s: StoredQuiz) { try { sessionStorage.setItem(QUIZ_KEY, JSON.stringify(s)) } catch {} }
function loadQuiz(): StoredQuiz | null {
  try {
    const raw = sessionStorage.getItem(QUIZ_KEY); if (!raw) return null
    const s = JSON.parse(raw) as StoredQuiz
    if (Date.now() - s.timestamp > 864e5) { sessionStorage.removeItem(QUIZ_KEY); return null }
    return s
  } catch { return null }
}
function clearQuiz() { sessionStorage.removeItem(QUIZ_KEY) }

// ── 排序簇内笔记 ────────────────────────────────

function sortNotes(notes: ClusterDetail['notes']) {
  return [...notes].sort((a, b) => {
    const aDue = a.sm2?.next_review_at && new Date(a.sm2.next_review_at) <= new Date()
    const bDue = b.sm2?.next_review_at && new Date(b.sm2.next_review_at) <= new Date()
    if (aDue !== bDue) return aDue ? -1 : 1
    const aOrd = MASTERY_ORDER.indexOf(a.mastery), bOrd = MASTERY_ORDER.indexOf(b.mastery)
    if (aOrd !== bOrd) return aOrd - bOrd
    return (a.sm2?.interval_days || 0) - (b.sm2?.interval_days || 0)
  })
}

// ── 主组件 ─────────────────────────────────────

export default function ReviewPage() {
  const storeNbId = useNotesStore((s) => s.activeNotebookId)
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [nbId, setNbId] = useState<number|null>(null)
  const [clusters, setClusters] = useState<ClusterInfo[]>([])
  const [dueData, setDueData] = useState<DueReviewsResponse|null>(null)
  const [loading, setLoading] = useState(true)
  const [reclustering, setReclustering] = useState(false)
  const [streak, setStreak] = useState<StreakInfo|null>(null)
  const [stats, setStats] = useState<ReviewStats|null>(null)
  const [bookmarks, setBookmarks] = useState<KnowledgeBookmark[]>([])
  const [wq, setWq] = useState<WrongQuestion[]>([])   // 缓存的错题

  const [selCid, setSelCid] = useState<number|null>(null)
  const [cDetail, setCDetail] = useState<ClusterDetail|null>(null)
  const [confirmModal, setConfirmModal] = useState<{clusterId:number;scope:string;count:number}|null>(null)
  const [wrongModal, setWrongModal] = useState(false)   // 错题重温弹窗

  const [quizId, setQuizId] = useState<number|null>(null)
  const [questions, setQuestions] = useState<any[]>([])
  const [answers, setAnswers] = useState<Record<string,string>>({})
  const [generating, setGenerating] = useState(false)
  const [grade, setGrade] = useState<ReviewGradeResponse|null>(null)
  const [noteRatings, setNoteRatings] = useState<Record<number,string>>({})
  const [ratingsDone, setRatingsDone] = useState(false)
  const [quizScope, setQuizScope] = useState('due')
  const [errorMsg, setErrorMsg] = useState<string|null>(null)
  const showErr = (m: string) => { setErrorMsg(m); setTimeout(() => setErrorMsg(null), 4000) }

  // ── 恢复 quiz ──
  useEffect(() => {
    const s = loadQuiz()
    if (s) { setQuizId(s.quizId); setQuestions(s.questions); setAnswers(s.answers)
      setGrade(s.grade); setQuizScope(s.scope); setSelCid(s.clusterId)
      setNoteRatings(s.noteRatings||{}); setRatingsDone(s.ratingsSubmitted||false) }
  }, [])

  // ── 初始化 ──
  useEffect(() => {
    notebooksApi.list().then(r => {
      const nbs = r.notebooks||[]; setNotebooks(nbs)
      const t = storeNbId ?? (nbs[0]?.id ?? null)
      if (t && t !== nbId) setNbId(t)
    }).catch(e => showErr('加载知识库失败: '+e?.message))
  }, [])

  const loadAll = useCallback(async (id: number) => {
    setLoading(true)
    try {
      const [c,d,s,st,b] = await Promise.all([
        reviewApi.clusters(id), reviewApi.due(id), reviewApi.streak(id),
        reviewApi.stats(id), reviewApi.bookmarks(id),
      ])
      setClusters(c.clusters||[]); setDueData(d); setStreak(s); setStats(st); setBookmarks(b.bookmarks||[])
    } catch(e: any) { showErr('加载失败: '+e?.message) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { if (nbId) loadAll(nbId) }, [nbId, loadAll])

  const switchNb = (id: number) => { setNbId(id); setSelCid(null); setCDetail(null); useNotesStore.getState().setActiveNotebook(id) }

  // ── 簇 ──
  const selectCluster = async (cid: number) => { setSelCid(cid); try { setCDetail(await reviewApi.clusterDetail(cid)) } catch(e:any){ showErr(e?.message||'') } }
  const recluster = async () => {
    if (!nbId) return showErr('请选择知识库'); if (reclustering) return
    setReclustering(true); setErrorMsg(null)
    try { await reviewApi.recluster(nbId); setSelCid(null); setCDetail(null); await loadAll(nbId) }
    catch(e:any){ showErr('重聚类失败: '+e?.message) } finally { setReclustering(false) }
  }

  // ── 出题 ──
  const requestQuiz = (clusterId: number, scope: string, count: number) => {
    if (scope === 'errors') { openWrongModal(clusterId); return }
    setConfirmModal({ clusterId, scope, count })
  }
  const startQuiz = async (clusterId: number, scope: string, count: number) => {
    setConfirmModal(null); setGenerating(true)
    setGrade(null); setAnswers({}); setNoteRatings({}); setRatingsDone(false); setQuizScope(scope)
    try {
      const res = await reviewApi.generate(clusterId, scope, count)
      setQuizId(res.quiz_id); setQuestions(res.questions); setSelCid(clusterId)
      saveQuiz({ quizId:res.quiz_id, questions:res.questions, answers:{}, grade:null, scope, clusterId, noteRatings:{}, ratingsSubmitted:false, timestamp:Date.now() })
    } catch(e:any){ showErr('出题失败: '+e?.message) } finally { setGenerating(false) }
  }
  const submitAnswers = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(([qid,a]) => ({ question_id:qid, answer:a }))
    try {
      const res = await reviewApi.grade(quizId, attempts)
      setGrade(res)
      saveQuiz({ quizId, questions, answers, grade:res, scope:quizScope, clusterId:selCid!, noteRatings, ratingsSubmitted:false, timestamp:Date.now() })
    } catch(e:any){ showErr('批改失败: '+e?.message) }
  }
  const submitRatings = async () => {
    if (!quizId) return
    const attempts: QuizAttempt[] = Object.entries(answers).map(([qid,a]) => ({ question_id:qid, answer:a }))
    const rts = Object.entries(noteRatings).map(([nid,r]) => ({ note_id:Number(nid), rating:r }))
    try {
      const res = await reviewApi.grade(quizId, attempts, rts)
      setGrade(res); setRatingsDone(true); clearQuiz()
      if (nbId) await loadAll(nbId)
    } catch(e:any){ showErr('提交评分失败: '+e?.message) }
  }
  const backToList = () => { clearQuiz(); setQuizId(null); setQuestions([]); setAnswers({}); setGrade(null); setNoteRatings({}); setRatingsDone(false); if (nbId) loadAll(nbId) }

  // ── 错题弹窗 ──
  const openWrongModal = async (clusterId: number) => {
    try { const r = await reviewApi.wrongQuestions(nbId!, clusterId); setWq(r.questions||[]); setWrongModal(true) }
    catch(e:any){ showErr('加载错题失败: '+e?.message) }
  }
  const markWrongDone = async () => {
    const ids = wq.map(w => w.id)
    if (ids.length === 0) { setWrongModal(false); return }
    try { await reviewApi.markWrongReviewed(ids); setWrongModal(false) } catch(e:any){ showErr(e?.message||'') }
  }

  // ── 收藏 ──
  const addBookmark = async (noteId: number, question: string, explanation: string, clusterId: number|null) => {
    if (!nbId) return
    try { await reviewApi.addBookmark({ notebook_id:nbId, note_id:noteId, question, explanation, cluster_id:clusterId })
      const r = await reviewApi.bookmarks(nbId); setBookmarks(r.bookmarks||[]) }
    catch(e:any){ showErr('收藏失败: '+e?.message) }
  }
  const removeBookmark = async (bmId: number) => {
    try { await reviewApi.removeBookmark(bmId); setBookmarks(p => p.filter(b=>b.id!==bmId)) }
    catch(e:any){ showErr('取消收藏失败: '+e?.message) }
  }

  // ── 渲染 ──
  const hasQuiz = questions.length > 0

  return (
    <div className="flex h-full gap-4">
      {/* 左侧栏 */}
      <aside className="w-[230px] shrink-0 border-r pr-2 flex flex-col">
        <div className="flex items-center justify-between mb-2 px-1">
          <h2 className="font-semibold text-sm flex items-center gap-2"><Brain className="size-4"/>概念簇</h2>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={recluster} disabled={reclustering} title="重聚类">
            <RefreshCw className={`size-3 ${reclustering?'animate-spin':''}`}/>
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {clusters.length===0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm px-2">
              <Brain className="size-8 mx-auto mb-2 opacity-30"/>
              {loading?'加载中...':'暂无概念簇，请导入笔记后点击重聚类'}
            </div>
          ) : (
            <div className="space-y-0.5">
              {clusters.map(c => {
                const dueCount = dueData?.clusters?.find(d=>d.cluster_id===c.id)?.due_count||0
                const m = c.mastery; const sel = selCid===c.id&&!hasQuiz
                return (
                  <button key={c.id} onClick={()=>selectCluster(c.id)}
                    className={`w-full text-left px-2 py-2 rounded-md text-sm transition-colors
                      ${sel?'bg-primary/10 border border-primary/30':'hover:bg-accent border border-transparent'}`}>
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium truncate text-xs">{c.name}</span>
                      <div className="flex items-center gap-1 shrink-0">
                        {dueCount>0&&<Badge variant="default" className="text-[10px] h-4 px-1">{dueCount}</Badge>}
                        {m&&<span className="text-[10px] text-muted-foreground">{c.note_count}篇</span>}
                      </div>
                    </div>
                    {m&&m.total>0&&(
                      <div className="flex items-center gap-1 mt-1">
                        <div className="flex-1 h-1 rounded-full overflow-hidden bg-muted flex">
                          {m.new>0&&<div className="bg-red-400 h-full" style={{width:`${(m.new/m.total)*100}%`}}/>}
                          {m.learning>0&&<div className="bg-amber-400 h-full" style={{width:`${(m.learning/m.total)*100}%`}}/>}
                          {m.young>0&&<div className="bg-green-400 h-full" style={{width:`${(m.young/m.total)*100}%`}}/>}
                          {m.mature>0&&<div className="bg-blue-400 h-full" style={{width:`${(m.mature/m.total)*100}%`}}/>}
                        </div>
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </ScrollArea>
        <div className="pt-2 border-t">
          <Button variant="outline" size="sm" className="w-full text-xs h-7" onClick={recluster} disabled={reclustering}>
            <RefreshCw className={`size-3 mr-1 ${reclustering?'animate-spin':''}`}/>{reclustering?'聚类中...':'重聚类'}
          </Button>
        </div>
      </aside>

      {/* 右侧 */}
      <main className="flex-1 flex flex-col min-w-0">
        <div className="px-1 pt-2 pb-1 flex items-center gap-3 flex-wrap">
          <label className="text-xs text-muted-foreground shrink-0">知识库:</label>
          <select className="border rounded-md px-2 py-1 text-xs bg-background max-w-[160px]"
            value={nbId??''} onChange={e=>{const id=Number(e.target.value);if(id)switchNb(id)}}>
            {notebooks.length===0&&<option value="">无可用知识库</option>}
            {notebooks.map(nb=><option key={nb.id} value={nb.id}>{nb.name}</option>)}
          </select>
          {streak&&(
            <span className="text-xs flex items-center gap-1 ml-auto">
              <Flame className={`size-3.5 ${streak.current_streak>0?'text-orange-500':'text-muted-foreground'}`}/>
              <span className="font-medium">{streak.current_streak}天</span>
              <span className="text-muted-foreground">最长{streak.longest_streak}天</span>
            </span>
          )}
        </div>
        {errorMsg&&(
          <div className="mx-1 mb-1 px-3 py-2 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-md text-sm text-red-700 dark:text-red-400 flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0"/><span>{errorMsg}</span>
            <button className="ml-auto shrink-0 hover:opacity-70" onClick={()=>setErrorMsg(null)}>✕</button>
          </div>
        )}
        <ScrollArea className="flex-1">
          {generating ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="size-6 animate-spin mr-2"/><span className="text-muted-foreground">AI 正在出题...</span></div>
          ) : hasQuiz ? (
            <QuizPanel questions={questions} answers={answers} setAnswers={setAnswers} grade={grade}
              noteRatings={noteRatings} setNoteRatings={setNoteRatings} ratingsDone={ratingsDone}
              scope={quizScope} onSubmit={submitAnswers} onSubmitRatings={submitRatings} onBack={backToList}
              onAddBookmark={addBookmark} onRetry={()=>startQuiz(selCid!,quizScope,questions.length)} selCid={selCid}/>
          ) : cDetail ? (
            <div className="space-y-4 max-w-3xl pr-2">
              <ClusterPanel detail={cDetail} dueData={dueData} onRequestQuiz={requestQuiz}/>
            </div>
          ) : (
            <div className="space-y-4 max-w-3xl pr-2">
              {stats && <StatsPanel stats={stats}/>}
              {dueData && dueData.total_due > 0 && (
                <DuePanel dueData={dueData} onSelect={selectCluster} onRequestQuiz={requestQuiz}/>
              )}
              <BookmarkPanel bookmarks={bookmarks} onRemove={removeBookmark}
                onNav={(nid)=>{const s=useNotesStore.getState();s.openTab(nid,'');document.querySelector('[data-nav-notes]')?.dispatchEvent(new MouseEvent('click',{bubbles:true}))}}/>
            </div>
          )}
        </ScrollArea>
      </main>

      {/* 出题确认弹窗 */}
      {confirmModal&&(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={()=>setConfirmModal(null)}>
          <div className="bg-background border rounded-lg shadow-xl p-6 max-w-sm w-full mx-4" onClick={e=>e.stopPropagation()}>
            <h3 className="font-semibold text-base mb-2">{SCOPE_META[confirmModal.scope]?.icon}<span className="ml-2">{SCOPE_META[confirmModal.scope]?.label}</span></h3>
            <p className="text-sm text-muted-foreground mb-1">{SCOPE_META[confirmModal.scope]?.desc}</p>
            <p className="text-sm mb-4">从「<strong>{clusters.find(c=>c.id===confirmModal.clusterId)?.name||'未知簇'}</strong>」出 {confirmModal.count} 道题</p>
            <div className="flex gap-2 justify-end">
              <Button variant="outline" size="sm" onClick={()=>setConfirmModal(null)}>取消</Button>
              <Button size="sm" onClick={()=>startQuiz(confirmModal.clusterId, confirmModal.scope, confirmModal.count)}>开始出题</Button>
            </div>
          </div>
        </div>
      )}

      {/* 错题重温弹窗 */}
      {wrongModal&&(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={()=>setWrongModal(false)}>
          <div className="bg-background border rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col" onClick={e=>e.stopPropagation()}>
            <h3 className="font-semibold text-base mb-3 flex items-center gap-2"><AlertCircle className="size-4"/>错题重温</h3>
            <ScrollArea className="flex-1 max-h-[60vh]">
              {wq.length===0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">暂无错题 🎉</p>
              ) : (
                <div className="space-y-4">
                  {wq.map((w,i)=>(
                    <div key={w.id} className="border rounded-lg p-3 text-sm">
                      <p className="font-medium mb-2">{i+1}. {w.question}</p>
                      <div className="space-y-1 mb-2">
                        {w.options.map(opt=>{
                          const letter=opt.charAt(0)
                          const isCorrect=letter===w.answer, isUser=letter===w.user_answer
                          return <div key={letter} className={`px-2 py-1 rounded text-xs border
                            ${isCorrect?'bg-green-50 border-green-300 dark:bg-green-950/30':''}
                            ${isUser&&!isCorrect?'bg-red-50 border-red-300 dark:bg-red-950/30':''}`}>
                            {opt} {isCorrect?'✓':''} {isUser&&!isCorrect?'← 你的答案':''}
                          </div>
                        })}
                      </div>
                      {w.explanation&&<p className="text-xs text-muted-foreground mb-1">{w.explanation}</p>}
                      <span className="text-xs text-muted-foreground">📝 {w.note_title}</span>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
            <div className="flex gap-2 justify-end mt-3 pt-3 border-t">
              <Button variant="outline" size="sm" onClick={()=>setWrongModal(false)}>关闭</Button>
              {wq.length>0&&<Button size="sm" onClick={markWrongDone}>标记全部已复习</Button>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 统计面板 ──────────────────────────────────

function StatsPanel({ stats }: { stats: ReviewStats }) {
  const total = stats.total_notes
  if (total === 0) return null
  return (
    <div className="border rounded-lg p-4">
      <h3 className="font-semibold text-sm flex items-center gap-2 mb-3"><BarChart3 className="size-4"/>学习概览</h3>
      <div className="grid grid-cols-4 gap-2 mb-3">
        {MASTERY_ORDER.map(k => (
          <div key={k} className="text-center">
            <div className={`text-lg font-bold ${k==='new'?'text-red-600':k==='learning'?'text-amber-600':k==='young'?'text-green-600':'text-blue-600'}`}>
              {stats.by_mastery[k]||0}
            </div>
            <div className="text-[10px] text-muted-foreground">{MASTERY_LABEL[k]}</div>
          </div>
        ))}
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-muted mb-3">
        {MASTERY_ORDER.map(k => {
          const pct = total>0?(stats.by_mastery[k]||0)/total*100:0
          const cls = k==='new'?'bg-red-400':k==='learning'?'bg-amber-400':k==='young'?'bg-green-400':'bg-blue-400'
          return pct>0?<div key={k} className={cls} style={{width:`${pct}%`}}/>:null
        })}
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>共 {total} 篇笔记</span>
        <span>近7天复习 {stats.recent_reviews_7d} 篇</span>
      </div>
    </div>
  )
}

// ── 簇详情面板 ────────────────────────────────

function ClusterPanel({ detail, dueData, onRequestQuiz }: {
  detail: ClusterDetail; dueData: DueReviewsResponse|null
  onRequestQuiz: (clusterId:number,scope:string,count:number)=>void
}) {
  const m = detail.mastery; const total = m?.total||0
  const dueCount = dueData?.clusters?.find(d=>d.cluster_id===detail.id)?.due_count||0
  const sorted = sortNotes(detail.notes||[])

  return (
    <div className="space-y-4">
      <div className="border rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-base">{detail.name}</h3>
          <span className="text-sm text-muted-foreground">{total} 篇笔记</span>
        </div>
        {m && total>0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs">
              {MASTERY_ORDER.map(k => (
                <span key={k} className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${k==='new'?'text-red-600 bg-red-50':k==='learning'?'text-amber-600 bg-amber-50':k==='young'?'text-green-600 bg-green-50':'text-blue-600 bg-blue-50'}`}>
                  {MASTERY_LABEL[k]} {(m as any)[k]}
                </span>
              ))}
              <span className="text-primary font-medium ml-auto">
                {Math.round(((m.young+m.mature)/total)*100)}% 已掌握
              </span>
            </div>
            <div className="flex h-2 rounded-full overflow-hidden bg-muted">
              {m.new>0&&<div className="bg-red-400 h-full" style={{width:`${(m.new/total)*100}%`}}/>}
              {m.learning>0&&<div className="bg-amber-400 h-full" style={{width:`${(m.learning/total)*100}%`}}/>}
              {m.young>0&&<div className="bg-green-400 h-full" style={{width:`${(m.young/total)*100}%`}}/>}
              {m.mature>0&&<div className="bg-blue-400 h-full" style={{width:`${(m.mature/total)*100}%`}}/>}
            </div>
          </div>
        )}
      </div>

      {sorted.length>0&&(
        <div className="border rounded-lg p-4">
          <h4 className="text-sm font-medium mb-2">📋 笔记列表</h4>
          <div className="space-y-1 max-h-[300px] overflow-auto">
            {sorted.map(n=>{
              const sm2=n.sm2; const isDue=sm2?.next_review_at&&new Date(sm2.next_review_at)<=new Date()
              return (
                <div key={n.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-accent text-sm">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className={`text-[10px] px-1 py-0.5 rounded font-medium shrink-0 ${isDue?'text-orange-600 bg-orange-50 dark:bg-orange-950/30':MASTERY_COLORS[n.mastery]}`}>
                      {isDue?'到期':MASTERY_LABEL[n.mastery]}
                    </span>
                    <span className="truncate">{n.title}</span>
                  </div>
                  <div className="text-xs text-muted-foreground shrink-0 ml-2 text-right">
                    {sm2?(isDue?null:<span>{sm2.interval_days}天后</span>):<span>未复习</span>}
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
          {(Object.keys(SCOPE_META) as Array<keyof typeof SCOPE_META>).map(scope=>{
            const info=SCOPE_META[scope]
            return (
              <Button key={scope} variant={scope==='due'?'default':'outline'} size="sm"
                onClick={()=>onRequestQuiz(detail.id, scope, 10)} className="justify-start h-auto py-2">
                <span className="flex items-center gap-1.5">{info.icon}<span>{info.label}</span>
                  {scope==='due'&&dueCount>0&&<Badge variant="secondary" className="text-[10px] h-4 px-1">{dueCount}篇</Badge>}
                </span>
              </Button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── 今日到期 ──────────────────────────────────

function DuePanel({ dueData, onSelect, onRequestQuiz }: {
  dueData: DueReviewsResponse; onSelect:(id:number)=>void; onRequestQuiz:(cid:number,scope:string,count:number)=>void
}) {
  return (
    <section>
      <h3 className="font-semibold text-base flex items-center gap-2 mb-3"><BookOpen className="size-4"/>今日待复习</h3>
      <div className="space-y-3">
        {dueData.clusters?.map(dc=>(
          <div key={dc.cluster_id} className="border rounded-lg p-4">
            <button className="font-medium text-left hover:text-primary" onClick={()=>onSelect(dc.cluster_id)}>{dc.cluster_name}<ChevronRight className="size-3 inline ml-1"/></button>
            <span className="text-sm text-muted-foreground ml-2">{dc.due_count}/{dc.note_count} 篇到期</span>
            <div className="flex gap-2 mt-3">
              <Button size="sm" onClick={()=>onRequestQuiz(dc.cluster_id,'due',10)}><BookOpen className="size-3 mr-1"/>到期复习</Button>
              <Button size="sm" variant="outline" onClick={()=>onRequestQuiz(dc.cluster_id,'all',10)}><Zap className="size-3 mr-1"/>集中突击</Button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── 收藏 ──────────────────────────────────────

function BookmarkPanel({ bookmarks, onRemove, onNav }: {
  bookmarks: KnowledgeBookmark[]; onRemove:(id:number)=>void; onNav:(nid:number)=>void
}) {
  if (bookmarks.length===0) return null
  return (
    <section>
      <h3 className="font-semibold text-base flex items-center gap-2 mb-3"><Bookmark className="size-4"/>知识点收藏 ({bookmarks.length})</h3>
      <div className="space-y-2">
        {bookmarks.map(bm=>(
          <div key={bm.id} className="border rounded-lg p-3 text-sm">
            <p className="mb-1">{bm.question}</p>
            {bm.explanation&&<p className="text-xs text-muted-foreground mb-2">{bm.explanation}</p>}
            <div className="flex items-center gap-2">
              <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={()=>onNav(bm.note_id)}>📝 查看笔记</Button>
              <Button variant="ghost" size="sm" className="h-6 px-1 text-xs text-muted-foreground" onClick={()=>onRemove(bm.id)}><Trash2 className="size-3"/></Button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── 测验面板 ──────────────────────────────────

function QuizPanel({ questions, answers, setAnswers, grade, noteRatings, setNoteRatings, ratingsDone, scope,
  onSubmit, onSubmitRatings, onBack, onAddBookmark, onRetry, selCid }: {
  questions: any[]; answers: Record<string,string>; setAnswers:(a:Record<string,string>)=>void
  grade: ReviewGradeResponse|null; noteRatings: Record<number,string>; setNoteRatings:(r:Record<number,string>)=>void
  ratingsDone: boolean; scope: string; onSubmit:()=>void; onSubmitRatings:()=>void; onBack:()=>void
  onAddBookmark:(nid:number,q:string,e:string,cid:number|null)=>void; onRetry:()=>void; selCid: number|null
}) {
  const unanswered = questions.filter(q=>!answers[q.id]).length
  const info = SCOPE_META[scope]||SCOPE_META.due
  const [bq, setBq] = useState<Set<string>>(new Set())
  const noteSet = new Map<number,{title:string;correct:number;total:number}>()
  questions.forEach(q=>{if(q.note_id){const e=noteSet.get(q.note_id)||{title:q.note_title||'未知',correct:0,total:0};e.total+=1;if(grade){const r=grade.results.find((r:any)=>r.question_id===q.id);if(r?.correct)e.correct+=1};noteSet.set(q.note_id,e)}})

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>← 返回</Button>
          <span className="text-sm text-muted-foreground flex items-center gap-1">{info.icon}{info.label} · {questions.length}题 · {unanswered}题未答</span>
        </div>
      </div>
      <div className="space-y-6">
        {questions.map((q,i)=>{
          const result = grade?.results?.find((r:any)=>r.question_id===q.id)
          const bookmarked = bq.has(q.id)
          return (
            <div key={q.id} className={`border rounded-lg p-4 ${result?(result.correct?'border-green-200 bg-green-50 dark:bg-green-950/20':'border-red-200 bg-red-50 dark:bg-red-950/20'):''}`}>
              <p className="font-medium mb-3"><span className="text-muted-foreground mr-2">{i+1}.</span>{q.question}</p>
              <div className="grid grid-cols-1 gap-2">
                {(q.options as string[]|undefined)?.map(opt=>{
                  const letter=opt.charAt(0), sel=answers[q.id]===letter
                  const isCorrect=result?.answer===letter, isWrong=grade&&sel&&!result?.correct
                  return <button key={letter} disabled={!!grade} onClick={()=>setAnswers({...answers,[q.id]:letter})}
                    className={`text-left px-3 py-2 rounded-md text-sm border transition-colors
                      ${sel&&!grade?'bg-primary/10 border-primary':'hover:bg-accent border-transparent'}
                      ${isCorrect&&grade?'bg-green-100 border-green-400 dark:bg-green-900/30':''}
                      ${isWrong?'bg-red-100 border-red-400 dark:bg-red-900/30':''}`}>{opt}</button>
                })}
              </div>
              {result&&(
                <div className="mt-3 pt-3 border-t text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    {result.correct?<CheckCircle2 className="size-4 text-green-600"/>:<XCircle className="size-4 text-red-600"/>}
                    <span className={result.correct?'text-green-700 dark:text-green-400':'text-red-700 dark:text-red-400'}>
                      {result.correct?'正确':`正确答案：${result.answer}`}</span>
                    {!result.correct&&(
                      <button onClick={()=>{onAddBookmark(q.note_id,q.question,result.explanation,selCid);setBq(p=>new Set([...p,q.id]))}}
                        disabled={bookmarked} className="ml-auto text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-accent disabled:opacity-50">
                        <BookmarkPlus className="size-3.5"/>{bookmarked?'已收藏':'收藏知识点'}
                      </button>
                    )}
                  </div>
                  {result.explanation&&<p className="text-muted-foreground mt-1">{result.explanation}</p>}
                  {q.note_id&&<span className="text-xs text-muted-foreground mt-1 inline-block">📝 {q.note_title||`#${q.note_id}`}</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {!grade&&questions.length>0&&(
        <div className="flex justify-center pt-4">
          <Button size="lg" onClick={onSubmit} disabled={unanswered>0}>提交批改 {unanswered>0&&`（${unanswered}题未答）`}</Button>
        </div>
      )}
      {grade&&!ratingsDone&&noteSet.size>0&&(
        <div className="border rounded-lg p-6 space-y-4">
          <div className="text-center">
            <div className="text-3xl font-bold mb-1">{grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span></div>
            <p className="text-muted-foreground text-sm">{grade.correct}/{grade.total}题 · {grade.summary}</p>
          </div><Separator/>
          <div><h4 className="text-sm font-medium mb-3">对每篇笔记的回忆质量评价：</h4>
            <div className="space-y-3">
              {Array.from(noteSet.entries()).map(([nid,inf])=>(
                <div key={nid} className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0"><div className="text-sm truncate">{inf.title}</div><div className="text-xs text-muted-foreground">出题{inf.total}道，对{inf.correct}道</div></div>
                  <div className="flex gap-1">
                    {RATING_OPTIONS.map(opt=>(
                      <button key={opt.key} onClick={()=>setNoteRatings({...noteRatings,[nid]:opt.key})}
                        className={`px-2 py-1 rounded-md text-xs border transition-colors ${noteRatings[nid]===opt.key?opt.color:'hover:bg-accent border-transparent'}`}
                        title={opt.hint}>{opt.label}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-center pt-2"><Button onClick={onSubmitRatings} disabled={Object.keys(noteRatings).length===0}>确认提交</Button></div>
        </div>
      )}
      {grade&&(ratingsDone||noteSet.size===0)&&(
        <div className="border rounded-lg p-6 text-center space-y-3">
          <div className="text-4xl font-bold">{grade.score}<span className="text-lg text-muted-foreground font-normal"> 分</span></div>
          <p className="text-muted-foreground">{grade.correct}/{grade.total}题正确</p><p className="text-sm text-muted-foreground">{grade.summary}</p>
          {grade.updated_states&&grade.updated_states.length>0&&(
            <div className="text-xs text-muted-foreground space-y-1 border-t pt-3">
              <div className="font-medium mb-1">SM-2 状态更新：</div>
              {grade.updated_states.map(s=>(
                <div key={s.note_id} className="flex items-center justify-center gap-1">
                  <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${s.mastery_before==='new'?'text-red-600 bg-red-50':s.mastery_before==='learning'?'text-amber-600 bg-amber-50':s.mastery_before==='young'?'text-green-600 bg-green-50':'text-blue-600 bg-blue-50'}`}>{MASTERY_LABEL[s.mastery_before]}</span>
                  <span>→</span>
                  <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${s.mastery_after==='new'?'text-red-600 bg-red-50':s.mastery_after==='learning'?'text-amber-600 bg-amber-50':s.mastery_after==='young'?'text-green-600 bg-green-50':'text-blue-600 bg-blue-50'}`}>{MASTERY_LABEL[s.mastery_after]}</span>
                  <span>{s.rating} · {s.old_interval}d→{s.new_interval}d
                    {s.next_review_at&&` (下次 ${new Date(s.next_review_at).toLocaleDateString('zh-CN')})`}</span>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-center gap-3 pt-2">
            <Button onClick={onBack} variant="outline">返回列表</Button><Button onClick={onRetry}>再做一套</Button>
          </div>
        </div>
      )}
    </div>
  )
}
