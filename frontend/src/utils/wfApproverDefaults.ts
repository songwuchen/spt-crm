import type { FieldDefinition, WfApproverRule } from '@/types/lowcode'

/** 新建抄送节点的默认规则：与内置模板对齐，避免默认落在「指定人员」空选。 */
export function defaultCcApproverRule(formFields: FieldDefinition[]): WfApproverRule {
  const hasApplicant = formFields.some(
    (f) => f.id === 'applicant' && (f.type === 'person' || f.type === 'person_multi'),
  )
  if (hasApplicant) {
    return {
      type: 'mixed',
      value: [
        { type: 'creator' },
        { type: 'form_field_person', value: 'applicant' },
      ],
    }
  }
  return { type: 'creator' }
}
