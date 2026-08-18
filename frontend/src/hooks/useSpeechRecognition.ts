import { useState, useRef, useCallback, useEffect } from 'react'

interface UseSpeechRecognitionOptions {
  language?: string
  continuous?: boolean
  interimResults?: boolean
  onResult?: (transcript: string, isFinal: boolean) => void
  onError?: (error: string) => void
}

export function useSpeechRecognition(options: UseSpeechRecognitionOptions = {}) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [isSupported, setIsSupported] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const {
    language = 'en-IN',
    continuous = true,
    interimResults = true,
    onResult,
    onError,
  } = options

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setIsSupported(!!SpeechRecognition)

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.lang = language
      recognition.continuous = continuous
      recognition.interimResults = interimResults
      recognition.maxAlternatives = 1

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let interim = ''
        let final = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i]
          if (result.isFinal) {
            final += result[0].transcript
            setTranscript(prev => prev + ' ' + final)
            onResult?.(final.trim(), true)
          } else {
            interim += result[0].transcript
          }
        }
        setInterimTranscript(interim)
      }

      recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
        console.error('Speech recognition error:', event.error)
        onError?.(event.error)
        if (event.error !== 'no-speech') {
          setIsListening(false)
        }
      }

      recognition.onend = () => {
        // Auto-restart if still supposed to be listening
        if (isListening && continuous) {
          try {
            recognition.start()
          } catch {
            setIsListening(false)
          }
        } else {
          setIsListening(false)
        }
      }

      recognitionRef.current = recognition
    }

    return () => {
      recognitionRef.current?.stop()
    }
  }, [language, continuous, interimResults, onResult, onError, isListening])

  const startListening = useCallback(() => {
    if (recognitionRef.current && !isListening) {
      setTranscript('')
      setInterimTranscript('')
      try {
        recognitionRef.current.start()
        setIsListening(true)
      } catch (error) {
        console.error('Failed to start recognition:', error)
      }
    }
  }, [isListening])

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }, [isListening])

  const resetTranscript = useCallback(() => {
    setTranscript('')
    setInterimTranscript('')
  }, [])

  return {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
  }
}

// Type declarations for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition
    webkitSpeechRecognition: typeof SpeechRecognition
  }
}
