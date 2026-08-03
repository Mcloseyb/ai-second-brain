/**
 * ContextMenu — 右键菜单组件
 * --------------------------
 * 基于 @radix-ui/react-context-menu，shadcn 风格。
 * 支持：普通项、分隔线、危险项、禁用项、图标、快捷键。
 */
import * as React from 'react'
import * as ContextMenuPrimitive from '@radix-ui/react-context-menu'
import { cn } from '@/lib/utils'

export interface ContextMenuItemDef {
  label: string
  onClick?: () => void
  danger?: boolean
  disabled?: boolean
  icon?: React.ReactNode
  shortcut?: string
  /** 'separator' 类型渲染为分隔线 */
  type?: 'item' | 'separator'
}

interface ContextMenuProps {
  items: ContextMenuItemDef[]
  children: React.ReactNode
}

export default function ContextMenu({ items, children }: ContextMenuProps) {
  if (items.length === 0) return <>{children}</>

  return (
    <ContextMenuPrimitive.Root>
      <ContextMenuPrimitive.Trigger asChild>
        {children}
      </ContextMenuPrimitive.Trigger>
      <ContextMenuPrimitive.Portal>
        <ContextMenuPrimitive.Content
          className={cn(
            'z-50 min-w-[10rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md',
            'animate-in fade-in-0 zoom-in-95',
          )}
        >
          {items.map((item, i) => {
            if (item.type === 'separator') {
              return (
                <ContextMenuPrimitive.Separator
                  key={`sep-${i}`}
                  className="-mx-1 my-1 h-px bg-muted"
                />
              )
            }
            return (
              <ContextMenuPrimitive.Item
                key={item.label}
                className={cn(
                  'relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-xs outline-none',
                  'focus:bg-accent focus:text-accent-foreground',
                  item.danger && 'text-destructive focus:bg-destructive/10',
                  item.disabled && 'pointer-events-none opacity-50',
                )}
                onClick={item.onClick}
                disabled={item.disabled}
              >
                {item.icon && (
                  <span className="size-3.5 shrink-0 text-muted-foreground">{item.icon}</span>
                )}
                <span className="flex-1">{item.label}</span>
                {item.shortcut && (
                  <span className="ml-4 text-[10px] text-muted-foreground tracking-widest">
                    {item.shortcut}
                  </span>
                )}
              </ContextMenuPrimitive.Item>
            )
          })}
        </ContextMenuPrimitive.Content>
      </ContextMenuPrimitive.Portal>
    </ContextMenuPrimitive.Root>
  )
}
