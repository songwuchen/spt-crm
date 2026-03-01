import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/stores/useAuthStore'

type MessageHandler = (data: Record<string, unknown>) => void

/**
 * WebSocket hook for real-time notifications.
 * Auto-connects when token is available, auto-reconnects on disconnect.
 */
export function useWebSocket(onMessage: MessageHandler) {
  const token = useAuthStore((s) => s.token)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/notifications?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      // Heartbeat every 25s
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 25000)
    }

    ws.onmessage = (e) => {
      if (e.data === 'pong') return
      try {
        const data = JSON.parse(e.data)
        onMessageRef.current(data)
      } catch {
        // ignore non-JSON
      }
    }

    ws.onclose = () => {
      cleanup()
      // Reconnect after 3s
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [token])

  const cleanup = useCallback(() => {
    if (pingTimer.current) {
      clearInterval(pingTimer.current)
      pingTimer.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      cleanup()
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent reconnect on intentional close
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, cleanup])
}
