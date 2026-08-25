import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'
import { amountToChineseUpper, buildQuotePrintHtml, plainCustomerDisplayName } from '@/pages/quote/quotePrint'

describe('quote print template', () => {
  it('strips customer code from display name', () => {
    expect(plainCustomerDisplayName('河北安丰钢铁集团有限公司 (C-20260706003)'))
      .toBe('河北安丰钢铁集团有限公司')
    expect(plainCustomerDisplayName('某某公司（C001）')).toBe('某某公司')
  })

  it('renders company header and customer name only', () => {
    const html = buildQuotePrintHtml({
      formData: {
        serial_no: 'HJ20260820015',
        customer_name: 'cust-id',
        sales_person: '张攀',
        price_lines: [
          { product_name: '香蕉筛', spec_model: 'WZXD-3073', qty: 1, unit: '台' },
        ],
        special_reminder: '不含电控',
      },
      labels: {
        users: {},
        customers: { 'cust-id': '河北安丰钢铁集团有限公司 (C-20260706003)' },
      },
      printDate: dayjs('2026-08-25'),
    })
    expect(html).toContain('河南威猛振动设备股份有限公司')
    expect(html).toContain('河北安丰钢铁集团有限公司')
    expect(html).not.toContain('C-20260706003')
    expect(html).toContain('发件人：')
    expect(html).toContain('联系人：')
    expect(html).toContain('致：')
    expect(html).toContain('&nbsp;&nbsp;您好：')
    expect(html).not.toContain('发&nbsp;&nbsp;件')
  })

  it('computes total and uppercase amount', () => {
    const html = buildQuotePrintHtml({
      formData: {
        price_lines: [
          { product_name: '电机', qty: 2, unit: '台', unit_price: 5000 },
        ],
      },
      labels: { users: {}, customers: {} },
    })
    expect(html).toContain('10,000.00')
    expect(amountToChineseUpper(10000)).toContain('壹')
    expect(amountToChineseUpper(10000)).toContain('元')
  })
})
