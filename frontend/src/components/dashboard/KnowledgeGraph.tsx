/**
 * KnowledgeGraph — ECharts 知识图谱可视化（P7 语义互联 + Top-K/悬停显边）
 * ---------------------------------------------------------------------
 * 节点 = 笔记（标签分类着色 + 字数/引用度决定大小）
 * 默认连线 = 每篇笔记 Top-K 语义邻居（稀疏，后端算好，避免全图过密）
 * 悬停节点 = 临时亮出该节点的全部语义关联（粗细=相似度），移出后恢复默认
 */
import { useRef, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { GraphNode, GraphEdge } from '@/types'

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  /** 全量语义边（>= 阈值），悬停节点时用于亮出完整关联 */
  allEdges?: GraphEdge[]
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

// 悬停时最多亮出的关联边数（防单节点关联过多时卡顿）
const REVEAL_MAX = 15

// 无向边去重 key（source/target 顺序无关）
function pairKey(a: number, b: number): string {
  return a < b ? `${a}-${b}` : `${b}-${a}`
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
  allEdges,
  loading,
  className,
  onNodeClick,
}: KnowledgeGraphProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<EChart | null>(null)

  useEffect(() => {
    if (!chartRef.current || loading) return

    let chart: EChart | null = null
    let restoreTimer: number | undefined

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' })

      const buildLinks = (edgeList: GraphEdge[]) =>
        edgeList.map((e) => ({
          source: String(e.source),
          target: String(e.target),
          value: e.weight || 0,
          lineStyle: {
            // 相似度 0.35→1px, 0.7→2px, 1.0→3px
            width: Math.max(0.5, (e.weight || 0) * 3),
            curveness: 0.2,
          },
        }))

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
            links: buildLinks(edges),
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

      // ---- 悬停节点 → 亮出该节点全部语义关联；移出 → 恢复默认 Top-K ----
      chart.on('mouseover', (raw: unknown) => {
        const params = raw as { dataType?: string; data?: { id?: string | number } }
        if (params.dataType !== 'node') return
        const id = Number(params.data?.id)
        if (Number.isNaN(id)) return
        // 取消恢复定时器：从节点 A 直接移到节点 B 时，不应先恢复默认再亮出（会闪烁）
        window.clearTimeout(restoreTimer)
        // 该节点的完整关联（按相似度降序，最多 REVEAL_MAX 条）
        const incident = (allEdges || [])
          .filter((e) => e.source === id || e.target === id)
          .sort((a, b) => (b.weight || 0) - (a.weight || 0))
          .slice(0, REVEAL_MAX)
        // 与默认 Top-K 边合并去重（默认边保留，追加该节点独有的关联）
        const defaultKeys = new Set(edges.map((e) => pairKey(e.source, e.target)))
        const merged = [
          ...edges,
          ...incident.filter((e) => !defaultKeys.has(pairKey(e.source, e.target))),
        ]
        chart?.setOption({ series: [{ links: buildLinks(merged) }] })
      })

      chart.on('mouseout', (raw: unknown) => {
        const params = raw as { dataType?: string }
        if (params.dataType !== 'node') return
        // 延迟 120ms 恢复默认：期间若又悬停到相邻节点，上面的 clearTimeout 会取消恢复
        restoreTimer = window.setTimeout(() => {
          chart?.setOption({ series: [{ links: buildLinks(edges) }] })
        }, 120)
      })

      instanceRef.current = chart

      // 监听容器大小变化
      const observer = new ResizeObserver(() => {
        chart?.resize()
      })
      observer.observe(chartRef.current)
    })

    return () => {
      window.clearTimeout(restoreTimer)
      if (chart) chart.dispose()
      instanceRef.current = null
    }
  }, [nodes, edges, allEdges, loading])

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
