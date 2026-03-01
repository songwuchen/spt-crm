import { Button, Result } from 'antd'
import { useNavigate } from 'react-router-dom'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function NoPermission() {
  usePageTitle('无权限')
  const navigate = useNavigate()
  return (
    <Result
      status="403"
      title="403"
      subTitle="抱歉，您没有权限访问此页面"
      extra={<Button type="primary" onClick={() => navigate('/')}>返回首页</Button>}
    />
  )
}
