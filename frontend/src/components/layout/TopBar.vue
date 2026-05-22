<template>
  <header class="topbar glass-chrome">
    <div class="topbar-inner">
      <!-- 主导航 -->
      <nav class="nav-stack">
        <router-link to="/" class="nav-pill logo-pill">
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
        >
          <component :is="item.icon" class="w-[14px] h-[14px] shrink-0" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 右侧动作 -->
      <div class="right-stack">
        <button
          class="action-btn"
          :title="`主题: ${mode} (生效: ${effective})`"
          @click="toggle"
        >
          <Sun v-if="effective === 'dark'" class="w-[16px] h-[16px]" />
          <Moon v-else class="w-[16px] h-[16px]" />
        </button>

        <div class="avatar-dot" title="账户">
          <User class="w-[14px] h-[14px]" />
        </div>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  LayoutDashboard,
  MessageSquare,
  Presentation,
  Video,
  FolderOpen,
  Brain,
  Settings,
  Sun,
  Moon,
  User,
} from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const { mode, effective, toggle } = useTheme()

type NavItem = {
  path: string
  label: string
  icon: unknown
  hue: 'dashboard' | 'chat' | 'ppt' | 'library' | 'memory' | 'settings'
}

const nav: NavItem[] = [
  { path: '/', label: '仪表盘', icon: LayoutDashboard, hue: 'dashboard' },
  { path: '/chat', label: '对话', icon: MessageSquare, hue: 'chat' },
  { path: '/ppt-studio', label: 'PPT 工作台', icon: Presentation, hue: 'ppt' },
  { path: '/video-studio', label: '微课', icon: Video, hue: 'ppt' },
  { path: '/library', label: '文件库', icon: FolderOpen, hue: 'library' },
  // { path: '/memory', label: '记忆', icon: Brain, hue: 'memory' },
  { path: '/settings', label: '设置', icon: Settings, hue: 'settings' },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

// expose for template
defineExpose({ mode, effective })
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
  position: relative;
}

.nav-pill.is-active::before,
.logo-pill.is-active::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 18px;
  height: 2px;
  border-radius: 0 0 3px 3px;
  background: var(--hue-active);
}

/* hue class — switch --hue-active to the module color */
.hue-dashboard { --hue-active: var(--nav-chat); }
.hue-chat { --hue-active: var(--nav-chat); }
.hue-ppt { --hue-active: var(--nav-ppt); }
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
}

/* 窄屏兜底:nav 自适应折叠(简化处理 — 隐藏文字) */
@media (max-width: 1024px) {
  .nav-pill span { display: none; }
  .nav-pill { padding: 0 9px; }
  .logo-pill span { display: none; }
  .logo-pill { padding: 0 9px; }
}
</style>
