/**
 * KnowledgeGraph — 云朵知识图谱（P7 重构，不画内部连线）
 * -----------------------------------------------------
 * 每簇笔记 = 一朵云（path 椭圆符号），云朵中央显示 Agent 起的主题名；
 * 相关云朵用线互联（线粗 = 簇间相似度）。
 * 布局：坐标全部前端计算（layout:'none'），位置固定不抖动、不可拖拽。
 * 交互：
 *   - 点击云朵 → 展开/收起该云朵内的笔记（显示笔记名）
 *   - 点击笔记 → 高亮其强关联笔记；再次点击同一笔记 → 打开笔记
 *   - 悬浮 → tooltip 显示名称
 * 节点文字颜色与圆圈/云朵颜色区分（深色/浅色自适应），保证可读性。
 */
import { useRef, useEffect, useMemo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { GraphNode, GraphEdge, GraphCluster, GraphClusterEdge } from '@/types'

interface KnowledgeGraphProps {
  nodes: GraphNode[]
  /** 语义邻居边：点击笔记时高亮这些关联笔记（不绘制） */
  edges: GraphEdge[]
  clusters?: GraphCluster[]
  clusterEdges?: GraphClusterEdge[]
  /** Agent 生成的云朵名称：cluster_id → 名称 */
  clusterNames?: Record<number, string>
  isDark?: boolean
  loading?: boolean
  className?: string
  onNodeClick?: (noteId: number) => void
}

// 云朵形状（feather cloud path，缩放为椭圆）
const CLOUD_PATH = 'path://M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z'

// 簇着色调色板（按 cluster_id hash 取值，稳定映射）
const CLUSTER_COLORS = [
  '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
  '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#2f4554',
]
function clusterColor(clusterId: number): string {
  let hash = Math.abs(clusterId)
  hash = (hash * 31 + 7) >>> 0
  return CLUSTER_COLORS[hash % CLUSTER_COLORS.length]
}

// 向日葵螺旋黄金角（云朵内放点防重叠）
const GOLDEN = Math.PI * (3 - Math.sqrt(5))

interface CloudGeom {
  cx: number
  cy: number
  a: number
  b: number
  R: number
}

/**
 * 计算云朵与笔记的固定坐标（纯函数，布局:'none' 直接使用 → 零抖动）
 */
function computeLayout(
  nodes: GraphNode[],
  clusters: GraphCluster[],
  clusterEdges: GraphClusterEdge[],
): {
  notePos: Map<number, { x: number; y: number }>
  cloudGeom: Map<number, CloudGeom>
  clusterOrder: number[]
  freeNotes: GraphNode[]
} {
  const notePos = new Map<number, { x: number; y: number }>()
  const cloudGeom = new Map<number, CloudGeom>()
  const freeNotes: GraphNode[] = []

  // 按簇分组，簇不在列表里的视为游离
  const byCluster = new Map<number, GraphNode[]>()
  const clusterIdSet = new Set((clusters || []).map((c) => c.cluster_id))
  for (const n of nodes) {
    if (n.cluster_id != null && clusterIdSet.has(n.cluster_id)) {
      if (!byCluster.has(n.cluster_id)) byCluster.set(n.cluster_id, [])
      byCluster.get(n.cluster_id)!.push(n)
    } else {
      freeNotes.push(n)
    }
  }
  const clusterIds = [...byCluster.keys()]

  if (clusterIds.length === 0) {
    // 没有簇：游离笔记排成圆
    freeNotes.forEach((n, i) => {
      const ang = (2 * Math.PI * i) / Math.max(freeNotes.length, 1)
      notePos.set(n.id, { x: 220 * Math.cos(ang), y: 220 * Math.sin(ang) })
    })
    return { notePos, cloudGeom, clusterOrder: [], freeNotes }
  }

  // ---- 云朵排序：把最相关的簇排到一起（贪心） ----
  const wKey = (a: number, b: number) => `${Math.min(a, b)}-${Math.max(a, b)}`
  const edgeW = new Map<string, number>()
  for (const e of clusterEdges || []) edgeW.set(wKey(e.source, e.target), e.weight || 0)
  const totalW = (c: number, placed: number[]) =>
    placed.reduce((s, p) => s + (edgeW.get(wKey(c, p)) || 0), 0)
  const totalConn = (c: number) => clusterIds.reduce((s, p) => s + (edgeW.get(wKey(c, p)) || 0), 0)

  const clusterOrder: number[] = []
  const remaining = [...clusterIds].sort((a, b) => totalConn(b) - totalConn(a))
  clusterOrder.push(remaining.shift()!)
  while (remaining.length > 0) {
    remaining.sort((a, b) => totalW(b, clusterOrder) - totalW(a, clusterOrder))
    clusterOrder.push(remaining.shift()!)
  }

  // ---- 云朵尺寸（按笔记数） ----
  const sizes = new Map<number, CloudGeom>()
  for (const id of clusterOrder) {
    const cnt = byCluster.get(id)!.length
    const R = 26 + cnt * 9
    sizes.set(id, { cx: 0, cy: 0, R, a: R * 0.95 + 52, b: R * 0.72 + 42 })
  }

  // ---- 云朵中心排成圆 ----
  const nC = clusterOrder.length
  const maxA = Math.max(...[...sizes.values()].map((s) => s.a))
  const Rc = Math.max(200, maxA * 1.7 + nC * 55)
  clusterOrder.forEach((id, i) => {
    const ang = (2 * Math.PI * i) / nC - Math.PI / 2
    const g = sizes.get(id)!
    g.cx = Rc * Math.cos(ang)
    g.cy = Rc * Math.sin(ang)
    cloudGeom.set(id, g)
  })

  // ---- 云朵内笔记：向日葵螺旋，避免重叠 ----
  for (const id of clusterOrder) {
    const notes = byCluster.get(id)!
    const { cx, cy, R } = sizes.get(id)!
    notes.forEach((n, i) => {
      const r = R * Math.sqrt((i + 0.5) / notes.length)
      const th = i * GOLDEN
      notePos.set(n.id, { x: cx + r * Math.cos(th) * 0.92, y: cy + r * Math.sin(th) * 0.74 })
    })
  }

  // ---- 游离笔记放在云朵圈外 ----
  freeNotes.forEach((n, i) => {
    const ang = (2 * Math.PI * i) / Math.max(freeNotes.length, 1)
    const r = Rc + maxA + 130
    notePos.set(n.id, { x: r * Math.cos(ang), y: r * Math.sin(ang) })
  })

  // ---- 归一化：整体缩放到视图框内，保证首屏全可见 ----
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  const consider = (x: number, y: number) => {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x)
    minY = Math.min(minY, y); maxY = Math.max(maxY, y)
  }
  for (const g of cloudGeom.values()) {
    consider(g.cx - g.a, g.cy - g.b)
    consider(g.cx + g.a, g.cy + g.b)
  }
  for (const p of notePos.values()) consider(p.x, p.y)

  const VIEW_W = 640
  const VIEW_H = 470
  const spanX = Math.max(maxX - minX, 1)
  const spanY = Math.max(maxY - minY, 1)
  const scale = Math.min(VIEW_W / spanX, VIEW_H / spanY, 1)
  if (scale < 1) {
    for (const g of cloudGeom.values()) {
      g.cx *= scale
      g.cy *= scale
      g.a *= scale
      g.b *= scale
    }
    for (const p of notePos.values()) {
      p.x *= scale
      p.y *= scale
    }
  }

  return { notePos, cloudGeom, clusterOrder, freeNotes }
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
  clusters,
  clusterEdges,
  clusterNames,
  isDark,
  loading,
  className,
  onNodeClick,
}: KnowledgeGraphProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const instanceRef = useRef<EChart | null>(null)
  // 交互状态（ref，避免触发 React 重渲染）
  const expandedRef = useRef<number | null>(null)   // 当前展开的云朵
  const selectedRef = useRef<number | null>(null)   // 当前高亮的笔记

  // 布局纯前端计算，输入变化才重算（固定坐标）
  const layout = useMemo(
    () => computeLayout(nodes, clusters || [], clusterEdges || []),
    [nodes, clusters, clusterEdges],
  )

  useEffect(() => {
    if (!chartRef.current || loading) return

    let chart: EChart | null = null
    expandedRef.current = null
    selectedRef.current = null

    import('echarts').then((echarts) => {
      if (!chartRef.current) return
      chart = echarts.init(chartRef.current, undefined, { renderer: 'canvas' }) as unknown as EChart

      const dark = !!isDark
      // 文字颜色与圆圈/云朵颜色区分（浅色：深字；深色：浅字）
      const textColor = dark ? '#f3f4f6' : '#1f2937'
      const lineColor = dark ? '#94a3b8' : '#64748b'
      const names = clusterNames || {}
      const cloudCount = new Map((clusters || []).map((c) => [c.cluster_id, c.count]))

      // 笔记的强关联邻居（点击高亮用）
      const neighborIds = (noteId: number): Set<number> => {
        const s = new Set<number>()
        for (const e of edges) {
          if (e.source === noteId) s.add(e.target)
          if (e.target === noteId) s.add(e.source)
        }
        return s
      }

      const buildClouds = () =>
        [...layout.cloudGeom.entries()].map(([cid, g]) => {
          const expanded = expandedRef.current === cid
          const color = clusterColor(cid)
          return {
            id: `c${cid}`,
            name: names[cid] || `簇${cid}`,
            symbol: CLOUD_PATH,
            symbolSize: [g.a, g.b],
            x: g.cx,
            y: g.cy,
            isCloud: true,
            clusterId: cid,
            count: cloudCount.get(cid) ?? 0,
            itemStyle: {
              color,
              opacity: 0.16,
              borderColor: expanded ? (dark ? '#ffffff' : '#000000') : color,
              borderWidth: expanded ? 2.5 : 1.5,
              shadowBlur: 14,
              shadowColor: 'rgba(0,0,0,0.16)',
            },
            // 云朵名称放在正中间
            label: {
              show: true,
              position: 'inside',
              fontSize: 13,
              fontWeight: 700,
              color: textColor,
            },
            emphasis: { scale: false }, // 云朵悬停不放大，只出 tooltip
          }
        })

      const buildNotes = () => {
        const expanded = expandedRef.current
        const selected = selectedRef.current
        const nbrs = selected != null ? neighborIds(selected) : null
        return nodes.map((n) => {
          const cid = n.cluster_id
          const pos = layout.notePos.get(n.id)
          const inCloud = cid != null && layout.cloudGeom.has(cid)
          // 游离节点 / 所属云朵已展开 → 显示名称
          const showLabel = !inCloud || expanded === cid
          // 高亮状态
          let opacity = 1
          let borderWidth = 1.5
          let size = Math.max(10, Math.min(n.symbolSize, 34))
          if (selected != null) {
            if (selected === n.id) {
              borderWidth = 2.5
              size += 5
            } else if (nbrs && nbrs.has(n.id)) {
              /* 关联笔记保持明亮 */
            } else {
              opacity = 0.15
            }
          }
          return {
            id: `n${n.id}`,
            name: n.name,
            noteId: n.id,
            degree: n.degree,
            x: pos?.x ?? 0,
            y: pos?.y ?? 0,
            symbol: 'circle',
            symbolSize: size,
            itemStyle: {
              color: inCloud ? clusterColor(cid!) : '#9ca3af',
              opacity,
              borderColor: dark ? '#111827' : '#ffffff',
              borderWidth,
            },
            label: {
              show: showLabel,
              position: 'bottom',
              distance: 6,
              fontSize: 11,
              color: textColor,
              backgroundColor: dark ? 'rgba(17,24,39,0.72)' : 'rgba(255,255,255,0.82)',
              borderRadius: 3,
              padding: [2, 5],
            },
          }
        })
      }

      const buildLinks = () =>
        (clusterEdges || []).map((e) => ({
          source: `c${e.source}`,
          target: `c${e.target}`,
          value: e.weight || 0,
          lineStyle: {
            color: lineColor,
            opacity: dark ? 0.6 : 0.45,
            width: 1 + (e.weight || 0) * 3,
          },
        }))

      const option = {
        tooltip: {
          formatter: (params: { data?: { isCloud?: boolean; name?: string; count?: number; degree?: number } }) => {
            const d = params.data
            if (!d) return ''
            if (d.isCloud) return `${d.name}<br/>包含 ${d.count ?? 0} 篇笔记<br/>点击展开 / 收起`
            return `${d.name}<br/>关联 ${d.degree ?? 0} 篇<br/>点击高亮 · 再次点击打开`
          },
        },
        series: [
          {
            type: 'graph',
            layout: 'none',
            roam: true,
            draggable: false, // 禁止拖拽节点，位置全由算法固定
            data: [...buildClouds(), ...buildNotes()],
            links: buildLinks(),
            label: { color: textColor },
            emphasis: { scale: true },
          },
        ],
      }

      chart.setOption(option)

      // 状态变化时只更新 data/links，不重建 → 位置不变，零抖动
      const render = () => {
        chart?.setOption({
          series: [{ data: [...buildClouds(), ...buildNotes()], links: buildLinks() }],
        })
      }

      chart.on('click', (raw: unknown) => {
        const params = raw as { data?: { isCloud?: boolean; clusterId?: number; noteId?: number } }
        const d = params.data
        if (!d) {
          // 点击空白：收起云朵 + 取消高亮
          expandedRef.current = null
          selectedRef.current = null
          render()
          return
        }
        if (d.isCloud && d.clusterId != null) {
          // 点击云朵：展开/收起该云朵内部笔记
          expandedRef.current = expandedRef.current === d.clusterId ? null : d.clusterId
          selectedRef.current = null
          render()
          return
        }
        if (d.noteId != null) {
          // 第一次点击：高亮关联；再次点击同一笔记：打开笔记
          if (selectedRef.current === d.noteId) {
            const noteId = d.noteId
            selectedRef.current = null
            render()
            onNodeClick?.(noteId)
          } else {
            selectedRef.current = d.noteId
            render()
          }
        }
      })

      instanceRef.current = chart

      const observer = new ResizeObserver(() => {
        chart?.resize()
      })
      observer.observe(chartRef.current)
    })

    return () => {
      if (chart) chart.dispose()
      instanceRef.current = null
    }
  }, [nodes, edges, clusters, clusterEdges, clusterNames, isDark, loading, layout])

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
