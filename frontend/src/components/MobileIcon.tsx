import React from 'react'
import {
  ArrowLeftOutlined, LeftOutlined, RightOutlined, DownOutlined, UpOutlined,
  ArrowUpOutlined, ArrowDownOutlined, CloseOutlined, SearchOutlined, FilterOutlined,
  PlusOutlined, MinusOutlined, EditOutlined, CameraOutlined, SwapOutlined, LinkOutlined,
  AudioOutlined, CheckCircleOutlined, CheckOutlined, WarningOutlined, ExclamationCircleOutlined,
  InfoCircleOutlined, ClockCircleOutlined, PauseCircleOutlined, LoadingOutlined, CloudOutlined,
  ReloadOutlined, CloseCircleOutlined, FieldTimeOutlined,
  DisconnectOutlined, FlagOutlined, LockOutlined, UserOutlined, TeamOutlined, PhoneOutlined,
  BankOutlined, ShopOutlined, SolutionOutlined, FileTextOutlined, ProfileOutlined,
  UnorderedListOutlined, IdcardOutlined, TagOutlined, InboxOutlined, AppstoreOutlined,
  PayCircleOutlined, DashboardOutlined, LineChartOutlined, BarChartOutlined, RiseOutlined,
  BellOutlined, CalendarOutlined, CustomerServiceOutlined, BulbOutlined, RobotOutlined,
  ThunderboltOutlined, RocketOutlined, StarOutlined,
  SafetyCertificateOutlined, UserAddOutlined, MailOutlined,
} from '@ant-design/icons'

// 移动端图标：钉钉手机 webview 渲染不了 Material Symbols 字体，故移动端一律用 antd 的内联 SVG
// 图标（打包进 JS、不依赖字体/网络，任何 webview 都能显示）。name 仍沿用 Material Symbols 名，
// 以便与桌面端图标语义保持一致、且各页面的图标映射表无需改动。
const MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  // 导航 / 动作
  arrow_back: ArrowLeftOutlined, arrow_back_ios: ArrowLeftOutlined,
  chevron_left: LeftOutlined, chevron_right: RightOutlined,
  expand_more: DownOutlined, expand_less: UpOutlined,
  arrow_upward: ArrowUpOutlined, arrow_downward: ArrowDownOutlined,
  close: CloseOutlined, search: SearchOutlined, filter_alt: FilterOutlined,
  add: PlusOutlined, add_business: ShopOutlined, add_a_photo: CameraOutlined,
  remove: MinusOutlined, edit: EditOutlined, edit_note: EditOutlined,
  swap_horiz: SwapOutlined, link: LinkOutlined, mic: AudioOutlined,
  // 状态 / 指示
  check: CheckOutlined, task_alt: CheckCircleOutlined, check_circle: CheckCircleOutlined,
  approved: CheckCircleOutlined, warning: WarningOutlined, report_problem: WarningOutlined,
  priority_high: ExclamationCircleOutlined, info: InfoCircleOutlined,
  schedule: ClockCircleOutlined, pending_actions: ClockCircleOutlined,
  pause_circle: PauseCircleOutlined, progress_activity: LoadingOutlined,
  cloud_off: DisconnectOutlined, cloud_done: CloudOutlined, flag: FlagOutlined, lock: LockOutlined,
  refresh: ReloadOutlined, sync: ReloadOutlined, hourglass_top: FieldTimeOutlined,
  hourglass_empty: FieldTimeOutlined, gpp_bad: CloseCircleOutlined, cancel: CloseCircleOutlined,
  block: CloseCircleOutlined,
  // 业务 / 实体
  person: UserOutlined, groups: TeamOutlined, contact_phone: PhoneOutlined, call: PhoneOutlined,
  business: BankOutlined, handshake: SolutionOutlined,
  description: FileTextOutlined, note: FileTextOutlined, edit_document: ProfileOutlined,
  checklist: UnorderedListOutlined, assignment_ind: IdcardOutlined,
  confirmation_number: TagOutlined, inventory_2: InboxOutlined,
  payments: PayCircleOutlined, paid: PayCircleOutlined,
  dashboard: DashboardOutlined, analytics: LineChartOutlined, leaderboard: BarChartOutlined,
  trending_up: RiseOutlined, notifications: BellOutlined, event: CalendarOutlined,
  support_agent: CustomerServiceOutlined, lightbulb: BulbOutlined,
  auto_awesome: ThunderboltOutlined, smart_toy: RobotOutlined, rocket_launch: RocketOutlined,
  star: StarOutlined,
  // 通知类型图标（NotificationBell）
  verified: SafetyCertificateOutlined, assignment: ProfileOutlined,
  person_add: UserAddOutlined, alternate_email: MailOutlined, summarize: FileTextOutlined,
}

const Fallback = AppstoreOutlined

export default function MobileIcon(
  { name, className, style }: { name?: string; className?: string; style?: React.CSSProperties },
) {
  const C = (name && MAP[name]) || Fallback
  return <C className={className} style={style} />
}
