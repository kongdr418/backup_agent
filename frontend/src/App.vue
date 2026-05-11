<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <div class="app-root app-mesh">
          <router-view />
        </div>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  darkTheme,
} from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useTheme } from '@/composables/useTheme'

const { effective } = useTheme()

const naiveTheme = computed(() => (effective.value === 'dark' ? darkTheme : null))

/**
 * Naive UI 用 seemly/rgba 解析颜色,不支持 CSS var,必须传具体 hex/rgb
 * 这里维护两套色板;CSS 层(组件 / Tailwind)仍由 tokens.css 驱动。
 */
const PALETTE = {
  light: {
    primary: '#0a84ff',
    primaryHover: '#0071f0',
    primaryPressed: '#0058c0',
    success: '#30d158',
    warning: '#ff9f0a',
    error: '#ff453a',
    info: '#5ac8fa',
    bgBase: '#fafafa',
    bgSurface: '#ffffff',
    ink1: '#111827',
    ink2: '#374151',
    ink3: '#6b7280',
    ink4: '#9ca3af',
    line: '#e5e7eb',
    bgSubtle: '#f5f5f7',
  },
  dark: {
    primary: '#4493ff',
    primaryHover: '#66a8ff',
    primaryPressed: '#0a84ff',
    success: '#4cd964',
    warning: '#ffaf38',
    error: '#ff6961',
    info: '#64d2ff',
    bgBase: '#0b0d10',
    bgSurface: '#16191d',
    ink1: '#f1f5f9',
    ink2: '#d1d5db',
    ink3: '#9ca3af',
    ink4: '#6b7280',
    line: '#26292f',
    bgSubtle: '#1c1f24',
  },
}

const themeOverrides = computed<GlobalThemeOverrides>(() => {
  const p = effective.value === 'dark' ? PALETTE.dark : PALETTE.light
  return {
    common: {
      primaryColor: p.primary,
      primaryColorHover: p.primaryHover,
      primaryColorPressed: p.primaryPressed,
      primaryColorSuppl: p.primary,
      successColor: p.success,
      warningColor: p.warning,
      errorColor: p.error,
      infoColor: p.info,
      bodyColor: p.bgBase,
      cardColor: p.bgSurface,
      modalColor: p.bgSurface,
      popoverColor: p.bgSurface,
      tableColor: p.bgSurface,
      textColorBase: p.ink1,
      textColor1: p.ink1,
      textColor2: p.ink2,
      textColor3: p.ink3,
      placeholderColor: p.ink4,
      dividerColor: p.line,
      borderColor: p.line,
      hoverColor: p.bgSubtle,
      borderRadius: '8px',
      borderRadiusSmall: '6px',
      fontFamily:
        'MiSans, -apple-system, BlinkMacSystemFont, "PingFang SC", "HarmonyOS Sans SC", system-ui, sans-serif',
    },
    Button: {
      borderRadiusMedium: '8px',
      borderRadiusLarge: '10px',
    },
    Input: {
      borderRadius: '8px',
    },
    Card: {
      borderRadius: '12px',
    },
    Drawer: {
      borderRadius: '12px',
    },
    Dialog: {
      borderRadius: '12px',
    },
  }
})
</script>

<style scoped>
.app-root {
  height: 100%;
  overflow: hidden;
  background-color: rgb(var(--bg-base-rgb));
}
</style>
