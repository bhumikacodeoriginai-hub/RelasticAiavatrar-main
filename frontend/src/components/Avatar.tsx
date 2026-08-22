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
 * Photoreal receptionist avatar (Option 3).
 *
 * Renders a real portrait photograph (the Code Origin.AI receptionist) and
 * overlays lightweight, real-time animation on top of it:
 *   - Mouth lip-sync driven by the actual TTS audio amplitude (Web Audio API).
 *   - Natural eye blinking.
 *   - Subtle head sway / breathing so the face feels alive.
 *
 * This is a purely presentational component. It only reads props and the
 * optional audio element — it NEVER touches the WebSocket / AI / voice logic.
 *
 * The portrait image is resolved from a list of candidate URLs so it works
 * both when served by Vite (frontend/public/receptionist.png) and by the
 * backend static route (/static/receptionist.png|jpg).
 */

// Candidate locations for the receptionist portrait, tried in order.
const IMAGE_CANDIDATES = [
  '/receptionist.png',
  '/receptionist.jpg',
  '/static/receptionist.png',
  '/static/receptionist.jpg',
  // When the frontend is served on a different origin than the backend during
  // dev, allow an explicit backend URL via Vite env (optional).
  (import.meta.env.VITE_AVATAR_IMAGE_URL as string) || '',
].filter(Boolean)

function Avatar({ isSpeaking, isListening, state, audioRef }: AvatarProps) {
  // 0 = closed, 1 = fully open (smoothed).
  const [mouth, setMouth] = useState(0)
  const [blink, setBlink] = useState(false)
  const [imgIndex, setImgIndex] = useState(0)
  const [imgFailed, setImgFailed] = useState(false)

  const rafRef = useRef<number | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const dataRef = useRef<Uint8Array | null>(null)
  const smoothedRef = useRef(0)

  const imageUrl = IMAGE_CANDIDATES[imgIndex]

  // --- Natural blinking ---
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>
    const scheduleBlink = () => {
      const delay = 2200 + Math.random() * 3200
      timeout = setTimeout(() => {
        setBlink(true)
        setTimeout(() => setBlink(false), 130)
        scheduleBlink()
      }, delay)
    }
    scheduleBlink()
    return () => clearTimeout(timeout)
  }, [])

  // --- Real lip-sync from audio amplitude (with graceful fallback) ---
  useEffect(() => {
    const audioEl = audioRef?.current

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
        analyserRef.current = analyser
        dataRef.current = new Uint8Array(analyser.frequencyBinCount)
      } catch {
        // createMediaElementSource can only be called once per element; if it
        // throws, fall back to the timed animation.
        analyserRef.current = null
      }
    }

    let fallbackPhase = 0

    const tick = () => {
      let target = 0

      if (isSpeaking) {
        const analyser = analyserRef.current
        const data = dataRef.current
        if (analyser && data) {
          analyser.getByteFrequencyData(data)
          let sum = 0
          const bins = Math.min(48, data.length)
          for (let i = 2; i < bins; i++) sum += data[i]
          const avg = sum / (bins - 2) / 255
          target = Math.min(1, avg * 2.4)
        } else {
          fallbackPhase += 0.35
          target =
            0.35 +
            0.3 * Math.abs(Math.sin(fallbackPhase)) +
            0.2 * Math.abs(Math.sin(fallbackPhase * 2.3))
        }
      }

      const s = smoothedRef.current
      const next = s + (target - s) * (target > s ? 0.5 : 0.28)
      smoothedRef.current = next
      setMouth(next)

      rafRef.current = requestAnimationFrame(tick)
    }

    if (isSpeaking) {
      ensureAnalyser()
      audioCtxRef.current?.resume?.().catch(() => {})
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [isSpeaking, audioRef])

  const openAmt = isSpeaking ? mouth : 0

  return (
    <div
      className={`avatar-container relative ${isSpeaking ? 'avatar-speaking' : ''} ${
        isListening ? 'avatar-listening' : ''
      }`}
    >
      {/* Ambient glow behind the portrait */}
      <div
        className={`absolute inset-0 z-0 transition-all duration-1000 ${
          isSpeaking
            ? 'bg-gradient-to-br from-primary-500/25 to-accent-500/25 animate-glow'
            : isListening
            ? 'bg-gradient-to-br from-green-500/15 to-primary-500/15'
            : 'bg-transparent'
        }`}
      />

      {/* Photoreal face with animated overlays */}
      <div className="avatar-photo-wrap absolute inset-0 z-10 flex items-center justify-center overflow-hidden">
        {!imgFailed ? (
          <div className="avatar-photo-inner relative w-full h-full">
            <img
              src={imageUrl}
              alt="AI Receptionist"
              className="avatar-photo w-full h-full object-cover object-top select-none pointer-events-none"
              draggable={false}
              onError={() => {
                // Try the next candidate URL; if all fail, show fallback UI.
                if (imgIndex < IMAGE_CANDIDATES.length - 1) {
                  setImgIndex((i: number) => i + 1)
                } else {
                  setImgFailed(true)
                }
              }}
            />

            {/*
              Overlay layer positioned over the face. Coordinates are tuned as
              percentages for the provided receptionist portrait (face centered,
              eyes ~40% down, mouth ~56% down).
            */}
            {/* Eyelids for blinking — thin skin-toned bars that drop over eyes */}
            <div
              className="avatar-eyelid avatar-eyelid-left"
              style={{ opacity: blink ? 1 : 0 }}
            />
            <div
              className="avatar-eyelid avatar-eyelid-right"
              style={{ opacity: blink ? 1 : 0 }}
            />

            {/* Mouth: a soft dark ellipse that grows with audio amplitude to
                simulate the lips opening. Sits over the mouth region. */}
            <div
              className="avatar-mouth-overlay"
              style={{
                transform: `translate(-50%, -50%) scaleY(${0.15 + openAmt * 1})`,
                opacity: openAmt > 0.06 ? 0.75 : 0,
              }}
            />
            {/* Subtle lower-lip shadow that deepens when the mouth opens */}
            <div
              className="avatar-mouth-shadow"
              style={{ opacity: openAmt * 0.5 }}
            />
          </div>
        ) : (
          // Fallback if the image can't be loaded, so the UI never breaks.
          <div className="flex flex-col items-center justify-center text-center px-6">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-4xl mb-3">
              🤖
            </div>
            <p className="text-sm text-gray-300">Receptionist</p>
            <p className="text-xs text-gray-500 mt-1">
              Add <code>receptionist.png</code> to serve the photo avatar
            </p>
          </div>
        )}
      </div>

      {/* State indicator */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20">
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
