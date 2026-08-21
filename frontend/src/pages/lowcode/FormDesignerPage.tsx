// 扩展平台 → 表单设计器(拖拽画布版)。
// 左: 字段面板(点选/添加); 中: @dnd-kit 可排序字段画布(拖动手柄排序、点选编辑); 右: 选中字段属性。
// 顶部: 表单规则(显隐/必填/只读 可视化编辑,替代旧的只能写 JSON)、实时预览、高级 JSON、保存/发布。
import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Space, Input, InputNumber, Select, Switch, message, Typography, Tag, Drawer, Empty, Divider, Modal, Tooltip, Form, Alert,
} from 'antd'
import {
  DeleteOutlined, PlusOutlined, ArrowLeftOutlined, HolderOutlined, EyeOutlined, BranchesOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import FieldTypeIcon, { FIELD_TYPE_LABEL as TYPE_LABEL } from '@/components/lowcode/fieldTypeIcon'
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { lowcodeApi } from '@/api/lowcode'
import { settingsApi } from '@/api/settings'
import { roleApi } from '@/api/user'
import { pickableScopeApi } from '@/api/pickableScope'
import type { Role } from '@/api/types'
import type { FieldDefinition, FieldType, FormRule } from '@/types/lowcode'
import type { CascadeOption } from '@/components/lowcode/fields/CascadeField'
import FormRenderer from '@/components/lowcode/FormRenderer'
import { fieldShowsTime } from '@/components/lowcode/dateField'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import PickableScopePropsEditor from '@/components/lowcode/PickableScopePropsEditor'
import type { PickableScope } from '@/components/lowcode/fields/PersonField'
import ContractRegistrationFields from '@/components/ContractRegistrationFields'
import { LineItemsEditor, PaymentTermsEditor, ContractSubtableTitle } from '@/components/ContractTerms'
import {
  FALLBACK_LINE_COLUMNS,
  FALLBACK_PAY_COLUMNS,
  LINE_ITEMS_FIELD_ID,
  PAYMENT_TERMS_FIELD_ID,
} from '@/constants/contractDetailTables'

const { Title, Text } = Typography

const PALETTE: { group: string; types: FieldType[] }[] = [
  { group: '基础', types: ['text', 'textarea', 'number', 'amount', 'date', 'datetime', 'switch'] },
  { group: '选择', types: ['select', 'multi_select', 'radio', 'checkbox', 'cascade'] },
  { group: '高级', types: ['person', 'person_multi', 'department', 'department_multi', 'project', 'contract', 'customer', 'file', 'image', 'address', 'rich_text', 'signature', 'formula', 'auto_number', 'detail_table'] },
]
const CHOICE_TYPES = new Set(['select', 'multi_select', 'radio', 'checkbox'])
/** 与后端 DETAIL_COLUMN_TYPES 对齐：可作为明细子表列的类型 */
const DETAIL_COLUMN_TYPES: FieldType[] = [
  'text', 'textarea', 'number', 'amount', 'date', 'datetime',
  'select', 'multi_select', 'radio', 'checkbox',
  'person', 'department', 'file', 'image', 'formula', 'switch',
]
const DETAIL_COL_OPTS = DETAIL_COLUMN_TYPES.map((t) => ({ label: TYPE_LABEL[t] || t, value: t }))
const SPANS = [{ label: '整行', value: 24 }, { label: '1/2', value: 12 }, { label: '1/3', value: 8 }, { label: '1/4', value: 6 }]
const genId = () => 'f' + Math.random().toString(36).slice(2, 9)
/** 角色列表尚未同步时，已写入 props 的 code 仍显示中文名 */
const ROLE_CODE_FALLBACK: Record<string, string> = {
  room_leader: '设计指派27.3~4/1.2.8/6.8/27.16/19.3',
  admin: '管理员',
  sales: '销售',
  finance: '财务',
}

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
  const [entityType, setEntityType] = useState<string | undefined>()
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [systemDefaults, setSystemDefaults] = useState<FormRule[]>([])
  const [selId, setSelId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [jsonText, setJsonText] = useState('')
  const [roles, setRoles] = useState<Role[]>([])
  const [personScopes, setPersonScopes] = useState<{ label: string; value: string }[]>([])
  const [deptScopes, setDeptScopes] = useState<{ label: string; value: string }[]>([])
  const [previewOpen, setPreviewOpen] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [previewVal, setPreviewVal] = useState<Record<string, unknown>>({})
  const [previewLines, setPreviewLines] = useState<Record<string, unknown>[]>([])
  const [previewPay, setPreviewPay] = useState<Record<string, unknown>[]>([])
  const [previewForm] = Form.useForm()

  const previewLineCols = useMemo(
    () => fields.find((f) => f.id === LINE_ITEMS_FIELD_ID)?.detail_table_columns || FALLBACK_LINE_COLUMNS,
    [fields],
  )
  const previewPayCols = useMemo(
    () => fields.find((f) => f.id === PAYMENT_TERMS_FIELD_ID)?.detail_table_columns || FALLBACK_PAY_COLUMNS,
    [fields],
  )

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const systemRules = useMemo(
    () => rules.filter((r) => String(r.id || '').startsWith('__sys_')),
    [rules],
  )
  const tenantRules = useMemo(
    () => rules.filter((r) => !String(r.id || '').startsWith('__sys_')),
    [rules],
  )
  const setTenantRules = (next: FormRule[]) => setRules([...systemRules, ...next])
  const setSystemRules = (next: FormRule[]) => setRules([...next, ...tenantRules])

  const detailTableFields = useMemo(() => fields.filter((f) => f.type === 'detail_table'), [fields])
  const otherFields = useMemo(() => fields.filter((f) => f.type !== 'detail_table'), [fields])
  const missingContractDetails = entityType === 'contract'
    && !fields.some((f) => f.id === LINE_ITEMS_FIELD_ID)
    && !fields.some((f) => f.id === PAYMENT_TERMS_FIELD_ID)

  useEffect(() => {
    (async () => {
      try {
        const [tpl, design] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.loadDesign(id)])
        setTplName(tpl.data.name)
        setEntityType(tpl.data.entity_type || design.data.entity_type)
        const raw = (design.data.field_definitions as FieldDefinition[]) || []
        // 明细子表置顶，避免淹没在几十个原生字段中间
        const details = raw.filter((f) => f.type === 'detail_table')
        const rest = raw.filter((f) => f.type !== 'detail_table')
        setFields([...details, ...rest])
        setRules((design.data.rule_definitions as FormRule[]) || [])
        setSystemDefaults((design.data.system_rule_defaults as FormRule[]) || [])
      } finally { setLoading(false) }
    })()
    roleApi.list().then((r) => setRoles(r.data || [])).catch(() => { /* 角色不可用 */ })
    pickableScopeApi.listForPicker({ kind: 'person' }).then((r) => {
      setPersonScopes((r.data || []).map((s) => ({
        value: s.code,
        label: `${s.name}（${s.code}）`,
      })))
    }).catch(() => {})
    pickableScopeApi.listForPicker({ kind: 'department' }).then((r) => {
      setDeptScopes((r.data || []).map((s) => ({
        value: s.code,
        label: `${s.name}（${s.code}）`,
      })))
    }).catch(() => {})
  }, [id])

  const roleOptions = useMemo(() => {
    const opts = roles.map((r) => ({ label: r.name || ROLE_CODE_FALLBACK[r.code] || r.code, value: r.code }))
    const known = new Set(opts.map((o) => o.value))
    for (const [code, name] of Object.entries(ROLE_CODE_FALLBACK)) {
      if (!known.has(code)) opts.push({ label: name, value: code })
    }
    return opts
  }, [roles])
  const sel = fields.find((f) => f.id === selId) || null
  const patch = (fid: string, p: Partial<FieldDefinition>) => setFields((fs) => fs.map((f) => (f.id === fid ? { ...f, ...p } : f)))

  const addField = (type: FieldType) => {
    const f: FieldDefinition = { id: genId(), type, label: TYPE_LABEL[type] || type, required: false, span: 24, props: {} }
    if (CHOICE_TYPES.has(type)) f.options = [{ label: '选项1', value: '选项1' }, { label: '选项2', value: '选项2' }]
    if (type === 'detail_table') {
      f.detail_table_columns = [{ id: genId(), type: 'text', label: '列1', required: false, props: {} }]
      // 新建明细子表插到列表顶部（与内置子表同区）
      setFields((fs) => [f, ...fs]); setSelId(f.id)
      return
    }
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
    // props 缺省/null 时后端要 dict；内置表单常带 null，保存前规整
    const normalizeField = (f: FieldDefinition): FieldDefinition => ({
      ...f,
      props: (f.props && typeof f.props === 'object') ? f.props : {},
      detail_table_columns: f.detail_table_columns?.map((c) => normalizeField(c as FieldDefinition)),
    })
    const payloadFields = fields.map(normalizeField)
    // 系统规则一并落库（作为租户覆盖）；运行时与目录默认 merge
    await lowcodeApi.saveDesign(id, { field_definitions: payloadFields, layout_definition: {}, rule_definitions: rules })
    if (publish) {
      await lowcodeApi.publish(id)
      if (entityType) {
        message.success('已发布：合同管理等业务页刷新后生效（必填/显隐/标签/明细列/扩展字段）')
      } else {
        message.success('已发布')
        nav('/lowcode/forms')
      }
    } else if (entityType) {
      message.warning('草稿已保存。业务页只读「已发布」版本，请再点「保存并发布」才会同步到合同管理。')
    } else {
      message.success('草稿已保存')
    }
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

  const openPreview = () => {
    setPreviewVal({})
    setPreviewLines([])
    setPreviewPay([])
    previewForm.resetFields()
    previewForm.setFieldsValue({ change_type: 'new', registration_json: {} })
    setPreviewOpen(true)
  }

  if (loading) return <Card loading />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav(-1)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>设计表单 · {tplName}</Title>
          {entityType && <Tag color="blue">实体 {entityType}</Tag>}
        </Space>
        <Space>
          <Button icon={<BranchesOutlined />} onClick={() => setRulesOpen(true)}>
            表单规则{rules.length ? ` (${rules.length})` : ''}
          </Button>
          <Button icon={<EyeOutlined />} onClick={openPreview}>预览</Button>
          <Button onClick={openJson}>高级(JSON)</Button>
          <Button onClick={() => doSave(false)}>保存草稿</Button>
          <Button type="primary" onClick={() => doSave(true)}>保存并发布</Button>
        </Space>
      </div>

      {/* 左右栏 sticky：中间画布随主内容区窗口滚动，避免选字段后再滚回属性栏 */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        {/* 字段面板 */}
        <Card
          size="small"
          title="字段类型"
          style={{ width: 190, flex: '0 0 190px', position: 'sticky', top: 12, maxHeight: 'calc(100vh - 88px)', overflow: 'auto', alignSelf: 'flex-start' }}
          styles={{ body: { padding: 10 } }}
        >
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

        {/* 画布：高度随内容撑开，由页面 Content 统一滚动 */}
        <Card size="small" title="表单画布(拖动手柄排序)" style={{ flex: 1, minWidth: 0 }}>
          {entityType && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="与业务页的同步方式"
              description={
                <span>
                  合同管理等页面只读<strong>已发布</strong>配置，改完须点「保存并发布」并刷新业务页。
                  可同步：必填/显隐/只读、字段标签、明细子表列、扩展字段。
                  登记表单的分区布局仍由业务页固定，画布上拖拽排序不会改业务页分区顺序。
                </span>
              }
            />
          )}
          {missingContractDetails && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="未加载到「合同明细 / 收款计划」内置子表"
              description="请确认后端已部署含 line_items 的目录并重启；入口须是「自定义字段 → 合同 → 设计字段」（系统实体模板），不是普通自定义表单。"
            />
          )}
          {fields.length === 0 ? <Empty description="从左侧点选字段开始设计" /> : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
              <SortableContext items={fields.map((f) => f.id)} strategy={verticalListSortingStrategy}>
                {detailTableFields.length > 0 && (
                  <div style={{ marginBottom: 14, padding: '10px 10px 4px', background: '#f7fafc', borderRadius: 8, border: '1px solid #e8eef5' }}>
                    <div style={{ marginBottom: 8 }}>
                      <Text strong style={{ fontSize: 13 }}>明细子表</Text>
                      <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                        点选后在右侧编辑列（合同明细 / 收款计划为内置）
                      </Text>
                    </div>
                    {detailTableFields.map((f) => (
                      <SortableFieldCard key={f.id} field={f} selected={selId === f.id}
                        onSelect={() => setSelId(f.id)} onDelete={() => remove(f.id)} />
                    ))}
                  </div>
                )}
                {otherFields.length > 0 && detailTableFields.length > 0 && (
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>其它字段</Text>
                )}
                {otherFields.map((f) => (
                  <SortableFieldCard key={f.id} field={f} selected={selId === f.id}
                    onSelect={() => setSelId(f.id)} onDelete={() => remove(f.id)} />
                ))}
              </SortableContext>
            </DndContext>
          )}
        </Card>

        {/* 属性 */}
        <Card
          size="small"
          title="字段属性"
          style={{ width: 300, flex: '0 0 300px', position: 'sticky', top: 12, maxHeight: 'calc(100vh - 88px)', overflow: 'auto', alignSelf: 'flex-start' }}
        >
          {/* 字段属性：改标签时同步 label_override，发布后业务页才能覆盖硬编码文案 */}
          {sel ? (
            <FieldProps
              key={sel.id}
              field={sel}
              roleOptions={roleOptions}
              personScopeOptions={personScopes}
              deptScopeOptions={deptScopes}
              onPatch={(p) => {
              if (sel.native && typeof p.label === 'string') {
                patch(sel.id, { ...p, label_override: p.label })
              } else {
                patch(sel.id, p)
              }
            }} />
          ) : <Empty description="点选一个字段编辑属性" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
        </Card>
      </div>

      {/* 实时预览：合同实体走业务登记表单，其它实体走通用 FormRenderer */}
      <Drawer
        title={entityType === 'contract' ? '合同登记预览（对齐业务页）' : '表单预览'}
        width={entityType === 'contract' ? 920 : 560}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
      >
        {entityType === 'contract' ? (
          <div>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
              与业务登记页相同分区 + 字段策略；明细/收款计划列取自当前设计（含未保存修改）。附件仍为占位。
            </Text>
            <FieldPolicyProvider
              entityType="contract"
              form={previewForm}
              rulesOverride={rules}
              nativeFieldsOverride={fields.filter((f) => f.native)}
            >
              <Form form={previewForm} layout="vertical" initialValues={{ change_type: 'new', registration_json: {} }}>
                <ContractRegistrationFields
                  form={previewForm}
                  mode="create"
                  slots={{
                    line_items: (
                      <div className="my-2">
                        <ContractSubtableTitle
                          fieldId={LINE_ITEMS_FIELD_ID}
                          fallback={fields.find((f) => f.id === LINE_ITEMS_FIELD_ID)?.label || '合同明细'}
                        />
                        <LineItemsEditor
                          value={previewLines}
                          onChange={setPreviewLines}
                          columns={previewLineCols}
                          onTotalChange={(t) => previewForm.setFieldValue('amount_total', t || undefined)}
                        />
                      </div>
                    ),
                    payment_terms: (
                      <div className="my-2">
                        <ContractSubtableTitle
                          fieldId={PAYMENT_TERMS_FIELD_ID}
                          fallback={fields.find((f) => f.id === PAYMENT_TERMS_FIELD_ID)?.label || '收款计划'}
                        />
                        <PaymentTermsEditor
                          value={previewPay}
                          onChange={setPreviewPay}
                          columns={previewPayCols}
                          hideFinanceFields
                        />
                      </div>
                    ),
                    contract_files: (
                      <div className="text-sm text-slate-400 py-2">附件槽位（业务页上传）</div>
                    ),
                    accept_files: (
                      <div className="text-sm text-slate-400 py-2">验收资料（业务页上传）</div>
                    ),
                  }}
                />
              </Form>
            </FieldPolicyProvider>
          </div>
        ) : (
          <FormRenderer fields={fields} rules={rules} mode="edit" value={previewVal} onChange={setPreviewVal} applyFieldPerms={false} />
        )}
      </Drawer>

      {/* 表单规则 */}
      <Drawer title="表单规则(显隐 / 必填 / 只读)" width={640} open={rulesOpen} onClose={() => setRulesOpen(false)}>
        <RulesEditor
          fields={fields}
          systemRules={systemRules}
          systemDefaults={systemDefaults}
          onSystemChange={setSystemRules}
          rules={tenantRules}
          onChange={setTenantRules}
        />
      </Drawer>

      {/* 高级 JSON */}
      <Drawer title="高级 · JSON(fields + rules)" width={620} open={jsonOpen} onClose={() => setJsonOpen(false)}
        extra={<Button type="primary" onClick={applyJson}>应用</Button>}>
        <Text type="secondary">直接编辑 {'{ fields, rules }'}（含系统规则 `__sys_*`，可改条件/停用）。</Text>
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
        {field.type === 'detail_table' && (
          <Tag style={{ marginLeft: 4 }}>{(field.detail_table_columns || []).length} 列</Tag>
        )}
        {field.native && <Tag style={{ marginLeft: 4 }} color="gold">内置</Tag>}
        {field.available_on_create === false && <Tag style={{ marginLeft: 4 }} color="orange">仅审批填</Tag>}
        {field.json_storage && <Tag style={{ marginLeft: 4 }}>登记JSON</Tag>}
        {field.form_editable === false && <Tag style={{ marginLeft: 4 }}>只读列</Tag>}
        {field.type === 'detail_table' && (field.detail_table_columns || []).length > 0 && (
          <div style={{ fontSize: 11, color: '#999', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {(field.detail_table_columns || []).map((c) => c.label).join(' · ')}
          </div>
        )}
      </div>
      {/* 原生字段对应业务表上的真实列，删除会写坏映射，只允许改配置 */}
      {!field.native && (
        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={(e) => { e.stopPropagation(); onDelete() }} />
      )}
    </div>
  )
}

// ---- 明细子表列设计 ----
function DetailColumnsEditor({ columns, onChange }: {
  columns: FieldDefinition[]
  onChange: (cols: FieldDefinition[]) => void
}) {
  const patchCol = (i: number, p: Partial<FieldDefinition>) =>
    onChange(columns.map((c, k) => (k === i ? { ...c, ...p } : c)))
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir
    if (j < 0 || j >= columns.length) return
    const next = [...columns]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  const addCol = () => onChange([...columns, {
    id: genId(), type: 'text',
    label: `列${columns.length + 1}`,
    required: false, props: {},
  }])

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
        明细列（运行时按下列渲染可编辑表格）
      </Text>
      {columns.length === 0 && (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无列，请添加" style={{ margin: '8px 0' }} />
      )}
      {columns.map((col, i) => {
        const colOptText = (col.options || [])
          .map((o) => (o.label === o.value ? o.label : `${o.label}|${o.value}`)).join('\n')
        const locked = col.props?.system_column === true
        const showWhen = col.props?.show_when as { field?: string; equals?: string[] } | undefined
        return (
          <Card key={col.id} size="small" style={{ marginBottom: 8 }}
            title={
              <Space size={4}>
                <Text style={{ fontSize: 12 }}>{col.label || `列${i + 1}`}</Text>
                {locked && <Tag style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>系统列</Tag>}
              </Space>
            }
            extra={
              <Space size={0}>
                <Button size="small" type="text" disabled={i === 0} onClick={() => move(i, -1)}>↑</Button>
                <Button size="small" type="text" disabled={i === columns.length - 1} onClick={() => move(i, 1)}>↓</Button>
                <Button size="small" type="text" danger icon={<DeleteOutlined />}
                  disabled={locked || columns.length <= 1}
                  title={locked ? '系统列不可删除' : '删除列'}
                  onClick={() => onChange(columns.filter((_, k) => k !== i))} />
              </Space>
            }
          >
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Input size="small" placeholder="列标签" value={col.label}
                onChange={(e) => patchCol(i, { label: e.target.value })} />
              <Select size="small" style={{ width: '100%' }} value={col.type} options={DETAIL_COL_OPTS}
                disabled={locked}
                onChange={(v) => {
                  const next: Partial<FieldDefinition> = { type: v }
                  if (CHOICE_TYPES.has(v) && !col.options?.length) {
                    next.options = [{ label: '选项1', value: '选项1' }, { label: '选项2', value: '选项2' }]
                  }
                  if (v === 'formula' && !col.props?.formula) {
                    next.props = { ...col.props, formula: '' }
                  }
                  patchCol(i, next)
                }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Text style={{ fontSize: 12 }}>必填</Text>
                <Switch size="small" checked={!!col.required} onChange={(v) => patchCol(i, { required: v })} />
              </div>
              {CHOICE_TYPES.has(col.type) && (
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>选项(每行一个,可用 显示|存储值)</Text>
                  <Input.TextArea size="small" rows={3} defaultValue={colOptText} key={`${col.id}-opts`}
                    onBlur={(e) => patchCol(i, {
                      options: e.target.value.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
                        const [a, b] = l.split('|')
                        return { label: a, value: (b ?? a).trim() }
                      }),
                    })} />
                </div>
              )}
              {col.type === 'formula' && (
                <Input size="small" placeholder="公式，如 $qty# * $price#"
                  value={(col.props?.formula as string) || ''}
                  onChange={(e) => patchCol(i, { props: { ...col.props, formula: e.target.value } })} />
              )}
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>行内显隐(依赖字段=值，逗号分隔多值)</Text>
                <Space.Compact style={{ width: '100%' }}>
                  <Input size="small" style={{ width: '45%' }} placeholder="字段 id"
                    value={showWhen?.field || ''}
                    onChange={(e) => {
                      const field = e.target.value.trim()
                      const equals = showWhen?.equals || []
                      patchCol(i, {
                        props: {
                          ...col.props,
                          show_when: field ? { field, equals } : undefined,
                        },
                      })
                    }} />
                  <Input size="small" style={{ width: '55%' }} placeholder="值，如 是"
                    value={(showWhen?.equals || []).join(',')}
                    onChange={(e) => {
                      const field = showWhen?.field || ''
                      const equals = e.target.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
                      patchCol(i, {
                        props: {
                          ...col.props,
                          show_when: field ? { field, equals } : undefined,
                        },
                      })
                    }} />
                </Space.Compact>
              </div>
              <Text type="secondary" style={{ fontSize: 10 }}>id: {col.id}</Text>
            </Space>
          </Card>
        )
      })}
      <Button size="small" type="dashed" block icon={<PlusOutlined />} onClick={addCol}>添加列</Button>
    </div>
  )
}

// ---- 字段属性面板 ----
function FieldProps({ field, roleOptions, personScopeOptions, deptScopeOptions, onPatch }: {
  field: FieldDefinition
  roleOptions: { label: string; value: string }[]
  personScopeOptions: { label: string; value: string }[]
  deptScopeOptions: { label: string; value: string }[]
  onPatch: (p: Partial<FieldDefinition>) => void
}) {
  const [permOpen, setPermOpen] = useState(false)
  const [dictLoading, setDictLoading] = useState(false)
  const setProp = (k: string, v: unknown) => onPatch({ props: { ...field.props, [k]: v } })
  const optText = (field.options || []).map((o) => {
    const v = String(o.value ?? '')
    return o.label === v || o.label == null ? v : `${o.label}|${v}`
  }).join('\n')

  const dictType = typeof field.options_source === 'string' && field.options_source.startsWith('dict:')
    ? field.options_source.slice(5)
    : null
  const enumSource = typeof field.options_source === 'string' && field.options_source.startsWith('enum:')
    ? field.options_source.slice(5)
    : null

  const loadDictOptions = async () => {
    if (!dictType) return
    setDictLoading(true)
    try {
      const r = await settingsApi.listDataDict(dictType) as { data?: { dict_code?: string; dict_label?: string; enabled?: boolean }[] }
      const items = (r.data || []).filter((d) => d.enabled !== false)
      const opts = items.map((d) => ({
        label: d.dict_label || d.dict_code || '',
        value: d.dict_code || d.dict_label || '',
      })).filter((o) => o.value)
      if (!opts.length) {
        message.warning(`数据字典「${dictType}」暂无启用项，仍显示目录默认选项`)
        return
      }
      onPatch({ options: opts })
      message.success(`已从字典「${dictType}」载入 ${opts.length} 项`)
    } catch {
      message.error('加载数据字典失败')
    } finally {
      setDictLoading(false)
    }
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Tag color="blue" icon={<FieldTypeIcon type={field.type} />}>{TYPE_LABEL[field.type] || field.type}</Tag>
      {field.native && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          内置字段：可改标签/必填/显隐/只读/选项与字段权限，不能删除或改类型。
          {field.json_storage ? ` 值存于 ${field.json_storage}。` : ''}
        </Text>
      )}
      <div><Text type="secondary" style={{ fontSize: 12 }}>标签</Text>
        <Input size="small" value={field.label} onChange={(e) => onPatch({ label: e.target.value })} /></div>
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>字段 id（系统标识，界面显示用上方标签）</Text>
        <Input size="small" value={field.id} disabled />
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <span><Text style={{ fontSize: 12 }}>必填 </Text>
          {/* system_required = 数据库 NOT NULL 或业务强依赖，锁死不给改 */}
          <Switch size="small" checked={!!field.required} disabled={!!field.system_required || field.available_on_create === false}
            onChange={(v) => onPatch({ required: v })} />
          {field.system_required && <Text type="secondary" style={{ fontSize: 12 }}> (系统必填)</Text>}
        </span>
        <span style={{ flex: 1 }}><Text type="secondary" style={{ fontSize: 12 }}>宽度 </Text>
          <Select size="small" style={{ width: 90 }} value={field.span || 24} options={SPANS} onChange={(v) => onPatch({ span: v })} /></span>
      </div>
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>填写阶段</Text>
        <Select
          size="small"
          style={{ width: '100%', marginTop: 4 }}
          value={field.available_on_create === false ? 'approver' : 'initiator'}
          options={[
            { value: 'initiator', label: '发起时填写（创建页可见）' },
            { value: 'approver', label: '仅审批时填写（创建隐藏）' },
          ]}
          onChange={(v) => {
            if (v === 'approver') {
              onPatch({
                available_on_create: false,
                fill_stage: 'approver',
                // 创建不必填：必填改到流程节点「本节点可填字段」里勾选
                required: false,
              })
            } else {
              onPatch({ available_on_create: true, fill_stage: 'initiator' })
            }
          }}
        />
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
          {field.available_on_create === false
            ? '创建页不展示。请到「流程设计」对应审批节点 → 本节点可填字段 中勾选，并可设为节点必填。'
            : '发起人在填报/提交时可见；勾选上方「必填」即创建必填。'}
        </Text>
      </div>
      <div><Text type="secondary" style={{ fontSize: 12 }}>提示文本</Text>
        <Input size="small" value={field.placeholder || ''} onChange={(e) => onPatch({ placeholder: e.target.value })} /></div>

      {(field.type === 'date' || field.type === 'datetime') && !field.native && (
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>时间精度</Text>
          <Select
            size="small"
            style={{ width: '100%', marginTop: 4 }}
            value={fieldShowsTime(field) ? 'datetime' : 'date'}
            options={[
              { value: 'date', label: '仅日期（不含时分）' },
              { value: 'datetime', label: '日期 + 时间' },
            ]}
            onChange={(v) => {
              if (v === 'date') {
                onPatch({
                  type: 'date',
                  props: { ...field.props, show_time: false, date_only: true },
                })
              } else {
                const nextProps = { ...(field.props || {}) }
                delete nextProps.show_time
                delete nextProps.date_only
                onPatch({ type: 'datetime', props: nextProps })
              }
            }}
          />
        </div>
      )}
      {(field.type === 'date' || field.type === 'datetime') && field.native && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Text style={{ fontSize: 12 }}>仅选择日期（不含时分）</Text>
          <Switch
            size="small"
            checked={!fieldShowsTime(field)}
            onChange={(onlyDate) => {
              if (onlyDate) setProp('show_time', false)
              else setProp('show_time', true)
            }}
          />
        </div>
      )}

      {CHOICE_TYPES.has(field.type) && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>选项(每行一个,可用 显示|存储值)</Text>
            {dictType && (
              <Button type="link" size="small" icon={<ReloadOutlined />} loading={dictLoading} onClick={loadDictOptions} style={{ padding: 0, height: 'auto' }}>
                从字典同步
              </Button>
            )}
          </div>
          {(dictType || enumSource) && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 6, padding: '4px 8px' }}
              message={
                <span style={{ fontSize: 12 }}>
                  {dictType
                    ? <>选项来源：数据字典 <Text code>{dictType}</Text>。下方为目录默认/已覆盖列表；可编辑后发布，或点「从字典同步」。</>
                    : <>选项来源：系统枚举 <Text code>{enumSource}</Text></>}
                </span>
              }
            />
          )}
          <Input.TextArea
            size="small"
            rows={Math.min(12, Math.max(4, (field.options || []).length || 4))}
            key={`${field.id}-opts-${(field.options || []).length}-${optText.slice(0, 24)}`}
            defaultValue={optText}
            placeholder={dictType ? '空则业务页回退读数据字典' : '每行一个选项'}
            onBlur={(e) => onPatch({
              options: e.target.value.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
                const [a, b] = l.split('|')
                const raw = (b ?? a).trim()
                return { label: a.trim(), value: raw }
              }),
            })}
          />
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
      {(field.type === 'person' || field.type === 'person_multi') && (
        <PickableScopePropsEditor
          kind="person"
          value={(field.props?.pickable_scope as PickableScope | undefined) || null}
          scopeOptions={personScopeOptions}
          showDeptFilterSwitch
          onChange={(next) => {
            const props = { ...(field.props || {}) }
            if (next) props.pickable_scope = next
            else delete props.pickable_scope
            onPatch({ props })
          }}
        />
      )}
      {(field.type === 'department' || field.type === 'department_multi') && (
        <PickableScopePropsEditor
          kind="department"
          value={(field.props?.pickable_scope as PickableScope | undefined) || null}
          scopeOptions={deptScopeOptions}
          onChange={(next) => {
            const props = { ...(field.props || {}) }
            if (next) props.pickable_scope = next
            else delete props.pickable_scope
            onPatch({ props })
          }}
        />
      )}

      {field.type === 'detail_table' && (
        <DetailColumnsEditor
          columns={field.detail_table_columns || []}
          onChange={(cols) => onPatch({ detail_table_columns: cols })}
        />
      )}

      <Divider style={{ margin: '6px 0' }} />
      <Button size="small" block onClick={() => setPermOpen(true)}>
        字段权限{(field.visible_roles?.length || field.unmask_roles?.length || field.edit_roles?.length || field.download_roles?.length) ? ' ●' : ''}
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
          {(field.type === 'file' || field.type === 'image') && (
            <div>
              <div style={{ marginBottom: 4, fontSize: 13 }}>可下载/打开角色<Text type="secondary" style={{ marginLeft: 6, fontSize: 12 }}>留空=可见即可打开;非空仅名单内角色+本单发起人</Text></div>
              <Select mode="multiple" allowClear style={{ width: '100%' }} placeholder="仅这些角色可预览/下载附件"
                value={field.download_roles || []} options={roleOptions} onChange={(v) => onPatch({ download_roles: v.length ? v : null })} />
            </div>
          )}
          <Text type="secondary" style={{ fontSize: 12 }}>
            说明: 优先级 隐藏 &gt; 脱敏 &gt; 只读；被脱敏的字段一律不可编辑。
            附件另可配「可下载/打开角色」。后端按登录者角色在列表/详情/导出上强制裁剪，设计器预览不受限。
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

function RulesEditor({ fields, rules, onChange, systemRules = [], systemDefaults = [], onSystemChange }: {
  fields: FieldDefinition[]
  rules: FormRule[]
  onChange: (r: FormRule[]) => void
  systemRules?: FormRule[]
  systemDefaults?: FormRule[]
  onSystemChange?: (r: FormRule[]) => void
}) {
  const fieldOpts = (() => {
    const top = fields.filter((f) => f.type !== 'detail_table').map((f) => ({ value: f.id, label: f.label }))
    // 子表列也可作规则条件（引擎按「任一行」求值）
    const cols = fields.flatMap((f) =>
      (f.type === 'detail_table' ? (f.detail_table_columns || []) : []).map((c) => ({
        value: c.id, label: `${f.label}.${c.label}`,
      })),
    )
    return [...top, ...cols]
  })()
  const addRule = () => onChange([...rules, {
    id: 'rule' + Math.random().toString(36).slice(2, 8), type: 'visibility', target_field_ids: [],
    condition: { rel: 'and', cond: [{ field: fields[0]?.id || '', operator: 'eq', value: '' }] }, action: { visible: true },
  }])
  const resetSys = (id: string) => {
    if (!onSystemChange) return
    const def = systemDefaults.find((d) => d.id === id)
    if (!def) return
    onSystemChange(systemRules.map((r) => (r.id === id ? { ...def, enabled: true } : r)))
  }

  return (
    <div>
      {systemRules.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 8 }}
            message="系统规则（可编辑）"
            description="产品默认显隐/必填，可改条件与动作、可停用；保存后覆盖生效。点「恢复默认」还原该条目录配置。"
          />
          {systemRules.map((r, i) => (
            <RuleCard
              key={r.id}
              rule={r}
              fields={fields}
              fieldOpts={fieldOpts}
              isSystem
              onChange={(nr) => onSystemChange?.(systemRules.map((x, k) => (k === i ? nr : x)))}
              onReset={() => resetSys(r.id)}
            />
          ))}
          <Divider style={{ margin: '12px 0' }} />
        </div>
      )}
      <Text strong style={{ display: 'block', marginBottom: 8 }}>租户规则</Text>
      <Button type="dashed" block icon={<PlusOutlined />} onClick={addRule} style={{ marginBottom: 12 }}>新增规则</Button>
      {rules.length === 0 && <Empty description="暂无租户规则。示例: 当「类型=其他」时 显示「说明」字段。" />}
      {rules.map((r, i) => (
        <RuleCard
          key={r.id}
          rule={r}
          fields={fields}
          fieldOpts={fieldOpts}
          onChange={(nr) => onChange(rules.map((x, k) => (k === i ? nr : x)))}
          onDelete={() => onChange(rules.filter((_, k) => k !== i))}
        />
      ))}
    </div>
  )
}

function RuleCard({ rule: r, fields, fieldOpts, onChange, onDelete, onReset, isSystem }: {
  rule: FormRule
  fields: FieldDefinition[]
  fieldOpts: { value: string; label: string }[]
  onChange: (r: FormRule) => void
  onDelete?: () => void
  onReset?: () => void
  isSystem?: boolean
}) {
  const fieldsById = useMemo(() => {
    const m = new Map<string, FieldDefinition>()
    for (const f of fields) {
      m.set(f.id, f)
      for (const c of f.detail_table_columns || []) m.set(c.id, c as FieldDefinition)
    }
    return m
  }, [fields])
  const fields0 = fieldOpts[0]?.value || ''
  const conds: { field: string; operator: string; value?: unknown }[] = (() => {
    const c = r.condition
    if (Array.isArray(c.cond) && c.cond.length) {
      return c.cond.map((n) => {
        if (n && typeof n === 'object' && 'field' in n) {
          const item = n as { field?: string; operator?: string; value?: unknown }
          return { field: item.field || '', operator: item.operator || 'eq', value: item.value }
        }
        return { field: fields0, operator: 'eq', value: '' }
      })
    }
    if (c.field && c.operator) return [{ field: c.field, operator: c.operator, value: c.value }]
    return [{ field: fields0, operator: 'eq', value: '' }]
  })()
  const setConds = (cond: { field: string; operator: string; value?: unknown }[]) =>
    onChange({ ...r, condition: { rel: r.condition.rel || 'and', cond } })
  const setAction = (key: string) => {
    const a = RULE_ACTIONS.find((x) => x.key === key)!
    onChange({ ...r, type: a.type as FormRule['type'], action: { ...a.action } })
  }
  const disabled = r.enabled === false

  return (
    <Card
      size="small"
      style={{ marginBottom: 10, opacity: disabled ? 0.55 : 1, background: isSystem ? '#fafafa' : undefined }}
      title={
        <Space size={4} wrap>
          {isSystem && <Tag color="gold">系统</Tag>}
          <span>当满足</span>
          <Select
            size="small" style={{ width: 70 }} value={r.condition.rel || 'and'}
            options={[{ label: '全部', value: 'and' }, { label: '任一', value: 'or' }]}
            disabled={disabled}
            onChange={(v) => onChange({ ...r, condition: { ...r.condition, rel: v } })}
          />
          <span>条件时</span>
        </Space>
      }
      extra={
        <Space size={4}>
          {isSystem && (
            <>
              <Tooltip title="停用后本条不参与求值">
                <Switch
                  size="small"
                  checked={r.enabled !== false}
                  checkedChildren="开"
                  unCheckedChildren="关"
                  onChange={(v) => onChange({ ...r, enabled: v })}
                />
              </Tooltip>
              <Button size="small" type="link" onClick={onReset}>恢复默认</Button>
            </>
          )}
          {onDelete && (
            <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={onDelete} />
          )}
        </Space>
      }
    >
      {isSystem && (
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 6 }}>{r.id}</Text>
      )}
      {conds.map((c, ci) => {
        const noVal = c.operator === 'is_empty' || c.operator === 'is_not_empty'
        const srcField = fieldsById.get(c.field)
        const choiceOpts = (srcField?.options || []).map((o) => ({ value: o.value, label: o.label || o.value }))
        const useChoice = choiceOpts.length > 0 && (c.operator === 'eq' || c.operator === 'ne' || c.operator === 'in' || c.operator === 'not_in')
        return (
          <div key={ci} style={{ display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' }}>
            <Select size="small" style={{ width: 120 }} placeholder="字段" value={c.field || undefined} options={fieldOpts}
              disabled={disabled}
              onChange={(v) => setConds(conds.map((x, k) => (k === ci ? { ...x, field: v, value: undefined } : x)))} />
            <Select size="small" style={{ width: 110 }} value={c.operator} options={RULE_OPS}
              disabled={disabled}
              onChange={(v) => setConds(conds.map((x, k) => (k === ci ? { ...x, operator: v } : x)))} />
            {!noVal && (
              useChoice ? (
                <Select
                  size="small"
                  style={{ flex: 1, minWidth: 160 }}
                  placeholder="选择选项"
                  mode={c.operator === 'in' || c.operator === 'not_in' ? 'multiple' : undefined}
                  options={choiceOpts}
                  disabled={disabled}
                  value={
                    c.operator === 'in' || c.operator === 'not_in'
                      ? (Array.isArray(c.value) ? c.value : (c.value != null && c.value !== '' ? [c.value] : []))
                      : (c.value as string | undefined)
                  }
                  onChange={(v) => setConds(conds.map((x, k) => (k === ci ? { ...x, value: v } : x)))}
                />
              ) : (
                <Input size="small" style={{ flex: 1 }} placeholder="值"
                  value={Array.isArray(c.value) ? c.value.join(',') : ((c.value as string) ?? '')}
                  disabled={disabled}
                  onChange={(e) => {
                    const raw = e.target.value
                    const value = c.operator === 'in'
                      ? raw.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
                      : raw
                    setConds(conds.map((x, k) => (k === ci ? { ...x, value } : x)))
                  }}
                />
              )
            )}
            <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={disabled || conds.length <= 1}
              onClick={() => setConds(conds.filter((_, k) => k !== ci))} />
          </div>
        )
      })}
      <Button size="small" type="link" icon={<PlusOutlined />} disabled={disabled}
        onClick={() => setConds([...conds, { field: fields0, operator: 'eq', value: '' }])}>加条件</Button>
      <Divider style={{ margin: '8px 0' }} />
      <Space wrap size={6}>
        <Tooltip title="满足条件时对目标字段执行的动作"><Text type="secondary" style={{ fontSize: 12 }}>则</Text></Tooltip>
        <Select size="small" style={{ width: 90 }} value={actionKeyOf(r)} options={RULE_ACTIONS.map((a) => ({ label: a.label, value: a.key }))}
          disabled={disabled} onChange={setAction} />
        <Select size="small" mode="multiple" style={{ minWidth: 220 }} placeholder="目标字段"
          value={r.target_field_ids?.length ? r.target_field_ids : (r.target_field_id ? [r.target_field_id] : [])}
          options={fieldOpts} disabled={disabled}
          onChange={(v) => onChange({ ...r, target_field_ids: v, target_field_id: v[0] || '' })} />
      </Space>
    </Card>
  )
}
