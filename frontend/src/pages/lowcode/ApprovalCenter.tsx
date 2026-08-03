// 扩展平台 → 流程审批（桌面已重定向到主审批中心；本页保留兼容移动/深链）
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Tabs, Button, Space, Tag, Input, message, Typography, Popconfirm, Modal, DatePicker,
} from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import dayjs from 'dayjs'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfAgent } from '@/api/lowcodeWorkflow'
import type { WfTodoItem } from '@/types/lowcode'
import PersonField from '@/components/lowcode/fields/PersonField'
import { bizEntityPath, useWfProcessDrawer } from '@/components/lowcode/WfProcessDrawer'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

const { Title, Text } = Typography

function fmtTime(v?: string | null) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).replace(/\//g, '-')
}

export default function ApprovalCenter() {
  const [tab, setTab] = useState('todo')
  const location = useLocation()
  const navState = (location.state || {}) as { openInstanceId?: string; openTaskId?: string }
  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 16 }} className="shrink-0">流程审批</Title>
      <Tabs activeKey={tab} onChange={setTab} className="px-4 pt-2 pb-4" items={[
        { key: 'todo', label: '我的待办', children: <TodoTab active={tab === 'todo'} autoOpen={navState} /> },
        { key: 'mine', label: '我发起的', children: <MineTab active={tab === 'mine'} /> },
        { key: 'done', label: '已办', children: <DoneTab active={tab === 'done'} /> },
        { key: 'agents', label: '我的代理', children: <AgentTab active={tab === 'agents'} /> },
      ]} />
    </div>
  )
}

function TodoTab({ active, autoOpen }: {
  active: boolean
  autoOpen?: { openInstanceId?: string; openTaskId?: string }
}) {
  const navigate = useNavigate()
  const location = useLocation()
  const [items, setItems] = useState<WfTodoItem[]>([])
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.todo({ pageNo: 1, pageSize: 50 }); setItems(r.data.items) } finally { setLoading(false) }
  }, [])
  const { openWith, node } = useWfProcessDrawer(load)
  useEffect(() => { if (active) load() }, [active, load])
  useEffect(() => {
    if (!active || !autoOpen?.openInstanceId) return
    openWith(autoOpen.openInstanceId, autoOpen.openTaskId || null)
    navigate(location.pathname, { replace: true, state: {} })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, autoOpen?.openInstanceId, autoOpen?.openTaskId])
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '节点', dataIndex: 'node_name', width: 120, render: (v: string) => v || '—' },
    { title: '来源', key: 'src', width: 130, render: (_: unknown, r: WfTodoItem) => (r.on_behalf_of ? <Tag color="purple">代 {r.delegator_name || '委托人'} 审批</Tag> : <Tag>指派给我</Tag>) },
    { title: '发起时间', dataIndex: 'created_at', render: (v: string) => fmtTime(v) },
    { title: '操作', key: 'op', width: 160, render: (_: unknown, r: WfTodoItem) => {
      const path = bizEntityPath(r.biz_type, r.biz_id, r.biz_ref_id)
      return (
        <Space size={4}>
          <Button size="small" type="primary" onClick={() => openWith(r.process_instance_id, r.task_id)}>处理</Button>
          {path && <Button size="small" type="link" onClick={() => navigate(path)}>单据</Button>}
        </Space>
      )
    } },
  ]
  return (<>
    <FillHeightTable rowKey="task_id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} scroll={{ x: 'max-content' }} />
    {node}
  </>)
}

function DoneTab({ active }: { active: boolean }) {
  const [items, setItems] = useState<WfTodoItem[]>([])
  const [loading, setLoading] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await workflowApi.done({ pageNo: 1, pageSize: 50 }); setItems(r.data.items) } finally { setLoading(false) }
  }, [])
  const { openWith, node } = useWfProcessDrawer(load)
  useEffect(() => { if (active) load() }, [active, load])
  const cols = [
    { title: '标题', dataIndex: 'title', render: (v: string) => v || '—' },
    { title: '我的处理', dataIndex: 'status', render: (s: string) => <Tag color={s === 'approved' ? 'green' : s === 'rejected' ? 'red' : s === 'returned' ? 'orange' : 'default'}>{s === 'approved' ? '已通过' : s === 'rejected' ? '已驳回' : s === 'returned' ? '已退回' : s}</Tag> },
    { title: '处理时间', dataIndex: 'action_at', render: (v: string) => fmtTime(v) },
    { title: '操作', key: 'op', width: 90, render: (_: unknown, r: WfTodoItem) => <Button size="small" onClick={() => openWith(r.process_instance_id)}>查看</Button> },
  ]
  return (<>
    <FillHeightTable rowKey="task_id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} scroll={{ x: 'max-content' }} />
    {node}
  </>)
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
      <div style={{ marginBottom: 12 }} className="shrink-0">
        <Text type="secondary">设置在某时间段由他人代你审批；代理人会在其「我的待办」看到你的待办并可代为处理。</Text>
        <Button type="primary" size="small" style={{ marginLeft: 12 }} onClick={() => setOpen(true)}>新增代理</Button>
      </div>
      <FillHeightTable rowKey="id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} scroll={{ x: 'max-content' }} />
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
  const { openWith, node } = useWfProcessDrawer(load)
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
    { title: '发起时间', dataIndex: 'created_at', render: (v: string) => fmtTime(v) },
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
  return (<>
    <FillHeightTable rowKey="id" size="small" loading={loading} columns={cols} dataSource={items} pagination={false} scroll={{ x: 'max-content' }} />
    {node}
  </>)
}
