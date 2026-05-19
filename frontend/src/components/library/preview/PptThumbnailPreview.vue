<template>
  <div class="ppt-thumb-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>加载 PPT 预览...</span>
    </div>
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <a :href="downloadUrl" target="_blank" rel="noopener" class="download-link">
        <Download class="w-4 h-4" /> 下载 PPTX
      </a>
    </div>
    <div v-else class="thumb-grid">
      <div
        v-for="slide in slides"
        :key="slide.page"
        class="thumb-card"
        :class="{ active: activeSlide === slide.page }"
        @click="activeSlide = slide.page"
      >
        <div class="thumb-img" v-html="slide.svg" />
        <div class="thumb-label">{{ slide.page }}</div>
      </div>
    </div>

    <div v-if="activeSlideData" class="slide-detail">
      <div class="slide-header">
        <span class="slide-title">第 {{ activeSlide }} 页</span>
        <span class="slide-of">/ {{ slides.length }}</span>
      </div>
      <div class="slide-full" v-html="activeSlideData.svg" />
    </div>

    <!-- Download link -->
    <a
      v-if="!loading && !error && downloadUrl !== '#'"
      :href="downloadUrl"
      target="_blank"
      rel="noopener"
      class="download-bar"
    >
      <Download class="w-4 h-4" />
      下载 PPTX
    </a>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Download } from 'lucide-vue-next'
import type { PptSlide } from '@/types'
import { getPptAllSlides, pptDownloadUrl } from '@/api/pptSvg'

const props = defineProps<{
  jobId: string
  name?: string
}>()

const slides = ref<PptSlide[]>([])
const loading = ref(false)
const error = ref('')
const activeSlide = ref(1)

const downloadUrl = computed(() => props.jobId ? pptDownloadUrl(props.jobId) : '#')

const activeSlideData = computed(() =>
  slides.value.find(s => s.page === activeSlide.value)
)

async function load() {
  if (!props.jobId) return
  loading.value = true
  error.value = ''
  try {
    const data = await getPptAllSlides(props.jobId)
    slides.value = data.slides
    activeSlide.value = 1
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'PPT 预览加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.jobId, load)
</script>

<style scoped>
.ppt-thumb-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.loading-dots { display: flex; gap: 4px; }
.loading-dots span {
  width: 5px; height: 5px; border-radius: 50%;
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
  margin-top: 10px;
  padding: 8px 16px;
  border-radius: 8px;
  background: rgb(var(--accent-rgb));
  color: white;
  font-size: 13px;
  text-decoration: none;
}

.thumb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
}

.thumb-card {
  position: relative;
  border-radius: 8px;
  border: 2px solid transparent;
  overflow: hidden;
  cursor: pointer;
  background: rgb(var(--bg-surface-rgb));
  transition: all 200ms;
}

.thumb-card:hover {
  border-color: rgb(var(--accent-rgb) / 0.3);
}

.thumb-card.active {
  border-color: rgb(var(--accent-rgb));
  box-shadow: 0 0 0 2px rgb(var(--accent-rgb) / 0.15);
}

.thumb-img {
  aspect-ratio: 16/9;
  overflow: hidden;
}

.thumb-img :deep(svg) {
  width: 100%;
  height: 100%;
}

.thumb-label {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 10px;
  font-weight: 600;
  color: rgb(var(--ink-3-rgb));
  background: rgb(var(--bg-surface-rgb) / 0.8);
  padding: 1px 5px;
  border-radius: 4px;
}

.slide-detail {
  border-radius: 12px;
  border: 1px solid rgb(var(--line-rgb));
  overflow: hidden;
}

.slide-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: rgb(var(--bg-subtle-rgb));
  border-bottom: 1px solid rgb(var(--line-rgb));
}

.slide-title {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}

.slide-of {
  font-size: 12px;
  color: rgb(var(--ink-4-rgb));
}

.slide-full {
  padding: 12px;
}

.slide-full :deep(svg) {
  width: 100%;
  height: auto;
}

.download-bar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 0;
  border-radius: 10px;
  background: rgb(var(--accent-rgb));
  color: white;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: opacity 200ms;
}

.download-bar:hover {
  opacity: 0.88;
}
</style>
