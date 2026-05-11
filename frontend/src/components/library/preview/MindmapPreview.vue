<template>
  <div class="mindmap-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>渲染思维导图...</span>
    </div>
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="retry-btn" @click="load">重试</button>
    </div>
    <div v-else ref="container" class="mindmap-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { readFile } from '@/api/files'

const props = defineProps<{ path: string }>()

const container = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref('')
let viewInstance: { destroy?: () => void } | null = null

async function load() {
  if (!props.path || !container.value) return
  loading.value = true
  error.value = ''

  try {
    const { content } = await readFile(props.path)
    const { Markmap } = await import('markmap-view')
    const { Transformer } = await import('markmap-lib')

    const transformer = new Transformer()
    const { root } = transformer.transform(content)

    // Clear previous
    container.value.innerHTML = ''
    if (viewInstance?.destroy) viewInstance.destroy()

    const mm = Markmap.create(container.value, {
      autoFit: true,
      duration: 300,
      maxWidth: 280,
      paddingX: 12,
    }, root)

    viewInstance = mm
  } catch (e) {
    error.value = e instanceof Error ? e.message : '思维导图渲染失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.path, load)
onUnmounted(() => {
  if (viewInstance?.destroy) viewInstance.destroy()
})
</script>

<style scoped>
.mindmap-preview {
  width: 100%;
  min-height: 300px;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.loading-dots {
  display: flex;
  gap: 4px;
}
.loading-dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgb(var(--ink-4-rgb));
  animation: dot-bounce 1.4s ease-in-out infinite;
}
.loading-dots span:nth-child(2) { animation-delay: 0.16s; }
.loading-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
  40% { transform: translateY(-3px); opacity: 1; }
}

.error-state {
  padding: 30px 20px;
  text-align: center;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.retry-btn {
  margin-top: 10px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms;
}
.retry-btn:hover {
  background: rgb(var(--accent-rgb));
  color: white;
  border-color: transparent;
}

.mindmap-container {
  width: 100%;
  min-height: 300px;
  max-height: 600px;
  overflow: auto;
  border-radius: 10px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
}

.mindmap-container :deep(svg) {
  width: 100%;
  height: auto;
}
</style>
