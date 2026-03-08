import { useState, useRef, useCallback } from 'react'
import { Button, Tooltip } from 'antd'

interface VoiceInputProps {
  onResult: (text: string) => void
  className?: string
}

// Extend window for SpeechRecognition
interface SpeechRecognitionEvent {
  results: { [key: number]: { [key: number]: { transcript: string } }; length: number }
  resultIndex: number
}

export default function VoiceInput({ onResult, className }: VoiceInputProps) {
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<any>(null)

  const supported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  const start = useCallback(() => {
    if (!supported) return
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = false

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      if (transcript) onResult(transcript)
    }

    recognition.onerror = () => {
      setListening(false)
    }

    recognition.onend = () => {
      setListening(false)
    }

    recognition.start()
    recognitionRef.current = recognition
    setListening(true)
  }, [supported, onResult])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  if (!supported) return null

  return (
    <Tooltip title={listening ? '点击停止' : '语音录入'}>
      <Button
        type={listening ? 'primary' : 'default'}
        danger={listening}
        shape="circle"
        size="small"
        className={className}
        onClick={listening ? stop : start}
        icon={
          <span className={`material-symbols-outlined ${listening ? 'animate-pulse' : ''}`} style={{ fontSize: 16 }}>
            {listening ? 'stop_circle' : 'mic'}
          </span>
        }
      />
    </Tooltip>
  )
}
