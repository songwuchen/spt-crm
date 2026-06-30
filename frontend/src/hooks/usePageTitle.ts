import { useEffect } from 'react'
import { useUiSettingsStore } from '@/stores/useUiSettingsStore'

const DEFAULT_APP_NAME = 'SPT-CRM'

export function usePageTitle(title?: string) {
  const systemName = useUiSettingsStore((s) => s.systemName)
  const appName = systemName || DEFAULT_APP_NAME
  useEffect(() => {
    document.title = title ? `${title} - ${appName}` : appName
    return () => { document.title = appName }
  }, [title, appName])
}
