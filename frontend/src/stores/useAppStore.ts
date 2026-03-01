import { create } from 'zustand'

interface AppState {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: window.innerWidth < 768,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
}))
