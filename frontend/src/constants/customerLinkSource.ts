/** 线索转化商机的客户绑定标识（仅来自线索转化时写入） */
export type CustomerLinkSource = 'matched' | 'unmatched' | 'ambiguous' | 'auto_created'

export const CUSTOMER_LINK_META: Record<
  CustomerLinkSource,
  { color: string; label: string; hint: string; alertType: 'info' | 'warning' }
> = {
  matched: {
    color: 'blue',
    label: '已匹配客户',
    hint: '线索公司名称与客户管理一致；如关联有误，请在编辑商机中更换关联客户。',
    alertType: 'info',
  },
  unmatched: {
    color: 'orange',
    label: '未匹配客户',
    hint: '客户管理中未找到与线索公司名称一致的客户，请在编辑商机中手工关联或先新建客户。',
    alertType: 'warning',
  },
  ambiguous: {
    color: 'red',
    label: '客户重名待选',
    hint: '客户管理中存在多个同名客户，请在编辑商机中手工选择正确的关联客户。',
    alertType: 'warning',
  },
  auto_created: {
    color: 'green',
    label: '系统创建客户',
    hint: '线索转商机时未匹配到已有客户，系统已按线索公司信息自动创建客户并关联；可在客户管理中补充完善资料。',
    alertType: 'info',
  },
}

export function customerLinkTag(source: string | null | undefined) {
  if (!source) return null
  return CUSTOMER_LINK_META[source as CustomerLinkSource] ?? null
}
