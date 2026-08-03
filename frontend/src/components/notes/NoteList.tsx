/**
 * NoteList — 笔记侧边栏（类 Windows 资源管理器风格）
 * ----------------------------------------------
 * 笔记库选择器 → 文件夹树（笔记挂在文件夹下）→ 根目录笔记
 */
import { useEffect, useState, useCallback } from 'react'
import { useNotesStore } from '@/stores/notes'
import { notesApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Plus, Search, FileText, Folder, FolderOpen,
  ChevronRight, ChevronDown, Library, Upload,
  Trash2, Pencil, AlertTriangle,
} from 'lucide-react'
import UploadNoteDialog from '@/components/notes/UploadNoteDialog'
import {
  DropdownMenu, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import ContextMenu from '@/components/ui/context-menu'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import type { FolderNode, NoteListItem } from '@/types'

/** 单条笔记行 */
function NoteRow({ note, selectedId, onSelect, onDelete }: {
  note: NoteListItem
  selectedId: number | null
  onSelect: (id: number) => void
  onDelete: (note: NoteListItem) => void
}) {
  const d = new Date(note.updated_at)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const timeStr = diff < 86400000
    ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : diff < 604800000 ? `${Math.floor(diff / 86400000)}天前`
    : d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })

  return (
    <ContextMenu items={[
      { label: '删除', icon: <Trash2 className="size-3.5" />, onClick: () => onDelete(note), danger: true },
    ]}>
      <button
        className={cn(
          'flex w-full items-start gap-2 rounded-sm px-2 py-1 text-left transition-colors hover:bg-accent',
          selectedId === note.id && 'bg-accent',
        )}
        onClick={() => onSelect(note.id)}
      >
        <FileText className="size-3.5 mt-0.5 shrink-0 text-muted-foreground" />
        <div className="flex-1 min-w-0">
          <p className="text-sm truncate">{note.title || '无标题'}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] text-muted-foreground">{timeStr}</span>
            {note.tags?.slice(0, 1).map((tag) => (
              <Badge key={tag.id} variant="secondary" className="text-[10px] px-1 py-0 h-4">{tag.name}</Badge>
            ))}
          </div>
        </div>
      </button>
    </ContextMenu>
  )
}

export default function NoteList() {
  const {
    loading, searchQuery, selectedId,
    notebooks, activeNotebookId, folderTree, rootNotes,
    setSearchQuery, setSelectedId, fetchNotebooks,
    createNote, deleteNote, moveNote,
    createNotebook, setActiveNotebook, fetchFolderTree,
  } = useNotesStore()

  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [notebookMenuOpen, setNotebookMenuOpen] = useState(false)
  const [newNotebookName, setNewNotebookName] = useState('')
  const [newFolderMode, setNewFolderMode] = useState(false)
  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderParent, setNewFolderParent] = useState('')

  // ---- 上传笔记对话框（加号菜单 + 文件夹右键） ----
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFolder, setUploadFolder] = useState('')

  // ---- 删除确认弹窗 ----
  const [deleteConfirm, setDeleteConfirm] = useState<{
    open: boolean; type: 'note' | 'folder'; target: NoteListItem | FolderNode | null; count: number
  }>({ open: false, type: 'note', target: null, count: 0 })

  const openUpload = (folder = '') => {
    setUploadFolder(folder)
    setUploadOpen(true)
  }

  useEffect(() => { fetchNotebooks() }, [])

  // ---- 笔记库 ----
  const handleSwitchNotebook = useCallback(async (id: number) => {
    await setActiveNotebook(id)
    setExpandedFolders(new Set())
  }, [setActiveNotebook])

  const handleCreateNotebook = async () => {
    const name = newNotebookName.trim()
    if (!name) return
    try {
      const nb = await createNotebook(name)
      setNewNotebookName('')
      setNotebookMenuOpen(false)
      await setActiveNotebook(nb.id)
      toast.success(`笔记库「${name}」已创建`)
    } catch (e) { toast.error('创建失败: ' + (e as Error).message) }
  }

  // ---- 文件夹 ----
  const toggleFolder = (path: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path); else next.add(path)
      return next
    })
  }

  const handleNewNote = async (folder = '') => {
    if (!activeNotebookId) return
    try {
      await createNote(activeNotebookId, folder)
      await fetchFolderTree()
      toast.success('笔记已创建')
    } catch (e) { toast.error('创建失败: ' + (e as Error).message) }
  }

  const handleCreateFolder = (parentPath = '') => {
    setNewFolderParent(parentPath)
    setNewFolderName('')
    setNewFolderMode(true)
  }

  const confirmCreateFolder = async () => {
    if (!newFolderName.trim() || !activeNotebookId) return
    const folderPath = newFolderParent
      ? `${newFolderParent}/${newFolderName.trim()}`
      : newFolderName.trim()
    await createNote(activeNotebookId, folderPath, '_folder_placeholder_', '')
    await fetchFolderTree()
    setNewFolderMode(false)
    toast.success('文件夹已创建')
  }

  const handleDeleteNote = (note: NoteListItem) => {
    setDeleteConfirm({ open: true, type: 'note', target: note, count: 0 })
  }

  const confirmDeleteNote = async () => {
    const note = deleteConfirm.target as NoteListItem | null
    if (!note) return
    try { await deleteNote(note.id); toast.success('已移入回收站'); await fetchFolderTree() }
    catch (e) { toast.error('删除失败: ' + (e as Error).message) }
    setDeleteConfirm({ open: false, type: 'note', target: null, count: 0 })
  }

  const handleDeleteFolder = async (folder: FolderNode) => {
    if (!activeNotebookId) return
    // 先统计笔记数
    try {
      const res: any = await notesApi.folderNoteCount(activeNotebookId, folder.path)
      const count = res.data?.count ?? res.count ?? 0
      setDeleteConfirm({ open: true, type: 'folder', target: folder, count })
    } catch {
      setDeleteConfirm({ open: true, type: 'folder', target: folder, count: 0 })
    }
  }

  const confirmDeleteFolder = async () => {
    const folder = deleteConfirm.target as FolderNode | null
    if (!folder || !activeNotebookId) return
    try {
      const res: any = await notesApi.deleteFolder(activeNotebookId, folder.path)
      const deleted = res.data?.deleted ?? res.deleted ?? 0
      toast.success(`文件夹「${folder.name}」已删除，${deleted} 篇笔记移入回收站`)
      await fetchFolderTree()
    } catch (e) { toast.error('删除失败: ' + (e as Error).message) }
    setDeleteConfirm({ open: false, type: 'folder', target: null, count: 0 })
  }

  const handleRenameFolder = async (oldPath: string) => {
    const newName = prompt('新文件夹名:', oldPath.split('/').pop() || '')
    if (!newName || !activeNotebookId) return
    const parts = oldPath.split('/')
    parts[parts.length - 1] = newName
    const newPath = parts.join('/')
    // 需要从 folderTree 中获取受影响的笔记...简化处理：遍历所有 notes
    // 由于需要遍历整个树，简化地用 fetch 刷新
    try {
      // 重命名：先创建新路径占位，再删除旧路径笔记，再移动子笔记...这太复杂
      // 简化：移动该文件夹直属笔记到新路径
      const findFolder = (folders: FolderNode[], path: string): FolderNode | null => {
        for (const f of folders) {
          if (f.path === path) return f
          const found = findFolder(f.children, path)
          if (found) return found
        }
        return null
      }
      const target = findFolder(folderTree, oldPath)
      if (target) {
        const allNotes = [...target.notes, ...target.children.flatMap(c => [...c.notes, ...c.children.flatMap(x => [...x.notes, ...x.children.flatMap(y => y.notes)])])]
        for (const n of allNotes) {
          const newNoteFolder = n.folder === oldPath ? newPath : newPath + (n.folder || '').slice(oldPath.length)
          try { await moveNote(n.id, newNoteFolder) } catch { /* skip */ }
        }
      }
      await fetchFolderTree()
      toast.success('文件夹已重命名')
    } catch (e) { toast.error('重命名失败') }
  }

  // ---- 递归渲染文件夹（含笔记） ----
  const renderFolder = (folder: FolderNode, depth = 0): React.ReactNode => {
    const isExpanded = expandedFolders.has(folder.path)
    const padLeft = 8 + depth * 14

    return (
      <div key={folder.path}>
        {/* 文件夹行 */}
        <ContextMenu items={[
          { label: '在此新建笔记', icon: <FileText className="size-3.5" />, onClick: () => handleNewNote(folder.path) },
          { label: '新建子文件夹', icon: <Folder className="size-3.5" />, onClick: () => handleCreateFolder(folder.path) },
          { label: '在此上传笔记', icon: <Upload className="size-3.5" />, onClick: () => openUpload(folder.path) },
          { type: 'separator', label: '' },
          { label: '重命名', icon: <Pencil className="size-3.5" />, onClick: () => handleRenameFolder(folder.path) },
          { type: 'separator', label: '' },
          { label: '删除文件夹', icon: <Trash2 className="size-3.5" />, onClick: () => handleDeleteFolder(folder), danger: true },
        ]}>
          <button
            className="flex w-full items-center gap-1.5 rounded-sm py-1 pr-2 text-left text-sm hover:bg-accent transition-colors"
            style={{ paddingLeft: `${padLeft}px` }}
            onClick={() => toggleFolder(folder.path)}
          >
            {isExpanded ? <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                         : <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />}
            {isExpanded ? <FolderOpen className="size-3.5 shrink-0 text-amber-500" />
                         : <Folder className="size-3.5 shrink-0 text-amber-500" />}
            <span className="flex-1 truncate font-medium">{folder.name}</span>
            <span className="text-[10px] text-muted-foreground shrink-0">{folder.note_count}</span>
          </button>
        </ContextMenu>

        {/* 展开后显示：子文件夹 + 笔记 */}
        {isExpanded && (
          <>
            {(folder.children || []).map((child) => renderFolder(child, depth + 1))}
            {(folder.notes || []).map((note) => (
              <div key={note.id} style={{ paddingLeft: `${padLeft + 16}px` }}>
                <NoteRow note={note} selectedId={selectedId} onSelect={setSelectedId} onDelete={handleDeleteNote} />
              </div>
            ))}
          </>
        )}
      </div>
    )
  }

  const activeNb = notebooks.find(n => n.id === activeNotebookId)
  const isEmpty = folderTree.length === 0 && rootNotes.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* 笔记库选择器 */}
      <div className="p-2">
        <DropdownMenu open={notebookMenuOpen} onOpenChange={setNotebookMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-start gap-2 h-8">
              <Library className="size-3.5 shrink-0" />
              <span className="flex-1 truncate text-left">{activeNb?.name || '选择笔记库'}</span>
              <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[240px]">
            {notebooks.map((nb) => (
              <DropdownMenuItem key={nb.id}
                className={cn('flex items-center gap-2', nb.id === activeNotebookId && 'bg-accent')}
                onClick={() => handleSwitchNotebook(nb.id)}
              >
                <Library className="size-3.5" />
                <span className="flex-1 truncate">{nb.name}</span>
                <span className="text-[10px] text-muted-foreground">{nb.note_count}</span>
              </DropdownMenuItem>
            ))}
            <div className="border-t mt-1 pt-1 px-2">
              <div className="flex items-center gap-1">
                <Input value={newNotebookName} onChange={(e) => setNewNotebookName(e.target.value)}
                  placeholder="新笔记库名称" className="h-7 text-xs"
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateNotebook()} />
                <Button size="icon" className="size-7 shrink-0" onClick={handleCreateNotebook}>
                  <Plus className="size-3" />
                </Button>
              </div>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 搜索 + 新建 */}
      <div className="flex items-center gap-1 px-2 pb-1">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" />
          <Input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索笔记..." className="pl-7 h-7 text-xs" />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="size-7 shrink-0">
              <Plus className="size-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuItem className="text-xs gap-2" onClick={() => handleNewNote()}>
              <FileText className="size-3.5" />新建笔记
            </DropdownMenuItem>
            <DropdownMenuItem className="text-xs gap-2" onClick={() => handleCreateFolder()}>
              <Folder className="size-3.5" />新建文件夹
            </DropdownMenuItem>
            <DropdownMenuItem className="text-xs gap-2" onClick={() => openUpload()}>
              <Upload className="size-3.5" />上传笔记
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 新建文件夹输入栏 */}
      {newFolderMode && (
        <div className="px-3 py-1 flex items-center gap-1">
          <Input autoFocus value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="文件夹名称" className="h-7 text-xs flex-1"
            onKeyDown={(e) => { if (e.key === 'Enter') confirmCreateFolder(); if (e.key === 'Escape') setNewFolderMode(false) }} />
          <Button size="sm" className="h-7 text-xs" onClick={confirmCreateFolder}>确定</Button>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setNewFolderMode(false)}>取消</Button>
        </div>
      )}

      {/* 主区域：文件夹树 + 根目录笔记 */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4].map((i) => (<Skeleton key={i} className="h-4 w-3/4" />))}
          </div>
        ) : isEmpty ? (
          <p className="p-4 text-center text-xs text-muted-foreground">
            还没有笔记，点击 + 新建
          </p>
        ) : (
          <div className="py-1">
            {/* 文件夹树（含笔记） */}
            {folderTree.map((folder) => renderFolder(folder))}

            {/* 根目录笔记（无文件夹的笔记） */}
            {rootNotes.map((note) => (
              <NoteRow key={note.id} note={note} selectedId={selectedId}
                onSelect={setSelectedId} onDelete={handleDeleteNote} />
            ))}
          </div>
        )}
      </ScrollArea>

      {/* 底部信息 */}
      {activeNb && (
        <div className="p-2 border-t text-[10px] text-muted-foreground">
          {activeNb.name} · {activeNb.note_count ?? 0} 篇笔记
        </div>
      )}

      {/* 上传笔记对话框（加号菜单 / 文件夹右键共用） */}
      <UploadNoteDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        folder={uploadFolder}
        notebookId={activeNotebookId}
      />

      {/* 删除确认弹窗 */}
      <Dialog open={deleteConfirm.open} onOpenChange={(v) => setDeleteConfirm((p) => ({ ...p, open: v }))}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="size-4 text-destructive" />
              {deleteConfirm.type === 'folder' ? '删除文件夹' : '删除笔记'}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {deleteConfirm.type === 'folder' ? (
                <>
                  确定删除文件夹
                  <strong>「{(deleteConfirm.target as FolderNode)?.name}」</strong>
                  {deleteConfirm.count > 0 && (
                    <> 及其内部 <strong className="text-destructive">{deleteConfirm.count}</strong> 篇笔记</>
                  )}
                  ？
                  <br />
                  <span className="text-muted-foreground">笔记将移入回收站，30 天后自动清理。</span>
                </>
              ) : (
                <>
                  确定删除笔记
                  <strong>「{(deleteConfirm.target as NoteListItem)?.title}」</strong>？
                  <br />
                  <span className="text-muted-foreground">将移入回收站，可随时恢复。</span>
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setDeleteConfirm((p) => ({ ...p, open: false }))}>
              取消
            </Button>
            <Button variant="destructive" size="sm"
              onClick={deleteConfirm.type === 'folder' ? confirmDeleteFolder : confirmDeleteNote}>
              <Trash2 className="size-3.5 mr-1" />
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
