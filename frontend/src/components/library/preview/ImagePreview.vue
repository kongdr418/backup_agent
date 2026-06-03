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
        :src="imageDataUrl || src"
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
      <button class="zoom-btn" @click="openOriginal" title="原图">
        <ExternalLink class="w-3.5 h-3.5" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Download, ZoomIn, ZoomOut, Maximize2, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  src: string
  name?: string
  apiMode?: boolean  // true when src is a JSON API endpoint returning {image: base64}
}>()

const panContainer = ref<HTMLElement | null>(null)
const imgEl = ref<HTMLImageElement | null>(null)
const loading = ref(true)
const error = ref('')
const imageDataUrl = ref('')
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let panzoomInstance: any = null

async function fetchImageFromApi(url: string): Promise<string> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`API request failed: ${resp.status}`)
  const json = await resp.json()
  if (!json.image) throw new Error('No image data in response')
  // json.image is already base64, construct data URL
  return `data:image/jpeg;base64,${json.image}`
}

async function fetchImageAsDataUrl(url: string): Promise<string> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Failed to fetch image: ${resp.status}`)
  const blob = await resp.blob()
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

async function loadImage() {
  loading.value = true
  error.value = ''
  imageDataUrl.value = ''

  try {
    if (props.apiMode) {
      // Fetch from JSON API endpoint (e.g., /api/graphic/image/xxx)
      const dataUrl = await fetchImageFromApi(props.src)
      imageDataUrl.value = dataUrl
    } else {
      // Fetch binary stream and convert to data URL
      const dataUrl = await fetchImageAsDataUrl(props.src)
      imageDataUrl.value = dataUrl
    }
    loading.value = false
    initPanzoom()
  } catch (e) {
    loading.value = false
    error.value = '图片加载失败'
  }
}

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

  // 图片还没加载完则跳过，等 onLoad 时再初始化
  const img = imgEl.value
  if (!img.complete || !img.naturalWidth) return

  // 清理旧实例，防止重复初始化
  if (panzoomInstance) {
    panzoomInstance.destroy()
    panzoomInstance = null
  }

  try {
    const Panzoom = (await import('@panzoom/panzoom')).default
    const container = panContainer.value

    // pan-container 的 flexbox 已经把图片居中，panzoom 不需要额外偏移
    // 否则 translate 会叠加在 flexbox 居中之上，导致双倍偏移
    panzoomInstance = Panzoom(img, {
      maxScale: 5,
      minScale: 0.5,
      step: 0.3,
    })
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

function onWheel(e: WheelEvent) {
  panzoomInstance?.zoomWithWheel(e)
}

function openOriginal() {
  const url = imageDataUrl.value || props.src
  if (!url) return

  // data URL 太长时直接用 <a href> 打开会空白，转为 Blob URL 更可靠
  if (url.startsWith('data:')) {
    const parts = url.split(',')
    const mime = parts[0].match(/:(.*?);/)?.[1] || 'image/jpeg'
    const byteString = parts[0].endsWith(';base64')
      ? atob(parts[1])
      : decodeURIComponent(parts[1])
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    const blob = new Blob([ab], { type: mime })
    const blobUrl = URL.createObjectURL(blob)
    window.open(blobUrl, '_blank')
    // 延迟释放，避免窗口还没打开就被回收
    setTimeout(() => URL.revokeObjectURL(blobUrl), 30000)
  } else {
    window.open(url, '_blank')
  }
}

onMounted(() => {
  loadImage()
})

onUnmounted(() => {
  panzoomInstance?.destroy()
  panzoomInstance = null
})

watch(() => props.src, () => {
  panzoomInstance?.destroy()
  panzoomInstance = null
  loadImage()
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
