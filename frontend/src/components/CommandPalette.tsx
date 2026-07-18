import { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import Icon from '@/components/Icon'
interface Command {
  id: string
  label: string
  icon: string
  category: string
  action: () => void
  keywords?: string
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const commands: Command[] = useMemo(() => [
    // Navigation
    { id: 'nav-dashboard', label: '仪表盘', icon: 'dashboard', category: '导航', action: () => navigate('/'), keywords: '首页 home' },
    { id: 'nav-customers', label: '客户列表', icon: 'business', category: '导航', action: () => navigate('/customers'), keywords: '客户' },
    { id: 'nav-leads', label: '线索列表', icon: 'trending_up', category: '导航', action: () => navigate('/leads'), keywords: '线索' },
    { id: 'nav-opportunities', label: '商机列表', icon: 'rocket_launch', category: '导航', action: () => navigate('/opportunities'), keywords: '商机 项目' },
    { id: 'nav-tickets', label: '工单列表', icon: 'confirmation_number', category: '导航', action: () => navigate('/service-tickets'), keywords: '工单 售后' },
    { id: 'nav-analytics', label: '报表中心', icon: 'analytics', category: '导航', action: () => navigate('/analytics'), keywords: '报表 分析' },
    { id: 'nav-approvals', label: '审批中心', icon: 'approval', category: '导航', action: () => navigate('/approvals'), keywords: '审批' },
    { id: 'nav-settings', label: '系统设置', icon: 'settings', category: '导航', action: () => navigate('/admin/settings'), keywords: '设置 配置' },
    // Create actions
    { id: 'create-customer', label: '新建客户', icon: 'person_add', category: '新建', action: () => navigate('/customers/new'), keywords: '创建 客户' },
    { id: 'create-lead', label: '新建线索', icon: 'add_circle', category: '新建', action: () => navigate('/leads/new'), keywords: '创建 线索' },
    { id: 'create-opportunity', label: '新建商机', icon: 'add_business', category: '新建', action: () => navigate('/opportunities/new'), keywords: '创建 商机 项目' },
    { id: 'create-ticket', label: '新建工单', icon: 'add_task', category: '新建', action: () => navigate('/service-tickets/new'), keywords: '创建 工单' },
  ], [navigate])

  const filtered = useMemo(() => {
    if (!query.trim()) return commands
    const q = query.toLowerCase()
    return commands.filter((c) =>
      c.label.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      (c.keywords && c.keywords.toLowerCase().includes(q))
    )
  }, [commands, query])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => { setSelectedIdx(0) }, [query])

  const execute = (cmd: Command) => {
    setOpen(false)
    cmd.action()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIdx]) {
      e.preventDefault()
      execute(filtered[selectedIdx])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  if (!open) return null

  const categories = [...new Set(filtered.map((c) => c.category))]

  return (
    <div className="fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh]"
      onClick={() => setOpen(false)}>
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      <div className="relative bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
          <Icon name="search" className="text-slate-400" style={{ fontSize: 20 }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入命令或搜索..."
            className="flex-1 text-sm outline-none bg-transparent text-slate-800 placeholder:text-slate-400"
          />
          <kbd className="px-1.5 py-0.5 rounded bg-slate-100 text-[12px] font-bold text-slate-400 border border-slate-200">ESC</kbd>
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto py-2">
          {filtered.length === 0 ? (
            <div className="text-center text-sm text-slate-400 py-8">未找到匹配的命令</div>
          ) : (
            categories.map((cat) => (
              <div key={cat}>
                <div className="px-4 py-1 text-[12px] font-bold text-slate-400 uppercase tracking-wider">{cat}</div>
                {filtered.filter((c) => c.category === cat).map((cmd) => {
                  const idx = filtered.indexOf(cmd)
                  return (
                    <div key={cmd.id}
                      className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                        idx === selectedIdx ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
                      }`}
                      onClick={() => execute(cmd)}
                      onMouseEnter={() => setSelectedIdx(idx)}>
                      <Icon name={cmd.icon} style={{ fontSize: 18 }} />
                      <span className="text-sm font-medium">{cmd.label}</span>
                    </div>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-slate-100 text-[12px] text-slate-400">
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-slate-100 border border-slate-200">↑↓</kbd> 移动
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-slate-100 border border-slate-200">↵</kbd> 确认
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-slate-100 border border-slate-200">Ctrl+K</kbd> 打开/关闭
          </span>
        </div>
      </div>
    </div>
  )
}
