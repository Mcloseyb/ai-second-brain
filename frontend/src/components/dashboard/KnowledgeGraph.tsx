/**
 * KnowledgeGraph — ECharts 知识图谱可视化（P7 语义互联 + Top-K/悬停显边）
 * ---------------------------------------------------------------------
 * 节点 = 笔记（标签分类着色 + 字数/引用度决定大小）
 * 默认连线 = 每篇笔记 Top-K 语义邻居（稀疏，后端算好，避免全图过密）
 * 悬停节点 = 通过一个 layout:'none' 的叠加系列临时画上该节点的完整语义关联
 *            （按主系列节点坐标绘制，不触发力导向重新布局 → 节点不跳动）
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
  getModel: () => {
    getSeriesByIndex: (i: number) => {
      getData: () => {
        count: () => number
        getItemLayout: (i: number) => { x: number; y: number } | undefined
        getRawDataItem: (i: number) => { id?: string | number } | undefined
      }
    } | undefined
  }
}

/** 读取主系列（力导向）当前各节点坐标，供叠加系列按相同位置画线 */
function readNodePositions(chart: EChart): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const series = chart.getModel().getSeriesByIndex(0)
  if (!series) return positions
  const data = series.getData()
  for (let i = 0; i < data.count(); i++) {
    const layout = data.getItemLayout(i)
    const raw = data.getRawDataItem(i)
    if (layout && raw && raw.id !== undefined) {
      positions.set(String(raw.id), { x: layout.x, y: layout.y })
    }
  }
  return positions
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
    let clearTimer: number | undefined

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' }) as unknown as EChart

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
            // 主系列: 力导向布局 + 默认 Top-K 边。悬停显边走叠加系列，此系列永不改动 → 不触发重新布局
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
          {
            // 叠加系列: 悬停显边（layout:'none'，按主系列节点坐标绘制，不参与布局）
            type: 'graph',
            layout: 'none',
            silent: true,
            z: 1,
            data: [],
            links: [],
            label: { show: false },
            tooltip: { show: false },
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

      // ---- 悬停节点 → 叠加系列亮出完整关联；移出 → 清空叠加系列 ----
      const clearReveal = () => {
        chart?.setOption({ series: [{}, { data: [], links: [] }] })
      }

      chart.on('mouseover', (raw: unknown) => {
        const params = raw as { dataType?: string; data?: { id?: string | number } }
        if (params.dataType !== 'node') return
        const id = Number(params.data?.id)
        if (Number.isNaN(id)) return
        // 取消清空定时器：从节点 A 直接移到节点 B 时，不先清空再亮出
        window.clearTimeout(clearTimer)

        // 该节点的完整关联（按相似度降序，最多 REVEAL_MAX 条），去掉默认 Top-K 已画的部分
        const incident = (allEdges || [])
          .filter((e) => e.source === id || e.target === id)
          .sort((a, b) => (b.weight || 0) - (a.weight || 0))
          .slice(0, REVEAL_MAX)
        const defaultKeys = new Set(edges.map((e) => pairKey(e.source, e.target)))
        const revealed = incident.filter((e) => !defaultKeys.has(pairKey(e.source, e.target)))
        if (revealed.length === 0) {
          clearReveal()
          return
        }

        // 读取主系列当前节点坐标，叠加系列按相同坐标画线 → 不触发主系列重新布局
        const positions = readNodePositions(chart!)
        const involved = Array.from(new Set(revealed.flatMap((e) => [e.source, e.target])))
        const overlayData = involved.map((nid) => {
          const p = positions.get(String(nid))
          return { id: String(nid), x: p?.x ?? 0, y: p?.y ?? 0, symbolSize: 0 }
        })
        const overlayLinks = revealed.map((e) => ({
          source: String(e.source),
          target: String(e.target),
          value: e.weight || 0,
          lineStyle: {
            width: Math.max(0.5, (e.weight || 0) * 3),
            curveness: 0.2,
          },
        }))
        chart?.setOption({ series: [{}, { data: overlayData, links: overlayLinks }] })
      })

      chart.on('mouseout', (raw: unknown) => {
        const params = raw as { dataType?: string }
        if (params.dataType !== 'node') return
        // 延迟清空：期间若悬停到相邻节点，上面的 clearTimeout 会取消
        clearTimer = window.setTimeout(clearReveal, 150)
      })

      instanceRef.current = chart

      // 监听容器大小变化
      const observer = new ResizeObserver(() => {
        chart?.resize()
      })
      observer.observe(chartRef.current)
    })

    return () => {
      window.clearTimeout(clearTimer)
      if (chart) chart.dispose()
      instanceRef.current = null
    }
  }, [nodes, edges, allEdges, loading])

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
