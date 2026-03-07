import { create } from 'zustand'

type Theme = 'light' | 'dark' | 'system'

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
}

function getInitialTheme(): Theme {
  try {
    return (localStorage.getItem('theme') as Theme) || 'light'
  } catch {
    return 'light'
  }
}

function applyTheme(theme: Theme) {
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)

  document.documentElement.classList.toggle('dark', isDark)
  localStorage.setItem('theme', theme)
}

export const useThemeStore = create<ThemeState>((set) => {
  const initial = getInitialTheme()
  applyTheme(initial)

  return {
    theme: initial,
    setTheme: (t) => {
      applyTheme(t)
      set({ theme: t })
    },
  }
})
