/** 技术协议评审查看内容：左单据 + 右流程动态（对齐表单「查看记录」弹窗）。 */
import type { ReactNode } from 'react'
import { Descriptions, Typography } from 'antd'
import type { TechAgreementReview } from '@/api/techAgreementReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import {
  TECH_AGREEMENT_SECTIONS,
  tarSectionAllFields,
  type TarFieldDef,
} from '@/constants/techAgreementReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import AttachmentPanel from '@/components/AttachmentPanel'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'

const { Text } = Typography

function formatField(f: TarFieldDef, row: TechAgreementReview, fj: Record<string, unknown>): ReactNode {
  if (f.key === 'owner_id') return row.owner_name || '-'
  if (f.key === 'applicant_id') return row.applicant_name || '-'
  if (f.key === 'department_id') return row.department_name || '-'

  const raw = f.source === 'native'
    ? (row as unknown as Record<string, unknown>)[f.key]
    : fj[f.key]

  if (raw == null || raw === '') return '-'
  if (f.key === 'apply_at' && raw) {
    return new Date(String(raw)).toLocaleString('zh-CN')
  }
  if (Array.isArray(raw)) {
    return raw.length ? raw.map(String).join('、') : '-'
  }
  return String(raw)
}

export async function loadTechAgreementWf(bizId: string): Promise<WfInstanceDetail | null> {
  try {
    const res = await workflowApi.byBiz({ biz_type: 'tech_agreement_review', biz_id: bizId })
    return res.data || null
  } catch {
    return null
  }
}

export default function TechAgreementReviewViewBody({
  row,
  wfInstance,
  onSubmitComment,
  commenting,
  showFlowPane = true,
}: {
  row: TechAgreementReview
  wfInstance: WfInstanceDetail | null
  onSubmitComment?: (content: string) => Promise<void>
  commenting?: boolean
  showFlowPane?: boolean
}) {
  const fj = row.form_json || {}

  return (
    <div className="flex gap-0" style={{ minHeight: 480 }}>
      <div className="flex-1 overflow-y-auto pr-3" style={{ maxHeight: '70vh' }}>
        {TECH_AGREEMENT_SECTIONS.map((sec) => (
          <div key={sec.key} className="mb-5">
            <ContractSectionTitle title={sec.title} />
            {sec.fillStage === 'approver' && (
              <p className="text-xs text-slate-400 mb-2 m-0">
                由总工填写「设计审批」、设计审批1 填写「设计审批2」；审批过程中写回。
              </p>
            )}
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
              {tarSectionAllFields(sec).map((f) => (
                <Descriptions.Item key={f.key} label={f.label} span={f.widget === 'textarea' ? 2 : 1}>
                  {formatField(f, row, fj)}
                </Descriptions.Item>
              ))}
            </Descriptions>
            {sec.afterSlot === 'approve_files' && (
              <div className="mt-3 space-y-3">
                <AttachmentPanel bizType="tech_agreement_review_drawing" bizId={row.id} title="认可图（附件）" />
                <AttachmentPanel bizType="tech_agreement_review" bizId={row.id} title="技术协议（附件）" />
              </div>
            )}
          </div>
        ))}
      </div>
      {showFlowPane && (
        <div
          className="w-[300px] shrink-0 overflow-hidden rounded-md border border-slate-200"
          style={{ maxHeight: '70vh' }}
        >
          {wfInstance ? (
            <WfFlowDynamics
              steps={wfInstance.flow_steps || []}
              comments={wfInstance.comments || []}
              onSubmitComment={onSubmitComment}
              commenting={commenting}
            />
          ) : (
            <div className="h-full flex flex-col bg-slate-50">
              <div className="px-3 pt-3 pb-2 text-sm font-medium text-slate-600 border-b border-slate-200">
                流程动态
              </div>
              <div className="flex-1 flex items-center justify-center px-4">
                <Text type="secondary" className="text-sm text-center">
                  {row.status === 'draft' ? '提交审批后将在此显示流程进度' : '暂无流程动态'}
                </Text>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
