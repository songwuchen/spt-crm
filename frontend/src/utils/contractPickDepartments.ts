/** 合同选择弹窗：多部门编制用户并集过滤，不单看表单一个「所在部门」。 */
import type { UserInfo } from '@/api/types'

export function contractPickDepartments(
  user?: Pick<UserInfo, 'department_id' | 'department_ids'> | null,
  formDepartmentId?: string,
): { departmentId?: string; departmentIds?: string[]; multiDept: boolean } {
  const ids = (user?.department_ids || []).map(String).filter(Boolean)
  if (ids.length > 1) {
    return { departmentIds: ids, multiDept: true }
  }
  const single = formDepartmentId || ids[0] || user?.department_id || undefined
  return { departmentId: single, multiDept: false }
}
