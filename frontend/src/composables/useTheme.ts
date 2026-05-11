/**
 * useTheme — 给组件用的 thin wrapper,暴露 themeStore 的核心 API
 */
import { storeToRefs } from 'pinia'
import { useThemeStore } from '@/stores/themeStore'

export function useTheme() {
  const store = useThemeStore()
  const { mode, effective, systemDark } = storeToRefs(store)
  return {
    mode,
    effective,
    systemDark,
    setMode: store.setMode,
    toggle: store.toggle,
  }
}
