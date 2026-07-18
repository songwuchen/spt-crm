import { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Button, Input, Typography, Alert, Statistic, Space, Modal, message, Tag } from 'antd'
import { ExclamationCircleOutlined, DeleteOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons'
import client from '@/api/client'
import { usePageTitle } from '@/hooks/usePageTitle'

import Icon from '@/components/Icon'
const { Title, Text, Paragraph } = Typography

interface PurgeStatus {
  status: 'idle' | 'scheduled' | 'executing' | 'completed' | 'cancelled' | 'failed'
  task_id?: string
  scheduled_at?: string
  execute_at?: string
  delay_seconds?: number
  completed_at?: string
  deleted_counts?: Record<string, number>
  error?: string
}

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  idle: { color: 'default', label: '空闲' },
  scheduled: { color: 'processing', label: '已计划' },
  executing: { color: 'warning', label: '执行中' },
  completed: { color: 'success', label: '已完成' },
  cancelled: { color: 'default', label: '已取消' },
  failed: { color: 'error', label: '失败' },
}

export default function DataManagePage() {
  usePageTitle('数据管理')

  const [purgeStatus, setPurgeStatus] = useState<PurgeStatus>({ status: 'idle' })
  const [confirmText, setConfirmText] = useState('')
  const [loading, setLoading] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await client.get('/api/admin/v1/tenant/customers/purge/status') as any
      const data: PurgeStatus = res.data
      setPurgeStatus(data)

      // Update countdown if scheduled
      if (data.status === 'scheduled' && data.execute_at) {
        const remaining = Math.max(0, Math.floor(
          (new Date(data.execute_at).getTime() - Date.now()) / 1000
        ))
        setCountdown(remaining)
      } else {
        setCountdown(0)
      }

      // Stop polling if terminal state
      if (data.status === 'completed' || data.status === 'cancelled' || data.status === 'failed') {
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      }
    } catch {
      // ignore poll errors
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [fetchStatus])

  // Countdown timer
  useEffect(() => {
    if (countdownRef.current) clearInterval(countdownRef.current)
    if (purgeStatus.status === 'scheduled' && countdown > 0) {
      countdownRef.current = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            if (countdownRef.current) clearInterval(countdownRef.current)
            fetchStatus()
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [purgeStatus.status, countdown > 0]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSchedulePurge = () => {
    if (confirmText !== '确认清空') {
      message.warning('请输入"确认清空"以继续')
      return
    }

    Modal.confirm({
      title: '最终确认',
      icon: <ExclamationCircleOutlined />,
      content: (
        <div>
          <Paragraph type="danger" strong>
            此操作将在 5 分钟后永久删除当前租户下的所有客户数据及关联数据（联系人、商机、报价、合同、回款等），且不可恢复！
          </Paragraph>
          <Paragraph>在倒计时结束前，您可以随时取消此操作。</Paragraph>
        </div>
      ),
      okText: '确认计划清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setLoading(true)
        try {
          const res = await client.post('/api/admin/v1/tenant/customers/purge', {
            delay_seconds: 300,
          }) as any
          message.success('清空任务已计划，5 分钟后执行')
          setPurgeStatus({
            status: 'scheduled',
            task_id: res.data.task_id,
            scheduled_at: res.data.scheduled_at,
            execute_at: res.data.execute_at,
            delay_seconds: res.data.delay_seconds,
          })
          setCountdown(300)
          setConfirmText('')

          // Start polling
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = setInterval(fetchStatus, 5000)
        } catch (err: any) {
          message.error(err?.response?.data?.message || '操作失败')
        } finally {
          setLoading(false)
        }
      },
    })
  }

  const handleCancel = async () => {
    setLoading(true)
    try {
      await client.post('/api/admin/v1/tenant/customers/purge/cancel')
      message.success('清空任务已取消')
      setPurgeStatus({ status: 'cancelled' })
      setCountdown(0)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    } catch (err: any) {
      message.error(err?.response?.data?.message || '取消失败')
    } finally {
      setLoading(false)
    }
  }

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const statusInfo = STATUS_MAP[purgeStatus.status] || STATUS_MAP.idle

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <Title level={3}>
        <Icon name="delete_sweep" className="align-middle mr-2" style={{ fontSize: 28 }} />
        数据管理
      </Title>
      <Paragraph type="secondary">管理租户数据的清理与维护操作。</Paragraph>

      <Card
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
            <span style={{ color: '#ff4d4f' }}>危险操作区</span>
          </Space>
        }
        style={{ borderColor: '#ff4d4f' }}
      >
        <Title level={5}>清空所有客户数据</Title>
        <Paragraph type="secondary">
          此操作将永久删除当前租户下的所有客户及关联数据，包括：联系人、商机项目、报价单、合同、
          方案、交付里程碑、回款计划、发票、收款记录、变更请求、售后工单、续约机会、ACL 共享、
          客户关系和相关活动记录。
        </Paragraph>

        <Alert
          type="warning"
          showIcon
          message="此操作不可恢复"
          description="建议在执行前先通过「系统配置 → 数据备份」功能导出数据备份。"
          className="mb-4"
        />

        {/* Current Status */}
        <div className="mb-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <Space size="large">
            <div>
              <Text type="secondary">当前状态：</Text>
              <Tag color={statusInfo.color}>{statusInfo.label}</Tag>
            </div>
            {purgeStatus.status === 'scheduled' && countdown > 0 && (
              <Statistic
                title="剩余时间"
                value={formatCountdown(countdown)}
                valueStyle={{ color: '#ff4d4f', fontSize: 24 }}
              />
            )}
            {purgeStatus.status === 'executing' && (
              <Text type="warning">正在执行数据清理，请勿关闭页面...</Text>
            )}
          </Space>

          {purgeStatus.status === 'completed' && purgeStatus.deleted_counts && (
            <div className="mt-3">
              <Text strong>清理结果：</Text>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {Object.entries(purgeStatus.deleted_counts).map(([key, count]) => (
                  <div key={key} className="text-sm">
                    <Text type="secondary">{key}:</Text> <Text strong>{count}</Text>
                  </div>
                ))}
              </div>
            </div>
          )}

          {purgeStatus.status === 'failed' && purgeStatus.error && (
            <Alert type="error" message="执行失败" description={purgeStatus.error} className="mt-3" />
          )}
        </div>

        {/* Action Area */}
        {purgeStatus.status === 'scheduled' ? (
          <Button
            danger
            icon={<StopOutlined />}
            onClick={handleCancel}
            loading={loading}
            size="large"
          >
            取消清空任务
          </Button>
        ) : purgeStatus.status === 'executing' ? (
          <Button disabled size="large">
            正在执行中...
          </Button>
        ) : (
          <Space direction="vertical" className="w-full" size="middle">
            <div>
              <Text>请输入 <Text strong code>确认清空</Text> 以启用操作按钮：</Text>
              <Input
                className="mt-2"
                placeholder="请输入：确认清空"
                value={confirmText}
                onChange={e => setConfirmText(e.target.value)}
                style={{ maxWidth: 300 }}
              />
            </div>
            <Button
              danger
              type="primary"
              icon={<DeleteOutlined />}
              disabled={confirmText !== '确认清空'}
              onClick={handleSchedulePurge}
              loading={loading}
              size="large"
            >
              计划清空全部客户数据（5 分钟延迟）
            </Button>
          </Space>
        )}

        {purgeStatus.status === 'completed' && (
          <div className="mt-4">
            <Button
              icon={<CheckCircleOutlined />}
              onClick={() => {
                setPurgeStatus({ status: 'idle' })
                setConfirmText('')
              }}
            >
              确认并重置
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
