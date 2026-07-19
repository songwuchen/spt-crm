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
import { useUiSettingsStore } from '@/stores/useUiSettingsStore'
import { authApi } from '@/api/auth'

import Icon from '@/components/Icon'
const { Sider, Content } = Layout

const breadcrumbNameMap: Record<string, string> = {
  '/': '工作台',
  '/customers': '客户管理',
  '/customers/new': '新建客户',
  '/leads': '线索管理',
  '/leads/new': '新建线索',
  '/opportunities': '商机管理',
  '/opportunities/new': '新建商机',
  '/opportunities/kanban': '看板视图',
  '/products': '产品目录',
  '/service-tickets': '售后工单',
  '/analytics': '数据分析',
  '/ai-center': 'AI 中心',
  '/approvals': '审批中心',
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
        items.push({ title: <span className="text-slate-700 font-semibold">详情</span> })
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
    }).catch(() => {
      logout()
      loginWithRedirect()
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
      else if (path.startsWith('/opportunities')) navigate('/opportunities/new')
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
