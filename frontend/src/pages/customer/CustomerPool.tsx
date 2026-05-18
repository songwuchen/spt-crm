import { useState, useEffect } from 'react'
import { Button, Table, Input, Tag, Modal, Select, Space, Form, message } from 'antd'
import { PlusOutlined, UploadOutlined, DownloadOutlined, DeleteOutlined, UserSwitchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useCountdownConfirm } from '@/hooks/useCountdownConfirm'
import { downloadFile } from '@/utils/download'
import ImportModal from '@/components/ImportModal'
import type { Customer } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'

export default function CustomerPool() {
  usePageTitle('客户公海')
  const navigate = useNavigate()
  const [items, setItems] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterLevel, setFilterLevel] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [importOpen, setImportOpen] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignForm] = Form.useForm()
  const [assigning, setAssigning] = useState(false)
  const levelDict = useDataDict('customer_level', ['A', 'B', 'C', 'D'].map(l => ({ label: `${l}级`, value: l })))
  const userSelect = useUserSelect()
  const dangerConfirm = useCountdownConfirm()

  const industryDict = useDataDict('industry')
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))

  const fetch = async (p = page) => {
    setLoading(true)
    try {
      const res = await customerApi.listPool({
        pageNo: p, pageSize: 20,
        keyword: keyword || undefined,
        level: filterLevel,
      })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch(page) }, [page])

  const handleSearch = () => { setPage(1); fetch(1) }

  const handleClaim = (id: string, name: string) => {
    Modal.confirm({
      title: '领取客户',
      content: `确认领取「${name}」？领取后您将成为该客户的负责人。`,
      okText: '确认领取',
      onOk: async () => {
        await customerApi.claim(id)
        message.success(`已成功领取客户「${name}」`)
        fetch()
      },
    })
  }

  const handleBatchClaim = () => {
    if (selectedIds.length === 0) { message.warning('请先勾选客户'); return }
    Modal.confirm({
      title: `批量领取 ${selectedIds.length} 个客户？`,
      content: '领取后您将成为这些客户的负责人',
      okText: '确认领取',
      onOk: async () => {
        let ok = 0
        for (const id of selectedIds) {
          try { await customerApi.claim(id); ok++ } catch { /* skip failed */ }
        }
        message.success(`成功领取 ${ok} 个客户`)
        setSelectedIds([])
        fetch()
      },
    })
  }

  const handleDelete = (id: string, name: string) => {
    dangerConfirm({
      title: '确认删除公海客户',
      content: `「${name}」将被永久删除，不可恢复。`,
      okText: '删除',
      countdown: 3,
      onOk: async () => {
        await customerApi.delete(id)
        message.success('已删除')
        fetch()
      },
    })
  }

  const openAssign = () => {
    if (selectedIds.length === 0) { message.warning('请先勾选要分配的客户'); return }
    assignForm.resetFields()
    setAssignOpen(true)
  }

  const handleAssign = async () => {
    const values = await assignForm.validateFields()
    const ownerName = userSelect.options.find(o => o.value === values.owner_id)?.label || ''
    setAssigning(true)
    try {
      const res = await customerApi.batchTransfer(selectedIds, values.owner_id, ownerName)
      message.success(`已分配 ${res.data?.updated || selectedIds.length} 个客户给 ${ownerName}`)
      setAssignOpen(false)
      assignForm.resetFields()
      setSelectedIds([])
      fetch()
    } catch {
      message.error('分配失败')
    } finally {
      setAssigning(false)
    }
  }

  const handleExport = () => {
    const params = new URLSearchParams()
    if (keyword) params.set('keyword', keyword)
    if (filterLevel) params.set('level', filterLevel)
    const qs = params.toString()
    downloadFile(
      `/api/v1/customers/pool/export/excel${qs ? `?${qs}` : ''}`,
      `customer_pool_${new Date().toISOString().slice(0, 10)}.xlsx`,
    )
  }

  const levelColors: Record<string, string> = { A: 'red', B: 'orange', C: 'blue', D: 'default' }
  const levelCounts = items.reduce<Record<string, number>>((acc, c) => {
    const lv = (c as any).level || '-'
    acc[lv] = (acc[lv] || 0) + 1
    return acc
  }, {})

  const columns: ColumnsType<Customer> = [
    { title: '客户名称', dataIndex: 'name', width: 200,
      render: (v, r) => (
        <a className="font-semibold text-primary" onClick={() => navigate(`/customers/${r.id}`)}>{v}</a>
      ) },
    { title: '级别', dataIndex: 'level', width: 60,
      render: (v) => v ? <Tag color={levelColors[v] || 'default'}>{v}</Tag> : '-' },
    { title: '行业', dataIndex: 'industry', width: 140,
      render: (v) => v ? (industryMap[v] || v) : <span className="text-slate-300">-</span> },
    { title: '地区', dataIndex: 'region', width: 100 },
    { title: '来源', dataIndex: 'source', width: 80 },
    { title: '释放时间', dataIndex: 'updated_at', width: 150,
      render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', width: 180, fixed: 'right',
      render: (_, r) => (
        <Space size={4}>
          <Button type="primary" size="small" onClick={() => handleClaim(r.id, r.name)}>领取</Button>
          <Button size="small" danger onClick={() => handleDelete(r.id, r.name)}>删除</Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">客户公海</h1>
          <p className="text-sm text-slate-500 mt-1">无人负责的客户，可自由领取跟进，管理员可分配给指定销售员</p>
        </div>
        <Space wrap>
          <Button icon={<UploadOutlined />} onClick={() => setImportOpen(true)}>导入</Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/customers/new?pool=1')}>
            新建到公海
          </Button>
        </Space>
      </div>

      {selectedIds.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">已选择 {selectedIds.length} 个客户</span>
          <Space>
            <Button size="small" type="primary" onClick={handleBatchClaim}>批量领取</Button>
            <Button size="small" icon={<UserSwitchOutlined />} onClick={openAssign}>分配给销售员</Button>
            <Button size="small" onClick={() => setSelectedIds([])}>取消选择</Button>
          </Space>
        </div>
      )}

      {/* Stats bar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-2">
          <span className="text-sm text-slate-500">总数</span>
          <span className="ml-2 text-lg font-black text-slate-900">{total}</span>
        </div>
        {Object.entries(levelCounts).filter(([k]) => k !== '-').map(([lv, cnt]) => (
          <div key={lv} className="bg-white border border-slate-200 rounded-lg px-4 py-2">
            <Tag color={levelColors[lv] || 'default'} className="mr-1">{lv}级</Tag>
            <span className="text-sm font-bold text-slate-700">{cnt}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Input.Search placeholder="搜索客户名称" value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onSearch={handleSearch} enterButton style={{ width: 280 }} allowClear />
        <Select placeholder="级别" allowClear style={{ width: 100 }} value={filterLevel}
          onChange={(v) => { setFilterLevel(v); setPage(1); setTimeout(() => fetch(1), 0) }}
          options={levelDict.options} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small"
          scroll={{ x: 1000 }}
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys as string[]),
          }}
          pagination={{ current: page, total, pageSize: 20, onChange: setPage, showTotal: (t) => `共 ${t} 条` }} />
      </div>

      {/* Assign Modal */}
      <Modal
        title="分配公海客户"
        open={assignOpen}
        onOk={handleAssign}
        confirmLoading={assigning}
        onCancel={() => { setAssignOpen(false); assignForm.resetFields() }}
        okText="分配"
      >
        <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
          将选中的 <b>{selectedIds.length}</b> 个客户分配给销售员，分配后客户将脱离公海。
        </div>
        <Form form={assignForm} layout="vertical">
          <Form.Item name="owner_id" label="销售员" rules={[{ required: true, message: '请选择销售员' }]}>
            <Select showSearch filterOption={false} placeholder="搜索并选择销售员"
              loading={userSelect.loading} options={userSelect.options}
              onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Modal */}
      <ImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onSuccess={() => fetch()}
        previewUrl="/api/v1/customers/import/preview"
        importUrl="/api/v1/customers/import/excel?to_pool=true"
        templateUrl="/api/v1/customers/import/template"
        title="导入到公海"
        expectedHeaders={['客户名称', '简称', '行业', '规模', '区域', '地址', '来源', '级别']}
      />
    </div>
  )
}
