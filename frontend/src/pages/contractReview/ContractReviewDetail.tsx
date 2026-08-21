import { useEffect, useState } from 'react'
import { Button, Space, Spin, Tag, message, Modal } from 'antd'
import { EditOutlined, DeleteOutlined, AuditOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import {
  CONTRACT_REVIEW_STATUS,
  findFirstMissingReviewRequired,
} from '@/constants/contractReview'
import ContractReviewReadonly from '@/components/lowcode/ContractReviewReadonly'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'
import { useSiblingRecordNav } from '@/hooks/useSiblingRecordNav'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { buildContractReviewFieldLabels } from '@/utils/dataLogLabels'

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
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)

  const siblingNav = useSiblingRecordNav('contract_review', id, {
    pathForId: (rid) => `/contract-reviews/${rid}`,
    fetchPage: async (pageNo, snap) => {
      const q = snap.listQuery || {}
      const res = await contractReviewApi.list({
        pageNo,
        pageSize: snap.pageSize,
        keyword: q.keyword as string | undefined,
        status: q.status as string | undefined,
        review_type: q.review_type as string | undefined,
      })
      return {
        ids: (res.data.items || []).map((x) => x.id),
        total: res.data.total,
      }
    },
  })

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
        <Space wrap>
          {siblingNav.hasNav && (
            <RecordPrevNextNav
              index={siblingNav.index}
              total={siblingNav.total}
              disabled={siblingNav.busy}
              onPrev={siblingNav.goPrev}
              onNext={siblingNav.goNext}
            />
          )}
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

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-4">
        <ContractReviewReadonly row={row} />
      </div>
    </div>
  )

  const crFieldLabels = buildContractReviewFieldLabels()
  const sidebarDataLog = id ? {
    resourceType: 'contract_review',
    resourceId: id,
    fieldLabels: crFieldLabels,
  } : undefined

  return (
    <div className="max-w-6xl mx-auto pb-10">
      <div className="flex gap-4 items-start">
        {main}
        <aside
          className="w-[300px] shrink-0 sticky top-4 hidden md:block self-start rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
          style={{ height: 'calc(100vh - 140px)', maxHeight: 840 }}
        >
          <WfFlowDynamics
            steps={wfInstance?.flow_steps || []}
            comments={wfInstance?.comments || []}
            onSubmitComment={wfInstance ? handleWfComment : undefined}
            commenting={wfCommenting}
            dataLog={sidebarDataLog}
          />
        </aside>
      </div>

      <div
        className="md:hidden mt-4 rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
        style={{ height: 420 }}
      >
        <WfFlowDynamics
          steps={wfInstance?.flow_steps || []}
          comments={wfInstance?.comments || []}
          onSubmitComment={wfInstance ? handleWfComment : undefined}
          commenting={wfCommenting}
          dataLog={sidebarDataLog}
        />
      </div>
    </div>
  )
}
