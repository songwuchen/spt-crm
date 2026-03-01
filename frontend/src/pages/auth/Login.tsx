import { useEffect } from 'react'
import { Form, Input, Button, Card, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function Login() {
  usePageTitle('登录')
  const navigate = useNavigate()
  const { token, setAuth } = useAuthStore()
  const [form] = Form.useForm()

  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token])

  const onFinish = async (values: { username: string; password: string }) => {
    try {
      const res = await authApi.login(values)
      setAuth(res.data.access_token, res.data.refresh_token)
      message.success('登录成功')
      navigate('/')
    } catch {
      // Error handled by interceptor
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-96 shadow-lg">
        <h1 className="text-2xl font-bold text-center mb-6">SPT-CRM</h1>
        <p className="text-center text-gray-500 mb-8">离散制造业 CRM + AI 平台</p>
        <Form form={form} onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              登录
            </Button>
          </Form.Item>
        </Form>
        <p className="text-center text-gray-400 text-xs mt-4">
          演示账号: admin / admin123
        </p>
      </Card>
    </div>
  )
}
