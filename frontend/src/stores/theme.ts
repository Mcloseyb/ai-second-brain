/**
 * 主题状态管理 (Zustand)
 * ---------------------
 * 浅色/深色一键切换，用 <html class="dark"> 驱动 Tailwind dark 模式。
 * 选择持久化到 localStorage，下次启动自动恢复。
 */
import { create } from 'zustand'

const STORAGE_KEY = 'asb-theme'

interface ThemeState {
  isDark: boolean
  toggle: () => void
  setTheme: (mode: 'light' | 'dark') => void
}

function getInitialDark(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === 'dark'
}

function applyTheme(isDark: boolean) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', isDark)
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  isDark: getInitialDark(),

  toggle: () => {
    const next = !get().isDark
    localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light')
    set({ isDark: next })
    applyTheme(next)
  },

  setTheme: (mode) => {
    const next = mode === 'dark'
    localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light')
    set({ isDark: next })
    applyTheme(next)
  },
}))

// 启动时应用一次
if (typeof window !== 'undefined') {
  applyTheme(getInitialDark())
}
