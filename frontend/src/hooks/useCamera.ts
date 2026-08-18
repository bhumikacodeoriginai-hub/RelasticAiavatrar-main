import { useState, useRef, useCallback, useEffect } from 'react'

interface UseCameraOptions {
  width?: number
  height?: number
  facingMode?: 'user' | 'environment'
  onFrame?: (imageData: string) => void
  captureInterval?: number
}

export function useCamera(options: UseCameraOptions = {}) {
  const [isActive, setIsActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasPermission, setHasPermission] = useState<boolean | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const {
    width = 640,
    height = 480,
    facingMode = 'user',
    onFrame,
    captureInterval = 1000,
  } = options

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: width },
          height: { ideal: height },
          facingMode,
        },
      })

      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }

      setIsActive(true)
      setHasPermission(true)
      setError(null)

      // Start frame capture if callback provided
      if (onFrame) {
        intervalRef.current = setInterval(() => {
          captureFrame()
        }, captureInterval)
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Camera access denied'
      setError(errorMsg)
      setHasPermission(false)
      setIsActive(false)
    }
  }, [width, height, facingMode, onFrame, captureInterval])

  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setIsActive(false)
  }, [])

  const captureFrame = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current) return null

    const canvas = canvasRef.current
    const video = videoRef.current
    canvas.width = video.videoWidth || width
    canvas.height = video.videoHeight || height

    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    ctx.drawImage(video, 0, 0)
    const imageData = canvas.toDataURL('image/jpeg', 0.7)

    if (onFrame) {
      // Remove the data:image/jpeg;base64, prefix
      const base64 = imageData.split(',')[1]
      onFrame(base64)
    }

    return imageData
  }, [width, height, onFrame])

  const capturePhoto = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current) return null

    const canvas = canvasRef.current
    const video = videoRef.current
    canvas.width = video.videoWidth || width
    canvas.height = video.videoHeight || height

    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    ctx.drawImage(video, 0, 0)
    return canvas.toDataURL('image/jpeg', 0.95)
  }, [width, height])

  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [stopCamera])

  return {
    isActive,
    error,
    hasPermission,
    videoRef,
    canvasRef,
    startCamera,
    stopCamera,
    captureFrame,
    capturePhoto,
  }
}
