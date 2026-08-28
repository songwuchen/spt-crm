import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { menuGroups, flattenMenuItems, type MenuItem } from '@/config/menus'
import { toZonePath } from '@/utils/zonePaths'

function canSeeItem(item: MenuItem, hasPermission: (p: string) => boolean): boolean {
  if (!item.permission) return true
  const perms = Array.isArray(item.permission) ? item.permission : [item.permission]
  return perms.some((p) => hasPermission(p))
}

export default function MobileMorePage() {
  usePageTitle('全部功能')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)

  const sections = useMemo(() => {
    return menuGroups.map((g) => {
      const items = flattenMenuItems([g]).filter((item) => {
        if (item.key.startsWith('submenu:')) return false
        if (item.key === '/') return false
        if (item.key.startsWith('/admin') || item.key.startsWith('/platform')) return false
        if (item.key.startsWith('/lowcode/forms') && item.key.includes('design')) return false
        return canSeeItem(item, hasPermission)
      })
      return { title: g.titleKey, items }
    }).filter((s) => s.items.length > 0)
  }, [hasPermission])

  const titleMap: Record<string, string> = {
    'nav.groupInbox': '收件箱',
    'nav.groupClients': '客户',
    'nav.groupDeals': '交易',
    'nav.groupFulfillment': '履约',
    'nav.groupService': '服务',
    'nav.groupOps': '运营',
    'nav.groupAdmin': '管理',
  }

  const labelMap: Record<string, string> = {
    'nav.approvals': '审批中心',
    'nav.notifications': '消息通知',
    'nav.customers': '客户列表',
    'nav.customerPool': '公海客户',
    'nav.contacts': '联系人',
    'nav.leads': '线索',
    'nav.leadReactivations': '180天激活',
    'nav.opportunities': '商机',
    'nav.drawingRequisitions': '合同图纸领用',
    'nav.installDrawingNotices': '安装图设计通知',
    'nav.presaleServiceNotices': '售前服务通知',
    'nav.quotes': '报价管理',
    'nav.pricingChecklists': '核价清单传递',
    'nav.researchCoopCards': '中央研究院协同卡',
    'nav.techAgreementFeedbacks': '技术协议反馈单',
    'nav.contractReviews': '合同评审',
    'nav.xunhanContractReviews': '迅焊合同评审',
    'nav.techAgreementReviews': '技术协议评审',
    'nav.contractDrawingMaps': '合同图纸对应表',
    'nav.prodCardSupplements': '生产卡/补充流程',
    'nav.invoiceApplications': '开票申请',
    'nav.shipmentNotices': '发货通知',
    'nav.paymentRegistrations': '收款登记',
    'nav.contractShipmentLoans': '合同及发货借据流程',
    'nav.shipmentLoanDashboard': '发货借据',
    'nav.contracts': '合同',
    'nav.orders': '订单',
    'nav.products': '产品',
    'nav.serviceTickets': '售后工单',
    'nav.followUps': '跟进记录',
    'nav.payments': '回款',
    'nav.tasks': '待办任务',
    'nav.calendar': '日历',
    'nav.analytics': '数据分析',
    'nav.aiCenter': 'AI 中心',
  }

  const open = (pcPath: string) => {
    navigate(toZonePath(pcPath))
  }

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)' }}>
      <h2 className="text-lg font-bold text-slate-900 mb-4">全部功能</h2>
      <div className="space-y-4">
        {sections.map((sec) => (
          <div key={sec.title}>
            <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">
              {titleMap[sec.title] || sec.title}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {sec.items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => open(item.key)}
                  className="flex items-center gap-2 p-3 rounded-xl border border-slate-200 bg-white text-left cursor-pointer active:bg-slate-50"
                >
                  <MobileIcon name={item.icon} className="text-primary shrink-0" style={{ fontSize: 20 }} />
                  <span className="text-sm font-bold text-slate-800 truncate">
                    {labelMap[item.labelKey] || item.labelKey}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() => navigate('/m/form-modules')}
          className="w-full flex items-center gap-2 p-3 rounded-xl border border-primary/30 bg-primary/5 text-left cursor-pointer"
        >
          <MobileIcon name="grid_view" className="text-primary" style={{ fontSize: 22 }} />
          <span className="text-sm font-bold text-primary">业务表单中心</span>
        </button>
      </div>
    </div>
  )
}
