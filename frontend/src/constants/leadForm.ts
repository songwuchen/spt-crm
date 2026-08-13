/** 简道云「申报信息」选项兜底（与 native_field_catalog / seed_lead_dicts 对齐） */

export const YES_NO = [
  { label: '是', value: '是' },
  { label: '否', value: '否' },
]

export const CATEGORY_OPTIONS = [
  { label: '自报', value: 'self_reported' },
  { label: '分发', value: 'distributed' },
]

export const COUNTRY_OPTIONS = [
  { label: '国内', value: 'domestic' },
  { label: '国外', value: 'overseas' },
]

/** 字典码兜底；有字典时优先用 useDataDict */
export const CUSTOMER_TYPE_OPTIONS = [
  { value: 'terminal_soe', label: '终端客户-央企/国企' },
  { value: 'terminal_large_private', label: '终端客户-大型民企（注册资本10亿以上）' },
  { value: 'terminal_private', label: '终端客户-一般民企' },
  { value: 'design_institute', label: '设计院' },
  { value: 'general_contractor', label: '总包商' },
  { value: 'supporting_trader', label: '配套商、贸易商' },
  { value: 'other', label: '其他' },
]

export const INDUSTRY_OPTIONS = [
  { value: 'screening_metallurgy', label: '筛分分选-冶金' },
  { value: 'screening_mining', label: '筛分分选-矿山' },
  { value: 'screening_aggregate', label: '筛分分选-砂石' },
  { value: 'screening_coking', label: '筛分分选-焦化' },
  { value: 'screening_coal', label: '筛分分选-煤炭' },
  { value: 'screening_power', label: '筛分分选-电力' },
  { value: 'screening_chemical', label: '筛分分选-化工' },
  { value: 'screening_pharma', label: '筛分分选-医药' },
  { value: 'screening_food', label: '筛分分选-食品' },
  { value: 'screening_spare_parts', label: '筛分分选-备件' },
  { value: 'circular_economy', label: '循环经济' },
  { value: 'scrap_steel', label: '废钢利用' },
  { value: 'bulk_material_intelligent', label: '智能化大宗物料管理' },
]

export const BID_RESULT_OPTIONS = [
  { label: '中标', value: '中标' },
  { label: '结果未出', value: '结果未出' },
  { label: '项目取消', value: '项目取消' },
  { label: '项目延期', value: '项目延期' },
  { label: '落标', value: '落标' },
  { label: '流标', value: '流标' },
  { label: '未参与', value: '未参与' },
]

export const BID_FAIL_REASON_OPTIONS = [
  { label: '价格原因：价格高、最低价中标', value: '价格原因：价格高、最低价中标' },
  { label: '内定：客户不愿意更换厂家、客户内部操作了、走形式、内定中标单位了', value: '内定：客户不愿意更换厂家、客户内部操作了、走形式、内定中标单位了' },
  { label: '资质原因：需要煤安证、矿安证、业主要求进口品牌；业绩达不到', value: '资质原因：需要煤安证、矿安证、业主要求进口品牌；业绩达不到' },
  { label: '技术原因：技术参数不符合、参数达不到现场要求、筛分效率达不到、功率偏高客户不同意、技术没达到对方要求、客户要求技术是国际标准', value: '技术原因：技术参数不符合、参数达不到现场要求、筛分效率达不到、功率偏高客户不同意、技术没达到对方要求、客户要求技术是国际标准' },
  { label: '客户现场原因：现场空间不足', value: '客户现场原因：现场空间不足' },
  { label: '质保原因：质保期达不到', value: '质保原因：质保期达不到' },
  { label: '付款方式偏离：客户不接受咱的付款方式', value: '付款方式偏离：客户不接受咱的付款方式' },
  { label: '工期原因：要求交货时间达不到', value: '工期原因：要求交货时间达不到' },
  { label: '客户不透露', value: '客户不透露' },
]

export const ENTRUST_STATUS_OPTIONS = [
  { label: '已开', value: '已开' },
  { label: '未开', value: '未开' },
]

export const PROJECT_ACTIVITY_OPTIONS = [
  { label: '技术交流', value: '技术交流' },
  { label: '出方案', value: '出方案' },
  { label: '报价', value: '报价' },
  { label: '投标', value: '投标' },
  { label: '拟建', value: '拟建' },
]

export const REPORT_PROJECT_STATUS_OPTIONS = [
  { label: '进行中', value: '进行中' },
  { label: '暂缓', value: '暂缓' },
  { label: '暂停', value: '暂停' },
  { label: '取消', value: '取消' },
  { label: '落标', value: '落标' },
  { label: '中标', value: '中标' },
  { label: '已签合同', value: '已签合同' },
]

/** 重激活选这些结果则结束本轮，不再进情报审批 */
export const REACTIVATION_CLOSE_STATUSES = ['暂缓', '暂停', '取消', '落标']

export const DEFAULT_LEAD_SOURCES = [
  { label: '展会', value: 'expo' },
  { label: '转介绍', value: 'referral' },
  { label: '广告', value: 'ad' },
  { label: '官网/入站', value: 'inbound' },
  { label: '合作伙伴', value: 'partner' },
  { label: '电话', value: 'call' },
]

export const FEEDBACK_FIELD_IDS = [
  'project_recent', 'follow_progress', 'site_visit', 'report_project_status',
]
