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
const CustomerPool = lazy(() => import('@/pages/customer/CustomerPool'))
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
const FollowUpPage = lazy(() => import('@/pages/activity/FollowUpPage'))
const PaymentPage = lazy(() => import('@/pages/payment/PaymentPage'))
const DepartmentPage = lazy(() => import('@/pages/admin/department/DepartmentPage'))
const UserList = lazy(() => import('@/pages/admin/user/UserList'))
const RoleList = lazy(() => import('@/pages/admin/role/RoleList'))
const AuditLogPage = lazy(() => import('@/pages/admin/audit/AuditLogPage'))
const SettingsPage = lazy(() => import('@/pages/admin/settings/SettingsPage'))
const AnalyticsPage = lazy(() => import('@/pages/analytics/AnalyticsPage'))
const SalesTargetPage = lazy(() => import('@/pages/analytics/SalesTargetPage'))
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
const MobileCustomerForm = lazy(() => import('@/pages/mobile/MobileCustomerForm'))
const MobileLeadDetail = lazy(() => import('@/pages/mobile/MobileLeadDetail'))
const MobileTasks = lazy(() => import('@/pages/mobile/MobileTasks'))
const MobileOpportunityDetail = lazy(() => import('@/pages/mobile/MobileOpportunityDetail'))
const MobileCustomerDetail = lazy(() => import('@/pages/mobile/MobileCustomerDetail'))
const MobileContracts = lazy(() => import('@/pages/mobile/MobileContracts'))
const MobilePayments = lazy(() => import('@/pages/mobile/MobilePayments'))
const MobileServiceTicketDetail = lazy(() => import('@/pages/mobile/MobileServiceTicketDetail'))
const MobileCalendar = lazy(() => import('@/pages/mobile/MobileCalendar'))
const MobileServiceTickets = lazy(() => import('@/pages/mobile/MobileServiceTickets'))
const MobileNotifications = lazy(() => import('@/pages/mobile/MobileNotifications'))
const MobileLeadForm = lazy(() => import('@/pages/mobile/MobileLeadForm'))
const MobileOpportunityForm = lazy(() => import('@/pages/mobile/MobileOpportunityForm'))
const MobileQuoteDetail = lazy(() => import('@/pages/mobile/MobileQuoteDetail'))
const MobileReports = lazy(() => import('@/pages/mobile/MobileReports'))
const MobileKanban = lazy(() => import('@/pages/mobile/MobileKanban'))
const MobileProducts = lazy(() => import('@/pages/mobile/MobileProducts'))
const MobileSearch = lazy(() => import('@/pages/mobile/MobileSearch'))
const MobileLeads = lazy(() => import('@/pages/mobile/MobileLeads'))
const NotificationCenter = lazy(() => import('@/pages/notification/NotificationCenter'))
const PlatformTenants = lazy(() => import('@/pages/platform/PlatformTenants'))
const ProductList = lazy(() => import('@/pages/product/ProductList'))
const TaskPage = lazy(() => import('@/pages/task/TaskPage'))
const CalendarPage = lazy(() => import('@/pages/calendar/CalendarPage'))
const ApiDocsPage = lazy(() => import('@/pages/admin/ApiDocsPage'))
const ProductReport = lazy(() => import('@/pages/report/ProductReport'))
const CustomerLifecycleReport = lazy(() => import('@/pages/report/CustomerLifecycleReport'))
const TeamPerformanceReport = lazy(() => import('@/pages/report/TeamPerformanceReport'))
const ChangeRequestList = lazy(() => import('@/pages/change/ChangeRequestList'))
const MilestoneList = lazy(() => import('@/pages/delivery/MilestoneList'))
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
      { path: 'customer-pool', element: <Guard permission="customer:view"><CustomerPool /></Guard> },
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
      { path: 'follow-ups', element: <Guard permission="customer:view"><FollowUpPage /></Guard> },
      { path: 'payments', element: <Guard permission="payment:view"><PaymentPage /></Guard> },
      { path: 'products', element: <Guard permission="product:view"><ProductList /></Guard> },
      { path: 'tasks', element: <Lazy><TaskPage /></Lazy> },
      { path: 'calendar', element: <Lazy><CalendarPage /></Lazy> },
      { path: 'analytics', element: <Guard permission="project:view"><AnalyticsPage /></Guard> },
      { path: 'sales-targets', element: <Guard permission="project:view"><SalesTargetPage /></Guard> },
      { path: 'reports/product', element: <Guard permission="product:view"><ProductReport /></Guard> },
      { path: 'reports/customer-lifecycle', element: <Guard permission="customer:view"><CustomerLifecycleReport /></Guard> },
      { path: 'reports/team-performance', element: <Guard permission="project:view"><TeamPerformanceReport /></Guard> },
      { path: 'change-requests', element: <Guard permission="change:view"><ChangeRequestList /></Guard> },
      { path: 'milestones', element: <Guard permission="delivery:view"><MilestoneList /></Guard> },
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
      { path: 'admin/api-docs', element: <Guard permission="role:manage"><ApiDocsPage /></Guard> },
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
      { path: 'opportunities/new', element: <Lazy><MobileOpportunityForm /></Lazy> },
      { path: 'opportunities/:id', element: <Lazy><MobileOpportunityDetail /></Lazy> },
      { path: 'opportunities/:id/quotes/:qid', element: <Lazy><MobileQuoteDetail /></Lazy> },
      { path: 'opportunities/:id/risk', element: <Lazy><MobileProjectRisk /></Lazy> },
      { path: 'approvals', element: <Lazy><MobileApprovals /></Lazy> },
      { path: 'approvals/:id', element: <Lazy><MobileApprovalDetail /></Lazy> },
      { path: 'customers/:id', element: <Lazy><MobileCustomerDetail /></Lazy> },
      { path: 'customers/new', element: <Lazy><MobileCustomerForm /></Lazy> },
      { path: 'contracts', element: <Lazy><MobileContracts /></Lazy> },
      { path: 'payments', element: <Lazy><MobilePayments /></Lazy> },
      { path: 'service-tickets', element: <Lazy><MobileServiceTickets /></Lazy> },
      { path: 'service-tickets/:id', element: <Lazy><MobileServiceTicketDetail /></Lazy> },
      { path: 'notifications', element: <Lazy><MobileNotifications /></Lazy> },
      { path: 'calendar', element: <Lazy><MobileCalendar /></Lazy> },
      { path: 'leads', element: <Lazy><MobileLeads /></Lazy> },
      { path: 'leads/new', element: <Lazy><MobileLeadForm /></Lazy> },
      { path: 'leads/:id', element: <Lazy><MobileLeadDetail /></Lazy> },
      { path: 'tasks', element: <Lazy><MobileTasks /></Lazy> },
      { path: 'follow-up/new', element: <Lazy><MobileFollowUp /></Lazy> },
      { path: 'reports', element: <Lazy><MobileReports /></Lazy> },
      { path: 'kanban', element: <Lazy><MobileKanban /></Lazy> },
      { path: 'products', element: <Lazy><MobileProducts /></Lazy> },
      { path: 'search', element: <Lazy><MobileSearch /></Lazy> },
      { path: 'profile', element: <Lazy><MobileProfile /></Lazy> },
    ],
  },
  { path: '*', element: <Lazy><NotFound /></Lazy> },
])
