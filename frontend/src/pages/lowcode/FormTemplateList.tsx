// 扩展平台 → 表单中心: 表单模板列表(建/设计/填报/数据/删)。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Space, Tag, Modal, Form, Input, message, Popconfirm, Typography, List, Empty, Spin, Alert,
} from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { PlusOutlined, AppstoreAddOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import { usePermission } from '@/hooks/usePermission'
import type { FormTemplate, BuiltinTemplate } from '@/types/lowcode'

const { Title } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  deprecated: { color: 'orange', text: '已停用' },
}

export default function FormTemplateList() {
  const nav = useNavigate()
  const { hasPermission } = usePermission()
  const canManage = hasPermission('form:manage')
  const canFill = hasPermission('form_data:create')
  const canViewData = hasPermission('form_data:view')
  const [items, setItems] = useState<FormTemplate[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()
  const [marketOpen, setMarketOpen] = useState(false)
  const [builtins, setBuiltins] = useState<BuiltinTemplate[]>([])
  const [marketLoading, setMarketLoading] = useState(false)
  const [installingKey, setInstallingKey] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')

  const openMarket = async () => {
    setMarketOpen(true)
    if (builtins.length === 0) {
      setMarketLoading(true)
      try {
        const res = await lowcodeApi.listBuiltins()
        setBuiltins(res.data || [])
      } catch {
        message.error('加载模板库失败')
      } finally {
        setMarketLoading(false)
      }
    }
  }

  const handleInstall = async (key: string) => {
    setInstallingKey(key)
    try {
      const res = await lowcodeApi.installBuiltin(key)
      message.success('已安装到表单中心，去设计')
      setMarketOpen(false)
      nav(`/lowcode/forms/${res.data.id}/design`)
    } catch { message.error('安装失败') } finally { setInstallingKey(null) }
  }

  const load = async () => {
    setLoading(true)
    try {
      const res = await lowcodeApi.listTemplates({
        pageNo,
        pageSize: 20,
        ...(keyword.trim() ? { name: keyword.trim() } : {}),
      })
      setItems(res.data.items)
      setTotal(res.data.total)
    } catch {
      message.error('加载表单列表失败')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [pageNo, keyword])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async () => {
    const v = await form.validateFields()
    setCreating(true)
    try {
      const res = await lowcodeApi.createTemplate(v)
      message.success('已创建，去设计表单')
      setCreateOpen(false)
      form.resetFields()
      nav(`/lowcode/forms/${res.data.id}/design`)
    } catch {
      message.error('创建表单失败')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await lowcodeApi.deleteTemplate(id)
      message.success('已删除')
      load()
    } catch {
      message.error('删除失败')
    }
  }

  const columns = [
    { title: '表单名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code' },
    { title: '分类', dataIndex: 'category', key: 'category', render: (v: string) => v || '—' },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => {
        const t = STATUS_TAG[s] || { color: 'default', text: s }
        return <Tag color={t.color}>{t.text}</Tag>
      },
    },
    { title: '版本', dataIndex: 'current_version', key: 'current_version', render: (v: number) => `v${v}` },
    {
      title: '操作', key: 'op', width: 320,
      render: (_: unknown, r: FormTemplate) => (
        <Space size="small" wrap>
          {canManage && <Button size="small" onClick={() => nav(`/lowcode/forms/${r.id}/design`)}>设计</Button>}
          {canFill && <Button size="small" type="link" disabled={r.status !== 'published'} onClick={() => nav(`/lowcode/forms/${r.id}/fill`)}>填报</Button>}
          {canViewData && <Button size="small" type="link" onClick={() => nav(`/lowcode/forms/${r.id}/data`)}>数据</Button>}
          {canManage && (
            <Popconfirm title="确认删除该表单模板?" onConfirm={() => handleDelete(r.id)} disabled={r.is_system}>
              <Button size="small" type="link" danger disabled={r.is_system}>删除</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }} className="shrink-0">
        <Title level={4} style={{ margin: 0 }}>表单中心</Title>
        {canManage && (
          <Space>
            <Button icon={<AppstoreAddOutlined />} onClick={openMarket}>从模板库新建</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建表单</Button>
          </Space>
        )}
      </div>
      <Alert
        type="info"
        showIcon
        className="mb-4"
        message="与「自定义字段」的区别"
        description={
          <>
            「自定义字段」是给客户/线索/商机等业务实体加扩展字段；图纸领用、安装图通知等是独立业务表单，在本页按名称或编码查找（如
            <Tag className="mx-1">合同图纸领用</Tag>
            编码 <code>drawing_requisition</code>，
            <Tag className="mx-1">安装图设计通知</Tag>
            编码 <code>install_drawing_notice</code>）。业务填报入口在左侧「方案管理」子菜单。
          </>
        }
      />
      <div className="mb-4 flex gap-2 flex-wrap items-center">
        <Input.Search
          allowClear
          placeholder="搜索表单名称或编码"
          style={{ width: 280 }}
          value={keyword}
          onChange={(e) => { setKeyword(e.target.value); setPageNo(1) }}
          onSearch={(v) => { setKeyword(v); setPageNo(1) }}
        />
        <span className="text-xs text-slate-400">共 {total} 个表单</span>
      </div>
      <FillHeightTable
          rowKey="id" loading={loading} columns={columns} dataSource={items} scroll={{ x: 'max-content' }}
          pagination={{ current: pageNo, total, pageSize: 20, onChange: setPageNo, showSizeChanger: false }}
        />

      <Modal title="新建表单" open={createOpen} onOk={handleCreate} confirmLoading={creating} onCancel={() => setCreateOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="表单名称" rules={[{ required: true, message: '请输入表单名称' }]}>
            <Input placeholder="如: 请假申请 / 采购申请" />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Input placeholder="可选, 如: 人事 / 行政 / 财务" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="模板市场 · 一键安装" open={marketOpen} footer={null} onCancel={() => setMarketOpen(false)} width={640}>
        {marketLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : builtins.length === 0 ? <Empty description="暂无内置模板" /> : (
          <List
            itemLayout="horizontal"
            dataSource={builtins}
            renderItem={(b) => (
              <List.Item
                actions={[
                  <Button key="install" type="primary" size="small" loading={installingKey === b.key}
                    onClick={() => handleInstall(b.key)}>安装</Button>,
                ]}
              >
                <List.Item.Meta
                  title={<Space>{b.name}{b.category && <Tag>{b.category}</Tag>}<span className="text-xs text-slate-400">{b.field_count} 个字段</span></Space>}
                  description={b.description}
                />
              </List.Item>
            )}
          />
        )}
      </Modal>
    </div>
  )
}
