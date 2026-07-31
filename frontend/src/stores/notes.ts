/**
 * 笔记状态管理 (Zustand)
 * ---------------------
 * 笔记列表、当前编辑、搜索、导入、同步、笔记本管理。
 */
import { create } from 'zustand'
import { notesApi, documentsApi, syncApi, notebooksApi } from '@/lib/api'
import type { Note, NoteListItem, SyncReport, Notebook, FolderNode } from '@/types'

interface NotesState {
  notes: NoteListItem[]
  loading: boolean
  searchQuery: string
  selectedId: number | null

  // 笔记库
  notebooks: Notebook[]
  activeNotebookId: number | null
  folderTree: FolderNode[]
  rootNotes: NoteListItem[]

  // Actions — 笔记
  setSearchQuery: (q: string) => void
  setSelectedId: (id: number | null) => void
  fetchNotes: (notebookId?: number, folder?: string) => Promise<void>
  fetchNote: (id: number) => Promise<Note | null>
  createNote: (notebookId: number, folder?: string, title?: string, content?: string) => Promise<Note>
  updateNote: (id: number, data: Partial<{ title: string; content: string; tags: string[] }>) => Promise<Note>
  deleteNote: (id: number) => Promise<void>
  moveNote: (noteId: number, folder: string) => Promise<void>
  importFile: (file: File) => Promise<unknown>
  /** 导入到指定笔记库/文件夹（导入后刷新文件夹树并选中新笔记） */
  importNoteToFolder: (
    file: File,
    notebookId: number,
    folder: string,
    tags: string,
    title: string,
  ) => Promise<{ noteId: number | null }>
  syncNow: () => Promise<SyncReport>

  // Actions — 笔记库
  fetchNotebooks: () => Promise<void>
  createNotebook: (name: string) => Promise<Notebook>
  deleteNotebook: (id: number) => Promise<void>
  renameNotebook: (id: number, name: string) => Promise<Notebook>
  setActiveNotebook: (id: number) => Promise<void>
  fetchFolderTree: () => Promise<void>
}

export const useNotesStore = create<NotesState>((set, get) => ({
  notes: [],
  loading: false,
  searchQuery: '',
  selectedId: null,
  notebooks: [],
  activeNotebookId: null,
  folderTree: [],
  rootNotes: [],

  setSearchQuery: (q) => set({ searchQuery: q }),
  setSelectedId: (id) => set({ selectedId: id }),

  // ---- 笔记 CRUD ----

  fetchNotes: async (notebookId?: number, folder?: string) => {
    const nbId = notebookId ?? get().activeNotebookId
    if (!nbId) return
    set({ loading: true })
    try {
      const res = await notebooksApi.notes(nbId, folder ?? '')
      set({ notes: res.notes || [] })
    } catch (e) {
      console.error('加载笔记失败:', (e as Error).message)
    } finally {
      set({ loading: false })
    }
  },

  fetchNote: async (id) => {
    const res = await notesApi.get(id)
    return res.note || null
  },

  createNote: async (notebookId, folder = '', title = '新笔记', content = '') => {
    const res = await notesApi.create({ title, content, tags: [], notebook_id: notebookId, folder })
    const note = res.note
    const activeId = get().activeNotebookId
    // 只在当前活跃笔记库中才加入列表（防止显示到其他库）
    if (notebookId === activeId) {
      set((s) => ({
        notes: [{
          id: note.id, title: note.title, folder: note.folder,
          notebook_id: note.notebook_id, format: note.format,
          word_count: note.word_count, tags: note.tags,
          created_at: note.created_at, updated_at: note.updated_at,
        }, ...s.notes],
        selectedId: note.id,
      }))
    }
    return note
  },

  updateNote: async (id, data) => {
    const res = await notesApi.update(id, data)
    const note = res.note
    set((s) => ({
      notes: s.notes.map((n) =>
        n.id === id
          ? { ...n, title: note.title, tags: note.tags, updated_at: note.updated_at }
          : n,
      ),
    }))
    return note
  },

  deleteNote: async (id) => {
    await notesApi.remove(id)
    set((s) => ({
      notes: s.notes.filter((n) => n.id !== id),
      selectedId: s.selectedId === id ? null : s.selectedId,
    }))
  },

  moveNote: async (noteId, folder) => {
    await notesApi.move(noteId, folder)
    // 从当前列表移除
    set((s) => ({
      notes: s.notes.filter((n) => n.id !== noteId),
      selectedId: s.selectedId === noteId ? null : s.selectedId,
    }))
  },

  importFile: async (file) => {
    const res = await documentsApi.import(file)
    await get().fetchNotes()
    return res
  },

  importNoteToFolder: async (file, notebookId, folder, tags, title) => {
    const res = await documentsApi.import(file, folder, tags, notebookId, title)
    // 刷新文件夹树，让新笔记出现在目标文件夹
    await get().fetchFolderTree()
    const noteId = res.note?.id ?? null
    if (noteId != null) set({ selectedId: noteId })
    return { noteId }
  },

  syncNow: async () => {
    const res = await syncApi.now()
    return res.report || { total: 0, synced: 0, skipped: 0, failed: 0, results: [] }
  },

  // ---- 笔记库 ----

  fetchNotebooks: async () => {
    try {
      const res = await notebooksApi.list()
      const notebooks = res.notebooks || []
      set({ notebooks })
      // 若未选中，自动选中第一个
      if (!get().activeNotebookId && notebooks.length > 0) {
        await get().setActiveNotebook(notebooks[0].id)
      }
    } catch (e) {
      console.error('加载笔记库失败:', (e as Error).message)
    }
  },

  createNotebook: async (name) => {
    const res = await notebooksApi.create(name)
    const nb = res.notebook
    set((s) => ({ notebooks: [...s.notebooks, nb] }))
    return nb
  },

  deleteNotebook: async (id) => {
    await notebooksApi.remove(id)
    set((s) => ({ notebooks: s.notebooks.filter((nb) => nb.id !== id) }))
    if (get().activeNotebookId === id) {
      const remaining = get().notebooks
      if (remaining.length > 0) {
        await get().setActiveNotebook(remaining[0].id)
      } else {
        set({ activeNotebookId: null, notes: [], folderTree: [], rootNotes: [] })
      }
    }
  },

  renameNotebook: async (id, name) => {
    const res = await notebooksApi.rename(id, name)
    set((s) => ({
      notebooks: s.notebooks.map((nb) => nb.id === id ? { ...nb, name } : nb),
    }))
    return res.notebook
  },

  setActiveNotebook: async (id) => {
    set({ activeNotebookId: id, selectedId: null, notes: [], searchQuery: '' })
    try {
      const res = await notebooksApi.folderTree(id)
      set({
        folderTree: res.folders || [],
        rootNotes: res.root_notes || [],
        notes: [],  // 笔记现在在 folderTree 和 rootNotes 中，不需要单独列表
      })
    } catch (e) {
      console.error('加载文件夹树失败:', (e as Error).message)
    }
  },

  fetchFolderTree: async () => {
    const nbId = get().activeNotebookId
    if (!nbId) return
    try {
      const res = await notebooksApi.folderTree(nbId)
      set({ folderTree: res.folders || [], rootNotes: res.root_notes || [] })
    } catch (e) {
      console.error('刷新文件夹树失败:', (e as Error).message)
    }
  },
}))

/** 按标题搜索过滤的选择器 */
export function useFilteredNotes() {
  return useNotesStore((s) => {
    const q = s.searchQuery.trim().toLowerCase()
    if (!q) return s.notes
    return s.notes.filter((n) => (n.title || '').toLowerCase().includes(q))
  })
}
