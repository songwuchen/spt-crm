// 工作流审批详情：左单据+操作 / 右流程动态（对齐简道云审批体验）
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Space, Tag, Drawer, Input, message, Typography, Select, Spin, Radio,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, SwapOutlined,
  RollbackOutlined, FileTextOutlined, PrinterOutlined,
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
import LeadOwnerConfirmActions from '@/components/lead/LeadOwnerConfirmActions'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import AttachmentPanel from '@/components/AttachmentPanel'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'
import { applyApproveFieldDefaults } from '@/utils/lowcodeFormDefaults'
import { canPrintDrawingDocument, printSchemeInstance } from '@/pages/drawing/schemePrint'
import { isLeadOwnerConfirmNode, isLeadReviseTodo, leadReviseEditPath } from '@/utils/leadWorkflow'

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
    customer: `${p}/customers/${bizId}`,
    order: `${p}/orders/${bizId}`,
    service_ticket: `${p}/service-tickets/${bizId}`,
    contract_review: `${p}/contract-reviews/${bizId}`,
    tech_agreement_review: `${p}/tech-agreement-reviews/${bizId}`,
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
  const [leadFinalStatus, setLeadFinalStatus] = useState<'include' | 'return' | 'attack'>('include')
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
    // 优先用流程详情内嵌的表单快照（审批人不必有 form_data:view）
    let nextFields: FieldDefinition[] = []
    if (d.data.form_fields?.length) {
      nextFields = d.data.form_fields
      setFields(d.data.form_fields)
      setFormData(d.data.form_data || {})
    } else if (d.data.form_instance_id) {
      try {
        const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
        nextFields = fi.data.field_definitions
        setFields(fi.data.field_definitions)
        setFormData(fi.data.form_data)
      } catch {
        setFields([])
        setFormData({})
      }
    } else {
      setFields([]); setFormData({})
    }
    const ct = d.data.current_task
    const seed = { ...(ct?.field_values || {}) }
    setFieldUpdates(applyApproveFieldDefaults(seed, {
      fieldIds: (ct?.field_perms || []).map((p) => p.field),
      formFields: nextFields,
      fieldMeta: ct?.field_meta,
    }))
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

  // 线索修订待办：关闭抽屉，跳到与首次申报相同的编辑页
  useEffect(() => {
    if (!open || !detail) return
    const ct = detail.current_task
    const revise = isLeadReviseTodo({
      taskKind: ct?.task_kind,
      nodeType: ct?.node_type,
      nodeName: ct?.node_name,
    })
    if (detail.biz_type === 'lead' && detail.biz_id && revise && ct?.task_id) {
      onClose()
      navigate(leadReviseEditPath(detail.biz_id, ct.task_id))
    }
  }, [open, detail, navigate, onClose])

  // URL/调用方传入的 taskId 仅作加载提示；能否操作以 current_task 为准（已办任务 id 不能误开操作区）
  const effectiveTaskId = detail?.current_task?.task_id || null
  const isReviseTask = detail?.current_task?.task_kind === 'revise'
    || detail?.current_task?.node_type === 'revise'
  const canAct = !!effectiveTaskId && (detail?.status === 'running' || isReviseTask)

  const act = async (action: string) => {
    if (!effectiveTaskId) return
    if (action === 'transfer' && !transferTo) return message.error('请选择转交接收人')
    if (action === 'return' && !returnTo) return message.error('请选择退回的目标节点')
    const ct = detail?.current_task
    if (action === 'approve' && ct && !isReviseTask) {
      if (ct.opinion_required && !opinion.trim()) return message.error('请填写审批意见')
      const miss = missingRequiredFields(ct.field_perms, fieldUpdates, {
        rules: detail?.form_rules,
        formFields: fields,
        formData,
        fieldMeta: ct.field_meta,
      })
      if (miss.length) {
        setFieldHighlight(true)
        const labels = miss.map((id) => ct.field_meta?.find((m) => m.id === id)?.label || id)
        return message.error(`请填写必填项: ${labels.join('、')}`)
      }
    }
    setBusy(true)
    try {
      // 修订待办：先保存表单再重新提交
      if (isReviseTask && (action === 'approve' || action === 'resubmit')) {
        if (detail?.form_instance_id) {
          const nextData = { ...formData, ...fieldUpdates }
          await lowcodeApi.updateInstance(detail.form_instance_id, { form_data: nextData })
        }
        await workflowApi.act(effectiveTaskId, { action: 'resubmit', opinion: opinion.trim() || undefined })
        message.success('已重新提交'); onDone(); onClose()
        return
      }
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
  const isLeadOwnerConfirm = detail?.biz_type === 'lead' && isLeadOwnerConfirmNode(
    detail?.current_task?.node_name,
    detail?.current_task?.node_id,
  )
  const isLeadIntel = detail?.biz_type === 'lead' && canAct && !!effectiveTaskId && !!detail?.biz_id
    && !isReviseTask && !isLeadOwnerConfirm
  const canPrintScheme = canPrintDrawingDocument(fields, formData, detail?.process_name)

  const handlePrintScheme = async () => {
    try {
      await printSchemeInstance({
        formData: { ...formData, ...fieldUpdates },
        fieldDefinitions: fields,
        businessNo: detail?.business_no,
        flowSteps: detail?.flow_steps,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '打印失败')
    }
  }

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
        <div className="flex h-full min-h-0 flex-1 flex-col lg:flex-row overflow-hidden">
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
                    {detail.title || detail.business_no || '(无标题)'}
                  </Title>
                  <div className="mt-2 inline-flex items-center gap-2 rounded-md bg-blue-50 text-blue-700 px-2.5 py-1 text-sm font-medium">
                    {isReviseTask ? '请修改后重新提交' : `当前节点：${currentNode}`}
                  </div>
                </div>
                <Space size="small" wrap className="shrink-0">
                  {canPrintScheme && (
                    <Button
                      size="small"
                      icon={<PrinterOutlined />}
                      onClick={() => { void handlePrintScheme() }}
                    >
                      打印
                    </Button>
                  )}
                  {bizPath && (
                    <Button
                      size="small"
                      icon={<FileTextOutlined />}
                      onClick={() => { onClose(); navigate(bizPath) }}
                    >
                      {contract ? '打开合同页' : isReviseTask ? '去修改单据' : '查看完整单据'}
                    </Button>
                  )}
                </Space>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              <section>
                <div className="text-sm font-semibold text-slate-700 mb-2">
                  {detail.biz_type === 'contract_version' && contract
                    ? '合同登记信息'
                    : detail.biz_type === 'lead'
                      ? '申报信息（创建时填写）'
                      : detail.biz_type === 'customer'
                        ? '客户信息'
                        : detail.biz_type === 'contract_review'
                          ? '合同评审信息'
                          : detail.biz_type === 'tech_agreement_review'
                            ? '技术协议评审信息'
                            : '业务信息'}
                </div>
                {detail.biz_type === 'lead' && detail.biz_id && (
                  <div className="mb-4">
                    <AttachmentPanel bizType="lead" bizId={detail.biz_id} title="附件" compact />
                  </div>
                )}
                {fields.length ? (
                  <FormRenderer
                    fields={fields}
                    mode={isReviseTask ? 'edit' : 'readonly'}
                    value={isReviseTask ? { ...formData, ...fieldUpdates } : formData}
                    onChange={isReviseTask ? ((v) => {
                      setFormData(v)
                      setFieldUpdates(v)
                    }) : undefined}
                    rules={detail.form_rules || []}
                    applyFieldPerms={false}
                  />
                ) : detail.biz_type === 'contract_version' ? (
                  contractLoading ? (
                    <div className="py-8 text-center"><Spin /></div>
                  ) : contract ? (
                    <ContractRegistrationReadonly contract={contract} version={contractVersion} />
                  ) : bizEntries.length ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 rounded-lg bg-slate-50 border border-slate-100 p-4">
                      {bizEntries.map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-sm min-w-0">
                          <span className="shrink-0 w-28 text-slate-500">{k}</span>
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
                      <div
                        key={k}
                        className={`flex gap-2 text-sm min-w-0 ${
                          ['备注1（线索内容）', '备注：请示部门经理的结果', '详细地址', '回退原因', '备注2', '操作意见', '备注', '核心需求', '母公司或者控股公司情况及性质说明'].includes(k)
                            ? 'sm:col-span-2'
                            : ''
                        }`}
                      >
                        <span className="shrink-0 w-36 text-slate-500">{k}</span>
                        <span className="text-slate-800 font-medium break-all whitespace-pre-wrap">
                          {v == null || v === '' ? '—' : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary">暂无业务明细{bizPath ? '，可点击上方「查看完整单据」' : ''}</Text>
                )}
                {detail.biz_type === 'customer' && detail.biz_id && (
                  <div className="mt-4">
                    <AttachmentPanel bizType="customer" bizId={detail.biz_id} title="附件" compact />
                  </div>
                )}
                {detail.biz_type === 'tech_agreement_review' && detail.biz_id && (
                  <div className="mt-4 space-y-3">
                    <AttachmentPanel
                      bizType="tech_agreement_review_drawing"
                      bizId={detail.biz_id}
                      title="认可图（附件）"
                      compact
                    />
                    <AttachmentPanel
                      bizType="tech_agreement_review"
                      bizId={detail.biz_id}
                      title="技术协议（附件）"
                      compact
                    />
                  </div>
                )}
              </section>

              {/* 本节点可填业务字段（通用：含线索情报节点 field_perms） */}
              {canAct && detail.current_task && (detail.current_task.field_perms?.length ?? 0) > 0 && (
                <section className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
                  <div className="text-sm font-semibold text-slate-700 mb-2">
                    本节点填写（{detail.current_task.node_name || '审批'}）
                  </div>
                  <ApproveFieldForm
                    currentTask={{
                      ...detail.current_task,
                      // 操作意见走底部通用栏，不在节点字段里再渲染一遍
                      field_perms: (detail.current_task.field_perms || []).filter(
                        (p) => p.field !== 'review_opinion',
                      ),
                    }}
                    values={fieldUpdates}
                    onChange={setFieldUpdates}
                    showTitle={false}
                    highlightMissing={fieldHighlight}
                    rules={detail.form_rules || []}
                    formData={formData}
                    formFields={fields}
                  />
                  {isLeadIntel && (
                    <div className="mt-4 pt-3 border-t border-amber-100/80">
                      <div className="text-sm font-medium text-slate-700 mb-2">
                        <span className="text-red-500 mr-0.5">*</span>项目最终状态
                      </div>
                      <Radio.Group
                        value={leadFinalStatus}
                        onChange={(e) => setLeadFinalStatus(e.target.value)}
                        optionType="button"
                        buttonStyle="solid"
                        options={[
                          { value: 'include', label: '收录' },
                          { value: 'return', label: '驳回' },
                          { value: 'attack', label: '袭击' },
                        ]}
                      />
                      {leadFinalStatus === 'return' && (
                        <div className="mt-2 text-xs text-amber-700">驳回须在上方填写原因；驳回后不可再报备</div>
                      )}
                    </div>
                  )}
                </section>
              )}
            </div>

            {/* 底部固定：操作意见 + 操作按钮（线索按钮为收录/袭击/回退/暂存） */}
            {canAct && (
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
                {isLeadIntel ? (
                  <div className="px-5 py-3">
                    <LeadIntelReviewForm
                      actionsOnly
                      showFinalStatus={false}
                      compact
                      leadId={detail.biz_id!}
                      taskId={effectiveTaskId!}
                      fieldValues={fieldUpdates}
                      opinion={opinion}
                      finalStatus={leadFinalStatus}
                      onFinalStatusChange={(v) => {
                        if (v === 'include' || v === 'return' || v === 'attack') setLeadFinalStatus(v)
                      }}
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
                ) : isLeadOwnerConfirm ? (
                  <div className="px-5 py-3 space-y-3">
                    <LeadOwnerConfirmActions
                      leadId={detail.biz_id!}
                      taskId={effectiveTaskId!}
                      opinion={opinion}
                      onDone={() => {
                        onDone()
                        onClose()
                      }}
                    />
                    <Button size="small" type="link" className="!px-0" onClick={() => setMoreOpen((v) => !v)}>
                      {moreOpen ? '收起转交' : '转交他人处理'}
                    </Button>
                  </div>
                ) : isReviseTask ? (
                  <div className="px-5 py-3 flex flex-wrap items-center gap-2">
                    <Button
                      type="primary"
                      icon={<CheckCircleOutlined />}
                      loading={busy}
                      onClick={() => act('resubmit')}
                    >
                      保存并重新提交
                    </Button>
                    <Text type="secondary" className="text-xs">
                      修改表单内容后提交，将重新进入审批流程
                    </Text>
                  </div>
                ) : (
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
                      title="驳回后发起人可修改并重新提交"
                    >
                      驳回
                    </Button>
                  </div>
                )}
                {!isLeadIntel && !isReviseTask && moreOpen && (
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

          {/* 右侧/下方：流程动态（始终展示，避免 hidden md:block 在窄屏/缩放时整栏消失） */}
          <div className="w-full lg:w-[320px] shrink-0 flex flex-col min-h-[280px] lg:min-h-0 lg:self-stretch border-t lg:border-t-0 lg:border-l border-slate-200 overflow-hidden bg-slate-50">
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
