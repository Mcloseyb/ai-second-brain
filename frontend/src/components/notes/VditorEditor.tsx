/**
 * VditorEditor — Vditor Markdown 编辑器的 React 封装
 * -------------------------------------------------
 * 使用 useEffect + useRef 管理 Vditor 生命周期。
 * 支持受控模式（value/onChange）+ 深色主题跟随（useThemeStore）。
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
}

export default function VditorEditor({
  value,
  onChange,
  className,
  placeholder = '开始写作...',
  readonly = false,
}: VditorEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const vditorRef = useRef<Vditor | null>(null)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const isDark = useThemeStore((s) => s.isDark)

  // Keep the latest onChange callback in ref
  onChangeRef.current = onChange

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
      },
      after() {
        vditorRef.current = vditor
        // 初始化后按当前主题强制刷新（v3 需 setTheme 才生效完整）
        vditor.setTheme(isDark ? 'dark' : 'classic')
        // Disable toolbar buttons in readonly mode
        if (readonly) {
          vditor.disabled()
        }
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
    }
  }, [value])

  return (
    <div
      ref={containerRef}
      className={cn('vditor-container h-full min-h-[300px]', className)}
    />
  )
}
