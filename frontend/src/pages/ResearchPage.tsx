/**
 * ResearchPage — 深度研究页面
 * ---------------------------
 * 研究主题输入 + Agent 进度可视化 + 流式报告输出。
 *
 * 注意: 后端 /api/research/start 接口待实现，
 * 当前前端做 UI 占位，通过模拟数据展示效果。
 */
import { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import AgentProgress from '@/components/agents/AgentProgress'
import { Telescope, FileText, Download } from 'lucide-react'
import { toast } from 'sonner'
import type { AgentStep } from '@/types'

export default function ResearchPage() {
  const [topic, setTopic] = useState('')
  const [useWebSearch, setUseWebSearch] = useState(true)
  const [useKnowledgeBase, setUseKnowledgeBase] = useState(true)
  const [running, setRunning] = useState(false)
  const [steps, setSteps] = useState<AgentStep[]>([
    { agent: 'retriever', status: 'pending' },
    { agent: 'analyst', status: 'pending' },
    { agent: 'writer', status: 'pending' },
    { agent: 'reviewer', status: 'pending' },
  ])
  const [report, setReport] = useState('')

  const handleStart = useCallback(async () => {
    if (!topic.trim() || running) return

    setRunning(true)
    setReport('')
    setSteps([
      { agent: 'retriever', status: 'running', message: '正在检索相关资料...' },
      { agent: 'analyst', status: 'pending' },
      { agent: 'writer', status: 'pending' },
      { agent: 'reviewer', status: 'pending' },
    ])

    try {
      // TODO: 替换为真实 SSE 流式调用
      // for await (const event of researchStream(topic, useWebSearch, useKnowledgeBase)) { ... }

      // 模拟 Agent 流程
      await new Promise((r) => setTimeout(r, 1500))
      setSteps((s) => s.map((a) => (a.agent === 'retriever' ? { ...a, status: 'completed' as const, message: '找到相关资料' } : a)))
      setSteps((s) => s.map((a) => (a.agent === 'analyst' ? { ...a, status: 'running' as const, message: '正在分析...' } : a)))

      await new Promise((r) => setTimeout(r, 1500))
      setSteps((s) => s.map((a) => (a.agent === 'analyst' ? { ...a, status: 'completed' as const, message: '分析完成' } : a)))
      setSteps((s) => s.map((a) => (a.agent === 'writer' ? { ...a, status: 'running' as const, message: '正在生成报告...' } : a)))

      await new Promise((r) => setTimeout(r, 1500))
      setReport(`# 深度研究报告: ${topic}\n\n## 一、研究概述\n本研究针对 "${topic}" 进行了系统性的资料检索和分析。\n\n## 二、关键发现\n待后端 /api/research/start 接口实现后，此区域将显示实时的流式报告内容。\n\n## 三、结论\n深度研究功能的 UI 框架已搭建完成，后端接口待开发。`)
      setSteps((s) => s.map((a) => (a.agent === 'writer' ? { ...a, status: 'completed' as const, message: '报告初稿完成' } : a)))
      setSteps((s) => s.map((a) => (a.agent === 'reviewer' ? { ...a, status: 'running' as const, message: '正在审核...' } : a)))

      await new Promise((r) => setTimeout(r, 1000))
      setSteps((s) => s.map((a) => (a.agent === 'reviewer' ? { ...a, status: 'completed' as const, message: '审核通过' } : a)))

      toast.success('研究完成')
    } catch (e) {
      toast.error('研究失败: ' + (e as Error).message)
    } finally {
      setRunning(false)
    }
  }, [topic, useWebSearch, useKnowledgeBase, running])

  const handleExport = () => {
    if (!report) return
    const blob = new Blob([report], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `研究报告-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('报告已导出')
  }

  return (
    <div className="flex h-full flex-col gap-4">
      {/* ======== 研究主题输入 ======== */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="输入研究主题，如「对比2024年新能源汽车市场的主流技术路线」"
                disabled={running}
                className="text-sm"
              />
            </div>
            <Button
              onClick={handleStart}
              disabled={!topic.trim() || running}
              className="gap-2"
            >
              <Telescope className="size-4" />
              {running ? '研究中...' : '开始研究'}
            </Button>
          </div>
          <div className="flex items-center gap-6 mt-3">
            <div className="flex items-center gap-2">
              <Switch
                id="web-search"
                checked={useWebSearch}
                onCheckedChange={setUseWebSearch}
                disabled={running}
              />
              <Label htmlFor="web-search" className="text-sm cursor-pointer">
                联网搜索
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="kb-search"
                checked={useKnowledgeBase}
                onCheckedChange={setUseKnowledgeBase}
                disabled={running}
              />
              <Label htmlFor="kb-search" className="text-sm cursor-pointer">
                使用知识库
              </Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ======== Agent 进度 ======== */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            研究进度
            {running && <Badge variant="secondary" className="text-[10px]">运行中</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0 overflow-x-auto">
          <AgentProgress steps={steps} />
        </CardContent>
      </Card>

      {/* ======== 报告输出 ======== */}
      <Card className="flex-1 min-h-0">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileText className="size-4" />
            研究报告
          </CardTitle>
          {report && (
            <Button variant="ghost" size="sm" className="gap-1" onClick={handleExport}>
              <Download className="size-3.5" />
              导出
            </Button>
          )}
        </CardHeader>
        <Separator />
        <CardContent className="p-0 h-full">
          <ScrollArea className="h-[300px] p-4">
            {report ? (
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {report}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full py-16">
                <div className="text-center">
                  <FileText className="size-10 mx-auto text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    研究报告将显示在这里
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    输入研究主题后点击"开始研究"
                  </p>
                </div>
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
