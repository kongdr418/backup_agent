<template>
  <CardShell
    hue="ppt"
    :icon="Presentation"
    title="PPT 预览"
    :subtitle="subtitle"
    :stats="stats"
    :is-expanded="isExpanded"
    @toggle="$emit('toggle')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Presentation } from 'lucide-vue-next'
import CardShell from './CardShell.vue'

const props = defineProps<{ data?: Record<string, unknown>; isExpanded?: boolean }>()
defineEmits<{ toggle: [] }>()

const slides = computed(
  () => (props.data?.slides as Array<{ page: number; base64?: string }>) || [],
)
const totalPages = computed(() => (props.data?.totalPages as number) || slides.value.length || 0)
const filename = computed(() => (props.data?.filename as string) || '')

const subtitle = computed(() => filename.value || `已生成 ${slides.value.length} 页`)
const stats = computed(() => {
  const have = slides.value.length
  if (totalPages.value && totalPages.value !== have) {
    return `${have} / ${totalPages.value} 页`
  }
  return `${have} 页`
})
</script>
