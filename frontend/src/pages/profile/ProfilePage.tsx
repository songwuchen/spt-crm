import { useState } from 'react'
import { Button, Form, Input, Avatar, message, Divider } from 'antd'
import { UserOutlined, LockOutlined, SaveOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/useAuthStore'
import { authApi } from '@/api/auth'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function ProfilePage() {
  usePageTitle('个人中心')
  const { user, setUser } = useAuthStore()
  const [profileForm] = Form.useForm()
  const [pwdForm] = Form.useForm()
  const [profileLoading, setProfileLoading] = useState(false)
  const [pwdLoading, setPwdLoading] = useState(false)

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
      message.success('密码修改成功')
      pwdForm.resetFields()
    } finally {
      setPwdLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">个人中心</h1>
        <p className="text-sm text-slate-500 mt-1">管理个人信息和账户安全</p>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Left: Avatar + Info */}
        <div className="col-span-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 text-center">
            <Avatar size={80} icon={<UserOutlined />} className="bg-primary/10 text-primary border-4 border-white shadow-lg mb-4" />
            <h2 className="text-xl font-bold text-slate-900">{user?.real_name || user?.username}</h2>
            <p className="text-sm text-slate-500 mt-1">@{user?.username}</p>
            <div className="flex justify-center gap-2 mt-3">
              {user?.roles?.map((r) => (
                <span key={r} className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-bold">{r}</span>
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
                <span className="font-mono text-xs text-slate-400">{user?.tenant_id}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Forms */}
        <div className="col-span-8 space-y-6">
          {/* Profile Edit */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <UserOutlined /> 基本信息
            </h3>
            <Form form={profileForm} layout="vertical" initialValues={{ real_name: user?.real_name, phone: user?.phone, email: user?.email }}>
              <div className="grid grid-cols-2 gap-4">
                <Form.Item name="real_name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
                  <Input placeholder="请输入姓名" />
                </Form.Item>
                <Form.Item name="phone" label="手机号">
                  <Input placeholder="请输入手机号" />
                </Form.Item>
              </div>
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

          {/* Password Change */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <LockOutlined /> 修改密码
            </h3>
            <Form form={pwdForm} layout="vertical">
              <Form.Item name="old_password" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
                <Input.Password placeholder="请输入当前密码" />
              </Form.Item>
              <div className="grid grid-cols-2 gap-4">
                <Form.Item name="new_password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少6位' }]}>
                  <Input.Password placeholder="请输入新密码" />
                </Form.Item>
                <Form.Item name="confirm_password" label="确认新密码" rules={[{ required: true, message: '请确认新密码' }]}>
                  <Input.Password placeholder="再次输入新密码" />
                </Form.Item>
              </div>
              <div className="flex justify-end">
                <Button type="primary" danger icon={<LockOutlined />} loading={pwdLoading} onClick={handlePasswordChange}>
                  修改密码
                </Button>
              </div>
            </Form>
          </div>
        </div>
      </div>
    </div>
  )
}
