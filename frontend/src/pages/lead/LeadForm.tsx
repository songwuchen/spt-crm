import { useEffect, useState } from 'react'
import { Form, Input, Select, Button, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import { userApi } from '@/api/user'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'

export default function LeadForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑线索' : '新建线索')

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  useEffect(() => {
    if (id) {
      leadApi.get(id).then((res) => form.setFieldsValue(res.data)).catch(() => message.error('加载线索数据失败'))
    }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      if (isEdit) {
        await leadApi.update(id!, values)
        message.success('线索已更新')
      } else {
        await leadApi.create(values)
        message.success('线索已创建')
      }
      navigate('/leads')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          {isEdit ? '编辑线索' : '新建线索'}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {isEdit ? '修改线索的基本信息' : '填写线索信息以创建新的销售线索'}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <Form form={form} layout="vertical" onFinish={onFinish} className="max-w-3xl">
          {/* Basic Info */}
          <div className="mb-6">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-4">基本信息</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Form.Item name="title" label="线索标题" rules={[{ required: true, message: '请输入线索标题' }]} className="col-span-2">
                <Input placeholder="请输入线索标题" />
              </Form.Item>
              <Form.Item name="company_name" label="公司名称">
                <Input placeholder="请输入公司名称" />
              </Form.Item>
              <Form.Item name="source" label="线索来源">
                <Select placeholder="请选择来源" allowClear
                  options={[
                    { label: '展会', value: 'expo' },
                    { label: '转介绍', value: 'referral' },
                    { label: '广告', value: 'ad' },
                    { label: '官网/入站', value: 'inbound' },
                    { label: '合作伙伴', value: 'partner' },
                    { label: '电话', value: 'call' },
                  ]} />
              </Form.Item>
              <Form.Item name="industry" label="行业">
                <Select placeholder="请选择行业" allowClear
                  options={['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他']
                    .map((i) => ({ label: i, value: i }))} />
              </Form.Item>
              <Form.Item name="region" label="区域">
                <Input placeholder="请输入区域" />
              </Form.Item>
              <Form.Item name="budget_range" label="预算范围">
                <Select placeholder="请选择预算范围" allowClear
                  options={['10万以下', '10-50万', '50-100万', '100-500万', '500万以上'].map((b) => ({ label: b, value: b }))} />
              </Form.Item>
              <Form.Item name="owner_id" label="负责人">
                <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                  loading={userSelect.loading}
                  options={userSelect.options}
                  onSearch={userSelect.onSearch}
                  onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
              </Form.Item>
            </div>
          </div>

          {/* Contact Info */}
          <div className="mb-6">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-4">联系人信息</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Form.Item name="contact_name" label="联系人姓名">
                <Input placeholder="请输入联系人姓名" />
              </Form.Item>
              <Form.Item name="contact_phone" label="联系电话"
                rules={[{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号' }]}>
                <Input placeholder="请输入联系电话" />
              </Form.Item>
              <Form.Item name="contact_email" label="联系邮箱" className="col-span-2"
                rules={[{ type: 'email', message: '请输入正确的邮箱地址' }]}>
                <Input placeholder="请输入联系邮箱" />
              </Form.Item>
            </div>
          </div>

          {/* Extra Info */}
          <div className="mb-6">
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-4">补充信息</h3>
            <Form.Item name="demand_summary" label="需求摘要">
              <Input.TextArea rows={3} placeholder="请描述客户需求" />
            </Form.Item>
            <Form.Item name="remark" label="备注">
              <Input.TextArea rows={3} placeholder="备注信息" />
            </Form.Item>
          </div>

          <div className="flex gap-3 pt-4 border-t border-slate-100">
            <Button type="primary" htmlType="submit" loading={loading} className="font-bold">
              保存
            </Button>
            <Button onClick={() => navigate('/leads')}>取消</Button>
          </div>
        </Form>
      </div>
    </div>
  )
}
