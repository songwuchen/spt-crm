/**
 * i18n utility — lightweight translation helper with locale switching.
 *
 * Usage:
 *   import { t, useLocale } from '@/locales'
 *   t('common.save')
 *   const { locale, setLocale } = useLocale()
 */

import { useState, useCallback } from 'react'
import zhCN from './zh-CN'
import enUS from './en-US'

export type LocaleCode = 'zh-CN' | 'en-US'

const localeMap: Record<LocaleCode, Record<string, any>> = {
  'zh-CN': zhCN,
  'en-US': enUS,
}

const STORAGE_KEY = 'app_locale'

function getInitialLocale(): LocaleCode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && saved in localeMap) return saved as LocaleCode
  return 'zh-CN'
}

let _currentCode: LocaleCode = getInitialLocale()
let _currentLocale: Record<string, any> = localeMap[_currentCode]
let _listeners: Array<() => void> = []

/**
 * Translate a dot-separated key path.
 * Returns the key itself if not found.
 * Supports interpolation: t('key', { count: 5 }) replaces {count} in the string.
 */
export function t(key: string, params?: Record<string, string | number>): string {
  const parts = key.split('.')
  let current: any = _currentLocale
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return key
    current = current[part]
  }
  let result = typeof current === 'string' ? current : key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      result = result.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  return result
}

/**
 * Set the active locale.
 */
export function setLocale(code: LocaleCode) {
  if (code === _currentCode) return
  _currentCode = code
  _currentLocale = localeMap[code] || localeMap['zh-CN']
  localStorage.setItem(STORAGE_KEY, code)
  _listeners.forEach((fn) => fn())
}

/**
 * Get current locale code.
 */
export function getLocale(): LocaleCode {
  return _currentCode
}

/**
 * React hook for reactive locale switching.
 * Components using this will re-render when locale changes.
 */
export function useLocale() {
  const [, forceUpdate] = useState(0)

  // Subscribe to locale changes
  const refresh = useCallback(() => forceUpdate((n) => n + 1), [])
  if (!_listeners.includes(refresh)) {
    _listeners.push(refresh)
  }

  return {
    locale: _currentCode,
    setLocale,
    t,
  }
}

export const localeLabels: Record<LocaleCode, string> = {
  'zh-CN': '简体中文',
  'en-US': 'English',
}

export { default as zhCN } from './zh-CN'
export { default as enUS } from './en-US'
