import { lazy, Suspense } from 'react'
import { createBrowserRouter, redirect, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import MainLayout from '@/layouts/MainLayout'
import MobileLayout from '@/layouts/MobileLayout'
import PermissionGuard from '@/components/PermissionGuard'
import { currentZone } from '@/config/zone'

const Login = lazy(() => import('@/pages/auth/Login'))
const Dashboard = lazy(() => import('@/pages/dashboard/Dashboard'))
const CustomerList = lazy(() => import('@/pages/customer/CustomerList'))
const CustomerDetail = lazy(() => import('@/pages/customer/CustomerDetail'))
const CustomerForm = lazy(() => import('@/pages/customer/CustomerForm'))
const CustomerPool = lazy(() => import('@/pages/customer/CustomerPool'))
const ContactList = lazy(() => import('@/pages/customer/ContactList'))
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
const FormTemplateList = lazy(() => import('@/pages/lowcode/FormTemplateList'))
const FormDesignerPage = lazy(() => import('@/pages/lowcode/FormDesignerPage'))
const FormFillPage = lazy(() => import('@/pages/lowcode/FormFillPage'))
const FormDataListPage = lazy(() => import('@/pages/lowcode/FormDataListPage'))
const WorkflowList = lazy(() => import('@/pages/lowcode/WorkflowList'))
const WorkflowDesignerPage = lazy(() => import('@/pages/lowcode/WorkflowCanvasPage'))
const LcApprovalCenter = lazy(() => import('@/pages/lowcode/ApprovalCenter'))
const LcDashboardList = lazy(() => import('@/pages/lowcode/DashboardList'))
const LcDashboardPage = lazy(() => import('@/pages/lowcode/DashboardPage'))
const LcEntityFieldsAdmin = lazy(() => import('@/pages/lowcode/EntityFieldsAdmin'))
const AiCenterPage = lazy(() => import('@/pages/ai/AiCenterPage'))
const KnowledgeBasePage = lazy(() => import('@/pages/ai/KnowledgeBasePage'))
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
const MobileLowcodeForms = lazy(() => import('@/pages/mobile/MobileLowcodeForms'))
const MobileLowcodeFormFill = lazy(() => import('@/pages/mobile/MobileLowcodeFormFill'))
const MobileLowcodeApprovals = lazy(() => import('@/pages/mobile/MobileLowcodeApprovals'))
const MobileLowcodeApprovalDetail = lazy(() => import('@/pages/mobile/MobileLowcodeApprovalDetail'))
const NotificationCenter = lazy(() => import('@/pages/notification/NotificationCenter'))
const PlatformTenants = lazy(() => import('@/pages/platform/PlatformTenants'))
const ProductList = lazy(() => import('@/pages/product/ProductList'))
const OrderList = lazy(() => import('@/pages/order/OrderList'))
const CommissionPage = lazy(() => import('@/pages/commission/CommissionPage'))
const CollectionPage = lazy(() => import('@/pages/collection/CollectionPage'))
const GuaranteePage = lazy(() => import('@/pages/guarantee/GuaranteePage'))
const EquipmentProfilePage = lazy(() => import('@/pages/equipment/EquipmentProfilePage'))
const MeasurementPage = lazy(() => import('@/pages/measurement/MeasurementPage'))
const TenderList = lazy(() => import('@/pages/tender/TenderList'))
const TaskPage = lazy(() => import('@/pages/task/TaskPage'))
const CalendarPage = lazy(() => import('@/pages/calendar/CalendarPage'))
const ApiDocsPage = lazy(() => import('@/pages/admin/ApiDocsPage'))
const OpenApiPage = lazy(() => import('@/pages/admin/openapi/OpenApiPage'))
const SystemHealthPage = lazy(() => import('@/pages/admin/SystemHealthPage'))
const DingTalkPage = lazy(() => import('@/pages/admin/settings/DingTalkPage'))
const DataManagePage = lazy(() => import('@/pages/admin/settings/DataManagePage'))
const ProductReport = lazy(() => import('@/pages/report/ProductReport'))
const CustomerLifecycleReport = lazy(() => import('@/pages/report/CustomerLifecycleReport'))
const TeamPerformanceReport = lazy(() => import('@/pages/report/TeamPerformanceReport'))
const ChangeRequestList = lazy(() => import('@/pages/change/ChangeRequestList'))
const MilestoneList = lazy(() => import('@/pages/delivery/MilestoneList'))
const QuoteList = lazy(() => import('@/pages/quote/QuoteList'))
const ContractList = lazy(() => import('@/pages/contract/ContractList'))
const SolutionList = lazy(() => import('@/pages/solution/SolutionList'))
const DashboardSnapshot = lazy(() => import('@/pages/dashboard/DashboardSnapshot'))
const NotFound = lazy(() => import('@/pages/NotFound'))

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<Spin className="flex justify-center mt-20" />}>{children}</Suspense>
}

function Guard({ permission, children }: { permission: string; children: React.ReactNode }) {
  return <Lazy><PermissionGuard permission={permission}>{children}</PermissionGuard></Lazy>
}

// The mobile domain (link.fourier.net.cn) is the 移动端 — any desktop route under
// "/" bounces to the mobile app so it never renders the desktop chrome on phones.
function webZoneLoader() {
  if (currentZone() === 'mobile') return redirect('/m')
  return null
}

// Root landing: platform domain opens the 平台管理端, everyone else the 工作台.
function ZoneEntry() {
  if (currentZone() === 'platform') return <Navigate to="/platform/tenants" replace />
  return <Lazy><Dashboard /></Lazy>
}

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <Lazy><Login /></Lazy>,
  },
  {
    path: '/',
    element: <MainLayout />,
    loader: webZoneLoader,
    children: [
      { index: true, element: <ZoneEntry /> },
      { path: 'customers', element: <Guard permission="customer:view"><CustomerList /></Guard> },
      { path: 'customers/new', element: <Guard permission="customer:create"><CustomerForm /></Guard> },
      { path: 'customers/:id', element: <Guard permission="customer:view"><CustomerDetail /></Guard> },
      { path: 'customers/:id/edit', element: <Guard permission="customer:edit"><CustomerForm /></Guard> },
      { path: 'customer-pool', element: <Guard permission="customer:view"><CustomerPool /></Guard> },
      { path: 'contacts', element: <Guard permission="contact:view"><ContactList /></Guard> },
      { path: 'leads', element: <Guard permission="lead:view"><LeadList /></Guard> },
      { path: 'leads/new', element: <Guard permission="lead:create"><LeadForm /></Guard> },
      { path: 'leads/:id', element: <Guard permission="lead:view"><LeadDetail /></Guard> },
      { path: 'leads/:id/edit', element: <Guard permission="lead:edit"><LeadForm /></Guard> },
      // 扩展平台 · 表单中心
      { path: 'lowcode/forms', element: <Guard permission="form:view"><FormTemplateList /></Guard> },
      { path: 'lowcode/forms/:id/design', element: <Guard permission="form:manage"><FormDesignerPage /></Guard> },
      { path: 'lowcode/forms/:id/fill', element: <Guard permission="form_data:create"><FormFillPage /></Guard> },
      { path: 'lowcode/forms/:id/data', element: <Guard permission="form_data:view"><FormDataListPage /></Guard> },
      { path: 'lowcode/workflows', element: <Guard permission="workflow:view"><WorkflowList /></Guard> },
      { path: 'lowcode/workflows/:id/design', element: <Guard permission="workflow:manage"><WorkflowDesignerPage /></Guard> },
      { path: 'lowcode/approvals', element: <Lazy><LcApprovalCenter /></Lazy> },
      { path: 'lowcode/dashboards', element: <Guard permission="dashboard:view"><LcDashboardList /></Guard> },
      { path: 'lowcode/dashboards/:id', element: <Guard permission="dashboard:view"><LcDashboardPage /></Guard> },
      { path: 'lowcode/entity-fields', element: <Guard permission="form:manage"><LcEntityFieldsAdmin /></Guard> },
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
      { path: 'commissions', element: <Guard permission="commission:view"><CommissionPage /></Guard> },
      { path: 'collection', element: <Guard permission="collection:view"><CollectionPage /></Guard> },
      { path: 'guarantees', element: <Guard permission="guarantee:view"><GuaranteePage /></Guard> },
      { path: 'equipment-profile', element: <Guard permission="customer:view"><EquipmentProfilePage /></Guard> },
      { path: 'measurements', element: <Guard permission="service:view"><MeasurementPage /></Guard> },
      { path: 'products', element: <Guard permission="product:view"><ProductList /></Guard> },
      { path: 'orders', element: <Guard permission="order:view"><OrderList /></Guard> },
      { path: 'tenders', element: <Guard permission="tender:view"><TenderList /></Guard> },
      { path: 'tasks', element: <Lazy><TaskPage /></Lazy> },
      { path: 'calendar', element: <Lazy><CalendarPage /></Lazy> },
      { path: 'analytics', element: <Guard permission="project:view"><AnalyticsPage /></Guard> },
      { path: 'sales-targets', element: <Guard permission="project:view"><SalesTargetPage /></Guard> },
      { path: 'reports/product', element: <Guard permission="product:view"><ProductReport /></Guard> },
      { path: 'reports/customer-lifecycle', element: <Guard permission="customer:view"><CustomerLifecycleReport /></Guard> },
      { path: 'reports/team-performance', element: <Guard permission="project:view"><TeamPerformanceReport /></Guard> },
      { path: 'solutions', element: <Guard permission="solution:view"><SolutionList /></Guard> },
      { path: 'quotes', element: <Guard permission="quote:view"><QuoteList /></Guard> },
      { path: 'contracts', element: <Guard permission="contract:view"><ContractList /></Guard> },
      { path: 'change-requests', element: <Guard permission="change:view"><ChangeRequestList /></Guard> },
      { path: 'milestones', element: <Guard permission="delivery:view"><MilestoneList /></Guard> },
      { path: 'approvals', element: <Lazy><ApprovalCenter /></Lazy> },
      { path: 'ai-center', element: <Guard permission="project:view"><AiCenterPage /></Guard> },
      { path: 'knowledge-base', element: <Guard permission="project:view"><KnowledgeBasePage /></Guard> },
      { path: 'notifications', element: <Lazy><NotificationCenter /></Lazy> },
      { path: 'profile', element: <Lazy><ProfilePage /></Lazy> },
      { path: 'admin/departments', element: <Guard permission="dept:view"><DepartmentPage /></Guard> },
      { path: 'admin/users', element: <Guard permission="user:view"><UserList /></Guard> },
      { path: 'admin/roles', element: <Guard permission="role:view"><RoleList /></Guard> },
      { path: 'admin/audit', element: <Guard permission="audit:view"><AuditLogPage /></Guard> },
      { path: 'admin/settings', element: <Guard permission="role:manage"><SettingsPage /></Guard> },
      { path: 'platform/tenants', element: <Guard permission="role:manage"><PlatformTenants /></Guard> },
      { path: 'admin/api-docs', element: <Guard permission="role:manage"><ApiDocsPage /></Guard> },
      { path: 'admin/openapi', element: <Guard permission="role:manage"><OpenApiPage /></Guard> },
      { path: 'admin/system-health', element: <Guard permission="role:manage"><SystemHealthPage /></Guard> },
      { path: 'admin/dingtalk', element: <Guard permission="role:manage"><DingTalkPage /></Guard> },
      { path: 'admin/data-manage', element: <Guard permission="role:manage"><DataManagePage /></Guard> },
      { path: 'dashboard/shared/:token', element: <Lazy><DashboardSnapshot /></Lazy> },
      { path: '*', element: <Lazy><NotFound /></Lazy> },
    ],
  },
  {
    path: '/m',
    element: <MobileLayout />,
    children: [
      // 移动端每条路由的权限与上面对应的桌面端路由保持一致；桌面端未设卡口的
      // (工作台/审批/通知/日历/任务/我的/搜索) 这里同样不设，避免两端行为分叉。
      { index: true, element: <Lazy><MobileWorkbench /></Lazy> },
      { path: 'customers', element: <Guard permission="customer:view"><MobileCustomers /></Guard> },
      { path: 'opportunities', element: <Guard permission="project:view"><MobileOpportunities /></Guard> },
      { path: 'opportunities/new', element: <Guard permission="project:create"><MobileOpportunityForm /></Guard> },
      { path: 'opportunities/:id', element: <Guard permission="project:view"><MobileOpportunityDetail /></Guard> },
      { path: 'opportunities/:id/quotes/:qid', element: <Guard permission="quote:view"><MobileQuoteDetail /></Guard> },
      { path: 'opportunities/:id/risk', element: <Guard permission="project:view"><MobileProjectRisk /></Guard> },
      { path: 'approvals', element: <Lazy><MobileApprovals /></Lazy> },
      { path: 'approvals/:id', element: <Lazy><MobileApprovalDetail /></Lazy> },
      { path: 'customers/:id', element: <Guard permission="customer:view"><MobileCustomerDetail /></Guard> },
      { path: 'customers/new', element: <Guard permission="customer:create"><MobileCustomerForm /></Guard> },
      { path: 'contracts', element: <Guard permission="contract:view"><MobileContracts /></Guard> },
      { path: 'payments', element: <Guard permission="payment:view"><MobilePayments /></Guard> },
      { path: 'service-tickets', element: <Guard permission="service:view"><MobileServiceTickets /></Guard> },
      { path: 'service-tickets/:id', element: <Guard permission="service:view"><MobileServiceTicketDetail /></Guard> },
      { path: 'notifications', element: <Lazy><MobileNotifications /></Lazy> },
      { path: 'calendar', element: <Lazy><MobileCalendar /></Lazy> },
      { path: 'leads', element: <Guard permission="lead:view"><MobileLeads /></Guard> },
      { path: 'leads/new', element: <Guard permission="lead:create"><MobileLeadForm /></Guard> },
      { path: 'leads/:id', element: <Guard permission="lead:view"><MobileLeadDetail /></Guard> },
      { path: 'tasks', element: <Lazy><MobileTasks /></Lazy> },
      // 桌面端 follow-ups 用 customer:view
      { path: 'follow-up/new', element: <Guard permission="customer:view"><MobileFollowUp /></Guard> },
      // 桌面端 analytics / opportunities/kanban 均用 project:view
      { path: 'reports', element: <Guard permission="project:view"><MobileReports /></Guard> },
      { path: 'kanban', element: <Guard permission="project:view"><MobileKanban /></Guard> },
      { path: 'products', element: <Guard permission="product:view"><MobileProducts /></Guard> },
      { path: 'search', element: <Lazy><MobileSearch /></Lazy> },
      { path: 'profile', element: <Lazy><MobileProfile /></Lazy> },
      { path: 'lowcode/forms', element: <Guard permission="form:view"><MobileLowcodeForms /></Guard> },
      { path: 'lowcode/forms/:id/fill', element: <Guard permission="form_data:create"><MobileLowcodeFormFill /></Guard> },
      { path: 'lowcode/approvals', element: <Lazy><MobileLowcodeApprovals /></Lazy> },
      { path: 'lowcode/approvals/:id', element: <Lazy><MobileLowcodeApprovalDetail /></Lazy> },
    ],
  },
  { path: '*', element: <Lazy><NotFound /></Lazy> },
])
