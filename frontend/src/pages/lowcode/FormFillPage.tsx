// 扩展平台 → 表单填报: 按已发布 schema 渲染, 提交生成一条数据。
import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Button, Space, message, Typography, Result } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import FormRenderer, { findRequiredError, scrollToLcField, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { useAuthStore } from '@/stores/useAuthStore'
import { DRAWING_FORM_LAYOUT, applyDrawingFormLayout } from '@/constants/drawingFormLayout'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { buildLowcodeInitialValues } from '@/utils/lowcodeFormDefaults'

const { Title, Text } = Typography

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
  templateCode,
  contentMaxWidth,
}: {
  /** 侧栏模块传入；缺省则从路由 /lowcode/forms/:id/fill 取 */
  templateId?: string
  /** 返回/提交后跳转；模块入口传列表路径，避免掉进扩展平台 */
  returnTo?: string
  pageTitle?: string
  /** 内置模块 code，用于图纸表单分区布局 */
  templateCode?: string
  contentMaxWidth?: number
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
  const currentUser = useAuthStore((s) => s.user)

  const layout = templateCode ? DRAWING_FORM_LAYOUT[templateCode] : undefined
  const displayFields = layout ? applyDrawingFormLayout(templateCode, fields) : fields
  const maxWidth = contentMaxWidth ?? layout?.contentMaxWidth ?? 760

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
        setValue(buildLowcodeInitialValues(defs, useAuthStore.getState().user))
      } catch {
        setErr('该表单尚未发布或不存在')
      } finally { setLoading(false) }
    })()
  }, [id])

  // 用户信息晚于 schema 加载时，补填 default_current_user / default_current_dept
  useEffect(() => {
    if (!currentUser?.id || !fields.length) return
    setValue((prev) => {
      let changed = false
      const next = { ...prev }
      const primaryDept = currentUser.department_id
        || currentUser.department_ids?.[0]
      for (const f of fields) {
        const props = (f.props || {}) as Record<string, unknown>
        if (props.default_current_user && (f.type === 'person' || f.type === 'person_multi')) {
          if (next[f.id] == null || next[f.id] === '') {
            next[f.id] = f.type === 'person_multi' ? [currentUser.id] : currentUser.id
            changed = true
          }
        }
        if (props.default_current_dept && (f.type === 'department' || f.type === 'department_multi') && primaryDept) {
          if (next[f.id] == null || next[f.id] === '' || (Array.isArray(next[f.id]) && !(next[f.id] as unknown[]).length)) {
            next[f.id] = f.type === 'department_multi' ? [primaryDept] : primaryDept
            changed = true
          }
        }
      }
      return changed ? next : prev
    })
  }, [currentUser?.id, currentUser?.department_id, currentUser?.department_ids, fields])

  // 关联商机 / 关联客户 → 回填公司名称（对齐合同登记：选商机带客户，选客户回填名称）
  const relatedProjectId = value.related_project == null || value.related_project === ''
    ? ''
    : String(value.related_project)
  const relatedCustomerId = value.related_customer == null || value.related_customer === ''
    ? ''
    : String(value.related_customer)

  useEffect(() => {
    if (!fields.length || !relatedProjectId) return
    const hasCustomer = fields.some((f) => f.id === 'related_customer')
    const nameField = fields.find((f) => f.id === 'customer_name')
    if (!hasCustomer && !nameField) return
    const nameIsCustomerPicker = nameField?.type === 'customer'

    let alive = true
    ;(async () => {
      try {
        const r = await projectApi.get(relatedProjectId)
        const cid = r.data?.customer_id
        let cname = (r.data?.customer_name || '').trim()
        if (cid && !cname) {
          try {
            const cr = await customerApi.get(cid)
            cname = (cr.data?.name || '').trim()
          } catch { /* ignore */ }
        }
        if (!alive) return
        setValue((prev) => {
          const next = { ...prev }
          let changed = false
          if (hasCustomer && cid && next.related_customer !== cid) {
            next.related_customer = cid
            changed = true
          }
          // 报价管理 customer_name 为客户选择器：回填客户 id；方案管理等为文本：回填名称
          if (nameField) {
            if (nameIsCustomerPicker && cid && next.customer_name !== cid) {
              next.customer_name = cid
              changed = true
            } else if (!nameIsCustomerPicker && cname && next.customer_name !== cname) {
              next.customer_name = cname
              changed = true
            }
          }
          return changed ? next : prev
        })
      } catch {
        /* 带出失败不阻断填报 */
      }
    })()
    return () => { alive = false }
  }, [relatedProjectId, fields])

  useEffect(() => {
    if (!fields.length || !relatedCustomerId) return
    const nameField = fields.find((f) => f.id === 'customer_name')
    // 仅文本型公司名称需要从关联客户回填；客户选择器本身已是 id
    if (!nameField || nameField.type === 'customer') return

    let alive = true
    ;(async () => {
      try {
        const r = await customerApi.get(relatedCustomerId)
        const cname = (r.data?.name || '').trim()
        if (!alive || !cname) return
        setValue((prev) => {
          if (prev.customer_name === cname) return prev
          return { ...prev, customer_name: cname }
        })
      } catch {
        /* ignore */
      }
    })()
    return () => { alive = false }
  }, [relatedCustomerId, fields])

  // 选部门 → 回填部门编号（对齐简道云「部门编号基础表」）
  const departmentId = value.department == null || value.department === ''
    ? ''
    : (typeof value.department === 'object' && value.department !== null && 'id' in (value.department as object)
      ? String((value.department as { id?: string }).id || '')
      : String(value.department))

  useEffect(() => {
    if (!fields.length || !departmentId) return
    if (!fields.some((f) => f.id === 'dept_code')) return

    let alive = true
    ;(async () => {
      try {
        const r = await lowcodeApi.lookupDeptCode(departmentId)
        const code = (r.data?.dept_code || '').trim()
        if (!alive) return
        setValue((prev) => {
          if (!code) {
            // 清部门或无匹配时不强制清空用户已手填编号
            return prev
          }
          if (prev.dept_code === code) return prev
          return { ...prev, dept_code: code }
        })
      } catch {
        /* ignore */
      }
    })()
    return () => { alive = false }
  }, [departmentId, fields])

  // 选业务员 → 回填区域经理/组长（对齐简道云「业务员区域经理对照」）
  const salesSourceField = fields.find((f) =>
    f.type === 'person' && (f.id === 'sales_person' || f.id === 'salesperson' || f.id === 'owner_id'
      || f.label === '业务员'),
  )
  const regionTargetField = fields.find((f) =>
    f.type === 'person' && (f.id === 'region_manager' || f.id === 'region_manager_id'
      || (f.label || '').includes('区域经理')),
  )
  const salesPersonRaw = salesSourceField ? value[salesSourceField.id] : undefined
  const salesPersonId = salesPersonRaw == null || salesPersonRaw === ''
    ? ''
    : (typeof salesPersonRaw === 'object' && salesPersonRaw !== null && 'id' in (salesPersonRaw as object)
      ? String((salesPersonRaw as { id?: string }).id || '')
      : String(salesPersonRaw))

  const prevSalesPersonRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (!fields.length || !salesSourceField || !regionTargetField) return
    const sid = salesPersonId.trim()
    const prev = prevSalesPersonRef.current
    const changed = prev !== undefined && prev !== sid
    prevSalesPersonRef.current = sid
    const targetId = regionTargetField.id

    if (!sid) {
      if (changed) {
        setValue((prevV) => {
          if (prevV[targetId] == null || prevV[targetId] === '') return prevV
          return { ...prevV, [targetId]: undefined }
        })
      }
      return
    }

    let alive = true
    ;(async () => {
      try {
        const r = await lowcodeApi.lookupSalespersonRegion(sid)
        const mid = (r.data?.region_manager_id || '').trim()
        if (!alive) return
        setValue((prevV) => {
          if (mid) {
            if (prevV[targetId] === mid) return prevV
            return { ...prevV, [targetId]: mid }
          }
          if (changed && prevV[targetId] != null && prevV[targetId] !== '') {
            return { ...prevV, [targetId]: undefined }
          }
          return prevV
        })
      } catch {
        /* ignore */
      }
    })()
    return () => { alive = false }
  }, [salesPersonId, fields, salesSourceField?.id, regionTargetField?.id])

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
      const states = computeFieldStates(displayFields, value, rules, deriveRolePerms(displayFields, userRoles))
      const e = findRequiredError(displayFields, states, value, rules)
      if (e) {
        message.error(e.message)
        scrollToLcField(e.fieldId)
        return
      }
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
      <div style={{ maxWidth }}>
        <FormRenderer
          fields={displayFields}
          rules={rules}
          mode="edit"
          value={value}
          onChange={(next) => setValue((prev) => ({ ...prev, ...next }))}
          serialPreviews={serialPreviews}
        />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={() => submit(true)} loading={submitting}>存草稿</Button>
          <Button type="primary" onClick={() => submit(false)} loading={submitting}>提交</Button>
        </Space>
        <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
          「提交」会发起审批；「存草稿」仅保存，可稍后在列表中打开草稿再点「提交审批」。
        </Text>
      </div>
    </Card>
  )
}
