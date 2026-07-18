// 字段类型图标 — 全部使用 antd 的内联 SVG 图标（打包进 JS、不依赖字体/网络），
// 与 MobileIcon 同样的理由：钉钉 webview 渲染不了图标字体。桌面端与移动端共用这一份映射，
// 保证各端字段图标语义一致。新增 FieldType 时请在此同步补充，否则回退到通用图标。
import React from 'react'
import {
  FontSizeOutlined, AlignLeftOutlined, NumberOutlined, MoneyCollectOutlined,
  CalendarOutlined, FieldTimeOutlined, DownSquareOutlined, ProfileOutlined,
  CheckCircleOutlined, CheckSquareOutlined, SwapOutlined, ApartmentOutlined, BranchesOutlined,
  UserOutlined, TeamOutlined, ClusterOutlined, PaperClipOutlined, PictureOutlined,
  TableOutlined, FunctionOutlined, FieldNumberOutlined, LinkOutlined,
  EnvironmentOutlined, AimOutlined, HighlightOutlined, FileTextOutlined,
  DatabaseOutlined, DeploymentUnitOutlined, BlockOutlined, BorderOuterOutlined,
} from '@ant-design/icons'
import type { FieldType } from '@/types/lowcode'

type IconComp = React.ComponentType<{ className?: string; style?: React.CSSProperties }>

// 覆盖 types/lowcode.ts 中全部 29 个 FieldType（Record 强约束，新增类型漏配会编译报错）
export const FIELD_TYPE_ICON: Record<FieldType, IconComp> = {
  // 基础
  text: FontSizeOutlined,
  textarea: AlignLeftOutlined,
  number: NumberOutlined,
  amount: MoneyCollectOutlined,
  date: CalendarOutlined,
  datetime: FieldTimeOutlined,
  switch: SwapOutlined,
  // 选择
  select: DownSquareOutlined,
  multi_select: ProfileOutlined,
  radio: CheckCircleOutlined,
  checkbox: CheckSquareOutlined,
  // 级联选择用 Branches 而非 Partition/Apartment：后两者在 12~14px 下与「部门」几乎无法区分
  cascade: BranchesOutlined,
  // 人员 / 部门
  person: UserOutlined,
  person_multi: TeamOutlined,
  department: ApartmentOutlined,
  department_multi: ClusterOutlined,
  // 附件 / 富媒体
  file: PaperClipOutlined,
  image: PictureOutlined,
  rich_text: FileTextOutlined,
  signature: HighlightOutlined,
  // 地址 / 定位
  address: EnvironmentOutlined,
  location: AimOutlined,
  // 高级
  formula: FunctionOutlined,
  auto_number: FieldNumberOutlined,
  detail_table: TableOutlined,
  sub_table_data: BorderOuterOutlined,
  related_doc: LinkOutlined,
  select_data: DatabaseOutlined,
  relation: DeploymentUnitOutlined,
}

// 搜索/筛选 schema(api/searchSchema.ts)用的是另一套更窄的类型名,在此归一到 FieldType,
// 否则 enum/boolean/people 会静默落到兜底图标。
const TYPE_ALIAS: Record<string, FieldType> = {
  enum: 'select',
  boolean: 'switch',
  people: 'person',
}

const Fallback = BlockOutlined

/** 按字段类型渲染 SVG 图标；未知类型回退到通用图标（不抛错、不留空白） */
export default function FieldTypeIcon(
  { type, className, style }: { type?: string; className?: string; style?: React.CSSProperties },
) {
  const key = type ? (TYPE_ALIAS[type] || (type as FieldType)) : undefined
  const C = (key && FIELD_TYPE_ICON[key]) || Fallback
  return <C className={className} style={style} />
}

// 字段类型中文名。原先私有在 FormDesignerPage 里,现与图标映射放在一起,便于各处“图标+名称”成对使用。
export const FIELD_TYPE_LABEL: Record<string, string> = {
  text: '单行文本', textarea: '多行文本', number: '数字', amount: '金额', date: '日期', datetime: '日期时间',
  select: '下拉单选', multi_select: '下拉多选', radio: '单选框', checkbox: '复选框', switch: '开关', cascade: '级联选择',
  person: '人员单选', person_multi: '人员多选', department: '部门单选', department_multi: '部门多选',
  file: '附件', image: '图片', address: '地址', rich_text: '富文本', signature: '手写签名',
  formula: '公式', auto_number: '流水号', detail_table: '明细子表',
}

/**
 * 生成带字段类型图标的 Select option。各处字段选择器(筛选/排序/规则/图表/流程)统一走这里,
 * 避免每个调用点各写一遍 label JSX。
 * 注意: label 变成 JSX 后无法再按 label 搜索,故同时给出纯文本 title —
 * 带 showSearch 的调用点请设 optionFilterProp="title"。
 */
export function fieldOption<T extends string>(
  { value, label, type }: { value: T; label: string; type?: string },
) {
  return {
    value,
    title: label,
    label: (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <FieldTypeIcon type={type} style={{ color: '#8c8c8c' }} />
        {label}
      </span>
    ),
  }
}
