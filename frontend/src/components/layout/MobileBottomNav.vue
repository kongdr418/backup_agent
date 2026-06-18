<template>
  <nav class="mobile-bottom-nav">
    <router-link
      v-for="item in tabs"
      :key="item.path"
      :to="item.path"
      class="mobile-nav-item"
      :class="{ active: isActive(item.path) }"
    >
      <component :is="item.icon" class="mobile-nav-icon" />
      <span class="mobile-nav-label">{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  LayoutDashboard,
  MessageSquare,
  Presentation,
  GraduationCap,
  BookMarked,
  FolderOpen,
  Settings,
} from 'lucide-vue-next'

const route = useRoute()

const tabs = [
  { path: '/', label: '仪表盘', icon: LayoutDashboard },
  { path: '/chat', label: '对话', icon: MessageSquare },
  { path: '/ppt-studio', label: 'PPT', icon: Presentation },
  { path: '/interactive-classroom', label: '课堂', icon: GraduationCap },
  { path: '/study-tools', label: '学习', icon: BookMarked },
  { path: '/library', label: '文件库', icon: FolderOpen },
  { path: '/settings', label: '设置', icon: Settings },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<style scoped>
.mobile-bottom-nav {
  display: none; /* hidden by default, shown on mobile via AppShell's media query */
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  height: 64px;
  padding-bottom: env(safe-area-inset-bottom, 0);
  background: var(--bg-surface);
  border-top: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-around;
  /* Tailwind: md:hidden — but we handle in AppShell, so use component media query as fallback */
}

@media (min-width: 768px) {
  .mobile-bottom-nav {
    display: none !important;
  }
}

@media (max-width: 767px) {
  .mobile-bottom-nav {
    display: flex;
  }
}

.mobile-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 4px 10px;
  min-width: 56px;
  min-height: 44px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--ink-tertiary);
  transition: color 150ms ease;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.mobile-nav-item.active {
  color: var(--accent);
  font-weight: 500;
}

.mobile-nav-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

.mobile-nav-label {
  font-size: 10px;
  line-height: 1;
  letter-spacing: 0.01em;
}
</style>
