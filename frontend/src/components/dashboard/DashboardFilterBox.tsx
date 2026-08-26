/** 仪表盘筛选格：字段名 + 运算符下拉 + 值控件（项目主题色） */
import { Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import type { ReactNode } from 'react'

export interface DashboardFilterOpOption {
  value: string
  label: string
}

interface Props {
  label: string
  method: string
  methodOptions: DashboardFilterOpOption[]
  onMethodChange: (v: string) => void
  width?: number | string
  children: ReactNode
  /** 为空/不为空等无需值控件时隐藏下方区域 */
  hideValue?: boolean
}

export default function DashboardFilterBox({
  label, method, methodOptions, onMethodChange, width = '100%', children, hideValue,
}: Props) {
  const current = methodOptions.find((o) => o.value === method)

  const menuItems: MenuProps['items'] = methodOptions.map((o) => ({
    key: o.value,
    label: (
      <span className={o.value === method ? 'text-primary font-medium' : ''}>{o.label}</span>
    ),
  }))

  return (
    <div
      className="dash-filter-box flex flex-col bg-white border border-slate-200 rounded-lg shadow-sm hover:border-slate-300 transition-colors"
      style={{ width, minWidth: typeof width === 'number' ? width : undefined, flex: width === '100%' ? '1 1 180px' : undefined }}
    >
      <div className="flex items-center justify-between gap-2 px-3 pt-2.5 pb-1 min-h-[32px]">
        <span className="text-[13px] text-slate-700 font-medium truncate">{label}</span>
        <Dropdown
          menu={{
            items: menuItems,
            selectedKeys: [method],
            onClick: ({ key }) => onMethodChange(String(key)),
          }}
          trigger={['click']}
          placement="bottomRight"
        >
          <button
            type="button"
            className="inline-flex items-center gap-0.5 text-xs text-primary hover:text-primary/80 shrink-0 max-w-[52%]"
          >
            <span className="truncate">{current?.label || method}</span>
            <DownOutlined style={{ fontSize: 10 }} />
          </button>
        </Dropdown>
      </div>
      {!hideValue && (
        <div className="dash-filter-value px-3 pb-2.5 min-h-[34px] flex items-center">
          {children}
        </div>
      )}
    </div>
  )
}
