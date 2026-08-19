import { Button, Spin, Tabs } from 'antd'
import { Link } from 'react-router-dom'
import type { LeadReactivationDetail } from '@/api/types'
import type { WfInstanceDetail } from '@/types/lowcode'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { leadReactivationStatusConfig } from '@/constants/labels'
import { sourceLabels } from '@/api/types'

const categoryLabels: Record<string, string> = { self_reported: '自报', distributed: '分发' }
const countryLabels: Record<string, string> = { domestic: '国内', overseas: '国外' }

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
      <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">{label}</div>
      <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{value || '-'}</div>
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
      <span className="text-[13px] font-semibold">{children}</span>
    </div>
  )
}

type Props = {
  row: LeadReactivationDetail | null
  wfInstance: WfInstanceDetail | null
  loading?: boolean
  onWfComment?: (content: string) => Promise<void>
  onHandle?: () => void
  compact?: boolean
}

export default function LeadReactivationDetailPanel({
  row, wfInstance, loading, onWfComment, onHandle, compact,
}: Props) {
  if (loading || !row) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spin />
      </div>
    )
  }

  const snap = row.lead_snapshot
  const stCfg = row.is_current_round && row.reactivation_status
    ? leadReactivationStatusConfig[row.reactivation_status]
    : null
  const canHandle = row.is_current_round
    && ['awaiting_reporter', 'awaiting_filler', 'pending_review'].includes(row.reactivation_status || '')

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-lg font-bold text-slate-900">{row.original_lead_code || '180天项目激活'}</div>
          <div className="text-sm text-slate-500">{row.lead_title}</div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {stCfg && (
            <span className="inline-flex px-2.5 py-1 rounded text-xs font-bold bg-blue-100 text-blue-700">
              {stCfg.label}
            </span>
          )}
          {canHandle && onHandle && (
            <Button type="primary" size="small" onClick={onHandle}>办理待办</Button>
          )}
          <Link to={`/leads/${row.lead_id}`} target={compact ? '_blank' : undefined}>
            <Button size="small">打开申报信息</Button>
          </Link>
        </div>
      </div>

      <div className={`grid grid-cols-1 gap-4 ${compact ? '' : 'lg:grid-cols-12'}`}>
        <div className={compact ? '' : 'lg:col-span-8'}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 sm:p-6">
            <Tabs
              items={[
                {
                  key: 'snapshot',
                  label: '原申报信息内容',
                  children: (
                    <div className="space-y-4 pt-2">
                      <SectionTitle>原申报信息内容</SectionTitle>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Field label="项目编号" value={snap?.lead_code} />
                        <Field label="申报人" value={snap?.reporter_name} />
                        <Field label="填表人" value={snap?.created_by_name} />
                        <Field label="申报时间" value={snap?.reported_at ? new Date(snap.reported_at).toLocaleString('zh-CN') : undefined} />
                        <Field label="来源" value={snap?.source ? (sourceLabels[snap.source] || snap.source) : undefined} />
                        <Field label="类别" value={snap?.category ? categoryLabels[snap.category] || snap.category : undefined} />
                        <Field label="项目名称" value={snap?.title} />
                        <Field label="公司名称" value={snap?.company_name} />
                        <Field label="客户类型" value={snap?.customer_type} />
                        <Field label="行业" value={snap?.industry} />
                        <Field label="国别" value={snap?.country_type ? countryLabels[snap.country_type] || snap.country_type : undefined} />
                        <Field label="是否内部冲突" value={snap?.has_internal_conflict} />
                        <Field label="项目动态" value={snap?.project_activity} />
                        <Field label="项目地址" value={[snap?.province, snap?.city, snap?.district].filter(Boolean).join('') || snap?.region} />
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'activation',
                  label: '本次激活内容',
                  children: (
                    <div className="space-y-4 pt-2">
                      <SectionTitle>本次 180 天激活（第 {row.round_no} 轮）</SectionTitle>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Field label="项目状态" value={row.report_project_status} />
                        <Field label="提交人" value={row.submitted_by_name} />
                        <Field label="提交时间" value={row.submitted_at ? new Date(row.submitted_at).toLocaleString('zh-CN') : undefined} />
                        <div className="sm:col-span-2"><Field label="项目近况" value={row.project_recent} /></div>
                        <div className="sm:col-span-2"><Field label="跟进进度" value={row.follow_progress} /></div>
                        <div className="sm:col-span-2"><Field label="实地拜访情况" value={row.site_visit} /></div>
                      </div>
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>

        <div className={compact ? '' : 'lg:col-span-4'}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <WfFlowDynamics
              variant="page"
              steps={wfInstance?.flow_steps || []}
              comments={wfInstance?.comments || []}
              onSubmitComment={wfInstance && onWfComment ? onWfComment : undefined}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
