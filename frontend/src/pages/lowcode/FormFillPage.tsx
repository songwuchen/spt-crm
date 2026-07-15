// 扩展平台 → 表单填报: 按已发布 schema 渲染, 提交生成一条数据。
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Space, message, Typography, Result } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import FormRenderer, { validateRequired } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'

const { Title } = Typography

export default function FormFillPage() {
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [value, setValue] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const [tpl, ver] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.publishedVersion(id)])
        setName(tpl.data.name)
        setFields((ver.data.field_definitions as FieldDefinition[]) || [])
        setRules((ver.data.rule_definitions as FormRule[]) || [])
      } catch {
        setErr('该表单尚未发布或不存在')
      } finally { setLoading(false) }
    })()
  }, [id])

  const submit = async (asDraft: boolean) => {
    if (!asDraft) {
      const states = computeFieldStates(fields, value, rules)
      const e = validateRequired(fields, states, value)
      if (e) { message.error(e); return }
    }
    setSubmitting(true)
    try {
      await lowcodeApi.createInstance({ template_id: id, form_data: value, as_draft: asDraft })
      message.success(asDraft ? '已存为草稿' : '提交成功')
      nav(`/lowcode/forms/${id}/data`)
    } finally { setSubmitting(false) }
  }

  if (loading) return <Card loading />
  if (err) return <Result status="warning" title={err} extra={<Button onClick={() => nav('/lowcode/forms')}>返回表单中心</Button>} />

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/lowcode/forms')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>填报 · {name}</Title>
      </Space>
      <div style={{ maxWidth: 760 }}>
        <FormRenderer fields={fields} rules={rules} mode="edit" value={value} onChange={setValue} />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={() => submit(true)} loading={submitting}>存草稿</Button>
          <Button type="primary" onClick={() => submit(false)} loading={submitting}>提交</Button>
        </Space>
      </div>
    </Card>
  )
}
