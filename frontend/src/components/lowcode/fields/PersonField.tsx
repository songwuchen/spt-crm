// 人员选择字段(person / person_multi)。值为用户 id(单)或 id 数组(多)。
import { useEffect, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface UserOpt { label: string; value: string }

// 模块级缓存,避免每个字段各自拉一次用户列表
let cache: { opts: UserOpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<UserOpt[]> | null = null

async function loadUsers(): Promise<UserOpt[]> {
  if (cache && Date.now() - cache.ts < TTL) return cache.opts
  if (inflight) return inflight
  // 仅需登录即可访问的选择器接口(原 admin 接口需 user:view,非管理员选不了人)
  inflight = client.get<unknown, ApiResponse<{ id: string; name: string }[]>>('/api/v1/lc/pickable-users')
    .then((res) => {
      const opts = (res.data || []).map((u) => ({ label: u.name, value: u.id }))
      cache = { opts, ts: Date.now() }
      inflight = null
      return opts
    }).catch(() => { inflight = null; return [] })
  return inflight
}

export default function PersonField({
  value, onChange, multi, readonly, placeholder,
}: {
  value: unknown
  onChange: (v: unknown) => void
  multi?: boolean
  readonly?: boolean
  placeholder?: string
}) {
  const [opts, setOpts] = useState<UserOpt[]>(cache?.opts || [])
  const [loading, setLoading] = useState(!cache)

  useEffect(() => {
    let alive = true
    loadUsers().then((o) => { if (alive) { setOpts(o); setLoading(false) } })
    return () => { alive = false }
  }, [])

  const nameOf = (id: string) => opts.find((o) => o.value === id)?.label || id

  if (readonly) {
    const ids = multi ? (Array.isArray(value) ? value : []) : value ? [value] : []
    if (!ids.length) return <div style={{ paddingTop: 4 }}>—</div>
    return <div style={{ paddingTop: 4 }}>{(ids as string[]).map(nameOf).join('，')}</div>
  }

  return (
    <Select
      style={{ width: '100%' }}
      mode={multi ? 'multiple' : undefined}
      showSearch allowClear
      loading={loading}
      placeholder={placeholder || '选择人员'}
      value={(value as string | string[]) ?? (multi ? [] : undefined)}
      options={opts}
      optionFilterProp="label"
      notFoundContent={loading ? <Spin size="small" /> : '无用户'}
      onChange={(v) => onChange(v)}
    />
  )
}
