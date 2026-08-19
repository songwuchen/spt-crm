/** 从合同评审字段定义构建 key → label 映射（数据日志展示用） */
import {
  CONTRACT_REVIEW_SECTIONS,
  reviewSectionAllFields,
  type ReviewFieldDef,
} from '@/constants/contractReview'

function addField(map: Record<string, string>, f: ReviewFieldDef) {
  map[f.key] = f.label
  if (f.source === 'reg') {
    map[`review_json.${f.key}`] = f.label
  }
}

export function buildContractReviewFieldLabels(): Record<string, string> {
  const map: Record<string, string> = {
    status: '状态',
    review_code: '评审编号',
    custom_fields_json: '扩展字段',
  }
  for (const sec of CONTRACT_REVIEW_SECTIONS) {
    for (const f of reviewSectionAllFields(sec)) {
      addField(map, f)
    }
  }
  return map
}

/** 从低代码字段定义构建 id → label */
export function buildFormFieldLabels(
  fields: Array<{ id?: string; label?: string }> | undefined,
): Record<string, string> {
  const map: Record<string, string> = {}
  for (const f of fields || []) {
    if (f.id && f.label) map[f.id] = f.label
  }
  return map
}

/** 从工作流实例详情推断数据日志 resource 参数 */
export function dataLogFromWfDetail(
  detail: {
    id?: string | null
    biz_type?: string | null
    biz_id?: string | null
    form_instance_id?: string | null
    form_fields?: Array<{ id?: string; label?: string }>
  },
): {
  resourceType: string
  resourceId: string
  fieldLabels?: Record<string, string>
  alsoResources?: Array<{ resourceType: string; resourceId: string }>
} | undefined {
  const fields = detail.form_fields
  const labels = detail.biz_type === 'contract_review'
    ? buildContractReviewFieldLabels()
    : buildFormFieldLabels(fields)

  if (detail.biz_type && detail.biz_id) {
    return { resourceType: detail.biz_type, resourceId: detail.biz_id, fieldLabels: labels }
  }
  if (detail.form_instance_id) {
    return {
      resourceType: 'form_instance',
      resourceId: detail.form_instance_id,
      fieldLabels: labels,
      // 旧版审批写回曾记到 wf_process_instance，合并展示
      alsoResources: detail.id
        ? [{ resourceType: 'wf_process_instance', resourceId: detail.id }]
        : undefined,
    }
  }
  return undefined
}
