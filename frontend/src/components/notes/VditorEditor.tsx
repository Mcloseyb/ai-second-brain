/**
 * VditorEditor — Vditor Markdown 编辑器的 React 封装
 * -------------------------------------------------
 * 使用 useEffect + useRef 管理 Vditor 生命周期。
 * 支持受控模式（value/onChange）。
 */
import { useEffect, useRef, useCallback } from 'react'
import Vditor from 'vditor'
import 'vditor/dist/index.css'
import { cn } from '@/lib/utils'

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

  // Keep the latest onChange callback in ref
  onChangeRef.current = onChange

  const initVditor = useCallback(() => {
    if (!containerRef.current || vditorRef.current) return

    const vditor = new Vditor(containerRef.current, {
      height: '100%',
      mode: 'ir',
      placeholder,
      value,
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
        // Disable toolbar buttons in readonly mode
        if (readonly) {
          vditor.disabled()
        }
      },
    })
  }, [placeholder, readonly])

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
