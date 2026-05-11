<template>
  <div class="page-header">
    <div class="min-w-0">
      <div class="page-title">{{ title }}</div>
      <div v-if="description" class="page-desc">
        {{ description }}
      </div>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2 shrink-0 ml-4">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<style scoped>
.page-header {
  padding: 24px 28px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.3;
}

.page-desc {
  font-size: 13px;
  color: rgb(var(--ink-3-rgb));
  margin-top: 4px;
  line-height: 1.5;
}
</style>
