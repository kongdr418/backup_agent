import { ref, onMounted, onUnmounted } from 'vue'

const MOBILE_BREAKPOINT = 767

const isMobile = ref(false)

function check() {
  isMobile.value = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches
}

export function useBreakpoint() {
  let mql: MediaQueryList | null = null

  onMounted(() => {
    check()
    mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
    mql.addEventListener('change', check)
  })

  onUnmounted(() => {
    if (mql) mql.removeEventListener('change', check)
  })

  return { isMobile }
}

export { isMobile }
