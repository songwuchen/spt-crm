/** 动态日期预设选择器 — 网格面板 + 自定义范围 */
import { useState } from 'react'
import { DatePicker, Popover } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import {
  DATE_PRESET_GRID,
  DATE_PRESET_LABELS,
  type DatePresetKey,
} from '@/utils/jdyDatePresets'

const { RangePicker } = DatePicker

interface Props {
  preset: DatePresetKey
  customRange: [Dayjs, Dayjs]
  onPreset: (key: DatePresetKey) => void
  onCustomRange: (range: [Dayjs, Dayjs]) => void
}

export default function DatePresetPicker({ preset, customRange, onPreset, onCustomRange }: Props) {
  const [open, setOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(false)

  const displayLabel = DATE_PRESET_LABELS[preset] || '今年'

  const panel = (
    <div className="w-[320px] p-2">
      <button
        type="button"
        className="w-full text-left text-sm text-slate-600 hover:text-primary py-1.5 px-2 rounded hover:bg-slate-50 mb-1"
        onClick={() => {
          setCustomOpen(true)
          setOpen(false)
        }}
      >
        自定义
      </button>
      <div className="grid grid-cols-3 gap-1">
        {DATE_PRESET_GRID.flat().map((key) => (
          <button
            key={key}
            type="button"
            className={`text-sm py-1.5 px-1 rounded transition-colors ${
              preset === key
                ? 'bg-primary text-white'
                : 'text-slate-700 hover:bg-slate-100'
            }`}
            onClick={() => {
              onPreset(key)
              setOpen(false)
            }}
          >
            {DATE_PRESET_LABELS[key]}
          </button>
        ))}
      </div>
    </div>
  )

  return (
    <>
      <Popover
        open={open}
        onOpenChange={setOpen}
        trigger="click"
        placement="bottomLeft"
        content={panel}
      >
        <button
          type="button"
          className="w-full flex items-center justify-between text-sm text-slate-800 hover:text-primary py-0.5"
        >
          <span>{displayLabel}</span>
          <DownOutlined className="text-slate-400" style={{ fontSize: 10 }} />
        </button>
      </Popover>
      <RangePicker
        open={customOpen}
        onOpenChange={setCustomOpen}
        value={customRange}
        allowClear={false}
        className="absolute opacity-0 pointer-events-none w-0 h-0 overflow-hidden"
        onChange={(v) => {
          if (v?.[0] && v[1]) {
            onCustomRange([v[0], v[1]])
            setCustomOpen(false)
          }
        }}
      />
    </>
  )
}
