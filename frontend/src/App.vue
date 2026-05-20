<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <div class="app-root app-mesh-warm">
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
    primary: '#2D5016',
    primaryHover: '#4A7C2B',
    primaryPressed: '#1C3910',
    success: '#2D5016',
    warning: '#92400E',
    error: '#B84A2B',
    info: '#1E4D6B',
    bgBase: '#FAF7F2',
    bgSurface: '#FFFFFF',
    ink1: '#1C1917',
    ink2: '#57534E',
    ink3: '#A8A29E',
    ink4: '#D6D3D1',
    line: '#E7E5E4',
    bgSubtle: '#F2EDE5',
  },
  dark: {
    primary: '#7CBF5E',
    primaryHover: '#9FD482',
    primaryPressed: '#7CBF5E',
    success: '#7CBF5E',
    warning: '#E8B85A',
    error: '#E87B5A',
    info: '#64D2FF',
    bgBase: '#131110',
    bgSurface: '#1C1917',
    ink1: '#FAF7F2',
    ink2: '#A8A29E',
    ink3: '#78716C',
    ink4: '#57534E',
    line: '#2C2825',
    bgSubtle: '#252220',
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
