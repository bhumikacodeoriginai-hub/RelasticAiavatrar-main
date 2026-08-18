import { useState, useEffect } from 'react'

interface AvatarProps {
  isSpeaking: boolean
  isListening: boolean
  state: 'idle' | 'greeting' | 'speaking' | 'listening' | 'thinking'
  name?: string
}

function Avatar({ isSpeaking, isListening, state }: AvatarProps) {
  const [mouthOpen, setMouthOpen] = useState(false)

  // Animate mouth when speaking
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null

    if (isSpeaking) {
      interval = setInterval(() => {
        setMouthOpen(prev => !prev)
      }, 150)
    } else {
      setMouthOpen(false)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isSpeaking])

  return (
    <div className="avatar-container relative">
      {/* Background glow effect */}
      <div
        className={`absolute inset-0 rounded-full transition-all duration-1000 ${
          isSpeaking
            ? 'bg-gradient-to-r from-primary-500/30 to-accent-500/30 animate-glow'
            : isListening
            ? 'bg-gradient-to-r from-green-500/20 to-primary-500/20'
            : 'bg-gradient-to-r from-gray-800 to-gray-900'
        }`}
      />

      {/* Avatar SVG */}
      <div className="absolute inset-0 flex items-center justify-center">
        <svg
          viewBox="0 0 200 200"
          className="w-4/5 h-4/5"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Face shape */}
          <ellipse
            cx="100"
            cy="100"
            rx="70"
            ry="80"
            fill="#f5deb3"
            stroke="#d4a574"
            strokeWidth="1"
          />

          {/* Hair */}
          <path
            d="M30 90 C30 40 70 15 100 15 C130 15 170 40 170 90 C170 70 150 35 100 35 C50 35 30 70 30 90"
            fill="#2d1810"
          />

          {/* Eyes */}
          <g>
            {/* Left eye */}
            <ellipse cx="75" cy="95" rx="10" ry="7" fill="white" />
            <ellipse cx="75" cy="95" rx="5" ry="5" fill="#4a3728" />
            <circle cx="73" cy="93" r="2" fill="white" opacity="0.7" />

            {/* Right eye */}
            <ellipse cx="125" cy="95" rx="10" ry="7" fill="white" />
            <ellipse cx="125" cy="95" rx="5" ry="5" fill="#4a3728" />
            <circle cx="123" cy="93" r="2" fill="white" opacity="0.7" />

            {/* Eyelids animation when speaking */}
            {state === 'thinking' && (
              <>
                <ellipse cx="75" cy="95" rx="10" ry="3" fill="#f5deb3" />
                <ellipse cx="125" cy="95" rx="10" ry="3" fill="#f5deb3" />
              </>
            )}
          </g>

          {/* Eyebrows */}
          <path d="M60 78 Q75 72 90 78" fill="none" stroke="#2d1810" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M110 78 Q125 72 140 78" fill="none" stroke="#2d1810" strokeWidth="2.5" strokeLinecap="round" />

          {/* Nose */}
          <path d="M100 100 L95 115 Q100 118 105 115 Z" fill="#e8c9a0" stroke="#d4a574" strokeWidth="0.5" />

          {/* Mouth */}
          <g className={isSpeaking ? 'avatar-mouth' : ''}>
            {mouthOpen ? (
              /* Open mouth (speaking) */
              <ellipse cx="100" cy="138" rx="14" ry="8" fill="#c94040" stroke="#a03030" strokeWidth="0.5" />
            ) : isListening ? (
              /* Slight smile (listening) */
              <path d="M85 135 Q100 145 115 135" fill="none" stroke="#c94040" strokeWidth="2" strokeLinecap="round" />
            ) : (
              /* Closed smile (idle) */
              <path d="M88 135 Q100 142 112 135" fill="none" stroke="#c94040" strokeWidth="2" strokeLinecap="round" />
            )}
          </g>

          {/* Blush */}
          <circle cx="65" cy="120" r="8" fill="#ffb6c1" opacity="0.3" />
          <circle cx="135" cy="120" r="8" fill="#ffb6c1" opacity="0.3" />
        </svg>
      </div>

      {/* State indicator */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
        {isSpeaking && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-primary-600/80 rounded-full">
            <div className="audio-wave text-white">
              <div className="audio-wave-bar" />
              <div className="audio-wave-bar" />
              <div className="audio-wave-bar" />
              <div className="audio-wave-bar" />
              <div className="audio-wave-bar" />
            </div>
            <span className="text-xs text-white font-medium ml-1">Speaking</span>
          </div>
        )}
        {isListening && !isSpeaking && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-green-600/80 rounded-full">
            <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse" />
            <span className="text-xs text-white font-medium">Listening</span>
          </div>
        )}
        {state === 'thinking' && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-yellow-600/80 rounded-full">
            <div className="w-2 h-2 bg-yellow-300 rounded-full animate-pulse" />
            <span className="text-xs text-white font-medium">Thinking...</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default Avatar
