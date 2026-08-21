// 扩展平台 → 流程可视化设计器(@xyflow 拖拽画布)。节点(开始/审批/抄送/结束)+ 连线(可挂条件分支)。
// 复用后端 save_design/publish;节点位置存 node.position(JSONB),条件存 route.condition。
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap, Handle, Position,
  addEdge, useNodesState, useEdgesState, useReactFlow,
  type Node, type Edge, type Connection, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import {
  Card, Button, Space, Input, InputNumber, Select, Switch, Typography, Tag, message, Empty, Divider,
  Checkbox,
} from 'antd'
import {
  ArrowLeftOutlined, PlusOutlined, DeleteOutlined, PlayCircleOutlined, StopOutlined,
  UserOutlined, NotificationOutlined, PartitionOutlined, ColumnHeightOutlined,
} from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfNode, WfRoute, WfDesign, FieldDefinition, WfFieldPerm } from '@/types/lowcode'
import PersonField from '@/components/lowcode/fields/PersonField'
import DeptField from '@/components/lowcode/fields/DeptField'
import { ApproverRuleEditor } from '@/components/lowcode/ApproverRuleEditor'
import { defaultCcApproverRule } from '@/utils/wfApproverDefaults'
import { fieldOption } from '@/components/lowcode/fieldTypeIcon'
import {
  routeEdgeLabel, edgeStroke,
} from '@/utils/wfCanvasEdgeLabel'

const { Title, Text } = Typography

const MULTI_MODES = [
  { value: 'or_sign', label: '或签(一人通过即可)' },
  { value: 'countersign', label: '会签(全部通过)' },
  { value: 'sequential', label: '顺序会签' },
]

/** 历史别名 and_sign → 会签；Select 无匹配 option 时会直接显示英文 value */
function normalizeMultiMode(mode?: string | null): WfNode['multi_mode'] {
  if (mode === 'and_sign') return 'countersign'
  if (mode === 'countersign' || mode === 'sequential' || mode === 'or_sign') return mode
  return 'or_sign'
}
const OPERATORS = [
  { value: 'eq', label: '等于' }, { value: 'ne', label: '不等于' },
  { value: 'in', label: '属于(in)' }, { value: 'not_in', label: '不属于' },
  { value: 'gt', label: '大于' }, { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' }, { value: 'lte', label: '小于等于' },
  { value: 'contains', label: '包含' },
  { value: 'is_empty', label: '为空' }, { value: 'is_not_empty', label: '不为空' },
]

type CondLeaf = { field: string; operator: string; value?: unknown }

function buildRfEdge(route: WfRoute, all: WfRoute[], fields: FieldDefinition[]): Edge {
  const lab = routeEdgeLabel(route, all, fields)
  const labelNode: ReactNode = lab?.text
    ? <span title={lab.title}>{lab.text}</span>
    : undefined
  return {
    id: route.id,
    source: route.source,
    target: route.target,
    type: 'smoothstep',
    label: labelNode,
    data: { route },
    style: { stroke: edgeStroke(route), strokeWidth: 1.6 },
    labelStyle: { fill: '#334155', fontSize: 11, fontWeight: 500 },
    labelBgStyle: { fill: '#ffffff', fillOpacity: 0.95 },
    labelBgPadding: [5, 7] as [number, number],
    labelBgBorderRadius: 4,
  }
}

function valueToInput(v: unknown): string {
  if (Array.isArray(v)) return v.map(String).join(',')
  if (v == null) return ''
  return String(v)
}

function parseCondValue(operator: string, raw: string): unknown {
  if (operator === 'in' || operator === 'not_in') {
    return raw.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  }
  return raw
}

function asMultiList(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String).filter((x) => x !== '')
  if (v == null || v === '') return []
  return String(v).split(/[,，]/).map((s) => s.trim()).filter(Boolean)
}

function asSingle(v: unknown): string | undefined {
  if (Array.isArray(v)) return v.length ? String(v[0]) : undefined
  if (v == null || v === '') return undefined
  return String(v)
}

/** 连线条件值：按字段类型用选择器，避免部门/选项只显示原始 id/code */
function CondValueInput({
  field, operator, value, onChange,
}: {
  field?: FieldDefinition
  operator: string
  value: unknown
  onChange: (v: unknown) => void
}) {
  const multi = operator === 'in' || operator === 'not_in'
  const t = field?.type

  if (t === 'department' || t === 'department_multi') {
    return (
      <DeptField
        multi={multi}
        value={multi ? asMultiList(value) : asSingle(value)}
        onChange={(nv) => onChange(multi ? (Array.isArray(nv) ? nv : []) : nv)}
        placeholder={multi ? '选择部门（可多选）' : '选择部门'}
      />
    )
  }

  if (t === 'person' || t === 'person_multi') {
    return (
      <PersonField
        multi={multi}
        value={multi ? asMultiList(value) : asSingle(value)}
        onChange={(nv) => onChange(multi ? (Array.isArray(nv) ? nv : []) : nv)}
        placeholder={multi ? '选择人员（可多选）' : '选择人员'}
      />
    )
  }

  if (t === 'select' || t === 'radio' || t === 'multi_select' || t === 'checkbox') {
    const opts = (field?.options || []).map((o) => ({ label: o.label, value: String(o.value) }))
    return (
      <Select
        size="small"
        style={{ width: '100%' }}
        mode={multi ? 'multiple' : undefined}
        allowClear
        showSearch
        optionFilterProp="label"
        options={opts}
        value={multi ? asMultiList(value) : asSingle(value)}
        onChange={(v) => onChange(v ?? (multi ? [] : undefined))}
        placeholder={multi ? '选择选项（可多选）' : '选择选项'}
      />
    )
  }

  if (t === 'switch') {
    return (
      <Select
        size="small"
        style={{ width: '100%' }}
        allowClear
        options={[
          { label: '是 / 开', value: 'true' },
          { label: '否 / 关', value: 'false' },
        ]}
        value={value == null || value === '' ? undefined : String(value)}
        onChange={(v) => onChange(v === 'true' ? true : v === 'false' ? false : v)}
        placeholder="选择"
      />
    )
  }

  if ((t === 'number' || t === 'amount') && !multi) {
    return (
      <InputNumber
        size="small"
        style={{ width: '100%' }}
        value={value == null || value === '' ? null : Number(value)}
        onChange={(v) => onChange(v)}
        placeholder="数值"
      />
    )
  }

  return (
    <Input
      size="small"
      placeholder={multi ? '多个值用逗号分隔' : '值'}
      value={valueToInput(value)}
      onChange={(e) => onChange(parseCondValue(operator, e.target.value))}
    />
  )
}
const genId = (p: string) => p + Math.random().toString(36).slice(2, 7)

const NODE_META: Record<string, { color: string; label: string; icon: ReactNode }> = {
  start: { color: '#12b876', label: '开始', icon: <PlayCircleOutlined /> },
  approval: { color: '#2f6bff', label: '审批', icon: <UserOutlined /> },
  cc: { color: '#64748b', label: '抄送', icon: <NotificationOutlined /> },
  end: { color: '#8c8c8c', label: '结束', icon: <StopOutlined /> },
  parallel: { color: '#fa8c16', label: '并行', icon: <PartitionOutlined /> },
  merge: { color: '#fa8c16', label: '汇聚', icon: <PartitionOutlined /> },
}
const TIMEOUT_ACTIONS = [
  { value: 'notify', label: '仅提醒' },
  { value: 'auto_approve', label: '自动通过' },
  { value: 'auto_reject', label: '自动驳回' },
  { value: 'auto_transfer', label: '自动转交' },
]

// ---- 自定义节点 ----
function WfNodeComp({ data, selected }: NodeProps) {
  const d = data as { node: WfNode; pathRole?: 'self' | 'from' | 'to' }
  const meta = NODE_META[d.node.type] || NODE_META.approval
  const role = d.pathRole
  const ring =
    selected || role === 'self' ? meta.color
      : role === 'from' ? '#13c2c2'
        : role === 'to' ? '#1677ff'
          : '#e5e7eb'
  const ringWidth = selected || role === 'self' || role === 'from' || role === 'to' ? 2 : 1.5
  return (
    <div style={{
      minWidth: 158, maxWidth: 220, padding: '10px 16px', borderRadius: 10, background: '#fff',
      border: `${ringWidth}px solid ${ring}`,
      boxShadow: (selected || role === 'self')
        ? `0 0 0 2px ${meta.color}33`
        : role === 'from' || role === 'to'
          ? `0 0 0 2px ${ring}22`
          : '0 1px 4px rgba(15,23,42,0.08)',
      display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
    }}>
      <span style={{
        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
        background: `${meta.color}14`, color: meta.color,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
      }}>
        {meta.icon}
      </span>
      <span style={{ fontWeight: 500, color: '#1e293b', lineHeight: 1.3, flex: 1 }}>{d.node.name}</span>
      {role === 'from' && (
        <span style={{ fontSize: 10, color: '#13c2c2', fontWeight: 600, flexShrink: 0 }}>来</span>
      )}
      {role === 'to' && (
        <span style={{ fontSize: 10, color: '#1677ff', fontWeight: 600, flexShrink: 0 }}>去</span>
      )}
      <Handle type="target" position={Position.Top} style={{ background: '#94a3b8', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#94a3b8', width: 8, height: 8 }} />
    </div>
  )
}
const nodeTypes = { wf: WfNodeComp }

const NODE_W = 180
const NODE_H = 52

function autoLayout(nodes: WfNode[], routes: WfRoute[]): Record<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', ranksep: 110, nodesep: 80, marginx: 40, marginy: 40 })
  g.setDefaultEdgeLabel(() => ({}))
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
  routes.forEach((r) => g.setEdge(r.source, r.target))
  dagre.layout(g)
  const pos: Record<string, { x: number; y: number }> = {}
  nodes.forEach((n) => {
    const gn = g.node(n.id)
    if (gn) pos[n.id] = { x: gn.x - NODE_W / 2, y: gn.y - NODE_H / 2 }
  })
  return pos
}

function DesignerInner() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const { fitView } = useReactFlow()
  const [name, setName] = useState('')
  const [bizType, setBizType] = useState<string | null>(null)
  const [formTemplateId, setFormTemplateId] = useState<string | null>(null)
  const [formFields, setFormFields] = useState<FieldDefinition[]>([])
  const [rfNodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selNode, setSelNode] = useState<string | null>(null)
  const [selEdge, setSelEdge] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      try {
        const def = await workflowApi.getDef(id)
        setName(def.data.name)
        setBizType(def.data.biz_type || null)
        setFormTemplateId(def.data.form_template_id || null)
        let fields: FieldDefinition[] = []
        if (def.data.form_template_id) {
          try {
            const v = await lowcodeApi.publishedVersion(def.data.form_template_id)
            fields = (v.data.field_definitions as FieldDefinition[]) || []
            setFormFields(fields)
          } catch { /* 未发布 */ }
        } else if (def.data.biz_type) {
          // 绑定业务类型的审批流没有表单：用业务字段目录填充条件分支/「表单人员字段」
          try {
            const r = await workflowApi.bizFields(def.data.biz_type)
            const list = Array.isArray(r.data) ? r.data : []
            fields = list.map((f) => ({
              id: f.id,
              label: f.label,
              type: f.type as FieldDefinition['type'],
            }))
            setFormFields(fields)
          } catch {
            message.warning('业务字段目录加载失败，抄送「表单人员字段」可能无选项')
            setFormFields([])
          }
        }
        const design = await workflowApi.loadDesign(id)
        let nodes = (design.data.node_definitions || []) as WfNode[]
        let routes = (design.data.route_definitions || []) as WfRoute[]
        if (nodes.length === 0) {
          nodes = [{ id: 'start', type: 'start', name: '开始' }, { id: 'end', type: 'end', name: '结束' }]
          routes = [{ id: 'r0', source: 'start', target: 'end' }]
        }
        const needLayout = nodes.some((n) => !n.position)
        const pos = needLayout ? autoLayout(nodes, routes) : {}
        setNodes(nodes.map((n) => ({
          id: n.id, type: 'wf',
          position: n.position || pos[n.id] || { x: 100, y: 100 },
          data: { node: n },
        })))
        setEdges(routes.map((r) => buildRfEdge(r, routes, fields)))
      } finally { setLoading(false) }
    })()
  }, [id])  // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = useCallback((c: Connection) => {
    const rid = genId('r')
    const route: WfRoute = { id: rid, source: c.source!, target: c.target! }
    setEdges((eds) => {
      const routes = [...eds.map((e) => (e.data as { route: WfRoute }).route), route]
      return addEdge(buildRfEdge(route, routes, formFields), eds)
    })
  }, [setEdges, formFields])

  const addNode = (type: 'approval' | 'cc' | 'parallel' | 'merge') => {
    const prefix = { approval: 'ap', cc: 'cc', parallel: 'par', merge: 'mrg' }[type]
    const nid = genId(prefix)
    const names = { approval: '审批', cc: '抄送', parallel: '并行网关', merge: '汇聚节点' }
    const node: WfNode = {
      id: nid, type, name: names[type],
      ...(type === 'approval' ? { approver_rule: { type: 'direct_supervisor' }, multi_mode: 'or_sign' as const } : {}),
      ...(type === 'cc' ? { approver_rule: defaultCcApproverRule(formFields) } : {}),
    }
    setNodes((nds) => [...nds, {
      id: nid, type: 'wf',
      position: { x: 120 + Math.random() * 80, y: 160 + nds.length * 40 },
      data: { node },
    }])
  }

  const patchNode = (nid: string, patch: Partial<WfNode>) => {
    setNodes((nds) => nds.map((n) => n.id === nid ? { ...n, data: { node: { ...(n.data as { node: WfNode }).node, ...patch } } } : n))
  }
  const patchRule = (nid: string, rule: NonNullable<WfNode['approver_rule']>) => {
    setNodes((nds) => nds.map((n) => {
      if (n.id !== nid) return n
      const node = (n.data as { node: WfNode }).node
      return { ...n, data: { node: { ...node, approver_rule: rule } } }
    }))
  }

  const remapEdges = useCallback((eds: Edge[]) => {
    const routes = eds.map((e) => (e.data as { route: WfRoute }).route)
    return eds.map((e) => buildRfEdge((e.data as { route: WfRoute }).route, routes, formFields))
  }, [formFields])

  const patchEdgeCond = (eid: string, cond: WfRoute['condition']) => {
    setEdges((eds) => {
      const next = eds.map((e) => {
        if (e.id !== eid) return e
        const route = { ...(e.data as { route: WfRoute }).route, condition: cond }
        return { ...e, data: { route } }
      })
      return remapEdges(next)
    })
  }

  const patchEdgeRoute = (eid: string, patch: Partial<WfRoute>) => {
    setEdges((eds) => {
      const next = eds.map((e) => {
        if (e.id !== eid) return e
        const route = { ...(e.data as { route: WfRoute }).route, ...patch }
        return { ...e, data: { route } }
      })
      return remapEdges(next)
    })
  }

  /** 同源非旁路边统一设/清互斥组 */
  const setSourceExclusive = (source: string, enabled: boolean) => {
    const gid = enabled ? `ex_${source}` : null
    setEdges((eds) => {
      const next = eds.map((e) => {
        const route = (e.data as { route: WfRoute }).route
        if (route.source !== source || route.always) return e
        const updated = { ...route, exclusive_group: gid }
        return { ...e, data: { route: updated } }
      })
      return remapEdges(next)
    })
  }

  const rearrangeLayout = () => {
    const nodes = rfNodes.map((n) => (n.data as { node: WfNode }).node)
    const routes = rfEdges.map((e) => (e.data as { route: WfRoute }).route)
    if (!nodes.length) return
    const pos = autoLayout(nodes, routes)
    setNodes((nds) => nds.map((n) => ({
      ...n,
      position: pos[n.id] || n.position,
    })))
    setEdges(routes.map((r) => buildRfEdge(r, routes, formFields)))
    requestAnimationFrame(() => {
      setTimeout(() => fitView({ padding: 0.18, duration: 220 }), 40)
    })
    message.success('已重新整理布局（保存草稿后生效）')
  }

  const delSelected = () => {
    if (selNode && !['start', 'end'].includes(selNode)) {
      setNodes((n) => n.filter((x) => x.id !== selNode))
      setEdges((e) => e.filter((x) => x.source !== selNode && x.target !== selNode))
      setSelNode(null)
    }
    if (selEdge) { setEdges((e) => e.filter((x) => x.id !== selEdge)); setSelEdge(null) }
  }

  const buildDesign = (): WfDesign => {
    const node_definitions = rfNodes.map((n) => ({ ...(n.data as { node: WfNode }).node, position: n.position }))
    const route_definitions = rfEdges.map((e) => (e.data as { route: WfRoute }).route)
    return { node_definitions, route_definitions, approver_rules: [] }
  }
  const save = async (publish = false) => {
    await workflowApi.saveDesign(id, buildDesign())
    if (publish) { await workflowApi.publish(id); message.success('已发布'); nav('/lowcode/workflows') }
    else message.success('草稿已保存')
  }

  const selectedNode = useMemo(() => rfNodes.find((n) => n.id === selNode), [rfNodes, selNode])
  const selectedEdge = useMemo(() => rfEdges.find((e) => e.id === selEdge), [rfEdges, selEdge])

  /** 对齐简道云：点选节点后，出边+入边高亮，并点亮相邻节点 */
  const displayNodes = useMemo(() => {
    const preds = new Set<string>()
    const succs = new Set<string>()
    if (selNode) {
      for (const e of rfEdges) {
        if (e.target === selNode) preds.add(e.source)
        if (e.source === selNode) succs.add(e.target)
      }
    }
    return rfNodes.map((n) => {
      const isSel = n.id === selNode
      const isPred = preds.has(n.id)
      const isSucc = succs.has(n.id)
      return {
        ...n,
        selected: isSel,
        style: {
          ...(n.style || {}),
          opacity: selNode && !isSel && !isPred && !isSucc ? 0.4 : 1,
        },
        data: {
          ...(n.data as object),
          pathRole: isSel ? 'self' : isPred ? 'from' : isSucc ? 'to' : undefined,
        },
      }
    })
  }, [rfNodes, rfEdges, selNode])
  const displayEdges = useMemo(() => {
    const OUT = '#1677ff'      // 往哪走
    const IN = '#13c2c2'       // 从哪来
    const DIM = '#cbd5e1'
    return rfEdges.map((e) => {
      const route = (e.data as { route: WfRoute } | undefined)?.route
      const baseStroke = route ? edgeStroke(route) : '#94a3b8'
      const isOut = !!selNode && e.source === selNode
      const isIn = !!selNode && e.target === selNode
      const isEdgePick = !!selEdge && e.id === selEdge
      if (isOut || isEdgePick) {
        return {
          ...e,
          style: { ...(e.style || {}), stroke: OUT, strokeWidth: 2.6, opacity: 1 },
          labelStyle: { ...(e.labelStyle || {}), fill: OUT, fontWeight: 600, fontSize: 11 },
          labelBgStyle: { fill: '#ffffff', fillOpacity: 0.98 },
          zIndex: 20,
        }
      }
      if (isIn) {
        return {
          ...e,
          style: { ...(e.style || {}), stroke: IN, strokeWidth: 2.4, opacity: 1 },
          labelStyle: { ...(e.labelStyle || {}), fill: IN, fontWeight: 600, fontSize: 11 },
          labelBgStyle: { fill: '#ffffff', fillOpacity: 0.98 },
          zIndex: 18,
        }
      }
      if (selNode) {
        return {
          ...e,
          style: { ...(e.style || {}), stroke: DIM, strokeWidth: 1.2, opacity: 0.35 },
          labelStyle: { ...(e.labelStyle || {}), fill: '#94a3b8', fontWeight: 400, fontSize: 11 },
          zIndex: 1,
        }
      }
      return {
        ...e,
        style: { ...(e.style || {}), stroke: baseStroke, strokeWidth: 1.6, opacity: 1 },
        zIndex: 2,
      }
    })
  }, [rfEdges, selNode, selEdge])

  if (loading) return <Card loading />

  const BIZ_LABEL: Record<string, string> = {
    contract_version: '合同版本（登记运营）',
    contract_review: '合同评审会签',
    lead: '线索',
    customer: '客户信息',
    order: '订单',
    quote_version: '报价单',
    service_ticket: '售后工单',
    change_request: '变更单',
    solution: '方案',
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/workflows')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>可视化流程 · {name}</Title>
          {bizType ? (
            <Tag color="geekblue">业务类型 · {BIZ_LABEL[bizType] || bizType}</Tag>
          ) : formTemplateId ? (
            <Tag color="blue">已绑定表单</Tag>
          ) : (
            <Tag>未绑定</Tag>
          )}
        </Space>
        <Space wrap>
          <Button icon={<PlusOutlined />} onClick={() => addNode('approval')}>审批节点</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('cc')}>抄送节点</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('parallel')}>并行网关</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('merge')}>汇聚节点</Button>
          <Button icon={<ColumnHeightOutlined />} onClick={rearrangeLayout}>整理布局</Button>
          <Button onClick={() => save(false)}>保存草稿</Button>
          <Button type="primary" onClick={() => save(true)}>保存并发布</Button>
        </Space>
      </div>
      {selNode && (
        <div style={{ marginBottom: 8, fontSize: 12, color: '#64748b' }}>
          <span style={{ color: '#13c2c2', fontWeight: 600 }}>青色线 /「来」</span>
          {' '}从哪来
          <span style={{ margin: '0 10px', color: '#e2e8f0' }}>|</span>
          <span style={{ color: '#1677ff', fontWeight: 600 }}>蓝色线 /「去」</span>
          {' '}往哪走
          <span style={{ marginLeft: 10, color: '#94a3b8' }}>（点空白取消）</span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 12 }}>
        <div style={{
          flex: 1, height: 720, border: '1px solid #e8ecf1', borderRadius: 10,
          background: '#f8fafc', overflow: 'hidden',
        }}>
          <ReactFlow
            nodes={displayNodes} edges={displayEdges} nodeTypes={nodeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onNodeClick={(_, n) => { setSelNode(n.id); setSelEdge(null) }}
            onEdgeClick={(_, e) => { setSelEdge(e.id); setSelNode(null) }}
            onPaneClick={() => { setSelNode(null); setSelEdge(null) }}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            minZoom={0.25}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ type: 'smoothstep' }}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} color="#cbd5e1" />
            <Controls />
            <MiniMap zoomable pannable />
          </ReactFlow>
        </div>

        <Card size="small" title="属性" style={{ width: 320 }}>
          {selectedNode ? (
            <NodeConfig node={(selectedNode.data as { node: WfNode }).node} formFields={formFields}
              onName={(v) => patchNode(selectedNode.id, { name: v })}
              onRule={(p) => patchRule(selectedNode.id, p)}
              onMode={(v) => patchNode(selectedNode.id, { multi_mode: v })}
              onPatch={(p) => patchNode(selectedNode.id, p)}
              onDelete={delSelected} />
          ) : selectedEdge ? (
            <EdgeConfig
              route={(selectedEdge.data as { route: WfRoute }).route}
              formFields={formFields}
              sourceExclusive={
                !!(selectedEdge.data as { route: WfRoute }).route.exclusive_group
                || rfEdges.some((e) => {
                  const r = (e.data as { route: WfRoute }).route
                  return r.source === (selectedEdge.data as { route: WfRoute }).route.source
                    && !r.always && !!r.exclusive_group
                })
              }
              onCond={(c) => patchEdgeCond(selectedEdge.id, c)}
              onExclusive={(on) => setSourceExclusive(
                (selectedEdge.data as { route: WfRoute }).route.source, on,
              )}
              onAlways={(on) => patchEdgeRoute(selectedEdge.id, { always: on || undefined })}
              onActivateOrder={(n) => patchEdgeRoute(selectedEdge.id, {
                activate_order: n == null ? undefined : n,
              })}
              onDelete={delSelected}
            />
          ) : (
            <Empty description="点击节点或连线编辑；拖动锚点连线" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      </div>
    </div>
  )
}

function NodeConfig({ node, formFields, onName, onRule, onMode, onPatch, onDelete }: {
  node: WfNode; formFields: FieldDefinition[]
  onName: (v: string) => void
  onRule: (rule: NonNullable<WfNode['approver_rule']>) => void
  onMode: (v: WfNode['multi_mode']) => void
  onPatch: (p: Partial<WfNode>) => void; onDelete: () => void
}) {
  const isEditable = node.type === 'approval' || node.type === 'cc'
  const to = node.timeout
  const permFieldEmptyHint = formFields.length === 0
    ? '未加载到表单字段：请确认本流程已绑定表单模板，且表单已发布'
    : '无可选字段'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Tag color={NODE_META[node.type]?.color}>{NODE_META[node.type]?.label}</Tag>
      <div><Text type="secondary" style={{ fontSize: 12 }}>节点名</Text>
        <Input size="small" value={node.name} onChange={(e) => onName(e.target.value)} /></div>
      {(node.type === 'parallel' || node.type === 'merge') && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {node.type === 'parallel'
            ? '并行网关: 从此节点引出的所有分支会同时进入审批。'
            : '汇聚节点: 等待所有并行分支到达后再继续(AND-join)。请让各并行分支都连到本节点。'}
        </Text>
      )}
      {isEditable && (
        <>
          <ApproverRuleEditor
            rule={node.approver_rule}
            formFields={formFields}
            roleLabel={node.type === 'approval' ? '审批人' : '抄送人'}
            onChange={onRule}
          />
          {node.type === 'cc' && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              抄送人与审批人共用同一套规则类型；可切换为「组合选人」以同时抄送发起人与表单人员字段。
            </Text>
          )}
          {node.type === 'approval' && (
            <>
              <div><Text type="secondary" style={{ fontSize: 12 }}>多人模式</Text>
                <Select size="small" style={{ width: '100%' }} value={normalizeMultiMode(node.multi_mode)} options={MULTI_MODES} onChange={onMode} /></div>
              <Divider style={{ margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>启用抄送</Text>
                <Switch
                  size="small"
                  checked={!!node.cc_rule}
                  onChange={(on) => onPatch({
                    cc_rule: on
                      ? (node.cc_rule || { type: 'specified_user', value: [] })
                      : undefined,
                  })}
                />
              </div>
              {node.cc_rule && (
                <ApproverRuleEditor
                  rule={node.cc_rule}
                  formFields={formFields}
                  roleLabel="抄送人员"
                  onChange={(r) => onPatch({ cc_rule: r })}
                />
              )}
              <Divider style={{ margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>审批超时(SLA)</Text>
                <Switch size="small" checked={!!to}
                  onChange={(on) => onPatch({ timeout: on ? { hours: 24, action: 'notify' } : null })} />
              </div>
              {to && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Text style={{ fontSize: 12 }}>超过</Text>
                    <InputNumber size="small" min={0.1} step={1} style={{ width: 90 }} value={to.hours}
                      onChange={(v) => onPatch({ timeout: { ...to, hours: Number(v) || 1 } })} />
                    <Text style={{ fontSize: 12 }}>小时后</Text>
                  </div>
                  <Select size="small" style={{ width: '100%' }} value={to.action} options={TIMEOUT_ACTIONS}
                    onChange={(v) => onPatch({ timeout: { ...to, action: v } })} />
                  {to.action === 'auto_transfer' && (
                    <PersonField value={to.transfer_to || undefined}
                      onChange={(v) => onPatch({ timeout: { ...to, transfer_to: (Array.isArray(v) ? v[0] : v) as string } })} />
                  )}
                </>
              )}
              <Divider style={{ margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>审批意见必填</Text>
                <Switch size="small" checked={!!node.opinion_required}
                  onChange={(on) => onPatch({ opinion_required: on })} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>本节点可填字段</Text>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 2 }}>
                  审批人在本节点待办里可改这些字段；勾选「必填」则通过时校验。
                  表单里设为「仅审批时填写」的字段也应加到这里。
                </Text>
                <Select
                  mode="multiple"
                  size="small"
                  allowClear
                  style={{ width: '100%', marginTop: 4 }}
                  placeholder="选择审批人可编辑的业务字段"
                  value={(node.field_perms || []).map((p) => p.field)}
                  options={formFields.map((f) => ({
                    value: f.id,
                    label: `${f.label || f.id}${f.available_on_create === false ? '（仅审批）' : ''}`,
                  }))}
                  optionFilterProp="label"
                  showSearch
                  notFoundContent={<span style={{ fontSize: 12 }}>{permFieldEmptyHint}</span>}
                  onChange={(ids: string[]) => {
                    const prev = new Map((node.field_perms || []).map((p) => [p.field, p.access]))
                    const next: WfFieldPerm[] = ids.map((id) => ({
                      field: id,
                      access: prev.get(id) || 'editable',
                    }))
                    onPatch({ field_perms: next.length ? next : undefined })
                  }}
                />
              </div>
              {(node.field_perms || []).length > 0 && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>必填字段</Text>
                  <Checkbox.Group
                    style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}
                    value={(node.field_perms || []).filter((p) => p.access === 'required').map((p) => p.field)}
                    options={(node.field_perms || []).map((p) => ({
                      value: p.field,
                      label: formFields.find((f) => f.id === p.field)?.label || p.field,
                    }))}
                    onChange={(reqIds) => {
                      const req = new Set(reqIds as string[])
                      onPatch({
                        field_perms: (node.field_perms || []).map((p) => ({
                          ...p,
                          access: req.has(p.field) ? 'required' : 'editable',
                        })),
                      })
                    }}
                  />
                </div>
              )}
            </>
          )}
        </>
      )}
      {node.type !== 'start' && node.type !== 'end' && (
        <><Divider style={{ margin: '8px 0' }} /><Button size="small" danger block onClick={onDelete}>删除节点</Button></>
      )}
    </Space>
  )
}

function EdgeConfig({ route, formFields, sourceExclusive, onCond, onExclusive, onAlways, onActivateOrder, onDelete }: {
  route: WfRoute
  formFields: FieldDefinition[]
  sourceExclusive: boolean
  onCond: (c: WfRoute['condition']) => void
  onExclusive: (on: boolean) => void
  onAlways: (on: boolean) => void
  onActivateOrder: (n: number | null) => void
  onDelete: () => void
}) {
  const fieldOpts = formFields
    .filter((f) => f.type !== 'detail_table')
    .map((f) => fieldOption({ value: f.id, label: f.label, type: f.type }))
  const defaultField = formFields.find((f) => f.type !== 'detail_table')?.id || ''
  const hasCond = !!route.condition
  const rel = route.condition?.rel || 'and'
  const conds: CondLeaf[] = (() => {
    const c = route.condition
    if (!c) return []
    if (Array.isArray(c.cond) && c.cond.length) {
      return c.cond.map((n) => ({
        field: n.field || defaultField,
        operator: n.operator || 'eq',
        value: n.value,
      }))
    }
    const single = c as { field?: string; operator?: string; value?: unknown }
    if (single.field && single.operator) {
      return [{ field: single.field, operator: single.operator, value: single.value }]
    }
    return [{ field: defaultField, operator: 'eq', value: '' }]
  })()
  const setConds = (next: CondLeaf[], nextRel: 'and' | 'or' = rel) => {
    onCond({ rel: nextRel, cond: next })
  }
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.6 }}>
        选路（谁亮）：条件 / 互斥组 / always 旁路。未互斥时多条命中都会创建，不是只走一条。
        <br />
        激活序（先走谁）：连线上填数字，越小越先。画布连线可以乱序，引擎仍按 1→2→3→4→5 激活。
        <br />
        相位硬规则：主链审批 → 抄送 → 结束。抄送就算填了激活序 1，也不能排到审批前面。
      </Text>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={{ fontSize: 12 }}>激活序 activate_order</Text>
        <InputNumber
          size="small"
          min={1}
          max={99}
          style={{ width: 88 }}
          placeholder="默认"
          value={typeof route.activate_order === 'number' ? route.activate_order : null}
          onChange={(v) => onActivateOrder(typeof v === 'number' ? v : null)}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={{ fontSize: 12 }}>同源出边互斥 (if/else)</Text>
        <Switch size="small" checked={sourceExclusive && !route.always}
          disabled={!!route.always}
          onChange={onExclusive} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={{ fontSize: 12 }}>旁路抄送 (always)</Text>
        <Switch size="small" checked={!!route.always} onChange={onAlways} />
      </div>
      {route.always && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          旁路不占用主链互斥名额；若设置条件，仅条件成立时才抄送
        </Text>
      )}
      {!route.always && sourceExclusive && !hasCond && (
        <Text type="secondary" style={{ fontSize: 12 }}>当前为 else 分支（无条件，互斥组内兜底）</Text>
      )}
      <Select size="small" style={{ width: '100%' }} value={hasCond ? 'cond' : 'none'}
        options={[
          { label: route.always ? '无条件（始终旁路）' : (sourceExclusive ? 'else（无条件）' : '默认(无条件)'), value: 'none' },
          { label: route.always ? '设置旁路条件' : '设置条件', value: 'cond' },
        ]}
        onChange={(v) => onCond(v === 'none' ? null : { rel: 'and', cond: [{ field: defaultField, operator: 'eq', value: '' }] })} />
      {hasCond && (
        <>
          <Space size={6} wrap>
            <Text style={{ fontSize: 12 }}>满足</Text>
            <Select size="small" style={{ width: 72 }} value={rel}
              options={[{ label: '全部', value: 'and' }, { label: '任一', value: 'or' }]}
              onChange={(v) => setConds(conds, v)} />
            <Text style={{ fontSize: 12 }}>条件</Text>
          </Space>
          {conds.map((c, ci) => {
            const noVal = c.operator === 'is_empty' || c.operator === 'is_not_empty'
            const fd = formFields.find((f) => f.id === c.field)
            return (
              <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: 8, background: '#fafafa', borderRadius: 6 }}>
                <Select size="small" style={{ width: '100%' }} placeholder="字段" value={c.field || undefined}
                  options={fieldOpts}
                  onChange={(v) => setConds(conds.map((x, k) => (k === ci ? { ...x, field: v, value: undefined } : x)))} />
                <Select size="small" style={{ width: '100%' }} value={c.operator || 'eq'} options={OPERATORS}
                  onChange={(v) => setConds(conds.map((x, k) => (k === ci ? { ...x, operator: v } : x)))} />
                {!noVal && (
                  <CondValueInput
                    field={fd}
                    operator={c.operator || 'eq'}
                    value={c.value}
                    onChange={(nv) => setConds(conds.map((x, k) => (k === ci ? { ...x, value: nv } : x)))}
                  />
                )}
                <Button size="small" type="text" danger icon={<DeleteOutlined />} disabled={conds.length <= 1}
                  onClick={() => setConds(conds.filter((_, k) => k !== ci))} style={{ alignSelf: 'flex-end' }}>
                  删除此条
                </Button>
              </div>
            )
          })}
          <Button size="small" type="dashed" block icon={<PlusOutlined />}
            onClick={() => setConds([...conds, { field: defaultField, operator: 'eq', value: '' }])}>
            加条件
          </Button>
        </>
      )}
      <Divider style={{ margin: '8px 0' }} />
      <Button size="small" danger block onClick={onDelete}>删除连线</Button>
    </Space>
  )
}

export default function WorkflowCanvasPage() {
  return <ReactFlowProvider><DesignerInner /></ReactFlowProvider>
}
