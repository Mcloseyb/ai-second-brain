/**
 * ChatBubble — 聊天气泡组件
 * -------------------------
 * 用户消息（右对齐，蓝色）+ AI 消息（左对齐，灰色）+ Markdown 渲染。
 */
import { cn } from '@/lib/utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { User, Bot, Loader2 } from 'lucide-react'
import type { ChatMessage } from '@/types'

interface ChatBubbleProps {
  message: ChatMessage
  isGenerating?: boolean
}

export default function ChatBubble({ message, isGenerating }: ChatBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      {/* 头像 */}
      <Avatar className="size-8 shrink-0">
        <AvatarFallback className={isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'}>
          {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
        </AvatarFallback>
      </Avatar>

      {/* 气泡 */}
      <div
        className={cn(
          'rounded-lg px-3 py-2 max-w-[75%] min-w-0',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted',
        )}
      >
        <div className="text-sm whitespace-pre-wrap break-words">
          {message.content || (isGenerating ? '' : ' ')}
          {isGenerating && !message.content && (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              思考中...
            </span>
          )}
          {isGenerating && message.content && (
            <span className="inline-block w-1.5 h-4 bg-current ml-0.5 animate-pulse align-middle" />
          )}
        </div>
      </div>
    </div>
  )
}
