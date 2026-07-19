import { useState, useEffect } from 'react'
import { Button, Table, Input, Tag, Modal, Select, Space, Form, Switch, InputNumber, Tooltip, message } from 'antd'
import { PlusOutlined, UploadOutlined, DownloadOutlined, UserSwitchOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { customerApi, customerPoolApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useCountdownConfirm } from '@/hooks/useCountdownConfirm'
import { usePermission } from '@/hooks/usePermission'
import { downloadFile } from '@/utils/download'
import ImportModal from '@/components/ImportModal'
import type { Customer, CustomerPool as PoolDef } from '@/api/types'
import { customerLevelColors, intentLevelColors, intentLevelShortLabels, poolSourceLabels } from '@/constants/labels'
import type { ColumnsType } from 'antd/es/table'

function daysSince(iso?: string): number | null {
  if (!iso) return null
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000))
}

export default function CustomerPool() {
  usePageTitle('客户公海')
  const navigate = useNavigate()
  const { hasPermission } = usePermission()
  const canManage = hasPermission('role:manage')
  const canDelete = hasPermission('customer:delete')

  const [items, setItems] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [poolId, setPoolId] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [importOpen, setImportOpen] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignForm] = Form.useForm()
  const [assigning, setAssigning] = useState(false)
  const [poolSettingsOpen, setPoolSettingsOpen] = useState(false)
  const [pools, setPools] = useState<PoolDef[]>([])
  const [defaultCount, setDefaultCount] = useState(0)
  const userSelect = useUserSelect()
  const dangerConfirm = useCountdownConfirm()

  const industryDict = useDataDict('industry')
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))

  const fetchPools = async () => {
    try {
      const res = await customerPoolApi.list()
      setPools(res.data?.items || [])
      setDefaultCount(res.data?.default_count || 0)
    } catch { /* 无公海配置时忽略 */ }
  }

  const fetch = async (p = page, pid = poolId) => {
    setLoading(true)
    try {
      const res = await customerApi.listPool({
        pageNo: p, pageSize: 20,
        keyword: keyword || undefined,
        pool_id: pid,
      })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchPools() }, [])
  // 单一数据源：翻页或切换公海都只经此触发一次拉取，避免 changePool 再手动 fetch 造成重复请求
  useEffect(() => { fetch(page) }, [page, poolId])

  const handleSearch = () => { setPage(1); fetch(1) }

  const handleClaim = (id: string, name: string) => {
    Modal.confirm({
      title: '领取客户',
      content: `确认领取「${name}」？领取后您将成为该客户的负责人。`,
      okText: '确认领取',
      onOk: async () => {
        await customerApi.claim(id)
        message.success(`已成功领取客户「${name}」`)
        fetch(); fetchPools()
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
        fetch(); fetchPools()
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
        fetch(); fetchPools()
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
      fetch(); fetchPools()
    } catch {
      message.error('分配失败')
    } finally {
      setAssigning(false)
    }
  }

  const handleExport = () => {
    const params = new URLSearchParams()
    if (keyword) params.set('keyword', keyword)
    if (poolId) params.set('pool_id', poolId)
    const qs = params.toString()
    downloadFile(
      `/api/v1/customers/pool/export/excel${qs ? `?${qs}` : ''}`,
      `customer_pool_${new Date().toISOString().slice(0, 10)}.xlsx`,
    )
  }

  const changePool = (v?: string) => {
    setPoolId(v || undefined)
    setPage(1)  // fetch 由 [page, poolId] effect 统一触发
  }

  const poolFilterOptions = [
    { label: '全部公海', value: '' },
    { label: `默认公海 (${defaultCount})`, value: '__default__' },
    ...pools.map(p => ({ label: `${p.name} (${p.customer_count || 0})`, value: p.id })),
  ]

  const columns: ColumnsType<Customer> = [
    { title: '客户名称', dataIndex: 'name', width: 200,
      render: (v, r) => (
        <a className="font-semibold text-primary" onClick={() => navigate(`/customers/${r.id}`)}>{v}</a>
      ) },
    { title: '级别', dataIndex: 'level', width: 60,
      render: (v) => v ? <Tag color={customerLevelColors[v] || 'default'}>{v}</Tag> : '-' },
    { title: '采购意向', dataIndex: 'intent_level', width: 92,
      render: (v) => v ? <Tag color={intentLevelColors[v] || 'default'} className="m-0">{intentLevelShortLabels[v] || v}</Tag> : <span className="text-slate-300">-</span> },
    { title: '行业', dataIndex: 'industry', width: 130,
      render: (v) => v ? (industryMap[v] || v) : <span className="text-slate-300">-</span> },
    { title: '地区', dataIndex: 'region', width: 100,
      render: (_, r) => [r.province, r.city, r.district].filter(Boolean).join('·') || r.region || '-' },
    { title: '来源', dataIndex: 'source', width: 80 },
    { title: '入池方式', dataIndex: 'pool_source', width: 90,
      render: (v) => v ? <Tag className="m-0">{poolSourceLabels[v] || v}</Tag> : <span className="text-slate-300">-</span> },
    { title: '进入公海', dataIndex: 'pool_entered_at', width: 150,
      render: (v, r) => {
        const when = v || r.updated_at
        const d = daysSince(when)
        return (
          <Tooltip title={when ? new Date(when).toLocaleString('zh-CN') : ''}>
            <span className="text-sm text-slate-600">{when ? new Date(when).toLocaleDateString('zh-CN') : '-'}</span>
            {d != null && <span className="text-xs text-slate-400 ml-1">({d}天)</span>}
          </Tooltip>
        )
      } },
    { title: '操作', key: 'actions', width: 160, fixed: 'right',
      render: (_, r) => (
        <Space size={4}>
          <Button type="primary" size="small" onClick={() => handleClaim(r.id, r.name)}>领取</Button>
          {canDelete && <Button size="small" danger onClick={() => handleDelete(r.id, r.name)}>删除</Button>}
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
          {canManage && <Button icon={<SettingOutlined />} onClick={() => setPoolSettingsOpen(true)}>公海设置</Button>}
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
          <span className="text-sm text-slate-500">当前列表</span>
          <span className="ml-2 text-lg font-black text-slate-900">{total}</span>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Input.Search placeholder="搜索客户名称" value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onSearch={handleSearch} enterButton style={{ width: 280 }} allowClear />
        <Select placeholder="按区域公海筛选" style={{ width: 200 }} value={poolId ?? ''}
          onChange={changePool} options={poolFilterOptions} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small"
          scroll={{ x: 1100 }}
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
        onSuccess={() => { fetch(); fetchPools() }}
        previewUrl="/api/v1/customers/import/preview"
        importUrl="/api/v1/customers/import/excel?to_pool=true"
        templateUrl="/api/v1/customers/import/template"
        title="导入到公海"
        expectedHeaders={['客户名称', '简称', '行业', '规模', '区域', '地址', '来源', '级别']}
      />

      {canManage && (
        <PoolSettingsModal
          open={poolSettingsOpen}
          pools={pools}
          onClose={() => setPoolSettingsOpen(false)}
          onChanged={() => { fetchPools(); fetch() }}
        />
      )}
    </div>
  )
}

// ===== 区域公海设置（增删改，role:manage）=====
function PoolSettingsModal({ open, pools, onClose, onChanged }: {
  open: boolean; pools: PoolDef[]; onClose: () => void; onChanged: () => void
}) {
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<PoolDef | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const dangerConfirm = useCountdownConfirm()

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ is_default: false, enabled: true, idle_A: 90, idle_B: 60, idle_C: 30, idle_D: 15, default_idle_days: 30 })
    setFormOpen(true)
  }
  const openEdit = (p: PoolDef) => {
    setEditing(p)
    const r = p.rules_json || {}
    const idle = r.idle_days || {}
    form.setFieldsValue({
      name: p.name, description: p.description, region_scope: p.region_scope, is_default: p.is_default,
      enabled: !!r.enabled, idle_A: idle.A ?? 90, idle_B: idle.B ?? 60, idle_C: idle.C ?? 30, idle_D: idle.D ?? 15,
      default_idle_days: r.default_idle_days ?? 30,
    })
    setFormOpen(true)
  }
  const save = async () => {
    const v = await form.validateFields()
    setSaving(true)
    try {
      const payload = {
        name: v.name, description: v.description, region_scope: v.region_scope, is_default: v.is_default,
        rules_json: {
          enabled: v.enabled,
          idle_days: { A: v.idle_A, B: v.idle_B, C: v.idle_C, D: v.idle_D },
          default_idle_days: v.default_idle_days,
        },
      }
      if (editing) await customerPoolApi.update(editing.id, payload)
      else await customerPoolApi.create(payload)
      message.success('已保存')
      setFormOpen(false)
      onChanged()
    } catch { message.error('保存失败') } finally { setSaving(false) }
  }
  const remove = (p: PoolDef) => dangerConfirm({
    title: '删除区域公海',
    content: `「${p.name}」删除后，归属该公海的客户将回落默认公海（不会丢失）。`,
    okText: '删除', countdown: 3,
    onOk: async () => { await customerPoolApi.delete(p.id); message.success('已删除'); onChanged() },
  })

  const poolColumns: ColumnsType<PoolDef> = [
    { title: '名称', dataIndex: 'name',
      render: (v, r) => <span>{v}{r.is_default && <Tag color="blue" className="ml-1">默认</Tag>}{!r.is_active && <Tag className="ml-1">停用</Tag>}</span> },
    { title: '覆盖区域(编码前缀)', dataIndex: 'region_scope', render: (v) => v || <span className="text-slate-300">兜底</span> },
    { title: '自动回收', key: 'rules',
      render: (_, r) => {
        const rr = r.rules_json
        return rr?.enabled
          ? <span className="text-xs text-slate-600">A{rr.idle_days?.A}/B{rr.idle_days?.B}/C{rr.idle_days?.C}/D{rr.idle_days?.D} 天</span>
          : <span className="text-slate-300">关闭</span>
      } },
    { title: '客户数', dataIndex: 'customer_count', width: 70 },
    { title: '', key: 'act', width: 110,
      render: (_, r) => (
        <Space size={6}>
          <a onClick={() => openEdit(r)}>编辑</a>
          <a className="text-rose-500" onClick={() => remove(r)}>删除</a>
        </Space>
      ) },
  ]

  return (
    <Modal title="区域公海设置" open={open} onCancel={onClose} footer={null} width={760}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-500">按区域/团队拆分公海；释放或系统回收时，按客户地区编码前缀自动归入匹配公海，无匹配则进默认公海。</span>
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreate}>新增公海</Button>
      </div>
      <Table rowKey="id" size="small" pagination={false} dataSource={pools} columns={poolColumns} />

      <Modal title={editing ? '编辑公海' : '新增公海'} open={formOpen} onOk={save} confirmLoading={saving}
        onCancel={() => setFormOpen(false)} okText="保存" destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="公海名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如：华东区公海 / 总部公海" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="region_scope" label="覆盖行政区划编码前缀"
            tooltip="逗号分隔，如 31,32,33；释放/回收时按客户地区自动归入此公海。留空表示兜底公海">
            <Input placeholder="31,32,33（留空为兜底）" />
          </Form.Item>
          <div className="grid grid-cols-2 gap-x-4">
            <Form.Item name="is_default" label="设为默认公海" valuePropName="checked"
              tooltip="无区域匹配的客户归入默认公海（全租户仅一个）">
              <Switch />
            </Form.Item>
            <Form.Item name="enabled" label="启用自动回收" valuePropName="checked">
              <Switch />
            </Form.Item>
          </div>
          <div className="text-xs text-slate-400 mb-2">各价值等级闲置多少天无跟进则自动回收到本公海：</div>
          <div className="grid grid-cols-4 gap-x-2">
            <Form.Item name="idle_A" label="A(天)"><InputNumber min={1} className="w-full" /></Form.Item>
            <Form.Item name="idle_B" label="B(天)"><InputNumber min={1} className="w-full" /></Form.Item>
            <Form.Item name="idle_C" label="C(天)"><InputNumber min={1} className="w-full" /></Form.Item>
            <Form.Item name="idle_D" label="D(天)"><InputNumber min={1} className="w-full" /></Form.Item>
          </div>
          <Form.Item name="default_idle_days" label="其他/未分级(天)">
            <InputNumber min={1} className="w-full" style={{ maxWidth: 160 }} />
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  )
}
