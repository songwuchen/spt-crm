import { useState, useRef, useEffect } from 'react'
import { Dropdown, Avatar, Input, Spin } from 'antd'
import { LogoutOutlined, UserOutlined, SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '@/stores/useAppStore'
import { useAuthStore } from '@/stores/useAuthStore'
import NotificationBell from '@/components/NotificationBell'
import client from '@/api/client'
import { t, useLocale, localeLabels, type LocaleCode } from '@/locales'
import { useThemeStore } from '@/stores/useThemeStore'

interface SearchResult {
  type: string
  id: string
  title: string
  subtitle: string
  url: string
}

const typeIcons: Record<string, { icon: string; label: string; color: string }> = {
  customer: { icon: 'business', label: '客户', color: '#3b82f6' },
  lead: { icon: 'trending_up', label: '线索', color: '#10b981' },
  project: { icon: 'rocket_launch', label: '商机', color: '#f59e0b' },
  contact: { icon: 'person', label: '联系人', color: '#6366f1' },
  ticket: { icon: 'confirmation_number', label: '工单', color: '#ef4444' },
}

export default function Header() {
  const { sidebarCollapsed, toggleSidebar } = useAppStore()
  const { user, logout } = useAuthStore()
  const { locale, setLocale } = useLocale()
  const { theme, setTheme } = useThemeStore()
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [showResults, setShowResults] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<any>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const handler = () => searchInputRef.current?.focus()
    window.addEventListener('focus-search', handler)
    return () => window.removeEventListener('focus-search', handler)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const doSearch = async (q: string) => {
    if (!q.trim()) { setResults([]); return }
    setSearching(true)
    try {
      const res = await client.get('/api/v1/dashboard/search', { params: { q: q.trim() } }) as any
      setResults(res.data || [])
      setShowResults(true)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleSearchChange = (val: string) => {
    setSearchText(val)
    if (timerRef.current) clearTimeout(timerRef.current)
    if (val.trim().length >= 1) {
      timerRef.current = setTimeout(() => doSearch(val), 300)
    } else {
      setResults([])
      setShowResults(false)
    }
  }

  const [activeIdx, setActiveIdx] = useState(-1)

  const handleResultClick = (r: SearchResult) => {
    navigate(r.url)
    setShowResults(false)
    setSearchText('')
    setActiveIdx(-1)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showResults || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((prev) => (prev + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((prev) => (prev <= 0 ? results.length - 1 : prev - 1))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault()
      handleResultClick(results[activeIdx])
    } else if (e.key === 'Escape') {
      setShowResults(false)
      setActiveIdx(-1)
    }
  }

  const highlightMatch = (text: string, query: string) => {
    if (!query.trim()) return text
    const idx = text.toLowerCase().indexOf(query.toLowerCase())
    if (idx === -1) return text
    return (
      <>
        {text.slice(0, idx)}
        <mark className="bg-yellow-200 text-inherit rounded-sm px-0.5">{text.slice(idx, idx + query.length)}</mark>
        {text.slice(idx + query.length)}
      </>
    )
  }

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowResults(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="h-14 sm:h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-700 flex items-center justify-between px-3 sm:px-4 md:px-6 sticky top-0 z-10">
      {/* Left: Toggle + Search */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggleSidebar}
          className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
        >
          <span className="material-symbols-outlined text-xl">
            {sidebarCollapsed ? 'menu_open' : 'menu'}
          </span>
        </button>
        <div ref={searchRef} style={{ position: 'relative' }} data-tour="search">
          <Input
            ref={searchInputRef}
            placeholder="搜索客户、线索、商机... (Ctrl+K)"
            prefix={searching ? <Spin size="small" /> : <SearchOutlined className="text-slate-400" />}
            className="w-40 sm:w-56 md:w-72 rounded-lg"
            style={{ background: '#f1f5f9', borderColor: 'transparent' }}
            value={searchText}
            onChange={(e) => handleSearchChange(e.target.value)}
            onFocus={() => { if (results.length > 0) setShowResults(true) }}
            onKeyDown={handleKeyDown}
          />
          {showResults && results.length > 0 && (
            <div
              className="absolute left-0 top-full mt-1 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden"
              style={{ width: 'min(400px, calc(100vw - 2rem))', maxHeight: 400, zIndex: 1000 }}
            >
              {/* Group by type */}
              {Object.entries(
                results.reduce<Record<string, SearchResult[]>>((acc, r) => {
                  (acc[r.type] ||= []).push(r); return acc
                }, {})
              ).map(([type, items]) => {
                const ti = typeIcons[type] || typeIcons.customer
                return (
                  <div key={type}>
                    <div className="px-4 py-1.5 bg-slate-50 text-[12px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                      {ti.label}（{items.length}）
                    </div>
                    {items.map((r) => {
                      const globalIdx = results.indexOf(r)
                      return (
                        <div
                          key={`${r.type}-${r.id}`}
                          onClick={() => handleResultClick(r)}
                          className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                            globalIdx === activeIdx ? 'bg-primary/5' : 'hover:bg-slate-50'
                          }`}
                        >
                          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                            style={{ background: `${ti.color}15` }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 18, color: ti.color }}>{ti.icon}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-semibold text-slate-800 truncate">{highlightMatch(r.title, searchText)}</div>
                            {r.subtitle && <div className="text-[13px] text-slate-400 truncate">{highlightMatch(r.subtitle, searchText)}</div>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
          )}
          {showResults && results.length === 0 && searchText.trim() && !searching && (
            <div
              className="absolute left-0 top-full mt-1 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden"
              style={{ width: 'min(400px, calc(100vw - 2rem))', zIndex: 1000 }}
            >
              <div className="text-center py-6 text-sm text-slate-400">未找到匹配结果</div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Lang + Notifications + User */}
      <div className="flex items-center gap-3">
        <Dropdown
          menu={{
            items: (['zh-CN', 'en-US'] as LocaleCode[]).map((code) => ({
              key: code,
              label: localeLabels[code],
              onClick: () => setLocale(code),
            })),
            selectedKeys: [locale],
          }}
          placement="bottomRight"
        >
          <button className="flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-slate-100 text-sm font-bold text-slate-500 transition-colors">
            <span className="material-symbols-outlined text-base">translate</span>
            <span className="hidden sm:inline">{locale === 'zh-CN' ? '中文' : 'EN'}</span>
          </button>
        </Dropdown>

        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
          title={theme === 'dark' ? '浅色模式' : '深色模式'}
          data-tour="theme"
        >
          <span className="material-symbols-outlined text-lg">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
        </button>

        <span data-tour="notifications"><NotificationBell /></span>

        <div className="h-8 w-px bg-slate-200 mx-1" />

        <Dropdown
          menu={{
            items: [
              { key: 'profile', icon: <UserOutlined />, label: t('nav.profile'), onClick: () => navigate('/profile') },
              { type: 'divider' as const },
              { key: 'logout', icon: <LogoutOutlined />, label: t('auth.logout'), onClick: handleLogout },
            ],
          }}
          placement="bottomRight"
        >
          <div className="flex items-center gap-3 cursor-pointer hover:bg-slate-50 rounded-lg px-2 py-1.5 transition-colors">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-semibold text-slate-900 leading-tight">
                {user?.real_name || user?.username || '用户'}
              </div>
              <div className="text-[13px] text-slate-400 leading-tight">
                {user?.roles?.[0] || '成员'}
              </div>
            </div>
            <Avatar
              size={36}
              icon={<UserOutlined />}
              className="bg-primary/10 text-primary border-2 border-white shadow-sm"
            />
          </div>
        </Dropdown>
      </div>
    </div>
  )
}
