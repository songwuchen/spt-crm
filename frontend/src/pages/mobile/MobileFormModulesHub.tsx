import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { useWorkflowFormTemplateCodes } from '@/hooks/useWorkflowFormTemplateCodes'
import { MOBILE_FORM_MODULES } from '@/config/mobileFormModules'
import { mobileFormModuleRouteSegment } from '@/config/mobileFormModules'

const GROUPS: {
  title: string
  codes: string[]
  extraLinks?: { title: string; path: string }[]
}[] = [
  {
    title: '方案与报价',
    codes: [
      'drawing_requisition', 'install_drawing_notice', 'presale_service_notice',
      'scheme_management', 'quote_management', 'pricing_checklist_hjqd',
      'research_coop_card', 'tech_agreement_feedback',
    ],
  },
  {
    title: '生产与交付',
    codes: [
      'prod_card_supplement', 'contract_outsource_early', 'shipment_notice',
      'invoice_application', 'payment_registration',
    ],
  },
  {
    title: '借据',
    codes: ['contract_shipment_loan'],
    extraLinks: [{ title: '发货借据', path: '/m/contract-shipment-loans/shipment-dashboard' }],
  },
  {
    title: '合同与评审',
    codes: ['xunhan_contract_review', 'contract_drawing_map'],
  },
  {
    title: '客服',
    codes: [
      'cs_service_request', 'cs_product_replace', 'cs_product_return',
      'cs_loan_slip', 'cs_drawing_request', 'cs_service_delay', 'cs_correspondence',
    ],
  },
  {
    title: '主数据',
    codes: [
      'application_field', 'application_material', 'material_name',
      'department_code_base', 'salesperson_region_map',
    ],
  },
  {
    title: '财务',
    codes: ['biz_bonus_transfer', 'biz_bonus_biz_initiate', 'commission_database'],
  },
]

export default function MobileFormModulesHub() {
  usePageTitle('业务表单')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const { codes: wfCodes } = useWorkflowFormTemplateCodes()

  const visible = useMemo(() => {
    return MOBILE_FORM_MODULES.filter((m) => {
      if (hasPermission('form_data:view') || hasPermission('form_data:create')) return true
      return wfCodes.has(m.templateCode)
    })
  }, [hasPermission, wfCodes])

  const byCode = useMemo(() => {
    const map = new Map(visible.map((m) => [m.templateCode, m]))
    return map
  }, [visible])

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)' }}>
      <div className="flex items-center justify-between mb-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"
        >
          <MobileIcon name="arrow_back_ios" />
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">业务表单</h2>
        <span className="w-6" />
      </div>

      <div className="bg-primary/10 rounded-xl p-3 mb-4 text-sm text-primary/80">
        与 PC 端相同的业务表单模块，支持列表查看、新建与编辑。
      </div>

      {visible.length === 0 && (
        <div className="text-center text-slate-400 text-sm py-12">暂无可用表单模块</div>
      )}

      {GROUPS.map((g) => {
        const items = g.codes.map((c) => byCode.get(c)).filter(Boolean) as typeof visible
        const extras = g.extraLinks || []
        if (!items.length && !extras.length) return null
        return (
          <div key={g.title} className="mb-4">
            <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">{g.title}</div>
            <div className="flex flex-col gap-2">
              {items.map((item) => (
                <button
                  key={item.templateCode}
                  type="button"
                  onClick={() => navigate(`/m/${mobileFormModuleRouteSegment(item.basePath)}`)}
                  className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 bg-white text-left cursor-pointer active:bg-slate-50"
                >
                  <MobileIcon name="description" className="text-primary" style={{ fontSize: 22 }} />
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-slate-900">{item.title}</div>
                  </div>
                  <MobileIcon name="chevron_right" className="text-slate-400" style={{ fontSize: 20 }} />
                </button>
              ))}
              {extras.map((link) => (
                <button
                  key={link.path}
                  type="button"
                  onClick={() => navigate(link.path)}
                  className="flex items-center gap-3 p-4 rounded-xl border border-slate-200 bg-white text-left cursor-pointer active:bg-slate-50"
                >
                  <MobileIcon name="insert_chart" className="text-primary" style={{ fontSize: 22 }} />
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-slate-900">{link.title}</div>
                  </div>
                  <MobileIcon name="chevron_right" className="text-slate-400" style={{ fontSize: 20 }} />
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
