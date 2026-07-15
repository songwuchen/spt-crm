// 扩展平台 → 审批中心: 我的待办 / 我发起的 / 已办 + 处理(通过/驳回/转交/评论) + 流程轨迹。
import { useEffect, useState, useCallback } from 'react'
import {
  Card, Tabs, Table, Button, Space, Tag, Drawer, Input, message, Timeline, Typography, Popconfirm, Divider,
} from 'antd'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfTodoItem, WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import PersonField from '@/components/lowcode/fields/PersonField'

const { Title, Text } = Typography

const PSTATUS: Record<string, { color: string; text: string }> = {
  running: { color: 'gold', text: '审批中' }, completed: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已驳回' }, withdrawn: { color: 'default', text: '已撤回' },
}
const ACTION_TXT: Record<string, string> = {
  submit: '发起', approve: '通过', reject: '驳回', transfer: '转交', comment: '评论',
  withdraw: '撤回', auto_approve: '自动通过', auto_reject: '自动终止',
}

export default function ApprovalCenter() {
  const [tab, setTab] = useState('todo')
  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>审批中心</Title>
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'todo', label: '我的待办', children: <TodoTab active={tab === 'todo'} /> },
        { key: 'mine', label: '我发起的', children: <MineTab active={tab === 'mine'} /> },
        { key: 'done', label: '已办', children: <DoneTab active={tab === 'done'} /> },
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
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !instanceId) return
    setOpinion(''); setTransferTo(undefined)
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
    setBusy(true)
    try {
      await workflowApi.act(taskId, {
        action, opinion,
        transfer_to: action === 'transfer' ? (Array.isArray(transferTo) ? transferTo[0] : transferTo) as string : undefined,
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
    { title: '我的处理', dataIndex: 'status', render: (s: string) => <Tag color={s === 'approved' ? 'green' : s === 'rejected' ? 'red' : 'default'}>{s === 'approved' ? '已通过' : s === 'rejected' ? '已驳回' : s}</Tag> },
    { title: '处理时间', dataIndex: 'action_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    { title: '操作', key: 'op', width: 90, render: (_: unknown, r: WfTodoItem) => <Button size="small" onClick={() => openWith(r.process_instance_id)}>查看</Button> },
  ]
  return <><Table rowKey="task_id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />{node}</>
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
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '状态', dataIndex: 'status', render: (s: string) => { const t = PSTATUS[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> } },
    { title: '发起时间', dataIndex: 'created_at', render: (v: string) => (v ? v.slice(0, 19).replace('T', ' ') : '—') },
    {
      title: '操作', key: 'op', width: 160, render: (_: unknown, r: { id: string; status: string }) => (
        <Space size="small">
          <Button size="small" onClick={() => openWith(r.id)}>查看</Button>
          {r.status === 'running' && <Popconfirm title="确认撤回?" onConfirm={() => withdraw(r.id)}><Button size="small" type="link" danger>撤回</Button></Popconfirm>}
        </Space>
      ),
    },
  ]
  return <><Table rowKey="id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} />{node}</>
}
