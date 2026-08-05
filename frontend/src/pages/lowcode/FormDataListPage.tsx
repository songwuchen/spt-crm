// 扩展平台 → 表单数据列表: 某模板的填报记录(看/改/删 + 去填报)。
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  Button, Space, Tag, Modal, message, Popconfirm, Typography,
} from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { ArrowLeftOutlined, PlusOutlined, DownloadOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { downloadFile } from '@/utils/download'
import type { FieldDefinition, FormRule, FormInstance, WfInstanceDetail } from '@/types/lowcode'
import FormRenderer, { validateRequired, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { useAuthStore } from '@/stores/useAuthStore'
import { DRAWING_FORM_LAYOUT, applyDrawingFormLayout } from '@/constants/drawingFormLayout'
import { getPersonLabelMap } from '@/components/lowcode/fields/PersonField'
import { getDeptNameMap } from '@/components/lowcode/fields/DeptField'
import { getProjectLabelMap } from '@/components/lowcode/fields/ProjectField'
import { getContractLabelMap } from '@/components/lowcode/fields/ContractField'
import { getCustomerLabelMap } from '@/components/lowcode/fields/CustomerField'

const { Title, Text } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'gold', text: '审批中' },
  completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

/** 列表不宜展开的重字段类型 */
const LIST_EXCLUDE_TYPES = new Set([
  'formula', 'detail_table', 'file', 'image', 'rich_text', 'signature',
  'textarea', 'address', 'location', 'cascade', 'sub_table_data',
  'section', 'separator',
])

/** 列表优先展示的类型（同优先级按 schema 顺序） */
const LIST_PRIORITY = new Set([
  'auto_number', 'text', 'number', 'amount', 'date', 'datetime',
  'select', 'radio', 'checkbox', 'switch', 'person', 'department', 'project', 'contract', 'customer',
])

function pickListColumns(fields: FieldDefinition[], max = 8): FieldDefinition[] {
  const listable = fields.filter((f) => {
    if (LIST_EXCLUDE_TYPES.has(f.type)) return false
    // 人员/部门旁常有「xxx（文本）」伴随字段，列表里优先显示解析后的人员列，跳过空文本桩
    if (/_text$|（文本）|\(文本\)$/.test(f.id) || /文本/.test(f.label || '')) return false
    if (f.type === 'section' || f.type === 'separator') return false
    return true
  })
  const preferred = listable.filter((f) => LIST_PRIORITY.has(f.type))
  const rest = listable.filter((f) => !LIST_PRIORITY.has(f.type))
  // 流水号靠前；人员/部门稍靠后，避免一屏全是姓名列挤掉业务字段
  const sorted = [
    ...preferred.filter((f) => f.type === 'auto_number'),
    ...preferred.filter((f) => f.type !== 'auto_number' && f.type !== 'person' && f.type !== 'department'
      && f.type !== 'person_multi' && f.type !== 'department_multi'),
    ...preferred.filter((f) => f.type === 'person' || f.type === 'department'
      || f.type === 'person_multi' || f.type === 'department_multi'),
    ...rest,
  ]
  return sorted.slice(0, max)
}

type NameMaps = {
  users: Record<string, string>
  depts: Record<string, string>
  projects: Record<string, string>
  contracts: Record<string, string>
  customers: Record<string, string>
}

function collectIds(v: unknown): string[] {
  if (v == null || v === '') return []
  if (Array.isArray(v)) {
    return v.flatMap((x) => {
      if (typeof x === 'object' && x && 'id' in x) return [String((x as { id: string }).id)]
      return x != null && x !== '' ? [String(x)] : []
    })
  }
  if (typeof v === 'object' && v && 'id' in v) return [String((v as { id: string }).id)]
  return [String(v)]
}

function cellText(field: FieldDefinition, v: unknown, maps?: NameMaps): string {
  if (v == null || v === '') return '—'
  const opts = field.options || []
  const labelOf = (x: unknown) => opts.find((o) => o.value === x)?.label ?? String(x)
  if (field.type === 'select' || field.type === 'radio') return labelOf(v)
  if (field.type === 'checkbox' || field.type === 'multi_select') {
    if (Array.isArray(v)) return v.map(labelOf).join('，') || '—'
  }
  if (field.type === 'switch') return v ? '是' : '否'
  if (field.type === 'detail_table') return `${(v as unknown[]).length} 行`
  if (field.type === 'amount') return `¥${Number(v).toFixed(2)}`
  if (field.type === 'department' || field.type === 'department_multi') {
    if (typeof v === 'object' && v !== null && 'name' in (v as object) && !Array.isArray(v)) {
      return String((v as { name?: string }).name || '—')
    }
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.depts[id] || id).join('，')
  }
  if (field.type === 'person' || field.type === 'person_multi') {
    if (typeof v === 'object' && v !== null && !Array.isArray(v)
      && ('name' in (v as object) || 'real_name' in (v as object))) {
      const o = v as { name?: string; real_name?: string }
      return String(o.real_name || o.name || '—')
    }
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.users[id] || id).join('，')
  }
  if (field.type === 'project') {
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.projects[id] || id).join('，')
  }
  if (field.type === 'contract') {
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.contracts[id] || id).join('，')
  }
  if (field.type === 'customer') {
    const ids = collectIds(v)
    if (!ids.length) return '—'
    return ids.map((id) => maps?.customers[id] || id).join('，')
  }
  if (Array.isArray(v)) return v.map(labelOf).join('，')
  return String(v)
}

type ViewRec = {
  fields: FieldDefinition[]
  value: Record<string, unknown>
  readonly: boolean
  id: string
  process_instance_id?: string | null
  rules: FormRule[]
  status?: string
}

export default function FormDataListPage({
  templateId: propId,
  moduleTitle,
  fillPath: fillPathProp,
  templateCode,
}: {
  /** 侧栏模块传入；缺省则从路由 /lowcode/forms/:id/data 取 */
  templateId?: string
  moduleTitle?: string
  /** 侧栏模块显式指定「新增」路径，避免落到 /lowcode/forms/... 导致菜单高亮错乱 */
  fillPath?: string
  /** 内置模块 code，用于图纸表单分区布局 */
  templateCode?: string
} = {}) {
  const { id: paramId = '' } = useParams()
  const id = propId || paramId
  const nav = useNavigate()
  const location = useLocation()
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const [name, setName] = useState('')
  const [colFields, setColFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [items, setItems] = useState<FormInstance[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [viewRec, setViewRec] = useState<ViewRec | null>(null)
  const [wfDetail, setWfDetail] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)
  const [nameMaps, setNameMaps] = useState<NameMaps>({
    users: {}, depts: {}, projects: {}, contracts: {}, customers: {},
  })
  const isModule = Boolean(propId)
  const fillPath = fillPathProp
    || (isModule ? `${location.pathname.replace(/\/$/, '')}/fill` : `/lowcode/forms/${id}/fill`)
  const drawingLayout = templateCode ? DRAWING_FORM_LAYOUT[templateCode] : undefined

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await lowcodeApi.listInstances({ template_id: id, pageNo, pageSize: 20 })
      setItems(res.data.items)
      setTotal(res.data.total)
    } finally { setLoading(false) }
  }, [id, pageNo])

  useEffect(() => {
    if (!id) return
    (async () => {
      const tpl = await lowcodeApi.getTemplate(id)
      setName(tpl.data.name)
      try {
        const ver = await lowcodeApi.publishedVersion(id)
        const fs = (ver.data.field_definitions as FieldDefinition[]) || []
        setColFields(pickListColumns(fs))
        setRules((ver.data.rule_definitions as FormRule[]) || [])
      } catch { /* 未发布 */ }
    })()
  }, [id])
  useEffect(() => { load() }, [load])

  // 列表里 person/department/project/contract/customer 存的是 id，需解析成显示名
  useEffect(() => {
    if (!items.length || !colFields.length) return
    const personIds: string[] = []
    const projectIds: string[] = []
    const contractIds: string[] = []
    const customerIds: string[] = []
    const needDept = colFields.some((f) => f.type === 'department' || f.type === 'department_multi')
    for (const f of colFields) {
      if (f.type === 'person' || f.type === 'person_multi') {
        for (const row of items) personIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'project') {
        for (const row of items) projectIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'contract') {
        for (const row of items) contractIds.push(...collectIds(row.form_data?.[f.id]))
      }
      if (f.type === 'customer') {
        for (const row of items) customerIds.push(...collectIds(row.form_data?.[f.id]))
      }
    }
    let alive = true
    ;(async () => {
      const [users, depts, projects, contracts, customers] = await Promise.all([
        personIds.length ? getPersonLabelMap(personIds) : Promise.resolve({}),
        needDept ? getDeptNameMap() : Promise.resolve({}),
        projectIds.length ? getProjectLabelMap(projectIds) : Promise.resolve({}),
        contractIds.length ? getContractLabelMap(contractIds) : Promise.resolve({}),
        customerIds.length ? getCustomerLabelMap(customerIds) : Promise.resolve({}),
      ])
      if (!alive) return
      setNameMaps({ users, depts, projects, contracts, customers })
    })()
    return () => { alive = false }
  }, [items, colFields])

  const loadWorkflow = async (recId: string, processInstanceId?: string | null) => {
    try {
      if (processInstanceId) {
        const res = await workflowApi.instance(processInstanceId)
        setWfDetail(res.data || null)
        return
      }
      const res = await workflowApi.byFormInstance({ form_instance_id: recId })
      setWfDetail(res.data || null)
    } catch {
      setWfDetail(null)
    }
  }

  const openView = async (recId: string, readonly: boolean) => {
    const res = await lowcodeApi.getInstance(recId)
    const detailRules = (res.data.rule_definitions as FormRule[] | undefined)
    setViewRec({
      fields: res.data.field_definitions,
      value: res.data.form_data,
      readonly,
      id: recId,
      process_instance_id: res.data.process_instance_id,
      rules: detailRules?.length ? detailRules : rules,
      status: res.data.status,
    })
    setWfDetail(null)
    await loadWorkflow(recId, res.data.process_instance_id)
  }

  const closeView = () => {
    setViewRec(null)
    setWfDetail(null)
  }

  const saveEdit = async () => {
    if (!viewRec) return
    const displayFields = drawingLayout
      ? applyDrawingFormLayout(templateCode, viewRec.fields)
      : viewRec.fields
    const states = computeFieldStates(
      displayFields, viewRec.value, viewRec.rules,
      deriveRolePerms(displayFields, userRoles),
    )
    const e = validateRequired(displayFields, states, viewRec.value)
    if (e) { message.error(e); return }
    await lowcodeApi.updateInstance(viewRec.id, { form_data: viewRec.value })
    message.success('已保存')
    closeView()
    load()
  }

  const handleWfComment = async (content: string) => {
    if (!wfDetail?.id) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfDetail.id, content)
      message.success('评论已发表')
      await loadWorkflow(viewRec!.id, wfDetail.id)
    } catch {
      message.error('发表评论失败')
    } finally {
      setWfCommenting(false)
    }
  }

  const del = async (recId: string) => {
    await lowcodeApi.deleteInstance(recId)
    message.success('已删除')
    load()
  }

  const columns = [
    // 侧栏业务模块不展示空的「单号/标题」（本类表单以图纸编号等业务字段为主）
    ...(!isModule ? [
      { title: '单号', dataIndex: 'business_no', key: 'business_no', render: (v: string) => v || '—' },
      { title: '标题', dataIndex: 'title', key: 'title', render: (v: string) => v || '—' },
    ] : []),
    ...colFields.map((f) => ({
      title: f.label, key: f.id, ellipsis: true,
      width: (f.type === 'person' || f.type === 'department') ? 120 : 140,
      render: (_: unknown, r: FormInstance) => cellText(f, r.form_data?.[f.id], nameMaps),
    })),
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90, fixed: 'right' as const,
      render: (s: string) => { const t = STATUS_TAG[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> },
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170, fixed: 'right' as const,
      render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—'),
    },
    {
      title: '操作', key: 'op', width: 180, fixed: 'right' as const,
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

  const showFlowPane = !!wfDetail || (
    !!viewRec && ['submitted', 'running', 'completed', 'rejected'].includes(viewRec.status || '')
  )
  const modalWidth = wfDetail || showFlowPane
    ? 1100
    : (drawingLayout ? 960 : 780)
  const displayFields = viewRec
    ? (drawingLayout ? applyDrawingFormLayout(templateCode, viewRec.fields) : viewRec.fields)
    : []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }} className="shrink-0">
        <Space>
          {!isModule && (
            <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
          )}
          <Title level={4} style={{ margin: 0 }}>{moduleTitle || name}{isModule ? '' : ' · 数据'}</Title>
        </Space>
        <Space>
          <Button icon={<DownloadOutlined />} disabled={total === 0}
            onClick={() => downloadFile(`/api/v1/lc/form-instances/export?template_id=${encodeURIComponent(id)}`, `${name || '表单数据'}.xlsx`)}>
            导出
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav(fillPath)}>新增</Button>
        </Space>
      </div>
      <FillHeightTable
          rowKey="id" loading={loading} columns={columns} dataSource={items}
          scroll={{ x: Math.max(1100, 140 * colFields.length + 440) }}
          pagination={{ current: pageNo, total, pageSize: 20, onChange: setPageNo, showSizeChanger: false }}
        />

      <Modal
        title={viewRec?.readonly ? '查看记录' : '编辑记录'} open={!!viewRec} width={modalWidth}
        onCancel={closeView}
        footer={viewRec?.readonly ? null : [
          <Button key="c" onClick={closeView}>取消</Button>,
          <Button key="s" type="primary" onClick={saveEdit}>保存</Button>,
        ]}
        destroyOnClose
        styles={{ body: { paddingTop: 12 } }}
      >
        {viewRec && (
          <div className="flex gap-0" style={{ minHeight: 480 }}>
            <div className="flex-1 overflow-y-auto pr-3" style={{ maxHeight: '70vh' }}>
              <FormRenderer
                fields={displayFields}
                rules={viewRec.rules}
                mode={viewRec.readonly ? 'readonly' : 'edit'}
                value={viewRec.value}
                onChange={(v) => setViewRec((s) => (s ? { ...s, value: v } : s))}
              />
            </div>
            {showFlowPane && (
              <div
                className="w-[300px] shrink-0 overflow-hidden rounded-md border border-slate-200"
                style={{ maxHeight: '70vh' }}
              >
                {wfDetail ? (
                  <WfFlowDynamics
                    steps={wfDetail.flow_steps || []}
                    comments={wfDetail.comments || []}
                    onSubmitComment={handleWfComment}
                    commenting={wfCommenting}
                  />
                ) : (
                  <div className="h-full flex items-center justify-center bg-slate-50 px-4">
                    <Text type="secondary" className="text-sm">暂无流程动态</Text>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
