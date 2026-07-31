/**
 * useBridge — Qt QWebChannel 桥接 React Hook
 * ------------------------------------------
 * 用法:
 *   const { ready, callBridge } = useBridge()
 *   if (ready) await callBridge('selectFile')
 */
import { useState, useEffect } from 'react'
import { waitForBridge, callBridge as bridgeCall, onQtEvent } from '@/lib/bridge'
import type { QtBridge } from '@/types'

export function useBridge() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    waitForBridge().then(setReady)
  }, [])

  return {
    ready,
    callBridge: <T = unknown>(method: keyof QtBridge, ...args: unknown[]) =>
      bridgeCall<T>(method, ...args),
    onQtEvent,
  }
}
