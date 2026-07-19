import { useState, useEffect, useRef } from 'react'
import { Table, Tag, Select, Input, Button, Modal, Form, InputNumber, DatePicker, message } from 'antd'
import { SearchOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import { contractApi } from '@/api/contract'
import { projectApi } from '@/api/project'
import type { ContractItem } from '@/api/types'
import { contractStatusLabels, contractStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'
// 金额格式化自带脱敏识别，见 @/utils/mask
import { fmtMoney } from '@/utils/mask'


export default function ContractList() {
  usePageTitle('合同管理')
  const navigate = useNavigate()
  const [data, setData] = useState<ContractItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const { hasPermission } = usePermission()
  const canCreate = hasPermission('contract:create')

  // 新增合同（需指定关联商机）
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [projOpts, setProjOpts] = useState<{ label: string; value: string }[]>([])
  const [projLoading, setProjLoading] = useState(false)
  const searchProjects = async (kw?: string) => {
    setProjLoading(true)
    try {
      const r = await projectApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined })
      setProjOpts((r.data.items || []).map((p) => ({ label: `${p.name}（${p.project_code}）`, value: p.id })))
    } catch { /* ignore */ } finally { setProjLoading(false) }
  }
  const openCreate = () => { createForm.resetFields(); setProjOpts([]); searchProjects(); setCreateOpen(true) }
  const handleCreate = async () => {
    let v
    try { v = await createForm.validateFields() } catch { return }
    setCreating(true)
    try {
      const res = await contractApi.create(v.project_id, {
        title: v.title || 'V1',
        ...(v.amount_total != null ? { amount_total: v.amount_total } : {}),
        ...(v.end_date ? { end_date: v.end_date.format('YYYY-MM-DD') } : {}),
        ...(v.content ? { key_clauses_json: [{ item: '合同内容', content: v.content }] } : {}),
      }) as any
      message.success('合同已创建，请在详情页完善内容与附件')
      setCreateOpen(false)
      const cid = res?.data?.contract?.id
      if (cid) navigate(`/opportunities/${v.project_id}/contracts/${cid}`)
      else fetchData()
    } catch { message.error('创建失败') } finally { setCreating(false) }
  }

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await contractApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, ...view.buildParams() }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const columns: ColumnsType<ContractItem> = [
    { title: '合同编号', dataIndex: 'contract_no', width: 180,
      render: (v: string, r: ContractItem) => r.project_id ? (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}/contracts/${r.id}`)}>{v}</a>
      ) : <span className="font-mono font-bold text-slate-700">{v}</span>,
    },
    { title: '商机名称', dataIndex: 'project_name', width: 200, ellipsis: true, render: (v: string) => v || '-' },
    { title: '客户名称', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v: string) => v || '-' },
    { title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={contractStatusColors[v] || 'default'}>{contractStatusLabels[v] || v}</Tag>,
    },
    { title: '金额', dataIndex: 'amount_total', width: 140, align: 'right',
      render: (v: number | string) => <span className="font-bold">{fmtMoney(v)}</span> },
    { title: '签约日期', dataIndex: 'signed_date', width: 120,
      render: (v: string) => v || '-' },
    { title: '到期日期', dataIndex: 'end_date', width: 120,
      render: (v: string) => v || '-' },
    { title: '负责人', dataIndex: 'assignee_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

  const view = useListView<ContractItem>('contract', columns, { pageKey: 'contracts', entityType: 'contract' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">合同管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的合同</p>
        </div>
        {canCreate && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增合同</Button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索合同编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(contractStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="contract" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          columns={view.columns}
        />
      </div>

      {/* 新增合同 */}
      <Modal title="新增合同" open={createOpen} onOk={handleCreate} confirmLoading={creating}
        onCancel={() => setCreateOpen(false)} okText="创建并完善" width={520} destroyOnClose>
        <Form form={createForm} layout="vertical" className="mt-3">
          <Form.Item name="project_id" label="关联商机" rules={[{ required: true, message: '请选择关联商机' }]}>
            <Select showSearch filterOption={false} placeholder="搜索商机名称 / 编号"
              options={projOpts} loading={projLoading} onSearch={searchProjects}
              onDropdownVisibleChange={(o) => { if (o && projOpts.length === 0) searchProjects() }} />
          </Form.Item>
          <Form.Item name="title" label="合同标题"><Input placeholder="如：设备采购合同（默认 V1）" /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="amount_total" label="合同金额"><InputNumber className="w-full" min={0} precision={2} /></Form.Item>
            <Form.Item name="end_date" label="到期日期"><DatePicker className="w-full" /></Form.Item>
          </div>
          <Form.Item name="content" label="合同内容"><Input.TextArea rows={3} placeholder="合同主要内容 / 关键条款（可在详情页继续完善）" /></Form.Item>
          <div className="text-[12px] text-slate-400">合同编号将自动生成；创建后将跳转到合同详情页，可上传附件并发起审批。</div>
        </Form>
      </Modal>
    </div>
  )
}
