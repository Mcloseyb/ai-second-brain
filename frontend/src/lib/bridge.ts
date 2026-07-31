/**
 * Qt ↔ React 双向通信桥 (QWebChannel)
 * ------------------------------------
 * 通过 QWebChannel 调用 Qt 端能力（desktop/bridge.py 暴露的方法）。
 * 纯浏览器调试时自动降级为 mock 模式。
 *
 * React 调用 Qt:
 *   const filePath = await callBridge('selectFile')
 *   await callBridge('minimizeWindow')
 *
 * Qt 推送 React（window.dispatchEvent('qt:xxx')）:
 *   const cleanup = onQtEvent('agent_progress', (data) => {...})
 */
import type { QtBridge } from '@/types'

declare global {
  interface Window {
    bridge?: QtBridge
  }
}

/** 获取 Qt 注入的 bridge 对象 */
function getBridge(): QtBridge | null {
  return window.bridge || null
}

/** 等待 Qt Bridge 就绪（QWebChannel 初始化是异步的） */
export function waitForBridge(timeout = 5000): Promise<boolean> {
  return new Promise((resolve) => {
    if (getBridge()) return resolve(true)
    const start = Date.now()
    const timer = setInterval(() => {
      if (getBridge()) {
        clearInterval(timer)
        resolve(true)
      } else if (Date.now() - start > timeout) {
        clearInterval(timer)
        resolve(false) // 非 Qt 环境
      }
    }, 100)
  })
}

/** 调用 Qt Bridge 方法 */
export async function callBridge<T = unknown>(
  method: keyof QtBridge,
  ...args: unknown[]
): Promise<T | null> {
  const bridge = getBridge()
  if (bridge && typeof bridge[method] === 'function') {
    try {
      const fn = bridge[method] as (...a: unknown[]) => T
      return fn(...args)
    } catch (err) {
      console.error(`[Bridge] 调用 ${method} 失败:`, err)
      return null
    }
  }
  console.log(`[Bridge Mock] ${method}(${args.join(', ')})`)
  return null
}

/** 监听 Qt 端推送的事件，返回清理函数 */
export function onQtEvent<T = unknown>(
  eventName: string,
  callback: (data: T) => void,
): () => void {
  const handler = (e: Event) => callback((e as CustomEvent<T>).detail)
  window.addEventListener(`qt:${eventName}`, handler)
  return () => window.removeEventListener(`qt:${eventName}`, handler)
}
