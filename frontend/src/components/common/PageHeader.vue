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
  padding: 28px 32px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  border-bottom: 1px solid var(--line);
}

.page-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--ink-primary);
  line-height: 1.2;
}

.page-desc {
  font-size: 13px;
  color: var(--ink-tertiary);
  margin-top: 4px;
  line-height: 1.5;
  font-family: 'DM Sans', sans-serif;
}
</style>
