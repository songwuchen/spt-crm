// 扩展平台 → 审批中心: 我的待办 / 我发起的 / 已办 + 处理(通过/驳回/转交/评论) + 流程轨迹。
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tabs, Table, Button, Space, Tag, Drawer, Input, message, Timeline, Typography, Popconfirm, Divider,
  Modal, DatePicker, Select,
} from 'antd'
import dayjs from 'dayjs'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfAgent } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfTodoItem, WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import PersonField from '@/components/lowcode/fields/PersonField'
import { WF_ACTION_TEXT as ACTION_TXT, WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

const { Title, Text } = Typography

export default function ApprovalCenter() {
  const [tab, setTab] = useState('todo')
  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>审批中心</Title>
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'todo', label: '我的待办', children: <TodoTab active={tab === 'todo'} /> },
        { key: 'mine', label: '我发起的', children: <MineTab active={tab === 'mine'} /> },
        { key: 'done', label: '已办', children: <DoneTab active={tab === 'done'} /> },
        { key: 'agents', label: '我的代理', children: <AgentTab active={tab === 'agents'} /> },
      ]} />
    </Card>
  )
}

// ---- 处理/查看流程详情抽屉 ----
function ProcessDrawer({ open, taskId, instanceId, onClose, onDone }: {
  open: boolean; taskId?: string | null; instanceId?: string | null; onClose: () => void; onDone: () => void
}) {
  const [detail, setDetail] = useState<WfInstanceDetail | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [opinion, setOpinion] = useState('')
  const [transferTo, setTransferTo] = useState<unknown>(undefined)
  const [returnTo, setReturnTo] = useState<string | undefined>(undefined)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !instanceId) return
    setOpinion(''); setTransferTo(undefined); setReturnTo(undefined)
    ;(async () => {
      const d = await workflowApi.instance(instanceId)
      setDetail(d.data)
      if (d.data.form_instance_id) {
        const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
        setFields(fi.data.field_definitions); setFormData(fi.data.form_data)
      } else { setFields([]); setFormData({}) }
    })()
  }, [open, instanceId])

  const act = async (action: string) => {
    if (!taskId) return
    if (action === 'transfer' && !transferTo) return message.error('请选择转交接收人')
    if (action === 'return' && !returnTo) return message.error('请选择退回的目标节点')
    setBusy(true)
    try {
      await workflowApi.act(taskId, {
        action, opinion,
        transfer_to: action === 'transfer' ? (Array.isArray(transferTo) ? transferTo[0] : transferTo) as string : undefined,
        to_node_id: action === 'return' ? returnTo : undefined,
      })
      message.success('已处理'); onDone(); onClose()
    } finally { setBusy(false) }
  }

  return (
    <Drawer title="流程详情" width={640} open={open} onClose={onClose}>
      {detail && (
        <>
          <Space><b>{detail.title || '(无标题)'}</b>{PSTATUS[detail.status] && <Tag color={PSTATUS[detail.status].color}>{PSTATUS[detail.status].text}</Tag>}</Space>
          <Divider style={{ margin: '12px 0' }}>表单内容</Divider>
          {fields.length ? <FormRenderer fields={fields} mode="readonly" value={formData} applyFieldPerms={false} /> : <Text type="secondary">无关联表单</Text>}
          <Divider style={{ margin: '12px 0' }}>流程轨迹</Divider>
          <Timeline items={(detail.timeline || []).map((t) => ({
            children: <div><b>{ACTION_TXT[t.action] || t.action}</b> · {t.actor_name || t.actor_id}
              {t.opinion ? <div style={{ color: '#888' }}>意见: {t.opinion}</div> : null}
              <div style={{ fontSize: 12, color: '#aaa' }}>{t.at?.slice(0, 19).replace('T', ' ')}</div></div>,
          }))} />
          {taskId && (
            <>
              <Divider style={{ margin: '12px 0' }}>审批操作</Divider>
              <Input.TextArea rows={2} placeholder="审批意见(可选)" value={opinion} onChange={(e) => setOpinion(e.target.value)} style={{ marginBottom: 8 }} />
              <Space wrap>
                <Button type="primary" loading={busy} onClick={() => act('approve')}>通过</Button>
                <Button danger loading={busy} onClick={() => act('reject')}>驳回</Button>
                <Button loading={busy} onClick={() => act('comment')}>评论</Button>
              </Space>
              <div style={{ marginTop: 8 }}>
                <Space>
                  <div style={{ width: 220 }}><PersonField value={transferTo} onChange={setTransferTo} /></div>
                  <Button loading={busy} onClick={() => act('transfer')}>转交</Button>
                </Space>
              </div>
              {(detail.approval_nodes?.length ?? 0) > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Space>
                    <Select style={{ width: 220 }} placeholder="退回到审批节点" value={returnTo} onChange={setReturnTo}
                      options={(detail.approval_nodes || []).map((n) => ({ label: n.name, value: n.id }))} />
                    <Button loading={busy} onClick={() => act('return')}>退回</Button>
                  </Space>
                </div>
              )}
            </>
          )}
        </>
      )}
    </Drawer>
  )
}

function useDrawer(reload: () => void) {
  const [open, setOpen] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [instanceId, setInstanceId] = useState<string | null>(null)
  const openWith = (iid: string, tid?: string | null) => { setInstanceId(iid); setTaskId(tid || null); setOpen(true) }
  const node = <ProcessDrawer open={open} taskId={taskId} instanceId={instanceId} onClose={() => setOpen(false)} onDone={reload} />
  return { openWith, node }
}

function TodoTab({ active }: { active: boolean }) {
  const [items, setItems] = useState<WfTodoItem[]>([])
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.todo({ pageNo: 1, pageSize: 50 }); setItems(r.data.items) } finally { setLoading(false) }
  }, [])
  const { openWith, node } = useDrawer(load)
  useEffect(() => { if (active) load() }, [active, load])
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '单号', dataIndex: 'business_no', render: (v: string) => v || '—' },
    { title: '来源', key: 'src', width: 130, render: (_: unknown, r: WfTodoItem) => (r.on_behalf_of ? <Tag color="purple">代 {r.delegator_name || '委托人'} 审批</Tag> : <Tag>本人</Tag>) },
    { title: '发起时间', dataIndex: 'created_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    { title: '操作', key: 'op', width: 100, render: (_: unknown, r: WfTodoItem) => <Button size="small" type="primary" onClick={() => openWith(r.process_instance_id, r.task_id)}>处理</Button> },
  ]
  return <><Table rowKey="task_id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />{node}</>
}

function DoneTab({ active }: { active: boolean }) {
  const [items, setItems] = useState<WfTodoItem[]>([])
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.done({ pageNo: 1, pageSize: 50 }); setItems(r.data.items) } finally { setLoading(false) }
  }, [])
  const { openWith, node } = useDrawer(load)
  useEffect(() => { if (active) load() }, [active, load])
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '我的处理', dataIndex: 'status', render: (s: string) => <Tag color={s === 'approved' ? 'green' : s === 'rejected' ? 'red' : s === 'returned' ? 'orange' : 'default'}>{s === 'approved' ? '已通过' : s === 'rejected' ? '已驳回' : s === 'returned' ? '已退回' : s}</Tag> },
    { title: '处理时间', dataIndex: 'action_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    { title: '操作', key: 'op', width: 90, render: (_: unknown, r: WfTodoItem) => <Button size="small" onClick={() => openWith(r.process_instance_id)}>查看</Button> },
  ]
  return <><Table rowKey="task_id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />{node}</>
}

function AgentTab({ active }: { active: boolean }) {
  const [items, setItems] = useState<WfAgent[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [agentId, setAgentId] = useState<unknown>(undefined)
  const [range, setRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.listAgents(); setItems(r.data || []) } finally { setLoading(false) }
  }, [])
  useEffect(() => { if (active) load() }, [active, load])

  const save = async () => {
    if (!agentId) { message.error('请选择代理人'); return }
    if (!range || !range[0] || !range[1]) { message.error('请选择代理时间段'); return }
    setSaving(true)
    try {
      await workflowApi.createAgent({
        agent_id: String(agentId), start_time: range[0].toISOString(), end_time: range[1].toISOString(),
        note: note || undefined,
      })
      message.success('已设置代理')
      setOpen(false); setAgentId(undefined); setRange(null); setNote('')
      load()
    } catch { message.error('设置失败') } finally { setSaving(false) }
  }

  const cols = [
    { title: '代理人', dataIndex: 'agent_name', render: (v: string, r: WfAgent) => v || r.agent_id },
    { title: '开始', dataIndex: 'start_time', render: (v: string) => (v ? v.slice(0, 16).replace('T', ' ') : '—') },
    { title: '结束', dataIndex: 'end_time', render: (v: string) => (v ? v.slice(0, 16).replace('T', ' ') : '—') },
    { title: '状态', key: 'st', width: 90, render: (_: unknown, r: WfAgent) => (r.active_now ? <Tag color="green">生效中</Tag> : <Tag>未生效</Tag>) },
    { title: '备注', dataIndex: 'note', render: (v: string) => v || '—' },
    { title: '操作', key: 'op', width: 80, render: (_: unknown, r: WfAgent) => (
      <Popconfirm title="撤销该代理?" onConfirm={async () => { await workflowApi.deleteAgent(r.id); message.success('已撤销'); load() }}>
        <Button size="small" type="link" danger>撤销</Button>
      </Popconfirm>
    ) },
  ]
  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">设置在某时间段由他人代你审批；代理人会在其「我的待办」看到你的待办并可代为处理。</Text>
        <Button type="primary" size="small" style={{ marginLeft: 12 }} onClick={() => setOpen(true)}>新增代理</Button>
      </div>
      <Table rowKey="id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />
      <Modal title="新增代理" open={open} onOk={save} confirmLoading={saving} onCancel={() => setOpen(false)} destroyOnClose>
        <div className="space-y-3">
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>代理人</div>
            <PersonField value={agentId} onChange={setAgentId} placeholder="选择代理人" />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>代理时间段</div>
            <DatePicker.RangePicker showTime style={{ width: '100%' }} value={range as never}
              onChange={(v) => setRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)} />
          </div>
          <div>
            <div style={{ marginBottom: 4, fontSize: 13 }}>备注</div>
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="可选，如：出差期间" />
          </div>
        </div>
      </Modal>
    </>
  )
}

function MineTab({ active }: { active: boolean }) {
  const [items, setItems] = useState<Array<{ id: string; title?: string; status: string; created_at?: string }>>([])
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.mine({ pageNo: 1, pageSize: 50 }); setItems(r.data.items) } finally { setLoading(false) }
  }, [])
  const { openWith, node } = useDrawer(load)
  useEffect(() => { if (active) load() }, [active, load])
  const withdraw = async (id: string) => { await workflowApi.withdraw(id); message.success('已撤回'); load() }
  const urge = async (id: string) => {
    try {
      const r = await workflowApi.urge(id)
      message.success(`已催办 ${r.data?.notified ?? 0} 人`)
    } catch (e) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.warning(msg || '催办失败')
    }
  }
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '状态', dataIndex: 'status', render: (s: string) => { const t = PSTATUS[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> } },
    { title: '发起时间', dataIndex: 'created_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    {
      title: '操作', key: 'op', width: 200, render: (_: unknown, r: { id: string; status: string }) => (
        <Space size="small">
          <Button size="small" onClick={() => openWith(r.id)}>查看</Button>
          {r.status === 'running' && <Button size="small" type="link" onClick={() => urge(r.id)}>催办</Button>}
          {r.status === 'running' && <Popconfirm title="确认撤回?" onConfirm={() => withdraw(r.id)}><Button size="small" type="link" danger>撤回</Button></Popconfirm>}
        </Space>
      ),
    },
  ]
  return <><Table rowKey="id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />{node}</>
}
