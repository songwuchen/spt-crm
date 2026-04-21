import { useState, useEffect } from 'react'
import { Button, Select, Tag, Space, Spin, Descriptions, Input, message, Modal, Table } from 'antd'
import { CopyOutlined, EditOutlined, SaveOutlined, CloseOutlined, SwapOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { solutionApi } from '@/api/solution'
import AttachmentPanel from '@/components/AttachmentPanel'
import type { SolutionItem, SolutionVersion } from '@/api/types'
import { solutionStatusLabels as statusLabels, solutionStatusColors as statusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'

const { TextArea } = Input

export default function SolutionDetail() {
  usePageTitle('方案详情')
  const { id: projectId, sid } = useParams<{ id: string; sid: string }>()
  const navigate = useNavigate()
  const [solution, setSolution] = useState<SolutionItem | null>(null)
  const [versions, setVersions] = useState<SolutionVersion[]>([])
  const [currentVersion, setCurrentVersion] = useState<SolutionVersion | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string>('')
  const [editing, setEditing] = useState(false)
  const [editSummary, setEditSummary] = useState('')
  const [editConfigJson, setEditConfigJson] = useState('')
  const [editRiskJson, setEditRiskJson] = useState('')
  const [compareModal, setCompareModal] = useState(false)
  const [compareV1, setCompareV1] = useState<number>(0)
  const [compareV2, setCompareV2] = useState<number>(0)
  const [compareResult, setCompareResult] = useState<any>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  const fetchSolution = async () => {
    const res = await solutionApi.get(sid!)
    const d = res.data
    setSolution(d)
    setVersions(d.versions || [])
    const curVer = d.versions?.find((v) => v.version_no === d.current_version_no)
    setCurrentVersion(curVer || null)
    if (curVer) setSelectedVersionId(curVer.id)
  }

  const fetchVersion = async (vid: string) => {
    const res = await solutionApi.getVersion(vid)
    setCurrentVersion(res.data)
    setSelectedVersionId(vid)
    setEditing(false)
  }

  useEffect(() => { fetchSolution() }, [sid])

  const handleNewVersion = async () => {
    await solutionApi.newVersion(sid!)
    message.success('新版本已创建')
    fetchSolution()
  }

  const startEdit = () => {
    if (!currentVersion) return
    setEditSummary(currentVersion.summary || '')
    setEditConfigJson(currentVersion.config_json ? JSON.stringify(currentVersion.config_json, null, 2) : '')
    setEditRiskJson(currentVersion.risk_list_json ? JSON.stringify(currentVersion.risk_list_json, null, 2) : '')
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    try {
      const payload: Record<string, unknown> = { summary: editSummary }
      if (editConfigJson.trim()) payload.config_json = JSON.parse(editConfigJson)
      else payload.config_json = null
      if (editRiskJson.trim()) payload.risk_list_json = JSON.parse(editRiskJson)
      else payload.risk_list_json = null
      await solutionApi.updateVersion(selectedVersionId, payload)
      message.success('版本已更新')
      setEditing(false)
      fetchVersion(selectedVersionId)
    } catch {
      message.error('JSON 格式错误，请检查')
    }
  }

  const handleStatusChange = async (status: string) => {
    Modal.confirm({
      title: `确认将方案状态改为 "${statusLabels[status]}"？`,
      onOk: async () => {
        await solutionApi.update(sid!, { status })
        message.success('状态已更新')
        fetchSolution()
      },
    })
  }

  if (!solution) return <DetailSkeleton />

  // Status transitions
  const nextStatuses: Record<string, string[]> = {
    draft: ['reviewing'],
    reviewing: ['approved', 'draft'],
    approved: ['obsolete'],
    obsolete: [],
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{solution.solution_no}</h1>
            <Tag color={statusColors[solution.status]}>{statusLabels[solution.status] || solution.status}</Tag>
          </div>
          <p className="text-sm text-slate-500">
            创建人: {solution.created_by_name || '-'} · {solution.created_at ? new Date(solution.created_at).toLocaleDateString('zh-CN') : ''}
          </p>
        </div>
        <Space>
          {(nextStatuses[solution.status] || []).map((s) => (
            <Button key={s} onClick={() => handleStatusChange(s)}>
              {statusLabels[s]}
            </Button>
          ))}
          <Button onClick={() => navigate(`/opportunities/${projectId}`)}>返回商机</Button>
        </Space>
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
          <Space>
            {!editing && <Button icon={<EditOutlined />} onClick={startEdit}>编辑</Button>}
            {editing && (
              <>
                <Button icon={<SaveOutlined />} type="primary" onClick={saveEdit}>保存</Button>
                <Button icon={<CloseOutlined />} onClick={cancelEdit}>取消</Button>
              </>
            )}
            {versions.length >= 2 && (
              <Button icon={<SwapOutlined />} onClick={() => {
                setCompareV1(versions[versions.length - 2]?.version_no || 1)
                setCompareV2(versions[versions.length - 1]?.version_no || 2)
                setCompareResult(null)
                setCompareModal(true)
              }}>版本对比</Button>
            )}
            <Button icon={<CopyOutlined />} onClick={handleNewVersion}>创建新版本</Button>
          </Space>
        </div>

        {currentVersion && !editing && (
          <>
            <Descriptions size="small" column={3} bordered className="mb-4">
              <Descriptions.Item label="版本标题">{currentVersion.title || '-'}</Descriptions.Item>
              <Descriptions.Item label="版本状态"><Tag>{currentVersion.status}</Tag></Descriptions.Item>
              <Descriptions.Item label="创建时间">{currentVersion.created_at ? new Date(currentVersion.created_at).toLocaleDateString('zh-CN') : '-'}</Descriptions.Item>
            </Descriptions>

            {currentVersion.summary && (
              <div className="mb-4">
                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">方案概要</h4>
                <p className="bg-slate-50 p-3 rounded-lg text-sm text-slate-700 whitespace-pre-wrap">{currentVersion.summary}</p>
              </div>
            )}

            {currentVersion.config_json && (
              <div className="mb-4">
                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">配置/选型清单</h4>
                <div className="bg-slate-50 p-3 rounded-lg overflow-auto">
                  {Array.isArray(currentVersion.config_json) ? (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200">
                          {currentVersion.config_json.length > 0 && Object.keys(currentVersion.config_json[0] as Record<string, unknown>).map((k) => (
                            <th key={k} className="text-left py-1.5 px-2 font-bold text-slate-500">{k}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(currentVersion.config_json as Record<string, unknown>[]).map((row, i) => (
                          <tr key={i} className="border-b border-slate-100 last:border-0">
                            {Object.values(row).map((v, j) => (
                              <td key={j} className="py-1.5 px-2 text-slate-700">{String(v ?? '-')}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : typeof currentVersion.config_json === 'object' ? (
                    <div className="space-y-1">
                      {Object.entries(currentVersion.config_json as Record<string, unknown>).map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-sm">
                          <span className="font-bold text-slate-500 min-w-[80px]">{k}:</span>
                          <span className="text-slate-700">{typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-700">{JSON.stringify(currentVersion.config_json, null, 2)}</div>
                  )}
                </div>
              </div>
            )}

            {currentVersion.risk_list_json && (
              <div className="mb-4">
                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-2">风险清单</h4>
                <div className="bg-slate-50 p-3 rounded-lg overflow-auto">
                  {Array.isArray(currentVersion.risk_list_json) ? (
                    <div className="space-y-2">
                      {(currentVersion.risk_list_json as Record<string, unknown>[]).map((risk, i) => (
                        <div key={i} className="bg-white p-3 rounded-lg border border-slate-200 text-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <Tag color={(risk.severity as string) === 'H' ? 'red' : (risk.severity as string) === 'M' ? 'orange' : 'green'}>
                              {String(risk.severity || risk.level || `R${i + 1}`)}
                            </Tag>
                            <span className="font-bold text-slate-800">{String(risk.description || risk.name || risk.title || '')}</span>
                          </div>
                          {risk.mitigation ? (
                            <div className="text-slate-500 mt-1">缓解: {String(risk.mitigation)}</div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-700">{JSON.stringify(currentVersion.risk_list_json, null, 2)}</div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {currentVersion && editing && (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">方案概要</label>
              <TextArea rows={3} value={editSummary} onChange={(e) => setEditSummary(e.target.value)} placeholder="输入方案概要说明..." />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">配置/选型清单 (JSON)</label>
              <TextArea rows={6} value={editConfigJson} onChange={(e) => setEditConfigJson(e.target.value)} placeholder='{"items": [...]}' className="font-mono text-sm" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">风险清单 (JSON)</label>
              <TextArea rows={6} value={editRiskJson} onChange={(e) => setEditRiskJson(e.target.value)} placeholder='{"risks": [...]}' className="font-mono text-sm" />
            </div>
          </div>
        )}
      </div>

      {/* Attachments */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <h3 className="text-sm font-bold text-slate-900 mb-4">方案附件</h3>
        <AttachmentPanel bizType="solution_version" bizId={selectedVersionId || sid!} />
      </div>

      {/* Compare Modal */}
      <Modal
        title="版本对比"
        open={compareModal}
        width={700}
        onCancel={() => setCompareModal(false)}
        footer={null}
      >
        <div className="flex items-center gap-3 mb-4">
          <Select
            value={compareV1}
            onChange={setCompareV1}
            style={{ width: 180 }}
            options={versions.map((v) => ({ label: `V${v.version_no} - ${v.title || '无标题'}`, value: v.version_no }))}
          />
          <span className="text-slate-400 font-bold">vs</span>
          <Select
            value={compareV2}
            onChange={setCompareV2}
            style={{ width: 180 }}
            options={versions.map((v) => ({ label: `V${v.version_no} - ${v.title || '无标题'}`, value: v.version_no }))}
          />
          <Button type="primary" loading={compareLoading} onClick={async () => {
            if (compareV1 === compareV2) { message.warning('请选择不同版本'); return }
            setCompareLoading(true)
            try {
              const r = await solutionApi.compare(sid!, compareV1, compareV2) as any
              setCompareResult(r.data)
            } catch { message.error('对比失败') }
            finally { setCompareLoading(false) }
          }}>对比</Button>
        </div>

        {compareResult && (
          <div>
            <div className="text-sm mb-3">
              共发现 <span className="font-bold text-primary">{compareResult.diff_count}</span> 处差异
            </div>
            {compareResult.diffs?.length > 0 ? (
              <Table
                size="small"
                pagination={false}
                dataSource={compareResult.diffs}
                rowKey="field"
                columns={[
                  { title: '字段', dataIndex: 'label', width: 120 },
                  { title: `V${compareV1}`, dataIndex: 'v1', render: (v: string) => <span className="text-sm bg-red-50 px-1.5 py-0.5 rounded">{v || '-'}</span> },
                  { title: `V${compareV2}`, dataIndex: 'v2', render: (v: string) => <span className="text-sm bg-green-50 px-1.5 py-0.5 rounded">{v || '-'}</span> },
                ]}
              />
            ) : (
              <div className="text-center py-6 text-slate-400 text-sm">两个版本内容完全一致</div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
