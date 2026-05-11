<template>
  <CardShell
    hue="memory"
    :icon="ImageIcon"
    title="图文内容"
    :subtitle="subtitle"
    :stats="stats"
    :is-expanded="isExpanded"
    @toggle="$emit('toggle')"
  />
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { ImageIcon } from 'lucide-vue-next'
import CardShell from './CardShell.vue'
import { useMediaRestore } from '@/composables/useMediaRestore'

const props = defineProps<{ data?: Record<string, unknown>; isExpanded?: boolean }>()
defineEmits<{ toggle: [] }>()

const dataRef = toRef(props, 'data')
const { imageBase64: restoredImage } = useMediaRestore(dataRef)

const xiaohongshu = computed(() => (props.data?.xiaohongshu as string) || '')
const topic = computed(() => (props.data?.topic as string) || '')

const subtitle = computed(() => {
  if (topic.value) return topic.value
  if (xiaohongshu.value) {
    const firstLine = xiaohongshu.value.split('\n').find((l) => l.trim())
    if (firstLine) return firstLine.replace(/^#+\s*/, '').slice(0, 40)
  }
  return restoredImage.value ? '小红书图文已生成' : '生成中...'
})

const stats = computed(() => {
  const parts: string[] = []
  if (xiaohongshu.value) {
    const len = xiaohongshu.value.length
    parts.push(len >= 1000 ? `${(len / 1000).toFixed(1)}k 字` : `${len} 字`)
  }
  if (restoredImage.value) parts.push('含封面图')
  return parts.join(' · ')
})
</script>
