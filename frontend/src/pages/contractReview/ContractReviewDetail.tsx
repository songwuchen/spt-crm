import { useEffect, useState, type ReactNode } from 'react'
import { Button, Descriptions, Space, Spin, Tag, message, Modal, Table } from 'antd'
import { EditOutlined, DeleteOutlined, AuditOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import {
  CONTRACT_REVIEW_SECTIONS,
  CONTRACT_REVIEW_STATUS,
  findFirstMissingReviewRequired,
  reviewDepVisible,
  reviewSectionAllFields,
  type ReviewFieldDef,
} from '@/constants/contractReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import AttachmentPanel from '@/components/AttachmentPanel'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  CONTRACT_REVIEW_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default', submitted: 'processing', approved: 'success', rejected: 'error',
}

/** 详情展示：人员/部门显示名称，不展示 UUID */
function formatReviewField(
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

export default function ContractReviewDetail() {
  usePageTitle('合同评审详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const [row, setRow] = useState<ContractReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)

  const loadWf = async (bizId: string) => {
    try {
      const res = await workflowApi.byBiz({ biz_type: 'contract_review', biz_id: bizId })
      setWfInstance(res.data || null)
    } catch {
      setWfInstance(null)
    }
  }

  const load = () => {
    if (!id) return
    setLoading(true)
    contractReviewApi.get(id)
      .then((res) => {
        setRow(res.data)
        void loadWf(res.data.id)
      })
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleWfComment = async (content: string) => {
    if (!wfInstance?.id || !row) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfInstance.id, content)
      const refreshed = await workflowApi.byBiz({
        biz_type: 'contract_review', biz_id: row.id,
      })
      if (refreshed.data) setWfInstance(refreshed.data)
    } finally {
      setWfCommenting(false)
    }
  }

  const handleSubmitApproval = () => {
    if (!id || !row) return
    const missing = findFirstMissingReviewRequired({
      ...(row as unknown as Record<string, unknown>),
      review_json: row.review_json || {},
    })
    if (missing) {
      message.warning(`请先填写「${missing.label}」后再提交审批`)
      navigate(`/contract-reviews/${id}/edit`, { state: { scrollToField: missing.name } })
      return
    }
    Modal.confirm({
      title: '提交审批',
      content: '确认提交本合同评审进入会签流程？提交后可在本页右侧「流程动态」查看进度。',
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
  const canEdit = canSubmit
  const canDelete = hasPermission('contract_review:delete') && row.status === 'draft'

  const main = (
    <div className="min-w-0 flex-1">
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
          {canEdit && (
            <Button icon={<EditOutlined />}
              onClick={() => navigate(`/contract-reviews/${id}/edit`)}>编辑</Button>
          )}
          {canDelete && (
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: `确定删除「${row.review_code}」？仅草稿可删除。`,
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
        const fields = reviewSectionAllFields(sec).filter((f) =>
          reviewDepVisible(f.showWhen, row as unknown as Record<string, unknown>),
        )
        const showContacts = sec.afterSlot === 'contacts' && contacts.length > 0 && String(row.review_type || '') === '合同评审'
        const showPricingFiles = sec.afterSlot === 'pricing_files'
          && String(row.review_type || '') === '合同评审'
          && String(row.need_pricing || '') === '有核价'
        const showReviewFiles = sec.afterSlot === 'review_files'
          && (String(row.review_type || '') === '合同评审' || String(row.review_type || '') === '项目评审')
        const showFeedbackFiles = sec.afterSlot === 'feedback_files'
        if (!fields.length && !showContacts && !showPricingFiles && !showReviewFiles && !showFeedbackFiles) return null
        return (
          <div key={sec.key} className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-4">
            <ContractSectionTitle title={sec.title} />
            {fields.length > 0 && (
              <Descriptions size="small" column={2} bordered>
                {fields.map((f) => (
                  <Descriptions.Item key={f.key} label={f.label} span={f.widget === 'textarea' ? 2 : 1}>
                    {formatReviewField(f, row, rj)}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            )}
            {showContacts && (
              <div className="mt-4">
                <div className="text-sm font-semibold text-slate-500 mb-2">联系信息</div>
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
              <div className="mt-4">
                <AttachmentPanel bizType="contract_review_cost" bizId={row.id} title="成本附件" />
              </div>
            )}
            {showReviewFiles && (
              <div className="mt-4 space-y-3">
                <AttachmentPanel bizType="contract_review" bizId={row.id} title="附件" />
                <AttachmentPanel bizType="contract_review_image" bizId={row.id} title="图片" accept="image/*" />
              </div>
            )}
            {showFeedbackFiles && (
              <div className="mt-4 space-y-3">
                <AttachmentPanel bizType="contract_review_feedback" bizId={row.id} title="反馈附件" />
                <AttachmentPanel bizType="contract_review_feedback_image" bizId={row.id} title="反馈图片" accept="image/*" />
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

  return (
    <div className="max-w-6xl mx-auto pb-10">
      <div className="flex gap-4 items-start">
        {main}
        <aside
          className="w-[300px] shrink-0 sticky top-4 hidden md:block self-start rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
          style={{ height: 'calc(100vh - 140px)', maxHeight: 840 }}
        >
          {wfInstance ? (
            <WfFlowDynamics
              steps={wfInstance.flow_steps || []}
              comments={wfInstance.comments || []}
              onSubmitComment={handleWfComment}
              commenting={wfCommenting}
            />
          ) : (
            <div className="h-full flex flex-col bg-slate-50">
              <div className="px-3 pt-3 pb-2 text-sm font-medium text-slate-600 border-b border-slate-200">
                流程动态
              </div>
              <div className="flex-1 flex items-center justify-center px-4 text-sm text-slate-400 text-center">
                {row.status === 'draft'
                  ? '提交审批后将在此显示流程进度'
                  : '暂无流程动态'}
              </div>
            </div>
          )}
        </aside>
      </div>

      <div
        className="md:hidden mt-4 rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
        style={{ height: 420 }}
      >
        {wfInstance ? (
          <WfFlowDynamics
            steps={wfInstance.flow_steps || []}
            comments={wfInstance.comments || []}
            onSubmitComment={handleWfComment}
            commenting={wfCommenting}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-sm text-slate-400">
            {row.status === 'draft' ? '提交审批后将在此显示流程进度' : '暂无流程动态'}
          </div>
        )}
      </div>
    </div>
  )
}
