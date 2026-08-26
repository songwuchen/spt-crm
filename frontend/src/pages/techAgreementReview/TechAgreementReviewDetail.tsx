/** 详情页（通知/直链）：布局与列表「查看记录」弹窗一致。 */
import { useEffect, useState } from 'react'
import { Button, Space, Spin, Tag, message, Modal, Popconfirm } from 'antd'
import { EditOutlined, DeleteOutlined, SendOutlined, ArrowLeftOutlined, PrinterOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { techAgreementReviewApi, type TechAgreementReview } from '@/api/techAgreementReview'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import {
  TECH_AGREEMENT_STATUS,
  findFirstMissingTarRequired,
} from '@/constants/techAgreementReview'
import TechAgreementReviewViewBody, {
  loadTechAgreementWf,
} from '@/pages/techAgreementReview/TechAgreementReviewViewBody'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useSiblingRecordNav } from '@/hooks/useSiblingRecordNav'
import { useAuthStore } from '@/stores/useAuthStore'
import { printTechAgreementReview } from '@/pages/techAgreementReview/techAgreementReviewPrint'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  TECH_AGREEMENT_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default', submitted: 'processing', approved: 'success', rejected: 'error',
}

function canEditRecord(status?: string) {
  return status === 'draft' || status === 'rejected'
}

export default function TechAgreementReviewDetail() {
  usePageTitle('技术协议评审详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const siblingNav = useSiblingRecordNav('tech_agreement_review', id, {
    pathForId: (rid) => `/tech-agreement-reviews/${rid}`,
    fetchPage: async (pageNo, snap) => {
      const q = snap.listQuery || {}
      const res = await techAgreementReviewApi.list({
        pageNo,
        pageSize: snap.pageSize,
        keyword: q.keyword as string | undefined,
        status: q.status as string | undefined,
      })
      return {
        ids: (res.data.items || []).map((x) => x.id),
        total: res.data.total,
      }
    },
  })
  const [row, setRow] = useState<TechAgreementReview | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)

  const load = async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await techAgreementReviewApi.get(id)
      setRow(res.data)
      setWfInstance(await loadTechAgreementWf(res.data.id))
    } catch {
      message.error('加载失败')
      setRow(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleWfComment = async (content: string) => {
    if (!wfInstance?.id || !row) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfInstance.id, content)
      setWfInstance(await loadTechAgreementWf(row.id))
    } finally {
      setWfCommenting(false)
    }
  }

  const handleSubmitApproval = () => {
    if (!id || !row) return
    const missing = findFirstMissingTarRequired({
      ...(row as unknown as Record<string, unknown>),
      form_json: row.form_json || {},
    })
    if (missing) {
      message.warning(`请先填写「${missing.label}」后再提交审批`)
      navigate(`/tech-agreement-reviews/${id}/edit`, { state: { scrollToField: missing.name } })
      return
    }
    Modal.confirm({
      title: '提交审批',
      content: '确认提交本技术协议评审进入审批流程？',
      okText: '提交审批',
      onOk: async () => {
        setSubmitting(true)
        try {
          await techAgreementReviewApi.submit(id)
          message.success('已提交审批')
          await load()
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

  const canEdit = hasPermission('tech_agreement_review:edit') && canEditRecord(row.status)
  const showFlowPane = !!wfInstance || ['submitted', 'approved', 'rejected'].includes(row.status)

  return (
    <div className="max-w-[1100px] mx-auto pb-10">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
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
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tech-agreement-reviews')}>返回</Button>
          <span className="font-mono font-semibold">{row.review_code}</span>
          <Tag color={STATUS_COLOR[row.status] || 'default'}>{STATUS_LABEL[row.status] || row.status}</Tag>
        </Space>
        <Space wrap>
          <Button
            icon={<PrinterOutlined />}
            onClick={() => {
              void printTechAgreementReview({ row, flowSteps: wfInstance?.flow_steps })
            }}
          >
            打印
          </Button>
          {canEdit && (
            <Button icon={<EditOutlined />} onClick={() => navigate(`/tech-agreement-reviews/${id}/edit`)}>
              编辑
            </Button>
          )}
          {canEdit && (
            <Button type="primary" icon={<SendOutlined />} loading={submitting} onClick={handleSubmitApproval}>
              提交审批
            </Button>
          )}
          {hasPermission('tech_agreement_review:delete') && (
            <Popconfirm
              title="确认删除该记录?"
              onConfirm={async () => {
                await techAgreementReviewApi.delete(row.id)
                message.success('已删除')
                navigate('/tech-agreement-reviews')
              }}
            >
              <Button danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <TechAgreementReviewViewBody
          row={row}
          wfInstance={wfInstance}
          onSubmitComment={handleWfComment}
          commenting={wfCommenting}
          showFlowPane={showFlowPane}
        />
      </div>
    </div>
  )
}
