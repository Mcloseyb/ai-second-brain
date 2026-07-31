/**
 * StatCard — 统计卡片组件
 * -----------------------
 * 显示单个 KPI 数值 + 标签 + 图标。
 */
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { type LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: number | string
  color?: string
  loading?: boolean
  subtitle?: string
}

export default function StatCard({
  icon: Icon,
  label,
  value,
  color = 'text-primary',
  loading,
  subtitle,
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div
          className={cn(
            'flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10',
            color.replace('text-', 'bg-').replace('-600', '/10').replace('-500', '/10'),
          )}
        >
          <Icon className={cn('size-5', color)} />
        </div>
        <div className="flex-1 min-w-0">
          {loading ? (
            <Skeleton className="h-7 w-16" />
          ) : (
            <div className="text-2xl font-bold tabular-nums">{value}</div>
          )}
          <p className="text-sm text-muted-foreground">{label}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
      </CardContent>
    </Card>
  )
}
