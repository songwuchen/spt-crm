// 扩展平台 → 表单设计器(拖拽画布版)。
// 左: 字段面板(点选/添加); 中: @dnd-kit 可排序字段画布(拖动手柄排序、点选编辑); 右: 选中字段属性。
// 顶部: 表单规则(显隐/必填/只读 可视化编辑,替代旧的只能写 JSON)、实时预览、高级 JSON、保存/发布。
import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Space, Input, InputNumber, Select, Switch, message, Typography, Tag, Drawer, Empty, Divider, Modal, Tooltip,
} from 'antd'
import {
  DeleteOutlined, PlusOutlined, ArrowLeftOutlined, HolderOutlined, EyeOutlined, BranchesOutlined,
} from '@ant-design/icons'
import FieldTypeIcon, { FIELD_TYPE_LABEL as TYPE_LABEL, fieldOption } from '@/components/lowcode/fieldTypeIcon'
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { lowcodeApi } from '@/api/lowcode'
import { roleApi } from '@/api/user'
import type { Role } from '@/api/types'
import type { FieldDefinition, FieldType, FormRule } from '@/types/lowcode'
import type { CascadeOption } from '@/components/lowcode/fields/CascadeField'
import FormRenderer from '@/components/lowcode/FormRenderer'

const { Title, Text } = Typography

const PALETTE: { group: string; types: FieldType[] }[] = [
  { group: '基础', types: ['text', 'textarea', 'number', 'amount', 'date', 'datetime', 'switch'] },
  { group: '选择', types: ['select', 'multi_select', 'radio', 'checkbox', 'cascade'] },
  { group: '高级', types: ['person', 'person_multi', 'department', 'department_multi', 'file', 'image', 'address', 'rich_text', 'signature', 'formula', 'auto_number', 'detail_table'] },
]
const CHOICE_TYPES = new Set(['select', 'multi_select', 'radio', 'checkbox'])
const SPANS = [{ label: '整行', value: 24 }, { label: '1/2', value: 12 }, { label: '1/3', value: 8 }, { label: '1/4', value: 6 }]
const genId = () => 'f' + Math.random().toString(36).slice(2, 9)

// ---- 级联选项 文本<->树 ----
function parseCascade(text: string): CascadeOption[] {
  const root: CascadeOption[] = []
  const stack: { level: number; node: { children?: CascadeOption[] } }[] = [{ level: -1, node: { children: root } }]
  for (const raw of text.split('\n')) {
    if (!raw.trim()) continue
    const level = Math.floor((raw.match(/^ */)?.[0].length || 0) / 2)
    const label = raw.trim()
    const node: CascadeOption = { label, value: label }
    while (stack.length > 1 && stack[stack.length - 1].level >= level) stack.pop()
    const parent = stack[stack.length - 1].node
    ;(parent.children ||= []).push(node)
    stack.push({ level, node })
  }
  return root
}
function cascadeToText(opts: CascadeOption[], depth = 0): string {
  return (opts || []).map((o) => '  '.repeat(depth) + o.label + (o.children?.length ? '\n' + cascadeToText(o.children, depth + 1) : '')).join('\n')
}

export default function FormDesignerPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [tplName, setTplName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [selId, setSelId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [jsonText, setJsonText] = useState('')
  const [roles, setRoles] = useState<Role[]>([])
  const [previewOpen, setPreviewOpen] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [previewVal, setPreviewVal] = useState<Record<string, unknown>>({})

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  useEffect(() => {
    (async () => {
      try {
        const [tpl, design] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.loadDesign(id)])
        setTplName(tpl.data.name)
        setFields((design.data.field_definitions as FieldDefinition[]) || [])
        setRules((design.data.rule_definitions as FormRule[]) || [])
      } finally { setLoading(false) }
    })()
    roleApi.list().then((r) => setRoles(r.data || [])).catch(() => { /* 角色不可用 */ })
  }, [id])

  const roleOptions = roles.map((r) => ({ label: r.name, value: r.code }))
  const sel = fields.find((f) => f.id === selId) || null
  const patch = (fid: string, p: Partial<FieldDefinition>) => setFields((fs) => fs.map((f) => (f.id === fid ? { ...f, ...p } : f)))

  const addField = (type: FieldType) => {
    const f: FieldDefinition = { id: genId(), type, label: TYPE_LABEL[type] || type, required: false, span: 24, props: {} }
    if (CHOICE_TYPES.has(type)) f.options = [{ label: '选项1', value: '选项1' }, { label: '选项2', value: '选项2' }]
    if (type === 'detail_table') f.detail_table_columns = [{ id: genId(), type: 'text', label: '列1', required: false, props: {} }]
    setFields((fs) => [...fs, f]); setSelId(f.id)
  }
  const remove = (fid: string) => { setFields((fs) => fs.filter((f) => f.id !== fid)); if (selId === fid) setSelId(null) }

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    setFields((fs) => {
      const oldI = fs.findIndex((f) => f.id === active.id)
      const newI = fs.findIndex((f) => f.id === over.id)
      return oldI < 0 || newI < 0 ? fs : arrayMove(fs, oldI, newI)
    })
  }

  const doSave = async (publish = false) => {
    const ids = new Set<string>()
    for (const f of fields) {
      if (!f.label?.trim()) return message.error('存在未命名字段')
      if (ids.has(f.id)) return message.error(`字段 id 重复: ${f.id}`)
      ids.add(f.id)
    }
    await lowcodeApi.saveDesign(id, { field_definitions: fields, layout_definition: {}, rule_definitions: rules })
    if (publish) { await lowcodeApi.publish(id); message.success('已发布'); nav('/lowcode/forms') }
    else message.success('草稿已保存')
  }

  const openJson = () => { setJsonText(JSON.stringify({ fields, rules }, null, 2)); setJsonOpen(true) }
  const applyJson = () => {
    try {
      const parsed = JSON.parse(jsonText)
      const nf = Array.isArray(parsed) ? parsed : parsed.fields
      if (!Array.isArray(nf)) throw new Error('fields 必须是数组')
      setFields(nf)
      if (Array.isArray(parsed.rules)) setRules(parsed.rules)
      setJsonOpen(false); message.success('已应用 JSON')
    } catch (e) { message.error('JSON 解析失败: ' + (e as Error).message) }
  }

  if (loading) return <Card loading />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>设计表单 · {tplName}</Title>
        </Space>
        <Space>
          <Button icon={<BranchesOutlined />} onClick={() => setRulesOpen(true)}>表单规则{rules.length ? ` (${rules.length})` : ''}</Button>
          <Button icon={<EyeOutlined />} onClick={() => { setPreviewVal({}); setPreviewOpen(true) }}>预览</Button>
          <Button onClick={openJson}>高级(JSON)</Button>
          <Button onClick={() => doSave(false)}>保存草稿</Button>
          <Button type="primary" onClick={() => doSave(true)}>保存并发布</Button>
        </Space>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        {/* 字段面板 */}
        <Card size="small" title="字段类型" style={{ width: 190, flex: '0 0 190px' }} styles={{ body: { padding: 10 } }}>
          {PALETTE.map((g) => (
            <div key={g.group} style={{ marginBottom: 10 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>{g.group}</Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                {g.types.map((t) => (
                  <Button key={t} size="small" onClick={() => addField(t)} icon={<FieldTypeIcon type={t} />} style={{ fontSize: 12, padding: '0 8px' }}>{TYPE_LABEL[t]}</Button>
                ))}
              </div>
            </div>
          ))}
        </Card>

        {/* 画布 */}
        <Card size="small" title="表单画布(拖动手柄排序)" style={{ flex: 1, minWidth: 0 }}>
          {fields.length === 0 ? <Empty description="从左侧点选字段开始设计" /> : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
              <SortableContext items={fields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                {fields.map((f) => (
                  <SortableFieldCard key={f.id} field={f} selected={selId === f.id}
                    onSelect={() => setSelId(f.id)} onDelete={() => remove(f.id)} />
                ))}
              </SortableContext>
            </DndContext>
          )}
        </Card>

        {/* 属性 */}
        <Card size="small" title="字段属性" style={{ width: 300, flex: '0 0 300px' }}>
          {sel ? (
            // key=字段 id: 切换选中字段时重挂属性面板,使非受控的选项/级联 textarea 的 defaultValue 正确复位,
            // 否则会把上一个字段的文本残留并在编辑后写回到新选中字段(数据串写)。
            <FieldProps key={sel.id} field={sel} roleOptions={roleOptions} onPatch={(p) => patch(sel.id, p)} />
          ) : <Empty description="点选一个字段编辑属性" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
        </Card>
      </div>

      {/* 实时预览 */}
      <Drawer title="表单预览" width={560} open={previewOpen} onClose={() => setPreviewOpen(false)}>
        <FormRenderer fields={fields} rules={rules} mode="edit" value={previewVal} onChange={setPreviewVal} applyFieldPerms={false} />
      </Drawer>

      {/* 表单规则 */}
      <Drawer title="表单规则(显隐 / 必填 / 只读)" width={640} open={rulesOpen} onClose={() => setRulesOpen(false)}>
        <RulesEditor fields={fields} rules={rules} onChange={setRules} />
      </Drawer>

      {/* 高级 JSON */}
      <Drawer title="高级 · JSON(fields + rules)" width={620} open={jsonOpen} onClose={() => setJsonOpen(false)}
        extra={<Button type="primary" onClick={applyJson}>应用</Button>}>
        <Text type="secondary">直接编辑 {'{ fields, rules }'}(明细子表列、级联选项、规则等)。</Text>
        <Divider style={{ margin: '8px 0' }} />
        <Input.TextArea value={jsonText} onChange={(e) => setJsonText(e.target.value)} style={{ fontFamily: 'monospace', minHeight: 480 }} />
      </Drawer>
    </div>
  )
}

// ---- 可排序字段卡片 ----
function SortableFieldCard({ field, selected, onSelect, onDelete }: {
  field: FieldDefinition; selected: boolean; onSelect: () => void; onDelete: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: field.id })
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1,
    border: `1px solid ${selected ? '#2f6bff' : '#f0f0f0'}`, borderRadius: 6, padding: '8px 10px', marginBottom: 8,
    background: selected ? '#f5f9ff' : '#fff', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
  }
  return (
    <div ref={setNodeRef} style={style} onClick={onSelect}>
      <span {...attributes} {...listeners} style={{ cursor: 'grab', color: '#bbb' }} onClick={(e) => e.stopPropagation()}><HolderOutlined /></span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontWeight: 500 }}>{field.required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}{field.label}</span>
        <Tag style={{ marginLeft: 8 }} icon={<FieldTypeIcon type={field.type} />}>{TYPE_LABEL[field.type] || field.type}</Tag>
        {field.native && <Tag style={{ marginLeft: 4 }} color="gold">内置</Tag>}
      </div>
      {/* 原生字段对应业务表上的真实列，删除会写坏映射，只允许改配置 */}
      {!field.native && (
        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={(e) => { e.stopPropagation(); onDelete() }} />
      )}
    </div>
  )
}

// ---- 字段属性面板 ----
function FieldProps({ field, roleOptions, onPatch }: {
  field: FieldDefinition; roleOptions: { label: string; value: string }[]; onPatch: (p: Partial<FieldDefinition>) => void
}) {
  const [permOpen, setPermOpen] = useState(false)
  const setProp = (k: string, v: unknown) => onPatch({ props: { ...field.props, [k]: v } })
  const optText = (field.options || []).map((o) => (o.label === o.value ? o.label : `${o.label}|${o.value}`)).join('\n')

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Tag color="blue" icon={<FieldTypeIcon type={field.type} />}>{TYPE_LABEL[field.type] || field.type}</Tag>
      {field.native && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          内置字段：可改标签/必填/显隐/只读与字段权限，不能删除或改类型。
        </Text>
      )}
      <div><Text type="secondary" style={{ fontSize: 12 }}>标签</Text>
        <Input size="small" value={field.label} onChange={(e) => onPatch({ label: e.target.value })} /></div>
      <div><Text type="secondary" style={{ fontSize: 12 }}>字段 id</Text>
        <Input size="small" value={field.id} disabled /></div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <span><Text style={{ fontSize: 12 }}>必填 </Text>
          {/* system_required = 数据库 NOT NULL 或业务强依赖，锁死不给改 */}
          <Switch size="small" checked={!!field.required} disabled={!!field.system_required}
            onChange={(v) => onPatch({ required: v })} />
          {field.system_required && <Text type="secondary" style={{ fontSize: 12 }}> (系统必填)</Text>}
        </span>
        <span style={{ flex: 1 }}><Text type="secondary" style={{ fontSize: 12 }}>宽度 </Text>
          <Select size="small" style={{ width: 90 }} value={field.span || 24} options={SPANS} onChange={(v) => onPatch({ span: v })} /></span>
      </div>
      <div><Text type="secondary" style={{ fontSize: 12 }}>提示文本</Text>
        <Input size="small" value={field.placeholder || ''} onChange={(e) => onPatch({ placeholder: e.target.value })} /></div>

      {CHOICE_TYPES.has(field.type) && (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>选项(每行一个,可用 显示|存储值)</Text>
          <Input.TextArea size="small" rows={4} defaultValue={optText}
            onBlur={(e) => onPatch({ options: e.target.value.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => { const [a, b] = l.split('|'); return { label: a, value: (b ?? a).trim() } }) })} />
        </div>
      )}
      {field.type === 'cascade' && (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>级联选项(缩进 2 空格表示层级)</Text>
          <Input.TextArea size="small" rows={6} defaultValue={cascadeToText((field.props?.cascade_options as CascadeOption[]) || [])}
            placeholder={'华东\n  江苏\n  浙江\n华南\n  广东'}
            onBlur={(e) => setProp('cascade_options', parseCascade(e.target.value))} />
        </div>
      )}
      {field.type === 'address' && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Text style={{ fontSize: 12 }}>显示详细地址行</Text>
          <Switch size="small" checked={field.props?.show_detail !== false} onChange={(v) => setProp('show_detail', v)} />
        </div>
      )}
      {field.type === 'signature' && (
        <div style={{ display: 'flex', gap: 8 }}>
          <span><Text type="secondary" style={{ fontSize: 12 }}>宽</Text><InputNumber size="small" style={{ width: 80 }} value={(field.props?.sign_width as number) || 360} onChange={(v) => setProp('sign_width', v)} /></span>
          <span><Text type="secondary" style={{ fontSize: 12 }}>高</Text><InputNumber size="small" style={{ width: 80 }} value={(field.props?.sign_height as number) || 140} onChange={(v) => setProp('sign_height', v)} /></span>
        </div>
      )}
      {field.type === 'formula' && (
        <div><Text type="secondary" style={{ fontSize: 12 }}>公式(如 $amt# * 2)</Text>
          <Input size="small" value={(field.props?.formula as string) || ''} onChange={(e) => setProp('formula', e.target.value)} /></div>
      )}

      <Divider style={{ margin: '6px 0' }} />
      <Button size="small" block onClick={() => setPermOpen(true)}>
        字段权限{(field.visible_roles?.length || field.unmask_roles?.length || field.edit_roles?.length) ? ' ●' : ''}
      </Button>

      <Modal title="字段权限" open={permOpen} footer={<Button type="primary" onClick={() => setPermOpen(false)}>完成</Button>} onCancel={() => setPermOpen(false)} destroyOnClose>
        <div className="space-y-4">
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>可见角色<Text type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>留空=所有人可见</Text></div>
            <Select mode="multiple" allowClear style={{ width: '100%' }} placeholder="仅这些角色可见"
              value={field.visible_roles || []} options={roleOptions} onChange={(v) => onPatch({ visible_roles: v.length ? v : null })} />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>可编辑角色<Text type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>留空=可见者皆可编辑</Text></div>
            <Select mode="multiple" allowClear style={{ width: '100%' }} placeholder="仅这些角色可编辑"
              value={field.edit_roles || []} options={roleOptions} onChange={(v) => onPatch({ edit_roles: v.length ? v : null })} />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>可见明文角色<Text type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>留空=所有人见明文;非空时其余人只看到 ***</Text></div>
            <Select mode="multiple" allowClear style={{ width: '100%' }} placeholder="仅这些角色能看到真实值"
              value={field.unmask_roles || []} options={roleOptions} onChange={(v) => onPatch({ unmask_roles: v.length ? v : null })} />
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            说明: 优先级 隐藏 &gt; 脱敏 &gt; 只读；被脱敏的字段一律不可编辑。
            后端按登录者角色在列表/详情/导出上强制裁剪，设计器预览不受限。
          </Text>
        </div>
      </Modal>
    </Space>
  )
}

// ---- 规则编辑器(显隐/必填/只读) ----
const RULE_ACTIONS = [
  { key: 'show', label: '显示', type: 'visibility', action: { visible: true } },
  { key: 'hide', label: '隐藏', type: 'visibility', action: { visible: false } },
  { key: 'require', label: '必填', type: 'required', action: { required: true } },
  { key: 'optional', label: '选填', type: 'required', action: { required: false } },
  { key: 'readonly', label: '只读', type: 'readonly', action: { readonly: true } },
  { key: 'editable', label: '可编辑', type: 'readonly', action: { readonly: false } },
] as const
const RULE_OPS = [
  { value: 'eq', label: '等于' }, { value: 'ne', label: '不等于' },
  { value: 'gt', label: '大于' }, { value: 'gte', label: '大于等于' }, { value: 'lt', label: '小于' }, { value: 'lte', label: '小于等于' },
  { value: 'contains', label: '包含' }, { value: 'in', label: '属于(逗号分隔)' },
  { value: 'is_empty', label: '为空' }, { value: 'is_not_empty', label: '非空' },
]

function actionKeyOf(r: FormRule): string {
  const a = r.action as Record<string, boolean>
  if (r.type === 'visibility') return a.visible === false ? 'hide' : 'show'
  if (r.type === 'required') return a.required === false ? 'optional' : 'require'
  if (r.type === 'readonly') return a.readonly === false ? 'editable' : 'readonly'
  return 'show'
}

function RulesEditor({ fields, rules, onChange }: {
  fields: FieldDefinition[]; rules: FormRule[]; onChange: (r: FormRule[]) => void
}) {
  const fieldOpts = fields.filter((f) => f.type !== 'detail_table').map((f) => fieldOption({ value: f.id, label: f.label, type: f.type }))
  const upd = (i: number, r: FormRule) => onChange(rules.map((x, k) => (k === i ? r : x)))
  const addRule = () => onChange([...rules, {
    id: 'rule' + Math.random().toString(36).slice(2, 8), type: 'visibility', target_field_ids: [],
    condition: { rel: 'and', cond: [{ field: fields[0]?.id || '', operator: 'eq', value: '' }] }, action: { visible: true },
  }])
  const setAction = (i: number, key: string) => {
    const a = RULE_ACTIONS.find((x) => x.key === key)!
    upd(i, { ...rules[i], type: a.type as FormRule['type'], action: { ...a.action } })
  }
  const conds = (r: FormRule) => (r.condition.cond || []) as { field: string; operator: string; value?: unknown }[]
  const setConds = (i: number, cond: { field: string; operator: string; value?: unknown }[]) =>
    upd(i, { ...rules[i], condition: { ...rules[i].condition, cond } })

  return (
    <div>
      <Button type="dashed" block icon={<PlusOutlined />} onClick={addRule} style={{ marginBottom: 12 }}>新增规则</Button>
      {rules.length === 0 && <Empty description="暂无规则。规则示例: 当「类型=其他」时 显示「说明」字段。" />}
      {rules.map((r, i) => {
        const cs = conds(r)
        return (
          <Card key={r.id} size="small" style={{ marginBottom: 10 }}
            title={<Space size={4}><span>当满足</span>
              <Select size="small" style={{ width: 70 }} value={r.condition.rel || 'and'} options={[{ label: '全部', value: 'and' }, { label: '任一', value: 'or' }]}
                onChange={(v) => upd(i, { ...r, condition: { ...r.condition, rel: v } })} />
              <span>条件时</span></Space>}
            extra={<Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(rules.filter((_, k) => k !== i))} />}>
            {cs.map((c, ci) => {
              const noVal = c.operator === 'is_empty' || c.operator === 'is_not_empty'
              return (
                <div key={ci} style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' }}>
                  <Select size="small" style={{ width: 120 }} placeholder="字段" value={c.field || undefined} options={fieldOpts}
                    onChange={(v) => setConds(i, cs.map((x, k) => (k === ci ? { ...x, field: v } : x)))} />
                  <Select size="small" style={{ width: 110 }} value={c.operator} options={RULE_OPS}
                    onChange={(v) => setConds(i, cs.map((x, k) => (k === ci ? { ...x, operator: v } : x)))} />
                  {!noVal && <Input size="small" style={{ flex: 1 }} placeholder="值" value={(c.value as string) ?? ''}
                    onChange={(e) => setConds(i, cs.map((x, k) => (k === ci ? { ...x, value: e.target.value } : x)))} />}
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={cs.length <= 1}
                    onClick={() => setConds(i, cs.filter((_, k) => k !== ci))} />
                </div>
              )
            })}
            <Button size="small" type="link" icon={<PlusOutlined />} onClick={() => setConds(i, [...cs, { field: fields[0]?.id || '', operator: 'eq', value: '' }])}>加条件</Button>
            <Divider style={{ margin: '8px 0' }} />
            <Space wrap size={6}>
              <Tooltip title="满足条件时对目标字段执行的动作"><Text type="secondary" style={{ fontSize: 12 }}>则</Text></Tooltip>
              <Select size="small" style={{ width: 90 }} value={actionKeyOf(r)} options={RULE_ACTIONS.map((a) => ({ label: a.label, value: a.key }))}
                onChange={(v) => setAction(i, v)} />
              <Select size="small" mode="multiple" style={{ minWidth: 220 }} placeholder="目标字段" value={r.target_field_ids || []}
                options={fieldOpts} onChange={(v) => upd(i, { ...r, target_field_ids: v })} />
            </Space>
          </Card>
        )
      })}
    </div>
  )
}
