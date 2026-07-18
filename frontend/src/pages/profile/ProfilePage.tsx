import { useState, useEffect } from 'react'
import { Button, Form, Input, Avatar, Switch, message, Divider, Modal, QRCode } from 'antd'
import { UserOutlined, LockOutlined, SaveOutlined, DeleteOutlined, LaptopOutlined, SafetyOutlined, BellOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/useAuthStore'
import { authApi } from '@/api/auth'
import client from '@/api/client'
import type { SessionItem } from '@/api/auth'
import { usePageTitle } from '@/hooks/usePageTitle'

import Icon from '@/components/Icon'
const deviceIcons: Record<string, { icon: string; label: string }> = {
  desktop: { icon: 'computer', label: '桌面端' },
  mobile: { icon: 'smartphone', label: '移动端' },
  tablet: { icon: 'tablet', label: '平板' },
}

export default function ProfilePage() {
  usePageTitle('个人中心')
  const { user, setUser } = useAuthStore()
  const [profileForm] = Form.useForm()
  const [pwdForm] = Form.useForm()
  const [profileLoading, setProfileLoading] = useState(false)
  const [pwdLoading, setPwdLoading] = useState(false)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [totpEnabled, setTotpEnabled] = useState(false)
  const [totpSetupData, setTotpSetupData] = useState<{ secret: string; uri: string } | null>(null)
  const [totpCode, setTotpCode] = useState('')
  const [totpLoading, setTotpLoading] = useState(false)
  const [disablePwd, setDisablePwd] = useState('')
  const [notifTypes, setNotifTypes] = useState<{ key: string; label: string }[]>([])
  const [notifPrefs, setNotifPrefs] = useState<Record<string, boolean>>({})
  const [notifSaving, setNotifSaving] = useState(false)

  const fetchNotifPrefs = async () => {
    try {
      const res = await client.get('/api/v1/notifications/preferences') as any
      const data = res.data || {}
      setNotifTypes((data.types || []).map((t: any) => typeof t === 'string' ? { key: t, label: t } : t))
      setNotifPrefs(data.preferences || {})
    } catch { /* ignore */ }
  }

  const handleNotifToggle = async (key: string, checked: boolean) => {
    const updated = { ...notifPrefs, [key]: checked }
    setNotifPrefs(updated)
    setNotifSaving(true)
    try {
      await client.put('/api/v1/notifications/preferences', { preferences: updated })
    } catch {
      message.error('保存通知偏好失败')
      setNotifPrefs(notifPrefs) // revert
    } finally {
      setNotifSaving(false)
    }
  }

  const fetchSessions = async () => {
    setSessionsLoading(true)
    try {
      const res = await authApi.sessions()
      setSessions(res.data || [])
    } catch { /* ignore */ }
    finally { setSessionsLoading(false) }
  }

  const fetchTotpStatus = async () => {
    try {
      const res = await authApi.totpStatus()
      setTotpEnabled(res.data?.enabled || false)
    } catch {}
  }

  useEffect(() => { fetchSessions(); fetchTotpStatus(); fetchNotifPrefs() }, [])

  const handleProfileSave = async () => {
    const values = await profileForm.validateFields()
    setProfileLoading(true)
    try {
      await authApi.updateProfile(values)
      if (user) {
        const res = await authApi.me()
        if (res.data) setUser(res.data)
      }
      message.success('个人信息已更新')
    } finally {
      setProfileLoading(false)
    }
  }

  const handlePasswordChange = async () => {
    const values = await pwdForm.validateFields()
    if (values.new_password !== values.confirm_password) {
      message.error('两次密码不一致')
      return
    }
    setPwdLoading(true)
    try {
      await authApi.changePassword({ old_password: values.old_password, new_password: values.new_password })
      message.success('密码修改成功，其他设备已自动下线')
      pwdForm.resetFields()
      fetchSessions()
    } finally {
      setPwdLoading(false)
    }
  }

  const handleRevokeSession = (id: string) => {
    Modal.confirm({
      title: '撤销会话',
      content: '确定要下线该设备吗？',
      okType: 'danger',
      onOk: async () => {
        await authApi.revokeSession(id)
        message.success('已撤销')
        fetchSessions()
      },
    })
  }

  const handleRevokeAll = () => {
    Modal.confirm({
      title: '下线所有其他设备',
      content: '确定要下线除当前设备外的所有设备吗？',
      okType: 'danger',
      onOk: async () => {
        const res = await authApi.revokeAllSessions()
        message.success(`已撤销 ${(res.data as any)?.revoked || 0} 个会话`)
        fetchSessions()
      },
    })
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">个人中心</h1>
        <p className="text-sm text-slate-500 mt-1">管理个人信息和账户安全</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left column: identity card + 高频自助 */}
        <div className="lg:col-span-5 space-y-6">
          {/* Identity card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 text-center">
            <Avatar size={80} icon={<UserOutlined />} className="bg-primary/10 text-primary border-4 border-white shadow-lg mb-4" />
            <h2 className="text-xl font-bold text-slate-900">{user?.real_name || user?.username}</h2>
            <p className="text-sm text-slate-500 mt-1">@{user?.username}</p>
            <div className="flex justify-center gap-2 mt-3 flex-wrap">
              {user?.roles?.map((r) => (
                <span key={r} className="px-2 py-0.5 rounded bg-primary/10 text-primary text-sm font-bold">{r}</span>
              ))}
            </div>
            <Divider className="my-4" />
            <div className="text-left space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">手机</span>
                <span className="font-medium text-slate-700">{user?.phone || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">邮箱</span>
                <span className="font-medium text-slate-700">{user?.email || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">租户ID</span>
                <span className="font-mono text-sm text-slate-400 truncate ml-2 max-w-[160px]">{user?.tenant_id}</span>
              </div>
            </div>
          </div>

          {/* Profile Edit */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <UserOutlined /> 基本信息
            </h3>
            <Form form={profileForm} layout="vertical" initialValues={{ real_name: user?.real_name, phone: user?.phone, email: user?.email }}>
              <Form.Item name="real_name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
                <Input placeholder="请输入姓名" />
              </Form.Item>
              <Form.Item name="phone" label="手机号">
                <Input placeholder="请输入手机号" />
              </Form.Item>
              <Form.Item name="email" label="邮箱">
                <Input placeholder="请输入邮箱" />
              </Form.Item>
              <div className="flex justify-end">
                <Button type="primary" icon={<SaveOutlined />} loading={profileLoading} onClick={handleProfileSave}>
                  保存修改
                </Button>
              </div>
            </Form>
          </div>

          {/* Password Change — moved up so it's visible without scrolling */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <LockOutlined /> 修改密码
            </h3>
            <Form form={pwdForm} layout="vertical">
              <Form.Item name="old_password" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
                <Input.Password placeholder="请输入当前密码" />
              </Form.Item>
              <Form.Item name="new_password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 8, message: '密码至少8位' }]}>
                <Input.Password placeholder="请输入新密码" />
              </Form.Item>
              <Form.Item name="confirm_password" label="确认新密码" rules={[{ required: true, message: '请确认新密码' }]}>
                <Input.Password placeholder="再次输入新密码" />
              </Form.Item>
              <p className="text-sm text-slate-400 mb-3">密码需包含大小写字母和数字，修改后其他设备将自动下线</p>
              <div className="flex justify-end">
                <Button type="primary" danger icon={<LockOutlined />} loading={pwdLoading} onClick={handlePasswordChange}>
                  修改密码
                </Button>
              </div>
            </Form>
          </div>
        </div>

        {/* Right column: 安全 + 通知 */}
        <div className="lg:col-span-7 space-y-6">
          {/* 2FA Setup */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <SafetyOutlined /> 二步验证 (2FA)
              </h3>
              <span className={`px-2 py-0.5 rounded text-sm font-bold ${totpEnabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                {totpEnabled ? '已启用' : '未启用'}
              </span>
            </div>
            {!totpEnabled && !totpSetupData && (
              <div>
                <p className="text-sm text-slate-500 mb-3">启用二步验证后，登录时需要输入 Google Authenticator 等应用生成的验证码</p>
                <Button onClick={async () => {
                  setTotpLoading(true)
                  try {
                    const res = await authApi.totpSetup()
                    setTotpSetupData(res.data)
                  } finally { setTotpLoading(false) }
                }} loading={totpLoading}>开始设置</Button>
              </div>
            )}
            {!totpEnabled && totpSetupData && (
              <div>
                <p className="text-sm text-slate-500 mb-3">使用 Google Authenticator 扫描二维码，然后输入6位验证码确认</p>
                <div className="flex items-start gap-6 flex-wrap">
                  <div className="bg-white p-2 rounded-lg border border-slate-200">
                    <QRCode value={totpSetupData.uri} size={160} />
                  </div>
                  <div className="flex-1 min-w-[220px]">
                    <p className="text-sm text-slate-400 mb-1">手动输入密钥：</p>
                    <code className="text-sm bg-slate-50 px-2 py-1 rounded border break-all">{totpSetupData.secret}</code>
                    <div className="mt-4 flex gap-2 flex-wrap">
                      <Input value={totpCode} onChange={(e) => setTotpCode(e.target.value)}
                        placeholder="6位验证码" maxLength={6} style={{ width: 140 }} />
                      <Button type="primary" loading={totpLoading} onClick={async () => {
                        if (!totpCode || totpCode.length !== 6) { message.warning('请输入6位验证码'); return }
                        setTotpLoading(true)
                        try {
                          await authApi.totpEnable(totpCode)
                          message.success('二步验证已启用')
                          setTotpEnabled(true)
                          setTotpSetupData(null)
                          setTotpCode('')
                        } finally { setTotpLoading(false) }
                      }}>验证并启用</Button>
                      <Button onClick={() => { setTotpSetupData(null); setTotpCode('') }}>取消</Button>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {totpEnabled && (
              <div>
                <p className="text-sm text-slate-500 mb-3">二步验证已启用。禁用需要输入密码确认。</p>
                <div className="flex gap-2 items-end flex-wrap">
                  <Input.Password value={disablePwd} onChange={(e) => setDisablePwd(e.target.value)}
                    placeholder="输入密码确认" style={{ width: 200 }} />
                  <Button danger loading={totpLoading} onClick={async () => {
                    if (!disablePwd) { message.warning('请输入密码'); return }
                    setTotpLoading(true)
                    try {
                      await authApi.totpDisable(disablePwd)
                      message.success('二步验证已禁用')
                      setTotpEnabled(false)
                      setDisablePwd('')
                    } finally { setTotpLoading(false) }
                  }}>禁用二步验证</Button>
                </div>
              </div>
            )}
          </div>

          {/* Active Sessions */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <LaptopOutlined /> 登录设备
              </h3>
              {sessions.length > 1 && (
                <Button size="small" danger onClick={handleRevokeAll}>下线其他设备</Button>
              )}
            </div>
            {sessionsLoading ? (
              <div className="text-center text-slate-400 text-sm py-4">加载中...</div>
            ) : sessions.length === 0 ? (
              <div className="text-center text-slate-400 text-sm py-4">暂无活跃会话</div>
            ) : (
              <div className="space-y-2">
                {sessions.map((s) => {
                  const dev = deviceIcons[s.device_type] || deviceIcons.desktop
                  return (
                    <div key={s.id} className={`flex items-center gap-3 p-3 rounded-lg border ${
                      s.is_current ? 'bg-primary/5 border-primary/20' : 'bg-slate-50 border-slate-100'
                    }`}>
                      <Icon name={dev.icon} className="text-xl text-slate-500" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-800">{dev.label}</span>
                          {s.is_current && (
                            <span className="px-1.5 py-0.5 rounded text-[12px] font-bold bg-emerald-100 text-emerald-700">当前</span>
                          )}
                        </div>
                        <div className="text-sm text-slate-400 truncate">
                          IP: {s.ip || '-'} · {s.last_active_at ? new Date(s.last_active_at).toLocaleString('zh-CN') : '-'}
                        </div>
                      </div>
                      {!s.is_current && (
                        <Button size="small" danger icon={<DeleteOutlined />}
                          onClick={() => handleRevokeSession(s.id)}>
                          下线
                        </Button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Notification Preferences */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <BellOutlined /> 通知偏好
            </h3>
            <p className="text-sm text-slate-500 mb-4">选择您希望接收的通知类型</p>
            {notifTypes.length === 0 ? (
              <div className="text-sm text-slate-400">加载中...</div>
            ) : (
              <div className="space-y-3">
                {notifTypes.map((t) => {
                  const typeLabels: Record<string, string> = {
                    approval_pending: '待审批通知',
                    approval_decided: '审批结果通知',
                    stage_change: '阶段变更通知',
                    payment_overdue: '回款逾期提醒',
                    ai_task_complete: 'AI 任务完成',
                    gate_blocked: '阶段门禁阻断',
                    system: '系统通知',
                    contract_expiry: '合同到期提醒',
                  }
                  return (
                    <div key={t.key} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                      <div>
                        <div className="text-sm font-medium text-slate-700">{typeLabels[t.key] || t.label || t.key}</div>
                      </div>
                      <Switch
                        checked={notifPrefs[t.key] !== false}
                        onChange={(checked) => handleNotifToggle(t.key, checked)}
                        loading={notifSaving}
                      />
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
