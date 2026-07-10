import { useState } from 'react'
import MobileIcon from '@/components/MobileIcon'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import client from '@/api/client'

export default function MobileProfile() {
  usePageTitle('我的')
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const [pwdModal, setPwdModal] = useState(false)
  const [pwdForm, setPwdForm] = useState({ old_password: '', new_password: '', confirm: '' })
  const [pwdLoading, setPwdLoading] = useState(false)
  const [pwdError, setPwdError] = useState('')

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleChangePassword = async () => {
    setPwdError('')
    if (!pwdForm.old_password || !pwdForm.new_password) {
      setPwdError('请填写完整'); return
    }
    if (pwdForm.new_password.length < 8) {
      setPwdError('新密码不能少于8位'); return
    }
    if (pwdForm.new_password !== pwdForm.confirm) {
      setPwdError('两次密码不一致'); return
    }
    setPwdLoading(true)
    try {
      await client.post('/api/v1/auth/change-password', {
        old_password: pwdForm.old_password,
        new_password: pwdForm.new_password,
      })
      setPwdModal(false)
      setPwdForm({ old_password: '', new_password: '', confirm: '' })
      alert('密码修改成功，请重新登录')
      handleLogout()
    } catch (e: any) {
      setPwdError(e?.response?.data?.message || e?.message || '修改失败')
    } finally {
      setPwdLoading(false)
    }
  }

  const menuItems = [
    { icon: 'lock', label: '修改密码', action: () => setPwdModal(true) },
    { icon: 'notifications', label: '消息通知', path: '/m' },
    { icon: 'task_alt', label: '我的审批', path: '/m/approvals' },
    { icon: 'edit_note', label: '新建跟进', path: '/m/follow-up/new' },
    { icon: 'description', label: '合同列表', path: '/m/contracts' },
    { icon: 'analytics', label: '数据分析', path: '/analytics' },
  ]

  return (
    <div>
      {/* User Card */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-4 mb-4">
        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center text-xl font-black text-primary">
          {(user?.real_name || user?.username || 'U').slice(0, 1)}
        </div>
        <div className="flex-1">
          <div className="text-lg font-extrabold text-slate-900">{user?.real_name || user?.username}</div>
          <div className="text-sm text-slate-500">{user?.roles?.join(', ') || '-'}</div>
        </div>
      </div>

      {/* Menu Items */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden mb-4">
        {menuItems.map((item, i) => (
          <div
            key={item.label}
            onClick={() => item.action ? item.action() : item.path && navigate(item.path)}
            className={`flex items-center gap-3 px-4 py-3.5 cursor-pointer active:bg-slate-50 ${
              i > 0 ? 'border-t border-slate-50' : ''
            }`}
          >
            <MobileIcon name={item.icon} className="text-slate-500" style={{ fontSize: 20 }} />
            <span className="flex-1 text-sm font-medium text-slate-800">{item.label}</span>
            <MobileIcon name="chevron_right" className="text-slate-300" style={{ fontSize: 16 }} />
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

      {/* Password Change Modal */}
      {pwdModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end justify-center" onClick={() => setPwdModal(false)}>
          <div className="bg-white w-full max-w-lg rounded-t-2xl p-6 pb-8" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-extrabold text-slate-900">修改密码</h3>
              <button onClick={() => setPwdModal(false)} className="text-slate-400">
                <MobileIcon name="close" style={{ fontSize: 22 }} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-bold text-slate-500 mb-1 block">原密码</label>
                <input type="password" className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  value={pwdForm.old_password} onChange={e => setPwdForm({ ...pwdForm, old_password: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-500 mb-1 block">新密码</label>
                <input type="password" className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="至少8位，含大小写字母和数字"
                  value={pwdForm.new_password} onChange={e => setPwdForm({ ...pwdForm, new_password: e.target.value })} />
              </div>
              <div>
                <label className="text-sm font-bold text-slate-500 mb-1 block">确认新密码</label>
                <input type="password" className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  value={pwdForm.confirm} onChange={e => setPwdForm({ ...pwdForm, confirm: e.target.value })} />
              </div>
              {pwdError && <div className="text-sm text-red-500 font-medium">{pwdError}</div>}
              <button
                onClick={handleChangePassword}
                disabled={pwdLoading}
                className="w-full bg-primary text-white font-bold text-sm py-3 rounded-lg active:opacity-80 disabled:opacity-50"
              >
                {pwdLoading ? '提交中...' : '确认修改'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
