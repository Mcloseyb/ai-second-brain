/**
 * ContextMenu — 右键菜单组件
 * --------------------------
 * 基于 @radix-ui/react-context-menu，shadcn 风格。
 */
import * as React from 'react'
import * as ContextMenuPrimitive from '@radix-ui/react-context-menu'
import { cn } from '@/lib/utils'

export interface ContextMenuItemDef {
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
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
            'z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md',
            'animate-in fade-in-0 zoom-in-95',
          )}
        >
          {items.map((item) => (
            <ContextMenuPrimitive.Item
              key={item.label}
              className={cn(
                'relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none',
                'focus:bg-accent focus:text-accent-foreground',
                item.danger && 'text-destructive focus:bg-destructive/10',
                item.disabled && 'pointer-events-none opacity-50',
              )}
              onClick={item.onClick}
              disabled={item.disabled}
            >
              {item.label}
            </ContextMenuPrimitive.Item>
          ))}
        </ContextMenuPrimitive.Content>
      </ContextMenuPrimitive.Portal>
    </ContextMenuPrimitive.Root>
  )
}
