/**
 * DashboardPage — 数据看板页面（P7 真实图谱）
 * ------------------------------------------
 * 统计卡片（真实 stats API）+ 知识图谱（语义互联）+ 热门标签。
 * 图谱筛选: 关联强度滑块（客户端过滤边）+ 标签多选（过滤节点）。
 * 点击图谱节点 → 跳转打开对应笔记。
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import StatCard from '@/components/dashboard/StatCard'
import KnowledgeGraph from '@/components/dashboard/KnowledgeGraph'
import { dashboardApi, tagsApi } from '@/lib/api'
import { useNotesStore } from '@/stores/notes'
import {
  FileText,
  CheckCircle2,
  RefreshCw,
  Tags,
  Link2,
  BarChart3,
  SlidersHorizontal,
  ChevronDown,
  Check,
} from 'lucide-react'
import type { Tag, GraphNode, GraphEdge } from '@/types'
import { cn } from '@/lib/utils'

// 关联强度滑块档位（客户端过滤边，避免高频请求后端）
const THRESHOLD_STEPS = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70]
const THRESHOLD_LABELS = ['25%', '30%', '35%', '40%', '45%', '50%', '60%', '70%']

export default function DashboardPage() {
  const navigate = useNavigate()
  const setSelectedId = useNotesStore((s) => s.setSelectedId)

  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total_notes: 0, total_tags: 0, total_links: 0, synced: 0, pending: 0 })
  const [tags, setTags] = useState<Tag[]>([])
  const [allNodes, setAllNodes] = useState<GraphNode[]>([])
  const [allEdges, setAllEdges] = useState<GraphEdge[]>([])

  // ---- 筛选状态（纯客户端） ----
  const [threshold, setThreshold] = useState(0.35)
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [statsRes, graphRes, tagsRes] = await Promise.all([
        dashboardApi.stats(),
        dashboardApi.graph({ threshold: 0.25 }), // 拉取所有弱边，客户端按滑块过滤
        tagsApi.list(),
      ])
      setStats(statsRes)
      setTags(tagsRes.tags || [])
      setAllNodes(graphRes.nodes || [])
      setAllEdges(graphRes.edges || [])
    } catch (e) {
      console.error('加载看板数据失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // ---- 标签筛选：保留含任一选中标签的节点，边只保留两端都在保留节点内 ----
  const filteredNodes = selectedTags.length === 0
    ? allNodes
    : allNodes.filter((n) => n.tags?.some((t) => selectedTags.includes(t)))
  const nodeIdSet = new Set(filteredNodes.map((n) => n.id))
  const filteredEdges = allEdges.filter(
    (e) =>
      nodeIdSet.has(e.source) &&
      nodeIdSet.has(e.target) &&
      (e.weight || 0) >= threshold,
  )

  // 防抖：强度滑块不直接调用后端，用 useMemo 客户端过滤即可
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
    <div className="flex h-full flex-col gap-4 overflow-auto">
      {/* ======== 统计卡片 ======== */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard icon={FileText} label="笔记总数" value={stats.total_notes} color="text-blue-600 dark:text-blue-400" loading={loading} />
        <StatCard icon={Link2} label="关联数" value={stats.total_links} color="text-violet-600 dark:text-violet-400" loading={loading} subtitle="双向链接" />
        <StatCard icon={Tags} label="标签数" value={stats.total_tags} color="text-purple-600 dark:text-purple-400" loading={loading} />
        <StatCard
          icon={syncIcon(stats.pending)}
          label={stats.pending > 0 ? `待同步 ${stats.pending}` : '已同步'}
          value={stats.pending > 0 ? stats.pending : stats.synced}
          color={stats.pending > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}
          loading={loading}
        />
      </div>

      {/* ======== 中行：热门标签 ======== */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <BarChart3 className="size-4" />
            热门标签
            <span className="text-[10px] text-muted-foreground font-normal">（仅着色，不参与连线）</span>
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
                  className={cn(
                    'text-sm px-3 py-1 cursor-pointer transition-colors',
                    selectedTags.includes(tag.name) && 'bg-primary text-primary-foreground',
                  )}
                  onClick={() => toggleTag(tag.name)}
                >
                  {tag.name}
                  {tag.note_count ? ` (${tag.note_count})` : ''}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ======== 知识图谱（语义互联） ======== */}
      <Card className="flex-1 min-h-[400px]">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium">知识图谱（语义互联）</CardTitle>
          <div className="flex items-center gap-2">
            {/* 关联强度滑块 */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <SlidersHorizontal className="size-3.5" />
              关联强度
              <input
                type="range"
                min={0}
                max={THRESHOLD_STEPS.length - 1}
                step={1}
                value={THRESHOLD_STEPS.indexOf(threshold)}
                onChange={(e) => setThreshold(THRESHOLD_STEPS[Number(e.target.value)])}
                className="w-28 accent-primary"
              />
              <span className="w-9">{threshold.toFixed(2)}</span>
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
        <CardContent className="p-4 h-[420px]">
          <KnowledgeGraph
            nodes={graphNodes}
            edges={graphEdges}
            loading={loading}
            className="h-full"
            onNodeClick={handleNodeClick}
          />
        </CardContent>
      </Card>
    </div>
  )
}

/** 待同步>0 时显示刷新图标 */
function syncIcon(pending: number) {
  return pending > 0 ? RefreshCw : CheckCircle2
}
