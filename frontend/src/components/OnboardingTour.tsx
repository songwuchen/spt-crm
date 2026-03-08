import { useState, useEffect } from 'react'
import { Button } from 'antd'
import { CloseOutlined } from '@ant-design/icons'

interface TourStep {
  target: string // CSS selector
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
}

const TOUR_STEPS: TourStep[] = [
  { target: '[data-tour="sidebar"]', title: '导航菜单', content: '左侧菜单可以快速切换各个功能模块，包括客户、商机、工单等', placement: 'right' },
  { target: '[data-tour="dashboard"]', title: '工作台', content: '这里展示了您最关注的业务数据和待办事项，可自定义卡片布局' },
  { target: '[data-tour="search"]', title: '全局搜索', content: '按 Ctrl+K 可快速搜索客户、商机、线索等，支持模糊匹配' },
  { target: '[data-tour="notifications"]', title: '消息通知', content: '这里会显示审批提醒、工单通知、@提及等消息' },
  { target: '[data-tour="theme"]', title: '主题切换', content: '支持亮色/暗色/跟随系统三种模式' },
  { target: '[data-tour="shortcuts"]', title: '快捷键', content: 'Ctrl+K 搜索、Ctrl+N 新建、Esc 关闭弹窗，提升操作效率' },
  { target: '[data-tour="calendar"]', title: '日历', content: '查看回款计划、合同到期、里程碑等日程事件' },
]

const STORAGE_KEY = 'spt_onboarding_done'

export default function OnboardingTour() {
  const [step, setStep] = useState(-1) // -1 = not started
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0, height: 0 })

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY)
    if (!done) {
      const timer = setTimeout(() => setStep(0), 1000)
      return () => clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (step < 0 || step >= TOUR_STEPS.length) return
    const el = document.querySelector(TOUR_STEPS[step].target)
    if (el) {
      const rect = el.getBoundingClientRect()
      setPosition({ top: rect.top, left: rect.left, width: rect.width, height: rect.height })
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [step])

  const finish = () => {
    setStep(-1)
    localStorage.setItem(STORAGE_KEY, '1')
  }

  const next = () => {
    if (step >= TOUR_STEPS.length - 1) { finish(); return }
    setStep(step + 1)
  }

  if (step < 0 || step >= TOUR_STEPS.length) return null

  const current = TOUR_STEPS[step]
  const placement = current.placement || 'bottom'

  // Calculate tooltip position based on placement
  let tooltipStyle: React.CSSProperties = {}
  const gap = 12
  if (placement === 'bottom') {
    tooltipStyle = { top: position.top + position.height + gap, left: position.left }
  } else if (placement === 'top') {
    tooltipStyle = { top: position.top - gap, left: position.left, transform: 'translateY(-100%)' }
  } else if (placement === 'right') {
    tooltipStyle = { top: position.top, left: position.left + position.width + gap }
  } else {
    tooltipStyle = { top: position.top, left: position.left - gap, transform: 'translateX(-100%)' }
  }

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 z-[9998]" style={{ background: 'rgba(0,0,0,0.4)' }} onClick={finish} />

      {/* Highlight */}
      <div
        className="fixed z-[9999] rounded-lg ring-4 ring-blue-400 ring-opacity-80"
        style={{
          top: position.top - 4, left: position.left - 4,
          width: position.width + 8, height: position.height + 8,
          background: 'transparent', pointerEvents: 'none',
          transition: 'all 0.3s ease',
        }}
      />

      {/* Tooltip */}
      <div
        className="fixed z-[10000] bg-white rounded-xl shadow-2xl border border-slate-200 p-4 max-w-xs"
        style={{ ...tooltipStyle, transition: 'all 0.3s ease' }}
      >
        <div className="flex items-start justify-between mb-1">
          <h4 className="font-bold text-slate-800">{current.title}</h4>
          <CloseOutlined className="text-slate-400 cursor-pointer hover:text-slate-600" onClick={finish} />
        </div>
        <p className="text-sm text-slate-500 mb-3">{current.content}</p>
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">{step + 1} / {TOUR_STEPS.length}</span>
          <div className="flex gap-2">
            <Button size="small" onClick={finish}>跳过</Button>
            <Button size="small" type="primary" onClick={next}>
              {step === TOUR_STEPS.length - 1 ? '完成' : '下一步'}
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
