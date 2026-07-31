/**
 * ChatPage — 知识问答页面
 * -----------------------
 * 对话列表 + 聊天消息区 + 输入框。
 * 支持 SSE 流式对话、知识库搜索、文档上传。
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useChatStore } from '@/stores/chat'
import { useNotesStore } from '@/stores/notes'
import ConversationList from '@/components/chat/ConversationList'
import ChatBubble from '@/components/chat/ChatBubble'
import ChatInput from '@/components/chat/ChatInput'
import SearchResults from '@/components/chat/SearchResults'
import FileDropZone from '@/components/documents/FileDropZone'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { MessageSquare, Search } from 'lucide-react'

export default function ChatPage() {
  const { messages, generating, sendMessage, newChat, searchResults, searchQuery } = useChatStore()
  const { importFile, setSelectedId } = useNotesStore()
  const navigate = useNavigate()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [showImport, setShowImport] = useState(false)
  const [searchEnabled, setSearchEnabled] = useState(true)

  // ---- 自动滚动到底部 ----
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current
      el.scrollTop = el.scrollHeight
    }
  }, [messages, searchResults])

  // ---- 文件导入 ----
  const handleFileImport = async (file: File) => {
    await importFile(file)
    setShowImport(false)
  }

  // ---- 发送消息（带搜索） ----
  const handleSend = useCallback(
    (text: string) => {
      sendMessage(text, searchEnabled)
    },
    [sendMessage, searchEnabled],
  )

  // ---- 点击搜索结果 → 跳转笔记页 ----
  const handleSelectNote = useCallback(
    (noteId: number) => {
      setSelectedId(noteId)
      navigate('/notes')
    },
    [setSelectedId, navigate],
  )

  // ---- 是否正在搜索 ----
  const isSearching = searchEnabled && generating && searchResults.length === 0

  return (
    <div className="flex h-full gap-4">
      {/* ======== 左侧：对话列表 ======== */}
      <div className="w-[240px] shrink-0 h-full border rounded-lg bg-card overflow-hidden flex flex-col">
        <ConversationList />
      </div>

      {/* ======== 右侧：聊天区域 ======== */}
      <div className="flex-1 min-w-0 h-full flex flex-col gap-3">
        {/* 文档导入区域（可折叠） */}
        {showImport && (
          <FileDropZone onFile={handleFileImport} disabled={false} />
        )}

        {/* 知识库搜索结果 */}
        {(searchResults.length > 0 || isSearching) && (
          <SearchResults
            results={searchResults}
            loading={isSearching}
            query={searchQuery}
            onSelect={handleSelectNote}
          />
        )}

        {/* 消息列表 */}
        <div className="flex-1 min-h-0">
          <ScrollArea className="h-full" ref={scrollRef}>
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full py-20">
                <div className="text-center">
                  <MessageSquare className="size-12 mx-auto text-muted-foreground mb-3" />
                  <p className="text-muted-foreground text-sm">
                    基于你的知识库进行智能问答
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    开启「搜索知识库」后，AI 会先检索你的笔记再回答
                  </p>
                  <button
                    className="text-xs text-primary mt-3 hover:underline"
                    onClick={() => setShowImport(!showImport)}
                  >
                    {showImport ? '收起' : '上传文档'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4 p-4 pb-2">
                {messages.map((msg, idx) => (
                  <ChatBubble
                    key={idx}
                    message={msg}
                    isGenerating={generating && idx === messages.length - 1}
                  />
                ))}
                {generating && (
                  <div className="text-center text-xs text-muted-foreground py-2">
                    AI 正在生成回复...
                  </div>
                )}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* 输入框 + 搜索开关 */}
        <div className="shrink-0 px-1 pb-1 space-y-2">
          {/* 搜索知识库开关 */}
          <div className="flex items-center gap-2 px-1">
            <Switch
              id="search-kb"
              checked={searchEnabled}
              onCheckedChange={setSearchEnabled}
              disabled={generating}
              className="scale-75"
            />
            <Label
              htmlFor="search-kb"
              className="text-xs text-muted-foreground cursor-pointer flex items-center gap-1"
            >
              <Search className="size-3" />
              搜索知识库
            </Label>
          </div>

          <ChatInput
            onSend={handleSend}
            disabled={false}
            generating={generating}
          />
        </div>
      </div>
    </div>
  )
}
