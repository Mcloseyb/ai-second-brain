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

// ---- Research agent types ----

export interface AgentStep {
  agent: 'retriever' | 'analyst' | 'writer' | 'reviewer'
  status: 'pending' | 'running' | 'completed' | 'error'
  message?: string
}

// ---- Dashboard types ----

export interface DashboardStats {
  total_notes: number
  total_documents: number
  total_conversations: number
  total_tags: number
}

export interface GraphNode {
  id: string
  name: string
  category: string
  symbolSize: number
}

export interface GraphEdge {
  source: string
  target: string
  weight?: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

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
