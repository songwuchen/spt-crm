// 扩展平台 → 流程可视化设计器(@xyflow 拖拽画布)。节点(开始/审批/抄送/结束)+ 连线(可挂条件分支)。
// 复用后端 save_design/publish;节点位置存 node.position(JSONB),条件存 route.condition。
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, Handle, Position,
  addEdge, useNodesState, useEdgesState, type Node, type Edge, type Connection, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import {
  Card, Button, Space, Input, InputNumber, Select, Switch, Typography, Tag, message, Empty, Divider,
} from 'antd'
import {
  ArrowLeftOutlined, PlusOutlined, AuditOutlined, SendOutlined, PlayCircleOutlined, StopOutlined,
} from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfNode, WfRoute, WfDesign, ApproverType, FieldDefinition } from '@/types/lowcode'
import PersonField from '@/components/lowcode/fields/PersonField'
import { fieldOption } from '@/components/lowcode/fieldTypeIcon'

const { Title, Text } = Typography

const APPROVER_TYPES: { value: ApproverType; label: string; needValue?: 'user' | 'field_person' | 'field_dept' | 'text' }[] = [
  { value: 'specified_user', label: '指定人员', needValue: 'user' },
  { value: 'creator', label: '发起人本人' },
  { value: 'direct_supervisor', label: '直接上级' },
  { value: 'dept_head', label: '部门负责人' },
  { value: 'multi_level_superior', label: '逐级上级' },
  { value: 'form_field_person', label: '表单人员字段', needValue: 'field_person' },
  { value: 'form_field_dept', label: '表单部门字段', needValue: 'field_dept' },
  { value: 'specified_role', label: '指定角色(角色码)', needValue: 'text' },
]
const MULTI_MODES = [
  { value: 'or_sign', label: '或签(一人通过即可)' },
  { value: 'countersign', label: '会签(全部通过)' },
  { value: 'sequential', label: '顺序会签' },
]
const OPERATORS = [
  { value: 'gt', label: '大于' }, { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' }, { value: 'lte', label: '小于等于' },
  { value: 'eq', label: '等于' }, { value: 'ne', label: '不等于' },
  { value: 'contains', label: '包含' },
]
const genId = (p: string) => p + Math.random().toString(36).slice(2, 7)

const NODE_META: Record<string, { color: string; label: string }> = {
  start: { color: '#12b876', label: '开始' }, approval: { color: '#2f6bff', label: '审批' },
  cc: { color: '#12b876', label: '抄送' }, end: { color: '#8c8c8c', label: '结束' },
  parallel: { color: '#fa8c16', label: '并行' }, merge: { color: '#fa8c16', label: '汇聚' },
}
const TIMEOUT_ACTIONS = [
  { value: 'notify', label: '仅提醒' },
  { value: 'auto_approve', label: '自动通过' },
  { value: 'auto_reject', label: '自动驳回' },
  { value: 'auto_transfer', label: '自动转交' },
]

// ---- 自定义节点 ----
function WfNodeComp({ data, selected }: NodeProps) {
  const d = data as { node: WfNode }
  const meta = NODE_META[d.node.type] || NODE_META.approval
  return (
    <div style={{
      minWidth: 150, padding: '8px 14px', borderRadius: 22, background: '#fff',
      border: `2px solid ${selected ? meta.color : '#e5e7eb'}`, boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: meta.color }} />
      <span style={{ fontWeight: 500 }}>{d.node.name}</span>
      <Handle type="target" position={Position.Top} style={{ background: '#9aa2af' }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#9aa2af' }} />
    </div>
  )
}
const nodeTypes = { wf: WfNodeComp }

function autoLayout(nodes: WfNode[], routes: WfRoute[]): Record<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', ranksep: 70, nodesep: 50 })
  g.setDefaultEdgeLabel(() => ({}))
  nodes.forEach((n) => g.setNode(n.id, { width: 160, height: 44 }))
  routes.forEach((r) => g.setEdge(r.source, r.target))
  dagre.layout(g)
  const pos: Record<string, { x: number; y: number }> = {}
  nodes.forEach((n) => { const gn = g.node(n.id); if (gn) pos[n.id] = { x: gn.x - 80, y: gn.y - 22 } })
  return pos
}

function DesignerInner() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [name, setName] = useState('')
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
        if (def.data.form_template_id) {
          try { const v = await lowcodeApi.publishedVersion(def.data.form_template_id); setFormFields((v.data.field_definitions as FieldDefinition[]) || []) } catch { /* 未发布 */ }
        } else if (def.data.biz_type) {
          // 绑定业务类型的审批流没有表单：用业务字段目录填充条件分支/字段选择
          try { const r = await workflowApi.bizFields(def.data.biz_type); setFormFields((r.data as unknown as FieldDefinition[]) || []) } catch { /* 无目录 */ }
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
        setNodes(nodes.map((n) => ({ id: n.id, type: 'wf', position: n.position || pos[n.id] || { x: 100, y: 100 }, data: { node: n } })))
        setEdges(routes.map((r) => ({ id: r.id, source: r.source, target: r.target, label: r.condition ? '条件' : undefined, data: { route: r }, animated: !!r.condition })))
      } finally { setLoading(false) }
    })()
  }, [id])  // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = useCallback((c: Connection) => {
    const rid = genId('r')
    setEdges((eds) => addEdge({ ...c, id: rid, data: { route: { id: rid, source: c.source!, target: c.target! } } }, eds))
  }, [setEdges])

  const addNode = (type: 'approval' | 'cc' | 'parallel' | 'merge') => {
    const prefix = { approval: 'ap', cc: 'cc', parallel: 'par', merge: 'mrg' }[type]
    const nid = genId(prefix)
    const names = { approval: '审批', cc: '抄送', parallel: '并行网关', merge: '汇聚节点' }
    const node: WfNode = {
      id: nid, type, name: names[type],
      ...(type === 'approval' ? { approver_rule: { type: 'direct_supervisor' }, multi_mode: 'or_sign' as const } : {}),
      ...(type === 'cc' ? { approver_rule: { type: 'specified_user' } } : {}),
    }
    setNodes((nds) => [...nds, { id: nid, type: 'wf', position: { x: 120 + Math.random() * 80, y: 160 + nds.length * 40 }, data: { node } }])
  }

  const patchNode = (nid: string, patch: Partial<WfNode>) => {
    setNodes((nds) => nds.map((n) => n.id === nid ? { ...n, data: { node: { ...(n.data as { node: WfNode }).node, ...patch } } } : n))
  }
  const patchRule = (nid: string, patch: Record<string, unknown>) => {
    setNodes((nds) => nds.map((n) => {
      if (n.id !== nid) return n
      const node = (n.data as { node: WfNode }).node
      return { ...n, data: { node: { ...node, approver_rule: { ...(node.approver_rule || { type: 'creator' }), ...patch } } } }
    }))
  }
  const patchEdgeCond = (eid: string, cond: WfRoute['condition']) => {
    setEdges((eds) => eds.map((e) => e.id === eid
      ? { ...e, label: cond ? '条件' : undefined, animated: !!cond, data: { route: { ...(e.data as { route: WfRoute }).route, condition: cond } } }
      : e))
  }
  const delSelected = () => {
    if (selNode && !['start', 'end'].includes(selNode)) { setNodes((n) => n.filter((x) => x.id !== selNode)); setEdges((e) => e.filter((x) => x.source !== selNode && x.target !== selNode)); setSelNode(null) }
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

  if (loading) return <Card loading />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/workflows')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>可视化流程 · {name}</Title>
        </Space>
        <Space>
          <Button icon={<PlusOutlined />} onClick={() => addNode('approval')}>审批节点</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('cc')}>抄送节点</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('parallel')}>并行网关</Button>
          <Button icon={<PlusOutlined />} onClick={() => addNode('merge')}>汇聚节点</Button>
          <Button onClick={() => save(false)}>保存草稿</Button>
          <Button type="primary" onClick={() => save(true)}>保存并发布</Button>
        </Space>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <div style={{ flex: 1, height: 560, border: '1px solid #f0f0f0', borderRadius: 8, background: '#fafafa' }}>
          <ReactFlow
            nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onNodeClick={(_, n) => { setSelNode(n.id); setSelEdge(null) }}
            onEdgeClick={(_, e) => { setSelEdge(e.id); setSelNode(null) }}
            onPaneClick={() => { setSelNode(null); setSelEdge(null) }}
            fitView proOptions={{ hideAttribution: true }}
          >
            <Background />
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
            <EdgeConfig route={(selectedEdge.data as { route: WfRoute }).route} formFields={formFields}
              onCond={(c) => patchEdgeCond(selectedEdge.id, c)} onDelete={delSelected} />
          ) : (
            <Empty description="点节点或连线编辑;拖动锚点连线" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      </div>
    </div>
  )
}

function NodeConfig({ node, formFields, onName, onRule, onMode, onPatch, onDelete }: {
  node: WfNode; formFields: FieldDefinition[]
  onName: (v: string) => void; onRule: (p: Record<string, unknown>) => void; onMode: (v: WfNode['multi_mode']) => void
  onPatch: (p: Partial<WfNode>) => void; onDelete: () => void
}) {
  const isEditable = node.type === 'approval' || node.type === 'cc'
  const meta = APPROVER_TYPES.find((a) => a.value === node.approver_rule?.type)
  const personFields = formFields.filter((f) => f.type === 'person' || f.type === 'person_multi')
  const deptFields = formFields.filter((f) => f.type === 'department' || f.type === 'department_multi')
  const to = node.timeout
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
          <div><Text type="secondary" style={{ fontSize: 12 }}>{node.type === 'approval' ? '审批人' : '抄送人'}</Text>
            <Select size="small" style={{ width: '100%' }} value={node.approver_rule?.type}
              options={APPROVER_TYPES.map((t) => ({ label: t.label, value: t.value }))}
              onChange={(v) => onRule({ type: v, value: undefined })} /></div>
          {meta?.needValue === 'user' && <PersonField value={node.approver_rule?.value} onChange={(v) => onRule({ value: v })} multi />}
          {(meta?.needValue === 'field_person' || meta?.needValue === 'field_dept') && (
            <Select size="small" style={{ width: '100%' }} placeholder="选择表单字段"
              value={(node.approver_rule?.value as string) || undefined}
              options={(meta.needValue === 'field_person' ? personFields : deptFields).map((f) => fieldOption({ value: f.id, label: f.label, type: f.type }))}
              onChange={(v) => onRule({ value: v })} />
          )}
          {meta?.needValue === 'text' && (
            <Input size="small" placeholder="角色码,逗号分隔"
              value={Array.isArray(node.approver_rule?.value) ? (node.approver_rule?.value as string[]).join(',') : ''}
              onChange={(e) => onRule({ value: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
          )}
          {node.type === 'approval' && (
            <>
              <div><Text type="secondary" style={{ fontSize: 12 }}>多人模式</Text>
                <Select size="small" style={{ width: '100%' }} value={node.multi_mode || 'or_sign'} options={MULTI_MODES} onChange={onMode} /></div>
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

function EdgeConfig({ route, formFields, onCond, onDelete }: {
  route: WfRoute; formFields: FieldDefinition[]; onCond: (c: WfRoute['condition']) => void; onDelete: () => void
}) {
  const c = route.condition?.cond?.[0] as { field?: string; operator?: string; value?: unknown } | undefined
  const hasCond = !!route.condition
  const setLeaf = (patch: Record<string, unknown>) => {
    const leaf = { field: c?.field || '', operator: c?.operator || 'gt', value: c?.value, ...patch }
    onCond({ rel: 'and', cond: [leaf] })
  }
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <Text type="secondary" style={{ fontSize: 12 }}>连线条件(满足才走此分支;无条件=默认分支)</Text>
      <Select size="small" style={{ width: '100%' }} value={hasCond ? 'cond' : 'none'}
        options={[{ label: '默认(无条件)', value: 'none' }, { label: '设置条件', value: 'cond' }]}
        onChange={(v) => onCond(v === 'none' ? null : { rel: 'and', cond: [{ field: formFields[0]?.id || '', operator: 'gt', value: '' }] })} />
      {hasCond && (
        <>
          <Select size="small" style={{ width: '100%' }} placeholder="字段" value={c?.field}
            options={formFields.filter((f) => f.type !== 'detail_table').map((f) => fieldOption({ value: f.id, label: f.label, type: f.type }))}
            onChange={(v) => setLeaf({ field: v })} />
          <Select size="small" style={{ width: '100%' }} value={c?.operator || 'gt'} options={OPERATORS} onChange={(v) => setLeaf({ operator: v })} />
          <Input size="small" placeholder="值" value={(c?.value as string) ?? ''} onChange={(e) => setLeaf({ value: e.target.value })} />
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
