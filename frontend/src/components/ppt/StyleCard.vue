<template>
  <button
    class="style-bar"
    :class="selected ? 'is-selected' : ''"
    @click="$emit('select')"
  >
    <div class="style-icon" :class="iconBgCls">
      <component :is="icon" class="w-4 h-4" :class="iconCls" />
    </div>
    <div class="style-text">
      <div class="style-label">{{ label }}</div>
      <div class="style-desc">{{ description }}</div>
    </div>
    <Check v-if="selected" class="w-4 h-4 text-ink-1 shrink-0" />
  </button>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps<{
  label: string
  description: string
  icon: Component
  tone: 'slate' | 'emerald' | 'amber' | 'sky' | 'violet'
  selected: boolean
}>()

defineEmits<{ select: [] }>()

const TONE_BG = {
  slate: 'bg-slate-50',
  emerald: 'bg-emerald-50',
  amber: 'bg-amber-50',
  sky: 'bg-sky-50',
  violet: 'bg-violet-50',
} as const

const TONE_FG = {
  slate: 'text-slate-700',
  emerald: 'text-emerald-700',
  amber: 'text-amber-700',
  sky: 'text-sky-700',
  violet: 'text-violet-700',
} as const

const iconBgCls = computed(() => TONE_BG[props.tone])
const iconCls = computed(() => TONE_FG[props.tone])
</script>

<style scoped>
.style-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  text-align: left;
  cursor: pointer;
  transition:
    border-color 200ms ease,
    background-color 200ms ease,
    box-shadow 200ms ease;
}
.style-bar:hover {
  border-color: rgb(var(--ink-4-rgb));
}
.style-bar.is-selected {
  border-color: rgb(var(--ink-1-rgb));
  background: rgb(var(--bg-subtle-rgb));
  box-shadow: 0 0 0 1px rgb(var(--ink-2-rgb) / 0.1);
}

.style-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.style-text {
  flex: 1;
  min-width: 0;
}
.style-label {
  font-size: 13px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.3;
}
.style-desc {
  font-size: 11.5px;
  color: rgb(var(--ink-3-rgb));
  margin-top: 2px;
  line-height: 1.4;
}
</style>
