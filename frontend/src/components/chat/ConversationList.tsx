/**
 * ConversationList — 对话历史列表
 * --------------------------------
 * 显示所有对话，支持点击切换、新建对话。
 */
import { useEffect } from 'react'
import { useChatStore } from '@/stores/chat'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Plus, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function ConversationList() {
  const { conversations, conversationId, fetchConversations, newChat, switchConversation } =
    useChatStore()

  useEffect(() => {
    fetchConversations()
  }, [])

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-2">
        <Button size="sm" variant="outline" className="w-full gap-1" onClick={newChat}>
          <Plus className="size-3.5" />
          新对话
        </Button>
      </div>
      <ScrollArea className="flex-1">
        {conversations.length === 0 ? (
          <div className="p-4 text-center text-xs text-muted-foreground">
            暂无对话记录
          </div>
        ) : (
          <div className="p-1">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                className={cn(
                  'flex w-full items-start gap-2 rounded-md px-2 py-2 text-left transition-colors hover:bg-accent',
                  conversationId === conv.id && 'bg-accent',
                )}
                onClick={() => switchConversation(conv.id)}
              >
                <MessageSquare className="size-4 mt-0.5 shrink-0 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{conv.title}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {formatDate(conv.updated_at)}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
