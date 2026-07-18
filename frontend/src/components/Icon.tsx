// 全站图标：一律使用 antd 的内联 SVG（打包进 JS、不依赖字体/网络）。
//
// 背景：原先桌面端用 Material Symbols 连字字体，移动端因钉钉 webview 渲染不了字体
// 而另走 MobileIcon(SVG)，形成两套并存。现统一到 SVG，各端一致，也彻底消除
// 「图标显示成空框或 'edit' 连字原文」的问题，同时省掉 359KB 字体预加载。
//
// name 仍沿用 Material Symbols 名，故各页面已有的 icon 映射表、menus.ts 配置均无需改动。
// 新增图标名请在此登记；未登记会回退到通用图标，并在开发环境 console.warn 提示。
import React from 'react'
import {
  ArrowLeftOutlined, ArrowRightOutlined, ArrowUpOutlined, ArrowDownOutlined,
  LeftOutlined, RightOutlined, UpOutlined, DownOutlined,
  PlusOutlined, PlusCircleOutlined, PlusSquareOutlined, MinusOutlined, CloseOutlined,
  CloseCircleOutlined, CheckOutlined, CheckCircleOutlined, CheckSquareOutlined,
  EditOutlined, DeleteOutlined, ClearOutlined, CopyOutlined, SearchOutlined,
  FilterOutlined, ReloadOutlined, SyncOutlined, UndoOutlined, SendOutlined,
  ExportOutlined, DownloadOutlined, ShareAltOutlined, LinkOutlined, DisconnectOutlined,
  EyeOutlined, HolderOutlined, PushpinOutlined, SelectOutlined, SwapOutlined,
  LoadingOutlined, PauseCircleOutlined, PlayCircleOutlined, StopOutlined,
  WarningOutlined, InfoCircleOutlined, ExclamationCircleOutlined, QuestionCircleOutlined,
  ClockCircleOutlined, FieldTimeOutlined, HistoryOutlined, CalendarOutlined,
  LockOutlined, LoginOutlined, SafetyOutlined, SafetyCertificateOutlined,
  UserOutlined, UserAddOutlined, TeamOutlined, IdcardOutlined, ContactsOutlined,
  PhoneOutlined, MailOutlined, MessageOutlined, NotificationOutlined, BellOutlined,
  BankOutlined, ShopOutlined, SolutionOutlined, ApartmentOutlined, DeploymentUnitOutlined,
  FileTextOutlined, FileDoneOutlined, FileProtectOutlined, ProfileOutlined, FolderOutlined,
  DiffOutlined, FormOutlined, ReadOutlined, AccountBookOutlined, AuditOutlined,
  UnorderedListOutlined, TableOutlined, ProjectOutlined, MergeCellsOutlined,
  TagOutlined, InboxOutlined, ShoppingCartOutlined, DollarOutlined, PayCircleOutlined,
  WalletOutlined, MoneyCollectOutlined, TrophyOutlined,
  DashboardOutlined, LineChartOutlined, BarChartOutlined, PieChartOutlined, FundOutlined,
  RiseOutlined, FallOutlined, RadarChartOutlined,
  BulbOutlined, ThunderboltOutlined, RocketOutlined, RobotOutlined, StarOutlined,
  ExperimentOutlined, ApiOutlined, ToolOutlined, BuildOutlined, ControlOutlined,
  SettingOutlined, GlobalOutlined, EnvironmentOutlined, AimOutlined,
  DesktopOutlined, MobileOutlined, TabletOutlined, CameraOutlined, PictureOutlined,
  AudioOutlined, CloudOutlined, FlagOutlined, HighlightOutlined, NodeIndexOutlined,
  ColumnWidthOutlined, CustomerServiceOutlined, AppstoreOutlined,
  MenuOutlined, MenuUnfoldOutlined, EllipsisOutlined, PaperClipOutlined,
  SunOutlined, MoonOutlined, BellFilled,
} from '@ant-design/icons'

type IconComp = React.ComponentType<{ className?: string; style?: React.CSSProperties }>

// Material Symbols 名 -> antd SVG 图标。语义就近映射，同名多处复用属正常。
const MAP: Record<string, IconComp> = {
  // ---- 导航 / 方向 ----
  arrow_back: ArrowLeftOutlined, arrow_back_ios: ArrowLeftOutlined,
  arrow_forward: ArrowRightOutlined, arrow_upward: ArrowUpOutlined,
  arrow_downward: ArrowDownOutlined, chevron_left: LeftOutlined, chevron_right: RightOutlined,
  expand_more: DownOutlined, expand_less: UpOutlined, open_in_new: ExportOutlined,
  forward: ExportOutlined, login: LoginOutlined,

  // ---- 通用动作 ----
  add: PlusOutlined, add_circle: PlusCircleOutlined, add_task: PlusSquareOutlined,
  add_business: ShopOutlined, add_a_photo: CameraOutlined, remove: MinusOutlined,
  close: CloseOutlined, cancel: CloseCircleOutlined, block: StopOutlined,
  check: CheckOutlined, edit: EditOutlined, edit_note: EditOutlined, draw: HighlightOutlined,
  delete: DeleteOutlined, delete_sweep: ClearOutlined, content_copy: CopyOutlined,
  search: SearchOutlined, filter_alt: FilterOutlined, filter_list: FilterOutlined,
  refresh: ReloadOutlined, restart_alt: ReloadOutlined, sync: SyncOutlined,
  undo: UndoOutlined, send: SendOutlined, download: DownloadOutlined,
  share: ShareAltOutlined, link_off: DisconnectOutlined, link: LinkOutlined,
  visibility: EyeOutlined, drag_indicator: HolderOutlined, push_pin: PushpinOutlined,
  touch_app: SelectOutlined, swap_horiz: SwapOutlined, merge: MergeCellsOutlined,
  settings: SettingOutlined, tune: ControlOutlined, rule: ControlOutlined,
  translate: GlobalOutlined, map: GlobalOutlined,
  menu: MenuOutlined, menu_open: MenuUnfoldOutlined, more_horiz: EllipsisOutlined,
  attach_file: PaperClipOutlined, stop_circle: StopOutlined,
  light_mode: SunOutlined, dark_mode: MoonOutlined,

  // ---- 状态 / 反馈 ----
  check_circle: CheckCircleOutlined, task_alt: CheckCircleOutlined, approved: CheckCircleOutlined,
  approval: AuditOutlined, warning: WarningOutlined, report_problem: WarningOutlined,
  error: CloseCircleOutlined, gpp_bad: CloseCircleOutlined,
  priority_high: ExclamationCircleOutlined, info: InfoCircleOutlined, help: QuestionCircleOutlined,
  schedule: ClockCircleOutlined, pending_actions: ClockCircleOutlined, timer: FieldTimeOutlined,
  hourglass_top: FieldTimeOutlined, hourglass_empty: FieldTimeOutlined, alarm: ClockCircleOutlined,
  // error_outline: 移动端一直在用,但旧 MobileIcon 漏配、长期回退到通用图标,此处补上
  error_outline: ExclamationCircleOutlined,
  pause_circle: PauseCircleOutlined, play_circle: PlayCircleOutlined,
  progress_activity: LoadingOutlined, pan_tool: StopOutlined,
  cloud_off: DisconnectOutlined, cloud_done: CloudOutlined,
  history: HistoryOutlined, lock: LockOutlined, flag: FlagOutlined, flag_circle: FlagOutlined,

  // ---- 人员 / 组织 ----
  person: UserOutlined, person_add: UserAddOutlined, group: TeamOutlined, groups: TeamOutlined,
  assignment_ind: IdcardOutlined, contacts: ContactsOutlined,
  contact_phone: PhoneOutlined, call: PhoneOutlined,
  account_tree: ApartmentOutlined, hub: DeploymentUnitOutlined,
  admin_panel_settings: SafetyOutlined, verified: SafetyCertificateOutlined,
  // verified_user 与 shield 是 RoleList 同一个三元的两个分支,必须用不同图标,否则内置/自定义角色看不出区别
  verified_user: SafetyCertificateOutlined, shield: SafetyOutlined,

  // ---- 消息 / 通知 ----
  mail: MailOutlined, alternate_email: MailOutlined, chat: MessageOutlined,
  campaign: NotificationOutlined, notifications: BellOutlined,
  // 订阅按钮用 active/none 两态表达是否已订阅,必须实心/空心区分,否则按钮点了看不出变化
  notifications_active: BellFilled, notifications_none: BellOutlined,
  mic: AudioOutlined,

  // ---- 业务实体 ----
  business: BankOutlined, factory: BuildOutlined, account_balance: BankOutlined,
  handshake: SolutionOutlined, contract: FileProtectOutlined,
  description: FileTextOutlined, note: FileTextOutlined, sticky_note_2: FileTextOutlined,
  summarize: FileTextOutlined, edit_document: ProfileOutlined, assignment: ProfileOutlined,
  fact_check: FileDoneOutlined, difference: DiffOutlined, dynamic_form: FormOutlined,
  folder: FolderOutlined, menu_book: ReadOutlined, receipt_long: AccountBookOutlined,
  checklist: UnorderedListOutlined, table_rows: TableOutlined, view_kanban: ProjectOutlined,
  confirmation_number: TagOutlined, sell: TagOutlined,
  inventory_2: InboxOutlined, inbox: InboxOutlined, search_off: SearchOutlined,
  shopping_cart: ShoppingCartOutlined, request_quote: DollarOutlined,
  payments: PayCircleOutlined, paid: PayCircleOutlined,
  account_balance_wallet: WalletOutlined, savings: MoneyCollectOutlined,
  emoji_events: TrophyOutlined,

  // ---- 日程 ----
  event: CalendarOutlined, event_busy: CalendarOutlined,
  calendar_month: CalendarOutlined, calendar_today: CalendarOutlined,

  // ---- 图表 / 数据 ----
  dashboard: DashboardOutlined, analytics: LineChartOutlined, insights: LineChartOutlined,
  show_chart: LineChartOutlined, bar_chart: BarChartOutlined, insert_chart: BarChartOutlined,
  leaderboard: BarChartOutlined, pie_chart: PieChartOutlined, monitoring: FundOutlined,
  monitor_heart: DashboardOutlined, trending_up: RiseOutlined, trending_down: FallOutlined,
  waves: RadarChartOutlined,

  // ---- AI / 技术 ----
  lightbulb: BulbOutlined, auto_awesome: ThunderboltOutlined, bolt: ThunderboltOutlined,
  rocket_launch: RocketOutlined, smart_toy: RobotOutlined, psychology: ExperimentOutlined,
  star: StarOutlined, api: ApiOutlined,
  precision_manufacturing: ToolOutlined, support_agent: CustomerServiceOutlined,

  // ---- 设备 / 位置 ----
  computer: DesktopOutlined, smartphone: MobileOutlined, phonelink_ring: MobileOutlined,
  tablet: TabletOutlined, photo_camera: CameraOutlined,
  location_on: EnvironmentOutlined, distance: ColumnWidthOutlined,
  directions_walk: NodeIndexOutlined,
}

const Fallback = AppstoreOutlined

// 未登记图标名只在 DEV 首次出现时告警一次。放在模块级而非 render 内累加，
// 避免长列表里每行每次渲染都刷屏（StrictMode 下还会翻倍）。
const warned = new Set<string>()

export default function Icon(
  { name, className, style, defaultSize = true }: {
    name?: string
    className?: string
    style?: React.CSSProperties
    /** 是否套用 app-icon 的 24px 默认字号。移动端传 false：那边多处调用不指定尺寸，
     *  依赖继承字号，套上 24px 会变大。 */
    defaultSize?: boolean
  },
) {
  const C = (name && MAP[name]) || Fallback
  if (import.meta.env.DEV && name && !MAP[name] && !warned.has(name)) {
    warned.add(name)
    console.warn(`[Icon] 未登记的图标名 "${name}"，已回退到通用图标。请在 components/Icon.tsx 补充映射。`)
  }
  // app-icon 提供 24px 默认字号；它定义在 index.css 的 @layer base 中，
  // 因此调用方的 Tailwind text-sm / text-5xl（utilities 层，排在 base 之后）能正常覆盖。
  const cls = [defaultSize ? 'app-icon' : '', className].filter(Boolean).join(' ')
  return <C className={cls || undefined} style={style} />
}

/** 图标名是否已登记。Icon.test.tsx 用它校验源码里所有可达图标名都有映射。 */
export const hasIcon = (name?: string) => !!(name && MAP[name])
