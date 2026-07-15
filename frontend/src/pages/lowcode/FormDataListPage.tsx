// 扩展平台 → 表单数据列表: 某模板的填报记录(看/改/删 + 去填报)。
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Table, Button, Space, Tag, Modal, message, Popconfirm, Typography,
} from 'antd'
import { ArrowLeftOutlined, PlusOutlined, DownloadOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import { downloadFile } from '@/utils/download'
import type { FieldDefinition, FormRule, FormInstance } from '@/types/lowcode'
import FormRenderer, { validateRequired } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'

const { Title } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

function cellText(field: FieldDefinition, v: unknown): string {
  if (v == null || v === '') return '—'
  const opts = field.options || []
  const labelOf = (x: unknown) => opts.find((o) => o.value === x)?.label ?? String(x)
  if (Array.isArray(v)) return v.map(labelOf).join('，')
  if (field.type === 'select' || field.type === 'radio') return labelOf(v)
  if (field.type === 'switch') return v ? '是' : '否'
  if (field.type === 'detail_table') return `${(v as unknown[]).length} 行`
  if (field.type === 'amount') return `¥${Number(v).toFixed(2)}`
  return String(v)
}

export default function FormDataListPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [colFields, setColFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [items, setItems] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [viewRec, setViewRec] = useState<{ fields: FieldDefinition[]; value: Record<string, unknown>; readonly: boolean; id: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await lowcodeApi.listInstances({ template_id: id, pageNo, pageSize: 20 })
      setItems(res.data.items)
      setTotal(res.data.total)
    } finally { setLoading(false) }
  }, [id, pageNo])

  useEffect(() => {
    (async () => {
      const tpl = await lowcodeApi.getTemplate(id)
      setName(tpl.data.name)
      try {
        const ver = await lowcodeApi.publishedVersion(id)
        const fs = (ver.data.field_definitions as FieldDefinition[]) || []
        setColFields(fs.filter((f) => f.type !== 'formula').slice(0, 4).concat(fs.filter((f) => f.type === 'formula').slice(0, 1)))
        setRules((ver.data.rule_definitions as FormRule[]) || [])
      } catch { /* 未发布 */ }
    })()
  }, [id])
  useEffect(() => { load() }, [load])

  const openView = async (recId: string, readonly: boolean) => {
    const res = await lowcodeApi.getInstance(recId)
    setViewRec({ fields: res.data.field_definitions, value: res.data.form_data, readonly, id: recId })
  }

  const saveEdit = async () => {
    if (!viewRec) return
    const states = computeFieldStates(viewRec.fields, viewRec.value, rules)
    const e = validateRequired(viewRec.fields, states, viewRec.value)
    if (e) { message.error(e); return }
    await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
    message.success('已保存')
    setViewRec(null)
    load()
  }

  const del = async (recId: string) => {
    await lowcodeApi.deleteInstance(recId)
    message.success('已删除')
    load()
  }

  const columns = [
    { title: '单号', dataIndex: 'business_no', key: 'business_no', render: (v: string) => v || '—' },
    { title: '标题', dataIndex: 'title', key: 'title', render: (v: string) => v || '—' },
    ...colFields.map((f) => ({
      title: f.label, key: f.id,
      render: (_: unknown, r: FormInstance) => cellText(f, r.form_data?.[f.id]),
    })),
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => { const t = STATUS_TAG[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> },
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    {
      title: '操作', key: 'op', width: 200,
      render: (_: unknown, r: FormInstance) => (
        <Space size="small">
          <Button size="small" type="link" onClick={() => openView(r.id, true)}>查看</Button>
          <Button size="small" type="link" onClick={() => openView(r.id, false)}>编辑</Button>
          <Popconfirm title="确认删除该记录?" onConfirm={() => del(r.id)}>
            <Button size="small" type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>{name} · 数据</Title>
        </Space>
        <Space>
          <Button icon={<DownloadOutlined />} disabled={total === 0}
            onClick={() => downloadFile(`/api/v1/lc/form-instances/export?template_id=${encodeURIComponent(id)}`, `${name || '表单数据'}.xlsx`)}>
            导出
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav(`/lowcode/forms/${id}/fill`)}>新增填报</Button>
        </Space>
      </div>
      <Table
        rowKey="id" loading={loading} columns={columns} dataSource={items}
        pagination={{ current: pageNo, total, pageSize: 20, onChange: setPageNo, showSizeChanger: false }}
      />

      <Modal
        title={viewRec?.readonly ? '查看记录' : '编辑记录'} open={!!viewRec} width={780}
        onCancel={() => setViewRec(null)}
        footer={viewRec?.readonly ? null : [
          <Button key="c" onClick={() => setViewRec(null)}>取消</Button>,
          <Button key="s" type="primary" onClick={saveEdit}>保存</Button>,
        ]}
        destroyOnClose
      >
        {viewRec && (
          <FormRenderer
            fields={viewRec.fields} rules={rules}
            mode={viewRec.readonly ? 'readonly' : 'edit'}
            value={viewRec.value}
            onChange={(v) => setViewRec((s) => (s ? { ...s, value: v } : s))}
          />
        )}
      </Modal>
    </Card>
  )
}
