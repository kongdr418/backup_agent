<template>
  <div class="h-full flex items-center justify-center px-6">
    <div class="empty-content text-center max-w-sm">
      <div
        v-if="icon"
        class="w-12 h-12 rounded-full bg-bg-subtle flex items-center justify-center mx-auto mb-4 text-ink-3"
      >
        <component :is="icon" class="w-5 h-5" />
      </div>
      <div class="text-[15px] font-medium text-ink-1 mb-1">{{ title }}</div>
      <div v-if="description" class="text-[13px] text-ink-3 leading-relaxed">
        {{ description }}
      </div>
      <div v-if="$slots.default" class="mt-5">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon?: Component
  title: string
  description?: string
}>()
</script>

<style scoped>
@media (max-width: 767px) {
  .empty-content {
    max-width: 260px;
  }
}
</style>
