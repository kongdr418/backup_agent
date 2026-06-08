<template>
  <header class="topbar glass-chrome">
    <div class="topbar-inner">
      <!-- 主导航 -->
      <nav ref="navRef" class="nav-stack">
        <router-link to="/" class="nav-pill logo-pill" :ref="el => setPillRef('/', el)">
          <img src="@/assets/logo.svg" alt="智创空间" class="h-11 w-auto" />
          <span class="logo-text">智创空间</span>
        </router-link>

        <router-link
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          class="nav-pill"
          :class="[
            isActive(item.path) ? `is-active hue-${item.hue}` : '',
          ]"
          :ref="el => setPillRef(item.path, el)"
        >
          <component :is="item.icon" class="w-[14px] h-[14px] shrink-0" />
          <span>{{ item.label }}</span>
        </router-link>

        <span ref="indicatorRef" class="nav-indicator" />
      </nav>

      <!-- 右侧动作 -->
      <div class="right-stack">
        <button
          class="action-btn"
          title="设置"
          @click="$emit('openSettings')"
        >
          <Settings class="w-[16px] h-[16px]" />
        </button>
        <button class="avatar-dot" title="学习者中心" @click="router.push('/student-profile')">
          <User class="w-[14px] h-[14px]" />
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  MessageSquare,
  Presentation,
  Video,
  GraduationCap,
  FolderOpen,
  Settings,
  User,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

type NavItem = {
  path: string
  label: string
  icon: unknown
  hue: 'dashboard' | 'chat' | 'ppt' | 'video' | 'classroom' | 'library' | 'memory' | 'settings'
}

const nav: NavItem[] = [
  { path: '/', label: '仪表盘', icon: LayoutDashboard, hue: 'dashboard' },
  { path: '/chat', label: '对话', icon: MessageSquare, hue: 'chat' },
  { path: '/ppt-studio', label: 'PPT 工作台', icon: Presentation, hue: 'ppt' },
  { path: '/video-studio', label: '微课', icon: Video, hue: 'video' },
  { path: '/interactive-classroom', label: '智慧课堂', icon: GraduationCap, hue: 'classroom' },
  { path: '/library', label: '文件库', icon: FolderOpen, hue: 'library' },
  // { path: '/memory', label: '记忆', icon: Brain, hue: 'memory' },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

/* ── Sliding indicator ── */
const navRef = ref<HTMLElement | null>(null)
const indicatorRef = ref<HTMLElement | null>(null)
const pillRefs: Record<string, HTMLElement> = {}

const INDICATOR_COLORS: Record<string, string> = {
  '/': 'var(--nav-dashboard)',
  '/chat': 'var(--nav-chat)',
  '/ppt-studio': 'var(--nav-ppt)',
  '/video-studio': 'var(--nav-video)',
  '/interactive-classroom': 'var(--nav-classroom)',
  '/library': 'var(--nav-library)',
  '/memory': 'var(--nav-memory)',
}

function setPillRef(path: string, el: any) {
  if (el?.$el) el = el.$el
  if (el) pillRefs[path] = el
}

let firstMove = true

const INDICATOR_W = 18

function showIndicator() {
  const indicator = indicatorRef.value
  if (!indicator) return
  firstMove = false
  indicator.style.opacity = '1'
  nextTick(() => { indicator.style.transition = '' })
}

function moveIndicator() {
  const nav = navRef.value
  const indicator = indicatorRef.value
  if (!nav || !indicator) return

  const activePath = route.path === '/'
    ? '/'
    : Object.keys(pillRefs).find(
        (p) => p !== '/' && (route.path === p || route.path.startsWith(p + '/')),
      ) || '/'

  const pill = pillRefs[activePath]
  if (!pill) return

  const navRect = nav.getBoundingClientRect()
  const pillRect = pill.getBoundingClientRect()
  const color = INDICATOR_COLORS[activePath] || 'var(--forest)'

  // Center the 18px indicator over the pill
  const pillCenter = pillRect.left - navRect.left + pillRect.width / 2
  const left = pillCenter - INDICATOR_W / 2

  if (firstMove) {
    indicator.style.transition = 'none'
    indicator.style.left = left + 'px'
    indicator.style.background = color
    // 首次加载不立即显示，等二次校正后由 showIndicator() 统一显示
  } else {
    indicator.style.left = left + 'px'
    indicator.style.background = color
    indicator.style.opacity = '1'
  }
}

onMounted(() => {
  nextTick(() => {
    moveIndicator()
    requestAnimationFrame(() => { moveIndicator(); showIndicator() })
  })
})
watch(() => route.fullPath, () => nextTick(moveIndicator))

// expose for template
defineExpose({})
</script>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  height: 56px;
  width: 100%;
}

.topbar-inner {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 18px;
  gap: 14px;
}

/* Logo pill */
.logo-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 34px;
  border-radius: 9px;
  text-decoration: none;
  transition:
    color var(--duration-base) var(--ease-out),
    background-color var(--duration-base) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}
.logo-text {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 13px;
  font-weight: 400;
  letter-spacing: -0.01em;
  color: var(--ink-primary);
  white-space: nowrap;
  line-height: 1;
  height: 19.5px;
  margin-top: 3px;
}

/* Nav stack */
.nav-stack {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 6px;
  flex: 1;
}

.nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 34px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--ink-secondary);
  text-decoration: none;
  transition:
    color var(--duration-base) var(--ease-out),
    background-color var(--duration-base) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}
.nav-pill:hover {
  color: var(--ink-primary);
  background: rgb(var(--bg-subtle-rgb) / 0.7);
}
.nav-pill:active {
  transform: scale(0.97);
}

/* Active state — warm palette colors */
.nav-pill.is-active,
.logo-pill.is-active {
  color: var(--hue-active);
  background: rgb(var(--hue-active) / 0.10);
  font-weight: 500;
}

/* Sliding indicator bar */
.nav-indicator {
  position: absolute;
  top: 0;
  width: 18px;
  height: 2px;
  border-radius: 0 0 3px 3px;
  transition: left 350ms var(--ease-out), background 350ms, opacity 200ms;
  pointer-events: none;
  opacity: 0;
}

/* hue class — switch --hue-active to the module color */
.hue-dashboard { --hue-active: var(--nav-dashboard); }
.hue-chat { --hue-active: var(--nav-chat); }
.hue-ppt { --hue-active: var(--nav-ppt); }
.hue-video { --hue-active: var(--nav-video); }
.hue-classroom { --hue-active: var(--nav-classroom); }
.hue-library { --hue-active: var(--nav-library); }
.hue-memory { --hue-active: var(--nav-memory); }
.hue-settings { --hue-active: var(--nav-settings); }

/* Right actions */
.right-stack {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition:
    background-color var(--duration-base) var(--ease-out),
    color var(--duration-base) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
}
.action-btn:hover {
  background: rgb(var(--bg-subtle-rgb) / 0.7);
  color: var(--ink-primary);
}
.action-btn:active {
  transform: scale(0.92);
}

.avatar-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--bg-subtle-rgb));
  color: var(--ink-secondary);
  border: 1px solid var(--line);
  margin-left: 4px;
  padding: 0;
  cursor: pointer;
  transition:
    background-color var(--duration-base) var(--ease-out),
    color var(--duration-base) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
}

.avatar-dot:hover {
  background: rgb(var(--bg-subtle-rgb) / 0.7);
  color: var(--ink-primary);
}

.avatar-dot:active {
  transform: scale(0.94);
}

/* 窄屏兜底:nav 自适应折叠(简化处理 — 隐藏文字) */
@media (max-width: 1024px) {
  .nav-pill span { display: none; }
  .nav-pill { padding: 0 9px; }
  .logo-pill span { display: none; }
  .logo-pill { padding: 0 9px; }
}

/* 手机端：隐藏 TopBar，导航由底部 MobileBottomNav 接管 */
@media (max-width: 767px) {
  .topbar {
    display: none !important;
  }
}
</style>
