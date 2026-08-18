/** 手工新建商机仅开放给系统账号 admin；其余用户从线索转化。 */
export const DIRECT_OPPORTUNITY_CREATE_USERNAME = 'admin'

export function canDirectCreateOpportunity(
  user: { username?: string | null } | null | undefined,
): boolean {
  return (user?.username || '').toLowerCase() === DIRECT_OPPORTUNITY_CREATE_USERNAME
}
