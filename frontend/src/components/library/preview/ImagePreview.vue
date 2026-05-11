<template>
  <div class="image-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>加载图片中...</span>
    </div>
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <a :href="src" target="_blank" rel="noopener" class="download-link">
        <Download class="w-4 h-4" /> 在新标签页打开
      </a>
    </div>
    <div
      v-else
      ref="panContainer"
      class="pan-container"
      @wheel.prevent="onWheel"
    >
      <img
        ref="imgEl"
        :src="src"
        :alt="name || '图片'"
        class="preview-img"
        @load="onLoad"
        @error="onImgError"
        draggable="false"
      />
    </div>

    <div v-if="!error" class="image-toolbar">
      <button class="zoom-btn" @click="zoomIn" title="放大">
        <ZoomIn class="w-3.5 h-3.5" />
      </button>
      <button class="zoom-btn" @click="zoomOut" title="缩小">
        <ZoomOut class="w-3.5 h-3.5" />
      </button>
      <button class="zoom-btn" @click="resetZoom" title="重置">
        <Maximize2 class="w-3.5 h-3.5" />
      </button>
      <a :href="src" target="_blank" rel="noopener" class="zoom-btn" title="原图">
        <ExternalLink class="w-3.5 h-3.5" />
      </a>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Download, ZoomIn, ZoomOut, Maximize2, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  name?: string
}>()

const panContainer = ref<HTMLElement | null>(null)
const imgEl = ref<HTMLImageElement | null>(null)
const loading = ref(true)
const error = ref('')
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let panzoomInstance: any = null

function onLoad() {
  loading.value = false
  initPanzoom()
}

function onImgError() {
  loading.value = false
  error.value = '图片加载失败'
}

async function initPanzoom() {
  if (!panContainer.value || !imgEl.value) return
  try {
    const Panzoom = (await import('@panzoom/panzoom')).default
    panzoomInstance = Panzoom(imgEl.value, {
      maxScale: 5,
      minScale: 0.5,
      step: 0.3,
      contain: 'outside',
    })
    panContainer.value.addEventListener('wheel', (e) => {
      panzoomInstance?.zoomWithWheel(e)
    }, { passive: false })
  } catch {
    // panzoom not available, image still shows without zoom
  }
}

function zoomIn() {
  if (panzoomInstance) {
    const s = panzoomInstance.getScale()
    panzoomInstance.zoomTo(s + 0.3)
  }
}

function zoomOut() {
  if (panzoomInstance) {
    const s = panzoomInstance.getScale()
    panzoomInstance.zoomTo(Math.max(0.5, s - 0.3))
  }
}

function resetZoom() {
  panzoomInstance?.reset()
}

function onWheel(_e: WheelEvent) {
  // handled by panzoom
}

onUnmounted(() => {
  panzoomInstance?.destroy()
  panzoomInstance = null
})

watch(() => props.src, () => {
  loading.value = true
  error.value = ''
  panzoomInstance?.destroy()
  panzoomInstance = null
})
</script>

<style scoped>
.image-preview {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.download-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 6px 14px;
  border-radius: 8px;
  background: rgb(var(--accent-rgb));
  color: white;
  font-size: 12px;
  text-decoration: none;
}

.pan-container {
  width: 100%;
  overflow: hidden;
  border-radius: 10px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  max-height: 500px;
  cursor: grab;
  touch-action: none;
}

.preview-img {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  border-radius: 8px;
  user-select: none;
}

.image-toolbar {
  display: flex;
  gap: 4px;
  justify-content: center;
}

.zoom-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  text-decoration: none;
  transition: all 150ms;
}

.zoom-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--accent-rgb) / 0.3);
}
</style>
