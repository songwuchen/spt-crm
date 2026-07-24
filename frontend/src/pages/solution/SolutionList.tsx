import { useState, useEffect, useRef } from 'react'
import { Table, Tag, Select, Input, Button, Modal, Form, message } from 'antd'
import { SearchOutlined, PlusOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { solutionApi } from '@/api/solution'
import { projectApi } from '@/api/project'
import type { SolutionItem } from '@/api/types'
import { solutionStatusLabels, solutionStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'

export default function SolutionList() {
  usePageTitle('方案管理')
  const navigate = useNavigate()
  const [data, setData] = useState<SolutionItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const { hasPermission } = usePermission()
  const canCreate = hasPermission('solution:create')

  // 新增方案（需指定关联商机）
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
      const res = await solutionApi.create(v.project_id, {
        title: v.title || 'V1',
        ...(v.summary ? { summary: v.summary } : {}),
      }) as any
      message.success('方案已创建，请在详情页完善配置与附件')
      setCreateOpen(false)
      const sid = res?.data?.solution?.id
      if (sid) navigate(`/opportunities/${v.project_id}/solutions/${sid}`)
      else fetchData()
    } catch { message.error('创建失败') } finally { setCreating(false) }
  }

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await solutionApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, ...view.buildParams() }) as any
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

  const columns: ColumnsType<SolutionItem> = [
    { title: '方案编号', dataIndex: 'solution_no', width: 180,
      render: (v: string, r: SolutionItem) => (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}/solutions/${r.id}`)}>{v}</a>
      ),
    },
    { title: '商机名称', dataIndex: 'project_name', width: 200, ellipsis: true, render: (v: string) => v || '-' },
    { title: '客户名称', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v: string) => v || '-' },
    { title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={solutionStatusColors[v] || 'default'}>{solutionStatusLabels[v] || v}</Tag>,
    },
    { title: '版本', dataIndex: 'current_version_no', width: 80, render: (v: number) => `V${v ?? 1}` },
    { title: '负责人', dataIndex: 'assignee_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建人', dataIndex: 'created_by_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

  const view = useListView<SolutionItem>('solution', columns, { pageKey: 'solutions' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">方案管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的技术方案</p>
        </div>
        {canCreate && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增方案</Button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索方案编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(solutionStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="solution" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          columns={view.columns}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
        />
      </div>

      {/* 新增方案 */}
      <Modal title="新增方案" open={createOpen} onOk={handleCreate} confirmLoading={creating}
        onCancel={() => setCreateOpen(false)} okText="创建并完善" width={520} destroyOnClose>
        <Form form={createForm} layout="vertical" className="mt-3">
          <Form.Item name="project_id" label="关联商机" rules={[{ required: true, message: '请选择关联商机' }]}>
            <Select showSearch filterOption={false} placeholder="搜索商机名称 / 编号"
              options={projOpts} loading={projLoading} onSearch={searchProjects}
              onDropdownVisibleChange={(o) => { if (o && projOpts.length === 0) searchProjects() }} />
          </Form.Item>
          <Form.Item name="title" label="方案标题"><Input placeholder="如：技术方案 V1（默认 V1）" /></Form.Item>
          <Form.Item name="summary" label="方案概要">
            <Input.TextArea rows={3} placeholder="方案主要内容 / 技术要点（可在详情页继续完善）" />
          </Form.Item>
          <div className="text-[12px] text-slate-400">方案编号将自动生成；创建后将跳转到方案详情页，可完善配置、风险并发起审批。</div>
        </Form>
      </Modal>
    </div>
  )
}
