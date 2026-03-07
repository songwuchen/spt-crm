import { useEffect, useState } from 'react'
import { Form, Input, Select, Button, Card, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { userApi } from '@/api/user'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import { useDataDict } from '@/hooks/useDataDict'
import { useAutoSave } from '@/hooks/useAutoSave'

const defaultIndustries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他'].map(i => ({ label: i, value: i }))
const defaultLevels = ['A', 'B', 'C', 'D'].map(l => ({ label: l, value: l }))
const defaultScales = ['微型', '小型', '中型', '大型', '特大型'].map(s => ({ label: s, value: s }))
const defaultSources = [
  { label: '展会', value: 'expo' }, { label: '转介绍', value: 'referral' },
  { label: '广告', value: 'ad' }, { label: '官网/入站', value: 'inbound' },
  { label: '合作伙伴', value: 'partner' }, { label: '电话', value: 'call' },
]

export default function CustomerForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑客户' : '新建客户')

  const industryDict = useDataDict('industry', defaultIndustries)
  const levelDict = useDataDict('customer_level', defaultLevels)
  const scaleDict = useDataDict('scale_level', defaultScales)
  const sourceDict = useDataDict('customer_source', defaultSources)

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const { restoreDraft, clearDraft } = useAutoSave(`customer_form_${id || 'new'}`, form)

  useEffect(() => {
    if (id) {
      customerApi.get(id).then((res) => form.setFieldsValue(res.data)).catch(() => message.error('加载客户数据失败'))
    } else {
      const restored = restoreDraft()
      if (restored) message.info('已恢复上次未保存的草稿')
    }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      if (isEdit) {
        await customerApi.update(id!, values)
        message.success('客户已更新')
      } else {
        await customerApi.create(values)
        message.success('客户已创建')
      }
      clearDraft()
      navigate('/customers')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{isEdit ? '编辑客户' : '新建客户'}</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={onFinish} className="max-w-2xl">
          <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="请输入客户全称" />
          </Form.Item>
          <Form.Item name="short_name" label="简称">
            <Input placeholder="请输入简称" />
          </Form.Item>
          <Form.Item name="customer_code" label="客户编码">
            <Input placeholder="请输入客户编码（选填，系统可自动生成）" />
          </Form.Item>
          <Form.Item name="industry" label="行业">
            <Select placeholder="请选择行业" allowClear options={industryDict.options} loading={industryDict.loading} />
          </Form.Item>
          <Form.Item name="scale_level" label="企业规模">
            <Select placeholder="请选择企业规模" allowClear options={scaleDict.options} loading={scaleDict.loading} />
          </Form.Item>
          <Form.Item name="region" label="区域">
            <Input placeholder="请输入区域，如华东/华南" />
          </Form.Item>
          <Form.Item name="address" label="详细地址">
            <Input placeholder="请输入详细地址" />
          </Form.Item>
          <Form.Item name="website" label="网站"
            rules={[{ type: 'url', message: '请输入正确的网址' }]}>
            <Input placeholder="请输入公司网站地址" />
          </Form.Item>
          <Form.Item name="source" label="客户来源">
            <Select placeholder="请选择来源" allowClear options={sourceDict.options} loading={sourceDict.loading} />
          </Form.Item>
          <Form.Item name="level" label="客户级别">
            <Select placeholder="请选择级别" allowClear options={levelDict.options} loading={levelDict.loading} />
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
              <Select options={[
                { label: '活跃', value: 'active' },
                { label: '不活跃', value: 'inactive' },
              ]} />
            </Form.Item>
          )}
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
            <Button className="ml-2" onClick={() => navigate('/customers')}>取消</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
