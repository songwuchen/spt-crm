import { useState, useEffect } from 'react'
import { Card, Statistic, Row, Col, Tag, Button, Spin, Progress, message } from 'antd'
import { ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import client from '@/api/client'
import { usePageTitle } from '@/hooks/usePageTitle'

interface HealthData {
  db: {
    ok: boolean
    latency_ms: number
    pool: { pool_size: number; checked_out: number; overflow: number; checked_in: number }
  }
  table_counts: Record<string, number>
  api: { total_ops_24h: number }
  timestamp: string
}

const TABLE_LABELS: Record<string, string> = {
  customers: '客户', leads: '线索', projects: '商机', notifications: '通知',
}

export default function SystemHealthPage() {
  usePageTitle('系统健康')
  const [data, setData] = useState<HealthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const fetchHealth = async () => {
    setLoading(true)
    try {
      const res = await client.get('/api/admin/v1/system/health') as any
      setData(res.data)
      setLastRefresh(new Date())
    } catch {
      message.error('获取健康信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchHealth() }, [])

  // Auto-refresh every 30s
  useEffect(() => {
    const timer = setInterval(fetchHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !data) return <div className="flex justify-center py-20"><Spin size="large" /></div>

  const pool = data?.db.pool
  const poolUsage = pool ? Math.round((pool.checked_out / Math.max(pool.pool_size + pool.overflow, 1)) * 100) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">系统健康监控</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            数据库、连接池、API 运行状态
            {lastRefresh && <span className="ml-2 text-slate-400">刷新于 {lastRefresh.toLocaleTimeString('zh-CN')}</span>}
          </p>
        </div>
        <Button icon={<ReloadOutlined />} onClick={fetchHealth} loading={loading}>刷新</Button>
      </div>

      {data && (
        <>
          {/* Status Cards */}
          <Row gutter={16} className="mb-6">
            <Col span={6}>
              <Card>
                <Statistic
                  title="数据库状态"
                  value={data.db.ok ? '正常' : '异常'}
                  prefix={data.db.ok ? <CheckCircleOutlined className="text-emerald-500" /> : <CloseCircleOutlined className="text-red-500" />}
                  valueStyle={{ color: data.db.ok ? '#10b981' : '#ef4444' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="DB 延迟" value={data.db.latency_ms} suffix="ms" precision={1}
                  valueStyle={{ color: data.db.latency_ms < 50 ? '#10b981' : data.db.latency_ms < 200 ? '#f59e0b' : '#ef4444' }} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="24h 操作数" value={data.api.total_ops_24h} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="连接池使用率" value={poolUsage} suffix="%" precision={0}
                  valueStyle={{ color: poolUsage < 60 ? '#10b981' : poolUsage < 85 ? '#f59e0b' : '#ef4444' }} />
              </Card>
            </Col>
          </Row>

          {/* Connection Pool Detail */}
          {pool && (
            <Card title="数据库连接池" className="mb-6" size="small">
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-black text-slate-900">{pool.pool_size}</div>
                  <div className="text-sm text-slate-500">池大小</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-black text-blue-600">{pool.checked_out}</div>
                  <div className="text-sm text-slate-500">使用中</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-black text-emerald-600">{pool.checked_in}</div>
                  <div className="text-sm text-slate-500">空闲</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-black text-amber-600">{pool.overflow}</div>
                  <div className="text-sm text-slate-500">溢出</div>
                </div>
              </div>
              <Progress percent={poolUsage} strokeColor={poolUsage < 60 ? '#10b981' : poolUsage < 85 ? '#f59e0b' : '#ef4444'} />
            </Card>
          )}

          {/* Table Row Counts */}
          <Card title="数据量统计" size="small">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(data.table_counts).map(([key, count]) => (
                <div key={key} className="bg-slate-50 rounded-xl p-4 text-center border border-slate-100">
                  <div className="text-2xl font-black text-slate-900">{count >= 0 ? count.toLocaleString() : <Tag color="red">ERR</Tag>}</div>
                  <div className="text-sm text-slate-500 mt-1">{TABLE_LABELS[key] || key}</div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
