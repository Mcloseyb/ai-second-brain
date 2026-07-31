/**
 * UploadNoteDialog — 上传笔记对话框
 * ---------------------------------
 * 选择文件 → 标题（Markdown 自动解析 / 手动设置）→ 标签（手动 / AI 推荐）→ 导入到目标文件夹。
 * 目标文件夹由调用方传入（"+"菜单 = 根目录；文件夹右键 = 该文件夹）。
 */
import { useState, useRef } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Upload, FileText, Sparkles, Loader2 } from 'lucide-react'
import { notesApi, documentsApi } from '@/lib/api'
import { useNotesStore } from '@/stores/notes'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { TagSuggestion } from '@/types'

interface UploadNoteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 目标文件夹（'' = 笔记库根目录） */
  folder: string
  /** 目标笔记库 ID */
  notebookId: number | null
}

const ACCEPTED = '.md,.docx,.pdf,.txt'

/** 从 Markdown 文本提取第一个 # 标题 */
function extractMdTitle(text: string): string {
  for (const line of text.split('\n')) {
    const s = line.trim()
    if (s.startsWith('# ') && s.length > 2) return s.slice(2).trim()
  }
  return ''
}

export default function UploadNoteDialog({
  open,
  onOpenChange,
  folder,
  notebookId,
}: UploadNoteDialogProps) {
  const importNoteToFolder = useNotesStore((s) => s.importNoteToFolder)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [suggestions, setSuggestions] = useState<TagSuggestion[]>([])
  const [suggesting, setSuggesting] = useState(false)
  const [uploading, setUploading] = useState(false)
  // md/txt 客户端读取的内容（供 AI 推荐标签）
  const contentRef = useRef('')

  // 关闭时清空，保证下次打开是全新状态
  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setFile(null)
      setTitle('')
      setTags('')
      setSuggestions([])
      contentRef.current = ''
    }
    onOpenChange(open)
  }

  // ---- 选择文件：md/txt 客户端解析标题；docx/pdf 留空由后端解析 ----
  const handlePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    setFile(f)
    setTags('')
    setSuggestions([])
    contentRef.current = ''
    const ext = f.name.split('.').pop()?.toLowerCase()
    if (ext === 'md' || ext === 'txt') {
      const reader = new FileReader()
      reader.onload = () => {
        const text = String(reader.result || '')
        contentRef.current = text
        const parsedTitle = extractMdTitle(text)
        setTitle(parsedTitle || f.name.replace(/\.(md|txt)$/i, ''))
      }
      reader.readAsText(f)
    } else {
      setTitle('')
    }
  }

  // ---- AI 推荐标签（简易版）：md/txt 用客户端内容；docx/pdf 先调 parse 取内容 ----
  const handleSuggest = async () => {
    if (!file) return
    setSuggesting(true)
    try {
      let content = contentRef.current
      if (!content) {
        const parsed = await documentsApi.parse(file)
        content = parsed.content
        if (!title) setTitle(parsed.title)
      }
      const res = await notesApi.suggestTags({ title: title || file.name, content })
      setSuggestions(res.suggestions || [])
      if (!res.suggestions?.length) toast.info('未能提取到标签建议')
    } catch (e) {
      toast.error('AI 标签推荐失败: ' + (e as Error).message)
    } finally {
      setSuggesting(false)
    }
  }

  // ---- 采纳建议标签：去重合并到标签输入框 ----
  const applySuggestion = (tag: string) => {
    const current = tags
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    if (!current.includes(tag)) setTags([...current, tag].join(', '))
  }

  // ---- 导入 ----
  const handleUpload = async () => {
    if (!file) {
      toast.error('请先选择文件')
      return
    }
    if (!notebookId) {
      toast.error('请先选择笔记库')
      return
    }
    setUploading(true)
    try {
      await importNoteToFolder(file, notebookId, folder, tags, title)
      toast.success(`"${file.name}" 已导入到 ${folder || '根目录'}`)
      handleOpenChange(false)
    } catch (e) {
      toast.error('导入失败: ' + (e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle className="text-base">
            上传笔记{folder ? ` → ${folder}` : ''}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          {/* 文件选择 */}
          <div>
            <Label className="text-xs text-muted-foreground">选择文件</Label>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              onChange={handlePick}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                'w-full flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed py-4 transition-colors',
                file
                  ? 'border-primary/60 bg-primary/5'
                  : 'border-muted-foreground/30 hover:border-muted-foreground/50',
              )}
            >
              {file ? (
                <>
                  <FileText className="size-5 text-primary" />
                  <span className="text-sm font-medium">{file.name}</span>
                  <span className="text-[10px] text-muted-foreground">点击重新选择</span>
                </>
              ) : (
                <>
                  <Upload className="size-5 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">选择 Markdown / Word / PDF / TXT</span>
                </>
              )}
            </button>
          </div>

          {/* 标题 */}
          <div>
            <Label className="text-xs text-muted-foreground">
              标题（Markdown 自动解析，可修改）
            </Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="留空自动从文件解析"
              className="h-8 text-sm"
            />
          </div>

          {/* 标签 */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <Label className="text-xs text-muted-foreground">标签（逗号分隔）</Label>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 gap-1 text-xs text-violet-500 hover:text-violet-600"
                onClick={handleSuggest}
                disabled={!file || suggesting}
              >
                {suggesting ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
                AI 推荐标签
              </Button>
            </div>
            <Input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="如: AI, 知识管理"
              className="h-8 text-sm"
            />
            {suggestions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {suggestions.map((s) => (
                  <Badge
                    key={`${s.tag}-${s.type}`}
                    variant="secondary"
                    className={cn('cursor-pointer', s.type === 'new' && 'border-dashed')}
                    title={`${s.type === 'existing' ? '复用已有标签' : '建议新建'} · 相关度 ${s.score}`}
                    onClick={() => applySuggestion(s.tag)}
                  >
                    {s.tag}
                    {s.type === 'new' ? '＋' : ''}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="mt-2">
          <Button variant="outline" size="sm" onClick={() => handleOpenChange(false)}>
            取消
          </Button>
          <Button size="sm" onClick={handleUpload} disabled={!file || uploading || !notebookId}>
            {uploading ? <Loader2 className="size-3 animate-spin" /> : <Upload className="size-3" />}
            导入
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
