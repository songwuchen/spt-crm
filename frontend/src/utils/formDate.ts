/** 表单日期：拦截 invalid dayjs / "Invalid Date"，避免提交给后端 422。 */
import dayjs from 'dayjs'

export function isBlankDate(v: unknown): boolean {
  return v == null || v === ''
}

export function isValidFormDate(v: unknown): boolean {
  if (isBlankDate(v)) return true
  if (dayjs.isDayjs(v)) return v.isValid()
  if (typeof v === 'string') {
    if (/invalid/i.test(v)) return false
    const d = dayjs(v)
    return d.isValid()
  }
  return false
}

/** 转 API 用的 YYYY-MM-DD；空则 undefined。非法日期返回 null（调用方应先校验）。 */
export function formatFormDate(v: unknown): string | undefined | null {
  if (isBlankDate(v)) return undefined
  if (!isValidFormDate(v)) return null
  if (dayjs.isDayjs(v)) return v.format('YYYY-MM-DD')
  if (typeof v === 'string') {
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v
    return dayjs(v).format('YYYY-MM-DD')
  }
  return undefined
}

/** antd Form 规则：有值则必须是有效日期 */
export const formDateRule = {
  validator(_: unknown, v: unknown) {
    if (isBlankDate(v)) return Promise.resolve()
    if (isValidFormDate(v)) return Promise.resolve()
    return Promise.reject(new Error('请选择或输入有效日期'))
  },
}
