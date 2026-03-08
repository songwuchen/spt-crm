import { useState, useEffect } from 'react'
import { Button } from 'antd'
import { CloseOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/useAuthStore'

interface TourStep {
  target: string // CSS selector
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  roles?: string[] // Only show for these roles (empty = all)
}

const TOUR_STEPS: TourStep[] = [
  { target: '[data-tour="sidebar"]', title: '导航菜单', content: '左侧菜单可以快速切换各个功能模块，包括客户、商机、工单等', placement: 'right' },
  { target: '[data-tour="dashboard"]', title: '工作台', content: '这里展示了您最关注的业务数据和待办事项。可以拖拽调整卡片顺序，点击设置按钮隐藏不需要的卡片' },
  { target: '[data-tour="search"]', title: '全局搜索 / 命令面板', content: '按 Ctrl+K 打开命令面板，可以快速搜索、导航到任意页面、或创建新记录' },
  { target: '[data-tour="notifications"]', title: '消息通知', content: '这里会显示审批提醒、工单通知、@提及等消息。关注客户或工单后会收到变更通知' },
  { target: '[data-tour="theme"]', title: '主题切换', content: '支持亮色/暗色/跟随系统三种模式' },
  { target: '[data-tour="shortcuts"]', title: '快捷键', content: 'Ctrl+K 命令面板、Ctrl+N 新建、Esc 关闭弹窗，提升操作效率', roles: ['sales', 'admin'] },
  { target: '[data-tour="calendar"]', title: '日历', content: '查看回款计划、合同到期、里程碑等日程事件' },
]

// Contextual tips shown on specific pages
export const CONTEXTUAL_TIPS: Record<string, { title: string; content: string }> = {
  '/customers': { title: '客户管理', content: '支持导入客户、批量转移、地图视图。新建客户时系统会自动查重' },
  '/leads': { title: '线索管理', content: '线索可以一键转化为客户和商机。支持批量导入和分配' },
  '/opportunities': { title: '商机管理', content: '支持看板视图拖拽推进阶段、报价管理、合同审批、回款计划追踪' },
  '/service-tickets': { title: '售后工单', content: '工单自动设置SLA时限。可搜索知识库查找类似问题的解决方案' },
  '/analytics': { title: '报表中心', content: '支持按时间段筛选、导出Excel/PDF/图片。阶段耗时分析帮助识别瓶颈' },
  '/approvals': { title: '审批中心', content: '支持批量审批、委托审批。长按可查看审批详情' },
}

const STORAGE_KEY = 'spt_onboarding_done'

export default function OnboardingTour() {
  const [step, setStep] = useState(-1) // -1 = not started
  const user = useAuthStore((s) => s.user)
  const [position, setPosition] = useState({ top: 0, left: 0, width: 0, height: 0 })

  const userRoles = user?.roles || []
  const filteredSteps = TOUR_STEPS.filter((s) =>
    !s.roles || s.roles.length === 0 || s.roles.some((r) => userRoles.includes(r)) || userRoles.includes('admin')
  )

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY)
    if (!done) {
      const timer = setTimeout(() => setStep(0), 1000)
      return () => clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (step < 0 || step >= filteredSteps.length) return
    const el = document.querySelector(filteredSteps[step].target)
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
    if (step >= filteredSteps.length - 1) { finish(); return }
    setStep(step + 1)
  }

  if (step < 0 || step >= filteredSteps.length) return null

  const current = filteredSteps[step]
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
          <span className="text-xs text-slate-400">{step + 1} / {filteredSteps.length}</span>
          <div className="flex gap-2">
            <Button size="small" onClick={finish}>跳过</Button>
            <Button size="small" type="primary" onClick={next}>
              {step === filteredSteps.length - 1 ? '完成' : '下一步'}
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
