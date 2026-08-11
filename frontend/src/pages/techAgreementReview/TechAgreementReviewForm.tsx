/**
 * 技术协议评审 · 新增（对齐方案管理 /solutions/fill）。
 * 路由：/tech-agreement-reviews/fill ；旧 /new、/:id/edit 仍可进本页。
 */
import { useEffect, useState } from 'react'
import { Button, Form, Space, message, Select } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useNavigate, useParams, useLocation, useSearchParams } from 'react-router-dom'
import { techAgreementReviewApi } from '@/api/techAgreementReview'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { industryLabels } from '@/api/types'
import TechAgreementFields from '@/components/TechAgreementFields'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { TECH_AGREEMENT_STATUS } from '@/constants/techAgreementReview'
import { tarBuildPayload, tarRowToFormValues, canEditTarStatus } from '@/pages/techAgreementReview/tarFormUtils'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCustomerSelect } from '@/hooks/useSelectOptions'
import { formatRegion } from '@/utils/address'

const LIST_PATH = '/tech-agreement-reviews'

type LocState = { scrollToField?: (string | number)[] }

function formatCustomerIndustry(c: Customer): string {
  const levels = [c.industry_l1, c.industry_l2, c.industry_l3].filter(Boolean)
  if (levels.length) return levels.join('/')
  const raw = (c.industry || '').trim()
  if (!raw) return ''
  return industryLabels[raw] || raw
}

function formatCustomerAddress(c: Customer): string {
  const region = formatRegion(c, '')
  const detail = (c.address || '').trim()
  if (region && detail) return `${region}${detail}`
  return region || detail
}

export default function TechAgreementReviewForm() {
  const { id: routeId } = useParams<{ id: string }>()
  const [search] = useSearchParams()
  const draftFromQuery = search.get('draft') || undefined
  const isRouteEdit = !!routeId && routeId !== 'new'
  const navigate = useNavigate()
  const location = useLocation()
  const isFillRoute = location.pathname.endsWith('/fill') || location.pathname.endsWith('/new')
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [fillingCustomer, setFillingCustomer] = useState(false)
  const [reviewId, setReviewId] = useState<string | undefined>(
    isRouteEdit ? routeId : draftFromQuery,
  )
  const customerSelect = useCustomerSelect()
  const currentUser = useAuthStore((s) => s.user)
  usePageTitle(isRouteEdit ? '编辑技术协议评审' : '新增 · 技术协议评审')

  const goList = () => navigate(LIST_PATH)

  const fillFromCustomer = async (customerId: string, fallbackName?: string) => {
    setFillingCustomer(true)
    try {
      const res = await customerApi.get(customerId)
      const c = res.data
      form.setFieldsValue({
        customer_id: customerId,
        company_name: (c.name || fallbackName || '').trim() || undefined,
        industry: formatCustomerIndustry(c) || undefined,
        address: formatCustomerAddress(c) || undefined,
      })
    } catch {
      form.setFieldsValue({
        customer_id: customerId,
        company_name: fallbackName || form.getFieldValue('company_name'),
      })
      message.warning('客户详情加载失败，行业/地址未自动带出，可手动填写')
    } finally {
      setFillingCustomer(false)
    }
  }

  useEffect(() => {
    let cancelled = false

    // 新增 fill：先落草稿以便上传附件（对齐简道云）
    if (!isRouteEdit && !draftFromQuery) {
      setLoading(true)
      const name = currentUser?.real_name || currentUser?.username
      techAgreementReviewApi.create({
        status: 'draft',
        applicant_id: currentUser?.id,
        applicant_name: name,
        owner_id: currentUser?.id,
        owner_name: name,
        apply_at: new Date().toISOString(),
        form_json: {},
      }).then((res) => {
        if (cancelled) return
        setReviewId(res.data.id)
        // 留在 fill，带 draft 参数，避免跳到独立编辑页（对齐方案管理）
        navigate(`${LIST_PATH}/fill?draft=${res.data.id}`, { replace: true, state: location.state })
        form.setFieldsValue(tarRowToFormValues(res.data))
      }).catch(() => {
        if (!cancelled) message.error('创建草稿失败，请返回重试')
      }).finally(() => {
        if (!cancelled) setLoading(false)
      })
      return () => { cancelled = true }
    }

    const loadId = isRouteEdit ? routeId! : draftFromQuery!
    setLoading(true)
    techAgreementReviewApi.get(loadId).then((res) => {
      if (cancelled) return
      const d = res.data
      if (!canEditTarStatus(d.status)) {
        message.warning('审批中或已通过的单据不可编辑，可返回列表查看')
        navigate(LIST_PATH, { replace: true })
        return
      }
      setReviewId(d.id)
      form.setFieldsValue(tarRowToFormValues(d))
      if (d.customer_id && d.company_name) {
        customerSelect.setInitialOption({ label: d.company_name, value: d.customer_id })
      }
      const scrollTo = (location.state as LocState | null)?.scrollToField
      if (scrollTo?.length) {
        setTimeout(() => form.scrollToField(scrollTo), 200)
      }
    }).catch(() => {
      if (!cancelled) {
        message.error('加载失败')
        navigate(LIST_PATH, { replace: true })
      }
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [routeId, isRouteEdit, draftFromQuery]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async (andSubmit: boolean) => {
    const rid = reviewId
    if (!rid) {
      message.warning('单据尚未就绪，请稍候再保存')
      return
    }

    let values: Record<string, unknown>
    if (andSubmit) {
      try {
        values = await form.validateFields()
      } catch (err: unknown) {
        const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
        const first = fields[0]?.errors?.[0]
        message.warning(first || '请完善必填项后再提交')
        const name = fields[0]?.name
        if (name?.length) form.scrollToField(name, { behavior: 'smooth', block: 'center' })
        return
      }
    } else {
      values = form.getFieldsValue(true) as Record<string, unknown>
    }

    setSaving(true)
    try {
      const payload = tarBuildPayload({ ...form.getFieldsValue(true), ...values })
      await techAgreementReviewApi.update(rid, payload)
      if (andSubmit) {
        try {
          await techAgreementReviewApi.submit(rid)
          message.success('已提交审批，请在「审批中心」处理待办')
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.warning(msg || '已保存，但提交审批失败，请到列表查看后重新提交')
          goList()
          return
        }
      } else {
        message.success('已存为草稿')
      }
      goList()
    } catch {
      message.error(andSubmit ? '提交失败' : '存草稿失败')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !reviewId) {
    return <div className="p-8 text-slate-400">正在创建草稿…</div>
  }

  return (
    <div className="max-w-5xl mx-auto pb-10">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={goList}>返回</Button>
          <h2 className="text-xl font-semibold m-0">
            {isFillRoute || !isRouteEdit ? '新增 · 技术协议评审' : '编辑技术协议评审'}
          </h2>
        </Space>
        <Space>
          <Button onClick={goList}>取消</Button>
          <Button loading={saving} onClick={() => void handleSave(false)}>存草稿</Button>
          <Button type="primary" loading={saving} onClick={() => void handleSave(true)}>提交</Button>
        </Space>
      </div>
      <p className="text-sm text-slate-500 mb-4 m-0">
        「提交」会直接发起审批；「存草稿」仅保存，可稍后在列表中打开再提交。
      </p>
      <Form form={form} layout="vertical" disabled={loading}>
        <ContractSectionTitle title="关联客户" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mb-4">
          <Form.Item name="customer_id" label="选择公司名称" extra="选择后自动带出公司名称、所属行业、地址">
            <Select
              allowClear
              showSearch
              filterOption={false}
              placeholder="从客户库选择"
              loading={customerSelect.loading || fillingCustomer}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
              onChange={(v, opt) => {
                if (!v) {
                  form.setFieldsValue({
                    customer_id: undefined,
                    company_name: undefined,
                    industry: undefined,
                    address: undefined,
                  })
                  return
                }
                void fillFromCustomer(String(v), (opt as { label?: string } | undefined)?.label)
              }}
            />
          </Form.Item>
          <Form.Item name="status" label="状态" hidden>
            <Select options={TECH_AGREEMENT_STATUS.map((s) => ({ value: s.value, label: s.label }))} />
          </Form.Item>
        </div>
        <TechAgreementFields
          form={form}
          slots={{
            approve_files: (
              <div className="md:col-span-2 mb-4 space-y-3">
                {reviewId ? (
                  <>
                    <AttachmentPanel bizType="tech_agreement_review_drawing" bizId={reviewId} title="认可图（附件）" />
                    <AttachmentPanel bizType="tech_agreement_review" bizId={reviewId} title="技术协议（附件）" />
                  </>
                ) : (
                  <p className="text-slate-400 text-sm m-0">正在准备附件区…</p>
                )}
              </div>
            ),
          }}
        />
      </Form>
      <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-slate-100">
        <Button onClick={goList}>取消</Button>
        <Button loading={saving} onClick={() => void handleSave(false)}>存草稿</Button>
        <Button type="primary" loading={saving} onClick={() => void handleSave(true)}>提交</Button>
      </div>
    </div>
  )
}
