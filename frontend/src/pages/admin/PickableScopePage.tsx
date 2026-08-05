// 系统管理 → 可选范围：直接勾选人员 / 部门，供表单字段引用。
import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Button, Form, Input, Modal, Select, Space, Switch, Table, Tag, message, Popconfirm,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { pickableScopeApi, type PickableScopeItem, type PickableScopeKind } from '@/api/pickableScope'
import { usePageTitle } from '@/hooks/usePageTitle'
import PersonField from '@/components/lowcode/fields/PersonField'
import DeptField from '@/components/lowcode/fields/DeptField'

const KIND_OPTS = [
  { value: 'person', label: '人员范围' },
  { value: 'department', label: '部门范围' },
]

export default function PickableScopePage() {
  usePageTitle('可选范围')
  const [items, setItems] = useState<PickableScopeItem[]>([])
  const [loading, setLoading] = useState(false)
  const [kindFilter, setKindFilter] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<PickableScopeItem | null>(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await pickableScopeApi.list(kindFilter ? { kind: kindFilter } : undefined)
      setItems(res.data || [])
    } catch (e: any) {
      message.error(e?.response?.data?.message || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [kindFilter])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({
      kind: 'person',
      include_children: true,
      user_ids: [],
      dept_ids: [],
    })
    setModalOpen(true)
  }

  const openEdit = (row: PickableScopeItem) => {
    setEditing(row)
    const rules = row.rules || {}
    form.setFieldsValue({
      code: row.code,
      name: row.name,
      kind: row.kind,
      description: row.description,
      user_ids: rules.user_ids || [],
      dept_ids: rules.dept_ids || [],
      include_children: rules.include_children !== false,
    })
    setModalOpen(true)
  }

  const handleSave = async () => {
    const v = await form.validateFields()
    // 人员范围只存勾选人员；部门范围只存可选部门
    const rules = v.kind === 'person'
      ? {
          role_codes: [],
          user_ids: v.user_ids || [],
          dept_ids: [],
          include_children: true,
        }
      : {
          role_codes: [],
          user_ids: [],
          dept_ids: v.dept_ids || [],
          include_children: v.include_children !== false,
        }
    try {
      if (editing) {
        await pickableScopeApi.update(editing.id, {
          name: v.name,
          description: v.description,
          rules,
        })
        message.success('已保存')
      } else {
        await pickableScopeApi.create({
          code: v.code,
          name: v.name,
          kind: v.kind as PickableScopeKind,
          description: v.description,
          rules,
        })
        message.success('已创建')
      }
      setModalOpen(false)
      load()
    } catch (e: any) {
      message.error(e?.response?.data?.message || '保存失败')
    }
  }

  const handleDelete = async (row: PickableScopeItem) => {
    try {
      await pickableScopeApi.remove(row.id)
      message.success('已删除')
      load()
    } catch (e: any) {
      message.error(e?.response?.data?.message || '删除失败')
    }
  }

  const kindWatch = Form.useWatch('kind', form)

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      render: (n: string, r: PickableScopeItem) => (
        <Space>
          <span className="font-bold">{n}</span>
          {r.is_system && <Tag color="blue">预置</Tag>}
        </Space>
      ),
    },
    { title: '编码', dataIndex: 'code', width: 160, render: (c: string) => <span className="font-mono text-slate-500">{c}</span> },
    {
      title: '类型',
      dataIndex: 'kind',
      width: 110,
      render: (k: string) => (k === 'department' ? <Tag>部门</Tag> : <Tag color="green">人员</Tag>),
    },
    {
      title: '成员',
      key: 'members',
      ellipsis: true,
      render: (_: unknown, r: PickableScopeItem) => {
        const rules = r.rules || {}
        if (r.kind === 'person') {
          const n = rules.user_ids?.length || 0
          return n ? `${n} 人` : <span className="text-slate-400">未设置（不限制）</span>
        }
        const n = rules.dept_ids?.length || 0
        return n ? `${n} 个部门` : <span className="text-slate-400">未设置（不限制）</span>
      },
    },
    {
      title: '操作',
      width: 140,
      render: (_: unknown, r: PickableScopeItem) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          {!r.is_system && (
            <Popconfirm title="确认删除该范围？" onConfirm={() => handleDelete(r)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">可选范围</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            直接勾选人员或部门。表单字段绑定范围编码后，下拉只出现这些人/部门。
          </p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建范围</Button>
      </div>

      <Alert
        type="info"
        showIcon
        className="mb-4"
        message="怎么用"
        description="1）「方案管理-设计指派」勾选人选、「方案管理-科室」勾选部门 → 2）表单字段绑定对应范围 → 3）审批下拉只出现这些人/部门。"
      />

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <Select
          allowClear
          placeholder="类型筛选"
          style={{ width: 160 }}
          options={KIND_OPTS}
          value={kindFilter}
          onChange={setKindFilter}
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={false} />
      </div>

      <Modal
        title={editing ? `编辑 · ${editing.name}` : '新建可选范围'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" className="mt-2">
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '必填' }]}
            extra="表单字段引用此编码；创建后不可改">
            <Input placeholder="如 room_leaders" disabled={!!editing} />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 方案管理-设计指派" />
          </Form.Item>
          <Form.Item name="kind" label="类型" rules={[{ required: true }]}>
            <Select options={KIND_OPTS} disabled={!!editing} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} placeholder="用途说明（可选）" />
          </Form.Item>

          {kindWatch === 'person' && (
            <Form.Item
              name="user_ids"
              label="成员"
              extra="勾选后，绑定本范围的人员字段只能选这些人；留空=不限制"
            >
              <PersonField multi placeholder="选择人员" />
            </Form.Item>
          )}

          {kindWatch === 'department' && (
            <>
              <Form.Item
                name="dept_ids"
                label="可选部门"
                extra="留空=不限制；非空=仅这些部门可选"
              >
                <DeptField multi />
              </Form.Item>
              <Form.Item name="include_children" label="含下级部门" valuePropName="checked">
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  )
}
