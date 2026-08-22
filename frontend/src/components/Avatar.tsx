import { useEffect, useRef, useState } from 'react'

interface AvatarProps {
  isSpeaking: boolean
  isListening: boolean
  state: 'idle' | 'greeting' | 'speaking' | 'listening' | 'thinking'
  name?: string
  /** Optional audio element used to drive real lip-sync from live amplitude. */
  audioRef?: React.RefObject<HTMLAudioElement>
}

/**
 * Realistic human receptionist avatar.
 *
 * Rendering is a layered, shaded SVG face (skin gradients, soft shadows,
 * detailed eyes with irises, natural brows/nose/lips).
 *
 * Lip-sync: when an `audioRef` is provided, the mouth is driven by the real
 * audio amplitude via the Web Audio API (AnalyserNode). If that is not
 * available (e.g. autoplay/analyser blocked), it falls back to a smooth
 * timed animation while `isSpeaking` is true.
 *
 * NOTE: This component is purely presentational. It only reads props and the
 * (optional) audio element — it never touches the WebSocket / AI / voice logic.
 */
function Avatar({ isSpeaking, isListening, state, audioRef }: AvatarProps) {
  // 0 = closed, 1 = fully open. Smoothed for natural motion.
  const [mouth, setMouth] = useState(0)
  // Mouth width factor for viseme variety (0.85 = "oo", 1.15 = "ee").
  const [mouthWide, setMouthWide] = useState(1)
  const [blink, setBlink] = useState(false)

  const rafRef = useRef<number | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null)
  const dataRef = useRef<Uint8Array | null>(null)
  const smoothedRef = useRef(0)

  // --- Natural blinking (always on, more often when idle/listening) ---
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 2200 + Math.random() * 3200
      timeout = setTimeout(() => {
        setBlink(true)
        setTimeout(() => setBlink(false), 120)
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timeout)
  }, [])

  // --- Real lip-sync from audio amplitude (with graceful fallback) ---
  useEffect(() => {
    const audioEl = audioRef?.current

    // Try to set up the Web Audio analyser once, lazily.
    function ensureAnalyser() {
      if (!audioEl || analyserRef.current) return
      try {
        const Ctx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext })
            .webkitAudioContext
        const ctx = new Ctx()
        const source = ctx.createMediaElementSource(audioEl)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 256
        analyser.smoothingTimeConstant = 0.6
        source.connect(analyser)
        analyser.connect(ctx.destination)
        audioCtxRef.current = ctx
        sourceRef.current = source
        analyserRef.current = analyser
        dataRef.current = new Uint8Array(analyser.frequencyBinCount)
      } catch {
        // createMediaElementSource can only be called once per element; if it
        // throws we simply fall back to the timed animation below.
        analyserRef.current = null
      }
    }

    let fallbackPhase = 0

    const tick = () => {
      let target = 0
      let wideTarget = 1

      if (isSpeaking) {
        const analyser = analyserRef.current
        const data = dataRef.current
        if (analyser && data) {
          analyser.getByteFrequencyData(data)
          // Focus on the low-mid band where speech energy lives.
          let sum = 0
          const bins = Math.min(48, data.length)
          for (let i = 2; i < bins; i++) sum += data[i]
          const avg = sum / (bins - 2) / 255 // 0..1
          target = Math.min(1, avg * 2.4)
          // Vary mouth width from spectral tilt for more natural visemes.
          let hi = 0
          for (let i = bins; i < Math.min(bins * 2, data.length); i++) hi += data[i]
          const hiAvg = hi / bins / 255
          wideTarget = 0.9 + Math.min(0.35, hiAvg * 1.6)
        } else {
          // Fallback: organic-looking timed motion.
          fallbackPhase += 0.35
          target =
            0.35 +
            0.3 * Math.abs(Math.sin(fallbackPhase)) +
            0.2 * Math.abs(Math.sin(fallbackPhase * 2.3))
          wideTarget = 1 + 0.15 * Math.sin(fallbackPhase * 1.7)
        }
      }

      // Smooth toward the target so lips don't jitter.
      const s = smoothedRef.current
      const next = s + (target - s) * (target > s ? 0.5 : 0.28)
      smoothedRef.current = next
      setMouth(next)
      setMouthWide((prev: number) => prev + (wideTarget - prev) * 0.3)

      rafRef.current = requestAnimationFrame(tick)
    }

    if (isSpeaking) {
      ensureAnalyser()
      // Resume context (browsers suspend until user gesture / playback).
      audioCtxRef.current?.resume?.().catch(() => {})
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [isSpeaking, audioRef])

  // Derived geometry for the lips.
  const openAmt = isSpeaking ? mouth : 0
  const lipGap = 1 + openAmt * 15 // vertical opening
  const lipHalfW = 15 * mouthWide // horizontal half-width
  const smile = isListening && !isSpeaking ? 4 : state === 'idle' ? 3 : 1

  // Eye state: closed on blink, half on thinking.
  const eyeOpen = blink ? 0.08 : state === 'thinking' ? 0.5 : 1

  return (
    <div
      className={`avatar-container relative ${isSpeaking ? 'avatar-speaking' : ''} ${
        isListening ? 'avatar-listening' : ''
      }`}
    >
      {/* Ambient glow behind the head */}
      <div
        className={`absolute inset-0 transition-all duration-1000 ${
          isSpeaking
            ? 'bg-gradient-to-br from-primary-500/25 to-accent-500/25 animate-glow'
            : isListening
            ? 'bg-gradient-to-br from-green-500/15 to-primary-500/15'
            : 'bg-transparent'
        }`}
      />

      <div className="absolute inset-0 flex items-center justify-center">
        <svg
          viewBox="0 0 300 320"
          className="avatar-face w-full h-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Skin gradient for soft, rounded shading */}
            <radialGradient id="skin" cx="42%" cy="38%" r="75%">
              <stop offset="0%" stopColor="#f6d3b6" />
              <stop offset="55%" stopColor="#eabf9c" />
              <stop offset="100%" stopColor="#cf9d78" />
            </radialGradient>
            <radialGradient id="neckShade" cx="50%" cy="0%" r="90%">
              <stop offset="0%" stopColor="#c99873" />
              <stop offset="100%" stopColor="#b3805d" />
            </radialGradient>
            {/* Hair gradient */}
            <linearGradient id="hair" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b2416" />
              <stop offset="100%" stopColor="#1c1109" />
            </linearGradient>
            <linearGradient id="hairShine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
              <stop offset="45%" stopColor="#8a6a4f" stopOpacity="0.35" />
              <stop offset="60%" stopColor="#ffffff" stopOpacity="0" />
            </linearGradient>
            {/* Iris gradient */}
            <radialGradient id="iris" cx="50%" cy="45%" r="55%">
              <stop offset="0%" stopColor="#7a5a3a" />
              <stop offset="55%" stopColor="#4a3320" />
              <stop offset="100%" stopColor="#241708" />
            </radialGradient>
            {/* Lip gradient */}
            <linearGradient id="lip" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#c9736c" />
              <stop offset="100%" stopColor="#a34d4a" />
            </linearGradient>
            {/* Soft shadow for depth */}
            <filter id="soft" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3" />
            </filter>
            <radialGradient id="cheek" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#e88b82" stopOpacity="0.45" />
              <stop offset="100%" stopColor="#e88b82" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Group that breathes / sways subtly */}
          <g className="avatar-head">
            {/* Neck */}
            <path
              d="M120 250 L120 300 Q150 315 180 300 L180 250 Z"
              fill="url(#neckShade)"
            />
            {/* Neck shadow under chin */}
            <ellipse cx="150" cy="252" rx="34" ry="14" fill="#a5744f" opacity="0.5" filter="url(#soft)" />

            {/* Back hair behind the face */}
            <path
              d="M78 120 C70 60 110 30 150 30 C190 30 230 60 222 120 L232 240 C232 240 210 210 205 175 L205 130 C205 130 195 160 150 160 C105 160 95 130 95 130 L95 175 C90 210 68 240 68 240 Z"
              fill="url(#hair)"
            />

            {/* Face */}
            <path
              d="M88 130 C88 90 112 66 150 66 C188 66 212 90 212 130 C212 175 195 205 175 225 C165 236 158 244 150 244 C142 244 135 236 125 225 C105 205 88 175 88 130 Z"
              fill="url(#skin)"
            />

            {/* Cheek blush / shading */}
            <ellipse cx="112" cy="172" rx="20" ry="15" fill="url(#cheek)" />
            <ellipse cx="188" cy="172" rx="20" ry="15" fill="url(#cheek)" />
            {/* Forehead / side shading for volume */}
            <path d="M88 130 C88 100 100 78 120 70 C104 90 98 112 100 140 C96 138 90 135 88 130 Z" fill="#c99873" opacity="0.35" />
            <path d="M212 130 C212 100 200 78 180 70 C196 90 202 112 200 140 C204 138 210 135 212 130 Z" fill="#c99873" opacity="0.35" />

            {/* Eyebrows */}
            <path
              className="avatar-brow"
              d="M104 118 Q124 108 143 116"
              fill="none"
              stroke="#2b1a0e"
              strokeWidth="5"
              strokeLinecap="round"
            />
            <path
              className="avatar-brow"
              d="M157 116 Q176 108 196 118"
              fill="none"
              stroke="#2b1a0e"
              strokeWidth="5"
              strokeLinecap="round"
            />

            {/* Eyes */}
            <g>
              {/* eye sockets shadow */}
              <ellipse cx="123" cy="136" rx="20" ry="13" fill="#d9a982" opacity="0.5" />
              <ellipse cx="177" cy="136" rx="20" ry="13" fill="#d9a982" opacity="0.5" />

              {/* Left eye white */}
              <g transform={`translate(123 136) scale(1 ${eyeOpen})`}>
                <ellipse cx="0" cy="0" rx="17" ry="10" fill="#fbf7f2" />
                <ellipse cx="0" cy="0" rx="8" ry="8" fill="url(#iris)" />
                <circle cx="0" cy="0" r="3.4" fill="#100a04" />
                <circle cx="-2.6" cy="-2.6" r="1.8" fill="#fff" opacity="0.85" />
              </g>
              {/* Right eye white */}
              <g transform={`translate(177 136) scale(1 ${eyeOpen})`}>
                <ellipse cx="0" cy="0" rx="17" ry="10" fill="#fbf7f2" />
                <ellipse cx="0" cy="0" rx="8" ry="8" fill="url(#iris)" />
                <circle cx="0" cy="0" r="3.4" fill="#100a04" />
                <circle cx="-2.6" cy="-2.6" r="1.8" fill="#fff" opacity="0.85" />
              </g>

              {/* Upper eyelid lines / lashes */}
              <path d="M106 130 Q123 122 140 130" fill="none" stroke="#3a2414" strokeWidth="2" strokeLinecap="round" />
              <path d="M160 130 Q177 122 194 130" fill="none" stroke="#3a2414" strokeWidth="2" strokeLinecap="round" />
            </g>

            {/* Nose */}
            <path
              d="M150 140 L150 172 M150 172 Q140 178 134 172 M150 172 Q160 178 166 172"
              fill="none"
              stroke="#c08a63"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <ellipse cx="150" cy="172" rx="9" ry="5" fill="#d9a982" opacity="0.4" />

            {/* --- Mouth / lips (lip-sync) --- */}
            <g className="avatar-mouth">
              {/* Inner mouth (only visible when open) */}
              {openAmt > 0.05 && (
                <path
                  d={`M ${150 - lipHalfW} 196
                      Q 150 ${196 - lipGap * 0.55} ${150 + lipHalfW} 196
                      Q 150 ${196 + lipGap} ${150 - lipHalfW} 196 Z`}
                  fill="#5a1f22"
                />
              )}
              {/* Teeth hint when fairly open */}
              {openAmt > 0.35 && (
                <path
                  d={`M ${150 - lipHalfW * 0.8} 194
                      Q 150 191 ${150 + lipHalfW * 0.8} 194
                      Q 150 197 ${150 - lipHalfW * 0.8} 194 Z`}
                  fill="#fcf7f0"
                  opacity="0.9"
                />
              )}
              {/* Upper lip */}
              <path
                d={`M ${150 - lipHalfW} 196
                    Q ${150 - lipHalfW * 0.4} ${188 - smile} 150 191
                    Q ${150 + lipHalfW * 0.4} ${188 - smile} ${150 + lipHalfW} 196
                    Q 150 ${196 - lipGap * 0.55} ${150 - lipHalfW} 196 Z`}
                fill="url(#lip)"
              />
              {/* Lower lip */}
              <path
                d={`M ${150 - lipHalfW} 196
                    Q 150 ${196 + lipGap + 5 + smile} ${150 + lipHalfW} 196
                    Q 150 ${196 + lipGap} ${150 - lipHalfW} 196 Z`}
                fill="url(#lip)"
              />
              {/* Lip highlight */}
              <path
                d={`M ${150 - lipHalfW * 0.6} 197 Q 150 ${199 + lipGap * 0.4} ${150 + lipHalfW * 0.6} 197`}
                fill="none"
                stroke="#e8a39c"
                strokeWidth="1.4"
                strokeLinecap="round"
                opacity="0.7"
              />
            </g>

            {/* Front hair / bangs framing the face */}
            <path
              d="M85 132 C80 82 112 52 150 52 C188 52 220 82 215 132 C210 112 200 96 190 92 C196 104 196 118 194 126 C186 104 172 92 150 92 C128 92 114 104 106 126 C104 118 104 104 110 92 C100 96 90 112 85 132 Z"
              fill="url(#hair)"
            />
            <path
              d="M150 52 C120 52 96 70 88 100 C96 84 112 72 130 68 Z"
              fill="url(#hairShine)"
            />
          </g>
        </svg>
      </div>

      {/* State indicator */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
        {isSpeaking && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-primary-600/80 rounded-full backdrop-blur-sm">
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
          <div className="flex items-center gap-1.5 px-3 py-1 bg-green-600/80 rounded-full backdrop-blur-sm">
            <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse" />
            <span className="text-xs text-white font-medium">Listening</span>
          </div>
        )}
        {state === 'thinking' && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-yellow-600/80 rounded-full backdrop-blur-sm">
            <div className="w-2 h-2 bg-yellow-300 rounded-full animate-pulse" />
            <span className="text-xs text-white font-medium">Thinking...</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default Avatar
