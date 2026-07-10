import { ref, watchEffect } from 'vue'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'kk-mis-theme'

function getInitialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY) as Theme | null
  if (saved === 'light' || saved === 'dark') return saved
  // 跟随系统偏好
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const theme = ref<Theme>(getInitialTheme())

function applyTheme(t: Theme) {
  const html = document.documentElement
  if (t === 'dark') {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
  // 同步 color-scheme，让浏览器原生控件（滚动条等）跟随
  html.style.colorScheme = t
}

/**
 * 主题切换 composable：亮/暗切换，持久化到 localStorage，首次跟随系统偏好。
 */
export function useTheme() {
  watchEffect(() => {
    applyTheme(theme.value)
    localStorage.setItem(STORAGE_KEY, theme.value)
  })

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  return { theme, toggleTheme }
}
