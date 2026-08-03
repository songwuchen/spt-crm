// 扩展平台 → 表单填报: 按已发布 schema 渲染, 提交生成一条数据。
import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Space, message, Typography, Result } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import FormRenderer, { validateRequired, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { useAuthStore } from '@/stores/useAuthStore'

const { Title } = Typography

function buildInitialValues(fields: FieldDefinition[]): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields) {
    if (f.default_value !== undefined && f.default_value !== null && f.default_value !== '') {
      out[f.id] = f.default_value
      continue
    }
    const props = (f.props || {}) as Record<string, unknown>
    if (props.default_today && (f.type === 'date' || f.type === 'datetime')) {
      out[f.id] = dayjs().format(f.type === 'datetime' ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD')
    }
  }
  return out
}

/** 影响流水号预览的依赖字段（date/field/format_by/period_scope） */
function serialDepKey(fields: FieldDefinition[], value: Record<string, unknown>): string {
  const keys = new Set<string>()
  for (const f of fields) {
    if (f.type !== 'auto_number') continue
    const rules = ((f.props || {}) as { serial_rules?: Array<Record<string, unknown>> }).serial_rules || []
    for (const r of rules) {
      if (r.date_field) keys.add(String(r.date_field))
      if (r.field_id) keys.add(String(r.field_id))
      const fb = r.format_by_field as { field_id?: string } | undefined
      if (fb?.field_id) keys.add(fb.field_id)
      const rb = r.reset_period_by_field as { field_id?: string } | undefined
      if (rb?.field_id) keys.add(rb.field_id)
      if (r.period_scope_field) keys.add(String(r.period_scope_field))
    }
  }
  return [...keys].sort().map((k) => `${k}=${JSON.stringify(value[k] ?? null)}`).join('|')
}

export default function FormFillPage({
  templateId: propId,
  returnTo,
  pageTitle,
}: {
  /** 侧栏模块传入；缺省则从路由 /lowcode/forms/:id/fill 取 */
  templateId?: string
  /** 返回/提交后跳转；模块入口传列表路径，避免掉进扩展平台 */
  returnTo?: string
  pageTitle?: string
} = {}) {
  const { id: paramId = '' } = useParams()
  const id = propId || paramId
  const nav = useNavigate()
  const backPath = returnTo || (id ? `/lowcode/forms/${id}/data` : '/lowcode/forms')
  const [name, setName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [value, setValue] = useState<Record<string, unknown>>({})
  const [serialPreviews, setSerialPreviews] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const peekTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const depKey = serialDepKey(fields, value)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setErr(null)
    ;(async () => {
      try {
        const [tpl, ver] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.publishedVersion(id)])
        const defs = (ver.data.field_definitions as FieldDefinition[]) || []
        setName(tpl.data.name)
        setFields(defs)
        setRules((ver.data.rule_definitions as FormRule[]) || [])
        setValue(buildInitialValues(defs))
      } catch {
        setErr('该表单尚未发布或不存在')
      } finally { setLoading(false) }
    })()
  }, [id])

  useEffect(() => {
    if (!id || loading || !fields.some((f) => f.type === 'auto_number')) return
    if (peekTimer.current) clearTimeout(peekTimer.current)
    peekTimer.current = setTimeout(() => {
      lowcodeApi.peekSerials(id, value).then((res) => {
        setSerialPreviews(res.data || {})
      }).catch(() => { /* 预览失败不阻断填报 */ })
    }, 200)
    return () => {
      if (peekTimer.current) clearTimeout(peekTimer.current)
    }
  }, [id, loading, fields, depKey])

  const userRoles = useAuthStore((s) => s.user?.roles) || []

  const submit = async (asDraft: boolean) => {
    if (!asDraft) {
      const states = computeFieldStates(fields, value, rules, deriveRolePerms(fields, userRoles))
      const e = validateRequired(fields, states, value)
      if (e) { message.error(e); return }
    }
    setSubmitting(true)
    try {
      // 不把预览号写入 form_data，由后端提交时正式取号，避免并发撞号
      await lowcodeApi.createInstance({ template_id: id, form_data: value, as_draft: asDraft })
      message.success(asDraft ? '已存为草稿' : '提交成功')
      nav(backPath)
    } finally { setSubmitting(false) }
  }

  if (loading) return <Card loading />
  if (err) {
    return (
      <Result
        status="warning"
        title={err}
        extra={<Button onClick={() => nav(returnTo || '/lowcode/forms')}>返回</Button>}
      />
    )
  }

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav(backPath)}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>{pageTitle || `填报 · ${name}`}</Title>
      </Space>
      <div style={{ maxWidth: 760 }}>
        <FormRenderer
          fields={fields}
          rules={rules}
          mode="edit"
          value={value}
          onChange={setValue}
          serialPreviews={serialPreviews}
        />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={() => submit(true)} loading={submitting}>存草稿</Button>
          <Button type="primary" onClick={() => submit(false)} loading={submitting}>提交</Button>
        </Space>
      </div>
    </Card>
  )
}
