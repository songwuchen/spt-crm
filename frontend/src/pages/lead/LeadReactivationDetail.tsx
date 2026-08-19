import { useEffect, useState } from 'react'
import { Button } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { leadReactivationApi } from '@/api/lead'
import type { LeadReactivationDetail } from '@/api/types'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import LeadReactivationDetailPanel from '@/components/lead/LeadReactivationDetailPanel'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'

export default function LeadReactivationDetailPage() {
  const { recordId } = useParams<{ recordId: string }>()
  const navigate = useNavigate()
  const [row, setRow] = useState<LeadReactivationDetail | null>(null)
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [loading, setLoading] = useState(true)

  usePageTitle(row?.original_lead_code ? `180天激活 · ${row.original_lead_code}` : '180天项目激活')

  const fetchDetail = async () => {
    if (!recordId) return
    setLoading(true)
    try {
      const res = await leadReactivationApi.get(recordId)
      setRow(res.data)
      if (res.data?.lead_id) {
        const wf = await workflowApi.byBiz({ biz_type: 'lead_reactivation', biz_id: res.data.lead_id })
        setWfInstance(wf.data?.status === 'running' ? wf.data : wf.data || null)
      } else {
        setWfInstance(null)
      }
    } catch {
      setRow(null)
      setWfInstance(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void fetchDetail() }, [recordId])

  const handleWfComment = async (content: string) => {
    if (!wfInstance?.id) return
    await workflowApi.comment(wfInstance.id, content)
    await fetchDetail()
  }

  if (loading && !row) return <DetailSkeleton />

  return (
    <div>
      <div className="mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/lead-reactivations')}>返回列表</Button>
      </div>
      <LeadReactivationDetailPanel
        row={row}
        wfInstance={wfInstance}
        loading={loading}
        onWfComment={handleWfComment}
        onHandle={() => row && navigate(`/leads/${row.lead_id}?react=1`)}
      />
    </div>
  )
}
