/**
 * QuizPage — AI 出题自测（P6）
 * ---------------------------
 * 选择出题范围（知识库 或 知识库内某文件夹，文件夹递归包含子文件夹笔记）
 * → AI 生成题目（5 选择 + 2 简答）→ 答题 → 批改 → 查看解析与复习建议。
 *
 * 范围规则: 选择文件夹 = 该文件夹 + 所有子文件夹下的全部笔记。
 */
import { useEffect, useState, useCallback } from 'react'
import { notebooksApi, quizApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import {
  GraduationCap, Loader2, Check, X, Folder, ClipboardList, Library,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Notebook, FolderNode, QuizGenerateResponse, QuizGradeResponse } from '@/types'

/** 递归统计文件夹笔记数（含所有子文件夹） */
function countFolderNotes(folder: FolderNode): number {
  return (
    (folder.notes?.length || 0) +
    (folder.children || []).reduce((sum, c) => sum + countFolderNotes(c), 0)
  )
}

/** 扁平化文件夹树（含层级深度，供下拉菜单展示） */
interface FlatFolder { path: string; name: string; count: number; depth: number }
function flattenFolders(folders: FolderNode[], depth = 0): FlatFolder[] {
  const out: FlatFolder[] = []
  for (const f of folders) {
    out.push({ path: f.path, name: f.name, count: countFolderNotes(f), depth })
    out.push(...flattenFolders(f.children || [], depth + 1))
  }
  return out
}

/** 「整个知识库」的下拉占位值 */
const SCOPE_ALL = '__all__'

export default function QuizPage() {
  // ---- 出题范围 ----
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [notebookId, setNotebookId] = useState<number | null>(null)
  const [folderTree, setFolderTree] = useState<FolderNode[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null) // null = 整个知识库
  const [scopeNotes, setScopeNotes] = useState<number | null>(null) // 选中范围笔记数
  const [notebookTotal, setNotebookTotal] = useState<number>(0) // 整个知识库笔记数

  // ---- 出题 / 答题 ----
  const [quiz, setQuiz] = useState<QuizGenerateResponse | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [grade, setGrade] = useState<QuizGradeResponse | null>(null)
  const [generating, setGenerating] = useState(false)
  const [grading, setGrading] = useState(false)

  // ---- 加载知识库列表 ----
  useEffect(() => {
    notebooksApi.list()
      .then((res) => setNotebooks(res.notebooks || []))
      .catch(() => toast.error('加载知识库列表失败'))
  }, [])

  // ---- 切换知识库 → 加载文件夹树 ----
  const handleNotebookChange = useCallback(async (id: number) => {
    setNotebookId(id)
    setSelectedFolder(null)
    setFolderTree([])
    setScopeNotes(null)
    setQuiz(null)
    setGrade(null)
    try {
      const res = await notebooksApi.folderTree(id)
      const folders = res.folders || []
      setFolderTree(folders)
      // 整个知识库的笔记数 = 文件夹 + 根目录（存起来供「整个知识库」复用）
      const folderCount = folders.reduce((s, f) => s + countFolderNotes(f), 0)
      const total = folderCount + (res.root_notes?.length || 0)
      setNotebookTotal(total)
      setScopeNotes(total)
    } catch {
      toast.error('加载文件夹树失败')
    }
  }, [])

  /** 选中范围（下拉菜单）：path=null 整个知识库；否则该文件夹（含子文件夹递归） */
  const handleSelectScope = (value: string | null) => {
    if (!value || value === SCOPE_ALL) {
      setSelectedFolder(null)
      setScopeNotes(notebookTotal)
    } else {
      setSelectedFolder(value)
      const flat = flattenFolders(folderTree)
      const target = flat.find((f) => f.path === value)
      setScopeNotes(target?.count ?? 0)
    }
    setQuiz(null)
    setGrade(null)
  }

  // ---- 下拉菜单的文件夹选项（含层级缩进） ----
  const flatFolders = flattenFolders(folderTree)

  // ---- 生成题目 ----
  const handleGenerate = useCallback(async () => {
    if (!notebookId) {
      toast.error('请先选择知识库')
      return
    }
    if (scopeNotes === 0) {
      toast.error('该范围内没有笔记，无法出题')
      return
    }
    setGenerating(true)
    setQuiz(null)
    setGrade(null)
    setAnswers({})
    try {
      const res = await quizApi.generate(notebookId, selectedFolder)
      setQuiz(res)
      toast.success(`已生成 ${res.questions.length} 道题（基于 ${res.note_count} 篇笔记）`)
    } catch (e) {
      toast.error('出题失败: ' + (e as Error).message)
    } finally {
      setGenerating(false)
    }
  }, [notebookId, selectedFolder, scopeNotes])

  // ---- 提交批改 ----
  const handleGrade = useCallback(async () => {
    if (!quiz) return
    const answered = Object.keys(answers).length
    if (answered < quiz.questions.length) {
      toast.warning(`还有 ${quiz.questions.length - answered} 题未作答`)
      return
    }
    setGrading(true)
    try {
      const attempts = Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer }))
      const res = await quizApi.grade(quiz.quiz_id, attempts)
      setGrade(res)
      toast.success(`批改完成: ${res.correct}/${res.total} 正确`)
    } catch (e) {
      toast.error('批改失败: ' + (e as Error).message)
    } finally {
      setGrading(false)
    }
  }, [quiz, answers])

  // 选中范围的显示名（下拉已直观展示；这里用于按钮下方小字）
  const scopeLabel = selectedFolder
    ? flattenFolders(folderTree).find((f) => f.path === selectedFolder)?.name || selectedFolder
    : notebooks.find((n) => n.id === notebookId)?.name || ''

  return (
    <div className="flex h-full flex-col gap-4">
      {/* ======== ① 出题范围选择 ======== */}
      <Card className="shrink-0">
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            {/* 知识库选择 */}
            <div className="w-[260px] shrink-0">
              <p className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1">
                <Library className="size-3" /> 知识库
              </p>
              <Select
                value={notebookId ? String(notebookId) : undefined}
                onValueChange={(v) => handleNotebookChange(Number(v))}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="选择知识库" />
                </SelectTrigger>
                <SelectContent>
                  {notebooks.map((nb) => (
                    <SelectItem key={nb.id} value={String(nb.id)}>
                      {nb.name}（{nb.note_count ?? 0} 篇）
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 出题范围（下拉菜单） */}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-muted-foreground mb-1.5 flex items-center gap-1">
                <Folder className="size-3" /> 出题范围
                <span className="text-[10px] opacity-70">（选择文件夹 = 包含其所有子文件夹笔记）</span>
              </p>
              <Select
                value={notebookId ? selectedFolder ?? SCOPE_ALL : undefined}
                onValueChange={(v) => handleSelectScope(v)}
                disabled={!notebookId}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="选择出题范围" />
                </SelectTrigger>
                <SelectContent>
                  {/* 整个知识库 */}
                  <SelectItem value={SCOPE_ALL}>
                    <span className="flex items-center gap-1.5">
                      <Library className="size-3.5" />
                      整个知识库（{notebookTotal} 篇）
                    </span>
                  </SelectItem>
                  {/* 所有文件夹（含层级缩进） */}
                  {flatFolders.map((f) => (
                    <SelectItem key={f.path} value={f.path}>
                      <span
                        className="flex items-center gap-1.5"
                        style={{ paddingLeft: `${f.depth * 16}px` }}
                      >
                        <Folder className="size-3.5 shrink-0 text-amber-500" />
                        {f.name}（{f.count} 篇）
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!notebookId && (
                <p className="text-[10px] text-muted-foreground mt-1">请先选择知识库</p>
              )}
            </div>

            {/* 生成按钮 */}
            <div className="w-[140px] shrink-0 flex flex-col justify-end gap-2">
              <Button
                onClick={handleGenerate}
                disabled={!notebookId || generating}
                className="gap-2"
              >
                {generating ? <Loader2 className="size-4 animate-spin" /> : <GraduationCap className="size-4" />}
                {generating ? '出题中...' : '生成题目'}
              </Button>
              <p className="text-[10px] text-muted-foreground text-center">
                范围: {scopeLabel || '未选择'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ======== ② 答题区域 ======== */}
      <Card className="flex-1 min-h-0 flex flex-col">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <ClipboardList className="size-4" />
            {quiz ? `自测题（${answers ? Object.keys(answers).length : 0}/${quiz.questions.length} 已作答）` : '自测题'}
            {quiz && <Badge variant="secondary" className="text-[10px]">基于 {quiz.note_count} 篇笔记</Badge>}
          </CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="p-0 flex-1 min-h-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-4">
              {!quiz && (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <GraduationCap className="size-10 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">选择知识库或文件夹，点击「生成题目」开始自测</p>
                  <p className="text-xs text-muted-foreground mt-1">AI 将基于范围内的笔记生成 5 道选择 + 2 道简答</p>
                </div>
              )}

              {quiz && quiz.questions.map((q, i) => (
                <div key={q.id} className="rounded-lg border p-3">
                  <p className="text-sm font-medium mb-2 flex gap-2">
                    <Badge variant="outline" className="shrink-0 h-5 min-w-5 justify-center">
                      {q.type === 'choice' ? '选' : '答'}
                    </Badge>
                    <span className="flex-1">{i + 1}. {q.question}</span>
                  </p>

                  {/* 选择题：选项按钮组 */}
                  {q.type === 'choice' && q.options && (
                    <div className="grid grid-cols-1 gap-1.5 mt-2">
                      {q.options.map((opt, oi) => {
                        const letter = String.fromCharCode(65 + oi) // A/B/C/D
                        const isPicked = answers[q.id] === letter
                        const graded = grade?.results.find((r) => r.question_id === q.id)
                        const isCorrect = graded && graded.correct && isPicked
                        const isWrong = graded && !graded.correct && isPicked
                        const showRight = graded && graded.correct && graded.answer === letter && !isPicked
                        return (
                          <button
                            key={letter}
                            type="button"
                            disabled={!!grade}
                            onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: letter }))}
                            className={cn(
                              'flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-left text-sm transition-colors',
                              isPicked && !grade
                                ? 'border-primary bg-primary/10'
                                : 'hover:bg-accent',
                              isCorrect && 'border-green-500 bg-green-500/10',
                              isWrong && 'border-red-500 bg-red-500/10',
                              showRight && 'border-green-500 bg-green-500/10',
                            )}
                          >
                            <span className={cn(
                              'flex items-center justify-center size-4 shrink-0 mt-0.5 rounded-full text-[10px] font-bold border',
                              isCorrect && 'border-green-500 text-green-600',
                              isWrong && 'border-red-500 text-red-600',
                            )}>{letter}</span>
                            <span className="flex-1">{opt.replace(/^[A-D][.、]\s*/, '')}</span>
                            {isCorrect && <Check className="size-3.5 text-green-600 shrink-0 mt-0.5" />}
                            {isWrong && <X className="size-3.5 text-red-600 shrink-0 mt-0.5" />}
                          </button>
                        )
                      })}
                    </div>
                  )}

                  {/* 简答题：文本框 */}
                  {q.type === 'short' && (
                    <Textarea
                      disabled={!!grade}
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder="请输入你的答案..."
                      className="mt-2 text-sm min-h-[70px]"
                    />
                  )}

                  {/* 批改结果 */}
                  {grade && (() => {
                    const r = grade.results.find((x) => x.question_id === q.id)
                    if (!r) return null
                    // 选择题答案 → 展示完整选项文本
                    const fullAnswer = q.type === 'choice' && q.options
                      ? q.options.find((o) => o.startsWith(r.answer)) || r.answer
                      : r.answer
                    return (
                      <div className={cn(
                        'mt-2 rounded-md p-2 text-xs space-y-1',
                        r.correct ? 'bg-green-500/10' : 'bg-red-500/10',
                      )}>
                        <p className={cn('font-medium', r.correct ? 'text-green-600' : 'text-red-600')}>
                          {r.correct ? '✓ 回答正确' : '✗ 回答有误'}
                          {r.score !== undefined && (
                            <span className="ml-2 font-normal">得分 {r.score}/10</span>
                          )}
                        </p>
                        {r.user_answer && (
                          <p className="text-muted-foreground">
                            你的答案: <span className={r.correct ? '' : 'line-through'}>{r.user_answer}</span>
                          </p>
                        )}
                        <p>参考答案: {fullAnswer}</p>
                        {r.explanation && <p className="text-muted-foreground">解析: {r.explanation}</p>}
                        {r.comment && <p className="text-muted-foreground">点评: {r.comment}</p>}
                      </div>
                    )
                  })()}
                </div>
              ))}

              {/* 提交 / 结果 */}
              {quiz && !grade && (
                <div className="flex justify-center pb-4">
                  <Button onClick={handleGrade} disabled={grading} className="gap-2 px-8">
                    {grading ? <Loader2 className="size-4 animate-spin" /> : <GraduationCap className="size-4" />}
                    {grading ? '批改中...' : '提交批改'}
                  </Button>
                </div>
              )}

              {/* 成绩总结 */}
              {grade && (
                <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center justify-center size-16 rounded-full bg-primary/10 border-2 border-primary shrink-0">
                      <span className="text-xl font-bold text-primary">{grade.score}分</span>
                    </div>
                    <div>
                      <p className="text-sm font-medium">正确 {grade.correct}/{grade.total}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{grade.summary}</p>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="outline" onClick={() => { setQuiz(null); setGrade(null); setAnswers({}) }}>
                      再做一套
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setGrade(null)}>
                      查看错题解析
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
