import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { authApi } from '@/api/auth'
import NotificationBell from '@/components/NotificationBell'
import ErrorBoundary from '@/components/ErrorBoundary'

const tabs = [
  { key: '/m', icon: 'dashboard', label: '工作台' },
  { key: '/m/customers', icon: 'business', label: '客户' },
  { key: '/m/opportunities', icon: 'rocket_launch', label: '商机' },
  { key: '/m/profile', icon: 'person', label: '我的' },
]

export default function MobileLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.token)
  const setUser = useAuthStore((s) => s.setUser)
  const setUserLoading = useAuthStore((s) => s.setUserLoading)
  const logout = useAuthStore((s) => s.logout)
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const on = () => setOffline(false)
    const off = () => setOffline(true)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [])

  // Load current user. The mobile domain (link.fourier.net.cn) enters /m directly
  // without ever mounting MainLayout, so MobileLayout must fetch /auth/me itself —
  // otherwise greeting/avatar/profile/permissions stay empty.
  useEffect(() => {
    if (!token) {
      setUserLoading(false)
      navigate('/login', { replace: true })
      return
    }
    setUserLoading(true)
    authApi.me()
      .then((res) => { if (res.data) setUser(res.data) })
      .catch(() => {
        logout()
        navigate('/login', { replace: true })
      })
  }, [token])

  return (
    <div className="flex flex-col min-h-screen bg-slate-50">
      {/* Offline Banner */}
      {offline && (
        <div className="bg-amber-500 text-white text-sm font-bold text-center py-1 px-2">
          <span className="material-symbols-outlined text-sm align-middle mr-1" style={{ fontSize: 14 }}>cloud_off</span>
          离线模式 — 部分数据可能不是最新的
        </div>
      )}
      {/* Mobile Header */}
      <header className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 h-12 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="SPT-CRM" className="w-7 h-7 rounded-lg object-cover" />
          <span className="font-bold text-sm text-slate-900">SPT-CRM</span>
        </div>
        <div className="flex items-center gap-3">
          <NotificationBell />
          <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center text-sm font-bold text-primary">
            {(user?.real_name || user?.username || 'U').slice(0, 1)}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 p-3 pb-16 overflow-y-auto">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>

      {/* Bottom Tab Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-20 bg-white border-t border-slate-200 h-14 flex items-center justify-around safe-area-bottom">
        {tabs.map((t) => {
          const active = t.key === '/m' ? location.pathname === '/m' : location.pathname.startsWith(t.key)
          return (
            <button
              key={t.key}
              onClick={() => navigate(t.key)}
              className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors border-0 bg-transparent cursor-pointer ${
                active ? 'text-primary' : 'text-slate-400'
              }`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{t.icon}</span>
              <span className="text-[12px] font-bold">{t.label}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
