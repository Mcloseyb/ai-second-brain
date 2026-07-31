/**
 * NotesPage — 智能笔记页面
 * -------------------------
 * 左侧: 笔记列表（搜索 + 新建 + 列表）
 * 右侧: 紧凑标题栏 + Vditor Markdown 编辑器（占满剩余空间）
 */
import { useState, useEffect, useCallback } from 'react'
import { useNotesStore } from '@/stores/notes'
import NoteList from '@/components/notes/NoteList'
import VditorEditor from '@/components/notes/VditorEditor'
import EditorContextMenu from '@/components/notes/EditorContextMenu'
import TagSuggestBar from '@/components/notes/TagSuggestBar'
import RelatedNotesPanel from '@/components/notes/RelatedNotesPanel'
import FileDropZone from '@/components/documents/FileDropZone'
import { notesApi, tagsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Save,
  Trash2,
  Upload,
  RefreshCw,
  NotebookPen,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import type { TagSuggestion, MergeSuggestion } from '@/types'

export default function NotesPage() {
  const {
    selectedId,
    setSelectedId,
    activeNotebookId,
    fetchNote,
    updateNote,
    deleteNote,
    importFile,
    syncNow,
  } = useNotesStore()

  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editTags, setEditTags] = useState('')
  const [noteTags, setNoteTags] = useState<Array<{ id: number; name: string }>>([])
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [showImport, setShowImport] = useState(false)

  // ---- AI 标签推荐（P4）----
  const [tagSuggestions, setTagSuggestions] = useState<TagSuggestion[]>([])
  const [mergeSuggestions, setMergeSuggestions] = useState<MergeSuggestion[]>([])
  const [tagSuggesting, setTagSuggesting] = useState(false)

  // ---- 正文标题高亮（P5.2.3）----
  const [highlightTitles, setHighlightTitles] = useState<string[]>([])

  // ---- 加载选中笔记内容 ----
  useEffect(() => {
    if (!selectedId) {
      setEditTitle('')
      setEditContent('')
      setEditTags('')
      setNoteTags([])
      setDirty(false)
      setTagSuggestions([])
      setMergeSuggestions([])
      return
    }

    fetchNote(selectedId).then((note) => {
      if (note) {
        setEditTitle(note.title)
        setEditContent(note.content || '')
        setNoteTags(note.tags || [])
        setEditTags((note.tags || []).map((t) => t.name).join(', '))
        setDirty(false)
        setTagSuggestions([])
        setMergeSuggestions([])
      }
    })
  }, [selectedId])

  // ---- 加载正文标题高亮数据（P5.2.3） ----
  useEffect(() => {
    if (!selectedId) {
      setHighlightTitles([])
      return
    }
    notesApi.titleLinks(selectedId)
      .then((res) => {
        setHighlightTitles((res.detections || []).map((d) => d.title))
      })
      .catch(() => setHighlightTitles([]))
  }, [selectedId])

  // ---- 保存笔记 ----
  const handleSave = useCallback(async () => {
    if (!selectedId) return
    setSaving(true)
    try {
      const tags = editTags
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean)
      const res = await updateNote(selectedId, { title: editTitle, content: editContent, tags })
      setDirty(false)
      toast.success('笔记已保存')
      // P4: 保存成功后自动触发 AI 标签推荐
      fetchTagSuggestions(selectedId)
      // 同步最新标签（res 可能含后端规范化后的标签）
      if (res && res.tags) {
        setNoteTags(res.tags)
        setEditTags(res.tags.map((t) => t.name).join(', '))
      }
    } catch (e) {
      toast.error('保存失败: ' + (e as Error).message)
    } finally {
      setSaving(false)
    }
  }, [selectedId, editTitle, editContent, editTags, updateNote])

  // ---- P4: AI 标签推荐（mode: simple=简易版 / llm=完整版） ----
  const fetchTagSuggestions = useCallback(async (noteId: number, mode: 'simple' | 'llm' = 'simple') => {
    setTagSuggesting(true)
    try {
      const res = await notesApi.autoTag(noteId, mode)
      setTagSuggestions(res.suggestions || [])
      setMergeSuggestions(res.merge_suggestions || [])
    } catch {
      setTagSuggestions([]) // 失败静默，不影响编辑
      setMergeSuggestions([])
    } finally {
      setTagSuggesting(false)
    }
  }, [])

  /** 应用标签合并建议（from → to） */
  const applyMerge = useCallback(async (from: string, to: string) => {
    try {
      const res = await tagsApi.merge(from, to)
      setMergeSuggestions((prev) =>
        prev.filter((m) => !(m.from === from && m.to === to)),
      )
      toast.success(
        `已合并标签: ${res.from} → ${res.to}` +
          (res.merged > 0 ? `（迁移 ${res.merged} 篇笔记）` : ''),
      )
    } catch (e) {
      toast.error('合并失败: ' + (e as Error).message)
    }
  }, [])

  /** 采纳标签（单个/全部），合并到当前标签并立即保存 */
  const applyTags = useCallback(async (newTags: string[]) => {
    if (!selectedId) return
    const current = editTags
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    const merged = [...new Set([...current, ...newTags])]
    try {
      const res = await updateNote(selectedId, { title: editTitle, content: editContent, tags: merged })
      setNoteTags(res.tags || [])
      setEditTags((res.tags || []).map((t) => t.name).join(', '))
      setTagSuggestions([])
      setDirty(false)
      toast.success(`已应用 ${newTags.length} 个标签`)
    } catch (e) {
      toast.error('应用标签失败: ' + (e as Error).message)
    }
  }, [selectedId, editTitle, editContent, editTags, updateNote])

  // ---- 删除笔记 ----
  const handleDelete = useCallback(async () => {
    if (!selectedId) return
    if (!confirm('确定要删除这篇笔记吗？')) return
    try {
      await deleteNote(selectedId)
      toast.success('笔记已删除')
    } catch (e) {
      toast.error('删除失败: ' + (e as Error).message)
    }
  }, [selectedId, deleteNote])

  // ---- 导入文件 ----
  const handleImport = useCallback(
    async (file: File) => {
      await importFile(file)
      setShowImport(false)
    },
    [importFile],
  )

  // ---- 同步到向量库 ----
  const handleSync = useCallback(async () => {
    setSyncing(true)
    try {
      const report = await syncNow()
      toast.success(
        `同步完成: ${report.synced} 篇已同步, ${report.skipped} 篇跳过`,
      )
    } catch (e) {
      toast.error('同步失败: ' + (e as Error).message)
    } finally {
      setSyncing(false)
    }
  }, [syncNow])

  // ---- Ctrl+S 快捷键 ----
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        if (dirty && selectedId) handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [dirty, selectedId, handleSave])

  return (
    <div className="flex h-full gap-4">
      {/* ======== 左侧：笔记列表 ======== */}
      <div className="w-[260px] shrink-0 h-full border rounded-lg bg-card overflow-hidden flex flex-col">
        <NoteList />
      </div>

      {/* ======== 中间：编辑器（占满剩余空间） ======== */}
      <div className="flex-1 min-w-0 h-full flex flex-col">
        {selectedId ? (
          <>
            {/* 导入区域（可折叠） */}
            {showImport && (
              <FileDropZone onFile={handleImport} disabled={false} />
            )}

            {/* 紧凑标题栏：标题 + 标签 + 操作按钮 全部在一行 */}
            <div className="flex items-center gap-1.5 shrink-0 px-1 py-0.5">
              <Input
                value={editTitle}
                onChange={(e) => {
                  setEditTitle(e.target.value)
                  setDirty(true)
                }}
                placeholder="笔记标题"
                className="text-sm font-medium border-0 h-7 flex-1 min-w-0 focus-visible:ring-0 px-1.5"
              />
              <Input
                value={editTags}
                onChange={(e) => {
                  setEditTags(e.target.value)
                  setDirty(true)
                }}
                placeholder="标签（逗号分隔）"
                className="text-xs border-0 h-7 w-[160px] shrink-0 focus-visible:ring-0 px-1.5 text-muted-foreground"
              />
              {noteTags.length > 0 && (
                <div className="flex gap-1 shrink-0">
                  {noteTags.map((tag) => (
                    <Badge key={tag.id} variant="secondary" className="text-[10px] px-1.5 py-0">
                      {tag.name}
                    </Badge>
                  ))}
                </div>
              )}
              <div className="w-px h-4 bg-border mx-0.5 shrink-0" />
              <Button variant="ghost" size="icon" className="size-7" onClick={() => setShowImport(!showImport)} title="导入">
                <Upload className="size-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="size-7" onClick={handleSync} disabled={syncing} title="同步">
                <RefreshCw className={`size-3.5 ${syncing ? 'animate-spin' : ''}`} />
              </Button>
              <Button variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive" onClick={handleDelete} title="删除">
                <Trash2 className="size-3.5" />
              </Button>
              <Button
                variant="ghost" size="icon" className="size-7 text-violet-500 hover:text-violet-600"
                onClick={() => fetchTagSuggestions(selectedId, 'llm')}
                disabled={tagSuggesting}
                title="AI 打标签（完整版 · LLM 分析）"
              >
                <Sparkles className={`size-3.5 ${tagSuggesting ? 'animate-pulse' : ''}`} />
              </Button>
              <Button size="icon" className="size-7" onClick={handleSave} disabled={saving || !dirty} title="保存 (Ctrl+S)">
                <Save className="size-3.5" />
              </Button>
            </div>

            {/* AI 标签推荐条（保存后自动弹出 / 点击 Sparkles 手动触发完整版） */}
            <TagSuggestBar
              suggestions={tagSuggestions}
              mergeSuggestions={mergeSuggestions}
              loading={tagSuggesting}
              onAccept={(tag) => applyTags([tag])}
              onAcceptAll={() => applyTags(tagSuggestions.map((s) => s.tag))}
              onDismiss={() => {
                setTagSuggestions([])
                setMergeSuggestions([])
              }}
              onApplyMerge={applyMerge}
            />

            {/* 编辑区域：占满全部剩余空间 */}
            <EditorContextMenu className="flex-1 min-h-0 mt-0.5">
              <div className="h-full border rounded-lg overflow-hidden">
                <VditorEditor
                  value={editContent}
                  onChange={(v) => {
                    setEditContent(v)
                    setDirty(true)
                  }}
                  className="h-full"
                  highlightTitles={highlightTitles}
                />
              </div>
            </EditorContextMenu>

            {/* 底部状态栏 */}
            <div className="flex items-center gap-2 shrink-0 text-[11px] text-muted-foreground px-2 py-0.5">
              <span className={dirty ? 'text-amber-500' : ''}>
                {dirty ? '● 未保存' : '已保存'}
              </span>
              <span>Ctrl+S</span>
            </div>
          </>
        ) : (
          /* 空状态 */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <NotebookPen className="size-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground text-sm">选择或创建一篇笔记开始编辑</p>
              <p className="text-xs text-muted-foreground mt-1">
                支持拖拽上传 PDF、Word、Markdown 文件
              </p>
            </div>
          </div>
        )}
      </div>

      {/* ======== 最右侧：智能双向链接面板（P5，可折叠） ======== */}
      {selectedId && (
        <RelatedNotesPanel noteId={selectedId} onSelect={setSelectedId} />
      )}
    </div>
  )
}
