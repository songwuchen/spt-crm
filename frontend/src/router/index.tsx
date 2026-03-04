import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import MobileLayout from '@/layouts/MobileLayout'
import PermissionGuard from '@/components/PermissionGuard'

const Login = lazy(() => import('@/pages/auth/Login'))
const Dashboard = lazy(() => import('@/pages/dashboard/Dashboard'))
const CustomerList = lazy(() => import('@/pages/customer/CustomerList'))
const CustomerDetail = lazy(() => import('@/pages/customer/CustomerDetail'))
const CustomerForm = lazy(() => import('@/pages/customer/CustomerForm'))
const LeadList = lazy(() => import('@/pages/lead/LeadList'))
const LeadDetail = lazy(() => import('@/pages/lead/LeadDetail'))
const LeadForm = lazy(() => import('@/pages/lead/LeadForm'))
const OpportunityList = lazy(() => import('@/pages/opportunity/OpportunityList'))
const OpportunityDetail = lazy(() => import('@/pages/opportunity/OpportunityDetail'))
const OpportunityForm = lazy(() => import('@/pages/opportunity/OpportunityForm'))
const QuoteDetail = lazy(() => import('@/pages/opportunity/QuoteDetail'))
const ContractDetail = lazy(() => import('@/pages/opportunity/ContractDetail'))
const SolutionDetail = lazy(() => import('@/pages/opportunity/SolutionDetail'))
const KanbanBoard = lazy(() => import('@/pages/opportunity/KanbanBoard'))
const ServiceTicketList = lazy(() => import('@/pages/service/ServiceTicketList'))
const ServiceTicketDetail = lazy(() => import('@/pages/service/ServiceTicketDetail'))
const RenewalList = lazy(() => import('@/pages/service/RenewalList'))
const DepartmentPage = lazy(() => import('@/pages/admin/department/DepartmentPage'))
const UserList = lazy(() => import('@/pages/admin/user/UserList'))
const RoleList = lazy(() => import('@/pages/admin/role/RoleList'))
const AuditLogPage = lazy(() => import('@/pages/admin/audit/AuditLogPage'))
const SettingsPage = lazy(() => import('@/pages/admin/settings/SettingsPage'))
const AnalyticsPage = lazy(() => import('@/pages/analytics/AnalyticsPage'))
const ApprovalCenter = lazy(() => import('@/pages/approval/ApprovalCenter'))
const AiCenterPage = lazy(() => import('@/pages/ai/AiCenterPage'))
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage'))
const MobileWorkbench = lazy(() => import('@/pages/mobile/MobileWorkbench'))
const MobileCustomers = lazy(() => import('@/pages/mobile/MobileCustomers'))
const MobileOpportunities = lazy(() => import('@/pages/mobile/MobileOpportunities'))
const MobileProfile = lazy(() => import('@/pages/mobile/MobileProfile'))
const MobileApprovals = lazy(() => import('@/pages/mobile/MobileApprovals'))
const MobileApprovalDetail = lazy(() => import('@/pages/mobile/MobileApprovalDetail'))
const MobileFollowUp = lazy(() => import('@/pages/mobile/MobileFollowUp'))
const MobileProjectRisk = lazy(() => import('@/pages/mobile/MobileProjectRisk'))
const NotificationCenter = lazy(() => import('@/pages/notification/NotificationCenter'))
const PlatformTenants = lazy(() => import('@/pages/platform/PlatformTenants'))
const NotFound = lazy(() => import('@/pages/NotFound'))

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<Spin className="flex justify-center mt-20" />}>{children}</Suspense>
}

function Guard({ permission, children }: { permission: string; children: React.ReactNode }) {
  return <Lazy><PermissionGuard permission={permission}>{children}</PermissionGuard></Lazy>
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <Lazy><Login /></Lazy>,
  },
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Lazy><Dashboard /></Lazy> },
      { path: 'customers', element: <Guard permission="customer:view"><CustomerList /></Guard> },
      { path: 'customers/new', element: <Guard permission="customer:create"><CustomerForm /></Guard> },
      { path: 'customers/:id', element: <Guard permission="customer:view"><CustomerDetail /></Guard> },
      { path: 'customers/:id/edit', element: <Guard permission="customer:edit"><CustomerForm /></Guard> },
      { path: 'leads', element: <Guard permission="lead:view"><LeadList /></Guard> },
      { path: 'leads/new', element: <Guard permission="lead:create"><LeadForm /></Guard> },
      { path: 'leads/:id', element: <Guard permission="lead:view"><LeadDetail /></Guard> },
      { path: 'leads/:id/edit', element: <Guard permission="lead:edit"><LeadForm /></Guard> },
      { path: 'opportunities', element: <Guard permission="project:view"><OpportunityList /></Guard> },
      { path: 'opportunities/kanban', element: <Guard permission="project:view"><KanbanBoard /></Guard> },
      { path: 'opportunities/new', element: <Guard permission="project:create"><OpportunityForm /></Guard> },
      { path: 'opportunities/:id', element: <Guard permission="project:view"><OpportunityDetail /></Guard> },
      { path: 'opportunities/:id/edit', element: <Guard permission="project:edit"><OpportunityForm /></Guard> },
      { path: 'opportunities/:id/quotes/:qid', element: <Guard permission="quote:view"><QuoteDetail /></Guard> },
      { path: 'opportunities/:id/contracts/:cid', element: <Guard permission="contract:view"><ContractDetail /></Guard> },
      { path: 'opportunities/:id/solutions/:sid', element: <Guard permission="solution:view"><SolutionDetail /></Guard> },
      { path: 'service-tickets', element: <Guard permission="service:view"><ServiceTicketList /></Guard> },
      { path: 'service-tickets/:id', element: <Guard permission="service:view"><ServiceTicketDetail /></Guard> },
      { path: 'renewals', element: <Guard permission="service:view"><RenewalList /></Guard> },
      { path: 'analytics', element: <Guard permission="project:view"><AnalyticsPage /></Guard> },
      { path: 'approvals', element: <Lazy><ApprovalCenter /></Lazy> },
      { path: 'ai-center', element: <Guard permission="project:view"><AiCenterPage /></Guard> },
      { path: 'notifications', element: <Lazy><NotificationCenter /></Lazy> },
      { path: 'profile', element: <Lazy><ProfilePage /></Lazy> },
      { path: 'admin/departments', element: <Guard permission="dept:view"><DepartmentPage /></Guard> },
      { path: 'admin/users', element: <Guard permission="user:view"><UserList /></Guard> },
      { path: 'admin/roles', element: <Guard permission="role:view"><RoleList /></Guard> },
      { path: 'admin/audit', element: <Guard permission="audit:view"><AuditLogPage /></Guard> },
      { path: 'admin/settings', element: <Guard permission="role:manage"><SettingsPage /></Guard> },
      { path: 'platform/tenants', element: <Guard permission="role:manage"><PlatformTenants /></Guard> },
      { path: '*', element: <Lazy><NotFound /></Lazy> },
    ],
  },
  {
    path: '/m',
    element: <MobileLayout />,
    children: [
      { index: true, element: <Lazy><MobileWorkbench /></Lazy> },
      { path: 'customers', element: <Lazy><MobileCustomers /></Lazy> },
      { path: 'opportunities', element: <Lazy><MobileOpportunities /></Lazy> },
      { path: 'opportunities/:id/risk', element: <Lazy><MobileProjectRisk /></Lazy> },
      { path: 'approvals', element: <Lazy><MobileApprovals /></Lazy> },
      { path: 'approvals/:id', element: <Lazy><MobileApprovalDetail /></Lazy> },
      { path: 'follow-up/new', element: <Lazy><MobileFollowUp /></Lazy> },
      { path: 'profile', element: <Lazy><MobileProfile /></Lazy> },
    ],
  },
  { path: '*', element: <Lazy><NotFound /></Lazy> },
])
