import { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '@/stores/useAuthStore'
import client from '@/api/client'

interface FieldRule {
  resource: string   // e.g. 'customer', 'project', 'contract'
  field: string      // e.g. 'phone', 'amount', 'email'
  roles: string[]    // roles this rule applies to (if user has ANY of these roles, rule is active)
  action: 'hide' | 'mask'  // hide = remove entirely, mask = show ***
}

let cachedRules: FieldRule[] | null = null
let fetchPromise: Promise<void> | null = null

export function useFieldPermission() {
  const [rules, setRules] = useState<FieldRule[]>(cachedRules || [])
  const user = useAuthStore((s) => s.user)
  const userRoles = user?.roles || []

  useEffect(() => {
    if (cachedRules !== null) {
      setRules(cachedRules)
      return
    }
    if (!fetchPromise) {
      fetchPromise = client.get('/api/admin/v1/tenant/field_rules')
        .then((res: any) => {
          cachedRules = res.data || []
          setRules(cachedRules!)
        })
        .catch(() => {
          cachedRules = []
          setRules([])
        })
        .finally(() => { fetchPromise = null })
    }
    fetchPromise.then(() => setRules(cachedRules || []))
  }, [])

  const getFieldAction = useCallback((resource: string, field: string): 'visible' | 'hide' | 'mask' => {
    for (const rule of rules) {
      if (rule.resource === resource && rule.field === field) {
        if (rule.roles.some((r) => userRoles.includes(r))) {
          return rule.action
        }
      }
    }
    return 'visible'
  }, [rules, userRoles])

  const renderField = useCallback((resource: string, field: string, value: unknown): string | null => {
    const action = getFieldAction(resource, field)
    if (action === 'hide') return null
    if (action === 'mask') {
      const str = String(value || '')
      if (str.length <= 2) return '***'
      return str[0] + '***' + str[str.length - 1]
    }
    return String(value ?? '')
  }, [getFieldAction])

  return { getFieldAction, renderField }
}

/** Reset cached rules (call after admin updates rules) */
export function resetFieldRulesCache() {
  cachedRules = null
}
