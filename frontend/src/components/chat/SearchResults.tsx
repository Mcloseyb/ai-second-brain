/**
 * SearchResults — 知识库搜索结果展示
 * ---------------------------------
 * 显示语义搜索返回的笔记列表：标题 + 匹配片段 + 相似度。
 * 点击可跳转到对应笔记。
 *
 * compact 模式用于右侧面板，非 compact 用于内嵌展示。
 */
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { FileText, ArrowUpRight } from 'lucide-react'
import type { NoteSearchResult } from '@/types'

interface SearchResultsProps {
  results: NoteSearchResult[]
  loading: boolean
  query: string
  onSelect: (noteId: number) => void
  /** 紧凑模式 — 用于右侧面板，去掉外层边框和标题 */
  compact?: boolean
}

export default function SearchResults({ results, loading, query, onSelect, compact = false }: SearchResultsProps) {
  if (!loading && results.length === 0) {
    return null
  }

  const body = (
    <>
      {/* 加载骨架 */}
      {loading && (
        <div className={compact ? 'space-y-2 p-3' : 'space-y-2'}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {/* 结果列表 */}
      {!loading && results.length > 0 && (
        <ScrollArea className={compact ? 'h-full' : 'max-h-[240px]'}>
          <div className={compact ? 'space-y-1 p-2' : 'space-y-1.5'}>
            {results.map((r) => (
              <button
                key={r.note_id}
                className="w-full text-left p-2 rounded-md hover:bg-accent transition-colors group flex items-start gap-2"
                onClick={() => onSelect(r.note_id)}
              >
                <ArrowUpRight className="size-3.5 mt-0.5 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-sm truncate">{r.title}</span>
                    <Badge variant="secondary" className="text-[10px] px-1 py-0 shrink-0">
                      {(r.similarity * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                    {r.text.slice(0, compact ? 100 : 150)}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>
      )}
    </>
  )

  // compact 模式：不要外层卡片包装
  if (compact) {
    return <div className="h-full">{body}</div>
  }

  // 非 compact：保留原有卡片的标题和边框
  return (
    <div className="border rounded-lg bg-muted/30 px-3 py-2 text-sm">
      {/* 标题行 */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
        <FileText className="size-3.5" />
        {loading ? (
          <span>正在搜索知识库...</span>
        ) : (
          <span>
            找到 <span className="font-medium text-foreground">{results.length}</span> 篇相关笔记
          </span>
        )}
      </div>
      {body}
    </div>
  )
}
