import { useState, useEffect, useRef } from 'react'
import { Table, Input, Select, Tag, Button, Modal, Form, Switch, Space, Popconfirm, Alert, message } from 'antd'
import { SearchOutlined, PhoneOutlined, MailOutlined, PlusOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { contactApi } from '@/api/contact'
import { customerApi } from '@/api/customer'
import { useAuthStore } from '@/stores/useAuthStore'
import type { Contact } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePageSize } from '@/hooks/usePageSize'

const roleTypeLabels: Record<string, string> = {
  decision_maker: '决策人',
  influencer: '影响者',
  user: '使用者',
  finance: '财务',
  procurement: '采购',
}
const roleTypeColors: Record<string, string> = {
  decision_maker: 'red',
  influencer: 'orange',
  user: 'blue',
  finance: 'green',
  procurement: 'purple',
}

type ContactItem = Contact & { customer_name?: string }

export default function ContactList() {
  usePageTitle('联系人')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const [data, setData] = useState<ContactItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [roleType, setRoleType] = useState<string | undefined>()
  const [pageSize, setPageSize] = usePageSize('contacts')

  // Create modal state
  const [createModal, setCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()
  const [customerOptions, setCustomerOptions] = useState<{ label: string; value: string }[]>([])
  const [customerSearching, setCustomerSearching] = useState(false)

  // Import modal state
  const [importModal, setImportModal] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ success: number; failed: number; total: number; errors: { row: number; reason: string }[] } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchData = async (page = pageNo, kw = keyword, rt = roleType) => {
    setLoading(true)
    try {
      const res = await contactApi.listAll({
        pageNo: page, pageSize,
        keyword: kw || undefined, role_type: rt,
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => { setPageNo(1); fetchData(1) }

  // Customer search for create modal
  const searchCustomers = async (kw: string) => {
    if (!kw || kw.length < 1) return
    setCustomerSearching(true)
    try {
      const res = await customerApi.list({ pageNo: 1, pageSize: 20, keyword: kw })
      setCustomerOptions(res.data.items.map((c) => ({ label: c.name, value: c.id })))
    } finally {
      setCustomerSearching(false)
    }
  }

  // Create contact
  const handleCreate = async () => {
    const values = await form.validateFields()
    setCreating(true)
    try {
      const { customer_id, ...contactData } = values
      await contactApi.create(customer_id, contactData)
      message.success('联系人已创建')
      setCreateModal(false)
      form.resetFields()
      fetchData()
    } catch {
      message.error('创建失败')
    } finally {
      setCreating(false)
    }
  }

  // Delete contact
  const handleDelete = async (customerId: string, contactId: string) => {
    try {
      await contactApi.delete(customerId, contactId)
      message.success('联系人已删除')
      fetchData()
    } catch {
      message.error('删除失败')
    }
  }

  // Import
  const openImportModal = () => {
    setImportFile(null)
    setImportResult(null)
    setImportModal(true)
  }

  const handleImport = async () => {
    if (!importFile) { message.warning('请选择CSV文件'); return }
    setImporting(true)
    setImportResult(null)
    try {
      const res = await contactApi.importCsv(importFile)
      setImportResult(res.data)
      if (res.data.errors.length === 0) {
        message.success(`成功导入 ${res.data.success} 个联系人`)
        setImportModal(false)
        setImportFile(null)
        fetchData()
      }
    } catch {
      message.error('导入失败')
    } finally {
      setImporting(false)
    }
  }

  const columns: ColumnsType<ContactItem> = [
    {
      title: '姓名', dataIndex: 'name', width: 150,
      render: (v: string, r) => (
        <span className="font-semibold text-slate-800">{v}{r.is_primary && <Tag color="gold" className="ml-1 text-[10px]">主联系人</Tag>}</span>
      ),
    },
    { title: '职位', dataIndex: 'title', width: 120, render: (v: string) => v || '-' },
    {
      title: '角色', dataIndex: 'role_type', width: 100,
      render: (v: string) => v ? <Tag color={roleTypeColors[v]}>{roleTypeLabels[v] || v}</Tag> : '-',
    },
    {
      title: '所属客户', dataIndex: 'customer_name', width: 180,
      render: (v: string, r) => (
        <a className="text-primary cursor-pointer" onClick={() => navigate(`/customers/${r.customer_id}`)}>{v || '-'}</a>
      ),
    },
    {
      title: '电话', key: 'phone', width: 150,
      render: (_, r) => (
        <span className="text-slate-600">
          {r.mobile && <span><PhoneOutlined className="mr-1" />{r.mobile}</span>}
          {!r.mobile && r.phone && <span><PhoneOutlined className="mr-1" />{r.phone}</span>}
          {!r.mobile && !r.phone && '-'}
        </span>
      ),
    },
    {
      title: '邮箱', dataIndex: 'email', width: 200,
      render: (v: string) => v ? <span><MailOutlined className="mr-1 text-slate-400" />{v}</span> : '-',
    },
    { title: '备注', dataIndex: 'remark', ellipsis: true },
    ...(hasPermission('contact:delete') ? [{
      title: '', width: 80, key: 'actions',
      render: (_: unknown, record: ContactItem) => (
        <Popconfirm
          title="确认删除该联系人？"
          description="删除后不可恢复"
          okText="删除"
          okButtonProps={{ danger: true }}
          cancelText="取消"
          onConfirm={() => handleDelete(record.customer_id, record.id)}
        >
          <a className="text-red-500 text-xs font-bold uppercase tracking-widest"><DeleteOutlined /> 删除</a>
        </Popconfirm>
      ),
    } as ColumnsType<ContactItem>[number]] : []),
  ]

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">联系人管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">跨客户搜索和管理所有联系人</p>
        </div>
        <Space>
          {hasPermission('contact:create') && (
            <Button icon={<UploadOutlined />} onClick={openImportModal}>导入</Button>
          )}
          {hasPermission('contact:create') && (
            <Button type="primary" icon={<PlusOutlined />}
              onClick={() => { form.resetFields(); setCustomerOptions([]); setCreateModal(true) }}
              className="shadow-lg shadow-primary/20 font-bold">
              新建联系人
            </Button>
          )}
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="搜索姓名/电话/邮箱..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
          />
          <Select
            placeholder="角色类型"
            allowClear
            style={{ width: 140 }}
            value={roleType}
            onChange={(v) => { setRoleType(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(roleTypeLabels).map(([k, v]) => ({ label: v, value: k }))}
          />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 900 }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (t) => `共 ${t} 条`,
            showSizeChanger: true, pageSizeOptions: ['20', '50', '100'],
            onChange: (p) => { setPageNo(p); fetchData(p) },
            onShowSizeChange: (_current, size) => { setPageSize(size); setPageNo(1); fetchData(1) },
          }}
        />
      </div>

      {/* Create Contact Modal */}
      <Modal
        title="新建联系人"
        open={createModal}
        onOk={handleCreate}
        onCancel={() => { setCreateModal(false); form.resetFields() }}
        confirmLoading={creating}
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="customer_id" label="所属客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select
              showSearch
              placeholder="搜索并选择客户"
              filterOption={false}
              onSearch={searchCustomers}
              loading={customerSearching}
              options={customerOptions}
              notFoundContent={customerSearching ? '搜索中...' : '请输入客户名称搜索'}
            />
          </Form.Item>
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item name="title" label="职位">
            <Input placeholder="请输入职位" />
          </Form.Item>
          <Form.Item name="role_type" label="角色类型">
            <Select
              placeholder="选择角色类型"
              allowClear
              options={Object.entries(roleTypeLabels).map(([k, v]) => ({ label: v, value: k }))}
            />
          </Form.Item>
          <Form.Item name="phone" label="电话">
            <Input placeholder="请输入电话" />
          </Form.Item>
          <Form.Item name="mobile" label="手机">
            <Input placeholder="请输入手机号" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item name="is_primary" label="主联系人" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea placeholder="请输入备注" rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Modal */}
      <Modal
        title="批量导入联系人"
        open={importModal}
        onOk={handleImport}
        onCancel={() => { setImportModal(false); setImportFile(null); setImportResult(null) }}
        okText="开始导入"
        confirmLoading={importing}
        width={520}
      >
        <div className="space-y-4">
          <div className="text-sm text-slate-500">
            请上传CSV文件，文件需包含以下列（第一行为标题行）：
            <div className="mt-2 bg-slate-50 rounded p-2 text-xs font-mono text-slate-700 break-all">
              customer_name, name, title, role_type, phone, mobile, email, is_primary, remark
            </div>
            <div className="mt-1 text-xs text-slate-400">
              customer_name 必须与系统中客户名称完全匹配；role_type 可选值：decision_maker, influencer, user, finance, procurement；is_primary 可填 true/1/是
            </div>
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) { setImportFile(f); setImportResult(null) }
              }}
            />
            <Button icon={<UploadOutlined />} onClick={() => fileInputRef.current?.click()}>
              选择CSV文件
            </Button>
            {importFile && (
              <span className="ml-2 text-sm text-slate-600">{importFile.name}</span>
            )}
          </div>
          {importResult && (
            <div className="space-y-2">
              <Alert
                type={importResult.errors.length === 0 ? 'success' : 'warning'}
                message={`导入完成：成功 ${importResult.success} 条，失败 ${importResult.failed} 条`}
                showIcon
              />
              {importResult.errors.length > 0 && (
                <div className="max-h-40 overflow-y-auto bg-red-50 rounded p-2">
                  {importResult.errors.map((f, i) => (
                    <div key={i} className="text-xs text-red-600">第 {f.row} 行：{f.reason}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
