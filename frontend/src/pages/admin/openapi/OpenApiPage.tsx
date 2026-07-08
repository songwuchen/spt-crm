import { useEffect, useState } from 'react'
import {
  Tabs, Table, Button, Modal, Form, Input, InputNumber, Select, Tag, Space,
  Popconfirm, Alert, Typography, message, Collapse,
} from 'antd'
import { usePageTitle } from '@/hooks/usePageTitle'
import { openApiApi } from '@/api/openapi'

const { Paragraph, Text } = Typography

interface AppRow {
  id: string
  app_key: string
  name: string
  app_type: string
  auth_mode: string
  status: string
  scopes: string[]
  secret_prefix?: string
  rate_limit_per_minute: number
  ip_whitelist: string[]
  remark?: string
  created_at?: string
}

const STATUS_COLOR: Record<string, string> = { enabled: 'green', disabled: 'red' }
const METHOD_COLOR: Record<string, string> = { GET: 'blue', POST: 'green', PUT: 'orange', DELETE: 'red' }

// ============================================================== Apps tab
function AppsTab() {
  const [rows, setRows] = useState<AppRow[]>([])
  const [scopes, setScopes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AppRow | null>(null)
  const [secret, setSecret] = useState<{ app_key: string; secret: string } | null>(null)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res: any = await openApiApi.listApps()
      setRows(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    openApiApi.listScopes().then((res: any) => setScopes(res.data || []))
  }, [])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ auth_mode: 'apikey', rate_limit_per_minute: 600, scopes: [] })
    setModalOpen(true)
  }

  const openEdit = (row: AppRow) => {
    setEditing(row)
    form.setFieldsValue({
      name: row.name,
      status: row.status,
      auth_mode: row.auth_mode,
      scopes: row.scopes || [],
      rate_limit_per_minute: row.rate_limit_per_minute,
      ip_whitelist: (row.ip_whitelist || []).join('\n'),
      remark: row.remark,
    })
    setModalOpen(true)
  }

  const submit = async () => {
    const v = await form.validateFields()
    const ipList = (v.ip_whitelist || '')
      .split('\n').map((s: string) => s.trim()).filter(Boolean)
    const payload: Record<string, unknown> = {
      name: v.name,
      auth_mode: v.auth_mode,
      scopes: v.scopes || [],
      rate_limit_per_minute: v.rate_limit_per_minute,
      ip_whitelist: ipList,
      remark: v.remark,
    }
    if (editing) {
      payload.status = v.status
      await openApiApi.updateApp(editing.id, payload)
      message.success('已更新应用')
    } else {
      const res: any = await openApiApi.createApp(payload)
      setSecret({ app_key: res.data.app_key, secret: res.data.secret })
    }
    setModalOpen(false)
    load()
  }

  const regenerate = async (row: AppRow) => {
    const res: any = await openApiApi.regenerateSecret(row.id)
    setSecret({ app_key: res.data.app_key, secret: res.data.secret })
    load()
  }

  const remove = async (row: AppRow) => {
    await openApiApi.deleteApp(row.id)
    message.success('已删除应用')
    load()
  }

  const columns = [
    { title: '名称', dataIndex: 'name' },
    { title: 'App ID', dataIndex: 'app_key', render: (v: string) => <code className="text-xs">{v}</code> },
    {
      title: '认证方式', dataIndex: 'auth_mode',
      render: (v: string) => <Tag>{v === 'hmac' ? 'HMAC 签名' : 'API Key'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status',
      render: (v: string) => <Tag color={STATUS_COLOR[v]}>{v === 'enabled' ? '启用' : '停用'}</Tag>,
    },
    {
      title: '权限范围', dataIndex: 'scopes',
      render: (v: string[]) => <span className="text-xs text-slate-500">{(v || []).length} 个</span>,
    },
    { title: '密钥', dataIndex: 'secret_prefix', render: (v: string) => <code className="text-xs">{v}…</code> },
    { title: '限流/分钟', dataIndex: 'rate_limit_per_minute' },
    {
      title: '操作', key: 'action', width: 220,
      render: (_: unknown, row: AppRow) => (
        <Space size="small">
          <Button size="small" onClick={() => openEdit(row)}>编辑</Button>
          <Popconfirm title="重置密钥后旧密钥立即失效，确定？" onConfirm={() => regenerate(row)}>
            <Button size="small">重置密钥</Button>
          </Popconfirm>
          <Popconfirm title="确定删除该应用？" onConfirm={() => remove(row)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button type="primary" onClick={openCreate}>新建应用</Button>
      </div>
      <Table rowKey="id" loading={loading} dataSource={rows} columns={columns} size="small" pagination={false} />

      <Modal
        title={editing ? '编辑应用' : '新建应用'}
        open={modalOpen}
        onOk={submit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="应用名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：金蝶 K3 对接" />
          </Form.Item>
          <Form.Item name="auth_mode" label="认证方式" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'apikey', label: 'API Key（X-API-Key，简单）' },
                { value: 'hmac', label: 'HMAC 签名（X-App-Id + 签名，更安全）' },
              ]}
            />
          </Form.Item>
          {editing && (
            <Form.Item name="status" label="状态">
              <Select options={[{ value: 'enabled', label: '启用' }, { value: 'disabled', label: '停用' }]} />
            </Form.Item>
          )}
          <Form.Item name="scopes" label="权限范围 (Scope)" rules={[{ required: true, message: '至少选择一个范围' }]}>
            <Select mode="multiple" placeholder="选择该应用可访问的资源" options={scopes.map((s) => ({ value: s, label: s }))} />
          </Form.Item>
          <Form.Item name="rate_limit_per_minute" label="每分钟限流">
            <InputNumber min={1} max={100000} className="w-full" />
          </Form.Item>
          <Form.Item name="ip_whitelist" label="IP 白名单（每行一个 CIDR，留空不限制）">
            <Input.TextArea rows={2} placeholder={'10.0.0.0/8\n203.0.113.5/32'} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="密钥已生成（仅显示一次）"
        open={!!secret}
        onCancel={() => setSecret(null)}
        footer={<Button type="primary" onClick={() => setSecret(null)}>我已保存</Button>}
      >
        <Alert
          type="warning" showIcon className="mb-3"
          message="请立即复制并妥善保存。关闭后将无法再次查看，只能重置生成新密钥。"
        />
        <div className="mb-2"><Text type="secondary">App ID</Text></div>
        <Paragraph copyable className="bg-slate-50 p-2 rounded"><code>{secret?.app_key}</code></Paragraph>
        <div className="mb-2"><Text type="secondary">Secret / API Key</Text></div>
        <Paragraph copyable className="bg-slate-50 p-2 rounded"><code>{secret?.secret}</code></Paragraph>
      </Modal>
    </div>
  )
}

// ========================================================= Call logs tab
function CallLogsTab() {
  const [rows, setRows] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const load = async (p = page) => {
    setLoading(true)
    try {
      const res: any = await openApiApi.listCallLogs({ page: p, page_size: 20 })
      setRows(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(1) }, [])

  const columns = [
    { title: '时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '' },
    { title: 'App ID', dataIndex: 'app_key', render: (v: string) => <code className="text-xs">{v}</code> },
    { title: '方法', dataIndex: 'method', render: (v: string) => <Tag color={METHOD_COLOR[v]}>{v}</Tag> },
    { title: '路径', dataIndex: 'path', render: (v: string) => <code className="text-xs">{v}</code> },
    {
      title: '状态', dataIndex: 'status_code',
      render: (v: number, r: any) => (
        <Tag color={v && v < 400 ? 'green' : 'red'}>{v}{r.error_code ? ` ${r.error_code}` : ''}</Tag>
      ),
    },
    { title: '耗时(ms)', dataIndex: 'duration_ms' },
    { title: '来源 IP', dataIndex: 'client_ip' },
  ]

  return (
    <Table
      rowKey="id" loading={loading} dataSource={rows} columns={columns} size="small"
      pagination={{ current: page, total, pageSize: 20, onChange: (p) => { setPage(p); load(p) }, showSizeChanger: false }}
    />
  )
}

// ============================================= Failed-event redeliver
function FailedEventsSection() {
  const [rows, setRows] = useState<any[]>([])
  const [status, setStatus] = useState<string>('failed')
  const [loading, setLoading] = useState(false)

  const load = async (s = status) => {
    setLoading(true)
    try {
      const res: any = await openApiApi.listEvents({ status: s, page_size: 50 })
      setRows(res.data?.items || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load('failed') }, [])

  const redeliver = async (id: string) => {
    await openApiApi.redeliverEvent(id)
    message.success('已重新入队，稍后由投递服务重试')
    load()
  }

  const columns = [
    { title: '时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '' },
    { title: '事件', dataIndex: 'event_type', render: (v: string) => <code className="text-xs">{v}</code> },
    {
      title: '状态', dataIndex: 'status',
      render: (v: string) => <Tag color={v === 'failed' ? 'red' : v === 'published' ? 'green' : 'orange'}>{v === 'published' ? '已推送' : v === 'failed' ? '失败' : v === 'pending' ? '待推送' : v}</Tag>,
    },
    { title: '重试次数', dataIndex: 'retry_count' },
    { title: '错误', dataIndex: 'error_message', ellipsis: true, render: (v: string) => <span className="text-xs text-slate-500">{v}</span> },
    {
      title: '操作', key: 'action', width: 110,
      render: (_: unknown, r: any) => (
        <Popconfirm title="重新投递该事件？" onConfirm={() => redeliver(r.id)}>
          <Button size="small">重新投递</Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-bold text-slate-800">事件投递</h3>
        <Select
          size="small" value={status} style={{ width: 140 }}
          onChange={(v) => { setStatus(v); load(v) }}
          options={[
            { value: 'failed', label: '投递失败' },
            { value: 'pending', label: '待投递' },
            { value: 'published', label: '已投递' },
          ]}
        />
      </div>
      <Table rowKey="id" loading={loading} dataSource={rows} columns={columns} size="small"
             pagination={{ pageSize: 10 }} />
    </div>
  )
}

// ========================================================== Webhooks tab
function WebhooksTab() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res: any = await openApiApi.listWebhooks()
      setRows(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const submit = async () => {
    const v = await form.validateFields()
    const types = (v.event_types || '').split(',').map((s: string) => s.trim()).filter(Boolean)
    await openApiApi.createWebhook({
      target_url: v.target_url,
      event_types_json: types.length ? types : ['*'],
      secret_token: v.secret_token || undefined,
    })
    message.success('已创建订阅')
    setModalOpen(false)
    form.resetFields()
    load()
  }

  const remove = async (id: string) => {
    await openApiApi.deleteWebhook(id)
    message.success('已删除')
    load()
  }

  const testPush = async (id: string) => {
    const res: any = await openApiApi.testWebhook(id)
    const r = res.data || {}
    Modal[r.success ? 'success' : 'error']({
      title: r.success ? '测试推送成功' : '测试推送失败',
      content: (
        <div className="text-sm">
          <div>HTTP 状态码：{r.status_code}</div>
          <div className="mt-1 break-all text-slate-500">响应：{r.response_body || '(空)'}</div>
        </div>
      ),
    })
  }

  const columns = [
    { title: '回调地址', dataIndex: 'target_url', render: (v: string) => <code className="text-xs">{v}</code> },
    {
      title: '订阅事件', dataIndex: 'event_types_json',
      render: (v: any) => Array.isArray(v) ? v.map((t) => <Tag key={t}>{t}</Tag>) : <Tag>*</Tag>,
    },
    { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '启用' : v === 'inactive' ? '停用' : v}</Tag> },
    {
      title: '操作', key: 'action', width: 160,
      render: (_: unknown, r: any) => (
        <Space size="small">
          <Button size="small" onClick={() => testPush(r.id)}>测试推送</Button>
          <Popconfirm title="确定删除该订阅？" onConfirm={() => remove(r.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Alert
        type="info" showIcon className="mb-3"
        message="当订阅的事件产生时，系统会向回调地址 POST 事件内容，并在 X-Webhook-Signature 头中带上 HMAC-SHA256 签名（密钥为下方 Secret）。Webhook 非 100% 可靠，请配合 GET /openapi/v1/events 拉取对账。"
      />
      <div className="mb-3 flex justify-end">
        <Button type="primary" onClick={() => setModalOpen(true)}>新建订阅</Button>
      </div>
      <Table rowKey="id" loading={loading} dataSource={rows} columns={columns} size="small" pagination={false} />

      <FailedEventsSection />

      <Modal title="新建 Webhook 订阅" open={modalOpen} onOk={submit} onCancel={() => setModalOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="target_url" label="回调地址" rules={[{ required: true, message: '请输入回调 URL' }]}>
            <Input placeholder="https://your-system.com/webhooks/crm" />
          </Form.Item>
          <Form.Item name="event_types" label="订阅事件（逗号分隔，留空订阅全部）">
            <Input placeholder="crm.contract.signed, crm.payment.received" />
          </Form.Item>
          <Form.Item name="secret_token" label="签名密钥 Secret（用于校验 X-Webhook-Signature）">
            <Input placeholder="可选，建议填写" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ============================================================== Docs tab
const SCOPE_DESC: { scope: string; desc: string }[] = [
  { scope: 'crm.customer.read', desc: '读取客户' },
  { scope: 'crm.contact.read', desc: '读取联系人' },
  { scope: 'crm.project.read', desc: '读取商机项目' },
  { scope: 'crm.contract.read', desc: '读取合同' },
  { scope: 'crm.quote.read', desc: '读取报价' },
  { scope: 'crm.order.read', desc: '读取订单' },
  { scope: 'crm.payment.read', desc: '读取回款记录' },
  { scope: 'crm.product.read', desc: '读取产品' },
  { scope: 'crm.service.read', desc: '读取售后工单' },
  { scope: 'crm.delivery.read', desc: '读取交付里程碑' },
  { scope: 'crm.event.read', desc: '拉取业务事件' },
  { scope: 'crm.lead.write', desc: '创建/转化/废弃线索（写入，需 Idempotency-Key）' },
  { scope: 'crm.activity.write', desc: '创建跟进/活动记录（写入）' },
  { scope: 'crm.customer.write', desc: '创建客户（写入）' },
  { scope: 'crm.service.write', desc: '创建售后工单（写入）' },
  { scope: 'crm.order.write', desc: '创建订单 / 写回订单状态（写入）' },
]

const ENDPOINTS = [
  { method: 'GET', path: '/openapi/v1/ping', desc: '鉴权连通性自检' },
  { method: 'GET', path: '/openapi/v1/customers', desc: '客户列表（keyword/status/customer_code/updated_since）' },
  { method: 'GET', path: '/openapi/v1/customers/{id}', desc: '客户详情' },
  { method: 'GET', path: '/openapi/v1/customers/{id}/contacts', desc: '客户联系人' },
  { method: 'GET', path: '/openapi/v1/contacts', desc: '联系人列表（customer_id）' },
  { method: 'GET', path: '/openapi/v1/projects', desc: '商机列表（customer_id/stage_code/status）' },
  { method: 'GET', path: '/openapi/v1/projects/{id}', desc: '商机详情' },
  { method: 'GET', path: '/openapi/v1/contracts', desc: '合同列表（project_id/status）' },
  { method: 'GET', path: '/openapi/v1/contracts/{id}', desc: '合同详情' },
  { method: 'GET', path: '/openapi/v1/quotes', desc: '报价列表（project_id/status）' },
  { method: 'GET', path: '/openapi/v1/quotes/{id}/lines', desc: '报价当前版本行项明细' },
  { method: 'GET', path: '/openapi/v1/quotes/{id}/versions', desc: '报价版本历史' },
  { method: 'GET', path: '/openapi/v1/contracts/{id}/versions', desc: '合同版本历史' },
  { method: 'GET', path: '/openapi/v1/projects/{id}/stage-history', desc: '商机阶段变更历史' },
  { method: 'GET', path: '/openapi/v1/orders', desc: '订单列表（customer_id/status）' },
  { method: 'GET', path: '/openapi/v1/payments', desc: '回款记录（project_id）' },
  { method: 'GET', path: '/openapi/v1/products', desc: '产品列表（keyword/is_active）' },
  { method: 'GET', path: '/openapi/v1/service-tickets', desc: '售后工单（customer_id/status）' },
  { method: 'GET', path: '/openapi/v1/milestones', desc: '交付里程碑（project_id）' },
  { method: 'GET', path: '/openapi/v1/events', desc: '事件拉取（游标 after_event_id + 时间范围）' },
  { method: 'GET', path: '/openapi/v1/events/{event_id}', desc: '单事件详情' },
  { method: 'POST', path: '/openapi/v1/leads', desc: '创建线索（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/leads/{id}/qualify', desc: '转化线索为客户（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/leads/{id}/discard', desc: '废弃线索（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/activities', desc: '创建跟进/活动（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/customers', desc: '创建客户（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/service-tickets', desc: '创建售后工单（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/orders', desc: '创建订单（需 Idempotency-Key）' },
  { method: 'POST', path: '/openapi/v1/orders/{id}/status', desc: '写回订单状态（需 Idempotency-Key）' },
]

const EVENTS = [
  'crm.customer.created', 'crm.lead.created', 'crm.project.stage_advanced',
  'crm.project.won', 'crm.project.lost', 'crm.contract.signed', 'crm.payment.received',
  'crm.service_ticket.created', 'crm.order.created', 'crm.order.status_changed',
]

function DocsTab() {
  return (
    <div className="space-y-4 max-w-4xl">
      <Alert
        type="success" showIcon
        message={(
          <span>
            机器可读规范：<a href="/openapi/v1/docs" target="_blank" rel="noreferrer">Swagger UI</a>
            {' / '}<a href="/openapi/v1/openapi.json" target="_blank" rel="noreferrer">openapi.json</a>
            （可导入 Postman/代码生成）。完整对接文档见 docs/product/开放平台API文档.md，下方为快速参考。
          </span>
        )}
      />
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="font-bold text-slate-800 mb-2">认证</h3>
        <p className="text-sm text-slate-600 mb-2">所有请求基址 <code className="bg-slate-100 px-1 rounded">/openapi/v1</code>，二选一：</p>
        <pre className="text-xs bg-slate-50 p-3 rounded overflow-x-auto">{`# 方式一：API Key
GET /openapi/v1/customers
X-API-Key: <secret>

# 方式二：HMAC 签名
X-App-Id: <app_key>
X-Timestamp: <unix 秒>
X-Signature: sha256=HMAC_SHA256(secret, "METHOD\\nPATH\\nQUERY\\nTIMESTAMP\\nSHA256(BODY)")`}</pre>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="font-bold text-slate-800 mb-2">统一响应</h3>
        <pre className="text-xs bg-slate-50 p-3 rounded overflow-x-auto">{`成功: { "code": 0, "message": "success", "traceId": "...", "data": { "items": [], "total": 0, "page": 1, "page_size": 20 } }
失败: { "code": 1, "error_code": "CRM_FORBIDDEN_SCOPE", "message": "...", "traceId": "...", "details": {} }`}</pre>
      </div>

      <Collapse
        items={[
          {
            key: 'scopes', label: <span className="font-bold">权限范围 Scope</span>,
            children: (
              <div className="space-y-1">
                {SCOPE_DESC.map((s) => (
                  <div key={s.scope} className="flex items-center gap-3 text-sm">
                    <code className="bg-slate-100 px-1 rounded">{s.scope}</code>
                    <span className="text-slate-500">{s.desc}</span>
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'endpoints', label: <span className="font-bold">接口列表</span>,
            children: (
              <div className="space-y-1">
                {ENDPOINTS.map((e) => (
                  <div key={e.path} className="flex items-center gap-3 py-1 text-sm border-b border-slate-50 last:border-0">
                    <Tag color={METHOD_COLOR[e.method]} className="font-mono text-[12px] min-w-[44px] text-center">{e.method}</Tag>
                    <code className="text-slate-700">{e.path}</code>
                    <span className="text-slate-500 ml-auto">{e.desc}</span>
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'events', label: <span className="font-bold">事件目录</span>,
            children: <div className="flex flex-wrap gap-2">{EVENTS.map((e) => <Tag key={e}>{e}</Tag>)}</div>,
          },
        ]}
      />
    </div>
  )
}

// ================================================================= Page
export default function OpenApiPage() {
  usePageTitle('开放平台')
  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">开放平台</h1>
        <p className="text-sm text-slate-500 mt-0.5">对外开放接口的应用、密钥、调用日志与 Webhook 订阅管理</p>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <Tabs
          items={[
            { key: 'apps', label: '应用与密钥', children: <AppsTab /> },
            { key: 'logs', label: '调用日志', children: <CallLogsTab /> },
            { key: 'webhooks', label: 'Webhook 订阅', children: <WebhooksTab /> },
            { key: 'docs', label: '接口说明', children: <DocsTab /> },
          ]}
        />
      </div>
    </div>
  )
}
