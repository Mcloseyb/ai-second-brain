/**
 * DashboardPage — 数据看板页面
 * ----------------------------
 * 统计卡片 + 知识图谱 + 标签分布。
 * 后端 API 待实现时使用 mock 数据。
 */
import { useEffect, useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import StatCard from '@/components/dashboard/StatCard'
import KnowledgeGraph from '@/components/dashboard/KnowledgeGraph'
import { notesApi, tagsApi, syncApi } from '@/lib/api'
import {
  FileText,
  CheckCircle2,
  RefreshCw,
  Tags,
  BarChart3,
} from 'lucide-react'
import type { Tag, GraphNode, GraphEdge } from '@/types'

export default function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [noteCount, setNoteCount] = useState(0)
  const [syncStatus, setSyncStatus] = useState({ synced: 0, pending: 0, never_synced: 0 })
  const [tags, setTags] = useState<Tag[]>([])
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      // 加载笔记数量
      const notesRes = await notesApi.list({ page_size: 1 })
      setNoteCount(notesRes.total)

      // 加载同步状态
      const syncRes = await syncApi.status()
      setSyncStatus({
        synced: syncRes.synced,
        pending: syncRes.pending,
        never_synced: syncRes.never_synced,
      })

      // 加载标签
      const tagsRes = await tagsApi.list()
      setTags(tagsRes.tags || [])

      // 构建知识图谱数据（基于标签共现）
      const notesResFull = await notesApi.list({ page_size: 50 })
      const allNotes = notesResFull.notes || []
      const tagMap = new Map<string, { count: number; notes: Set<string> }>()

      for (const note of allNotes) {
        for (const tag of note.tags || []) {
          if (!tagMap.has(tag.name)) {
            tagMap.set(tag.name, { count: 0, notes: new Set() })
          }
          const entry = tagMap.get(tag.name)!
          entry.count++
          entry.notes.add(note.title)
        }
      }

      const nodes: GraphNode[] = []
      const edges: GraphEdge[] = []
      const tagEntries = Array.from(tagMap.entries())
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 15)

      for (const [name, data] of tagEntries) {
        nodes.push({
          id: name,
          name,
          category: '标签',
          symbolSize: Math.max(20, Math.min(60, data.count * 8)),
        })
      }

      // 标签共现 = 边
      const allTags = tagEntries.map(([name]) => name)
      for (const note of allNotes) {
        const noteTagNames = (note.tags || []).map((t) => t.name).filter((n) => allTags.includes(n))
        for (let i = 0; i < noteTagNames.length; i++) {
          for (let j = i + 1; j < noteTagNames.length; j++) {
            edges.push({ source: noteTagNames[i], target: noteTagNames[j], weight: 1 })
          }
        }
      }

      setGraphNodes(nodes)
      setGraphEdges(edges)
    } catch (e) {
      console.error('加载看板数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      {/* ======== 统计卡片 ======== */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          icon={FileText}
          label="笔记总数"
          value={noteCount}
          color="text-blue-600 dark:text-blue-400"
          loading={loading}
        />
        <StatCard
          icon={CheckCircle2}
          label="已同步"
          value={syncStatus.synced}
          color="text-green-600 dark:text-green-400"
          loading={loading}
        />
        <StatCard
          icon={RefreshCw}
          label="待同步"
          value={syncStatus.pending}
          color="text-amber-600 dark:text-amber-400"
          loading={loading}
        />
        <StatCard
          icon={Tags}
          label="标签数"
          value={tags.length}
          color="text-purple-600 dark:text-purple-400"
          loading={loading}
        />
      </div>

      {/* ======== 中行：标签分布 ======== */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <BarChart3 className="size-4" />
            热门标签
          </CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="p-4">
          {loading ? (
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-6 w-20" />
              ))}
            </div>
          ) : tags.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无标签</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <Badge
                  key={tag.id}
                  variant="secondary"
                  className="text-sm px-3 py-1"
                  style={{
                    fontSize: `${Math.max(0.75, Math.min(1.2, 0.8 + (tag.note_count || 0) * 0.05))}rem`,
                  }}
                >
                  {tag.name}
                  {tag.note_count ? ` (${tag.note_count})` : ''}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ======== 知识图谱 ======== */}
      <Card className="flex-1 min-h-[400px]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">知识图谱</CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="p-4 h-[420px]">
          <KnowledgeGraph
            nodes={graphNodes}
            edges={graphEdges}
            loading={loading}
            className="h-full"
            onNodeClick={(nodeId) => {
              console.log('Clicked node:', nodeId)
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}
