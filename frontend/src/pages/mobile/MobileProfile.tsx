import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function MobileProfile() {
  usePageTitle('我的')
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div>
      {/* User Card */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-4 mb-4">
        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-xl font-black text-primary">
          {(user?.real_name || user?.username || 'U').slice(0, 1)}
        </div>
        <div>
          <div className="text-lg font-extrabold text-slate-900">{user?.real_name || user?.username}</div>
          <div className="text-xs text-slate-500">{user?.roles?.join(', ') || '-'}</div>
        </div>
      </div>

      {/* Menu Items */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden mb-4">
        {[
          { icon: 'person', label: '个人资料', path: '/profile' },
          { icon: 'notifications', label: '消息通知', path: '/m' },
          { icon: 'task_alt', label: '我的审批', path: '/m/approvals' },
          { icon: 'edit_note', label: '新建跟进', path: '/m/follow-up/new' },
          { icon: 'analytics', label: '数据分析', path: '/analytics' },
        ].map((item, i) => (
          <div
            key={item.label}
            onClick={() => navigate(item.path)}
            className={`flex items-center gap-3 px-4 py-3.5 cursor-pointer active:bg-slate-50 ${
              i > 0 ? 'border-t border-slate-50' : ''
            }`}
          >
            <span className="material-symbols-outlined text-slate-500" style={{ fontSize: 20 }}>{item.icon}</span>
            <span className="flex-1 text-sm font-medium text-slate-800">{item.label}</span>
            <span className="material-symbols-outlined text-slate-300" style={{ fontSize: 16 }}>chevron_right</span>
          </div>
        ))}
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-3.5 text-center text-sm font-bold text-red-500 cursor-pointer active:bg-red-50 transition-colors"
      >
        退出登录
      </button>
    </div>
  )
}
