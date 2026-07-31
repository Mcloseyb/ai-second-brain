/**
 * DashboardPage — 数据看板页面（P7 真实图谱）
 * ------------------------------------------
 * 整页只保留知识图谱（语义互联，Top-K 邻居 + 悬停显边）。
 * 图谱筛选: 邻居数 K 滑块（控制默认边密度）+ 标签多选（过滤节点）。
 * 悬停节点 → 临时亮出该节点全部语义关联。点击节点 → 跳转打开笔记。
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import KnowledgeGraph from '@/components/dashboard/KnowledgeGraph'
import { dashboardApi, tagsApi } from '@/lib/api'
import { useNotesStore } from '@/stores/notes'
import {
  SlidersHorizontal,
  ChevronDown,
  Check,
} from 'lucide-react'
import type { Tag, GraphNode, GraphEdge } from '@/types'
import { cn } from '@/lib/utils'

// 邻居数 K 档位（每篇笔记连接的语义最近邻居数，控制默认边密度）
const TOP_K_OPTIONS = [1, 2, 3, 4, 5]

export default function DashboardPage() {
  const navigate = useNavigate()
  const setSelectedId = useNotesStore((s) => s.setSelectedId)

  const [loading, setLoading] = useState(true)
  const [tags, setTags] = useState<Tag[]>([])
  const [allNodes, setAllNodes] = useState<GraphNode[]>([])
  const [topKEdges, setTopKEdges] = useState<GraphEdge[]>([])
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([])

  // ---- 筛选状态（纯客户端） ----
  const [topK, setTopK] = useState(3)
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [graphRes, tagsRes] = await Promise.all([
        // threshold=0.2 拉足全量弱边供悬停展示；默认展示边由后端按 top_k 算好
        dashboardApi.graph({ threshold: 0.2, top_k: topK }),
        tagsApi.list(),
      ])
      setTags(tagsRes.tags || [])
      setAllNodes(graphRes.nodes || [])
      setTopKEdges(graphRes.edges || [])
      setAllEdges(graphRes.all_edges || [])
    } catch (e) {
      console.error('加载看板数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [topK])

  useEffect(() => {
    loadData()
  }, [loadData])

  // ---- 标签筛选：保留含任一选中标签的节点，边只保留两端都在保留节点内 ----
  const filteredNodes = selectedTags.length === 0
    ? allNodes
    : allNodes.filter((n) => n.tags?.some((t) => selectedTags.includes(t)))
  const nodeIdSet = new Set(filteredNodes.map((n) => n.id))
  // 默认展示边（Top-K，已稀疏），仅按标签过滤
  const filteredEdges = topKEdges.filter(
    (e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target),
  )
  // 悬停展示的完整关联边，同样按标签过滤
  const filteredAllEdges = allEdges.filter(
    (e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target),
  )

  const graphNodes = filteredNodes
  const graphEdges = filteredEdges

  const toggleTag = (name: string) => {
    setSelectedTags((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name],
    )
  }

  // ---- 点击节点 → 打开笔记 ----
  const handleNodeClick = useCallback((noteId: number) => {
    setSelectedId(noteId)
    navigate('/notes')
  }, [setSelectedId, navigate])

  return (
    <div className="flex h-full flex-col gap-4 p-4 overflow-auto">
      {/* ======== 知识图谱（语义互联，整页） ======== */}
      <Card className="flex-1 min-h-[400px] flex flex-col">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium">知识图谱（语义互联）</CardTitle>
          <div className="flex items-center gap-2">
            {/* 邻居数 K 滑块（控制默认边密度） */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <SlidersHorizontal className="size-3.5" />
              邻居数
              <input
                type="range"
                min={0}
                max={TOP_K_OPTIONS.length - 1}
                step={1}
                value={TOP_K_OPTIONS.indexOf(topK)}
                onChange={(e) => setTopK(TOP_K_OPTIONS[Number(e.target.value)])}
                className="w-28 accent-primary"
              />
              <span className="w-4">{topK}</span>
            </div>
            {/* 标签筛选下拉 */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-7 gap-1 text-xs">
                  标签筛选
                  {selectedTags.length > 0 && (
                    <Badge variant="secondary" className="text-[10px] px-1.5 h-4">{selectedTags.length}</Badge>
                  )}
                  <ChevronDown className="size-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-h-[240px] overflow-y-auto">
                <DropdownMenuLabel className="text-xs">点击切换选中</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {tags.map((tag) => (
                  <DropdownMenuItem key={tag.id} className="text-xs gap-2" onSelect={(e) => e.preventDefault()}>
                    <button
                      type="button"
                      className="flex flex-1 items-center gap-2"
                      onClick={() => toggleTag(tag.name)}
                    >
                      <span className={cn(
                        'flex size-4 items-center justify-center rounded border',
                        selectedTags.includes(tag.name) && 'bg-primary border-primary',
                      )}>
                        {selectedTags.includes(tag.name) && <Check className="size-3 text-primary-foreground" />}
                      </span>
                      {tag.name}
                      {tag.note_count ? ` (${tag.note_count})` : ''}
                    </button>
                  </DropdownMenuItem>
                ))}
                {selectedTags.length > 0 && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-xs" onClick={() => setSelectedTags([])}>
                      清除筛选
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="p-4 flex-1 min-h-0">
          <KnowledgeGraph
            nodes={graphNodes}
            edges={graphEdges}
            allEdges={filteredAllEdges}
            loading={loading}
            className="h-full"
            onNodeClick={handleNodeClick}
          />
        </CardContent>
      </Card>
    </div>
  )
}
