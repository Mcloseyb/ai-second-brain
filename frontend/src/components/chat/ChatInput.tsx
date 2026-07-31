/**
 * ChatInput — 对话输入框组件
 * --------------------------
 * Textarea + 发送按钮，支持 Enter 发送、Shift+Enter 换行。
 */
import { useState, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Send, Loader2 } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  generating?: boolean
}

export default function ChatInput({ onSend, disabled, generating }: ChatInputProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || disabled || generating) return
    onSend(text)
    setInput('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, disabled, generating, onSend])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 200) + 'px'
    }
  }, [])

  return (
    <div className="flex items-end gap-2">
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => {
          setInput(e.target.value)
          adjustHeight()
        }}
        onKeyDown={handleKeyDown}
        placeholder="输入你的问题...（Enter 发送，Shift+Enter 换行）"
        disabled={disabled || generating}
        rows={1}
        className="min-h-[40px] max-h-[200px] resize-none flex-1"
      />
      <Button
        size="icon"
        onClick={handleSend}
        disabled={disabled || !input.trim() || generating}
        className="shrink-0"
      >
        {generating ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Send className="size-4" />
        )}
      </Button>
    </div>
  )
}
