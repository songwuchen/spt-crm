import { Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'
import { Button, Result } from 'antd'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

function reportError(error: Error, componentStack?: string) {
  try {
    const token = localStorage.getItem('access_token')
    const payload = {
      type: 'ui_error',
      message: error.message,
      stack: error.stack?.slice(0, 2000),
      component_stack: componentStack?.slice(0, 2000),
      url: window.location.href,
      user_agent: navigator.userAgent,
      timestamp: new Date().toISOString(),
    }
    navigator.sendBeacon?.(
      '/api/v1/frontend-errors',
      new Blob([JSON.stringify(payload)], { type: 'application/json' }),
    ) || fetch('/api/v1/frontend-errors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {})
  } catch {}
}

// Global unhandled error + rejection capture
if (typeof window !== 'undefined') {
  window.addEventListener('error', (e) => {
    if (e.error) reportError(e.error)
  })
  window.addEventListener('unhandledrejection', (e) => {
    const err = e.reason instanceof Error ? e.reason : new Error(String(e.reason))
    reportError(err)
  })
}

// Simple performance observer
if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
  try {
    const lcp = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const last = entries[entries.length - 1]
      if (last) {
        (window as any).__spt_lcp = last.startTime
      }
    })
    lcp.observe({ type: 'largest-contentful-paint', buffered: true })
  } catch {}

  try {
    const longTask = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 200) {
          console.warn('[perf] Long task:', entry.duration.toFixed(0), 'ms')
        }
      }
    })
    longTask.observe({ type: 'longtask', buffered: true })
  } catch {}
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
    reportError(error, info.componentStack ?? undefined)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center min-h-[400px] p-8">
          <Result
            status="error"
            title="页面出错了"
            subTitle={this.state.error?.message || '发生了未知错误，请尝试刷新页面'}
            extra={[
              <Button key="retry" type="primary" onClick={this.handleReset}>
                重试
              </Button>,
              <Button key="reload" onClick={this.handleReload}>
                刷新页面
              </Button>,
            ]}
          />
        </div>
      )
    }
    return this.props.children
  }
}
