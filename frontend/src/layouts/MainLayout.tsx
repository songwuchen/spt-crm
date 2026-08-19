import { useEffect, useMemo } from 'react'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { Layout, Breadcrumb, Spin } from 'antd'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import { useHotkeys } from '@/hooks/useHotkeys'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ErrorBoundary from '@/components/ErrorBoundary'
import OnboardingTour from '@/components/OnboardingTour'
import CommandPalette from '@/components/CommandPalette'
import ContextualHelp from '@/components/ContextualHelp'
import FloatingAssistant from '@/components/ai/FloatingAssistant'
import MustChangePasswordBanner from '@/components/MustChangePasswordBanner'
import { useAppStore } from '@/stores/useAppStore'
import { useAuthStore } from '@/stores/useAuthStore'
import { canDirectCreateOpportunity } from '@/utils/opportunityCreate'
import { useUiSettingsStore } from '@/stores/useUiSettingsStore'
import { authApi } from '@/api/auth'

import Icon from '@/components/Icon'
const { Sider, Content } = Layout

const breadcrumbNameMap: Record<string, string> = {
  '/': '工作台',
  '/customers': '客户管理',
  '/customers/new': '新建客户',
  '/leads': '线索管理',
  '/lead-reactivations': '180天项目激活',
  '/leads/new': '新建线索',
  '/opportunities': '商机管理',
  '/opportunities/new': '新建商机',
  '/opportunities/kanban': '看板视图',
  '/contracts': '合同管理',
  '/application-fields': '应用领域',
  '/application-fields/fill': '新增',
  '/application-materials': '应用物料',
  '/application-materials/fill': '新增',
  '/material-names': '物料名称',
  '/material-names/fill': '新增',
  '/department-codes': '部门编号',
  '/department-codes/fill': '新增',
  '/salesperson-region-map': '业务员区域经理',
  '/salesperson-region-map/fill': '新增',
  '/contract-reviews': '合同评审',
  '/contract-reviews/new': '新建合同评审',
  '/tech-agreement-reviews': '技术协议评审',
  '/tech-agreement-reviews/fill': '新增',
  '/tech-agreement-reviews/new': '新增',
  '/prod-card-supplements': '生产卡/补充流程',
  '/prod-card-supplements/fill': '新增',
  '/invoice-applications': '开票申请',
  '/invoice-applications/fill': '新增',
  '/payment-registrations': '收款登记',
  '/payment-registrations/fill': '新增',
  '/solutions': '方案管理',
  '/solutions/fill': '新增',
  '/drawing-requisitions': '合同图纸领用',
  '/drawing-requisitions/fill': '新增',
  '/install-drawing-notices': '安装图设计通知',
  '/install-drawing-notices/fill': '新增',
  '/contract-drawing-maps': '合同图纸对应表',
  '/contract-drawing-maps/fill': '新增',
  '/products': '产品目录',
  '/service-tickets': '售后工单',
  '/cs-service-requests': '客户服务申请及反馈',
  '/cs-service-requests/fill': '新增',
  '/cs-product-replaces': '售出产品更换（补发）',
  '/cs-product-replaces/fill': '新增',
  '/cs-product-returns': '售出产品/工具退回',
  '/cs-product-returns/fill': '新增',
  '/cs-loan-slips': '客服借据',
  '/cs-loan-slips/fill': '新增',
  '/cs-drawing-requests': '客服领图',
  '/cs-drawing-requests/fill': '新增',
  '/cs-service-delays': '客户服务延期申请',
  '/cs-service-delays/fill': '新增',
  '/cs-correspondences': '客服往来函件',
  '/cs-correspondences/fill': '新增',
  '/analytics': '数据分析',
  '/ai-center': 'AI 中心',
  '/approvals': '审批中心',
  '/notifications': '通知中心',
  '/profile': '个人设置',
  '/admin/departments': '部门管理',
  '/admin/users': '用户管理',
  '/admin/roles': '角色管理',
  '/admin/audit': '操作日志',
  '/admin/settings': '系统设置',
  '/admin/api-docs': 'API 文档',
  '/admin/system-health': '系统健康',
}

function getBreadcrumbs(pathname: string) {
  const parts = pathname.split('/').filter(Boolean)
  const items: { title: React.ReactNode }[] = [
    { title: <Link to="/" className="text-slate-400 hover:text-primary">首页</Link> },
  ]

  let currentPath = ''
  for (let i = 0; i < parts.length; i++) {
    currentPath += '/' + parts[i]
    const name = breadcrumbNameMap[currentPath]
    if (name) {
      const isLast = i === parts.length - 1
      items.push({
        title: isLast
          ? <span className="text-slate-700 font-semibold">{name}</span>
          : <Link to={currentPath} className="text-slate-400 hover:text-primary">{name}</Link>,
      })
    } else if (parts[i] !== 'admin') {
      if (parts[i] === 'edit') {
        items.push({ title: <span className="text-slate-700 font-semibold">编辑</span> })
      } else if (parts[i] === 'quotes') {
        items.push({ title: <span className="text-slate-700 font-semibold">报价详情</span> })
        break
      } else if (parts[i] === 'contracts') {
        items.push({ title: <span className="text-slate-700 font-semibold">合同详情</span> })
        break
      } else if (parts[i] === 'solutions') {
        items.push({ title: <span className="text-slate-700 font-semibold">方案详情</span> })
        break
      } else if (breadcrumbNameMap['/' + parts.slice(0, i).join('/')]) {
        // 合同管理下的 /contracts/:id →「合同详情」；商机下的 uuid 段仍为「详情」
        const parentPath = '/' + parts.slice(0, i).join('/')
        const label = parentPath === '/contracts' ? '合同详情' : '详情'
        items.push({ title: <span className="text-slate-700 font-semibold">{label}</span> })
      }
    }
  }
  return items
}

export default function MainLayout() {
  const { sidebarCollapsed, setSidebarCollapsed } = useAppStore()
  const { token, setUser, setUserLoading, userLoading } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  // Auto-collapse sidebar on window resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarCollapsed(true)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [setSidebarCollapsed])

  // Auto-collapse sidebar on mobile navigation
  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarCollapsed(true)
    }
  }, [location.pathname, setSidebarCollapsed])

  const logout = useAuthStore((s) => s.logout)
  const loadUiSettings = useUiSettingsStore((s) => s.load)

  useEffect(() => {
    // 未登录跳登录时保留目标路径（如钉钉待办深链 /approvals），登录后回跳而非落到首页
    const loginWithRedirect = () => {
      const target = location.pathname + location.search
      const q = target && target !== '/' ? '?redirect=' + encodeURIComponent(target) : ''
      navigate('/login' + q, { replace: true })
    }
    if (!token) {
      setUserLoading(false)
      loginWithRedirect()
      return
    }
    setUserLoading(true)
    authApi.me().then((res) => {
      if (res.data) setUser(res.data)
    }).catch((err: unknown) => {
      // StrictMode / 路由切换会取消 in-flight 请求；取消不是鉴权失败，不能清会话
      const ax = err as { code?: string; name?: string; response?: { status?: number } }
      const canceled =
        ax.code === 'ERR_CANCELED'
        || ax.name === 'CanceledError'
        || ax.name === 'AbortError'
      if (canceled) {
        setUserLoading(false)
        return
      }
      // 无 HTTP 响应 = 网络/证书/Service Worker 干扰，保留登录态，避免「登录成功立刻退出」
      if (!ax.response) {
        setUserLoading(false)
        return
      }
      if (ax.response.status === 401) {
        logout()
        loginWithRedirect()
        return
      }
      setUserLoading(false)
    })
    // 拉取界面个性化设置（系统显示名 / 菜单别名 / 隐藏）
    loadUiSettings()
  }, [token])

  // Global keyboard shortcuts
  const hotkeys = useMemo(() => ({
    // ctrl+k is handled by CommandPalette
    'ctrl+n': () => {
      const path = location.pathname
      if (path.startsWith('/customers')) navigate('/customers/new')
      else if (path.startsWith('/leads')) navigate('/leads/new')
      else if (path.startsWith('/opportunities') && canDirectCreateOpportunity(useAuthStore.getState().user)) {
        navigate('/opportunities/new')
      }
    },
    'escape': () => window.dispatchEvent(new CustomEvent('close-modal')),
  }), [location.pathname, navigate])
  useHotkeys(hotkeys)

  const online = useOnlineStatus()
  const breadcrumbItems = getBreadcrumbs(location.pathname)
  const isHome = location.pathname === '/'
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768

  return (
    <Layout className="h-screen">
      {/* Mobile overlay when sidebar is open */}
      {isMobile && !sidebarCollapsed && (
        <div
          className="fixed inset-0 bg-black/30 z-20"
          onClick={() => setSidebarCollapsed(true)}
        />
      )}
      <Sider
        trigger={null}
        collapsible
        collapsed={sidebarCollapsed}
        width={240}
        collapsedWidth={0}
        className={`!bg-white dark:!bg-slate-950 ${isMobile && !sidebarCollapsed ? 'fixed left-0 top-0 bottom-0 z-30' : ''}`}
        style={{ overflow: 'hidden', height: '100vh' }}
      >
        <div data-tour="sidebar" style={{ height: '100%' }}><Sidebar /></div>
      </Sider>
      <Layout className="bg-bg-light dark:!bg-slate-900" style={{ height: '100vh', overflow: 'hidden' }}>
        {!online && (
          <div className="bg-amber-500 text-white text-sm font-bold text-center py-1 px-2 flex items-center justify-center gap-1">
            <Icon name="cloud_off" style={{ fontSize: 14 }} />
            网络已断开 — 部分功能可能不可用
          </div>
        )}
        <Header />
        <MustChangePasswordBanner profilePath="/profile" />
        <Content className="overflow-auto" style={{ flex: 1, minHeight: 0 }}>
          <div className="p-3 sm:p-4 md:p-6">
            {!isHome && breadcrumbItems.length > 1 && (
              <Breadcrumb items={breadcrumbItems} className="mb-4" />
            )}
            {userLoading ? (
              <div className="flex justify-center items-center h-64">
                <Spin size="large" />
              </div>
            ) : (
              <ErrorBoundary>
                <Outlet />
              </ErrorBoundary>
            )}
          </div>
        </Content>
      </Layout>
      <OnboardingTour />
      <CommandPalette />
      <ContextualHelp />
      <FloatingAssistant />
    </Layout>
  )
}
