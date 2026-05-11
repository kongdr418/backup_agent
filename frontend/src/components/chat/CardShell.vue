<template>
  <button
    class="card-shell"
    :class="[`hue-${hue}`, isExpanded ? 'is-expanded' : '']"
    :disabled="disabled"
    @click="$emit('toggle')"
  >
    <!-- 左:模块色徽章 -->
    <div class="badge">
      <component :is="icon" class="w-4 h-4" />
    </div>

    <!-- 中:文本 -->
    <div class="text">
      <div class="title-row">
        <span class="title">{{ title }}</span>
        <span v-if="isExpanded" class="active-pill">查看中</span>
      </div>
      <div v-if="subtitle" class="subtitle">{{ subtitle }}</div>
      <div v-if="stats" class="stats">{{ stats }}</div>
    </div>

    <!-- 右:展开图标 -->
    <div class="action">
      <ChevronRight class="chev" :class="isExpanded ? 'open' : ''" />
    </div>
  </button>
</template>

<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'

defineProps<{
  hue: 'chat' | 'ppt' | 'library' | 'memory' | 'settings' | 'dashboard'
  icon: unknown
  title: string
  subtitle?: string
  stats?: string
  isExpanded?: boolean
  disabled?: boolean
}>()

defineEmits<{ toggle: [] }>()
</script>

<style scoped>
.card-shell {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  max-width: 480px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  text-align: left;
  cursor: pointer;
  transition:
    transform 120ms cubic-bezier(0.2, 0.8, 0.2, 1),
    border-color 220ms cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}
.card-shell:hover:not(:disabled) {
  border-color: rgb(var(--card-hue) / 0.40);
  box-shadow: 0 4px 12px rgb(var(--card-hue) / 0.12);
  transform: translateY(-1px);
}
.card-shell:active:not(:disabled) {
  transform: translateY(0);
}
.card-shell:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Active(当前展开) */
.card-shell.is-expanded {
  border-color: rgb(var(--card-hue) / 0.55);
  background: rgb(var(--card-hue) / 0.04);
  box-shadow: 0 0 0 3px rgb(var(--card-hue) / 0.10);
}

/* 模块色 */
.hue-chat { --card-hue: var(--hue-chat-rgb); }
.hue-ppt { --card-hue: var(--hue-ppt-rgb); }
.hue-library { --card-hue: var(--hue-library-rgb); }
.hue-memory { --card-hue: var(--hue-memory-rgb); }
.hue-settings { --card-hue: var(--hue-settings-rgb); }
.hue-dashboard { --card-hue: var(--hue-dashboard-rgb); }

/* 徽章 */
.badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgb(var(--card-hue) / 0.12);
  color: rgb(var(--card-hue));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 文本 */
.text {
  flex: 1;
  min-width: 0;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  letter-spacing: -0.01em;
}
.active-pill {
  font-size: 10px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 9999px;
  background: rgb(var(--card-hue) / 0.15);
  color: rgb(var(--card-hue));
  letter-spacing: 0.02em;
}
.subtitle {
  font-size: 12.5px;
  color: rgb(var(--ink-3-rgb));
  margin-top: 2px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stats {
  font-size: 11.5px;
  color: rgb(var(--ink-4-rgb));
  margin-top: 4px;
}

/* 右侧 */
.action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  color: rgb(var(--ink-3-rgb));
}
.chev {
  width: 18px;
  height: 18px;
  transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.chev.open {
  transform: rotate(90deg);
  color: rgb(var(--card-hue));
}
</style>
