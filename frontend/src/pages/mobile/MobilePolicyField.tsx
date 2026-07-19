// 移动端表单的字段策略接入件。
//
// 移动端此前是裸 useState + 原生 input，接不了字段策略，而且字段集是桌面端的真子集
// （线索桌面端 18 个可填字段，移动端只有 6 个）。后端 create 走 required_scope="all"：
// 租户一旦把某个移动端没有的字段设为必填，移动端就再也建不了记录 —— 且界面上无处可填。
// 这里把移动端也纳入同一套策略，并补齐缺失字段。
//
// MField 是 PolicyItem 的移动端样式变体：沿用移动端的 label 观感，其余行为完全一致
// （必填注入、按规则隐藏、只读/脱敏禁用）。
import { useState, type ReactNode } from 'react'
import { PolicyItem, useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import type { FormItemProps } from 'antd'

type MFieldProps = Omit<FormItemProps, 'label'> & { name: string; label: ReactNode }

export function MField({ label, ...rest }: MFieldProps) {
  return (
    <PolicyItem
      {...rest}
      label={<span className="text-sm font-bold text-slate-500 uppercase tracking-wider">{label}</span>}
    />
  )
}

/**
 * 「更多字段」折叠区：移动端屏幕小，把不常用的字段收起来。
 *
 * 但只要区内有任一字段被租户配成必填，就默认展开 —— 否则用户会遇到
 * 「保存被拦下，却找不到是哪个字段」的困境。
 */
export function MoreFields({ fieldIds, children }: { fieldIds: string[]; children: ReactNode }) {
  const policy = useFieldPolicy()
  const hasRequired = fieldIds.some((id) => {
    const st = policy.states[id]
    return st?.visible && st?.required && !st?.masked
  })
  const [open, setOpen] = useState(false)
  const expanded = open || hasRequired

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left text-sm font-bold text-primary py-2"
      >
        {expanded ? '收起更多字段' : '展开更多字段'}
        {hasRequired && !open && <span className="text-slate-400 font-normal ml-2">（含必填项）</span>}
      </button>
      {/* 用 hidden 而非卸载：卸载会让 antd Form 丢掉这些字段的值 */}
      <div className={expanded ? 'space-y-4' : 'hidden'}>{children}</div>
    </div>
  )
}
