/**
 * TrashPage — 回收站页面
 * ----------------------
 * 显示已删除的笔记，支持恢复和永久删除。
 */
import { useEffect, useState } from 'react'
import { notesApi } from '@/lib/api'
import { useNotesStore } from '@/stores/notes'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Trash2, RotateCcw, AlertTriangle, FileText,
} from 'lucide-react'
import { toast } from 'sonner'

interface TrashNote {
  id: number
  title: string
  folder: string
  word_count: number
  deleted_at: string | null
  updated_at: string
}

export default function TrashPage() {
  const { activeNotebookId } = useNotesStore()
  const [notes, setNotes] = useState<TrashNote[]>([])
  const [loading, setLoading] = useState(false)

  const fetchTrash = async () => {
    setLoading(true)
    try {
      const res: any = await notesApi.trashList(activeNotebookId ?? undefined)
      setNotes(res.notes || [])
    } catch {
      setNotes([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchTrash() }, [activeNotebookId])

  const handleRestore = async (id: number) => {
    try {
      await notesApi.restore(id)
      toast.success('笔记已恢复')
      fetchTrash()
    } catch (e) {
      toast.error('恢复失败: ' + (e as Error).message)
    }
  }

  const handlePermanentDelete = async (id: number) => {
    if (!confirm('确定永久删除？此操作不可撤销。')) return
    try {
      await notesApi.permanentDelete(id)
      toast.success('已永久删除')
      fetchTrash()
    } catch (e) {
      toast.error('删除失败: ' + (e as Error).message)
    }
  }

  const handleEmpty = async () => {
    if (!confirm('确定清空回收站？所有笔记将被永久删除且无法恢复。')) return
    try {
      const res: any = await notesApi.emptyTrash(activeNotebookId ?? undefined)
      toast.success(`已清空 ${res.data?.deleted || res.deleted || 0} 篇笔记`)
      fetchTrash()
    } catch (e) {
      toast.error('清空失败: ' + (e as Error).message)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* 顶部操作栏 */}
      <div className="flex items-center gap-2 shrink-0 px-4 py-2 border-b">
        <Trash2 className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold flex-1">回收站</h2>
        {notes.length > 0 && (
          <Button variant="outline" size="sm" className="text-xs h-7 text-destructive hover:text-destructive" onClick={handleEmpty}>
            清空回收站
          </Button>
        )}
      </div>

      {/* 内容 */}
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
            加载中…
          </div>
        ) : notes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
            <Trash2 className="size-10 mb-3 opacity-30" />
            <p className="text-sm">回收站为空</p>
            <p className="text-xs mt-1">删除的笔记会出现在这里，30 天后自动清理</p>
          </div>
        ) : (
          <div className="py-1">
            {notes.map((note) => (
              <div key={note.id} className="flex items-center gap-3 px-4 py-2 hover:bg-accent transition-colors group">
                <FileText className="size-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{note.title || '无标题'}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {note.folder ? `${note.folder} · ` : ''}
                    {note.word_count || 0} 字 · 删除于 {note.deleted_at ? new Date(note.deleted_at).toLocaleDateString('zh-CN') : ''}
                  </p>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Button variant="ghost" size="icon" className="size-7" onClick={() => handleRestore(note.id)} title="恢复">
                    <RotateCcw className="size-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="size-7 text-destructive hover:text-destructive" onClick={() => handlePermanentDelete(note.id)} title="永久删除">
                    <AlertTriangle className="size-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
