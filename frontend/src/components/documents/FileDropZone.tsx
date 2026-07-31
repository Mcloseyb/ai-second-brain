/**
 * FileDropZone — 文件拖拽上传组件
 * --------------------------------
 * 支持拖拽 + 点击选择文件，校验 PDF/MD/DOCX/TXT 格式。
 */
import { useState, useCallback, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Upload, FileText, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

const ACCEPTED_TYPES = [
  'application/pdf',
  'text/markdown',
  'text/plain',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]
const ACCEPTED_EXTENSIONS = '.md,.txt,.docx,.pdf'

interface FileDropZoneProps {
  onFile: (file: File) => Promise<void>
  disabled?: boolean
}

export default function FileDropZone({ onFile, disabled }: FileDropZoneProps) {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = useCallback((file: File): boolean => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.split(',').includes(ext)) {
      toast.error(`不支持的格式 "${ext}"，支持: ${ACCEPTED_EXTENSIONS}`)
      return false
    }
    if (file.size === 0) {
      toast.error('文件内容为空')
      return false
    }
    if (file.size > 50 * 1024 * 1024) {
      toast.error('文件超过 50MB 限制')
      return false
    }
    return true
  }, [])

  const handleFile = useCallback(
    async (file: File) => {
      if (!validateFile(file) || disabled) return
      setUploading(true)
      try {
        await onFile(file)
        toast.success(`"${file.name}" 导入成功`)
      } catch (e) {
        toast.error(`导入失败: ${(e as Error).message}`)
      } finally {
        setUploading(false)
      }
    },
    [onFile, validateFile, disabled],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const files = Array.from(e.dataTransfer.files)
      if (files.length > 0) handleFile(files[0])
    },
    [handleFile],
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }, [])

  const handleClick = () => {
    if (!disabled) fileInputRef.current?.click()
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    // Reset input so same file can be selected again
    e.target.value = ''
  }

  return (
    <div
      className={cn(
        'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer',
        dragOver && 'border-primary bg-primary/5',
        !dragOver && 'border-muted-foreground/25 hover:border-muted-foreground/50',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS}
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
      {uploading ? (
        <>
          <Loader2 className="size-8 text-primary animate-spin mb-2" />
          <p className="text-sm text-muted-foreground">正在导入...</p>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2 mb-2">
            <Upload className="size-5 text-muted-foreground" />
            <FileText className="size-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">拖拽文件到此处或点击选择</p>
          <p className="text-xs text-muted-foreground mt-1">
            支持 Markdown、PDF、Word、TXT（最大 50MB）
          </p>
        </>
      )}
    </div>
  )
}
