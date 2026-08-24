/** 审批抽屉 / 详情页共用：合同评审全部分区只读展示（对齐 ContractReviewDetail） */
import { Descriptions, Table } from 'antd'
import type { ReactNode } from 'react'
import type { ContractReview } from '@/api/contractReview'
import {
  CONTRACT_REVIEW_SECTIONS,
  reviewDepVisible,
  reviewSectionAllFields,
  type ReviewFieldDef,
} from '@/constants/contractReview'
import AttachmentPanel from '@/components/AttachmentPanel'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'

function SectionTitle({ title }: { title: string }) {
  return (
    <div className="text-sm font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-100">
      {title}
    </div>
  )
}

export function formatReviewFieldValue(
  f: ReviewFieldDef,
  row: ContractReview,
  rj: Record<string, unknown>,
): ReactNode {
  if (f.key === 'owner_id') return row.owner_name || '-'
  if (f.key === 'region_manager_id') return row.region_manager_name || '-'
  if (f.key === 'department_id') return row.department_name || '-'

  const raw = f.source === 'native'
    ? (row as unknown as Record<string, unknown>)[f.key]
    : rj[f.key]

  if (raw == null || raw === '') return '-'
  if (f.key === 'contract_amount' && typeof raw === 'number') {
    return `¥${raw.toLocaleString()}`
  }
  if (f.key === 'reported_at' && raw) {
    return new Date(String(raw)).toLocaleString('zh-CN')
  }
  if (Array.isArray(raw)) {
    return raw.length ? raw.map(String).join('、') : '-'
  }
  return String(raw)
}

export default function ContractReviewReadonly({
  row,
  compactAttachments = false,
}: {
  row: ContractReview
  /** 审批抽屉内附件用 compact 样式 */
  compactAttachments?: boolean
}) {
  const rj = row.review_json || {}
  const contacts = Array.isArray(rj.contacts) ? rj.contacts as Record<string, unknown>[] : []
  const rowRec = row as unknown as Record<string, unknown>

  return (
    <div className="space-y-5">
      {CONTRACT_REVIEW_SECTIONS.map((sec) => {
        const fields = reviewSectionAllFields(sec).filter((f) =>
          reviewDepVisible(f.showWhen, rowRec),
        )
        const showContacts = sec.afterSlot === 'contacts' && contacts.length > 0 && String(row.review_type || '') === '合同评审'
        const showPricingFiles = sec.afterSlot === 'pricing_files'
          && String(row.review_type || '') === '合同评审'
          && String(row.need_pricing || '') === '有核价'
        const showReviewFiles = sec.afterSlot === 'review_files'
          && (String(row.review_type || '') === '合同评审' || String(row.review_type || '') === '项目评审')
        const showFeedbackFiles = sec.afterSlot === 'feedback_files'
        if (!fields.length && !showContacts && !showPricingFiles && !showReviewFiles && !showFeedbackFiles) {
          return null
        }
        return (
          <div key={sec.key}>
            <SectionTitle title={sec.title} />
            {fields.length > 0 && (
              <Descriptions size="small" column={2} bordered className="mb-3 text-sm">
                {fields.map((f) => (
                  <Descriptions.Item
                    key={f.key}
                    label={f.label}
                    span={f.widget === 'textarea' ? 2 : 1}
                  >
                    <span className="whitespace-pre-wrap break-all">
                      {formatReviewFieldValue(f, row, rj)}
                    </span>
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}
            {showContacts && (
              <div className="mb-3">
                <div className="text-xs text-slate-500 mb-2">联系信息</div>
                <Table
                  size="small"
                  pagination={false}
                  rowKey={(_, i) => String(i)}
                  dataSource={contacts}
                  scroll={{ x: 900 }}
                  columns={[
                    { title: '联系人', dataIndex: 'contact_name', render: (v) => v || '-' },
                    { title: '上级领导', dataIndex: 'superior', render: (v) => v || '-' },
                    { title: '手机', dataIndex: 'mobile', render: (v) => v || '-' },
                    { title: '职务', dataIndex: 'title', render: (v) => v || '-' },
                    { title: '邮箱or请示', dataIndex: 'email_or_ask', render: (v) => v || '-' },
                    { title: '邮箱', dataIndex: 'email', render: (v) => v || '-' },
                    { title: '请示', dataIndex: 'ask', render: (v) => v || '-' },
                    { title: '地址', dataIndex: 'address', render: (v) => v || '-' },
                  ]}
                />
              </div>
            )}
            {showPricingFiles && (
              <div className="mb-3">
                <AttachmentPanel
                  bizType="contract_review_cost"
                  bizId={row.id}
                  title="成本附件"
                  compact={compactAttachments}
                  readonly={compactAttachments}
                />
              </div>
            )}
            {showReviewFiles && (
              <div className="mb-3 space-y-3">
                <AttachmentPanel
                  bizType="contract_review"
                  bizId={row.id}
                  title="附件"
                  compact={compactAttachments}
                  readonly={compactAttachments}
                />
                <AttachmentPanel
                  bizType="contract_review_image"
                  bizId={row.id}
                  title="图片"
                  accept="image/*"
                  compact={compactAttachments}
                  readonly={compactAttachments}
                />
              </div>
            )}
            {showFeedbackFiles && (
              <div className="mb-3 space-y-3">
                <AttachmentPanel
                  bizType="contract_review_feedback"
                  bizId={row.id}
                  title="反馈附件"
                  compact={compactAttachments}
                  readonly={compactAttachments}
                />
                <AttachmentPanel
                  bizType="contract_review_feedback_image"
                  bizId={row.id}
                  title="反馈图片"
                  accept="image/*"
                  compact={compactAttachments}
                  readonly={compactAttachments}
                />
              </div>
            )}
          </div>
        )
      })}
      <EntityCustomFields
        entityType="contract_review"
        value={row.custom_fields_json || {}}
        readOnly
      />
    </div>
  )
}
