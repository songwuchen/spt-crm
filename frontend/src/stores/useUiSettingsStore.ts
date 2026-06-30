import { create } from 'zustand'
import { settingsApi } from '@/api/settings'

export interface UiSettings {
  system_name: string | null
  menu_aliases: Record<string, string>
  hidden_menus: string[]
}

interface UiSettingsState {
  systemName: string | null
  menuAliases: Record<string, string>
  hiddenMenus: string[]
  loaded: boolean
  /** 登录后拉取一次（任意用户可读）。失败时静默回退默认。 */
  load: () => Promise<void>
  /** 保存成功后即时刷新本地状态，使侧边栏/品牌名立即生效。 */
  apply: (s: Partial<UiSettings>) => void
}

export const useUiSettingsStore = create<UiSettingsState>((set) => ({
  systemName: null,
  menuAliases: {},
  hiddenMenus: [],
  loaded: false,

  load: async () => {
    try {
      const res = (await settingsApi.getUiSettings()) as unknown as { data?: UiSettings }
      const d = res.data || ({} as UiSettings)
      set({
        systemName: d.system_name ?? null,
        menuAliases: d.menu_aliases ?? {},
        hiddenMenus: d.hidden_menus ?? [],
        loaded: true,
      })
    } catch {
      set({ loaded: true })
    }
  },

  apply: (s) => set({
    systemName: s.system_name ?? null,
    menuAliases: s.menu_aliases ?? {},
    hiddenMenus: s.hidden_menus ?? [],
  }),
}))
