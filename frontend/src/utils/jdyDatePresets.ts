/** 仪表盘日期「动态筛选」预设 */
import dayjs, { type Dayjs } from 'dayjs'
import quarterOfYear from 'dayjs/plugin/quarterOfYear'

dayjs.extend(quarterOfYear)

export type DatePresetKey =
  | 'today' | 'yesterday' | 'tomorrow'
  | 'last7Days' | 'last30Days'
  | 'thisWeek' | 'lastWeek' | 'nextWeek'
  | 'thisMonth' | 'lastMonth' | 'nextMonth'
  | 'thisQuarter' | 'lastQuarter' | 'nextQuarter'
  | 'thisYear' | 'lastYear' | 'nextYear'

export const DATE_PRESET_LABELS: Record<DatePresetKey, string> = {
  today: '今天',
  yesterday: '昨天',
  tomorrow: '明天',
  last7Days: '近7天',
  last30Days: '近30天',
  thisWeek: '本周',
  lastWeek: '上周',
  nextWeek: '下周',
  thisMonth: '本月',
  lastMonth: '上月',
  nextMonth: '下月',
  thisQuarter: '本季度',
  lastQuarter: '上季度',
  nextQuarter: '下季度',
  thisYear: '今年',
  lastYear: '去年',
  nextYear: '明年',
}

/** 动态筛选面板：三列网格顺序（对齐简道云布局） */
export const DATE_PRESET_GRID: DatePresetKey[][] = [
  ['today', 'thisWeek', 'thisMonth', 'thisQuarter', 'thisYear'],
  ['yesterday', 'lastWeek', 'lastMonth', 'lastQuarter', 'lastYear'],
  ['tomorrow', 'nextWeek', 'nextMonth', 'nextQuarter', 'nextYear'],
  ['last7Days', 'last30Days'],
]

export function resolveDatePreset(key: DatePresetKey, now = dayjs()): [Dayjs, Dayjs] {
  switch (key) {
    case 'today':
      return [now.startOf('day'), now.endOf('day')]
    case 'yesterday': {
      const d = now.subtract(1, 'day')
      return [d.startOf('day'), d.endOf('day')]
    }
    case 'tomorrow': {
      const d = now.add(1, 'day')
      return [d.startOf('day'), d.endOf('day')]
    }
    case 'thisWeek':
      return [now.startOf('week'), now.endOf('week')]
    case 'lastWeek': {
      const d = now.subtract(1, 'week')
      return [d.startOf('week'), d.endOf('week')]
    }
    case 'nextWeek': {
      const d = now.add(1, 'week')
      return [d.startOf('week'), d.endOf('week')]
    }
    case 'thisMonth':
      return [now.startOf('month'), now.endOf('month')]
    case 'lastMonth': {
      const d = now.subtract(1, 'month')
      return [d.startOf('month'), d.endOf('month')]
    }
    case 'nextMonth': {
      const d = now.add(1, 'month')
      return [d.startOf('month'), d.endOf('month')]
    }
    case 'thisQuarter':
      return [now.startOf('quarter'), now.endOf('quarter')]
    case 'lastQuarter': {
      const d = now.subtract(1, 'quarter')
      return [d.startOf('quarter'), d.endOf('quarter')]
    }
    case 'nextQuarter': {
      const d = now.add(1, 'quarter')
      return [d.startOf('quarter'), d.endOf('quarter')]
    }
    case 'thisYear':
      return [now.startOf('year'), now.endOf('year')]
    case 'lastYear': {
      const d = now.subtract(1, 'year')
      return [d.startOf('year'), d.endOf('year')]
    }
    case 'nextYear': {
      const d = now.add(1, 'year')
      return [d.startOf('year'), d.endOf('year')]
    }
    case 'last7Days':
      return [now.subtract(6, 'day').startOf('day'), now.endOf('day')]
    case 'last30Days':
      return [now.subtract(29, 'day').startOf('day'), now.endOf('day')]
    default:
      return [now.startOf('year'), now.endOf('year')]
  }
}

/** @deprecated 兼容旧引用 */
export type JdyDatePresetKey = DatePresetKey
export const JDY_DATE_PRESET_LABELS = DATE_PRESET_LABELS
export const JDY_DATE_PRESET_OPTIONS = (Object.keys(DATE_PRESET_LABELS) as DatePresetKey[])
  .map((k) => ({ value: k, label: DATE_PRESET_LABELS[k] }))
export const resolveJdyDatePreset = resolveDatePreset
