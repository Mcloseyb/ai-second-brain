/**
 * RelatedNotesPanel — 智能双向链接面板（P5）
 * ------------------------------------------
 * 位于编辑器右侧，可折叠。
 * 三块内容:
 *   1. 标题引用建议 — 正文包含其他笔记标题（用户确认后落库）
 *   2. 语义相关笔记 — 基于 Embedding 相似度的 Top-K 相关笔记（点击跳转）
 *   3. 反向链接(Linked from) — 引用了当前笔记的其他笔记
 */
import { useEffect, useState, useCallback } from 'react'
import { notesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Link2, PanelRightClose, PanelRightOpen,
  Sparkles, Inbox, ArrowUpRight, Check,
} from 'lucide-react'
import { toast } from 'sonner'
import type { RelatedNote, LinkedFromItem, TitleLinkDetection } from '@/types'

export default function RelatedNotesPanel({
  noteId,
  onSelect,
}: {
  noteId: number
  onSelect: (id: number) => void
}) {
  const [collapsed, setCollapsed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [related, setRelated] = useState<RelatedNote[]>([])
  const [linkedFrom, setLinkedFrom] = useState<LinkedFromItem[]>([])
  const [detections, setDetections] = useState<TitleLinkDetection[]>([])
  const [showLinkedFrom, setShowLinkedFrom] = useState(false)

  const load = useCallback(async (id: number) => {
    setLoading(true)
    try {
      const [r1, r2, r3] = await Promise.all([
        notesApi.related(id),
        notesApi.linkedFrom(id),
        notesApi.titleLinks(id),
      ])
      setRelated(r1.related || [])
      setLinkedFrom(r2.linked_from || [])
      setDetections(r3.detections || [])
    } catch {
      setRelated([])
      setLinkedFrom([])
      setDetections([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(noteId) }, [noteId, load])

  /** 确认全部标题引用 → 落库 */
  const confirmDetections = useCallback(async () => {
    if (detections.length === 0) return
    try {
      const ids = detections.map((d) => d.target_note_id)
      const res = await notesApi.createLinks(noteId, ids, 'title')
      toast.success(`已确认 ${res.recorded} 条标题引用`)
      const r2 = await notesApi.linkedFrom(noteId)
      setLinkedFrom(r2.linked_from || [])
    } catch (e) {
      toast.error('确认失败: ' + (e as Error).message)
    }
  }, [noteId, detections])

  const width = collapsed ? 36 : 280
  return (
    <div
      className="h-full flex flex-col border rounded-lg bg-card overflow-hidden transition-all shrink-0"
      style={{ width }}
    >
      {collapsed ? (
        <div className="flex justify-center pt-2">
          <Button variant="ghost" size="icon" className="size-7" onClick={() => setCollapsed(false)} title="展开 Related Notes">
            <PanelRightOpen className="size-3.5" />
          </Button>
        </div>
      ) : (
        <>
          {/* 标题栏 */}
          <div className="flex items-center gap-1.5 px-2 py-1.5 border-b shrink-0">
            <Link2 className="size-3.5 text-blue-500 shrink-0" />
            <span className="text-xs font-medium flex-1">Related Notes</span>
            {loading && <span className="text-[10px] text-muted-foreground animate-pulse">加载中…</span>}
            <Button variant="ghost" size="icon" className="size-6" onClick={() => setCollapsed(true)} title="折叠">
              <PanelRightClose className="size-3" />
            </Button>
          </div>

          <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : (
          <div className="p-2 space-y-3">
            {/* 1. 标题引用建议 */}
            {detections.length > 0 && (
              <div className="space-y-1">
                <div className="flex items-center gap-1">
                  <Sparkles className="size-3 text-violet-500 shrink-0" />
                  <span className="text-[11px] font-medium text-muted-foreground">正文包含标题</span>
                  <Button size="sm" className="h-5 text-[10px] px-1.5 ml-auto" onClick={confirmDetections}>
                    <Check className="size-2.5 mr-0.5" />全部确认
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {detections.map((d) => (
                    <button
                      key={d.target_note_id}
                      onClick={() => onSelect(d.target_note_id)}
                      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] bg-violet-500/10 text-violet-700 dark:text-violet-300 border border-violet-300/40 hover:bg-violet-500/20 cursor-pointer transition-colors"
                    >
                      {d.title}
                      <ArrowUpRight className="size-2.5" />
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 2. 语义相关笔记 */}
            <div className="space-y-1">
              <p className="text-[11px] font-medium text-muted-foreground flex items-center gap-1">
                <Link2 className="size-3 text-blue-500" /> 语义相关
              </p>
              {related.length === 0 ? (
                <p className="text-[11px] text-muted-foreground/60 pl-4">暂无相关笔记</p>
              ) : (
                related.map((r) => (
                  <button
                    key={r.note_id}
                    onClick={() => onSelect(r.note_id)}
                    className="w-full text-left rounded-md px-2 py-1.5 hover:bg-accent transition-colors group"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium truncate flex-1">{r.title}</span>
                      <span className="text-[10px] text-blue-500 shrink-0 tabular-nums">
                        {Math.round(r.similarity * 100)}%
                      </span>
                      <ArrowUpRight className="size-3 text-muted-foreground opacity-0 group-hover:opacity-100 shrink-0" />
                    </div>
                    {r.text && (
                      <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">{r.text}</p>
                    )}
                  </button>
                ))
              )}
            </div>

            {/* 3. 反向链接 */}
            <div className="space-y-1">
              <button
                className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 hover:text-foreground"
                onClick={() => setShowLinkedFrom(!showLinkedFrom)}
              >
                <Inbox className="size-3" />
                {linkedFrom.length > 0 ? `${linkedFrom.length} 篇笔记引用此篇` : '暂无反向引用'}
                {linkedFrom.length > 0 && (
                  <span className="text-[9px]">{showLinkedFrom ? '▲' : '▼'}</span>
                )}
              </button>
              {showLinkedFrom && linkedFrom.map((item) => (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.id)}
                  className="w-full text-left rounded-md px-2 py-1 text-xs hover:bg-accent transition-colors flex items-center gap-1.5"
                >
                  <span className="truncate flex-1">{item.title}</span>
                  {item.link_type === 'manual' && (
                    <Badge variant="secondary" className="text-[9px] px-1 h-3.5">手动</Badge>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
          </ScrollArea>
        </>
      )}
    </div>
  )
}
