/**
 * KnowledgeGraph — ECharts 知识图谱可视化
 * ---------------------------------------
 * 使用 echarts-for-react 渲染力导向图。
 * 节点 = 笔记，连线 = 关联关系。
 */
import { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface GraphNode {
  id: string
  name: string
  category: string
  symbolSize: number
}

interface GraphEdge {
  source: string
  target: string
  weight?: number
}

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  loading?: boolean
  className?: string
  onNodeClick?: (nodeId: string) => void
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

    let chart: { setOption: (o: Record<string, unknown>) => void; resize: () => void; dispose: () => void; on: (e: string, cb: (p: unknown) => void) => void } | null = null

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' })

      const option = {
        tooltip: {
          formatter: (params: { data?: { name?: string; category?: string } }) => {
            if (params.data) {
              return `${params.data.name}<br/>${params.data.category || ''}`
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
              id: n.id,
              name: n.name,
              category: n.category,
              symbolSize: n.symbolSize,
            })),
            links: edges.map((e) => ({
              source: e.source,
              target: e.target,
              lineStyle: {
                width: Math.max(1, (e.weight || 1) * 2),
                curveness: 0.2,
              },
            })),
            categories: [
              { name: '笔记', itemStyle: { color: '#5470c6' } },
              { name: '标签', itemStyle: { color: '#91cc75' } },
            ],
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
        chart.on('click', (params: { data?: { id?: string } }) => {
          if (params.data?.id) onNodeClick(params.data.id)
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
          知识图谱数据加载完成后显示
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
