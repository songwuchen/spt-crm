// 扩展平台 → 表单设计器(Phase 1 精简版: 结构化字段编辑 + 实时预览 + 保存/发布)。
// 完整拖拽设计器为后续切片;此处提供可用的字段列表编辑 + 原始 JSON 高级编辑。
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Space, Input, Select, Switch, message, Row, Col, Divider, Modal,
  Typography, Tag, Drawer, Empty,
} from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, DeleteOutlined, PlusOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FieldType } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'

const { Title, Text } = Typography

const ADDABLE_TYPES: { value: FieldType; label: string }[] = [
  { value: 'text', label: '单行文本' }, { value: 'textarea', label: '多行文本' },
  { value: 'number', label: '数字' }, { value: 'amount', label: '金额' },
  { value: 'date', label: '日期' }, { value: 'datetime', label: '日期时间' },
  { value: 'select', label: '下拉单选' }, { value: 'multi_select', label: '下拉多选' },
  { value: 'radio', label: '单选框' }, { value: 'checkbox', label: '复选框' },
  { value: 'switch', label: '开关' }, { value: 'formula', label: '公式' },
  { value: 'auto_number', label: '流水号' }, { value: 'detail_table', label: '明细子表' },
  { value: 'person', label: '人员单选' }, { value: 'person_multi', label: '人员多选' },
  { value: 'department', label: '部门单选' }, { value: 'department_multi', label: '部门多选' },
  { value: 'file', label: '附件' }, { value: 'image', label: '图片' },
]
const CHOICE_TYPES = new Set(['select', 'multi_select', 'radio', 'checkbox'])

const genId = () => 'f' + Math.random().toString(36).slice(2, 9)

export default function FormDesignerPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [tplName, setTplName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [addType, setAddType] = useState<FieldType>('text')
  const [jsonOpen, setJsonOpen] = useState(false)
  const [jsonText, setJsonText] = useState('')
  const [optEditing, setOptEditing] = useState<{ idx: number; text: string } | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const [tpl, design] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.loadDesign(id)])
        setTplName(tpl.data.name)
        setFields((design.data.field_definitions as FieldDefinition[]) || [])
      } finally { setLoading(false) }
    })()
  }, [id])

  const addField = () => {
    const meta = ADDABLE_TYPES.find((t) => t.value === addType)!
    const f: FieldDefinition = { id: genId(), type: addType, label: meta.label, required: false, props: {} }
    if (CHOICE_TYPES.has(addType)) f.options = [{ label: '选项1', value: '选项1' }, { label: '选项2', value: '选项2' }]
    if (addType === 'detail_table') f.detail_table_columns = [{ id: genId(), type: 'text', label: '列1', required: false, props: {} }]
    setFields([...fields, f])
  }
  const patch = (idx: number, p: Partial<FieldDefinition>) => setFields(fields.map((f, i) => (i === idx ? { ...f, ...p } : f)))
  const remove = (idx: number) => setFields(fields.filter((_, i) => i !== idx))
  const move = (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= fields.length) return
    const next = [...fields]
    ;[next[idx], next[j]] = [next[j], next[idx]]
    setFields(next)
  }

  const openOptEditor = (idx: number) => {
    const f = fields[idx]
    const text = (f.options || []).map((o) => (o.label === o.value ? o.label : `${o.label}|${o.value}`)).join('\n')
    setOptEditing({ idx, text })
  }
  const saveOpts = () => {
    if (!optEditing) return
    const options = optEditing.text.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
      const [label, value] = l.split('|')
      return { label, value: (value ?? label).trim() }
    })
    patch(optEditing.idx, { options })
    setOptEditing(null)
  }

  const doSave = async (publish = false) => {
    // 校验字段 id 唯一 & 有 label
    const ids = new Set<string>()
    for (const f of fields) {
      if (!f.label?.trim()) return message.error('存在未命名字段')
      if (ids.has(f.id)) return message.error(`字段 id 重复: ${f.id}`)
      ids.add(f.id)
    }
    await lowcodeApi.saveDesign(id, { field_definitions: fields, layout_definition: {}, rule_definitions: [] })
    if (publish) {
      await lowcodeApi.publish(id)
      message.success('已发布')
      nav('/lowcode/forms')
    } else {
      message.success('草稿已保存')
    }
  }

  const openJson = () => { setJsonText(JSON.stringify(fields, null, 2)); setJsonOpen(true) }
  const applyJson = () => {
    try {
      const parsed = JSON.parse(jsonText)
      if (!Array.isArray(parsed)) throw new Error('根节点必须是数组')
      setFields(parsed)
      setJsonOpen(false)
      message.success('已应用 JSON')
    } catch (e) {
      message.error('JSON 解析失败: ' + (e as Error).message)
    }
  }

  if (loading) return <Card loading />

  const previewValue: Record<string, unknown> = {}

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>设计表单 · {tplName}</Title>
      </Space>
      <Space style={{ float: 'right' }}>
        <Button onClick={openJson}>高级(JSON)</Button>
        <Button onClick={() => doSave(false)}>保存草稿</Button>
        <Button type="primary" onClick={() => doSave(true)}>保存并发布</Button>
      </Space>

      <Row gutter={16}>
        <Col span={13}>
          <Card title="字段" size="small" extra={
            <Space>
              <Select size="small" style={{ width: 130 }} value={addType} onChange={(v) => setAddType(v)} options={ADDABLE_TYPES} />
              <Button size="small" type="primary" icon={<PlusOutlined />} onClick={addField}>添加字段</Button>
            </Space>
          }>
            {fields.length === 0 ? <Empty description="点击「添加字段」开始设计" /> : fields.map((f, idx) => (
              <div key={f.id} style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 10, marginBottom: 8 }}>
                <Row gutter={8} align="middle">
                  <Col flex="auto">
                    <Input size="small" value={f.label} onChange={(e) => patch(idx, { label: e.target.value })} addonBefore="标签" />
                  </Col>
                  <Col><Tag>{ADDABLE_TYPES.find((t) => t.value === f.type)?.label || f.type}</Tag></Col>
                </Row>
                <Row gutter={8} align="middle" style={{ marginTop: 6 }}>
                  <Col><Text type="secondary" style={{ fontSize: 12 }}>id: {f.id}</Text></Col>
                  <Col><Space size={4}><Text style={{ fontSize: 12 }}>必填</Text><Switch size="small" checked={!!f.required} onChange={(v) => patch(idx, { required: v })} /></Space></Col>
                  {CHOICE_TYPES.has(f.type) && <Col><Button size="small" onClick={() => openOptEditor(idx)}>选项({f.options?.length || 0})</Button></Col>}
                  {f.type === 'formula' && (
                    <Col flex="auto">
                      <Input size="small" placeholder="公式, 如 $amt# * 2" value={(f.props?.formula as string) || ''}
                        onChange={(e) => patch(idx, { props: { ...f.props, formula: e.target.value } })} />
                    </Col>
                  )}
                  <Col flex="none" style={{ marginLeft: 'auto' }}>
                    <Space size={2}>
                      <Button size="small" type="text" icon={<ArrowUpOutlined />} onClick={() => move(idx, -1)} />
                      <Button size="small" type="text" icon={<ArrowDownOutlined />} onClick={() => move(idx, 1)} />
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => remove(idx)} />
                    </Space>
                  </Col>
                </Row>
              </div>
            ))}
          </Card>
        </Col>
        <Col span={11}>
          <Card title="实时预览" size="small">
            <FormRenderer fields={fields} mode="edit" value={previewValue} onChange={() => { /* 预览不保存 */ }} />
          </Card>
        </Col>
      </Row>

      <Modal title="编辑选项" open={!!optEditing} onOk={saveOpts} onCancel={() => setOptEditing(null)} destroyOnClose>
        <Text type="secondary">每行一个选项，格式 <code>显示文本</code> 或 <code>显示文本|存储值</code></Text>
        <Input.TextArea rows={8} value={optEditing?.text} style={{ marginTop: 8 }}
          onChange={(e) => setOptEditing((s) => (s ? { ...s, text: e.target.value } : s))} />
      </Modal>

      <Drawer title="高级 · 字段 JSON" width={560} open={jsonOpen} onClose={() => setJsonOpen(false)}
        extra={<Button type="primary" onClick={applyJson}>应用</Button>}>
        <Text type="secondary">直接编辑 field_definitions(可配置明细子表列、高级字段类型等)。</Text>
        <Divider style={{ margin: '8px 0' }} />
        <Input.TextArea value={jsonText} onChange={(e) => setJsonText(e.target.value)} style={{ fontFamily: 'monospace', minHeight: 460 }} />
      </Drawer>
    </div>
  )
}
