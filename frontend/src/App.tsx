/**
 * App.tsx — 应用根组件
 * --------------------
 * 全局布局: 左侧固定侧边栏 + 右侧内容区。
 * 侧边栏: Logo + 4 个导航项 + 底部主题开关/后端状态。
 *
 * 端口现有 App.vue 的 shadcn Sidebar 布局到自定义实现。
 */
import { useEffect, useState, Suspense } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useThemeStore } from '@/stores/theme'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Brain,
  NotebookPen,
  MessageSquare,
  GraduationCap,
  LayoutDashboard,
  Trash2,
  Sun,
  Moon,
  Wifi,
  WifiOff,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ---- 导航菜单定义 ----
const navItems = [
  { icon: NotebookPen, title: '智能笔记', path: '/notes' },
  { icon: MessageSquare, title: '知识问答', path: '/chat' },
  { icon: GraduationCap, title: '出题自测', path: '/quiz' },
  { icon: Brain, title: '知识进阶', path: '/mastery' },
  { icon: LayoutDashboard, title: '数据看板', path: '/dashboard' },
]

export default function App() {
  const { isDark, toggle } = useThemeStore()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [backendOnline, setBackendOnline] = useState(false)

  // ---- 后端健康检查 ----
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch('http://127.0.0.1:8000/health')
        setBackendOnline(r.ok)
      } catch {
        setBackendOnline(false)
      }
    }
    check()
    const timer = setInterval(check, 15000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* ============================================================
          左侧侧边栏
          ============================================================ */}
      <aside
        className={cn(
          'flex flex-col border-r bg-card transition-all duration-300',
          collapsed ? 'w-[68px]' : 'w-[240px]',
        )}
      >
        {/* Logo 区域 */}
        <div className="flex h-14 items-center gap-3 px-3">
          <div className="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Brain className="size-4" />
          </div>
          {!collapsed && (
            <div className="flex flex-col gap-0.5 leading-none min-w-0">
              <span className="font-semibold text-sm truncate">AI Second Brain</span>
              <span className="text-[10px] text-muted-foreground">个人知识库</span>
            </div>
          )}
        </div>

        <Separator />

        {/* 导航菜单 */}
        <ScrollArea className="flex-1 py-2">
          <nav className="flex flex-col gap-1 px-2">
            {navItems.map((item) => {
              const isActive = pathname === item.path ||
                (item.path !== '/notes' && pathname.startsWith(item.path))
              return (
                <Button
                  key={item.path}
                  variant={isActive ? 'secondary' : 'ghost'}
                  size={collapsed ? 'icon' : 'default'}
                  className={cn(
                    'justify-start gap-3 h-10',
                    collapsed ? 'w-10 mx-auto' : 'w-full',
                    isActive && 'font-medium',
                  )}
                  onClick={() => navigate(item.path)}
                  title={collapsed ? item.title : undefined}
                >
                  <item.icon className="size-4 shrink-0" />
                  {!collapsed && <span className="truncate">{item.title}</span>}
                </Button>
              )
            })}
          </nav>
        </ScrollArea>

        <Separator />

        {/* 回收站（左下角，深色/浅色模式上方） */}
        <div className="px-3 pt-2">
          <Button
            variant={pathname === '/trash' ? 'secondary' : 'ghost'}
            size={collapsed ? 'icon' : 'default'}
            className={cn(
              'justify-start gap-3 h-10',
              collapsed ? 'w-10 mx-auto' : 'w-full',
              pathname === '/trash' && 'font-medium',
            )}
            onClick={() => navigate('/trash')}
            title={collapsed ? '回收站' : undefined}
          >
            <Trash2 className="size-4 shrink-0" />
            {!collapsed && <span className="truncate">回收站</span>}
          </Button>
        </div>

        {/* 底部控制区 */}
        <div className="p-3 flex flex-col gap-2">
          {!collapsed ? (
            /* ---- 展开态：折叠按钮 + 主题切换 同行 ---- */
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0"
                onClick={() => setCollapsed(!collapsed)}
                title="折叠侧边栏"
              >
                <PanelLeftClose className="size-4" />
              </Button>
              <div className="flex-1" />
              <div className="flex items-center gap-1.5">
                {isDark ? <Sun className="size-4 shrink-0" /> : <Moon className="size-4 shrink-0" />}
                <Switch checked={isDark} onCheckedChange={toggle} />
              </div>
            </div>
          ) : (
            /* ---- 折叠态：和原来一样，垂直布局 ---- */
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 self-end"
                onClick={() => setCollapsed(!collapsed)}
                title="展开侧边栏"
              >
                <PanelLeft className="size-4" />
              </Button>
              <div className="flex justify-center">
                {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </div>
              <div className="flex justify-center">
                <Switch checked={isDark} onCheckedChange={toggle} />
              </div>
            </>
          )}

          {/* 后端状态 */}
          <div className={cn('flex items-center', collapsed ? 'justify-center' : 'gap-2 px-1')}>
            {backendOnline ? (
              <Wifi className="size-3 text-green-500 shrink-0" />
            ) : (
              <WifiOff className="size-3 text-destructive shrink-0" />
            )}
            {!collapsed && (
              <span className="text-xs text-muted-foreground">
                {backendOnline ? '后端在线' : '后端离线'}
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* ============================================================
          右侧: 顶栏 + 页面内容
          ============================================================ */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* 页面内容区 */}
        <main className="flex-1 overflow-hidden p-4">
          <Suspense fallback={
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="inline-block size-6 border-2 border-primary border-t-transparent rounded-full animate-spin mb-2" />
                <p className="text-sm text-muted-foreground">加载中...</p>
              </div>
            </div>
          }>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
