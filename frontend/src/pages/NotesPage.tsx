/**
 * NotesPage — 智能笔记页面
 * -------------------------
 * 左侧: 笔记列表（搜索 + 新建 + 列表）
 * 右侧: 紧凑标题栏 + Vditor Markdown 编辑器（占满剩余空间）
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useNotesStore } from '@/stores/notes'
import NoteList from '@/components/notes/NoteList'
import VditorEditor from '@/components/notes/VditorEditor'
import EditorContextMenu from '@/components/notes/EditorContextMenu'
import TagSuggestBar from '@/components/notes/TagSuggestBar'
import RelatedNotesPanel from '@/components/notes/RelatedNotesPanel'
import { notesApi, tagsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import ContextMenu from '@/components/ui/context-menu'
import type { ContextMenuItemDef } from '@/components/ui/context-menu'
import {
  Save,
  Trash2,
  RefreshCw,
  NotebookPen,
  Sparkles,
  X,
  Tag,
  Pencil,
  Pin,
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
    syncNow,
    // 标签页（store 持久化，切页面不丢失）
    openTabs,
    dirtyTabIds,
    openTab,
    closeTab: closeTabStore,
    closeOtherTabs: closeOtherTabsStore,
    closeAllTabs: closeAllTabsStore,
    updateTabTitle,
    setTabDirty,
  } = useNotesStore()

  // 当前标签页是否 dirty（从 store 派生）
  const dirty = selectedId != null && dirtyTabIds.includes(selectedId)

  const setDirty = useCallback((v: boolean) => {
    if (selectedId != null) setTabDirty(selectedId, v)
  }, [selectedId, setTabDirty])

  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [noteTags, setNoteTags] = useState<Array<{ id: number; name: string }>>([])
  const [newTag, setNewTag] = useState('')
  const [showAddTag, setShowAddTag] = useState(false)
  const addTagInputRef = useRef<HTMLInputElement>(null)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [editingTabId, setEditingTabId] = useState<number | null>(null)  // 哪个标签页正在重命名
  const [renameTitle, setRenameTitle] = useState('')                      // 重命名输入

  // ---- AI 标签推荐（P4）----
  const [tagSuggestions, setTagSuggestions] = useState<TagSuggestion[]>([])
  const [mergeSuggestions, setMergeSuggestions] = useState<MergeSuggestion[]>([])
  const [tagSuggesting, setTagSuggesting] = useState(false)

  // 追踪已自动推荐过标签的笔记（只在首次保存时推荐，避免每次保存都推荐）
  const autoTaggedIds = useRef<Set<number>>(new Set())

  // ---- 正文标题高亮（P5.2.3）----
  const [highlightTitles, setHighlightTitles] = useState<string[]>([])

  // ---- 加载选中笔记内容 + 标签页管理 ----
  useEffect(() => {
    if (!selectedId) {
      setEditTitle('')
      setEditContent('')
      setNoteTags([])
      setNewTag('')
      setShowAddTag(false)
      setTagSuggestions([])
      setMergeSuggestions([])
      return
    }

    // 加入标签页（store 持久化）
    openTab(selectedId, '加载中…')

    fetchNote(selectedId).then((note) => {
      if (note) {
        setEditTitle(note.title)
        setEditContent(note.content || '')
        setNoteTags(note.tags || [])
        setNewTag('')
        setShowAddTag(false)
        setTagSuggestions([])
        setMergeSuggestions([])
        // 更新标签页标题
        updateTabTitle(selectedId, note.title)
      }
    })
  }, [selectedId])

  // ---- 关闭标签页 ----
  const closeTab = useCallback((tabId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    closeTabStore(tabId)
  }, [closeTabStore])

  // ---- 更新标签页标题（editTitle 变化时同步到 store） ----
  useEffect(() => {
    if (!selectedId) return
    updateTabTitle(selectedId, editTitle || '未命名')
  }, [editTitle, selectedId, updateTabTitle])

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
      const tags = noteTags.map((t) => t.name)
      const res = await updateNote(selectedId, { title: editTitle, content: editContent, tags })
      setDirty(false)
      toast.success('笔记已保存')
      // P4: 仅首次保存时自动触发 AI 标签推荐（已保存过的笔记不再重复推荐）
      if (!autoTaggedIds.current.has(selectedId)) {
        autoTaggedIds.current.add(selectedId)
        fetchTagSuggestions(selectedId)
      }
      // 同步最新标签（res 可能含后端规范化后的标签）
      if (res && res.tags) {
        setNoteTags(res.tags)
      }
    } catch (e) {
      toast.error('保存失败: ' + (e as Error).message)
    } finally {
      setSaving(false)
    }
  }, [selectedId, editTitle, editContent, noteTags, updateNote])

  /** 构建标签页右键菜单项 */
  const buildTabContextMenu = useCallback((tab: { id: number; title: string }): ContextMenuItemDef[] => {
    const isDirty = dirtyTabIds.includes(tab.id)
    const items: ContextMenuItemDef[] = [
      {
        label: '重命名',
        icon: <Pencil className="size-3.5" />,
        onClick: () => { setEditingTabId(tab.id); setRenameTitle(tab.title) },
      },
    ]
    if (isDirty) {
      items.push({
        label: '保存',
        icon: <Save className="size-3.5" />,
        onClick: () => { if (tab.id === selectedId) handleSave() },
        disabled: tab.id !== selectedId,
      })
    }
    items.push(
      { type: 'separator', label: '' },
      {
        label: '固定标签页',
        icon: <Pin className="size-3.5" />,
        onClick: () => toast.info('固定功能开发中…'),
        disabled: true,
      },
      { type: 'separator', label: '' },
      {
        label: '关闭',
        icon: <X className="size-3.5" />,
        shortcut: 'Ctrl+W',
        onClick: () => closeTabStore(tab.id),
      },
      {
        label: '关闭其他',
        icon: <X className="size-3.5" />,
        onClick: () => closeOtherTabsStore(tab.id),
        disabled: openTabs.length <= 1,
      },
      {
        label: '全部关闭',
        icon: <X className="size-3.5" />,
        onClick: closeAllTabsStore,
        disabled: openTabs.length === 0,
      },
    )
    return items
  }, [selectedId, handleSave, closeTabStore, closeOtherTabsStore, closeAllTabsStore, openTabs.length, dirtyTabIds])

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
  const applyTags = useCallback(async (newTagNames: string[]) => {
    if (!selectedId) return
    const existingNames = noteTags.map((t) => t.name)
    const merged = [...new Set([...existingNames, ...newTagNames])]
    try {
      const res = await updateNote(selectedId, { title: editTitle, content: editContent, tags: merged })
      setNoteTags(res.tags || [])
      setTagSuggestions([])
      setDirty(false)
      toast.success(`已应用 ${newTagNames.length} 个标签`)
    } catch (e) {
      toast.error('应用标签失败: ' + (e as Error).message)
    }
  }, [selectedId, editTitle, editContent, noteTags, updateNote])

  /** 手动添加单个标签（去重，标记 dirty） */
  const addTag = useCallback(() => {
    const name = newTag.trim()
    if (!name) return
    if (noteTags.some((t) => t.name === name)) {
      setNewTag('')
      addTagInputRef.current?.focus()
      return  // 已存在，静默跳过
    }
    const tempId = -Date.now()
    setNoteTags((prev) => [...prev, { id: tempId, name }])
    setNewTag('')
    setShowAddTag(false)
    setDirty(true)
  }, [newTag, noteTags])

  /** 打开加标签弹窗并聚焦输入框 */
  const openAddTag = useCallback(() => {
    setShowAddTag(true)
    setTimeout(() => addTagInputRef.current?.focus(), 50)
  }, [])

  /** 删除单个标签（标记 dirty） */
  const removeTag = useCallback((tagId: number) => {
    setNoteTags((prev) => prev.filter((t) => t.id !== tagId))
    setDirty(true)
  }, [])

  // ---- 删除笔记 ----
  const handleDelete = useCallback(async () => {
    if (!selectedId) return
    if (!confirm('确定要删除这篇笔记吗？')) return
    const id = selectedId
    try {
      await deleteNote(id)
      closeTabStore(id)  // 关闭对应标签页
      toast.success('笔记已删除')
    } catch (e) {
      toast.error('删除失败: ' + (e as Error).message)
    }
  }, [selectedId, deleteNote, closeTabStore])

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
            {/* ======== 第一行：标签页栏 + 操作按钮 ======== */}
            <div className="flex items-center shrink-0 border-b overflow-hidden">
              {/* 标签页（左侧，过多时自动压缩） */}
              <div className="flex items-center flex-1 min-w-0 overflow-hidden">
                {openTabs.map((tab) => {
                  const isActive = tab.id === selectedId
                  const isDirty = dirtyTabIds.includes(tab.id)
                  const isEditing = editingTabId === tab.id
                  return (
                    <ContextMenu key={tab.id} items={buildTabContextMenu(tab)}>
                      <div
                        onClick={() => { if (!isActive) setSelectedId(tab.id) }}
                        className={`
                          group flex items-center gap-1 h-8 px-2.5 text-xs cursor-pointer select-none
                          border-r transition-colors max-w-[180px] min-w-[64px] overflow-hidden
                          ${isActive
                            ? 'bg-background border-t border-t-primary text-foreground font-medium -mb-px'
                            : 'bg-muted/50 text-muted-foreground hover:bg-muted border-t border-t-transparent'
                          }
                        `}
                      >
                        {isEditing ? (
                          <input
                            value={renameTitle}
                            onChange={(e) => setRenameTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                setEditTitle(renameTitle)
                                setDirty(true)
                                setEditingTabId(null)
                              }
                              if (e.key === 'Escape') setEditingTabId(null)
                            }}
                            onBlur={() => {
                              if (renameTitle.trim()) { setEditTitle(renameTitle); setDirty(true) }
                              setEditingTabId(null)
                            }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-transparent border-0 outline-none text-xs font-medium w-full min-w-[60px]"
                            autoFocus
                          />
                        ) : (
                          <span className="truncate min-w-0">
                            {isDirty && <span className="text-amber-500 mr-0.5">●</span>}
                            {tab.title || '未命名'}
                          </span>
                        )}
                        <button
                          onClick={(e) => closeTab(tab.id, e)}
                          className="shrink-0 inline-flex items-center justify-center rounded-sm size-4
                                     opacity-0 group-hover:opacity-100 hover:bg-muted-foreground/20 transition-all cursor-pointer"
                          title="关闭"
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                    </ContextMenu>
                  )
                })}
              </div>

              {/* 操作按钮组（右侧，固定不压缩） */}
              <div className="flex items-center gap-0.5 shrink-0 pr-1">
                {/* 手动添加标签按钮 + 弹出输入框 */}
                {showAddTag ? (
                  <div className="flex items-center gap-0.5">
                    <Input
                      ref={addTagInputRef}
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); addTag() }
                        if (e.key === 'Escape') { setShowAddTag(false); setNewTag('') }
                      }}
                      onBlur={() => { setTimeout(() => { setShowAddTag(false); setNewTag('') }, 150) }}
                      placeholder="输入标签名…"
                      className="text-xs border h-7 w-[110px] shrink-0 focus-visible:ring-0 px-1.5"
                    />
                    <Button variant="ghost" size="icon" className="size-6" onClick={addTag} disabled={!newTag.trim()}>
                      <X className="size-3" />
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 text-muted-foreground hover:text-foreground"
                    onClick={openAddTag}
                    title="添加标签"
                  >
                    <Tag className="size-3.5" />
                  </Button>
                )}
                <Button variant="ghost" size="icon" className="size-7" onClick={handleSync} disabled={syncing} title="同步到向量库">
                  <RefreshCw className={`size-3.5 ${syncing ? 'animate-spin' : ''}`} />
                </Button>
                <Button variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive" onClick={handleDelete} title="删除笔记">
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
            </div>

            {/* ======== AI 标签推荐条 ======== */}
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

            {/* ======== 编辑区域 ======== */}
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

            {/* ======== 底部状态栏：保存状态居左 + 标签居右 ======== */}
            <div className="flex items-center gap-2 shrink-0 px-2 py-1">
              {/* 左侧：保存状态 */}
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className={dirty ? 'text-amber-500' : ''}>
                  {dirty ? '● 未保存' : '已保存'}
                </span>
                <span>Ctrl+S</span>
              </div>

              {/* 占位 */}
              <div className="flex-1" />

              {/* 右侧：已有标签（× 仅在悬停时显示） */}
              {noteTags.map((tag) => (
                <Badge
                  key={tag.id}
                  variant="secondary"
                  className="text-[11px] px-1.5 py-0 gap-0.5 select-none group/tag"
                >
                  {tag.name}
                  <button
                    onClick={() => removeTag(tag.id)}
                    className="inline-flex items-center justify-center rounded-full
                               opacity-0 group-hover/tag:opacity-100 hover:bg-muted-foreground/20
                               transition-all cursor-pointer"
                    title={`删除标签「${tag.name}」`}
                  >
                    <X className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </>
        ) : (
          /* 空状态 */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <NotebookPen className="size-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground text-sm">选择或创建一篇笔记开始编辑</p>
              <p className="text-xs text-muted-foreground mt-1">
                左侧 + 或右键文件夹可上传 PDF / Word / Markdown 笔记
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
