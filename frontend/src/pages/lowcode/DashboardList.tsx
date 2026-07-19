// 扩展平台 → 仪表盘列表(建/打开/删)。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Row, Col, Button, Modal, Form, Input, message, Popconfirm, Empty, Typography } from 'antd'
import { PlusOutlined, DashboardOutlined, DeleteOutlined } from '@ant-design/icons'
import { dashboardApi } from '@/api/lowcodeDashboard'
import { usePermission } from '@/hooks/usePermission'
import type { Dashboard } from '@/types/lowcode'

const { Title, Text } = Typography

export default function DashboardList() {
  const nav = useNavigate()
  const { hasPermission } = usePermission()
  const canManage = hasPermission('dashboard:manage')
  const [items, setItems] = useState<Dashboard[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try { const r = await dashboardApi.list({ pageNo: 1, pageSize: 100 }); setItems(r.data.items) }
    catch { message.error('加载仪表盘失败') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    const v = await form.validateFields()
    setCreating(true)
    try {
      const r = await dashboardApi.create(v)
      message.success('已创建'); setOpen(false); form.resetFields()
      nav(`/lowcode/dashboards/${r.data.id}`)
    } catch { message.error('创建仪表盘失败') } finally { setCreating(false) }
  }
  const del = async (id: string) => {
    try { await dashboardApi.remove(id); message.success('已删除'); load() }
    catch { message.error('删除失败') }
  }

  return (
    <Card loading={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>仪表盘</Title>
        {canManage && <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>新建仪表盘</Button>}
      </div>
      {items.length === 0 ? <Empty description={canManage ? '还没有仪表盘,点右上角新建' : '还没有仪表盘'} /> : (
        <Row gutter={[16, 16]}>
          {items.map((d) => (
            <Col key={d.id} xs={24} sm={12} md={8} lg={6}>
              <Card hoverable onClick={() => nav(`/lowcode/dashboards/${d.id}`)}
                actions={canManage ? [
                  <Popconfirm key="del" title="删除该仪表盘?" onConfirm={(e) => { e?.stopPropagation(); del(d.id) }} onCancel={(e) => e?.stopPropagation()}>
                    <DeleteOutlined onClick={(e) => e.stopPropagation()} />
                  </Popconfirm>,
                ] : undefined}>
                <Card.Meta avatar={<DashboardOutlined style={{ fontSize: 28, color: '#1677ff' }} />}
                  title={d.name} description={<Text type="secondary">{d.components?.length || 0} 个组件</Text>} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal title="新建仪表盘" open={open} onOk={create} confirmLoading={creating} onCancel={() => setOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如: 销售概览 / 请假统计" />
          </Form.Item>
          <Form.Item name="description" label="说明"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
