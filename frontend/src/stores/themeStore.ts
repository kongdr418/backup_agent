/**
 * Theme Store — 'auto' | 'light' | 'dark'
 *
 * - 通过 prefers-color-scheme 监听系统;mode='auto' 时跟随系统
 * - 把 effective mode 写到 documentElement.classList('dark') 上,Tailwind dark: 启用
 * - 持久化到 localStorage('theme')
 * - init() 必须在 mount 前同步调用,避免 FOUC
 */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

type Mode = 'auto' | 'light' | 'dark'
type Effective = 'light' | 'dark'

const STORAGE_KEY = 'ai_creator.theme'

function getInitialMode(): Mode {
  if (typeof window === 'undefined') return 'light'
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'auto' || stored === 'light' || stored === 'dark') return stored
  return 'light'
}

function getSystemDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<Mode>(getInitialMode())
  const systemDark = ref<boolean>(getSystemDark())

  const effective = computed<Effective>(() =>
    mode.value === 'auto' ? (systemDark.value ? 'dark' : 'light') : mode.value,
  )

  let mediaQuery: MediaQueryList | null = null
  let listener: ((e: MediaQueryListEvent) => void) | null = null
  let initialized = false

  /**
   * 在 createApp().mount() 之前同步调用一次,设置首屏 dark class,避免白闪
   */
  function init() {
    if (initialized || typeof window === 'undefined') return
    initialized = true

    // 1. 立刻应用一次(同步,首屏不闪)
    apply(effective.value)

    // 2. 监听系统主题变化(用户在 mode='auto' 时被动响应)
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    listener = (e) => {
      systemDark.value = e.matches
    }
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', listener)
    } else if ((mediaQuery as MediaQueryList).addListener) {
      ;(mediaQuery as MediaQueryList).addListener(listener)
    }

    // 3. 当 effective 变化时(主动切换或系统切换),写 class + localStorage
    watch(effective, (next) => {
      apply(next)
    })

    watch(mode, (next) => {
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* SSR / private mode */
      }
    })
  }

  function apply(eff: Effective) {
    if (typeof document === 'undefined') return
    const root = document.documentElement

    // transition guard:第一次 init 不加过渡(避免首屏渐变);之后切换才加
    if (initialized) {
      root.classList.add('theme-transition')
      window.setTimeout(() => root.classList.remove('theme-transition'), 240)
    }

    root.classList.toggle('dark', eff === 'dark')
    // 设置 color-scheme 让原生控件(form / scrollbar)也跟随
    root.style.colorScheme = eff
  }

  function setMode(next: Mode) {
    mode.value = next
  }

  /** 在 light/dark 之间切换(忽略 auto) */
  function toggle() {
    mode.value = effective.value === 'dark' ? 'light' : 'dark'
  }

  function dispose() {
    if (mediaQuery && listener) {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', listener)
      } else if ((mediaQuery as MediaQueryList).removeListener) {
        ;(mediaQuery as MediaQueryList).removeListener(listener)
      }
    }
    mediaQuery = null
    listener = null
    initialized = false
  }

  return {
    mode,
    systemDark,
    effective,
    init,
    setMode,
    toggle,
    dispose,
  }
})
