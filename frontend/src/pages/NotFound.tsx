import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function NotFound() {
  usePageTitle('页面不存在')
  const navigate = useNavigate()
  return (
    <Result
      status="404"
      title="404"
      subTitle="页面不存在"
      extra={<Button type="primary" onClick={() => navigate('/')}>返回首页</Button>}
    />
  )
}
