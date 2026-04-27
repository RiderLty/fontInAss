import { ref, computed, watch } from 'vue'
import { theme as antTheme } from 'ant-design-vue'

const THEME_KEY = 'theme'

const themeMode = ref(localStorage.getItem(THEME_KEY) || 'auto')

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const systemDark = ref(mediaQuery.matches)
mediaQuery.addEventListener('change', (e) => { systemDark.value = e.matches })

const isDark = computed(() => {
  if (themeMode.value === 'auto') return systemDark.value
  return themeMode.value === 'dark'
})

const algorithm = computed(() => {
  return isDark.value ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm
})

watch(themeMode, (v) => {
  localStorage.setItem(THEME_KEY, v)
})

function setTheme(mode) {
  themeMode.value = mode
}

function cycleTheme() {
  const order = ['light', 'dark', 'auto']
  const idx = order.indexOf(themeMode.value)
  themeMode.value = order[(idx + 1) % 3]
}

export function useTheme() {
  return { themeMode, isDark, algorithm, setTheme, cycleTheme }
}
