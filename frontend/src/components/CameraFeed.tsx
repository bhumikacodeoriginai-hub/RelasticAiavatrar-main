import { useRef, useEffect } from 'react'

interface CameraFeedProps {
  videoRef: React.RefObject<HTMLVideoElement>
  canvasRef: React.RefObject<HTMLCanvasElement>
  isActive: boolean
  personDetected: boolean
  faceDetected: boolean
  onToggle: () => void
}

function CameraFeed({
  videoRef,
  canvasRef,
  isActive,
  personDetected,
  faceDetected,
  onToggle,
}: CameraFeedProps) {
  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300">Camera Feed</h3>
        <button
          onClick={onToggle}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
            isActive
              ? 'bg-red-600/20 text-red-400 hover:bg-red-600/30'
              : 'bg-green-600/20 text-green-400 hover:bg-green-600/30'
          }`}
        >
          {isActive ? 'Stop' : 'Start'}
        </button>
      </div>

      <div className="relative rounded-xl overflow-hidden bg-gray-900 aspect-video">
        {/* Video element */}
        <video
          ref={videoRef}
          className="w-full h-full object-cover"
          autoPlay
          muted
          playsInline
          style={{ display: isActive ? 'block' : 'none' }}
        />

        {/* Hidden canvas for frame capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Placeholder when camera is off */}
        {!isActive && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <svg className="w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z" />
            </svg>
            <span className="text-xs text-gray-500">Camera inactive</span>
          </div>
        )}

        {/* Detection indicators */}
        {isActive && (
          <div className="absolute top-2 left-2 flex flex-col gap-1">
            <div className={`status-badge ${personDetected ? 'bg-green-600/80 text-green-100' : 'bg-gray-700/80 text-gray-400'}`}>
              <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${personDetected ? 'bg-green-300' : 'bg-gray-500'}`} />
              Person {personDetected ? '✓' : '—'}
            </div>
            <div className={`status-badge ${faceDetected ? 'bg-blue-600/80 text-blue-100' : 'bg-gray-700/80 text-gray-400'}`}>
              <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${faceDetected ? 'bg-blue-300' : 'bg-gray-500'}`} />
              Face {faceDetected ? '✓' : '—'}
            </div>
          </div>
        )}

        {/* Recording indicator */}
        {isActive && (
          <div className="absolute top-2 right-2 flex items-center gap-1">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-xs text-red-400 font-medium">LIVE</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default CameraFeed
