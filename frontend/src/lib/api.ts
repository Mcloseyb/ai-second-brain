/**
 * 后端 API 封装 (Axios)
 * ----------------------
 * 统一管理所有 HTTP 请求，成功时直接返回后端 JSON data。
 *
 * 用法:
 *   import { notesApi, chatStream } from '@/lib/api'
 *   const data = await notesApi.list({ page_size: 50 })
 *   for await (const evt of chatStream('你好')) { ... }
 */
import axios from 'axios'
import type {
  NotesListResponse,
  NoteResponse,
  NoteSearchResponse,
  AutoTagResponse,
  RelatedResponse,
  LinkedFromResponse,
  TitleLinksResponse,
  TagsListResponse,
  TagResponse,
  Conversation,
  ConversationsListResponse,
  MessagesListResponse,
  SyncStatusResponse,
  SyncNowResponse,
  PendingSyncResponse,
  ImportResponse,
  Notebook,
  FolderTreeResponse,
} from '@/types'

// 后端固定地址
export const BASE_URL = 'http://127.0.0.1:8000'

// 全局唯一 Axios 实例
const client = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
})

// 响应拦截: 成功解出 data；失败提取后端 detail 错误信息
client.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    console.error('[API]', msg)
    return Promise.reject(new Error(msg))
  },
)

// ============================================================
// 笔记 CRUD
// ============================================================
export const notesApi = {
  /** 列表: {search?, tag?, page?, page_size?} */
  list: (params: Record<string, unknown> = {}) =>
    client.get('/api/notes', { params }) as Promise<NotesListResponse>,

  /** 详情（含正文） */
  get: (id: number) =>
    client.get(`/api/notes/${id}`) as Promise<NoteResponse>,

  /** 新建: {title, content, tags[], notebook_id?, folder?} */
  create: (data: { title: string; content: string; tags: string[]; notebook_id?: number; folder?: string }) =>
    client.post('/api/notes', data) as Promise<NoteResponse>,

  /** 更新: {title?, content?, tags?} */
  update: (id: number, data: Partial<{ title: string; content: string; tags: string[] }>) =>
    client.put(`/api/notes/${id}`, data) as Promise<NoteResponse>,

  /** 删除 */
  remove: (id: number) =>
    client.delete(`/api/notes/${id}`) as Promise<{ ok: boolean }>,

  /** 语义搜索: {query, top_k?, threshold?, hybrid?} */
  search: (data: { query: string; top_k?: number; threshold?: number; hybrid?: boolean }) =>
    client.post('/api/notes/search', data) as Promise<NoteSearchResponse>,

  /** 移动笔记到文件夹: {folder} */
  move: (noteId: number, folder: string) =>
    client.put(`/api/notebooks/notes/${noteId}/move`, null, { params: { folder } }) as Promise<{ note: NoteResponse['note'] }>,

  /** AI 自动标签推荐（P4）: mode=simple 简易版(零token) / mode=llm 完整版(Function Calling) */
  autoTag: (noteId: number, mode: 'simple' | 'llm' = 'simple') =>
    client.post(`/api/notes/${noteId}/auto-tag`, null, { params: { mode } }) as Promise<AutoTagResponse>,

  /** 语义相关笔记（P5 双向链接） */
  related: (noteId: number, topK = 5) =>
    client.get(`/api/notes/${noteId}/related`, { params: { top_k: topK } }) as Promise<RelatedResponse>,

  /** 反向链接 — 引用此笔记的笔记 */
  linkedFrom: (noteId: number) =>
    client.get(`/api/notes/${noteId}/linked-from`) as Promise<LinkedFromResponse>,

  /** 标题检测 — 正文包含其他笔记标题 */
  titleLinks: (noteId: number) =>
    client.get(`/api/notes/${noteId}/title-links`) as Promise<TitleLinksResponse>,

  /** 确认记录链接（标题检测/手动） */
  createLinks: (noteId: number, targetIds: number[], linkType: 'title' | 'manual' = 'title') =>
    client.post(`/api/notes/${noteId}/links`, { target_ids: targetIds, link_type: linkType }) as Promise<{ recorded: number; skipped: number }>,
}

// ============================================================
// 笔记库
// ============================================================
export const notebooksApi = {
  /** 列表 */
  list: () => client.get('/api/notebooks') as Promise<{ notebooks: Notebook[] }>,

  /** 创建: {name} */
  create: (name: string) =>
    client.post('/api/notebooks', { name }) as Promise<{ notebook: Notebook }>,

  /** 删除 */
  remove: (id: number) =>
    client.delete(`/api/notebooks/${id}`) as Promise<{ ok: boolean }>,

  /** 重命名 */
  rename: (id: number, name: string) =>
    client.put(`/api/notebooks/${id}`, { name }) as Promise<{ notebook: Notebook }>,

  /** 文件夹树 + 根目录笔记 */
  folderTree: (notebookId: number) =>
    client.get(`/api/notebooks/${notebookId}/folders`) as Promise<FolderTreeResponse>,

  /** 按文件夹获取笔记 */
  notes: (notebookId: number, folder?: string) =>
    client.get(`/api/notebooks/${notebookId}/notes`, { params: { folder } }) as Promise<NotesListResponse>,
}

// ============================================================
// 标签
// ============================================================
export const tagsApi = {
  list: () => client.get('/api/tags') as Promise<TagsListResponse>,

  create: (name: string, color = '#6B9FFF') =>
    client.post('/api/tags', { name, color }) as Promise<TagResponse>,

  remove: (id: number) =>
    client.delete(`/api/tags/${id}`) as Promise<{ ok: boolean }>,

  /** 合并标签（from → to）: from 的笔记转移到 to */
  merge: (fromName: string, toName: string) =>
    client.post('/api/tags/merge', { from_name: fromName, to_name: toName }) as Promise<{ ok: boolean; merged: number; from: string; to: string }>,
}

// ============================================================
// 对话（历史走 HTTP，流式走 SSE）
// ============================================================
export const chatApi = {
  conversations: (params: Record<string, unknown> = {}) =>
    client.get('/api/conversations', { params }) as Promise<ConversationsListResponse>,

  createConversation: (title = '新对话') =>
    client.post('/api/conversations', { title }) as Promise<Conversation>,

  messages: (conversationId: number, params: Record<string, unknown> = {}) =>
    client.get(`/api/conversations/${conversationId}/messages`, { params }) as Promise<MessagesListResponse>,
}

// ============================================================
// 文档导入（multipart 上传，含拖拽）
// ============================================================
export const documentsApi = {
  /**
   * 上传文件导入为笔记
   * @param file 文件对象
   * @param folder 目标文件夹
   * @param tags 逗号分隔标签
   */
  import: (file: File, folder = '', tags = '') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('folder', folder)
    formData.append('tags', tags)
    // 不手动设置 Content-Type，浏览器自动加 multipart boundary
    return client.post('/api/documents/import', formData, { timeout: 120000 }) as Promise<ImportResponse>
  },

  /** 从本地路径导入 */
  importFromPath: (filePath: string, folder = '', tags: string[] = []) =>
    client.post('/api/documents/import-from-path', { file_path: filePath, folder, tags }) as Promise<ImportResponse>,
}

// ============================================================
// 同步（笔记 → 向量库）
// ============================================================
export const syncApi = {
  /** 手动全量同步 */
  now: () => client.post('/api/sync/now') as Promise<SyncNowResponse>,

  /** 同步状态: {total_notes, synced, pending, never_synced} */
  status: () => client.get('/api/sync/status') as Promise<SyncStatusResponse>,

  /** 待同步列表 */
  pending: () => client.get('/api/sync/pending') as Promise<PendingSyncResponse>,

  /** 同步单篇笔记 */
  syncNote: (noteId: number) =>
    client.post(`/api/sync/notes/${noteId}`) as Promise<{ result: { note_id: number; title: string; status: string; detail: string } }>,

  /** 开关自动同步 */
  toggleAuto: (enabled: boolean, intervalMinutes = 30) =>
    client.post('/api/sync/auto/toggle', { enabled, interval_minutes: intervalMinutes }) as Promise<{ auto_sync_enabled: boolean; interval_minutes: number }>,

  /** 查询自动同步状态 */
  autoStatus: () => client.get('/api/sync/auto/status') as Promise<{ auto_sync_enabled: boolean; interval_minutes: number; last_sync_at: string | null }>,
}
