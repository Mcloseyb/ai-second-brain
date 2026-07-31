/**
 * EditorContextMenu — Markdown 编辑器右键格式菜单
 * ----------------------------------------------
 * 选中文字后右键 → 一级/二级标题 / 代码块 / 加粗 / 斜体
 * 通过 DOM 操作 Vditor 编辑区的内容。
 */
import { useState, useCallback, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Heading1, Heading2, Code, Bold, Italic, Strikethrough, Quote, List } from 'lucide-react'

interface MenuItem {
  label: string
  icon: ReactNode
  shortcut?: string
  action: (selected: string) => { before: string; after: string }
}

const FORMAT_ITEMS: MenuItem[] = [
  { label: '一级标题', icon: <Heading1 className="size-3.5" />, shortcut: 'Ctrl+1',
    action: () => ({ before: '# ', after: '' }) },
  { label: '二级标题', icon: <Heading2 className="size-3.5" />, shortcut: 'Ctrl+2',
    action: () => ({ before: '## ', after: '' }) },
  { label: '三级标题', icon: <Heading2 className="size-3.5" />,
    action: () => ({ before: '### ', after: '' }) },
  { label: '代码块', icon: <Code className="size-3.5" />, shortcut: 'Ctrl+`',
    action: (s) => ({ before: '```\n', after: s ? `\n\`\`\`` : '```' }) },
  { label: '加粗', icon: <Bold className="size-3.5" />, shortcut: 'Ctrl+B',
    action: (s) => ({ before: '**', after: '**' }) },
  { label: '斜体', icon: <Italic className="size-3.5" />, shortcut: 'Ctrl+I',
    action: (s) => ({ before: '*', after: '*' }) },
  { label: '删除线', icon: <Strikethrough className="size-3.5" />,
    action: (s) => ({ before: '~~', after: '~~' }) },
]

interface EditorContextMenuProps {
  children: ReactNode
  className?: string
}

export default function EditorContextMenu({ children, className }: EditorContextMenuProps) {
  const [menu, setMenu] = useState<{ x: number; y: number; selected: string } | null>(null)

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    const sel = window.getSelection()
    const selectedText = sel?.toString().trim() || ''

    if (selectedText.length > 0) {
      e.preventDefault()
      setMenu({ x: e.clientX, y: e.clientY, selected: selectedText })
    }
  }, [])

  const handleAction = useCallback((item: MenuItem) => {
    if (!menu) return
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) { setMenu(null); return }

    const range = sel.getRangeAt(0)
    const { before, after } = item.action(menu.selected)
    const formatted = `${before}${menu.selected}${after}`

    // Replace the selected text with formatted version
    range.deleteContents()
    const textNode = document.createTextNode(formatted)
    range.insertNode(textNode)

    // Trigger Vditor's input handler by dispatching an input event
    const container = document.querySelector('.vditor') || document.querySelector('.vditor-ir')
    if (container) {
      container.dispatchEvent(new Event('input', { bubbles: true }))
      // Also trigger Vditor's internal change detection if possible
      const vditorEl = container.querySelector('[contenteditable="true"]')
      if (vditorEl) {
        vditorEl.dispatchEvent(new Event('input', { bubbles: true }))
      }
    }

    setMenu(null)
  }, [menu])

  return (
    <div className={cn('relative', className)} onContextMenu={handleContextMenu}>
      {children}

      {/* 浮动右键菜单 */}
      {menu && (
        <>
          {/* 点击其他地方关闭 */}
          <div className="fixed inset-0 z-40" onClick={() => setMenu(null)} />

          {/* 菜单 */}
          <div
            className="fixed z-50 w-44 rounded-md border bg-popover shadow-md py-1 animate-in fade-in-0 zoom-in-95"
            style={{ left: menu.x, top: menu.y }}
          >
            <div className="px-2 py-1 text-[10px] text-muted-foreground border-b">
              已选中 {menu.selected.length > 20 ? menu.selected.slice(0, 20) + '...' : menu.selected}
            </div>
            {FORMAT_ITEMS.map((item) => (
              <button
                key={item.label}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-sm hover:bg-accent transition-colors"
                onClick={() => handleAction(item)}
              >
                {item.icon}
                <span className="flex-1 text-left">{item.label}</span>
                {item.shortcut && (
                  <span className="text-[10px] text-muted-foreground">{item.shortcut}</span>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
