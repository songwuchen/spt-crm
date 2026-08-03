// 工作流审批详情：左单据+操作 / 右流程动态（对齐简道云审批体验）
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Space, Tag, Drawer, Input, message, Typography, Select, Spin,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, SwapOutlined,
  RollbackOutlined, FileTextOutlined,
} from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import { contractApi } from '@/api/contract'
import type { ContractItem, ContractVersion } from '@/api/types'
import type { WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import ApproveFieldForm, { missingRequiredFields } from '@/components/lowcode/ApproveFieldForm'
import PersonField from '@/components/lowcode/fields/PersonField'
import ContractRegistrationReadonly from '@/components/lowcode/ContractRegistrationReadonly'
import LeadIntelReviewForm from '@/components/lead/LeadIntelReviewForm'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

const { Text, Title } = Typography

/** 业务单据审批 → 完整详情页路径 */
export function bizEntityPath(
  bizType?: string | null,
  bizId?: string | null,
  bizRefId?: string | null,
  mobile = false,
): string | null {
  if (!bizType || !bizId) return null
  const p = mobile ? '/m' : ''
  const map: Record<string, string> = {
    lead: `${p}/leads/${bizId}`,
    order: `${p}/orders/${bizId}`,
    service_ticket: `${p}/service-tickets/${bizId}`,
    contract_review: `${p}/contract-reviews/${bizId}`,
  }
  if (map[bizType]) return map[bizType]
  if (bizType === 'contract_version') {
    const cid = bizRefId || null
    return cid ? `${p}/contracts/${cid}` : null
  }
  return null
}

export function WfProcessDrawer({ open, taskId, instanceId, onClose, onDone }: {
  open: boolean
  taskId?: string | null
  instanceId?: string | null
  onClose: () => void
  onDone: () => void
}) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState<WfInstanceDetail | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [opinion, setOpinion] = useState('')
  const [fieldUpdates, setFieldUpdates] = useState<Record<string, unknown>>({})
  const [fieldHighlight, setFieldHighlight] = useState(false)
  const [transferTo, setTransferTo] = useState<unknown>(undefined)
  const [returnTo, setReturnTo] = useState<string | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [sideTab, setSideTab] = useState('flow')
  const [commenting, setCommenting] = useState(false)
  const [contract, setContract] = useState<ContractItem | null>(null)
  const [contractVersion, setContractVersion] = useState<ContractVersion | null>(null)
  const [contractLoading, setContractLoading] = useState(false)

  const loadContractBiz = async (d: WfInstanceDetail) => {
    if (d.biz_type !== 'contract_version') {
      setContract(null); setContractVersion(null)
      return
    }
    const cid = d.biz_ref_id
    const vid = d.biz_id
    if (!cid && !vid) return
    setContractLoading(true)
    try {
      const [cRes, vRes] = await Promise.all([
        cid ? contractApi.get(cid).catch(() => null) : Promise.resolve(null),
        vid ? contractApi.getVersion(vid).catch(() => null) : Promise.resolve(null),
      ])
      if (cRes?.data) setContract(cRes.data)
      if (vRes?.data) {
        setContractVersion(vRes.data)
        if (!cRes?.data && vRes.data.contract_id) {
          const c2 = await contractApi.get(vRes.data.contract_id).catch(() => null)
          if (c2?.data) setContract(c2.data)
        }
      } else if (cRes?.data?.versions?.length && vid) {
        const match = cRes.data.versions.find((v) => v.id === vid)
          || cRes.data.versions.find((v) => v.version_no === cRes.data.current_version_no)
        if (match) setContractVersion(match)
      }
    } finally {
      setContractLoading(false)
    }
  }

  const reloadDetail = async () => {
    if (!instanceId) return
    const d = await workflowApi.instance(instanceId, taskId ? { task_id: taskId } : undefined)
    setDetail(d.data)
    setFieldUpdates({ ...(d.data.current_task?.field_values || {}) })
    if (d.data.form_instance_id) {
      const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
      setFields(fi.data.field_definitions); setFormData(fi.data.form_data)
    } else {
      setFields([]); setFormData({})
    }
    await loadContractBiz(d.data)
  }

  useEffect(() => {
    if (!open || !instanceId) return
    setOpinion(''); setTransferTo(undefined); setReturnTo(undefined); setFieldUpdates({}); setFieldHighlight(false); setMoreOpen(false)
    setSideTab('flow'); setContract(null); setContractVersion(null)
    setLoading(true)
    ;(async () => {
      try {
        await reloadDetail()
      } finally {
        setLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅随抽屉打开/实例切换重载
  }, [open, instanceId, taskId])

  const effectiveTaskId = taskId || detail?.current_task?.task_id || null
  const canAct = !!effectiveTaskId && detail?.status === 'running'

  const act = async (action: string) => {
    if (!effectiveTaskId) return
    if (action === 'transfer' && !transferTo) return message.error('请选择转交接收人')
    if (action === 'return' && !returnTo) return message.error('请选择退回的目标节点')
    const ct = detail?.current_task
    if (action === 'approve' && ct) {
      if (ct.opinion_required && !opinion.trim()) return message.error('请填写审批意见')
      const miss = missingRequiredFields(ct.field_perms, fieldUpdates)
      if (miss.length) {
        setFieldHighlight(true)
        const labels = miss.map((id) => ct.field_meta?.find((m) => m.id === id)?.label || id)
        return message.error(`请填写必填项: ${labels.join('、')}`)
      }
    }
    setBusy(true)
    try {
      const updates = (ct?.field_perms || []).length
        ? Object.fromEntries((ct!.field_perms || []).map((p) => [p.field, fieldUpdates[p.field]]))
        : undefined
      await workflowApi.act(effectiveTaskId, {
        action, opinion: opinion.trim() || undefined,
        transfer_to: action === 'transfer' ? (Array.isArray(transferTo) ? transferTo[0] : transferTo) as string : undefined,
        to_node_id: action === 'return' ? returnTo : undefined,
        field_updates: action === 'approve' ? updates : undefined,
      })
      message.success('已处理'); onDone(); onClose()
    } finally { setBusy(false) }
  }

  const submitComment = async (content: string) => {
    if (!instanceId) return
    setCommenting(true)
    try {
      await workflowApi.comment(instanceId, content)
      await reloadDetail()
      setSideTab('comments')
      message.success('评论已发送')
    } finally {
      setCommenting(false)
    }
  }

  const bizPath = detail ? bizEntityPath(detail.biz_type, detail.biz_id, detail.biz_ref_id) : null
  const bizEntries = detail?.biz_detail ? Object.entries(detail.biz_detail) : []
  const currentNode = detail?.current_task?.node_name
    || detail?.flow_steps?.find((s) => s.is_current)?.node_name
    || '审批'
  const isLeadIntel = detail?.biz_type === 'lead' && canAct && !!effectiveTaskId && !!detail?.biz_id

  return (
    <Drawer
      title={null}
      width="min(1100px, 96vw)"
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        body: { padding: 0, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' },
        wrapper: { height: '100%' },
      }}
      className="wf-approve-drawer"
      rootClassName="wf-approve-drawer-root"
    >
      {loading || !detail ? (
        <div className="flex items-center justify-center h-full min-h-[560px]"><Spin /></div>
      ) : (
        <div className="flex h-full min-h-0 flex-1">
          {/* 左侧：单据滚动 + 底部固定操作区 */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 shrink-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {detail.business_no && (
                      <Text type="secondary" className="text-xs font-mono">{detail.business_no}</Text>
                    )}
                    {PSTATUS[detail.status] && (
                      <Tag color={PSTATUS[detail.status].color}>{PSTATUS[detail.status].text}</Tag>
                    )}
                  </div>
                  <Title level={4} style={{ margin: '6px 0 0' }} className="!text-lg truncate">
                    {detail.title || '(无标题)'}
                  </Title>
                  <div className="mt-2 inline-flex items-center gap-2 rounded-md bg-blue-50 text-blue-700 px-2.5 py-1 text-sm font-medium">
                    当前节点：{currentNode}
                  </div>
                </div>
                {bizPath && (
                  <Button
                    size="small"
                    icon={<FileTextOutlined />}
                    onClick={() => { onClose(); navigate(bizPath) }}
                  >
                    {contract ? '打开合同页' : '查看完整单据'}
                  </Button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              <section>
                <div className="text-sm font-semibold text-slate-700 mb-2">
                  {detail.biz_type === 'contract_version' && contract
                    ? '合同登记信息'
                    : detail.biz_type === 'lead'
                      ? '线索信息'
                      : '业务信息'}
                </div>
                {fields.length ? (
                  <FormRenderer fields={fields} mode="readonly" value={formData} applyFieldPerms={false} />
                ) : detail.biz_type === 'contract_version' ? (
                  contractLoading ? (
                    <div className="py-8 text-center"><Spin /></div>
                  ) : contract ? (
                    <ContractRegistrationReadonly contract={contract} version={contractVersion} />
                  ) : bizEntries.length ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 rounded-lg bg-slate-50 border border-slate-100 p-4">
                      {bizEntries.map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-sm min-w-0">
                          <span className="shrink-0 w-24 text-slate-500">{k}</span>
                          <span className="text-slate-800 font-medium break-all">
                            {v == null || v === '' ? '—' : String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Text type="secondary">暂无业务明细{bizPath ? '，可点击上方「查看完整单据」' : ''}</Text>
                  )
                ) : bizEntries.length ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 rounded-lg bg-slate-50 border border-slate-100 p-4">
                    {bizEntries.map(([k, v]) => (
                      <div key={k} className="flex gap-2 text-sm min-w-0">
                        <span className="shrink-0 w-24 text-slate-500">{k}</span>
                        <span className="text-slate-800 font-medium break-all">
                          {v == null || v === '' ? '—' : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary">暂无业务明细{bizPath ? '，可点击上方「查看完整单据」' : ''}</Text>
                )}
              </section>

              {canAct && !isLeadIntel && detail.current_task && (detail.current_task.field_perms?.length ?? 0) > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
                  <div className="text-sm font-semibold text-slate-700 mb-2">
                    本节点填写（{detail.current_task.node_name || '审批'}）
                  </div>
                  <ApproveFieldForm
                    currentTask={detail.current_task}
                    values={fieldUpdates}
                    onChange={setFieldUpdates}
                    showTitle={false}
                    highlightMissing={fieldHighlight}
                  />
                </section>
              )}
            </div>

            {/* 线索：情报四态裁定（收录/袭击/回退/暂存），隐藏通用通过驳回 */}
            {isLeadIntel && (
              <div className="shrink-0 border-t border-slate-200 bg-white shadow-[0_-4px_12px_rgba(15,23,42,0.04)] px-5 py-4 max-h-[45vh] overflow-y-auto">
                <div className="text-sm font-semibold text-slate-700 mb-3">情报审批</div>
                <LeadIntelReviewForm
                  leadId={detail.biz_id!}
                  taskId={effectiveTaskId!}
                  initialNewness={
                    detail.biz_detail?.['客户类型'] === '新' ? 'new'
                      : detail.biz_detail?.['客户类型'] === '老' ? 'old'
                        : undefined
                  }
                  onDone={(decision) => {
                    if (decision === 'draft') {
                      void reloadDetail()
                      return
                    }
                    onDone()
                    onClose()
                  }}
                />
              </div>
            )}

            {/* 底部固定：操作意见 + 操作按钮（对齐简道云；线索走情报表单） */}
            {canAct && !isLeadIntel && (
              <div className="shrink-0 border-t border-slate-200 bg-white shadow-[0_-4px_12px_rgba(15,23,42,0.04)]">
                <div className="px-5 pt-3 pb-2">
                  <div className="text-sm font-semibold text-slate-700 mb-2">操作意见</div>
                  <Input.TextArea
                    rows={3}
                    placeholder={detail.current_task?.opinion_required
                      ? '请填写操作意见（必填）'
                      : '请填写操作意见（可选）'}
                    value={opinion}
                    onChange={(e) => setOpinion(e.target.value)}
                    className="!resize-none"
                  />
                </div>
                <div className="px-5 py-3 flex flex-wrap items-center gap-2">
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    loading={busy}
                    onClick={() => act('approve')}
                  >
                    通过
                  </Button>
                  <Button
                    loading={busy}
                    icon={<RollbackOutlined />}
                    onClick={() => {
                      if (!(detail.approval_nodes?.length)) {
                        message.info('当前流程无可退回节点')
                        return
                      }
                      setMoreOpen(true)
                    }}
                    disabled={!(detail.approval_nodes?.length)}
                  >
                    退回
                  </Button>
                  <Button
                    loading={busy}
                    icon={<SwapOutlined />}
                    onClick={() => setMoreOpen(true)}
                  >
                    转交
                  </Button>
                  <Button
                    danger
                    icon={<CloseCircleOutlined />}
                    loading={busy}
                    onClick={() => act('reject')}
                  >
                    驳回
                  </Button>
                </div>
                {moreOpen && (
                  <div className="px-5 pb-3 space-y-2 border-t border-dashed border-slate-100 pt-3">
                    <Space wrap>
                      <div style={{ width: 220 }}>
                        <PersonField value={transferTo} onChange={setTransferTo} placeholder="选择转交人员" />
                      </div>
                      <Button type="primary" ghost icon={<SwapOutlined />} loading={busy} onClick={() => act('transfer')}>
                        确认转交
                      </Button>
                    </Space>
                    {(detail.approval_nodes?.length ?? 0) > 0 && (
                      <Space wrap>
                        <Select
                          style={{ width: 220 }}
                          placeholder="退回到审批节点"
                          value={returnTo}
                          onChange={setReturnTo}
                          allowClear
                          options={(detail.approval_nodes || []).map((n) => ({ label: n.name, value: n.id }))}
                        />
                        <Button type="primary" ghost icon={<RollbackOutlined />} loading={busy} onClick={() => act('return')}>
                          确认退回
                        </Button>
                      </Space>
                    )}
                    <Button type="link" size="small" className="!px-0" onClick={() => setMoreOpen(false)}>
                      收起
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 右侧：流程动态 / 数据评论 */}
          <div className="w-[320px] shrink-0 hidden md:block min-h-0 self-stretch">
            <WfFlowDynamics
              steps={detail.flow_steps || []}
              comments={detail.comments || []}
              tab={sideTab}
              onTabChange={setSideTab}
              onSubmitComment={submitComment}
              commenting={commenting}
            />
          </div>
        </div>
      )}
    </Drawer>
  )
}

export function useWfProcessDrawer(reload: () => void) {
  const [open, setOpen] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [instanceId, setInstanceId] = useState<string | null>(null)
  const openWith = (iid: string, tid?: string | null) => {
    setInstanceId(iid)
    setTaskId(tid || null)
    setOpen(true)
  }
  const node = (
    <WfProcessDrawer
      open={open}
      taskId={taskId}
      instanceId={instanceId}
      onClose={() => setOpen(false)}
      onDone={reload}
    />
  )
  return { openWith, node }
}
