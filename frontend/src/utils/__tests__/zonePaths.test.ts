import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { formModuleInstancePath } from '@/utils/workflowBizPath'
import { taskNavigatePath } from '@/utils/taskNavigation'
import { toZonePath, mobileZoneRedirectTarget } from '@/utils/zonePaths'

describe('toZonePath', () => {
  it('maps PC paths to /m on mobile zone', () => {
    expect(toZonePath('/prod-card-supplements?instance=abc', 'mobile')).toBe(
      '/m/prod-card-supplements?instance=abc',
    )
    expect(toZonePath('/customers/c1', 'mobile')).toBe('/m/customers/c1')
    expect(toZonePath('/analytics', 'mobile')).toBe('/m/analytics')
    expect(toZonePath('/m/leads/1', 'mobile')).toBe('/m/leads/1')
  })

  it('keeps PC paths on web zone', () => {
    expect(toZonePath('/prod-card-supplements', 'web')).toBe('/prod-card-supplements')
  })
})

describe('formModuleInstancePath mobile', () => {
  it('prefixes /m when mobile=true', () => {
    expect(
      formModuleInstancePath('prod_card_supplement', 'inst-1', { mobile: true }),
    ).toBe('/m/prod-card-supplements?instance=inst-1')
  })
})

describe('taskNavigatePath', () => {
  it('returns mobile paths when mobile zone', () => {
    expect(taskNavigatePath({ biz_type: 'project', biz_id: 'p1' }, true)).toBe('/m/opportunities/p1')
    expect(taskNavigatePath({ biz_type: 'contract', biz_id: 'c1' }, true)).toBe('/m/contracts/c1')
  })
})

describe('mobileZoneRedirectTarget', () => {
  const orig = window.location

  beforeEach(() => {
    vi.stubGlobal('location', {
      ...orig,
      pathname: '/prod-card-supplements',
      search: '?instance=x',
      hash: '',
    })
  })

  afterEach(() => {
    vi.stubGlobal('location', orig)
  })

  it('preserves path and query when redirecting mobile domain', () => {
    expect(mobileZoneRedirectTarget()).toBe('/m/prod-card-supplements?instance=x')
  })
})
