/** 客户表单选项：对齐简道云数据中心「客户信息」 */
export const YES_NO = [
  { label: '是', value: true },
  { label: '否', value: false },
]

/** 所属行业（简道云 radiogroup 主选项；字典未配置时兜底） */
export const DEFAULT_INDUSTRIES = [
  '工业升级', '循环经济', '基建民生', '技术改造', '其他',
].map((i) => ({ label: i, value: i }))

export const DEFAULT_LEVELS = ['A', 'B', 'C', 'D'].map((l) => ({ label: l, value: l }))
export const DEFAULT_SCALES = ['微型', '小型', '中型', '大型', '特大型'].map((s) => ({ label: s, value: s }))

/** 客户来源：CRM 通用 + 简道云外贸渠道 */
export const DEFAULT_SOURCES = [
  { label: '展会', value: 'expo' },
  { label: '转介绍', value: 'referral' },
  { label: '广告', value: 'ad' },
  { label: '官网/入站', value: 'inbound' },
  { label: '合作伙伴', value: 'partner' },
  { label: '电话', value: 'call' },
  { label: '阿里', value: '阿里' },
  { label: 'QQ', value: 'QQ' },
  { label: 'TQ', value: 'TQ' },
  { label: 'ETW', value: 'ETW' },
  { label: 'GM', value: 'GM' },
  { label: 'Trade2cn', value: 'Trade2cn' },
  { label: 'Tradekey', value: 'Tradekey' },
  { label: 'Direct Industry', value: 'Direct Industry' },
  { label: '搜索', value: '搜索' },
  { label: '康帕斯', value: '康帕斯' },
  { label: 'LINKEDIN', value: 'LINKEDIN' },
  { label: '其他', value: '其他' },
]

export const CUSTOMER_NATURE_OPTIONS = [
  '一般民企', '国企控股', '国有企业', '上市公司', '其他',
].map((v) => ({ label: v, value: v }))

export const CUSTOMER_RELATION_OPTIONS = [
  { label: '直接关系', value: '直接关系' },
  { label: '间接关系', value: '间接关系' },
]

export const CONTACT_TITLE_LEVEL_OPTIONS = [
  '一般员工', '主管级别', '部门经理级别', '副总经理级别', '总经理及董事长级别',
].map((v) => ({ label: v, value: v }))

export const WAGE_INSURANCE_OPTIONS = [
  '正常', '正常有拖欠', '非正常',
].map((v) => ({ label: v, value: v }))

export const FOREIGN_CUSTOMER_TYPE_OPTIONS = [
  '合作客户', '潜在客户', '合作供应商', '潜在供应商', '合作货贷商',
  '验货公司', '合作会展商', '合作推广商', '潜在推广商', '潜在货代商',
].map((v) => ({ label: v, value: v }))

export const FOCUS_PRODUCT_OPTIONS = [
  '旋振筛', '检验筛', '振动筛', '高幅筛', '熔剂筛', '节肢筛', '圆振筛', '直线筛',
  '球团筛', '香蕉筛', '弧形筛', '脱泥脱介筛', '轻型筛', '落砂机', '给料机',
  '输送机', '破碎机', '破碎筛分生产线', '备件', '其他',
].map((v) => ({ label: v, value: v }))

export const MAIN_PRODUCT_OPTIONS = [
  '冶金', '煤炭', '矿山', '焦化', '电力', '食品', '医药', '化工', '砂石骨料，制砂', '水处理',
].map((v) => ({ label: v, value: v }))

export const INTENT_OPTIONS = [
  { label: 'A · 3个月内会订购', value: 'A' },
  { label: 'B · 半年内', value: 'B' },
  { label: 'C · 一年内', value: 'C' },
  { label: 'D · 一年以上/暂无', value: 'D' },
]

export const MATCH_OPTIONS = [
  { label: '有需求有预算', value: 'has_need_budget' },
  { label: '有需求与需求负责人', value: 'has_need_owner' },
  { label: '仅有需求', value: 'need_only' },
  { label: '需求不明确', value: 'unclear' },
]

export const CURRENCY_OPTIONS = [
  { label: '人民币 CNY', value: 'CNY' },
  { label: '美元 USD', value: 'USD' },
  { label: '欧元 EUR', value: 'EUR' },
  { label: '日元 JPY', value: 'JPY' },
]
