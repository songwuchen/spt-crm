// 移动端 → 表单填报页: 按已发布 schema 渲染 FormRenderer, 提交/存草稿。
// 支持 ?code=scheme_management 分区布局、默认值、关联商机/客户回填、returnTo。
import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import FormRenderer, { validateRequired, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { useAuthStore } from '@/stores/useAuthStore'
import { DRAWING_FORM_LAYOUT, applyDrawingFormLayout } from '@/constants/drawingFormLayout'
import { buildLowcodeInitialValues } from '@/utils/lowcodeFormDefaults'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'

export default function MobileLowcodeFormFill() {
  usePageTitle('填报')
  const { id: paramId = '' } = useParams()
  const [sp] = useSearchParams()
  const templateCode = sp.get('code') || undefined
  const returnTo = sp.get('returnTo') || '/m/lowcode/forms'
  const nav = useNavigate()
  const [templateId, setTemplateId] = useState(paramId)
  const [name, setName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [value, setValue] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const currentUser = useAuthStore((s) => s.user)

  const layout = templateCode ? DRAWING_FORM_LAYOUT[templateCode] : undefined
  const displayFields = layout ? applyDrawingFormLayout(templateCode, fields) : fields

  useEffect(() => {
    (async () => {
      try {
        let tid = paramId
        if (!tid && templateCode) {
          const res = await lowcodeApi.ensureBuiltin(templateCode)
          tid = res.data.id
        }
        if (!tid) {
          setErr('缺少表单'); return
        }
        setTemplateId(tid)
        const [tpl, ver] = await Promise.all([lowcodeApi.getTemplate(tid), lowcodeApi.publishedVersion(tid)])
        const defs = (ver.data.field_definitions as FieldDefinition[]) || []
        setName(tpl.data.name)
        setFields(defs)
        setRules((ver.data.rule_definitions as FormRule[]) || [])
        setValue(buildLowcodeInitialValues(defs, useAuthStore.getState().user))
      } catch { setErr('该表单尚未发布或不存在') } finally { setLoading(false) }
    })()
  }, [paramId, templateCode])

  useEffect(() => {
    if (!currentUser?.id || !fields.length) return
    setValue((prev) => {
      let changed = false
      const next = { ...prev }
      for (const f of fields) {
        const props = (f.props || {}) as Record<string, unknown>
        if (!props.default_current_user) continue
        if (f.type !== 'person' && f.type !== 'person_multi') continue
        if (next[f.id] != null && next[f.id] !== '') continue
        next[f.id] = f.type === 'person_multi' ? [currentUser.id] : currentUser.id
        changed = true
      }
      return changed ? next : prev
    })
  }, [currentUser?.id, fields])

  const relatedProjectId = value.related_project == null || value.related_project === ''
    ? ''
    : String(value.related_project)
  const relatedCustomerId = value.related_customer == null || value.related_customer === ''
    ? ''
    : String(value.related_customer)

  useEffect(() => {
    if (!fields.length || !relatedProjectId) return
    const hasCustomer = fields.some((f) => f.id === 'related_customer')
    const hasName = fields.some((f) => f.id === 'customer_name')
    if (!hasCustomer && !hasName) return
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
          if (hasName && cname && next.customer_name !== cname) {
            next.customer_name = cname
            changed = true
          }
          return changed ? next : prev
        })
      } catch { /* ignore */ }
    })()
    return () => { alive = false }
  }, [relatedProjectId, fields])

  useEffect(() => {
    if (!fields.length || !relatedCustomerId) return
    if (!fields.some((f) => f.id === 'customer_name')) return
    let alive = true
    ;(async () => {
      try {
        const r = await customerApi.get(relatedCustomerId)
        const cname = (r.data?.name || '').trim()
        if (!alive || !cname) return
        setValue((prev) => (prev.customer_name === cname ? prev : { ...prev, customer_name: cname }))
      } catch { /* ignore */ }
    })()
    return () => { alive = false }
  }, [relatedCustomerId, fields])

  const save = async (asDraft: boolean) => {
    if (!templateId) return
    if (!asDraft) {
      const states = computeFieldStates(displayFields, value, rules, deriveRolePerms(displayFields, userRoles))
      const e = validateRequired(displayFields, states, value, rules)
      if (e) { message.error(e); return }
    }
    setSubmitting(true)
    try {
      await lowcodeApi.createInstance({ template_id: templateId, form_data: value, as_draft: asDraft })
      message.success(asDraft ? '草稿已保存' : '提交成功')
      nav(returnTo)
    } catch { message.error(asDraft ? '保存失败' : '提交失败') } finally { setSubmitting(false) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} /></div>
  if (err) return (
    <div className="text-center py-16">
      <MobileIcon name="error_outline" className="text-slate-200 mb-2" style={{ fontSize: 48 }} />
      <p className="text-sm text-slate-400 mt-2">{err}</p>
      <button onClick={() => nav(returnTo)} className="mt-4 text-primary bg-transparent border-0">返回</button>
    </div>
  )

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 140px)' }}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center truncate px-2">{name}</h2>
        <div className="w-10" />
      </div>
      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <FormRenderer
          fields={displayFields}
          rules={rules}
          mode="edit"
          value={value}
          onChange={setValue}
          detailLayout="cards"
        />
      </div>
      <div className="fixed left-0 right-0 z-30 bg-white border-t border-slate-100 p-3"
        style={{ bottom: 'calc(env(safe-area-inset-bottom) + 56px)' }}>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => save(true)}
            disabled={submitting}
            className="flex-1 h-11 rounded-xl bg-slate-100 text-slate-700 font-bold border-0 disabled:opacity-60"
          >
            存草稿
          </button>
          <button
            type="button"
            onClick={() => save(false)}
            disabled={submitting}
            className="flex-[1.4] h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60"
          >
            {submitting ? '提交中…' : '提交'}
          </button>
        </div>
      </div>
    </div>
  )
}
