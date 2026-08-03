/**
 * MasteryPage — 知识进阶页面
 * ---------------------------
 * Agent 对话式评估概念掌握度。
 * 左侧: 概念列表（掌握度卡片 + 选择/自定义概念）
 * 右侧: 评估对话区（SSE 流式）
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNotesStore } from '@/stores/notes'
import { masteryApi } from '@/lib/api'
import { masteryAssessStream } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
  Brain,
  Send,
  Plus,
  ChevronRight,
  TrendingUp,
  Target,
  Sparkles,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import type { ConceptMastery, MasterySSEEvent } from '@/types'

export default function MasteryPage() {
  const { activeNotebookId } = useNotesStore()
  const [concepts, setConcepts] = useState<ConceptMastery[]>([])
  const [loading, setLoading] = useState(false)
  const [assessing, setAssessing] = useState(false)
  const [selectedConcept, setSelectedConcept] = useState<string | null>(null)
  const [customConcept, setCustomConcept] = useState('')
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([])
  const [reply, setReply] = useState('')
  const [agentTyping, setAgentTyping] = useState('')
  const [score, setScore] = useState<{ score: number; strengths: string[]; weaknesses: string[]; summary: string } | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // ---- 加载概念列表 ----
  const fetchConcepts = useCallback(async () => {
    if (!activeNotebookId) return
    setLoading(true)
    try {
      const res = await masteryApi.concepts(activeNotebookId)
      setConcepts(res.concepts || [])
    } catch {
      // 静默
    } finally {
      setLoading(false)
    }
  }, [activeNotebookId])

  useEffect(() => { fetchConcepts() }, [fetchConcepts])

  // ---- 自动滚动 ----
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, agentTyping])

  // ---- 开始评估 ----
  const startAssessment = useCallback(async (concept: string) => {
    if (!activeNotebookId) {
      toast.error('请先选择笔记库')
      return
    }
    setSelectedConcept(concept)
    setAssessing(true)
    setMessages([])
    setAgentTyping('')
    setScore(null)
    setSessionId(null)

    try {
      for await (const evt of masteryAssessStream(concept, activeNotebookId, null, null)) {
        handleSSEEvent(evt)
      }
    } catch (e) {
      toast.error('评估失败: ' + (e as Error).message)
      setAssessing(false)
    }
  }, [activeNotebookId])

  // ---- 发送回复 ----
  const sendReply = useCallback(async () => {
    if (!reply.trim() || !activeNotebookId || !selectedConcept) return
    const msg = reply.trim()
    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setReply('')
    setAgentTyping('...')

    try {
      for await (const evt of masteryAssessStream(selectedConcept, activeNotebookId, sessionId, msg)) {
        handleSSEEvent(evt)
      }
    } catch (e) {
      toast.error('发送失败: ' + (e as Error).message)
      setAssessing(false)
    }
  }, [reply, activeNotebookId, selectedConcept, sessionId])

  // ---- SSE 事件处理 ----
  const handleSSEEvent = useCallback((evt: MasterySSEEvent) => {
    switch (evt.type) {
      case 'status':
        break // 状态提示跳过
      case 'token':
        setAgentTyping('') // 收到第一个 token 后清除 "思考中"
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: last.content + evt.content }]
          }
          return [...prev, { role: 'assistant', content: evt.content }]
        })
        break
      case 'score':
        setScore({
          score: evt.score,
          strengths: evt.strengths,
          weaknesses: evt.weaknesses,
          summary: evt.summary,
        })
        setSessionId(evt.session_id)
        setAssessing(false)
        fetchConcepts() // 刷新概念列表
        break
      case 'done':
        setSessionId(evt.session_id)
        break
      case 'error':
        toast.error(evt.content)
        setAssessing(false)
        break
    }
  }, [fetchConcepts])

  // ---- 评分圆环色 ----
  const scoreColor = (s: number) => {
    if (s >= 80) return 'text-emerald-500'
    if (s >= 60) return 'text-amber-500'
    return 'text-red-500'
  }

  return (
    <div className="flex h-full gap-4">
      {/* ======== 左侧：概念列表 ======== */}
      <div className="w-[280px] shrink-0 h-full border rounded-lg bg-card overflow-hidden flex flex-col">
        <div className="px-3 py-2.5 border-b shrink-0">
          <h2 className="text-sm font-semibold flex items-center gap-1.5">
            <Target className="size-3.5" />
            知识进阶
          </h2>
          <p className="text-[10px] text-muted-foreground mt-0.5">Agent 对话评估掌握度</p>
        </div>

        {/* 自定义概念输入 */}
        <div className="px-3 py-2 border-b shrink-0 flex gap-1.5">
          <Input
            value={customConcept}
            onChange={(e) => setCustomConcept(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && customConcept.trim()) startAssessment(customConcept.trim()) }}
            placeholder="输入概念名…"
            className="text-xs border h-7 focus-visible:ring-0 px-2"
          />
          <Button
            size="icon"
            className="size-7 shrink-0"
            onClick={() => customConcept.trim() && startAssessment(customConcept.trim())}
            disabled={assessing}
          >
            <Plus className="size-3.5" />
          </Button>
        </div>

        <ScrollArea className="flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
              加载中…
            </div>
          ) : concepts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground px-4">
              <Brain className="size-8 mb-2 opacity-30" />
              <p className="text-xs text-center">还没有评估过任何概念</p>
              <p className="text-[10px] text-center mt-1">在上方输入概念名开始首次评估</p>
            </div>
          ) : (
            <div className="py-1">
              {concepts.map((c) => (
                <button
                  key={c.id}
                  onClick={() => startAssessment(c.concept_name)}
                  disabled={assessing}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-accent transition-colors disabled:opacity-50 ${
                    selectedConcept === c.concept_name ? 'bg-accent' : ''
                  }`}
                >
                  {/* 掌握度圆环 */}
                  <div className="relative size-8 shrink-0 flex items-center justify-center">
                    <svg className="size-8 -rotate-90">
                      <circle cx="16" cy="16" r="12" fill="none" stroke="currentColor" strokeWidth="3" className="text-muted/20" />
                      <circle
                        cx="16" cy="16" r="12" fill="none"
                        stroke="currentColor" strokeWidth="3" strokeLinecap="round"
                        className={scoreColor(c.mastery_score)}
                        strokeDasharray={`${(c.mastery_score / 100) * 75.4} 75.4`}
                      />
                    </svg>
                    <span className={`absolute text-[9px] font-bold ${scoreColor(c.mastery_score)}`}>
                      {Math.round(c.mastery_score)}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.concept_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {c.assessment_count} 次评估
                      {c.last_assessed_at && ` · ${new Date(c.last_assessed_at).toLocaleDateString('zh-CN')}`}
                    </p>
                    {c.weaknesses.length > 0 && (
                      <div className="flex flex-wrap gap-0.5 mt-0.5">
                        {c.weaknesses.slice(0, 2).map((w, i) => (
                          <Badge key={i} variant="outline" className="text-[9px] px-1 py-0 h-4 text-red-500/70 border-red-500/20">
                            {w.length > 12 ? w.slice(0, 12) + '…' : w}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
                </button>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* 底部统计 */}
        {concepts.length > 0 && (
          <div className="px-3 py-2 border-t shrink-0 text-[10px] text-muted-foreground flex items-center gap-3">
            <span className="flex items-center gap-1"><TrendingUp className="size-3" />{concepts.length} 个概念</span>
            <span>均分 {Math.round(concepts.reduce((s, c) => s + c.mastery_score, 0) / concepts.length)}</span>
          </div>
        )}
      </div>

      {/* ======== 右侧：评估对话区 ======== */}
      <div className="flex-1 min-w-0 h-full flex flex-col border rounded-lg bg-card overflow-hidden">
        {selectedConcept ? (
          <>
            {/* 顶部标题栏 */}
            <div className="flex items-center gap-2 shrink-0 px-3 py-2 border-b">
              <Sparkles className="size-3.5 text-violet-500" />
              <span className="text-sm font-medium">评估: {selectedConcept}</span>
              {score && (
                <Badge className={`ml-auto text-xs ${score.score >= 80 ? 'bg-emerald-500/10 text-emerald-600' : score.score >= 60 ? 'bg-amber-500/10 text-amber-600' : 'bg-red-500/10 text-red-600'}`}>
                  {Math.round(score.score)} 分
                </Badge>
              )}
            </div>

            {/* 对话消息 */}
            <ScrollArea className="flex-1 min-h-0" ref={scrollRef}>
              <div className="flex flex-col gap-3 p-4">
                {messages.length === 0 && !agentTyping && (
                  <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
                    Agent 正在准备第一个问题…
                  </div>
                )}

                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}>
                      <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                    </div>
                  </div>
                ))}

                {agentTyping && (
                  <div className="flex justify-start">
                    <div className="max-w-[75%] rounded-lg px-3 py-2 text-sm bg-muted">
                      <span className="inline-flex items-center gap-1 text-muted-foreground">
                        <Loader2 className="size-3 animate-spin" />
                        {agentTyping === '...' ? '思考中…' : agentTyping}
                      </span>
                    </div>
                  </div>
                )}

                {/* 评估结果卡片 */}
                {score && (
                  <div className="bg-accent/50 rounded-lg p-3 mt-2 border">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-lg font-bold ${scoreColor(score.score)}`}>
                        {Math.round(score.score)} 分
                      </span>
                      <span className="text-xs text-muted-foreground">掌握度评估</span>
                    </div>

                    {score.strengths.length > 0 && (
                      <div className="mb-1.5">
                        <span className="text-[10px] text-muted-foreground">✅ 强项</span>
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {score.strengths.map((s, i) => (
                            <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0 h-5 bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                              {s}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {score.weaknesses.length > 0 && (
                      <div className="mb-1.5">
                        <span className="text-[10px] text-muted-foreground">🎯 需加强</span>
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {score.weaknesses.map((w, i) => (
                            <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0 h-5 bg-red-500/10 text-red-600 border-red-500/20">
                              {w}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {score.summary && (
                      <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{score.summary}</p>
                    )}
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* 输入框 */}
            {assessing ? (
              <div className="shrink-0 px-4 py-3 border-t text-center text-xs text-muted-foreground">
                <Loader2 className="size-3 inline animate-spin mr-1" />
                Agent 正在思考…
              </div>
            ) : (
              <div className="shrink-0 px-3 py-2 border-t flex gap-2">
                <Input
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      sendReply()
                    }
                  }}
                  placeholder={score ? '评估已完成，输入消息可继续对话…' : '输入你的回答…'}
                  className="text-sm h-9 flex-1"
                  disabled={assessing}
                />
                <Button size="icon" className="size-9 shrink-0" onClick={sendReply} disabled={assessing || !reply.trim()}>
                  <Send className="size-4" />
                </Button>
              </div>
            )}
          </>
        ) : (
          /* 空状态 */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Brain className="size-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground text-sm">选择一个概念开始评估</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                Agent 会通过对话判断你的理解深度，不是做选择题，
                而是用你自己的话解释概念
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
