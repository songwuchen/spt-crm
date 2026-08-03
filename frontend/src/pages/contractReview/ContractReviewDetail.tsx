import { useEffect, useState, type ReactNode } from 'react'
import { Button, Descriptions, Space, Spin, Tag, message, Modal } from 'antd'
import { EditOutlined, DeleteOutlined, AuditOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import {
  CONTRACT_REVIEW_SECTIONS,
  CONTRACT_REVIEW_STATUS,
  reviewSectionAllFields,
} from '@/constants/contractReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import AttachmentPanel from '@/components/AttachmentPanel'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  CONTRACT_REVIEW_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default', submitted: 'processing', approved: 'success', rejected: 'error',
}

export default function ContractReviewDetail() {
  usePageTitle('合同评审详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const [row, setRow] = useState<ContractReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    if (!id) return
    setLoading(true)
    contractReviewApi.get(id)
      .then((res) => setRow(res.data))
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmitApproval = () => {
    if (!id) return
    Modal.confirm({
      title: '提交审批',
      content: '确认提交本合同评审进入会签流程？提交后请在「扩展平台 → 审批中心」查看进度。',
      okText: '提交审批',
      onOk: async () => {
        setSubmitting(true)
        try {
          await contractReviewApi.submit(id)
          message.success('已提交审批')
          load()
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          if (msg) message.error(msg)
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  if (loading || !row) {
    return <div className="flex justify-center py-20"><Spin /></div>
  }

  const rj = row.review_json || {}
  const contacts = Array.isArray(rj.contacts) ? rj.contacts as Record<string, unknown>[] : []
  const canSubmit = hasPermission('contract_review:edit') && (row.status === 'draft' || row.status === 'rejected')

  const resolve = (source: 'native' | 'reg', key: string) => {
    if (source === 'native') return (row as unknown as Record<string, unknown>)[key]
    return rj[key]
  }

  return (
    <div className="max-w-5xl mx-auto pb-10">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-xl font-semibold m-0">{row.company_name || row.review_code}</h2>
            <Tag color={STATUS_COLOR[row.status] || 'default'}>{STATUS_LABEL[row.status] || row.status}</Tag>
          </div>
          <div className="text-sm text-slate-500">
            {row.review_code} · {row.review_type || '-'} · 业务员 {row.owner_name || '-'}
          </div>
        </div>
        <Space>
          <Button onClick={() => navigate('/contract-reviews')}>返回</Button>
          {canSubmit && (
            <Button type="primary" icon={<AuditOutlined />} loading={submitting} onClick={handleSubmitApproval}>
              提交审批
            </Button>
          )}
          {hasPermission('contract_review:edit') && (
            <Button icon={<EditOutlined />}
              onClick={() => navigate(`/contract-reviews/${id}/edit`)}>编辑</Button>
          )}
          {hasPermission('contract_review:delete') && (
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: `确定删除「${row.review_code}」？`,
                okType: 'danger',
                onOk: async () => {
                  await contractReviewApi.delete(id!)
                  message.success('已删除')
                  navigate('/contract-reviews')
                },
              })
            }}>删除</Button>
          )}
        </Space>
      </div>

      {CONTRACT_REVIEW_SECTIONS.map((sec) => {
        const fields = reviewSectionAllFields(sec)
        return (
          <div key={sec.key} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-4">
            <ContractSectionTitle title={sec.title} />
            <Descriptions size="small" column={2} bordered>
              {fields.map((f) => {
                const raw = resolve(f.source, f.key)
                let display: ReactNode = raw == null || raw === '' ? '-' : String(raw)
                if (f.key === 'contract_amount' && typeof raw === 'number') {
                  display = `¥${raw.toLocaleString()}`
                }
                if (f.key === 'reported_at' && raw) {
                  display = new Date(String(raw)).toLocaleString('zh-CN')
                }
                return (
                  <Descriptions.Item key={f.key} label={f.label} span={f.widget === 'textarea' ? 2 : 1}>
                    {display}
                  </Descriptions.Item>
                )
              })}
            </Descriptions>
            {sec.afterSlot === 'contacts' && contacts.length > 0 && (
              <div className="mt-4">
                <div className="text-sm font-semibold text-slate-500 mb-2">联系信息</div>
                <Descriptions size="small" column={2} bordered>
                  {contacts.map((c, i) => (
                    <Descriptions.Item key={i} label={`联系人${i + 1}`} span={2}>
                      {[c.contact_name, c.mobile, c.title, c.email].filter(Boolean).join(' · ') || '-'}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              </div>
            )}
            {sec.afterSlot === 'review_files' && (
              <div className="mt-4 space-y-3">
                <AttachmentPanel bizType="contract_review" bizId={row.id} title="附件" />
                <AttachmentPanel bizType="contract_review_image" bizId={row.id} title="图片" accept="image/*" />
              </div>
            )}
            {sec.afterSlot === 'feedback_files' && (
              <div className="mt-4 space-y-3">
                <AttachmentPanel bizType="contract_review_feedback" bizId={row.id} title="反馈附件" />
                <AttachmentPanel bizType="contract_review_feedback_image" bizId={row.id} title="反馈图片" accept="image/*" />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
