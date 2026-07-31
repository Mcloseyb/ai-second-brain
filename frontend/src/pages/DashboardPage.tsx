/**
 * DashboardPage — 数据看板页面（P7 云朵知识图谱）
 * ----------------------------------------------
 * 整页 = 云朵知识图谱：每簇笔记一朵云，云朵中央是 Agent 起的主题名，
 * 相关云朵用线互联；点击云朵展开内部笔记，点击笔记高亮关联、再点打开。
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Separator } from '@/components/ui/separator'
import KnowledgeGraph from '@/components/dashboard/KnowledgeGraph'
import { dashboardApi } from '@/lib/api'
import { useNotesStore } from '@/stores/notes'
import { useThemeStore } from '@/stores/theme'
import { Loader2 } from 'lucide-react'
import type { GraphNode, GraphEdge, GraphCluster, GraphClusterEdge } from '@/types'

export default function DashboardPage() {
  const navigate = useNavigate()
  const setSelectedId = useNotesStore((s) => s.setSelectedId)
  const isDark = useThemeStore((s) => s.isDark)

  const [loading, setLoading] = useState(true)
  const [naming, setNaming] = useState(false)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [clusters, setClusters] = useState<GraphCluster[]>([])
  const [clusterEdges, setClusterEdges] = useState<GraphClusterEdge[]>([])
  const [clusterNames, setClusterNames] = useState<Record<number, string>>({})

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const graphRes = await dashboardApi.graph({ threshold: 0.62 })
      setNodes(graphRes.nodes || [])
      setEdges(graphRes.edges || [])
      setClusters(graphRes.clusters || [])
      setClusterEdges(graphRes.cluster_edges || [])

      // Agent 给每朵云起名（失败时后端已降级为「簇N」）
      const cl = graphRes.clusters || []
      if (cl.length > 0) {
        setNaming(true)
        try {
          const res = await dashboardApi.clusterNames(cl)
          const map: Record<number, string> = {}
          for (const item of res.names || []) map[item.cluster_id] = item.name
          setClusterNames(map)
        } finally {
          setNaming(false)
        }
      }
    } catch (e) {
      console.error('加载看板数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // ---- 再次点击节点 → 打开笔记 ----
  const handleNodeClick = useCallback((noteId: number) => {
    setSelectedId(noteId)
    navigate('/notes')
  }, [setSelectedId, navigate])

  return (
    <div className="flex h-full flex-col gap-2 p-4 overflow-auto">
      {/* 顶部提示条 */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">云朵知识图谱</span>
        <span>· 点击云朵展开内部笔记 · 点击笔记高亮关联，再次点击打开</span>
        {naming && (
          <span className="inline-flex items-center gap-1">
            <Loader2 className="size-3 animate-spin" />
            云朵命名中...
          </span>
        )}
      </div>
      <Separator />
      <div className="flex-1 min-h-0">
        <KnowledgeGraph
          nodes={nodes}
          edges={edges}
          clusters={clusters}
          clusterEdges={clusterEdges}
          clusterNames={clusterNames}
          isDark={isDark}
          loading={loading}
          className="h-full"
          onNodeClick={handleNodeClick}
        />
      </div>
    </div>
  )
}
