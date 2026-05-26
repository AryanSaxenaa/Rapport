import { useCallback, useEffect, useRef } from 'react'

type Handlers = {
  onTranscript: (text: string) => void
  onBrief: (data: unknown) => void
  onError: (message: string) => void
  onStatusChange: (status: 'online' | 'offline') => void
  onConnect: () => void
}

export function useSidecarSocket(handlers: Handlers) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    try {
      const ws = new WebSocket('ws://127.0.0.1:8765/ws/transcript')
      wsRef.current = ws

      ws.onopen = () => {
        handlersRef.current.onStatusChange('online')
        handlersRef.current.onConnect()
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = null
        }
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data as string) as { type: string; text?: string; data?: unknown; message?: string }
          if (payload.type === 'transcript' && payload.text) handlersRef.current.onTranscript(payload.text)
          if (payload.type === 'brief' && payload.data) handlersRef.current.onBrief(payload.data)
          if (payload.type === 'error' && payload.message) handlersRef.current.onError(payload.message)
        } catch {
          /* ignore malformed frames */
        }
      }

      ws.onerror = () => handlersRef.current.onStatusChange('offline')

      ws.onclose = () => {
        handlersRef.current.onStatusChange('offline')
        wsRef.current = null
        if (!reconnectTimer.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null
            connect()
          }, 3000)
        }
      }
    } catch {
      handlersRef.current.onStatusChange('offline')
      if (!reconnectTimer.current) {
        reconnectTimer.current = setTimeout(() => {
          reconnectTimer.current = null
          connect()
        }, 3000)
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])
}
