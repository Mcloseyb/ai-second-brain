/**
 * SSE 流式对话客户端
 * ------------------
 * 格式: data: {"type": "token", "content": "你"}
 *       data: {"type": "done", "message_id": 42}
 *
 * 用法:
 *   for await (const event of chatStream('你好')) {
 *     if (event.type === 'token') console.log(event.content)
 *   }
 */
import { BASE_URL } from './api'
import type { SSEEvent } from '@/types'

export async function* chatStream(
  message: string,
  conversationId: number | null = null,
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })

  if (!response.ok) throw new Error(`请求失败: ${response.status}`)

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const dataStr = trimmed.slice(5).trim()
      if (!dataStr) continue
      try {
        yield JSON.parse(dataStr) as SSEEvent
      } catch {
        // 跳过无法解析的行
      }
    }
  }
}

/**
 * SSE 流式研究（深度研究页面）
 * 格式: data: {"type": "agent_status", "agent": "retriever", "status": "running", ...}
 */
export async function* researchStream(
  topic: string,
  useWebSearch = true,
  useKnowledgeBase = true,
  documentIds: number[] = [],
): AsyncGenerator<Record<string, unknown>> {
  const response = await fetch(`${BASE_URL}/api/research/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic,
      use_web_search: useWebSearch,
      use_knowledge_base: useKnowledgeBase,
      document_ids: documentIds,
    }),
  })

  if (!response.ok) throw new Error(`请求失败: ${response.status}`)

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const dataStr = trimmed.slice(5).trim()
      if (!dataStr) continue
      try {
        yield JSON.parse(dataStr)
      } catch {
        // 跳过
      }
    }
  }
}
