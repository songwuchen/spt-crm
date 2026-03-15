import { useEffect, useState } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { t } from '@/locales'

export default function Login() {
  usePageTitle(t('auth.login'))
  const navigate = useNavigate()
  const { token, setAuth } = useAuthStore()
  const [form] = Form.useForm()
  const [needTotp, setNeedTotp] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token])

  const onFinish = async (values: { username: string; password: string; totp_code?: string }) => {
    setLoading(true)
    try {
      const res = await authApi.login(values)
      // Check if 2FA is required
      if (res.data && (res.data as any).requires_totp) {
        setNeedTotp(true)
        message.info('请输入二步验证码')
        return
      }
      setAuth(res.data.access_token, res.data.refresh_token)
      message.success('登录成功')
      navigate('/')
    } catch (err: unknown) {
      // Interceptor shows message.error for business errors;
      // catch here in case interceptor didn't display (e.g. network error)
      const msg = err instanceof Error ? err.message : '登录失败'
      if (!msg.includes('请求失败')) message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-96 shadow-lg">
        <h1 className="text-2xl font-bold text-center mb-6">{t('auth.loginTitle')}</h1>
        <p className="text-center text-gray-500 mb-8">{t('auth.loginSubtitle')}</p>
        <Form form={form} onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: t('auth.username') }]}>
            <Input prefix={<UserOutlined />} placeholder={t('auth.username')} disabled={needTotp} />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: t('auth.password') }]}>
            <Input.Password prefix={<LockOutlined />} placeholder={t('auth.password')} disabled={needTotp} />
          </Form.Item>
          {needTotp && (
            <Form.Item name="totp_code" rules={[{ required: true, message: '请输入验证码' }]}>
              <Input prefix={<SafetyOutlined />} placeholder="6位验证码" maxLength={6} autoFocus />
            </Form.Item>
          )}
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              {needTotp ? '验证' : t('auth.login')}
            </Button>
          </Form.Item>
          {needTotp && (
            <Button type="link" block onClick={() => { setNeedTotp(false); form.setFieldValue('totp_code', '') }}>
              返回登录
            </Button>
          )}
        </Form>
        <p className="text-center text-gray-400 text-xs mt-4">
          演示账号: admin / admin123
        </p>
      </Card>
    </div>
  )
}
