import { useEffect, useState } from 'react'
import { Form, Input, Select, Button, Card, InputNumber, DatePicker, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { userApi } from '@/api/user'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import dayjs from 'dayjs'

const riskOptions = [
  { label: '低', value: 'L' },
  { label: '中', value: 'M' },
  { label: '高', value: 'H' },
]

const statusOptions = [
  { label: '进行中', value: 'active' },
  { label: '赢单', value: 'won' },
  { label: '丢单', value: 'lost' },
  { label: '暂停', value: 'suspended' },
]

export default function OpportunityForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑商机' : '新建商机')

  const customerSelect = useRemoteSelect(async (kw) => {
    const r = await customerApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  useEffect(() => {
    if (id) {
      projectApi.get(id).then((res) => {
        const d = res.data
        form.setFieldsValue({
          ...d,
          close_date_expect: d.close_date_expect ? dayjs(d.close_date_expect) : undefined,
        })
      }).catch(() => message.error('加载商机数据失败'))
    }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      const payload = {
        ...values,
        close_date_expect: values.close_date_expect ? (values.close_date_expect as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
      }
      if (isEdit) {
        await projectApi.update(id!, payload)
        message.success('商机已更新')
      } else {
        await projectApi.create(payload)
        message.success('商机已创建')
      }
      navigate('/opportunities')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{isEdit ? '编辑商机' : '新建商机'}</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={onFinish} className="max-w-2xl">
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="customer_id" label="关联客户" rules={[{ required: true, message: '请选择关联客户' }]}>
            <Select placeholder="请选择客户" showSearch filterOption={false}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </Form.Item>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Form.Item name="amount_expect" label="预期金额" rules={[{ required: true, message: '请输入预期金额' }]}>
              <InputNumber className="w-full" placeholder="请输入预期金额" min={0} precision={2} />
            </Form.Item>
            <Form.Item name="probability" label="成交概率 (%)" rules={[{ type: 'number', min: 0, max: 100, message: '概率范围 0-100' }]}>
              <InputNumber className="w-full" placeholder="0-100" min={0} max={100} />
            </Form.Item>
          </div>
          <Form.Item name="close_date_expect" label="预期成交日期">
            <DatePicker className="w-full" />
          </Form.Item>
          <Form.Item name="risk_level" label="风险等级">
            <Select placeholder="请选择风险等级" allowClear options={riskOptions} />
          </Form.Item>
          <Form.Item name="owner_id" label="负责人">
            <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
          {isEdit && (
            <Form.Item name="status" label="状态">
              <Select options={statusOptions} />
            </Form.Item>
          )}
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
            <Button className="ml-2" onClick={() => navigate('/opportunities')}>取消</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
