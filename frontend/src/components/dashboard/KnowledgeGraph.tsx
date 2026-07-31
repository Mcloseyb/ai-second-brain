/**
 * KnowledgeGraph — ECharts 知识图谱可视化（P7 语义聚类，不画连线）
 * -------------------------------------------------------------
 * 关联表达：颜色 + 位置 + 大小（用户约束，不画连线）
 *   - 同簇（语义连通）笔记 → 同一颜色
 *   - 力导向布局把关联笔记聚到一起，静置后固定不动
 *   - 关联次数越多 → 节点越大（越重要）
 * 交互：点击节点 → 高亮其关联节点（突出显示）；再次点击同一节点 → 跳转打开笔记
 */
import { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { GraphNode, GraphEdge } from '@/types'

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  /** 语义邻居边：仅用于力导向布局聚簇 + 点击高亮，不绘制 */
  edges: GraphEdge[]
  loading?: boolean
  className?: string
  onNodeClick?: (nodeId: number) => void
}

// 分类着色调色板（按簇名 hash 取值，同簇同色且稳定）
const CATEGORY_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#2f4554',
]
function categoryColor(category: string): string {
  let hash = 0
  for (const ch of category) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return CATEGORY_COLORS[hash % CATEGORY_COLORS.length]
}

type EChart = {
  setOption: (o: Record<string, unknown>) => void
  resize: () => void
  dispose: () => void
  on: (e: string, cb: (p: unknown) => void) => void
}

export default function KnowledgeGraph({
  nodes,
  edges,
  loading,
  className,
  onNodeClick,
}: KnowledgeGraphProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<EChart | null>(null)
  // 已选中的节点 id（区分「第一次点击=高亮」与「第二次点击=跳转」）
  const selectedIdRef = useRef<number | null>(null)

  useEffect(() => {
    if (!chartRef.current || loading) return

    let chart: EChart | null = null
    selectedIdRef.current = null

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' }) as unknown as EChart

      // 按簇分组，categories 动态生成（簇名 → 颜色）
      const categories = Array.from(new Set(nodes.map((n) => n.category))).map((name) => ({
        name,
        itemStyle: { color: categoryColor(name) },
      }))

      const option = {
        tooltip: {
          formatter: (params: { data?: { name?: string; degree?: number; tags?: string[] } }) => {
            const d = params.data
            if (!d) return ''
            const tags = (d.tags || []).join('、') || '无标签'
            return `${d.name}<br/>关联: ${d.degree ?? 0} 篇<br/>标签: ${tags}`
          },
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            force: {
              repulsion: 250,
              edgeLength: [100, 250],
            },
            // 连线不绘制（用户约束），只用于布局聚簇 + 点击高亮
            lineStyle: { opacity: 0 },
            data: nodes.map((n) => ({
              id: String(n.id),
              name: n.name,
              category: n.category,
              symbolSize: n.symbolSize,
              degree: n.degree,
              tags: n.tags,
            })),
            links: edges.map((e) => ({
              source: String(e.source),
              target: String(e.target),
              value: e.weight || 0,
            })),
            categories,
            label: {
              show: true,
              fontSize: 11,
              color: 'inherit',
            },
            // 悬停：轻微放大做反馈（不高亮，高亮由点击触发）
            emphasis: {
              scale: true,
            },
            // 点击选中：关联节点保持明亮，其余变暗 → 「突出显示关联」
            selectedMode: 'single',
            select: {
              focus: 'adjacency',
              scale: true,
              itemStyle: { opacity: 1 },
            },
            blur: {
              itemStyle: { opacity: 0.15 },
            },
          },
        ],
      }

      chart.setOption(option)

      if (onNodeClick) {
        chart.on('click', (raw: unknown) => {
          const params = raw as { dataType?: string; data?: { id?: string | number } }
          if (params.dataType !== 'node') return
          const id = Number(params.data?.id)
          if (Number.isNaN(id)) return
          // 第一次点击：选中高亮关联；再次点击同一节点：跳转打开笔记
          if (selectedIdRef.current === id) {
            selectedIdRef.current = null
            onNodeClick(id)
          } else {
            selectedIdRef.current = id
          }
        })
      }

      instanceRef.current = chart

      // 监听容器大小变化
      const observer = new ResizeObserver(() => {
        chart?.resize()
      })
      observer.observe(chartRef.current)
    })

    return () => {
      if (chart) chart.dispose()
      instanceRef.current = null
    }
  }, [nodes, edges, loading])

  if (loading) {
    return (
      <Card className={cn('min-h-[400px]', className)}>
        <CardContent className="flex items-center justify-center h-full p-4">
          <Skeleton className="h-full w-full" />
        </CardContent>
      </Card>
    )
  }

  if (nodes.length === 0) {
    return (
      <Card className={cn('min-h-[400px]', className)}>
        <CardContent className="flex items-center justify-center h-full p-4 text-muted-foreground text-sm">
          暂无笔记数据
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn('min-h-[400px] flex flex-col', className)}>
      <CardContent className="p-0 flex-1 min-h-0">
        <div ref={chartRef} className="w-full h-full" />
      </CardContent>
    </Card>
  )
}
