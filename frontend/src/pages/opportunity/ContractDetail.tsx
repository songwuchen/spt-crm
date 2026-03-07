import { useState, useEffect } from 'react'
import { Button, Select, Tag, Space, Spin, Descriptions, Modal, DatePicker, Tabs, message } from 'antd'
import { CopyOutlined, CheckCircleOutlined, AuditOutlined, RobotOutlined, PrinterOutlined, FilePdfOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useParams, useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import { approvalApi } from '@/api/approval'
import { userApi } from '@/api/user'
import { aiApi } from '@/api/ai'
import AttachmentPanel from '@/components/AttachmentPanel'
import type { ContractItem, ContractVersion } from '@/api/types'
import { riskLabels, riskColors } from '@/api/types'
import { contractStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
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

  // Approval
  const [approvalModal, setApprovalModal] = useState(false)
  const [selectedApprovers, setSelectedApprovers] = useState<string[]>([])
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

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
    if (curVer) setSelectedVersionId(curVer.id)
  }

  const fetchVersion = async (vid: string) => {
    const res = await contractApi.getVersion(vid)
    setCurrentVersion(res.data)
    setSelectedVersionId(vid)
  }

  useEffect(() => { fetchContract() }, [cid])

  const handleNewVersion = async () => {
    await contractApi.newVersion(cid!)
    message.success('新版本已创建')
    fetchContract()
  }

  const handleSign = async () => {
    if (!signDate) return
    await contractApi.sign(cid!, { signed_date: signDate.format('YYYY-MM-DD') })
    message.success('合同已签署')
    setSignModal(false)
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
          {contract.status === 'draft' && (
            <>
              <Button icon={<AuditOutlined />} onClick={openApprovalModal}>提交审批</Button>
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => setSignModal(true)}>签署合同</Button>
            </>
          )}
          {contract.status === 'signed' && (
            <Button type="primary" onClick={async () => {
              try {
                await contractApi.renew(contract.id)
                message.success('续约机会已创建，请前往续约管理查看')
              } catch { message.error('创建续约失败') }
            }}>发起续约</Button>
          )}
          <Button icon={<FilePdfOutlined />} onClick={() => downloadFile(`/api/v1/contracts/${cid}/export/pdf`, `contract_${contract.contract_no}.pdf`)}>导出PDF</Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印</Button>
          <Button onClick={() => navigate(`/opportunities/${projectId}`)}>返回商机</Button>
        </Space>
      </div>

      {/* Contract Info */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <Descriptions size="small" column={3} bordered>
          <Descriptions.Item label="合同金额">
            <span className="font-bold text-lg">{contract.amount_total != null ? `¥${Number(contract.amount_total).toLocaleString()}` : '-'}</span>
          </Descriptions.Item>
          <Descriptions.Item label="状态"><Tag color={statusColors[contract.status]}>{contract.status}</Tag></Descriptions.Item>
          <Descriptions.Item label="签署日期">{contract.signed_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="到期日期">{contract.end_date || '-'}</Descriptions.Item>
        </Descriptions>

        {contract.payment_terms_json && (
          <div className="mt-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">付款条款</h4>
            <div className="bg-slate-50 p-3 rounded-lg">
              {typeof contract.payment_terms_json === 'object' && !Array.isArray(contract.payment_terms_json) ? (
                <Descriptions column={1} size="small" bordered>
                  {Object.entries(contract.payment_terms_json as Record<string, unknown>).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>{String(v ?? '-')}</Descriptions.Item>
                  ))}
                </Descriptions>
              ) : (
                <div className="text-xs text-slate-700">{JSON.stringify(contract.payment_terms_json, null, 2)}</div>
              )}
            </div>
          </div>
        )}
        {contract.delivery_terms_json && (
          <div className="mt-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">交付条款</h4>
            <div className="bg-slate-50 p-3 rounded-lg">
              {typeof contract.delivery_terms_json === 'object' && !Array.isArray(contract.delivery_terms_json) ? (
                <Descriptions column={1} size="small" bordered>
                  {Object.entries(contract.delivery_terms_json as Record<string, unknown>).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>{String(v ?? '-')}</Descriptions.Item>
                  ))}
                </Descriptions>
              ) : (
                <div className="text-xs text-slate-700">{JSON.stringify(contract.delivery_terms_json, null, 2)}</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Version Selector + Version Detail */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">版本</span>
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
                <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${riskColors[currentVersion.risk_level] || ''}`}>
                  {riskLabels[currentVersion.risk_level]}
                </span>
              ) : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}

        {currentVersion?.key_clauses_json && (
          <div className="mt-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">结构化条款</h4>
            <pre className="bg-slate-50 p-3 rounded-lg text-xs text-slate-700 overflow-auto">
              {JSON.stringify(currentVersion.key_clauses_json, null, 2)}
            </pre>
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
                  <div className="text-xs text-slate-400">AI 将从交付周期、违约条款、知识产权、付款条件等维度分析合同风险</div>
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
                        <span className="text-xs font-bold uppercase text-slate-400">综合风险</span>
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
                        <h4 className="text-xs font-bold uppercase text-slate-400 mb-2">条款风险清单</h4>
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
                        <div className="text-xs font-bold uppercase text-blue-400 mb-1">AI 综合建议</div>
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
      <Modal title="签署合同" open={signModal} onOk={handleSign} onCancel={() => setSignModal(false)}>
        <div className="py-4">
          <p className="text-sm text-slate-600 mb-3">确认签署合同 <span className="font-bold">{contract.contract_no}</span>？</p>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">签署日期</label>
            <DatePicker className="w-full" value={signDate} onChange={(d) => setSignDate(d)} />
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
            <div className="text-xs text-slate-400 mt-1">多选时将按选择顺序依次审批</div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
