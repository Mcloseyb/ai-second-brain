/**
 * TagSuggestBar — AI 自动标签推荐条（P4）
 * --------------------------------------
 * 保存笔记后自动弹出，展示 AI 推荐的 3-5 个标签。
 * existing 类型 = 复用已有标签（蓝色）；new 类型 = 建议新建（紫色带"新"角标）。
 * 支持：单个采纳 / 全部采纳 / 忽略。
 */
import { Sparkles, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { TagSuggestion } from '@/types'

export default function TagSuggestBar({
  suggestions,
  loading,
  onAccept,
  onAcceptAll,
  onDismiss,
}: {
  suggestions: TagSuggestion[]
  loading?: boolean
  onAccept: (tag: string) => void
  onAcceptAll: () => void
  onDismiss: () => void
}) {
  if (!loading && suggestions.length === 0) return null

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-md border border-violet-200 dark:border-violet-800 bg-violet-50/80 dark:bg-violet-950/40 shrink-0">
      <Sparkles className="size-3.5 shrink-0 text-violet-500" />

      {loading ? (
        <span className="text-xs text-muted-foreground animate-pulse">AI 正在分析内容，推荐标签…</span>
      ) : (
        <>
          <span className="text-xs text-muted-foreground shrink-0">推荐:</span>
          <div className="flex flex-wrap gap-1 min-w-0">
            {suggestions.map((s) => (
              <button
                key={s.tag}
                onClick={() => onAccept(s.tag)}
                title={`来自关键词「${s.keyword}」· 相关度 ${Math.round(s.score * 100)}%`}
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
        </>
      )}
    </div>
  )
}
