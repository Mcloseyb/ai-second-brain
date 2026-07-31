/**
 * TagSuggestBar — AI 自动标签推荐条（P4）
 * --------------------------------------
 * 保存笔记后自动弹出（简易版）或点击"AI 打标签"（完整版）。
 * existing 类型 = 复用已有标签（蓝色）；new 类型 = 建议新建（紫色带"新"角标）。
 * 支持：单个采纳 / 全部采纳 / 忽略。
 * 完整版额外支持：merge 建议展示 + 应用合并。
 */
import { Sparkles, Check, X, Merge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { TagSuggestion, MergeSuggestion } from '@/types'

export default function TagSuggestBar({
  suggestions,
  mergeSuggestions,
  loading,
  onAccept,
  onAcceptAll,
  onDismiss,
  onApplyMerge,
}: {
  suggestions: TagSuggestion[]
  mergeSuggestions?: MergeSuggestion[]
  loading?: boolean
  onAccept: (tag: string) => void
  onAcceptAll: () => void
  onDismiss: () => void
  onApplyMerge?: (from: string, to: string) => void
}) {
  if (!loading && suggestions.length === 0 && !(mergeSuggestions?.length)) return null

  return (
    <div className="flex flex-col gap-1 px-2 py-1.5 rounded-md border border-violet-200 dark:border-violet-800 bg-violet-50/80 dark:bg-violet-950/40 shrink-0">
      {loading ? (
        <div className="flex items-center gap-2">
          <Sparkles className="size-3.5 shrink-0 text-violet-500" />
          <span className="text-xs text-muted-foreground animate-pulse">AI 正在分析内容，推荐标签…</span>
        </div>
      ) : (
        <>
          {/* 标签推荐 */}
          {suggestions.length > 0 && (
            <div className="flex items-center gap-2">
              <Sparkles className="size-3.5 shrink-0 text-violet-500" />
              <span className="text-xs text-muted-foreground shrink-0">推荐:</span>
              <div className="flex flex-wrap gap-1 min-w-0">
                {suggestions.map((s) => (
                  <button
                    key={s.tag}
                    onClick={() => onAccept(s.tag)}
                    title={`${s.reason || `来自关键词「${s.keyword}」`} · 相关度 ${Math.round(s.score * 100)}%`}
                    className={cn(
                      'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]',
                      'transition-colors hover:brightness-110 cursor-pointer',
                      s.type === 'existing'
                        ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border border-blue-300/50'
                        : 'bg-violet-500/15 text-violet-700 dark:text-violet-300 border border-violet-300/50',
                    )}
                  >
                    {s.tag}
                    {s.type === 'new' && (
                      <span className="text-[9px] text-violet-500 dark:text-violet-400 font-bold">新</span>
                    )}
                  </button>
                ))}
              </div>

              <div className="ml-auto flex items-center gap-1 shrink-0">
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={onDismiss}>
                  <X className="size-3 mr-0.5" />
                  忽略
                </Button>
                <Button size="sm" className="h-6 text-xs px-2 gap-1" onClick={onAcceptAll}>
                  <Check className="size-3" />
                  全部采纳
                </Button>
              </div>
            </div>
          )}

          {/* merge 建议（完整版去重提示） */}
          {mergeSuggestions && mergeSuggestions.length > 0 && (
            <div className="flex items-center gap-2 pl-5">
              <Merge className="size-3 shrink-0 text-orange-500" />
              <div className="flex flex-wrap items-center gap-1 min-w-0">
                {mergeSuggestions.map((m) => (
                  <span key={`${m.from}-${m.to}`} className="text-[11px] text-muted-foreground flex items-center gap-1">
                    检测到重复标签
                    <code className="text-orange-600 dark:text-orange-400 line-through decoration-orange-400">{m.from}</code>
                    <span>→</span>
                    <code className="text-orange-600 dark:text-orange-400">{m.to}</code>
                    {m.reason && <span className="text-muted-foreground/70">({m.reason})</span>}
                    {onApplyMerge && (
                      <button
                        onClick={() => onApplyMerge(m.from, m.to)}
                        className="text-[10px] px-1.5 py-0 rounded border border-orange-300 text-orange-600 dark:text-orange-400 hover:bg-orange-500/10 transition-colors cursor-pointer"
                      >
                        合并
                      </button>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
