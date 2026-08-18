import { useState, useEffect, useRef, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  [key: string]: unknown
}

interface UseWebSocketOptions {
  onMessage?: (data: WebSocketMessage) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  autoConnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttempts = useRef(0)
  const intentionalClose = useRef(false)

  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    autoConnect = true,
    reconnectInterval = 5000,  // 5 seconds between reconnect attempts
    maxReconnectAttempts = 10, // Stop after 10 failed attempts
  } = options

  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN || 
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    // Don't reconnect if max attempts reached
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      console.warn(`WebSocket: Max reconnect attempts (${maxReconnectAttempts}) reached for ${url}`)
      return
    }

    try {
      console.log(`WebSocket: Connecting to ${url} (attempt ${reconnectAttempts.current + 1})`)
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log(`WebSocket: Connected to ${url}`)
        setIsConnected(true)
        reconnectAttempts.current = 0 // Reset on successful connection
        intentionalClose.current = false
        onOpen?.()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)
          onMessage?.(data)
        } catch {
          console.error('WebSocket: Failed to parse message')
        }
      }

      ws.onclose = (event) => {
        console.log(`WebSocket: Closed (code: ${event.code}, reason: ${event.reason})`)
        setIsConnected(false)
        wsRef.current = null
        onClose?.()

        // Only reconnect if not intentionally closed
        if (!intentionalClose.current && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1
          const delay = reconnectInterval * Math.min(reconnectAttempts.current, 5) // Exponential backoff (max 25s)
          console.log(`WebSocket: Reconnecting in ${delay}ms...`)
          reconnectTimer.current = setTimeout(() => {
            connect()
          }, delay)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket: Error', error)
        onError?.(error)
      }

      wsRef.current = ws
    } catch (error) {
      console.error('WebSocket: Connection error:', error)
      reconnectAttempts.current += 1
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnectInterval, maxReconnectAttempts])

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect')
      wsRef.current = null
    }
    setIsConnected(false)
    reconnectAttempts.current = 0
  }, [])

  const sendMessage = useCallback((data: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    console.warn('WebSocket: Cannot send - not connected')
    return false
  }, [])

  useEffect(() => {
    if (autoConnect) {
      connect()
    }
    return () => {
      disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount/unmount

  return { isConnected, lastMessage, sendMessage, connect, disconnect }
}
