import { useRef, useEffect } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

interface ConversationPanelProps {
  messages: Message[]
  isListening: boolean
  interimTranscript: string
  visitorName: string | null
  sessionState: string
}

function ConversationPanel({
  messages,
  isListening,
  interimTranscript,
  visitorName,
  sessionState,
}: ConversationPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, interimTranscript])

  const getStateLabel = (state: string) => {
    switch (state) {
      case 'greeting_new': return 'Welcoming new visitor'
      case 'greeting_returning': return 'Welcoming back'
      case 'waiting_for_name': return 'Waiting for name'
      case 'asking_consent': return 'Asking consent'
      case 'active_conversation': return 'In conversation'
      case 'farewell': return 'Saying goodbye'
      case 'ended': return 'Session ended'
      default: return 'Idle'
    }
  }

  return (
    <div className="glass-panel flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700/50 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Conversation</h3>
          {visitorName && (
            <p className="text-xs text-primary-400 mt-0.5">
              Talking with: {visitorName}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{getStateLabel(sessionState)}</span>
          <div className={`w-2 h-2 rounded-full ${
            sessionState === 'active_conversation' ? 'bg-green-500' :
            sessionState === 'idle' || sessionState === 'ended' ? 'bg-gray-500' :
            'bg-yellow-500'
          }`} />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <svg className="w-12 h-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-sm">Waiting for visitor...</p>
            <p className="text-xs mt-1">Conversation will appear here</p>
          </div>
        ) : (
          messages
            .filter(m => m.role !== 'system')
            .map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={
                  message.role === 'user'
                    ? 'conversation-bubble-user'
                    : 'conversation-bubble-ai'
                }
              >
                <p>{message.content}</p>
                <p className="text-xs opacity-50 mt-1">
                  {new Date(message.timestamp).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
            </div>
          ))
        )}

        {/* Interim transcript (what user is currently saying) */}
        {isListening && interimTranscript && (
          <div className="flex justify-end">
            <div className="conversation-bubble-user opacity-60">
              <p className="italic">{interimTranscript}...</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Status bar */}
      <div className="px-4 py-2 border-t border-gray-700/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isListening ? (
            <>
              <div className="audio-wave text-primary-400">
                <div className="audio-wave-bar" />
                <div className="audio-wave-bar" />
                <div className="audio-wave-bar" />
                <div className="audio-wave-bar" />
                <div className="audio-wave-bar" />
              </div>
              <span className="text-xs text-primary-400">Listening...</span>
            </>
          ) : (
            <span className="text-xs text-gray-500">Microphone ready</span>
          )}
        </div>
        <span className="text-xs text-gray-500">
          {messages.filter(m => m.role !== 'system').length} messages
        </span>
      </div>
    </div>
  )
}

export default ConversationPanel
