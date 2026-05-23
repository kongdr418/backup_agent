<template>
  <n-drawer v-model:show="visible" :width="drawerWidth" placement="right">
    <n-drawer-content :title="file?.name || '预览'" closable>
      <template v-if="file">
        <!-- Meta info bar -->
        <div class="meta-bar">
          <div class="meta-item">
            <span class="meta-label">类型</span>
            <span class="meta-value">{{ file.type_label }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">大小</span>
            <span class="meta-value">{{ file.size_formatted }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">时间</span>
            <span class="meta-value">{{ file.created }}</span>
          </div>
          <div class="meta-actions">
            <a :href="downloadHref" target="_blank" rel="noopener" class="meta-download-btn">
              <Download class="w-3.5 h-3.5" />
              下载
            </a>
          </div>
        </div>

        <!-- Image preview -->
        <ImagePreview
          v-if="file.type === 'content_image'"
          :src="imageUrl(file.name)"
          :name="file.name"
          :api-mode="true"
        />

        <!-- Audio preview -->
        <AudioPreview
          v-else-if="file.type === 'content_audio'"
          :src="audioUrl(file.name)"
          :name="file.name"
        />

        <!-- Video preview -->
        <VideoPreview
          v-else-if="file.type === 'video'"
          :src="downloadHref"
          :name="file.name"
          :meta="`${file.size_formatted} · ${file.created}`"
        />

        <!-- PPT: SVG PPT 展示预览图+下载，旧版PPT只显示下载 -->
        <PptThumbnailPreview
          v-else-if="file.type === 'ppt' && isSvgPpt"
          :job-id="svgJobId"
          :name="file.name"
        />
        <DownloadCard
          v-else-if="file.type === 'ppt'"
          :name="file.name"
          :path="file.path"
          type="ppt"
          :size="file.size_formatted"
          :date="file.created"
          :download-url="fileDownloadUrl(file.path)"
        />

        <!-- DOCX -->
        <DocxPreview
          v-else-if="fileExtension === 'docx'"
          :path="file.path"
          :name="file.name"
        />

        <!-- JSON -->
        <JsonPreview
          v-else-if="fileExtension === 'json'"
          :path="file.path"
        />

        <!-- Markdown / text -->
        <MarkdownPreview
          v-else-if="isTextFile"
          :path="file.path"
        />

        <!-- Mindmap (special handling) -->
        <MindmapPreview
          v-else-if="file.type === 'mindmap' && fileExtension === 'md'"
          :path="file.path"
        />

        <!-- Fallback: download card -->
        <DownloadCard
          v-else
          :name="file.name"
          :path="file.path"
          :type="file.type"
          :size="file.size_formatted"
          :date="file.created"
          :download-url="downloadHref"
        />
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { NDrawer, NDrawerContent } from 'naive-ui'
import { Download } from 'lucide-vue-next'
import type { GeneratedFile } from '@/types'
import { graphicImageUrl, videoAudioUrl } from '@/api/preview'
import { pptDownloadUrl as pptSvgDownloadUrl } from '@/api/pptSvg'
import { fileDownloadUrl } from '@/api/files'

// Lazy-loaded preview sub-components
const ImagePreview = defineAsyncComponent(() => import('./preview/ImagePreview.vue'))
const AudioPreview = defineAsyncComponent(() => import('./preview/AudioPreview.vue'))
const VideoPreview = defineAsyncComponent(() => import('./preview/VideoPreview.vue'))
const MarkdownPreview = defineAsyncComponent(() => import('./preview/MarkdownPreview.vue'))
const DocxPreview = defineAsyncComponent(() => import('./preview/DocxPreview.vue'))
const MindmapPreview = defineAsyncComponent(() => import('./preview/MindmapPreview.vue'))
const JsonPreview = defineAsyncComponent(() => import('./preview/JsonPreview.vue'))
const DownloadCard = defineAsyncComponent(() => import('./preview/DownloadCard.vue'))
const PptThumbnailPreview = defineAsyncComponent(() => import('./preview/PptThumbnailPreview.vue'))

const props = defineProps<{ show: boolean; file?: GeneratedFile | null }>()
const emit = defineEmits<{ 'update:show': [v: boolean] }>()

const visible = computed({ get: () => props.show, set: (v) => emit('update:show', v) })

const drawerWidth = ref(720)
const MOBILE_BREAKPOINT = 767

function updateWidth() {
  drawerWidth.value = window.innerWidth <= MOBILE_BREAKPOINT ? window.innerWidth : 720
}

onMounted(() => {
  updateWidth()
  window.addEventListener('resize', updateWidth)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateWidth)
})

const svgJobId = ref('')

const isTextFile = computed(() => {
  if (!props.file) return false
  const name = props.file.name.toLowerCase()
  return name.endsWith('.md') || name.endsWith('.txt')
})

const fileExtension = computed(() => {
  if (!props.file) return ''
  return props.file.name.split('.').pop()?.toLowerCase() || ''
})

const isSvgPpt = computed(() => {
  if (!props.file) return false
  return props.file.id?.startsWith('svg_ppt_') ?? false
})

const downloadHref = computed(() => {
  if (!props.file) return '#'
  return fileDownloadUrl(props.file.path)
})

watch(
  () => props.file,
  (f) => {
    svgJobId.value = ''
    if (!f) return
    if (f.id?.startsWith('svg_ppt_')) {
      svgJobId.value = f.id.replace(/^svg_ppt_/, '')
    }
  },
  { immediate: true },
)

function imageUrl(name: string) {
  return graphicImageUrl(name)
}
function audioUrl(name: string) {
  return videoAudioUrl(name)
}
</script>

<style scoped>
.meta-bar {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  font-size: 12px;
}

.meta-item {
  display: flex;
  gap: 6px;
  align-items: center;
}

.meta-label {
  color: rgb(var(--ink-4-rgb));
}

.meta-value {
  color: rgb(var(--ink-2-rgb));
  font-weight: 500;
}

.meta-actions {
  margin-left: auto;
}

.meta-download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgb(var(--accent-rgb));
  color: white;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  transition: opacity 200ms;
}
.meta-download-btn:hover {
  opacity: 0.85;
}
</style>