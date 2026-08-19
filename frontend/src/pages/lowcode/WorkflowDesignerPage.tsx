// 扩展平台 → 流程设计器(Phase 3 结构化版: 开始→[审批/抄送节点]→结束 线性编排 + 审批人配置 + JSON 高级)。
// 完整 @xyflow 可视化画布(自由分支)为后续切片;此处结构化线性编排 + JSON 支持分支。
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Button, Space, Input, Select, message, Typography, Tag, Drawer, Divider, Empty, Row, Col,
} from 'antd'
import { ArrowLeftOutlined, PlusOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfNode, WfDesign, FieldDefinition } from '@/types/lowcode'
import { ApproverRuleEditor } from '@/components/lowcode/ApproverRuleEditor'
import { defaultCcApproverRule } from '@/utils/wfApproverDefaults'

const { Title, Text } = Typography

const MULTI_MODES = [
  { value: 'or_sign', label: '或签(一人通过即可)' },
  { value: 'countersign', label: '会签(全部通过)' },
  { value: 'sequential', label: '顺序会签(依次)' },
]
const genId = (p: string) => p + Math.random().toString(36).slice(2, 8)

export default function WorkflowDesignerPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [formTemplateId, setFormTemplateId] = useState<string | null>(null)
  const [bizType, setBizType] = useState<string | null>(null)
  const [formFields, setFormFields] = useState<FieldDefinition[]>([])
  const [middle, setMiddle] = useState<WfNode[]>([])
  const [loading, setLoading] = useState(true)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [jsonText, setJsonText] = useState('')

  useEffect(() => {
    (async () => {
      try {
        const def = await workflowApi.getDef(id)
        setName(def.data.name)
        setFormTemplateId(def.data.form_template_id || null)
        setBizType(def.data.biz_type || null)
        if (def.data.form_template_id) {
          try {
            const ver = await lowcodeApi.publishedVersion(def.data.form_template_id)
            setFormFields((ver.data.field_definitions as FieldDefinition[]) || [])
          } catch { /* 表单未发布 */ }
        } else if (def.data.biz_type) {
          try {
            const r = await workflowApi.bizFields(def.data.biz_type)
            const list = Array.isArray(r.data) ? r.data : []
            setFormFields(list.map((f) => ({
              id: f.id,
              label: f.label,
              type: f.type as FieldDefinition['type'],
            })))
          } catch {
            setFormFields([])
          }
        }
        const design = await workflowApi.loadDesign(id)
        const nodes = design.data.node_definitions || []
        setMiddle(nodes.filter((n) => n.type === 'approval' || n.type === 'cc'))
      } finally { setLoading(false) }
    })()
  }, [id])

  const addNode = (type: 'approval' | 'cc') => {
    setMiddle([...middle, {
      id: genId(type === 'approval' ? 'ap' : 'cc'),
      type, name: type === 'approval' ? '审批' : '抄送',
      approver_rule: type === 'approval'
        ? { type: 'direct_supervisor' }
        : defaultCcApproverRule(formFields),
      ...(type === 'approval' ? { multi_mode: 'or_sign' as const } : {}),
    }])
  }
  const patch = (idx: number, p: Partial<WfNode>) => setMiddle(middle.map((n, i) => (i === idx ? { ...n, ...p } : n)))
  const patchRule = (idx: number, rule: NonNullable<WfNode['approver_rule']>) =>
    setMiddle(middle.map((n, i) => (i === idx ? { ...n, approver_rule: rule } : n)))
  const remove = (idx: number) => setMiddle(middle.filter((_, i) => i !== idx))
  const move = (idx: number, dir: -1 | 1) => {
    const j = idx + dir
    if (j < 0 || j >= middle.length) return
    const next = [...middle]; [next[idx], next[j]] = [next[j], next[idx]]; setMiddle(next)
  }

  const buildDesign = (): WfDesign => {
    const start: WfNode = { id: 'start', type: 'start', name: '开始' }
    const end: WfNode = { id: 'end', type: 'end', name: '结束' }
    const seq = [start, ...middle, end]
    const routes = seq.slice(0, -1).map((n, i) => ({ id: `r${i}`, source: n.id, target: seq[i + 1].id }))
    return { node_definitions: seq, route_definitions: routes, approver_rules: [] }
  }

  const save = async (publish = false) => {
    for (const n of middle) {
      if (!n.name?.trim()) return message.error('存在未命名节点')
      if (n.type === 'approval' && !n.approver_rule?.type) return message.error(`节点「${n.name}」未配置审批人`)
    }
    await workflowApi.saveDesign(id, buildDesign())
    if (publish) {
      await workflowApi.publish(id); message.success('已发布'); nav('/lowcode/workflows')
    } else { message.success('草稿已保存') }
  }

  const openJson = () => { setJsonText(JSON.stringify(buildDesign(), null, 2)); setJsonOpen(true) }
  const applyJson = async () => {
    try {
      const parsed = JSON.parse(jsonText) as WfDesign
      await workflowApi.saveDesign(id, parsed)
      message.success('已保存 JSON 设计(含分支需在此维护)')
      setJsonOpen(false)
      setMiddle((parsed.node_definitions || []).filter((n) => n.type === 'approval' || n.type === 'cc'))
    } catch (e) { message.error('JSON 解析/保存失败: ' + (e as Error).message) }
  }

  if (loading) return <Card loading />

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/workflows')}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>设计流程 · {name}</Title>
          {formTemplateId ? (
            <Tag color="blue">已绑定表单</Tag>
          ) : bizType ? (
            <Tag color="geekblue">业务类型 · {bizType}</Tag>
          ) : (
            <Tag>未绑定</Tag>
          )}
        </Space>
        <Space>
          <Button onClick={openJson}>高级(JSON/分支)</Button>
          <Button onClick={() => save(false)}>保存草稿</Button>
          <Button type="primary" onClick={() => save(true)}>保存并发布</Button>
        </Space>
      </div>

      <Card size="small" style={{ maxWidth: 720 }}>
        <NodeBadge color="#52c41a" label="开始" />
        {middle.length === 0 && <Empty description="在下方添加审批/抄送节点" style={{ margin: '12px 0' }} />}
        {middle.map((n, idx) => (
          <div key={n.id} style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 12, margin: '8px 0' }}>
            <Row gutter={8} align="middle">
              <Col><Tag color={n.type === 'approval' ? 'processing' : 'default'}>{n.type === 'approval' ? '审批' : '抄送'}</Tag></Col>
              <Col flex="auto"><Input size="small" value={n.name} addonBefore="节点名" onChange={(e) => patch(idx, { name: e.target.value })} /></Col>
              <Col>
                <Space size={2}>
                  <Button size="small" type="text" icon={<ArrowUpOutlined />} onClick={() => move(idx, -1)} />
                  <Button size="small" type="text" icon={<ArrowDownOutlined />} onClick={() => move(idx, 1)} />
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => remove(idx)} />
                </Space>
              </Col>
            </Row>
            <Row gutter={8} align="top" style={{ marginTop: 8 }}>
              <Col span={n.type === 'approval' ? 17 : 24}>
                <ApproverRuleEditor
                  rule={n.approver_rule}
                  formFields={formFields}
                  roleLabel={n.type === 'approval' ? '审批人' : '抄送人'}
                  onChange={(next) => patchRule(idx, next)}
                />
              </Col>
              {n.type === 'approval' && (
                <Col span={7}>
                  <Text type="secondary" style={{ fontSize: 12 }}>多人模式</Text>
                  <Select size="small" style={{ width: '100%' }} value={n.multi_mode || 'or_sign'}
                    options={MULTI_MODES} onChange={(v) => patch(idx, { multi_mode: v })} />
                </Col>
              )}
            </Row>
          </div>
        ))}
        <Space style={{ marginTop: 8 }}>
          <Button size="small" icon={<PlusOutlined />} onClick={() => addNode('approval')}>加审批节点</Button>
          <Button size="small" icon={<PlusOutlined />} onClick={() => addNode('cc')}>加抄送节点</Button>
        </Space>
        <div style={{ marginTop: 12 }}><NodeBadge color="#ff4d4f" label="结束" /></div>
      </Card>

      <Drawer title="高级 · 流程 JSON(节点/连线/条件分支)" width={620} open={jsonOpen} onClose={() => setJsonOpen(false)}
        extra={<Button type="primary" onClick={applyJson}>保存</Button>}>
        <Text type="secondary">可维护条件分支: route 增加 condition {'{rel, cond:[{field,operator,value}]}'}。</Text>
        <Divider style={{ margin: '8px 0' }} />
        <Input.TextArea value={jsonText} onChange={(e) => setJsonText(e.target.value)} style={{ fontFamily: 'monospace', minHeight: 480 }} />
      </Drawer>
    </div>
  )
}

function NodeBadge({ color, label }: { color: string; label: string }) {
  return <span style={{ display: 'inline-block', padding: '2px 12px', borderRadius: 12, background: color, color: '#fff', fontSize: 12 }}>{label}</span>
}
