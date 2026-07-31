/**
 * 对话状态管理 (Zustand)
 * ---------------------
 * 消息列表、对话 ID、生成状态、历史对话、知识库搜索。
 */
import { create } from 'zustand'
import { chatStream } from '@/lib/sse'
import { chatApi, notesApi } from '@/lib/api'
import type { ChatMessage, Conversation, NoteSearchResult } from '@/types'

interface ChatState {
  messages: ChatMessage[]
  conversationId: number | null
  generating: boolean
  conversations: Conversation[]

  // 知识库搜索结果
  searchResults: NoteSearchResult[]
  searchQuery: string

  // Actions
  sendMessage: (text: string, searchKB?: boolean) => Promise<void>
  newChat: () => void
  switchConversation: (id: number) => Promise<void>
  fetchConversations: () => Promise<void>
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  conversationId: null,
  generating: false,
  conversations: [],
  searchResults: [],
  searchQuery: '',

  sendMessage: async (text, searchKB = false) => {
    if (!text.trim() || get().generating) return

    // ---- 知识库搜索 ----
    let contextText = text
    let results: NoteSearchResult[] = []

    if (searchKB) {
      set({ searchResults: [], searchQuery: text })
      try {
        const res = await notesApi.search({ query: text, top_k: 5 })
        results = res.results || []
        set({ searchResults: results, searchQuery: text })

        // 将搜索结果作为上下文注入消息
        if (results.length > 0) {
          const snippets = results
            .map((r, i) => `[笔记${i + 1}] 《${r.title}》\n${r.text}`)
            .join('\n\n')
          contextText = `以下是从用户知识库中检索到的相关笔记，请基于这些内容回答问题。如果笔记内容不足以回答，可以结合你的知识补充。\n\n${snippets}\n\n---\n用户问题：${text}`
        }
      } catch (e) {
        console.error('知识库搜索失败:', (e as Error).message)
        // 搜索失败不阻止对话，降级为普通对话
      }
    } else {
      set({ searchResults: [], searchQuery: '' })
    }

    // ---- 发送消息 ----
    set((s) => ({
      messages: [
        ...s.messages,
        { role: 'user', content: text },
        { role: 'assistant', content: '' },
      ],
      generating: true,
    }))

    try {
      for await (const event of chatStream(contextText, get().conversationId)) {
        set((s) => {
          const msgs = [...s.messages]
          const lastIdx = msgs.length - 1
          const last = msgs[lastIdx]
          if (!last) return s

          if (event.type === 'token') {
            msgs[lastIdx] = { ...last, content: last.content + event.content }
          } else if (event.type === 'error') {
            msgs[lastIdx] = { ...last, content: last.content + `\n\n[错误] ${event.content}` }
          }
          return { messages: msgs }
        })
      }
    } catch (e) {
      const errMsg = (e as Error).message || '连接失败'
      set((s) => {
        const msgs = [...s.messages]
        const lastIdx = msgs.length - 1
        const last = msgs[lastIdx]
        if (last) {
          msgs[lastIdx] = { ...last, content: last.content + `\n\n[连接失败] ${errMsg}` }
        }
        return { messages: msgs }
      })
    } finally {
      set({ generating: false })
    }
  },

  newChat: () => set({ messages: [], conversationId: null, searchResults: [], searchQuery: '' }),

  switchConversation: async (id) => {
    set({ conversationId: id, messages: [], searchResults: [], searchQuery: '' })
    try {
      const res = await chatApi.messages(id, { limit: 100 })
      const messages = (res.messages || []).map((m) => ({
        role: m.role as ChatMessage['role'],
        content: m.content,
      }))
      set({ messages })
    } catch (e) {
      console.error('加载对话历史失败:', (e as Error).message)
    }
  },

  fetchConversations: async () => {
    try {
      const res = await chatApi.conversations({ limit: 50 })
      set({ conversations: res.conversations || [] })
    } catch (e) {
      console.error('加载对话列表失败:', (e as Error).message)
    }
  },
}))
