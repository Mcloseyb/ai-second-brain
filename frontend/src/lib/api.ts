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
  DocumentParseResponse,
  SuggestTagsResponse,
  Notebook,
  FolderTreeResponse,
  QuizGenerateResponse,
  QuizGradeResponse,
  QuizAttempt,
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

  // ---- 回收站 ----
  trashList: (notebookId?: number, page = 1, pageSize = 50) =>
    client.get('/api/notes/trash', { params: { notebook_id: notebookId, page, page_size: pageSize } }),
  restore: (noteId: number) =>
    client.post(`/api/notes/${noteId}/restore`),
  permanentDelete: (noteId: number) =>
    client.delete(`/api/notes/${noteId}/permanent`),
  emptyTrash: (notebookId?: number) =>
    client.post('/api/notes/trash/empty', null, { params: { notebook_id: notebookId } }),
  deleteFolder: (notebookId: number, folder: string) =>
    client.post('/api/notes/folder-delete', { notebook_id: notebookId, folder }),
  folderNoteCount: (notebookId: number, folder: string) =>
    client.get('/api/notes/folder-count', { params: { notebook_id: notebookId, folder } }),
  /** AI 自动标签推荐（P4）: mode=simple 简易版(零token) / mode=llm 完整版(Function Calling) */
  autoTag: (noteId: number, mode: 'simple' | 'llm' = 'simple') =>
    client.post(`/api/notes/${noteId}/auto-tag`, null, { params: { mode } }) as Promise<AutoTagResponse>,

  /** 内容标签推荐（导入对话框用，无需先创建笔记） */
  suggestTags: (data: { title: string; content: string }) =>
    client.post('/api/notes/suggest-tags', data) as Promise<SuggestTagsResponse>,

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
// 出题自测（P6）
// ============================================================
export const quizApi = {
  /** 生成题目 — folder 为 null/空 = 整个知识库；否则该文件夹(含子文件夹)全部笔记 */
  generate: (notebookId: number, folder: string | null = null, count = 7) =>
    client.post('/api/quiz/generate', { notebook_id: notebookId, folder, count }) as Promise<QuizGenerateResponse>,

  /** 批改答案 */
  grade: (quizId: number, answers: QuizAttempt[]) =>
    client.post('/api/quiz/grade', { quiz_id: quizId, answers }) as Promise<QuizGradeResponse>,
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
   * @param notebookId 目标笔记库 ID（必须，否则笔记不在文件夹树中显示）
   * @param title 标题覆盖（留空则从文件自动解析）
   */
  import: (file: File, folder = '', tags = '', notebookId?: number | null, title = '') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('folder', folder)
    formData.append('tags', tags)
    if (notebookId != null) formData.append('notebook_id', String(notebookId))
    if (title) formData.append('title', title)
    // 不手动设置 Content-Type，浏览器自动加 multipart boundary
    return client.post('/api/documents/import', formData, { timeout: 120000 }) as Promise<ImportResponse>
  },

  /** 解析文件返回标题/内容（不创建笔记，供导入对话框预填标题 + AI 标签推荐） */
  parse: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post('/api/documents/parse', formData, { timeout: 60000 }) as Promise<DocumentParseResponse>
  },

  /** 从本地路径导入 */
  importFromPath: (filePath: string, folder = '', tags: string[] = [], notebookId?: number | null, title = '') =>
    client.post('/api/documents/import-from-path', { file_path: filePath, folder, tags, notebook_id: notebookId, title }) as Promise<ImportResponse>,
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

// ============================================================
// 温故知新 — 聚类 / 复习 / 出题 / 打卡 / 日历
// ============================================================
export const reviewApi = {
  /** 簇列表（含掌握度统计） */
  clusters: (notebookId: number) =>
    client.get('/api/review/clusters', { params: { notebook_id: notebookId } }) as Promise<{ clusters: import('@/types').ClusterInfo[] }>,

  /** 簇详情（含 SM-2 状态 + 掌握度） */
  clusterDetail: (clusterId: number) =>
    client.get(`/api/review/clusters/${clusterId}`) as Promise<import('@/types').ClusterDetail>,

  /** 全量重聚类 */
  recluster: (notebookId: number) =>
    client.post(`/api/review/clusters/recluster?notebook_id=${notebookId}`) as Promise<any>,

  /** 今日到期 */
  due: (notebookId: number) =>
    client.get('/api/review/due', { params: { notebook_id: notebookId } }) as Promise<import('@/types').DueReviewsResponse>,

  /** 生成复习测验 — scope: due|all|errors|new */
  generate: (clusterId: number, scope: string = 'due', count: number = 10) =>
    client.post('/api/review/generate', { cluster_id: clusterId, scope, count }) as Promise<import('@/types').ReviewGenerateResponse>,

  /** 批改复习测验 — 可选 ratings */
  grade: (quizId: number, answers: import('@/types').QuizAttempt[], ratings?: Array<{ note_id: number; rating: string }>) =>
    client.post('/api/review/grade', { quiz_id: quizId, answers, ratings }) as Promise<import('@/types').ReviewGradeResponse>,

  /** 打卡状态 */
  streak: (notebookId: number) =>
    client.get('/api/review/streak', { params: { notebook_id: notebookId } }) as Promise<import('@/types').StreakInfo>,

  /** 复习日历（月） */
  calendar: (notebookId: number, year: number, month: number) =>
    client.get('/api/review/calendar', { params: { notebook_id: notebookId, year, month } }) as Promise<{ days: Array<{ date: string; count: number; score_avg: number }>; total_reviews: number; total_questions: number }>,

  /** 日历某天详情 */
  calendarDay: (notebookId: number, date: string) =>
    client.get('/api/review/calendar/day', { params: { notebook_id: notebookId, date } }) as Promise<import('@/types').CalendarDayDetail>,

  /** 自由出题 */
  freeGenerate: (notebookId: number, clusterId: number | null, count: number) =>
    client.post('/api/review/free-generate', { notebook_id: notebookId, cluster_id: clusterId, count }) as Promise<import('@/types').ReviewGenerateResponse>,

  /** 自由出题批改 */
  freeGrade: (quizId: number, answers: import('@/types').QuizAttempt[]) =>
    client.post('/api/review/free-grade', { quiz_id: quizId, answers }) as Promise<import('@/types').ReviewGradeResponse>,
}
