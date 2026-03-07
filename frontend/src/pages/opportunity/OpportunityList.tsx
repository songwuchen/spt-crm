import { useState, useEffect } from 'react'
import { Table, Button, Input, Select, Space, Modal, Form, Progress, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import ImportModal from '@/components/ImportModal'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import type { OpportunityProject, Customer } from '@/api/types'
import { stageLabels, stageColors, riskLabels, riskColors } from '@/api/types'
import { userApi } from '@/api/user'
import type { ColumnsType } from 'antd/es/table'
import { opportunityStatusMap as statusMap } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']

export default function OpportunityList() {
  usePageTitle('商机管理')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<OpportunityProject[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(Number(searchParams.get('page')) || 1)
  const [keyword, setKeyword] = useState(searchParams.get('q') || '')
  const [stageCode, setStageCode] = useState<string | undefined>(searchParams.get('stage') || undefined)
  const [status, setStatus] = useState<string | undefined>(searchParams.get('status') || undefined)
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({})
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchStageModal, setBatchStageModal] = useState(false)
  const [batchStage, setBatchStage] = useState<string>('S1')
  const [importModal, setImportModal] = useState(false)
  const [batchTransferModal, setBatchTransferModal] = useState(false)
  const [transferForm] = Form.useForm()
  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const handleBatchStageChange = async () => {
    const results = await Promise.allSettled(
      selectedRowKeys.map((id) => projectApi.update(id as string, { stage_code: batchStage }))
    )
    const ok = results.filter(r => r.status === 'fulfilled').length
    message.success(`已更新 ${ok} 个商机阶段`)
    setBatchStageModal(false)
    setSelectedRowKeys([])
    fetchData()
  }

  const handleBatchTransfer = async () => {
    const values = await transferForm.validateFields()
    const ownerName = userSelect.options.find(o => o.value === values.owner_id)?.label || ''
    const results = await Promise.allSettled(
      selectedRowKeys.map((id) => projectApi.update(id as string, { owner_id: values.owner_id, owner_name: ownerName }))
    )
    const ok = results.filter(r => r.status === 'fulfilled').length
    message.success(`已转让 ${ok} 个商机`)
    setBatchTransferModal(false)
    transferForm.resetFields()
    setSelectedRowKeys([])
    fetchData()
  }

  const handleBatchDelete = () => {
    Modal.confirm({
      title: '批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个商机？`,
      okType: 'danger',
      onOk: async () => {
        await Promise.all(selectedRowKeys.map((id) => projectApi.delete(id as string)))
        message.success(`已删除 ${selectedRowKeys.length} 条`)
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const fetchData = async (page = pageNo, kw = keyword, sc = stageCode, st = status) => {
    setLoading(true)
    try {
      const res = await projectApi.list({
        pageNo: page, pageSize: 20,
        keyword: kw || undefined, stage_code: sc, status: st,
      })
      setData(res.data.items)
      setTotal(res.data.total)

      // Fetch customer names for display
      const ids = [...new Set(res.data.items.map((p) => p.customer_id).filter(Boolean))] as string[]
      if (ids.length > 0) {
        const custRes = await customerApi.list({ pageNo: 1, pageSize: 100 })
        const map: Record<string, string> = {}
        custRes.data.items.forEach((c: Customer) => { map[c.id] = c.name })
        setCustomerMap(map)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => {
    setPageNo(1)
    const params: Record<string, string> = {}
    if (keyword) params.q = keyword
    if (stageCode) params.stage = stageCode
    if (status) params.status = status
    setSearchParams(params, { replace: true })
    fetchData(1, keyword, stageCode, status)
  }

  const columns: ColumnsType<OpportunityProject> = [
    { title: '项目', key: 'name', width: 260,
      render: (_, r) => (
        <div>
          <a onClick={() => navigate(`/opportunities/${r.id}`)} className="text-sm font-bold text-slate-900 hover:text-primary">
            {r.name}
          </a>
          <div className="text-[11px] text-slate-400 font-mono">{r.project_code}</div>
        </div>
      ),
    },
    { title: '客户', key: 'customer', width: 140,
      render: (_, r) => r.customer_id ? (
        <span className="text-sm text-slate-700">{customerMap[r.customer_id] || '-'}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '阶段', key: 'stage', width: 110,
      render: (_, r) => (
        <span className={`inline-flex items-center px-2.5 py-1 rounded text-[10px] font-black uppercase border ${stageColors[r.stage_code] || stageColors.S1}`}>
          {r.stage_code} {stageLabels[r.stage_code]}
        </span>
      ),
    },
    { title: '预期金额', key: 'amount', width: 120, align: 'right',
      render: (_, r) => r.amount_expect != null ? (
        <span className="text-sm font-bold text-slate-800">{Number(r.amount_expect).toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 0 })}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '概率', key: 'probability', width: 110, responsive: ['lg'],
      render: (_, r) => r.probability != null ? (
        <div className="flex items-center gap-2">
          <Progress percent={r.probability} size="small" showInfo={false} strokeColor="#6366f1" className="flex-1 m-0" />
          <span className="text-xs font-bold text-slate-600 w-8 text-right">{r.probability}%</span>
        </div>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '风险', key: 'risk', width: 70, responsive: ['xl'],
      render: (_, r) => r.risk_level ? (
        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${riskColors[r.risk_level] || ''}`}>
          {riskLabels[r.risk_level]}
        </span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '状态', key: 'status', width: 90,
      render: (_, r) => {
        const s = statusMap[r.status] || statusMap.active
        return (
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${s.dot}`} />
            <span className="text-xs font-medium text-slate-600">{s.label}</span>
          </div>
        )
      },
    },
    { title: '负责人', dataIndex: 'owner_name', width: 90,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '', key: 'actions', width: 150, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a onClick={() => navigate(`/opportunities/${r.id}`)} className="text-primary text-xs font-bold uppercase tracking-widest px-2">详情</a>
          <a onClick={() => navigate(`/opportunities/${r.id}/edit`)} className="text-slate-500 text-xs font-bold uppercase tracking-widest px-2 hover:text-primary">编辑</a>
          <a className="text-xs font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
            Modal.confirm({
              title: '确认删除', content: `确定要删除商机「${r.name}」？`, okType: 'danger',
              onOk: async () => { await projectApi.delete(r.id); message.success('已删除'); fetchData() },
            })
          }}>删除</a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900">商机管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理销售项目全生命周期</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {selectedRowKeys.length > 0 && (
            <>
              <Button onClick={() => setBatchStageModal(true)}>批量变更阶段</Button>
              <Button onClick={() => { transferForm.resetFields(); setBatchTransferModal(true) }}>批量转让</Button>
              <Button danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>
                删除 {selectedRowKeys.length} 项
              </Button>
            </>
          )}
          <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>导入</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/projects/export/excel', 'projects.xlsx')}>导出</Button>
          <button onClick={() => navigate('/opportunities/kanban')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>view_kanban</span>
            看板
          </button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/opportunities/new')}
            className="shadow-lg shadow-primary/20 font-bold">
            新建商机
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input placeholder="搜索项目名称/编号..." prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword} onChange={(e) => setKeyword(e.target.value)} onPressEnter={doSearch}
            allowClear style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }} />
          <Select placeholder="阶段" allowClear style={{ width: 130 }} value={stageCode}
            onChange={(v) => { setStageCode(v); setPageNo(1); fetchData(1, keyword, v, status) }}
            options={STAGES.map((s) => ({ label: `${s} ${stageLabels[s]}`, value: s }))} />
          <Select placeholder="状态" allowClear style={{ width: 110 }} value={status}
            onChange={(v) => { setStatus(v); setPageNo(1); fetchData(1, keyword, stageCode, v) }}
            options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            筛选
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading} scroll={{ x: 1200 }}
          rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>

      {/* Import Modal */}
      <ImportModal
        open={importModal}
        onClose={() => setImportModal(false)}
        onSuccess={() => fetchData()}
        previewUrl="/api/v1/projects/import/preview"
        importUrl="/api/v1/projects/import/excel"
        title="导入商机"
        expectedHeaders={['项目名称', '预计金额', '概率(%)', '预计关闭日', '风险等级', '备注']}
      />

      {/* Batch Stage Modal */}
      <Modal title="批量变更阶段" open={batchStageModal} onOk={handleBatchStageChange}
        onCancel={() => setBatchStageModal(false)} okText="确认变更">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将选中的 <b>{selectedRowKeys.length}</b> 个商机变更到新阶段
          </div>
          <Select className="w-full" value={batchStage} onChange={setBatchStage}
            options={STAGES.map((s) => ({ label: `${s} ${stageLabels[s]}`, value: s }))} />
        </div>
      </Modal>

      {/* Batch Transfer Modal */}
      <Modal title="批量转让商机" open={batchTransferModal} onOk={handleBatchTransfer}
        onCancel={() => setBatchTransferModal(false)} okText="确认转让">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将选中的 <b>{selectedRowKeys.length}</b> 个商机转让给新的负责人
          </div>
          <Form form={transferForm} layout="vertical">
            <Form.Item name="owner_id" label="新负责人" rules={[{ required: true, message: '请选择' }]}>
              <Select showSearch filterOption={false} placeholder="搜索用户"
                loading={userSelect.loading} options={userSelect.options}
                onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  )
}
