import { useState, useEffect } from 'react'
import { Button, message, Tooltip } from 'antd'
import client from '@/api/client'

import Icon from '@/components/Icon'
interface SubscribeButtonProps {
  bizType: string
  bizId: string
  bizName?: string
}

export default function SubscribeButton({ bizType, bizId, bizName }: SubscribeButtonProps) {
  const [subscribed, setSubscribed] = useState(false)
  const [subId, setSubId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    client.get('/api/v1/data_subscriptions', { params: { biz_type: bizType, biz_id: bizId } })
      .then((r: any) => {
        const subs = r.data || []
        if (subs.length > 0) {
          setSubscribed(true)
          setSubId(subs[0].id)
        }
      })
      .catch(() => {})
  }, [bizType, bizId])

  const toggle = async () => {
    setLoading(true)
    try {
      if (subscribed && subId) {
        await client.delete(`/api/v1/data_subscriptions/${subId}`)
        setSubscribed(false)
        setSubId(null)
        message.success('已取消关注')
      } else {
        const r = await client.post('/api/v1/data_subscriptions', {
          biz_type: bizType, biz_id: bizId, biz_name: bizName,
          events_json: ['update', 'status_change', 'comment'],
        }) as any
        setSubscribed(true)
        setSubId(r.data?.id || null)
        message.success('已关注，变更时将收到通知')
      }
    } catch {
      message.error('操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Tooltip title={subscribed ? '取消关注此记录的变更通知' : '关注此记录，变更时收到通知'}>
      <Button
        size="small"
        loading={loading}
        onClick={toggle}
        type={subscribed ? 'primary' : 'default'}
        ghost={subscribed}
      >
        <Icon name={subscribed ? 'notifications_active' : 'notifications_none'} className="text-sm mr-1" style={{ fontSize: 14 }} />
        {subscribed ? '已关注' : '关注'}
      </Button>
    </Tooltip>
  )
}
