<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium"
    :class="cls"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="dotCls" />
    <slot />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    tone?: 'neutral' | 'success' | 'warning' | 'danger'
  }>(),
  { tone: 'neutral' },
)

const cls = computed(
  () =>
    ({
      neutral: 'bg-bg-subtle text-ink-2',
      success: 'bg-emerald-50 text-emerald-700',
      warning: 'bg-amber-50 text-amber-700',
      danger: 'bg-rose-50 text-rose-700',
    })[props.tone],
)

const dotCls = computed(
  () =>
    ({
      neutral: 'bg-ink-4',
      success: 'bg-emerald-500',
      warning: 'bg-amber-500',
      danger: 'bg-rose-500',
    })[props.tone],
)
</script>
