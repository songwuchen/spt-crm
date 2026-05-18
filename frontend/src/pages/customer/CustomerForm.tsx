import { useEffect, useState, useRef, useCallback } from 'react'
import { Form, Input, Select, Button, Card, Alert, message } from 'antd'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import { useAutoSave } from '@/hooks/useAutoSave'
import { useAuthStore } from '@/stores/useAuthStore'

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
  const [searchParams] = useSearchParams()
  const toPool = searchParams.get('pool') === '1'
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑客户' : toPool ? '新建公海客户' : '新建客户')

  const industryDict = useDataDict('industry', defaultIndustries)
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))
  const levelDict = useDataDict('customer_level', defaultLevels)
  const scaleDict = useDataDict('scale_level', defaultScales)
  const sourceDict = useDataDict('customer_source', defaultSources)

  const currentUser = useAuthStore((s) => s.user)
  const userSelect = useUserSelect()

  const [similarCustomers, setSimilarCustomers] = useState<{ id: string; name: string; short_name?: string; industry?: string; owner_name?: string; match_type?: string; match_phone?: string; match_contact?: string }[]>([])
  const dupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const checkDuplicates = useCallback((name?: string, phone?: string) => {
    if (dupTimerRef.current) clearTimeout(dupTimerRef.current)
    if ((!name || name.length < 2) && (!phone || phone.length < 4)) { setSimilarCustomers([]); return }
    dupTimerRef.current = setTimeout(async () => {
      try {
        const res = await customerApi.checkSimilar({
          name: name && name.length >= 2 ? name : undefined,
          phone: phone && phone.length >= 4 ? phone : undefined,
          exclude_id: id,
        })
        setSimilarCustomers(res.data || [])
      } catch { /* ignore */ }
    }, 500)
  }, [id])

  const { restoreDraft, clearDraft, markDirty } = useAutoSave(`customer_form_${id || 'new'}`, form)

  useEffect(() => {
    if (id) {
      customerApi.get(id).then((res) => {
        form.setFieldsValue(res.data)
        // Seed owner option so Select shows name instead of raw ID
        if (res.data.owner_id && res.data.owner_name) {
          userSelect.setInitialOption({ label: res.data.owner_name, value: res.data.owner_id })
        }
      }).catch(() => message.error('加载客户数据失败'))
    } else {
      const restored = restoreDraft()
      if (restored) message.info('已恢复上次未保存的草稿')
      // Pre-fill current user as owner for normal customers; pool customers stay unassigned.
      if (currentUser && !toPool) {
        form.setFieldsValue({ owner_id: currentUser.id })
        userSelect.setInitialOption({ label: currentUser.real_name || currentUser.username, value: currentUser.id })
      }
    }
    return () => { if (dupTimerRef.current) clearTimeout(dupTimerRef.current) }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      const payload = { ...values, owner_id: toPool ? null : (values.owner_id || null) } as any
      if (isEdit) {
        await customerApi.update(id!, payload)
        message.success('客户已更新')
      } else {
        await customerApi.create(payload, toPool)
        message.success(toPool ? '已新建到公海' : '客户已创建')
      }
      clearDraft()
      navigate(toPool ? '/customers/pool' : '/customers')
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
        <Form form={form} layout="vertical" onFinish={onFinish} onValuesChange={markDirty} className="max-w-2xl">
          <Form.Item name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="请输入客户全称" onChange={(e) => checkDuplicates(e.target.value, form.getFieldValue('phone'))} />
          </Form.Item>
          {similarCustomers.length > 0 && (
            <Alert type="warning" showIcon className="mb-4"
              message={`发现 ${similarCustomers.length} 个疑似重复客户`}
              description={
                <div className="mt-1 space-y-1">
                  {similarCustomers.map((c) => (
                    <div key={c.id} className="flex items-center gap-2 text-sm">
                      <a onClick={() => navigate(`/customers/${c.id}`)} className="text-primary font-bold hover:underline">{c.name}</a>
                      {c.match_type === 'phone' && (
                        <span className="text-orange-500 text-sm bg-orange-50 px-1.5 py-0.5 rounded">
                          电话匹配: {c.match_contact} {c.match_phone}
                        </span>
                      )}
                      {c.match_type === 'name' && (
                        <span className="text-blue-500 text-sm bg-blue-50 px-1.5 py-0.5 rounded">名称匹配</span>
                      )}
                      {c.industry && <span className="text-slate-400 text-sm">{industryMap[c.industry] || c.industry}</span>}
                      {c.owner_name && <span className="text-slate-400 text-sm">负责人: {c.owner_name}</span>}
                      {!isEdit && (
                        <a onClick={() => navigate(`/customers/${c.id}`)} className="text-sm text-emerald-600 hover:underline">查看并合并</a>
                      )}
                    </div>
                  ))}
                </div>
              }
            />
          )}
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
          {!toPool && (
            <Form.Item name="owner_id" label="负责人">
              <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                loading={userSelect.loading}
                options={userSelect.options}
                onSearch={userSelect.onSearch}
                onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            </Form.Item>
          )}
          {toPool && (
            <Alert type="info" showIcon className="mb-4"
              message="新建到公海"
              description="该客户将进入公海池（无负责人），后续可由销售员领取或由管理员分配。" />
          )}
          {isEdit && (
            <Form.Item name="status" label="状态">
              <Select options={[
                { label: '活跃', value: 'active' },
                { label: '不活跃', value: 'inactive' },
              ]} />
            </Form.Item>
          )}
          <Form.Item name="tags_json" label="标签">
            <Select mode="tags" placeholder="输入标签后回车添加" tokenSeparators={[',']} />
          </Form.Item>
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
