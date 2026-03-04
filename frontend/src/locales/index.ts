/**
 * i18n utility — lightweight translation helper.
 *
 * Currently only supports zh-CN. Designed to be extended with additional
 * locales (en-US, etc.) when needed.
 *
 * Usage:
 *   import { t } from '@/locales'
 *   t('common.save')        // '保存'
 *   t('opportunity.stages.S1') // '线索确认'
 */

import zhCN from './zh-CN'

type NestedKeys<T, Prefix extends string = ''> = T extends string
  ? Prefix
  : {
      [K in keyof T & string]: NestedKeys<T[K], Prefix extends '' ? K : `${Prefix}.${K}`>
    }[keyof T & string]

// Current locale — can be made reactive later
let _currentLocale: Record<string, any> = zhCN

/**
 * Set the active locale object.
 */
export function setLocale(locale: Record<string, any>) {
  _currentLocale = locale
}

/**
 * Translate a dot-separated key path.
 * Returns the key itself if not found.
 */
export function t(key: string): string {
  const parts = key.split('.')
  let current: any = _currentLocale
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return key
    current = current[part]
  }
  return typeof current === 'string' ? current : key
}

export { default as zhCN } from './zh-CN'
