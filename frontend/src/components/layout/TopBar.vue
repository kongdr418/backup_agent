<template>
  <header class="topbar glass-chrome">
    <div class="topbar-inner">
      <!-- Logo -->
      <router-link to="/" class="logo-cell">
        <div class="logo-dot">
          <Sparkles class="w-[14px] h-[14px]" />
        </div>
        <span class="logo-text">智课源</span>
      </router-link>

      <!-- 主导航 -->
      <nav class="nav-stack">
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
  Sparkles,
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

/* Logo */
.logo-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  flex-shrink: 0;
  padding: 4px 6px;
  border-radius: 10px;
  transition: background-color var(--duration-base) var(--ease-spring);
}
.logo-cell:hover {
  background: rgb(var(--bg-subtle-rgb) / 0.5);
}
.logo-dot {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    135deg,
    rgb(var(--accent-rgb)) 0%,
    rgb(var(--hue-ppt-rgb)) 100%
  );
  color: white;
  box-shadow: 0 2px 8px -2px rgb(var(--accent-rgb) / 0.4);
}
.logo-text {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: rgb(var(--ink-1-rgb));
  white-space: nowrap;
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
  color: rgb(var(--ink-2-rgb));
  text-decoration: none;
  transition:
    color var(--duration-base) var(--ease-spring),
    background-color var(--duration-base) var(--ease-spring),
    transform var(--duration-quick) var(--ease-spring);
  white-space: nowrap;
}
.nav-pill:hover {
  color: rgb(var(--ink-1-rgb));
  background: rgb(var(--bg-subtle-rgb) / 0.7);
}
.nav-pill:active {
  transform: scale(0.97);
}

/* Active 状态 — 用模块 hue */
.nav-pill.is-active {
  color: rgb(var(--hue-active));
  background: rgb(var(--hue-active) / 0.10);
  font-weight: 500;
  position: relative;
}
.nav-pill.is-active::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 18px;
  height: 2px;
  border-radius: 0 0 3px 3px;
  background: rgb(var(--hue-active));
}

/* hue 类 — 把 --hue-active 切到对应模块 */
.hue-dashboard { --hue-active: var(--hue-dashboard-rgb); }
.hue-chat { --hue-active: var(--hue-chat-rgb); }
.hue-ppt { --hue-active: var(--hue-ppt-rgb); }
.hue-library { --hue-active: var(--hue-library-rgb); }
.hue-memory { --hue-active: var(--hue-memory-rgb); }
.hue-settings { --hue-active: var(--hue-settings-rgb); }

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
  color: rgb(var(--ink-2-rgb));
  background: transparent;
  border: none;
  cursor: pointer;
  transition:
    background-color var(--duration-base) var(--ease-spring),
    color var(--duration-base) var(--ease-spring),
    transform var(--duration-quick) var(--ease-spring);
}
.action-btn:hover {
  background: rgb(var(--bg-subtle-rgb) / 0.7);
  color: rgb(var(--ink-1-rgb));
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
  color: rgb(var(--ink-2-rgb));
  border: 1px solid rgb(var(--line-rgb));
  margin-left: 4px;
}

/* 窄屏兜底:nav 自适应折叠(简化处理 — 隐藏文字) */
@media (max-width: 1024px) {
  .nav-pill span { display: none; }
  .nav-pill { padding: 0 9px; }
  .logo-text { display: none; }
}
</style>
