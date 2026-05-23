<template>
  <button
    class="style-bar"
    :class="{ 'is-selected': selected }"
    @click="$emit('select')"
  >
    <div class="style-icon">
      <component :is="icon" class="w-4 h-4" />
    </div>
    <div class="style-text">
      <div class="style-label">{{ label }}</div>
      <div class="style-desc">{{ description }}</div>
    </div>
    <Check v-if="selected" class="w-4 h-4 shrink-0" />
  </button>
</template>

<script setup lang="ts">
import { type Component } from 'vue'
import { Check } from 'lucide-vue-next'

defineProps<{
  label: string
  description: string
  icon: Component
  selected: boolean
}>()

defineEmits<{ select: [] }>()
</script>

<style scoped>
.style-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
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
  border-color: rgb(var(--line-strong-rgb));
}

.style-bar.is-selected {
  border-color: rgb(var(--ink-1-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.style-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-2-rgb));
}

.style-bar.is-selected .style-icon {
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
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

.style-bar.is-selected .style-desc {
  color: rgb(var(--ink-2-rgb));
}
</style>
