import { useState, useEffect } from 'react'
import { Button, Select, Tag, Space, Spin, Descriptions, Modal, DatePicker, InputNumber, Input, Table, Alert, Checkbox, Tabs, Steps, message } from 'antd'
import { CopyOutlined, CheckCircleOutlined, AuditOutlined, RobotOutlined, PrinterOutlined, FilePdfOutlined, EditOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useParams, useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import { paymentApi } from '@/api/payment'
import { deliveryApi } from '@/api/delivery'
import { approvalApi } from '@/api/approval'
import { aiApi } from '@/api/ai'
import AttachmentPanel from '@/components/AttachmentPanel'
import SignaturePad from '@/components/SignaturePad'
import DataView, { formatMoney } from '@/components/DataView'
import { PaymentTermsView, ClauseTermsView, PaymentTermsEditor, LineItemsEditor, toCanonicalRows, PAY_FIELDS, LINE_FIELDS } from '@/components/ContractTerms'
import type { ContractItem, ContractVersion } from '@/api/types'
import { riskLabels, riskColors } from '@/api/types'
import { contractStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useUserSelect } from '@/hooks/useSelectOptions'
import dayjs from 'dayjs'

export default function ContractDetail() {
  usePageTitle('合同详情')
  const { id: projectId, cid } = useParams<{ id: string; cid: string }>()
  const navigate = useNavigate()
  const [contract, setContract] = useState<ContractItem | null>(null)
  const [versions, setVersions] = useState<ContractVersion[]>([])
  const [currentVersion, setCurrentVersion] = useState<ContractVersion | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string>('')
  const [signModal, setSignModal] = useState(false)
  const [signDate, setSignDate] = useState<dayjs.Dayjs | null>(dayjs())
  const [signatureImage, setSignatureImage] = useState<string | null>(null)
  const [showSignPad, setShowSignPad] = useState(false)

  const [renewLoading, setRenewLoading] = useState(false)

  // 条款编辑
  const [editModal, setEditModal] = useState(false)
  const [editAmount, setEditAmount] = useState<number | null>(null)
  const [editEndDate, setEditEndDate] = useState<dayjs.Dayjs | null>(null)
  const [editPay, setEditPay] = useState<Record<string, unknown>[]>([])
  const [editLines, setEditLines] = useState<Record<string, unknown>[]>([])
  const [editSaving, setEditSaving] = useState(false)

  const openEditModal = () => {
    setEditAmount(typeof contract?.amount_total === 'number' ? contract.amount_total : null)
    setEditEndDate(contract?.end_date ? dayjs(contract.end_date) : null)
    setEditPay(toCanonicalRows(contract?.payment_terms_json, PAY_FIELDS))
    setEditLines(toCanonicalRows(currentVersion?.key_clauses_json, LINE_FIELDS))
    setEditModal(true)
  }

  const handleEditSave = async () => {
    setEditSaving(true)
    try {
      const payload: Record<string, unknown> = {
        payment_terms_json: editPay,
        end_date: editEndDate ? editEndDate.format('YYYY-MM-DD') : null,
      }
      if (editAmount != null) payload.amount_total = editAmount
      await contractApi.update(cid!, payload)
      if (currentVersion) await contractApi.updateVersion(currentVersion.id, { key_clauses_json: editLines })
      message.success('合同条款已保存')
      setEditModal(false)
      fetchContract()
    } catch {
      message.error('保存失败')
    } finally {
      setEditSaving(false)
    }
  }

  // 根据付款条款生成回款计划
  type DraftPlan = { remark?: string; amount: number | null; due_date: dayjs.Dayjs | null; trigger_milestone_code?: string }
  const [genModal, setGenModal] = useState(false)
  const [genRows, setGenRows] = useState<DraftPlan[]>([])
  const [genSaving, setGenSaving] = useState(false)
  const [sameContractCount, setSameContractCount] = useState(0)  // 本合同上次生成的计划数
  const [otherPlanCount, setOtherPlanCount] = useState(0)        // 其它来源（手工/其它合同）计划数
  const [replaceExisting, setReplaceExisting] = useState(true)
  const [milestoneOpts, setMilestoneOpts] = useState<{ label: string; value: string }[]>([])

  /** 把合同付款条款映射成回款计划草稿（兼容简道云旧 _widget_ 字段） */
  const deriveDraftPlans = (): DraftPlan[] => {
    const terms = toCanonicalRows(contract?.payment_terms_json, PAY_FIELDS)
    const total = typeof contract?.amount_total === 'number' ? contract.amount_total : null
    let allRatio = terms.length > 0
    const rows: DraftPlan[] = terms.map((t) => {
      const explicit = t.amount != null && t.amount !== '' ? Number(t.amount) : null
      const ratio = t.ratio != null && t.ratio !== '' ? Number(t.ratio) : null
      if (explicit != null) allRatio = false
      let amount: number | null = Number.isFinite(explicit as number) ? explicit : null
      if (amount == null && ratio != null && total != null) amount = Math.round(ratio * total * 100) / 100
      const remark = [t.kind, t.note].filter((x) => x != null && x !== '').map(String).join(' · ') || undefined
      return { remark, amount, due_date: t.due_date ? dayjs(t.due_date as string) : null }
    })
    // 末行兜底差额：仅当全部按比例反算且合同总额已知时，吸收凑整误差
    if (allRatio && total != null && rows.length > 0 && rows.every((r) => r.amount != null)) {
      const sumExceptLast = rows.slice(0, -1).reduce((s, r) => s + (r.amount as number), 0)
      rows[rows.length - 1].amount = Math.round((total - sumExceptLast) * 100) / 100
    }
    return rows
  }

  const openGenModal = async () => {
    setGenRows(deriveDraftPlans())
    setReplaceExisting(true)
    setGenModal(true)
    try {
      const [plansRes, msRes] = await Promise.all([
        paymentApi.listPlans(projectId!),
        deliveryApi.listMilestones(projectId!),
      ])
      const plans = plansRes.data || []
      setSameContractCount(plans.filter((p) => p.source_contract_id === cid).length)
      setOtherPlanCount(plans.filter((p) => p.source_contract_id !== cid).length)
      setMilestoneOpts((msRes.data || []).map((m) => ({
        label: `${m.milestone_code}${m.name ? ' · ' + m.name : ''}`, value: m.milestone_code,
      })))
    } catch {
      setSameContractCount(0); setOtherPlanCount(0); setMilestoneOpts([])
    }
  }

  const updateGenRow = (i: number, key: keyof DraftPlan, val: unknown) =>
    setGenRows((rows) => rows.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const delGenRow = (i: number) => setGenRows((rows) => rows.filter((_, j) => j !== i))
  const addGenRow = () => setGenRows((rows) => [...rows, { remark: undefined, amount: null, due_date: null }])

  const handleGenerate = async () => {
    const valid = genRows.filter((r) => r.amount != null || r.remark || r.due_date)
    if (!valid.length) { message.warning('没有可生成的回款计划'); return }
    setGenSaving(true)
    try {
      const plans = valid.map((r) => ({
        amount: r.amount ?? undefined,
        due_date: r.due_date ? r.due_date.format('YYYY-MM-DD') : undefined,
        remark: r.remark || undefined,
        trigger_milestone_code: r.trigger_milestone_code || undefined,
      }))
      await paymentApi.bulkCreatePlans(projectId!, plans, {
        source_contract_id: cid,
        replace_existing: sameContractCount > 0 ? replaceExisting : false,
      })
      message.success(`已生成 ${plans.length} 条回款计划`)
      setGenModal(false)
      Modal.confirm({
        title: '回款计划已生成',
        content: `已为该商机生成 ${plans.length} 条回款计划，是否前往「回款」查看？`,
        okText: '前往查看', cancelText: '留在本页',
        onOk: () => navigate(`/opportunities/${projectId}`),
      })
    } catch {
      message.error('生成失败')
    } finally {
      setGenSaving(false)
    }
  }

  // Approval
  const [approvalModal, setApprovalModal] = useState(false)
  const [selectedApprovers, setSelectedApprovers] = useState<string[]>([])
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)

  const userSelect = useUserSelect()

  // Signing workflow
  const [approvalFlow, setApprovalFlow] = useState<import('@/api/types').ApprovalFlowItem | null>(null)

  // AI analysis
  const [aiResult, setAiResult] = useState<{
    risk_level?: string
    clauses?: { clause: string; risk: string; detail: string }[]
    overall_comment?: string
  } | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const handleAiAnalyze = async () => {
    if (!selectedVersionId) return
    setAiLoading(true)
    try {
      const res = await aiApi.analyze({ biz_type: 'contract_version', biz_id: selectedVersionId, analysis_type: 'contract_review' })
      setAiResult(res.data?.result || null)
    } catch {
      message.error('AI 分析失败')
    } finally {
      setAiLoading(false)
    }
  }

  const fetchContract = async () => {
    const res = await contractApi.get(cid!)
    const d = res.data
    setContract(d)
    setVersions(d.versions || [])
    const curVer = d.versions?.find((v) => v.version_no === d.current_version_no)
    setCurrentVersion(curVer || null)
    if (curVer) {
      setSelectedVersionId(curVer.id)
      fetchApprovalFlow(curVer.id)
    }
  }

  const fetchVersion = async (vid: string) => {
    const res = await contractApi.getVersion(vid)
    setCurrentVersion(res.data)
    setSelectedVersionId(vid)
    fetchApprovalFlow(vid)
  }

  const fetchApprovalFlow = async (versionId: string) => {
    try {
      const res = await approvalApi.list({ biz_type: 'contract_version', biz_id: versionId })
      const flows = res.data?.items || []
      setApprovalFlow(flows.length > 0 ? flows[0] : null)
    } catch { setApprovalFlow(null) }
  }

  useEffect(() => { fetchContract() }, [cid])

  const handleNewVersion = async () => {
    await contractApi.newVersion(cid!)
    message.success('新版本已创建')
    fetchContract()
  }

  const handleSign = async () => {
    if (!signDate) return
    await contractApi.sign(cid!, {
      signed_date: signDate.format('YYYY-MM-DD'),
      ...(signatureImage ? { signature_image: signatureImage } : {}),
    })
    message.success('合同已签署')
    setSignModal(false)
    setSignatureImage(null)
    setShowSignPad(false)
    fetchContract()
  }

  const openApprovalModal = () => {
    setSelectedApprovers([])
    setApprovalModal(true)
  }

  const handleSubmitApproval = async () => {
    setApprovalSubmitting(true)
    try {
      const approverNames = selectedApprovers.map((id) => userSelect.options.find((o) => o.value === id)?.label || '')
      const res = await approvalApi.submit({
        biz_type: 'contract_version',
        biz_id: selectedVersionId,
        title: `合同审批 - ${contract?.contract_no} V${currentVersion?.version_no || ''}`,
        assignee_ids: selectedApprovers,
        assignee_names: approverNames.length > 0 ? approverNames : undefined,
      })
      if (res.data?.approval_mode && res.data.approval_mode !== 'sequential') {
        message.success(`审批已自动发起（${res.data.approval_mode === 'parallel' ? '并行模式' : '任一通过模式'}）`)
      } else {
        message.success('审批已提交')
      }
      setApprovalModal(false)
    } catch (err: any) {
      if (err?.response?.data?.message) {
        message.error(err.response.data.message)
      }
    } finally {
      setApprovalSubmitting(false)
    }
  }

  if (!contract) return <DetailSkeleton />

  const statusColors = contractStatusColors
  // 只有结构化（行数组）付款条款才能生成回款计划；非行结构（如 {method:"分期"}）不展示按钮
  const canGenerate = toCanonicalRows(contract.payment_terms_json, PAY_FIELDS).length > 0 && contract.status !== 'terminated'
  const genTotal = genRows.reduce((s, r) => s + (r.amount || 0), 0)
  const contractTotal = typeof contract.amount_total === 'number' ? contract.amount_total : null
  const genMismatch = contractTotal != null && Math.abs(genTotal - contractTotal) > 0.01

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{contract.contract_no}</h1>
            <Tag color={statusColors[contract.status]}>{contract.status}</Tag>
          </div>
          <p className="text-sm text-slate-500">
            创建人: {contract.created_by_name || '-'} · {contract.created_at ? new Date(contract.created_at).toLocaleDateString('zh-CN') : ''}
          </p>
        </div>
        <Space>
          {contract.status !== 'terminated' && (
            <Button icon={<EditOutlined />} onClick={openEditModal}>编辑条款</Button>
          )}
          {contract.status === 'draft' && (
            <>
              <Button icon={<AuditOutlined />} onClick={openApprovalModal}>提交审批</Button>
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => setSignModal(true)}>签署合同</Button>
            </>
          )}
          {contract.status === 'signed' && (
            <Button type="primary" loading={renewLoading} onClick={async () => {
              setRenewLoading(true)
              try {
                await contractApi.renew(contract.id)
                message.success('续约机会已创建，请前往续约管理查看')
              } catch { message.error('创建续约失败') }
              finally { setRenewLoading(false) }
            }}>发起续约</Button>
          )}
          <Button icon={<FilePdfOutlined />} onClick={() => downloadFile(`/api/v1/contracts/${cid}/export/pdf`, `contract_${contract.contract_no}.pdf`)}>导出PDF</Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印</Button>
          <Button onClick={() => navigate(`/opportunities/${projectId}`)}>返回商机</Button>
        </Space>
      </div>

      {/* 编辑条款 Modal */}
      <Modal title="编辑合同条款" open={editModal} onOk={handleEditSave} confirmLoading={editSaving}
        onCancel={() => setEditModal(false)} width={960} okText="保存" cancelText="取消">
        <div className="space-y-5 py-2">
          <div className="flex flex-wrap gap-6">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">合同金额</label>
              <InputNumber value={editAmount} min={0} onChange={(v) => setEditAmount(v)} style={{ width: 220 }} addonBefore="¥"
                placeholder={typeof contract.amount_total === 'string' ? '当前已脱敏，留空则不修改' : '输入金额'} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">到期日期</label>
              <DatePicker value={editEndDate} onChange={(d) => setEditEndDate(d)} style={{ width: 220 }} />
            </div>
          </div>
          <div>
            <div className="text-sm font-bold text-slate-700 mb-2">付款条款（收款计划）</div>
            <PaymentTermsEditor value={editPay} onChange={setEditPay} />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-700 mb-2">合同明细（结构化条款）</div>
            <LineItemsEditor value={editLines} onChange={setEditLines} />
          </div>
        </div>
      </Modal>

      {/* 生成回款计划 Modal */}
      <Modal title="生成回款计划" open={genModal} onOk={handleGenerate} confirmLoading={genSaving}
        onCancel={() => setGenModal(false)} width={920}
        okText={genRows.length ? `确认生成 ${genRows.length} 条` : '确认生成'}
        okButtonProps={{ disabled: genRows.length === 0 }} cancelText="取消">
        <div className="py-2 space-y-3">
          <div className="text-sm text-slate-500">
            已根据合同付款条款预填，请核对金额、到期日期与关联里程碑后确认。生成的计划可在商机「回款」中继续编辑。
          </div>
          {sameContractCount > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg">
              <Checkbox checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)}>
                覆盖本合同上次生成的 {sameContractCount} 条计划（取消勾选则追加）
              </Checkbox>
            </div>
          )}
          {otherPlanCount > 0 && (
            <Alert type="info" showIcon
              message={`该商机另有 ${otherPlanCount} 条非本合同生成的计划（手工录入或其它合同），不受影响。`} />
          )}
          <Table size="small" rowKey={(_, i) => String(i)} pagination={false} dataSource={genRows}
            locale={{ emptyText: '无付款条款可生成，点击下方「添加一行」手动录入' }}
            columns={[
              {
                title: '款项说明', key: 'remark',
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Input size="small" value={genRows[i].remark}
                    placeholder="如：预付款 / 进度款"
                    onChange={(e) => updateGenRow(i, 'remark', e.target.value)} />
                ),
              },
              {
                title: '金额', key: 'amount', width: 160,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <InputNumber size="small" style={{ width: '100%' }} min={0} addonBefore="¥"
                    value={genRows[i].amount} onChange={(v) => updateGenRow(i, 'amount', v)} />
                ),
              },
              {
                title: '到期日期', key: 'due_date', width: 150,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <DatePicker size="small" style={{ width: '100%' }} value={genRows[i].due_date}
                    onChange={(d) => updateGenRow(i, 'due_date', d)} />
                ),
              },
              {
                title: '关联里程碑', key: 'milestone', width: 190,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Select size="small" style={{ width: '100%' }} allowClear showSearch optionFilterProp="label"
                    placeholder={milestoneOpts.length ? '进度款挂里程碑（可选）' : '暂无里程碑'}
                    value={genRows[i].trigger_milestone_code} options={milestoneOpts}
                    onChange={(v) => updateGenRow(i, 'trigger_milestone_code', v)} />
                ),
              },
              {
                title: '', key: '__op', width: 44,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => delGenRow(i)} />
                ),
              },
            ]} />
          <div className="flex items-center justify-between">
            <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addGenRow}>添加一行</Button>
            <div className="text-sm">
              <span className="text-slate-400">合计 </span>
              <span className="font-bold text-primary">{formatMoney(genTotal)}</span>
              {contractTotal != null && (
                <>
                  <span className="text-slate-400"> / 合同金额 </span>
                  <span className="font-semibold text-slate-600">{formatMoney(contractTotal)}</span>
                  {genMismatch && <Tag color="warning" className="ml-2">与合同金额不一致</Tag>}
                </>
              )}
            </div>
          </div>
        </div>
      </Modal>

      {/* Signing Workflow Stepper */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">签章流程</div>
        <Steps
          size="small"
          current={
            contract.status === 'signed' ? 3 :
            contract.status === 'terminated' ? 3 :
            approvalFlow?.status === 'approved' ? 2 :
            approvalFlow?.status === 'pending' ? 1 :
            0
          }
          status={
            contract.status === 'terminated' ? 'error' :
            approvalFlow?.status === 'rejected' ? 'error' :
            undefined
          }
          items={[
            {
              title: '草稿',
              description: contract.status === 'draft' && !approvalFlow ? '当前' : '完成',
              icon: <span className="material-symbols-outlined" style={{ fontSize: 20 }}>edit_document</span>,
            },
            {
              title: '审批',
              description: approvalFlow
                ? approvalFlow.status === 'pending'
                  ? `${approvalFlow.current_node}/${approvalFlow.total_nodes} 审批中`
                  : approvalFlow.status === 'approved' ? '已通过'
                  : approvalFlow.status === 'rejected' ? '已驳回'
                  : approvalFlow.status === 'withdrawn' ? '已撤回' : approvalFlow.status
                : '待提交',
              icon: <span className="material-symbols-outlined" style={{ fontSize: 20 }}>approval</span>,
            },
            {
              title: '签章',
              description: contract.status === 'signed' ? '已签署' :
                approvalFlow?.status === 'approved' ? '待签署' : '等待中',
              icon: <span className="material-symbols-outlined" style={{ fontSize: 20 }}>draw</span>,
            },
            {
              title: contract.status === 'terminated' ? '已终止' : '生效',
              description: contract.status === 'signed'
                ? `${contract.signed_date || ''}`
                : contract.status === 'terminated' ? '合同已终止' : '等待中',
              icon: <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                {contract.status === 'terminated' ? 'cancel' : 'verified'}
              </span>,
            },
          ]}
        />
        {/* Approval tasks detail */}
        {approvalFlow?.tasks && approvalFlow.tasks.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="text-sm font-bold text-slate-400 mb-2">审批记录</div>
            <div className="flex flex-wrap gap-2">
              {approvalFlow.tasks.map((t) => (
                <div key={t.id} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border ${
                  t.status === 'approved' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                  t.status === 'rejected' ? 'bg-red-50 border-red-200 text-red-700' :
                  t.status === 'pending' ? 'bg-blue-50 border-blue-200 text-blue-700' :
                  'bg-slate-50 border-slate-200 text-slate-500'
                }`}>
                  <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                    {t.status === 'approved' ? 'check_circle' : t.status === 'rejected' ? 'cancel' : t.status === 'pending' ? 'schedule' : 'more_horiz'}
                  </span>
                  {t.assignee_name || '审批人'}
                  {t.comment && <span className="text-slate-400 ml-1">"{t.comment}"</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Contract Info */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <Descriptions size="small" column={3} bordered>
          <Descriptions.Item label="合同金额">
            <span className="font-bold text-lg">{formatMoney(contract.amount_total)}</span>
          </Descriptions.Item>
          <Descriptions.Item label="状态"><Tag color={statusColors[contract.status]}>{contract.status}</Tag></Descriptions.Item>
          <Descriptions.Item label="签署日期">{contract.signed_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="到期日期">{contract.end_date || '-'}</Descriptions.Item>
        </Descriptions>

        {contract.payment_terms_json && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">付款条款</h4>
              {canGenerate && (
                <Button size="small" icon={<span className="material-symbols-outlined" style={{ fontSize: 16 }}>savings</span>}
                  onClick={openGenModal}>生成回款计划</Button>
              )}
            </div>
            <PaymentTermsView value={contract.payment_terms_json} />
          </div>
        )}
        {contract.delivery_terms_json && (
          <div className="mt-4">
            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">交付条款</h4>
            <DataView value={contract.delivery_terms_json} />
          </div>
        )}
      </div>

      {/* Version Selector + Version Detail */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold uppercase tracking-wider text-slate-400">版本</span>
            <Select
              value={selectedVersionId}
              onChange={fetchVersion}
              style={{ width: 200 }}
              options={versions.map((v) => ({ label: `${v.title || `V${v.version_no}`} (V${v.version_no})`, value: v.id }))}
            />
          </div>
          <Button icon={<CopyOutlined />} onClick={handleNewVersion}>创建新版本</Button>
        </div>

        {currentVersion && (
          <Descriptions size="small" column={3} bordered>
            <Descriptions.Item label="版本标题">{currentVersion.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="版本状态"><Tag>{currentVersion.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="风险等级">
              {currentVersion.risk_level ? (
                <span className={`inline-flex px-2 py-0.5 rounded text-[12px] font-bold border ${riskColors[currentVersion.risk_level] || ''}`}>
                  {riskLabels[currentVersion.risk_level]}
                </span>
              ) : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}

        {currentVersion?.key_clauses_json && (
          <div className="mt-4">
            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">结构化条款</h4>
            <ClauseTermsView value={currentVersion.key_clauses_json} />
          </div>
        )}
      </div>

      {/* Attachments + AI Analysis */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Tabs defaultActiveKey="attachments" className="px-6 pt-2" items={[
          {
            key: 'attachments',
            label: <span className="font-semibold">合同附件</span>,
            children: (
              <div className="pb-6">
                <AttachmentPanel bizType="contract" bizId={cid!} />
              </div>
            ),
          },
          {
            key: 'ai_analysis',
            label: <span className="font-semibold flex items-center gap-1"><RobotOutlined /> AI条款分析</span>,
            children: (
              <div className="pb-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm text-slate-400">AI 将从交付周期、违约条款、知识产权、付款条件等维度分析合同风险</div>
                  <Button type="primary" size="small" icon={<RobotOutlined />} onClick={handleAiAnalyze} loading={aiLoading}>
                    {aiResult ? '重新分析' : '开始分析'}
                  </Button>
                </div>
                {aiLoading ? (
                  <div className="flex items-center justify-center py-16">
                    <Spin tip="AI 正在分析合同条款..." />
                  </div>
                ) : aiResult ? (
                  <div className="space-y-4">
                    {/* Risk Level */}
                    {aiResult.risk_level && (
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-bold uppercase text-slate-400">综合风险</span>
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                          aiResult.risk_level === 'H' ? 'bg-red-50 text-red-600 border border-red-200' :
                          aiResult.risk_level === 'M' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                          'bg-emerald-50 text-emerald-600 border border-emerald-200'
                        }`}>
                          {aiResult.risk_level === 'H' ? '高风险' : aiResult.risk_level === 'M' ? '中风险' : '低风险'}
                        </span>
                      </div>
                    )}

                    {/* Clause Risk Items */}
                    {Array.isArray(aiResult.clauses) && (
                      <div>
                        <h4 className="text-sm font-bold uppercase text-slate-400 mb-2">条款风险清单</h4>
                        <div className="space-y-2">
                          {aiResult.clauses.map((c, i) => {
                            const riskConfig: Record<string, { bg: string; border: string; icon: string; label: string; iconColor: string }> = {
                              H: { bg: 'bg-red-50', border: 'border-red-200', icon: 'error', label: '高', iconColor: 'text-red-500' },
                              M: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'warning', label: '中', iconColor: 'text-amber-500' },
                              L: { bg: 'bg-emerald-50', border: 'border-emerald-200', icon: 'check_circle', label: '低', iconColor: 'text-emerald-500' },
                            }
                            const rc = riskConfig[c.risk] || riskConfig.M
                            return (
                              <div key={i} className={`p-3 rounded-lg border ${rc.bg} ${rc.border}`}>
                                <div className="flex items-center gap-2 mb-1">
                                  <span className={`material-symbols-outlined text-sm ${rc.iconColor}`}>{rc.icon}</span>
                                  <span className="text-sm font-bold text-slate-800">{c.clause}</span>
                                  <Tag color={c.risk === 'H' ? 'error' : c.risk === 'M' ? 'warning' : 'success'}>
                                    {rc.label}风险
                                  </Tag>
                                </div>
                                <div className="text-sm text-slate-600 ml-6">{c.detail}</div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {/* Overall Comment */}
                    {aiResult.overall_comment && (
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div className="text-sm font-bold uppercase text-blue-400 mb-1">AI 综合建议</div>
                        <div className="text-sm text-blue-800">{String(aiResult.overall_comment)}</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-16 text-slate-400 text-sm">
                    <RobotOutlined className="text-3xl mb-3 block text-slate-300" />
                    点击"开始分析"让 AI 审核当前合同版本的条款风险
                  </div>
                )}
              </div>
            ),
          },
        ]} />
      </div>

      {/* Sign Modal */}
      <Modal title="签署合同" open={signModal} onOk={handleSign} onCancel={() => { setSignModal(false); setShowSignPad(false); setSignatureImage(null) }}
        width={showSignPad ? 600 : 480}>
        <div className="py-4">
          <p className="text-sm text-slate-600 mb-3">确认签署合同 <span className="font-bold">{contract.contract_no}</span>？</p>
          <div className="mb-4">
            <label className="text-sm font-medium text-slate-700 mb-1 block">签署日期</label>
            <DatePicker className="w-full" value={signDate} onChange={(d) => setSignDate(d)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-2 block">电子签名（可选）</label>
            {signatureImage ? (
              <div className="border border-slate-200 rounded-lg p-2 bg-slate-50">
                <img src={signatureImage} alt="签名" className="max-h-24" />
                <Button size="small" className="mt-2" onClick={() => { setSignatureImage(null); setShowSignPad(true) }}>重新签名</Button>
              </div>
            ) : showSignPad ? (
              <SignaturePad
                onSave={(dataUrl) => { setSignatureImage(dataUrl); setShowSignPad(false) }}
                onCancel={() => setShowSignPad(false)}
              />
            ) : (
              <Button onClick={() => setShowSignPad(true)} className="border-dashed">
                <span className="material-symbols-outlined text-sm mr-1">draw</span>
                添加手写签名
              </Button>
            )}
          </div>
        </div>
      </Modal>

      {/* Submit Approval Modal */}
      <Modal title="提交合同审批" open={approvalModal} onOk={handleSubmitApproval}
        onCancel={() => setApprovalModal(false)} confirmLoading={approvalSubmitting} okText="提交审批">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将合同 <b>{contract?.contract_no}</b> 当前版本 V{currentVersion?.version_no} 提交审批
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择审批人（按顺序）</label>
            <Select mode="multiple" className="w-full" placeholder="请选择审批人" showSearch filterOption={false}
              value={selectedApprovers} onChange={setSelectedApprovers}
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            <div className="text-sm text-slate-400 mt-1">多选时将按选择顺序依次审批</div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
