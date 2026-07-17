// 移动端 → 表单填报页: 按已发布 schema 渲染 FormRenderer, 提交生成一条数据。
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition, FormRule } from '@/types/lowcode'
import FormRenderer, { validateRequired, deriveRolePerms } from '@/components/lowcode/FormRenderer'
import { computeFieldStates } from '@/components/lowcode/RuleEngine'
import { useAuthStore } from '@/stores/useAuthStore'

export default function MobileLowcodeFormFill() {
  usePageTitle('填报')
  const { id = '' } = useParams()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [rules, setRules] = useState<FormRule[]>([])
  const [value, setValue] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const userRoles = useAuthStore((s) => s.user?.roles) || []

  useEffect(() => {
    (async () => {
      try {
        const [tpl, ver] = await Promise.all([lowcodeApi.getTemplate(id), lowcodeApi.publishedVersion(id)])
        setName(tpl.data.name)
        setFields((ver.data.field_definitions as FieldDefinition[]) || [])
        setRules((ver.data.rule_definitions as FormRule[]) || [])
      } catch { setErr('该表单尚未发布或不存在') } finally { setLoading(false) }
    })()
  }, [id])

  const submit = async () => {
    const states = computeFieldStates(fields, value, rules, deriveRolePerms(fields, userRoles))
    const e = validateRequired(fields, states, value)
    if (e) { message.error(e); return }
    setSubmitting(true)
    try {
      await lowcodeApi.createInstance({ template_id: id, form_data: value, as_draft: false })
      message.success('提交成功'); nav('/m/lowcode/forms')
    } catch { message.error('提交失败') } finally { setSubmitting(false) }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} /></div>
  if (err) return (
    <div className="text-center py-16">
      <MobileIcon name="error_outline" className="text-slate-200 mb-2" style={{ fontSize: 48 }} />
      <p className="text-sm text-slate-400 mt-2">{err}</p>
      <button onClick={() => nav('/m/lowcode/forms')} className="mt-4 text-primary bg-transparent border-0">返回</button>
    </div>
  )

  return (
    <div className="pb-20">
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center truncate px-2">{name}</h2>
        <div className="w-10" />
      </div>
      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <FormRenderer fields={fields} rules={rules} mode="edit" value={value} onChange={setValue} />
      </div>
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
        <button onClick={submit} disabled={submitting}
          className="w-full h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60">
          {submitting ? '提交中…' : '提交'}
        </button>
      </div>
    </div>
  )
}
