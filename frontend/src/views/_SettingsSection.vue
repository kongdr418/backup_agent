<template>
  <div class="flex items-center gap-3 mb-4">
    <div
      class="w-9 h-9 rounded-lg bg-bg-subtle flex items-center justify-center text-ink-2"
    >
      <component :is="icon" class="w-4 h-4" />
    </div>
    <div class="min-w-0">
      <div class="text-[13.5px] font-medium text-ink-1">{{ title }}</div>
      <div v-if="subtitle" class="text-[11.5px] text-ink-3 mt-0.5">{{ subtitle }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  title: string
  subtitle?: string
}>()
</script>
