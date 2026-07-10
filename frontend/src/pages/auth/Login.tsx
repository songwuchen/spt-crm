import { useEffect, useState } from 'react'
import { Form, Input, Button, Card, message, Divider } from 'antd'
import { UserOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import { t } from '@/locales'
import { isDingTalkContainer, getDingTalkAuthCode } from '@/utils/dingtalk'

// DingTalk brand color
const DT_COLOR = '#1A7AF8'

function DingTalkIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm-.2 17.2c-.4.2-.9.1-1.2-.3L7.4 12.5c-.3-.4-.2-.9.2-1.2.4-.3.9-.2 1.2.2l2.4 3.2 4.8-6.4c.3-.4.8-.4 1.2-.1.4.3.4.8.1 1.2l-5.5 7.8z"/>
    </svg>
  )
}

export default function Login() {
  usePageTitle(t('auth.login'))
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { token, setAuth } = useAuthStore()
  const [form] = Form.useForm()
  const [needTotp, setNeedTotp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [dtConfig, setDtConfig] = useState<{ login_enabled: boolean; app_key: string; corp_id: string } | null>(null)
  const [dtLoading, setDtLoading] = useState(false)

  // Redirect if already logged in
  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token])

  // Load DingTalk SSO config
  useEffect(() => {
    authApi.dingtalkConfig()
      .then(res => setDtConfig(res.data))
      .catch(() => {/* silently ignore — no config */})
  }, [])

  // Handle OAuth callback: if ?code= is present in URL, exchange it
  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    if (!code) return

    // Validate state to prevent CSRF
    const savedState = sessionStorage.getItem('dt_oauth_state')
    if (savedState && state !== savedState) {
      message.error('钉钉登录状态验证失败，请重试')
      return
    }
    sessionStorage.removeItem('dt_oauth_state')

    // Exchange code for JWT
    setDtLoading(true)
    const redirectUri = `${window.location.origin}/login`
    authApi.dingtalkCallback({ code, redirect_uri: redirectUri, state: state ?? undefined })
      .then(res => {
        setAuth(res.data.access_token, res.data.refresh_token)
        message.success('钉钉登录成功')
        navigate('/', { replace: true })
      })
      .catch((err: any) => {
        const msg = err?.response?.data?.message || '钉钉登录失败，请使用账号密码登录'
        message.error(msg)
        // Clean up the ?code param so user can try password login
        navigate('/login', { replace: true })
      })
      .finally(() => setDtLoading(false))
  }, [searchParams])

  // 钉钉容器内自动免登：无需扫码/密码，静默用 requestAuthCode 换取 CRM token。
  // 失败则静默回退到账号密码表单。
  useEffect(() => {
    if (!dtConfig?.login_enabled || !dtConfig.corp_id) return
    if (!isDingTalkContainer()) return
    if (searchParams.get('code')) return // 走 OAuth 回调分支，不重复触发
    if (token) return

    setDtLoading(true)
    getDingTalkAuthCode(dtConfig.corp_id)
      .then((authCode) => authApi.dingtalkJsapiLogin({ auth_code: authCode, corp_id: dtConfig.corp_id }))
      .then((res) => {
        setAuth(res.data.access_token, res.data.refresh_token)
        navigate('/', { replace: true })
      })
      .catch(() => { /* 免登失败静默回退，用户可用账号密码登录 */ })
      .finally(() => setDtLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dtConfig])

  const handleDingTalkLogin = () => {
    if (!dtConfig?.app_key) return
    const state = Math.random().toString(36).slice(2) + Date.now().toString(36)
    sessionStorage.setItem('dt_oauth_state', state)
    const redirectUri = encodeURIComponent(`${window.location.origin}/login`)
    const url = `https://login.dingtalk.com/oauth2/auth?response_type=code&client_id=${dtConfig.app_key}&redirect_uri=${redirectUri}&scope=openid&state=${state}&prompt=consent`
    window.location.href = url
  }

  const onFinish = async (values: { username: string; password: string; totp_code?: string }) => {
    setLoading(true)
    try {
      const res = await authApi.login(values)
      if (res.data && (res.data as any).requires_totp) {
        setNeedTotp(true)
        message.info('请输入二步验证码')
        return
      }
      setAuth(res.data.access_token, res.data.refresh_token)
      message.success('登录成功')
      navigate('/')
    } catch {
      // 错误提示由 client.ts 响应拦截器统一弹出（如"用户名或密码错误"），
      // 此处不再二次弹出，避免叠加 axios 的英文 "Request failed with status code 401"。
    } finally {
      setLoading(false)
    }
  }

  // If we're processing a DingTalk callback, show a loading state
  if (dtLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <Card className="w-80 shadow-lg text-center">
          <div className="py-6">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: DT_COLOR }}>
              <DingTalkIcon />
            </div>
            <p className="text-gray-600 font-medium">正在验证钉钉身份...</p>
            <p className="text-gray-400 text-sm mt-1">请稍候</p>
          </div>
        </Card>
      </div>
    )
  }

  const showDingTalk = dtConfig?.login_enabled && dtConfig?.app_key

  return (
    <div className="h-screen flex items-center justify-center bg-gray-50">
      <Card className="w-96 shadow-lg">
        <div className="flex justify-center mb-4">
          <img src="/logo.png" alt="SPT-CRM" className="w-20 h-20 rounded-2xl" />
        </div>
        <h1 className="text-2xl font-bold text-center mb-2">{t('auth.loginTitle')}</h1>
        <p className="text-center text-gray-500 mb-6">{t('auth.loginSubtitle')}</p>

        {/* DingTalk SSO Button */}
        {showDingTalk && (
          <>
            <Button
              block
              size="large"
              onClick={handleDingTalkLogin}
              style={{ borderColor: DT_COLOR, color: DT_COLOR, fontWeight: 600 }}
              icon={<DingTalkIcon />}
            >
              钉钉一键登录
            </Button>
            <Divider plain className="text-gray-400 text-sm">或使用账号密码登录</Divider>
          </>
        )}

        {/* Username / Password Form */}
        <Form form={form} onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: t('auth.loginAccount') }]}>
            <Input prefix={<UserOutlined />} placeholder={t('auth.loginAccount')} disabled={needTotp} />
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
      </Card>
    </div>
  )
}
