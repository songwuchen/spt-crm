import { create } from 'zustand'
import type { UserInfo } from '@/api/types'

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: UserInfo | null
  userLoading: boolean
  setAuth: (token: string, refreshToken: string) => void
  setUser: (user: UserInfo) => void
  setUserLoading: (loading: boolean) => void
  logout: () => void
  hasPermission: (perm: string) => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: null,
  userLoading: true,

  setAuth: (token, refreshToken) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('refresh_token', refreshToken)
    set({ token, refreshToken })
  },

  setUser: (user) => set({ user, userLoading: false }),

  setUserLoading: (loading) => set({ userLoading: loading }),

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ token: null, refreshToken: null, user: null, userLoading: false })
  },

  hasPermission: (perm) => {
    const { user } = get()
    return user?.permissions?.includes(perm) ?? false
  },
}))
