// ============================================================
// Shared TypeScript interfaces for AI Second Brain
// ============================================================

// ---- API response types ----

export interface Note {
  id: number
  title: string
  content?: string
  folder?: string
  notebook_id?: number | null
  format: string
  word_count: number
  source_type?: string
  source_path?: string
  content_hash?: string
  last_synced_at?: string
  tags: Tag[]
  created_at: string
  updated_at: string
}

export interface NoteListItem {
  id: number
  title: string
  folder?: string
  notebook_id?: number | null
  format: string
  word_count: number
  tags: Tag[]
  created_at: string
  updated_at: string
}

// ---- Notebook types ----

export interface Notebook {
  id: number
  name: string
  description: string
  note_count?: number
  created_at: string
  updated_at: string
}

export interface FolderNode {
  name: string
  path: string
  note_count: number
  notes: NoteListItem[]
  children: FolderNode[]
}

export interface FolderTreeResponse {
  folders: FolderNode[]
  root_notes: NoteListItem[]
  total: number
}

export interface Tag {
  id: number
  name: string
  color?: string
  note_count?: number
}

export interface Conversation {
  id: number
  title: string
  created_at: string
  updated_at: string
  message_count?: number
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface MessageRecord {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens: number
  created_at: string
}

// ---- SSE event types ----

export type SSEEvent =
  | { type: 'thinking'; content: string }
  | { type: 'token'; content: string }
  | { type: 'done'; message_id: number; tokens: number }
  | { type: 'error'; content: string }

// ---- Sync types ----

export interface SyncStatus {
  total_notes: number
  synced: number
  pending: number
  never_synced: number
}

export interface SyncResult {
  note_id: number
  title: string
  status: 'synced' | 'skipped' | 'failed'
  detail: string
}

export interface SyncReport {
  total: number
  synced: number
  skipped: number
  failed: number
  results: SyncResult[]
}

// ---- Import types ----

export interface ImportResult {
  note: Note
  synced: boolean
}

// ---- Bridge types ----

export interface QtBridge {
  selectFile(): string
  selectFolder(): string
  readFolder(path: string): string
  minimizeWindow(): void
  maximizeWindow(): void
  closeWindow(): void
  getAppVersion(): string
  getPlatform(): string
  uploadFileToBackend(path: string): string
  checkBackendHealth(): string
}

// ---- Agent progress types (深度研究页曾用；暂保留供 Agent 进度组件复用) ----

export interface AgentStep {
  agent: 'retriever' | 'analyst' | 'writer' | 'reviewer'
  status: 'pending' | 'running' | 'completed' | 'error'
  message?: string
}

// ---- Quiz types (P6 出题自测) ----

export interface QuizQuestion {
  /** 答题阶段可见的题目（不含答案） */
  id: string
  type: 'choice' | 'short'
  question: string
  /** 单选题 4 个选项；简答题为空 */
  options?: string[]
}

export interface QuizGenerateResponse {
  quiz_id: number
  notebook_id: number
  folder: string | null
  note_count: number
  questions: QuizQuestion[]
}

export interface QuizGradeResult {
  question_id: string
  correct: boolean
  user_answer: string
  answer: string
  explanation: string
  comment: string | null
  /** 简答题批改的 0-10 分；选择题无 */
  score?: number
}

export interface QuizGradeResponse {
  quiz_id: number
  notebook_id: number | null
  total: number
  correct: number
  score: number
  results: QuizGradeResult[]
  summary: string
}

export interface QuizAttempt {
  question_id: string
  answer: string
}

// ---- Dashboard types (P7 真实图谱) ----

export interface DashboardStats {
  total_notes: number
  total_tags: number
  total_links: number
  synced: number
  pending: number
}

export interface GraphNode {
  id: number
  name: string
  /** 节点分类 = 语义连通簇（"簇N"），同簇进同一朵云；无关联为 "未关联" */
  category: string
  symbolSize: number
  /** 关联次数（被多少篇笔记关联，越大越重要） */
  degree?: number
  /** KMeans 簇编号；null = 游离节点（不在任何云朵内） */
  cluster_id?: number | null
  word_count: number
  notebook_id: number | null
  folder: string
  tags: string[]
}

export interface GraphEdge {
  source: number
  target: number
  /** 语义相似度 0~1 */
  weight?: number
}

/** 云朵（KMeans 语义簇）— 供前端绘制云朵 + Agent 命名 */
export interface GraphCluster {
  cluster_id: number
  count: number
  titles: string[]
  preview?: string
}

/** 簇间相似度边（相关云朵互联） */
export interface GraphClusterEdge {
  source: number
  target: number
  /** 两簇笔记相似度均值 0~1 */
  weight?: number
}

export interface GraphData {
  nodes: GraphNode[]
  /** 语义邻居边：用于点击高亮关联笔记，不绘制 */
  edges: GraphEdge[]
  /** KMeans 语义簇（云朵） */
  clusters?: GraphCluster[]
  /** 簇间相似度边（云朵互联） */
  cluster_edges?: GraphClusterEdge[]
}

/** 云朵命名结果（Agent LLM 生成） */
export interface ClusterNamesResponse {
  names: { cluster_id: number; name: string }[]
}

export interface DashboardStatsResponse extends DashboardStats {}

export interface GraphResponse extends GraphData {}

// ---- API response wrappers ----

export interface NotesListResponse {
  notes: NoteListItem[]
  total: number
  page: number
  page_size: number
}

export interface NoteResponse {
  note: Note
}

export interface TagsListResponse {
  tags: Tag[]
}

export interface TagResponse {
  tag: Tag
}

export interface ConversationsListResponse {
  conversations: Conversation[]
  total: number
}

export interface MessagesListResponse {
  messages: MessageRecord[]
}

export interface SyncStatusResponse extends SyncStatus {}

export interface SyncNowResponse {
  report: SyncReport
}

export interface PendingSyncResponse {
  pending: Array<{
    id: number
    title: string
    folder: string
    source_type: string
    last_synced_at: string | null
  }>
}

export interface ImportResponse {
  note: Note
  synced: boolean
}

/** 文档解析结果（导入对话框预填标题 / AI 标签推荐用，不创建笔记） */
export interface DocumentParseResponse {
  title: string
  content: string
  source_type: string
  word_count: number
}

/** 内容标签推荐（导入对话框，先推荐后导入） */
export interface SuggestTagsResponse {
  mode: 'simple' | 'llm'
  suggestions: TagSuggestion[]
}

// ---- Search types (P3) ----

export interface NoteSearchResult {
  note_id: number
  title: string
  text: string
  similarity: number
  folder: string
  tags: Tag[]
  word_count: number
  updated_at: string | null
}

export interface NoteSearchResponse {
  results: NoteSearchResult[]
  query: string
}

// ---- 智能双向链接（P5） ----

export interface RelatedNote {
  note_id: number
  title: string
  text: string
  similarity: number
  folder: string
  word_count: number
  tags: Tag[]
  updated_at: string | null
}

export interface RelatedResponse {
  note_id: number
  related: RelatedNote[]
}

export interface LinkedFromItem {
  id: number
  title: string
  folder: string
  word_count: number
  tags: Tag[]
  link_type: string
  updated_at: string | null
}

export interface LinkedFromResponse {
  note_id: number
  linked_from: LinkedFromItem[]
}

export interface TitleLinkDetection {
  target_note_id: number
  title: string
  count: number
}

export interface TitleLinksResponse {
  note_id: number
  detections: TitleLinkDetection[]
}

// ---- AI 自动标签（P4） ----

export interface TagSuggestion {
  tag: string
  type: 'existing' | 'new'
  tag_id: number | null
  keyword: string
  score: number
  reason?: string
}

export interface MergeSuggestion {
  from: string
  to: string
  reason?: string
}

export interface AutoTagResponse {
  note_id: number
  mode?: 'simple' | 'llm'
  suggestions: TagSuggestion[]
  merge_suggestions?: MergeSuggestion[]
  steps?: Array<{ tool: string; observation: string | null }>
}
