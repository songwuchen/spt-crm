// 移动端表单的字段策略接入件。
//
// 移动端此前是裸 useState + 原生 input，接不了字段策略，而且字段集是桌面端的真子集
// （线索桌面端 18 个可填字段，移动端只有 6 个）。后端 create 走 required_scope="all"：
// 租户一旦把某个移动端没有的字段设为必填，移动端就再也建不了记录 —— 且界面上无处可填。
// 这里把移动端也纳入同一套策略，并补齐缺失字段。
//
// MField 是 PolicyItem 的移动端样式变体：沿用移动端的 label 观感，其余行为完全一致
// （必填注入、按规则隐藏、只读/脱敏禁用）。
import { Children, isValidElement, useMemo, useState, type ReactNode } from 'react'
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

/** 递归收集子树里所有带 name 的字段项，供「区内是否有必填」判定使用。 */
function collectFieldNames(node: ReactNode, out: string[] = []): string[] {
  Children.forEach(node, (child) => {
    if (!isValidElement(child)) return
    const props = child.props as { name?: unknown; children?: ReactNode }
    if (typeof props.name === 'string') out.push(props.name)
    if (props.children) collectFieldNames(props.children, out)
  })
  return out
}

/**
 * 「更多字段」折叠区：移动端屏幕小，把不常用的字段收起来。
 *
 * 只要区内有任一字段被租户配成必填，就强制展开并隐藏折叠按钮 —— 否则用户会遇到
 * 「保存被拦下，却找不到是哪个字段」的困境；而留一个点了没反应的按钮更糟。
 *
 * 字段名从 children 递归收集，不再靠调用方手写 id 数组 —— 那份数组必须与 JSX 内容
 * 保持同步，漏加一个就会让自动展开失效，正好掉进上面那个坑。
 */
export function MoreFields({ children }: { children: ReactNode }) {
  const policy = useFieldPolicy()
  const fieldIds = useMemo(() => collectFieldNames(children), [children])
  const hasRequired = fieldIds.some((id) => {
    const st = policy.states[id]
    return st?.visible && st?.required && !st?.masked
  })
  const [open, setOpen] = useState(false)
  const expanded = open || hasRequired

  return (
    <div>
      {hasRequired ? (
        <div className="text-sm font-bold text-slate-500 py-2">
          更多字段<span className="text-slate-400 font-normal ml-2">（含必填项，已展开）</span>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full text-left text-sm font-bold text-primary py-2"
        >
          {expanded ? '收起更多字段' : '展开更多字段'}
        </button>
      )}
      {/* 用 hidden 而非卸载：卸载会让 antd Form 丢掉这些字段的值 */}
      <div className={expanded ? 'space-y-4' : 'hidden'}>{children}</div>
    </div>
  )
}

/**
 * 提交失败时把首个校验错误提示出来。
 *
 * 折叠区用 display:none 隐藏，字段仍然挂载并参与校验 —— 若错误落在收起的字段上
 * （典型是策略还没加载完、自动展开尚未触发时提交），用户只会看到「保存没反应」。
 * 这里显式把错误文案弹出来，至少让人知道卡在哪。
 */
export function reportFirstFormError(err: unknown, notify: (msg: string) => void): void {
  const fields = (err as { errorFields?: { errors?: string[] }[] })?.errorFields
  const first = fields?.find((f) => f.errors?.length)?.errors?.[0]
  if (first) notify(first)
}
