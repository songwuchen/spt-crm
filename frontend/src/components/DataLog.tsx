import { useState, useEffect, useCallback, useMemo } from 'react'
import { Avatar, Spin, Typography, Tag } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import DataView from '@/components/DataView'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'

const { Text } = Typography

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export interface DataLogEntry {
  id: string
  user_id?: string
  user_name?: string
  action: string
  summary?: string
  detail?: Record<string, unknown>
  created_at: string
}

export interface DataLogProps {
  resourceType: string
  resourceId: string
  alsoResources?: Array<{ resourceType: string; resourceId: string }>
  fieldLabels?: Record<string, string>
  className?: string
}

const ACTION_LABEL: Record<string, string> = {
  create: '创建',
  update: '修改',
  delete: '删除',
  advance_stage: '推进阶段',
  qualify: '转化',
  discard: '废弃',
  sign: '签约',
  release: '释放',
  claim: '领取',
  submit_review: '提交审批',
  submit_approval: '提交审批',
  intel_include: '收录',
  intel_attack: '标记袭击',
  intel_revise: '退回修改',
  intel_return: '驳回',
  intel_draft: '暂存',
  approve: '通过',
  reject: '驳回',
  return: '退回',
  transfer: '转交',
}

function fmtTime(v?: string) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).replace(/\//g, '-')
}

function avatarLetter(name: string) {
  const t = (name || '').trim()
  return t ? t.slice(0, 1) : '?'
}

function collectPersonIds(val: unknown): string[] {
  if (val == null || val === '') return []
  if (Array.isArray(val)) return val.flatMap(collectPersonIds)
  if (typeof val === 'object') {
    const o = val as Record<string, unknown>
    const id = String(o.id || o.value || o.username || '').trim()
    return id ? [id] : []
  }
  if (typeof val === 'string') {
    const s = val.trim()
    if (!s) return []
    if (s.startsWith('[') || s.startsWith('{')) {
      try {
        return collectPersonIds(JSON.parse(s))
      } catch {
        return [s]
      }
    }
    return [s]
  }
  return [String(val)]
}

function looksLikeUnresolvedPerson(text: string): boolean {
  if (UUID_RE.test(text)) return true
  return text.startsWith('[') && text.includes('-')
}

function resolvePersonText(text: string, labels: Record<string, string>): string {
  if (!text) return text
  if (text.startsWith('[')) {
    try {
      const parsed = JSON.parse(text)
      if (Array.isArray(parsed)) {
        return parsed.map((x) => labels[String(x)] || String(x)).join('、')
      }
    } catch {
      /* ignore */
    }
  }
  if (UUID_RE.test(text)) return labels[text] || text
  return text
}

function formatValue(val: unknown, labels: Record<string, string>): string {
  if (val == null || val === '') return '—'
  const ids = collectPersonIds(val)
  if (ids.length && ids.every((id) => UUID_RE.test(id))) {
    const resolved = ids.map((id) => labels[id] || id).join('、')
    if (ids.some((id) => labels[id])) return resolved
  }
  if (typeof val === 'object') {
    try {
      const s = JSON.stringify(val)
      if (looksLikeUnresolvedPerson(s)) return resolvePersonText(s, labels)
      return s
    } catch {
      return String(val)
    }
  }
  const s = String(val)
  if (looksLikeUnresolvedPerson(s)) return resolvePersonText(s, labels)
  return s
}

type FieldChange = {
  old?: unknown
  new?: unknown
  label?: string
  display_old?: string | null
  display_new?: string | null
}

function parseChanges(
  detail: Record<string, unknown> | undefined,
  fieldLabels?: Record<string, string>,
): FieldChange[] {
  if (!detail || typeof detail !== 'object') return []
  const changes = detail.changes as Record<string, FieldChange> | undefined
  if (!changes || typeof changes !== 'object') return []
  return Object.entries(changes).map(([key, diff]) => ({
    ...diff,
    label: diff.label || fieldLabels?.[key] || fieldLabels?.[key.split('.').pop() || ''] || key,
  }))
}

function displayText(
  change: FieldChange,
  side: 'old' | 'new',
  labels: Record<string, string>,
): string | null {
  const displayKey = side === 'old' ? 'display_old' : 'display_new'
  const raw = side === 'old' ? change.old : change.new
  const preferred = change[displayKey]
  let text: string | null = null
  if (preferred != null && preferred !== '') {
    text = String(preferred)
    if (looksLikeUnresolvedPerson(text)) text = resolvePersonText(text, labels)
  } else if (raw != null && raw !== '') {
    text = formatValue(raw, labels)
  }
  return text
}

function FieldDiff({
  change,
  personLabels,
}: {
  change: FieldChange
  personLabels: Record<string, string>
}) {
  const oldText = displayText(change, 'old', personLabels)
  const newText = displayText(change, 'new', personLabels)
  if (!oldText && !newText) return null
  const label = change.label ? `${change.label}:` : ''
  return (
    <div className="py-2 border-b border-slate-100 last:border-b-0">
      {label && (
        <div className="flex items-center gap-1.5 text-[13px] text-slate-600 mb-1.5">
          <FileTextOutlined className="text-slate-400 text-xs" />
          <span>{label}</span>
        </div>
      )}
      {oldText && newText && oldText !== newText && (
        <div className="text-[13px] text-red-500 line-through break-all leading-relaxed mb-1">
          {oldText}
        </div>
      )}
      {newText && (
        <span className="inline-block max-w-full px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 text-[13px] break-all leading-relaxed">
          {newText}
        </span>
      )}
    </div>
  )
}

function LogEntry({
  log,
  fieldLabels,
  personLabels,
}: {
  log: DataLogEntry
  fieldLabels?: Record<string, string>
  personLabels: Record<string, string>
}) {
  const actionText = ACTION_LABEL[log.action] || log.action
  const changes = parseChanges(log.detail, fieldLabels)
  const changeCount = changes.length

  return (
    <div className="relative pb-4 last:pb-0">
      <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 shadow-sm">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <Avatar size={32} className="bg-teal-500 shrink-0 text-xs">
              {avatarLetter(log.user_name || '系统')}
            </Avatar>
            <div className="text-sm font-medium text-slate-800 truncate">
              {log.user_name || '系统'}
            </div>
          </div>
          <div className="text-right shrink-0">
            <Text type="secondary" className="text-xs block whitespace-nowrap">
              {fmtTime(log.created_at)}
            </Text>
            <Tag color={log.action === 'create' ? 'green' : 'blue'} className="mt-1 mr-0">
              {actionText}
            </Tag>
          </div>
        </div>

        {changeCount > 0 ? (
          <>
            <div className="text-xs text-slate-500 mb-1">
              有 {changeCount} 处更改
            </div>
            <div className="space-y-0">
              {changes.map((c, i) => (
                <FieldDiff key={`${c.label}-${i}`} change={c} personLabels={personLabels} />
              ))}
            </div>
          </>
        ) : log.summary ? (
          <div className="text-sm text-slate-700">
            <span className="inline-block px-2.5 py-1 rounded-md bg-emerald-50 text-emerald-700 break-all">
              {log.summary}
            </span>
          </div>
        ) : log.detail ? (
          <DataView value={log.detail} />
        ) : null}
      </div>
    </div>
  )
}

function collectPersonIdsFromLogs(logs: DataLogEntry[]): string[] {
  const ids = new Set<string>()
  for (const log of logs) {
    for (const c of parseChanges(log.detail)) {
      for (const side of ['old', 'new'] as const) {
        for (const id of collectPersonIds(side === 'old' ? c.old : c.new)) {
          if (UUID_RE.test(id)) ids.add(id)
        }
        const disp = side === 'old' ? c.display_old : c.display_new
        if (disp) collectPersonIds(disp).forEach((id) => { if (UUID_RE.test(id)) ids.add(id) })
      }
    }
  }
  return [...ids]
}

export default function DataLog({
  resourceType,
  resourceId,
  alsoResources,
  fieldLabels,
  className,
}: DataLogProps) {
  const [logs, setLogs] = useState<DataLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [personLabels, setPersonLabels] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)

  const resourceKey = [
    resourceType,
    resourceId,
    ...(alsoResources || []).flatMap((r) => [r.resourceType, r.resourceId]),
  ].join('|')

  const fetchOne = async (rt: string, rid: string) => {
    const res = await client.get<unknown, ApiResponse<{ items: DataLogEntry[]; total: number }>>(
      '/api/v1/audit_logs/data_logs/by_resource',
      { params: { resource_type: rt, resource_id: rid, pageNo: 1, pageSize: 50 } },
    )
    return res.data || { items: [], total: 0 }
  }

  const fetchLogs = useCallback(async () => {
    if (!resourceType || !resourceId) return
    setLoading(true)
    try {
      const targets = [
        { resourceType, resourceId },
        ...(alsoResources || []),
      ].filter((r) => r.resourceType && r.resourceId)
      const parts = await Promise.all(targets.map((r) => fetchOne(r.resourceType, r.resourceId)))
      const merged = parts.flatMap((part) => part.items || [])
      const fieldChanges = merged.filter((it) => {
        const changes = (it.detail as { changes?: unknown } | undefined)?.changes
        return it.action === 'create' || it.action === 'update' || (changes && typeof changes === 'object')
      })
      fieldChanges.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      const seen = new Set<string>()
      const deduped = fieldChanges.filter((it) => {
        if (seen.has(it.id)) return false
        seen.add(it.id)
        return true
      })
      setLogs(deduped)
      setPage(1)
      const ids = collectPersonIdsFromLogs(deduped)
      if (ids.length) {
        const map = await getPersonLabelMap(ids)
        setPersonLabels(map)
      } else {
        setPersonLabels({})
      }
    } finally {
      setLoading(false)
    }
  }, [resourceType, resourceId, alsoResources])

  useEffect(() => {
    setLogs([])
    setPersonLabels({})
    void fetchLogs()
  }, [fetchLogs, resourceKey])

  const labels = useMemo(() => personLabels, [personLabels])

  if (loading && logs.length === 0) {
    return <Spin className="flex justify-center py-8" />
  }

  if (logs.length === 0) {
    return (
      <div className={`text-center py-8 text-slate-400 text-sm ${className || ''}`}>
        暂无数据日志
      </div>
    )
  }

  return (
    <div className={className}>
      <div className="relative pl-1">
        <div className="absolute left-[11px] top-3 bottom-3 w-px bg-slate-200" />
        {logs.map((log) => (
          <div key={log.id} className="relative pl-6">
            <span className="absolute left-[7px] top-3 w-2 h-2 rounded-full bg-teal-400 border-2 border-white shadow-sm" />
            <LogEntry log={log} fieldLabels={fieldLabels} personLabels={labels} />
          </div>
        ))}
      </div>
    </div>
  )
}
