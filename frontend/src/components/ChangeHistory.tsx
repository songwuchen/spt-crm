import { useState, useEffect } from 'react'
import { Timeline, Spin, Tag } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import DataView from '@/components/DataView'

interface AuditEntry {
  id: string
  user_name?: string
  action: string
  summary?: string
  detail?: Record<string, unknown>
  created_at: string
}

interface Props {
  resourceType: string
  resourceId: string
}

const actionLabels: Record<string, { label: string; color: string }> = {
  create: { label: '创建', color: 'green' },
  update: { label: '更新', color: 'blue' },
  delete: { label: '删除', color: 'red' },
  advance_stage: { label: '推进阶段', color: 'purple' },
  qualify: { label: '转化', color: 'cyan' },
  discard: { label: '废弃', color: 'default' },
  sign: { label: '签约', color: 'green' },
  release: { label: '释放', color: 'orange' },
  claim: { label: '领取', color: 'blue' },
}

function DetailDiff({ detail }: { detail: Record<string, unknown> }) {
  if (!detail || typeof detail !== 'object') return null
  const changes = detail.changes as Record<string, { old?: unknown; new?: unknown }>
  if (!changes || typeof changes !== 'object') {
    // Fallback: 结构化渲染明细，而不是裸 JSON
    return <div className="mt-1"><DataView value={detail} /></div>
  }
  const entries = Object.entries(changes)
  if (entries.length === 0) return null
  return (
    <div className="mt-1 space-y-0.5">
      {entries.map(([field, { old: oldVal, new: newVal }]) => (
        <div key={field} className="flex items-start gap-1 text-[11px]">
          <span className="font-mono text-slate-500 shrink-0">{field}:</span>
          {oldVal != null && <span className="text-red-500 line-through">{String(oldVal)}</span>}
          {oldVal != null && newVal != null && <span className="text-slate-400">&rarr;</span>}
          {newVal != null && <span className="text-emerald-600">{String(newVal)}</span>}
        </div>
      ))}
    </div>
  )
}

export default function ChangeHistory({ resourceType, resourceId }: Props) {
  const [logs, setLogs] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  const fetchLogs = async (p = page) => {
    setLoading(true)
    try {
      const res = await client.get<unknown, ApiResponse<{ items: AuditEntry[]; total: number }>>(
        '/api/v1/audit_logs/by_resource',
        { params: { resource_type: resourceType, resource_id: resourceId, pageNo: p, pageSize: 20 } }
      )
      setLogs(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchLogs() }, [resourceType, resourceId])

  if (loading && logs.length === 0) return <Spin className="flex justify-center py-8" />

  if (logs.length === 0) {
    return <div className="text-center py-8 text-slate-400 text-sm">暂无变更记录</div>
  }

  const items = logs.map((log) => {
    const cfg = actionLabels[log.action] || { label: log.action, color: 'default' }
    return {
      key: log.id,
      children: (
        <div>
          <div className="flex items-center gap-2">
            <Tag color={cfg.color} className="text-[10px]">{cfg.label}</Tag>
            <span className="text-sm text-slate-700">{log.summary || ''}</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {log.user_name || '系统'} &middot; {log.created_at ? new Date(log.created_at).toLocaleString('zh-CN') : ''}
          </div>
          {log.detail && <DetailDiff detail={log.detail} />}
        </div>
      ),
    }
  })

  return (
    <div>
      <Timeline items={items} />
      {total > 20 && (
        <div className="text-center">
          <a className="text-sm text-primary" onClick={() => { const next = page + 1; setPage(next); fetchLogs(next) }}>
            加载更多...
          </a>
        </div>
      )}
    </div>
  )
}
