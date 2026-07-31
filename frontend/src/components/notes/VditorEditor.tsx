/**
 * VditorEditor — Vditor Markdown 编辑器的 React 封装
 * -------------------------------------------------
 * 使用 useEffect + useRef 管理 Vditor 生命周期。
 * 支持受控模式（value/onChange）+ 深色主题跟随（useThemeStore）
 * + 正文标题高亮（highlightTitles，P5.2.3）。
 */
import { useEffect, useRef, useCallback } from 'react'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { cn } from '@/lib/utils'
import { useThemeStore } from '@/stores/theme'

interface VditorEditorProps {
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
  readonly?: boolean
  /** 需要高亮的其他笔记标题（P5.2.3 正文标题高亮） */
  highlightTitles?: string[]
}

export default function VditorEditor({
  value,
  onChange,
  className,
  placeholder = '开始写作...',
  readonly = false,
  highlightTitles = [],
}: VditorEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const vditorRef = useRef<Vditor | null>(null)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const isDark = useThemeStore((s) => s.isDark)

  // 高亮标题保持最新（供稳定回调引用）
  const highlightTitlesRef = useRef<string[]>(highlightTitles)
  highlightTitlesRef.current = highlightTitles

  // Keep the latest onChange callback in ref
  onChangeRef.current = onChange

  // ============================================================
  // 正文标题高亮（P5.2.3）— 在 .vditor-ir 内容区包裹命中标题
  // ============================================================
  const applyHighlights = useCallback(() => {
    const container = containerRef.current
    const titles = highlightTitlesRef.current
    if (!container || titles.length === 0) return

    const ir = container.querySelector('.vditor-ir') as HTMLElement | null
    if (!ir) return

    // 1. 清理旧高亮（还原为纯文本，避免重复包裹）
    ir.querySelectorAll('.vditor-link-hl').forEach((el) => {
      const parent = el.parentNode
      if (parent) {
        parent.replaceChild(document.createTextNode(el.textContent || ''), el)
        parent.normalize()
      }
    })

    // 2. 长标题优先（避免短标题抢占长标题的子串）
    const sorted = [...titles].sort((a, b) => b.length - a.length)

    // 3. 遍历文本节点，收集命中区间
    const walker = document.createTreeWalker(ir, NodeFilter.SHOW_TEXT)
    const nodes: Text[] = []
    while (walker.nextNode()) nodes.push(walker.currentNode as Text)

    for (const node of nodes) {
      const text = node.textContent || ''
      if (!text.trim()) continue

      const matches: Array<{ start: number; end: number }> = []
      for (const title of sorted) {
        if (title.length < 2) continue
        let idx = text.indexOf(title)
        while (idx !== -1) {
          matches.push({ start: idx, end: idx + title.length })
          idx = text.indexOf(title, idx + 1)
        }
      }
      if (matches.length === 0) continue

      // 4. 合并重叠区间
      matches.sort((a, b) => a.start - b.start)
      const merged: Array<{ start: number; end: number }> = []
      for (const m of matches) {
        const last = merged[merged.length - 1]
        if (last && m.start < last.end) {
          last.end = Math.max(last.end, m.end)
        } else {
          merged.push({ ...m })
        }
      }

      // 5. 重建节点：普通文本 + <span class="vditor-link-hl">
      const frag = document.createDocumentFragment()
      let cursor = 0
      for (const m of merged) {
        if (m.start > cursor) {
          frag.appendChild(document.createTextNode(text.slice(cursor, m.start)))
        }
        const mark = document.createElement('span')
        mark.className = 'vditor-link-hl'
        mark.textContent = text.slice(m.start, m.end)
        frag.appendChild(mark)
        cursor = m.end
      }
      if (cursor < text.length) {
        frag.appendChild(document.createTextNode(text.slice(cursor)))
      }
      node.parentNode?.replaceChild(frag, node)
    }
  }, [])

  const applyHighlightsRef = useRef(applyHighlights)
  applyHighlightsRef.current = applyHighlights

  const initVditor = useCallback(() => {
    if (!containerRef.current || vditorRef.current) return

    const vditor = new Vditor(containerRef.current, {
      height: '100%',
      mode: 'ir',
      placeholder,
      value,
      theme: isDark ? 'dark' : 'classic',  // 跟随应用主题
      toolbar: [
        'headings',
        'bold',
        'italic',
        'strike',
        '|',
        'line',
        'quote',
        'list',
        'ordered-list',
        'check',
        'code',
        'inline-code',
        '|',
        'upload',
        'table',
        '|',
        'undo',
        'redo',
        '|',
        'fullscreen',
        'outline',
      ],
      cache: {
        enable: false,
      },
      input(value) {
        valueRef.current = value
        onChangeRef.current(value)
        // 延迟重新高亮（等 Vditor 重渲染完成）
        setTimeout(() => applyHighlightsRef.current(), 0)
      },
      after() {
        vditorRef.current = vditor
        // 初始化后按当前主题强制刷新（v3 需 setTheme 才生效完整）
        vditor.setTheme(isDark ? 'dark' : 'classic')
        // Disable toolbar buttons in readonly mode
        if (readonly) {
          vditor.disabled()
        }
        // 首次渲染后应用标题高亮
        applyHighlightsRef.current()
      },
    })
  }, [placeholder, readonly, isDark])

  // Initialize on mount
  useEffect(() => {
    initVditor()
    return () => {
      if (vditorRef.current) {
        vditorRef.current.destroy()
        vditorRef.current = null
      }
    }
  }, [])

  // 主题切换时动态跟随（避免 md 编辑区与全局深色模式脱节）
  useEffect(() => {
    if (vditorRef.current) {
      vditorRef.current.setTheme(isDark ? 'dark' : 'classic')
    }
  }, [isDark])

  // Sync external value changes
  useEffect(() => {
    if (vditorRef.current && value !== valueRef.current) {
      vditorRef.current.setValue(value)
      valueRef.current = value
      setTimeout(() => applyHighlightsRef.current(), 0)
    }
  }, [value])

  // 高亮标题变化时重新应用（切换笔记 / 检测结果更新）
  useEffect(() => {
    applyHighlightsRef.current()
  }, [highlightTitles])

  return (
    <div
      ref={containerRef}
      className={cn('vditor-container h-full min-h-[300px]', className)}
    />
  )
}
