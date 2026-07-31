/**
 * KnowledgeGraph — ECharts 知识图谱可视化（P7 语义互联）
 * ---------------------------------------------------
 * 节点 = 笔记（标签分类着色 + 字数/引用度决定大小）
 * 连线 = 语义相似度（粗细映射相似度）
 */
import { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { GraphNode, GraphEdge } from '@/types'

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  loading?: boolean
  className?: string
  onNodeClick?: (nodeId: number) => void
}

// 分类着色调色板（按标签名 hash 取值，稳定映射）
const CATEGORY_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#2f4554',
]
function categoryColor(category: string): string {
  let hash = 0
  for (const ch of category) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return CATEGORY_COLORS[hash % CATEGORY_COLORS.length]
}

export default function KnowledgeGraph({
  nodes,
  edges,
  loading,
  className,
  onNodeClick,
}: KnowledgeGraphProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<unknown>(null)

  useEffect(() => {
    if (!chartRef.current || loading) return

    let chart: {
      setOption: (o: Record<string, unknown>) => void
      resize: () => void
      dispose: () => void
      on: (e: string, cb: (p: unknown) => void) => void
    } | null = null

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' })

      // 按分类分组，categories 动态生成（标签名 → 颜色）
      const categories = Array.from(new Set(nodes.map((n) => n.category))).map((name) => ({
        name,
        itemStyle: { color: categoryColor(name) },
      }))
      // 记录 nodeId → category，供连线 tooltip 用
      const idCategory = new Map(nodes.map((n) => [String(n.id), n.category]))

      const option = {
        tooltip: {
          formatter: (params: { data?: { name?: string; word_count?: number; tags?: string[] }; value?: number | string; dataType?: string }) => {
            if (params.dataType === 'edge') {
              return `关联强度: ${params.value}`
            }
            const d = params.data
            if (d) {
              const tags = (d.tags || []).join('、') || '无标签'
              return `${d.name}<br/>分类: ${idCategory.get(String(params.data?.name)) || '未分类'}<br/>标签: ${tags}<br/>字数: ${d.word_count ?? 0}`
            }
            return ''
          },
        },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            force: {
              repulsion: 200,
              edgeLength: [100, 300],
            },
            data: nodes.map((n) => ({
              id: String(n.id),
              name: n.name,
              category: n.category,
              symbolSize: n.symbolSize,
              word_count: n.word_count,
              tags: n.tags,
            })),
            links: edges.map((e) => ({
              source: String(e.source),
              target: String(e.target),
              value: e.weight || 0,
              lineStyle: {
                // 相似度 0.35→1px, 0.7→2px, 1.0→3px
                width: Math.max(0.5, (e.weight || 0) * 3),
                curveness: 0.2,
              },
            })),
            categories,
            label: {
              show: true,
              fontSize: 11,
              color: 'inherit',
            },
            emphasis: {
              focus: 'adjacency',
              lineStyle: { width: 3 },
            },
          },
        ],
      }

      chart.setOption(option)

      if (onNodeClick) {
        chart.on('click', (raw: unknown) => {
          const params = raw as { data?: { id?: string | number } }
          const id = params?.data?.id
          if (id !== undefined && !Number.isNaN(Number(id))) {
            onNodeClick(Number(id))
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
    }
  }, [nodes, edges, loading])

  if (loading) {
    return (
      <Card className={cn('min-h-[400px]', className)}>
        <CardContent className="flex items-center justify-center h-full p-4">
          <Skeleton className="h-[350px] w-full" />
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
    <Card className={cn('min-h-[400px]', className)}>
      <CardContent className="p-0 h-full">
        <div ref={chartRef} className="w-full h-[400px]" />
      </CardContent>
    </Card>
  )
}
