// 扩展平台 → 自定义字段: 为既有业务实体(客户/线索/订单...)设计扩展字段。
// 复用表单设计器: 每个实体的扩展字段 = 一张系统表单模板,点「设计字段」跳设计器。
import { useNavigate } from 'react-router-dom'
import { Card, List, Button, Typography, Tag, message } from 'antd'
import { EditOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'

const { Title, Text } = Typography

const ENTITIES: { type: string; label: string; desc: string }[] = [
  { type: 'customer', label: '客户', desc: '客户档案扩展字段' },
  { type: 'lead', label: '线索', desc: '线索登记扩展字段' },
  { type: 'project', label: '商机', desc: '商机跟进扩展字段' },
  { type: 'contact', label: '联系人', desc: '联系人扩展字段' },
  { type: 'order', label: '订单', desc: '订单扩展字段' },
  { type: 'contract', label: '合同', desc: '合同扩展字段' },
  { type: 'service_ticket', label: '售后工单', desc: '工单扩展字段' },
  // 报价/回款的扩展字段已在 QuoteDetail、PaymentPage 渲染，后端白名单也一直支持，
  // 这里此前漏了入口，导致这两个实体的字段无处可设计。
  { type: 'quote', label: '报价', desc: '报价单扩展字段' },
  { type: 'payment', label: '回款', desc: '回款记录扩展字段' },
]

export default function EntityFieldsAdmin() {
  const nav = useNavigate()
  const design = async (entityType: string) => {
    try {
      const r = await lowcodeApi.entityTemplate(entityType)
      nav(`/lowcode/forms/${r.data.id}/design`)
    } catch { message.error('打开设计器失败') }
  }
  return (
    <Card>
      <Title level={4} style={{ marginTop: 0 }}>自定义字段</Title>
      <Text type="secondary">为既有业务表单添加扩展字段,复用表单设计器(支持文本/数字/金额/日期/人员/部门/下拉/明细子表/公式等富字段类型)。设计并发布后,对应业务的新建/编辑/详情页会自动展示这些字段。</Text>
      <List
        style={{ marginTop: 16 }}
        grid={{ gutter: 16, xs: 1, sm: 2, md: 3 }}
        dataSource={ENTITIES}
        renderItem={(e) => (
          <List.Item>
            <Card size="small" title={<span>{e.label} <Tag>{e.type}</Tag></span>}
              extra={<Button type="link" icon={<EditOutlined />} onClick={() => design(e.type)}>设计字段</Button>}>
              <Text type="secondary" style={{ fontSize: 12 }}>{e.desc}</Text>
            </Card>
          </List.Item>
        )}
      />
    </Card>
  )
}
