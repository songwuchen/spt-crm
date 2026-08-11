/** 技术协议评审表单取值/回填（新建 fill 页与列表弹窗共用）。 */
import dayjs from 'dayjs'
import type { TechAgreementReview } from '@/api/techAgreementReview'
import { TAR_DATE_KEYS, TAR_NATIVE_KEYS } from '@/constants/techAgreementReview'

export function tarRowToFormValues(d: TechAgreementReview): Record<string, unknown> {
  const vals: Record<string, unknown> = { ...d, form_json: d.form_json || {} }
  for (const k of TAR_DATE_KEYS) {
    if (vals[k]) vals[k] = dayjs(vals[k] as string)
  }
  return vals
}

export function tarBuildPayload(merged: Record<string, unknown>): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    status: 'draft',
    form_json: (merged.form_json as Record<string, unknown>) || {},
  }
  for (const k of TAR_NATIVE_KEYS) {
    if (merged[k] !== undefined) payload[k] = merged[k]
  }
  for (const k of TAR_DATE_KEYS) {
    const v = payload[k]
    if (v && dayjs.isDayjs(v)) payload[k] = (v as dayjs.Dayjs).toISOString()
  }
  return payload
}

export function canEditTarStatus(status?: string) {
  return status === 'draft' || status === 'rejected'
}
