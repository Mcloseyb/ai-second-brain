/**
 * AgentProgress — Agent 执行进度可视化
 * -------------------------------------
 * 4 个 Agent 步骤：Retriever → Analyst → Writer → Reviewer
 * 每步显示状态（等待/运行中/完成/失败）+ 动画效果。
 */
import { cn } from '@/lib/utils'
import {
  Search,
  BarChart3,
  FileEdit,
  CheckCircle2,
  Loader2,
  XCircle,
  Circle,
} from 'lucide-react'
import type { AgentStep as AgentStepType } from '@/types'

const agentConfig: Record<string, { icon: typeof Search; label: string }> = {
  retriever: { icon: Search, label: '检索 Agent' },
  analyst: { icon: BarChart3, label: '分析 Agent' },
  writer: { icon: FileEdit, label: '写作 Agent' },
  reviewer: { icon: CheckCircle2, label: '审核 Agent' },
}

interface AgentProgressProps {
  steps: AgentStepType[]
}

export default function AgentProgress({ steps }: AgentProgressProps) {
  const stepMap = new Map(steps.map((s) => [s.agent, s]))

  const agents = ['retriever', 'analyst', 'writer', 'reviewer'] as const

  return (
    <div className="flex items-center gap-2">
      {agents.map((agent, idx) => {
        const step = stepMap.get(agent)
        const config = agentConfig[agent]
        const Icon = config.icon
        const status = step?.status || 'pending'

        return (
          <div key={agent} className="flex items-center gap-2">
            {/* Agent 卡片 */}
            <div
              className={cn(
                'flex flex-col items-center gap-1 rounded-lg border px-3 py-2 min-w-[100px] transition-all',
                status === 'running' && 'border-primary bg-primary/5 shadow-sm',
                status === 'completed' && 'border-green-500/50 bg-green-50 dark:bg-green-950/20',
                status === 'error' && 'border-destructive/50 bg-destructive/5',
                status === 'pending' && 'border-dashed opacity-50',
              )}
            >
              {/* 状态图标 */}
              <div className="relative">
                {status === 'running' ? (
                  <Loader2 className="size-5 text-primary animate-spin" />
                ) : status === 'completed' ? (
                  <CheckCircle2 className="size-5 text-green-500" />
                ) : status === 'error' ? (
                  <XCircle className="size-5 text-destructive" />
                ) : (
                  <Circle className="size-5 text-muted-foreground" />
                )}
              </div>
              {/* Agent 名称 */}
              <span className="text-xs font-medium">{config.label}</span>
              {/* 状态文字 */}
              <span
                className={cn(
                  'text-[10px]',
                  status === 'running' && 'text-primary',
                  status === 'completed' && 'text-green-600 dark:text-green-400',
                  status === 'error' && 'text-destructive',
                  status === 'pending' && 'text-muted-foreground',
                )}
              >
                {status === 'running'
                  ? '运行中...'
                  : status === 'completed'
                    ? '完成'
                    : status === 'error'
                      ? '失败'
                      : '等待中'}
              </span>
            </div>

            {/* 连接箭头（最后一个不加） */}
            {idx < agents.length - 1 && (
              <div className="text-muted-foreground text-lg">→</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
