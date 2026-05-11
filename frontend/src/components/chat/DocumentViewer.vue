<template>
  <div class="document-viewer">
    <!-- Header -->
    <div class="dv-header">
      <div class="dv-title-block">
        <component
          v-if="kindIcon"
          :is="kindIcon"
          class="dv-kind-icon"
          :class="`hue-${kindHue}`"
        />
        <div class="dv-title-stack">
          <div class="dv-title">{{ title || '文档' }}</div>
          <div v-if="subtitle" class="dv-subtitle">{{ subtitle }}</div>
        </div>
      </div>
      <div class="dv-actions">
        <a
          v-if="downloadHref"
          :href="downloadHref"
          target="_blank"
          rel="noopener"
          class="dv-action-btn"
          :title="`下载 ${downloadLabel || '文件'}`"
        >
          <Download class="w-4 h-4" />
        </a>
        <a
          v-if="docxHref"
          :href="docxHref"
          target="_blank"
          rel="noopener"
          class="dv-action-btn primary"
          title="下载 DOCX"
        >
          <FileText class="w-4 h-4" />
          <span class="dv-action-label">DOCX</span>
        </a>
        <button class="dv-action-btn" title="收起 (Esc)" @click="$emit('close')">
          <X class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Body — 根据 kind 渲染 -->
    <div class="dv-body">
      <!-- 文本 / 摘要内容(MD 渲染) -->
      <div v-if="markdownContent" class="dv-md prose prose-doc" v-html="renderedMarkdown" />

      <!-- 图文卡(图片 + 文案) -->
      <div v-else-if="kind === 'graphic_image' && imageBase64" class="dv-graphic">
        <div v-if="xiaohongshu" class="dv-md prose prose-doc" v-html="renderedXiaohongshu" />
        <img :src="imageBase64" class="dv-image" alt="封面" />
        <details v-if="prompt" class="dv-prompt">
          <summary>AI 绘图提示词</summary>
          <p>{{ prompt }}</p>
        </details>
      </div>

      <!-- 视频音频(脚本 + 配音) -->
      <div v-else-if="kind === 'video_audio'" class="dv-audio">
        <div v-if="renderedVideoScript" class="dv-md prose prose-doc dv-script-section" v-html="renderedVideoScript" />
        <div v-if="audioBase64" class="dv-audio-player">
          <div class="dv-audio-label">
            <Music class="w-3.5 h-3.5" />
            <span>AI 配音</span>
          </div>
          <audio :src="audioBase64" controls class="dv-audio-el" />
        </div>
        <div v-if="voiceoverText && !renderedVideoScript" class="dv-voiceover">{{ voiceoverText }}</div>
      </div>

      <!-- PPT 预览(slides 缩略图) -->
      <div v-else-if="kind === 'ppt_preview' && slides.length" class="dv-ppt">
        <div
          v-for="s in slides"
          :key="s.page"
          class="dv-slide"
        >
          <div class="dv-slide-no">第 {{ s.page }} 页</div>
          <img v-if="s.base64" :src="s.base64" class="dv-slide-img" />
          <div v-if="s.title" class="dv-slide-title">{{ s.title }}</div>
        </div>
      </div>

      <!-- 兜底 -->
      <div v-else class="dv-empty">
        <div class="dv-empty-icon"><FileQuestion class="w-8 h-8 opacity-50" /></div>
        <div class="dv-empty-text">无可预览内容</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, toRef } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  Download,
  X,
  FileText,
  FileQuestion,
  GraduationCap,
  BookOpen,
  Lightbulb,
  Network,
  ImageIcon,
  Music,
  Presentation,
  ClipboardList,
  Megaphone,
  ScrollText,
} from 'lucide-vue-next'
import { useMediaRestore } from '@/composables/useMediaRestore'

marked.setOptions({ gfm: true, breaks: true })

type Kind =
  | 'content_result'
  | 'graphic_image'
  | 'video_audio'
  | 'ppt_preview'
  | 'markdown'
  | 'text'
  | string

const props = defineProps<{
  kind?: Kind
  data?: Record<string, unknown>
  // markdown content fallback(text/markdown 类型时直接传 message.content)
  markdownContent?: string
}>()

const emit = defineEmits<{ close: [] }>()

// ESC 收起
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))

const data = computed(() => props.data || {})
const dataRef = toRef(props, 'data')
const { audioBase64: restoredAudio, imageBase64: restoredImage } = useMediaRestore(dataRef)

const completeType = computed(() => (data.value.completeType as string) || '')
const topic = computed(() => (data.value.topic as string) || '')
const filepath = computed(() => (data.value.filepath as string) || '')
const docxFilepath = computed(
  () => (data.value.docx_filepath as string) || (data.value.md_filepath as string) || '',
)

const xiaohongshu = computed(() => (data.value.xiaohongshu as string) || '')
const imageBase64 = computed(() => (data.value.imageBase64 as string) || restoredImage.value || '')
const prompt = computed(() => (data.value.prompt as string) || '')

const audioBase64 = computed(() => (data.value.audioBase64 as string) || restoredAudio.value || '')
const voiceoverText = computed(() => (data.value.voiceoverText as string) || '')
const videoScript = computed(() => (data.value.video_script as string) || '')

const slides = computed(() => {
  const s = data.value.slides as Array<{ page: number; base64?: string; title?: string }> | undefined
  return s || []
})

// content_result 的 content 字段
const contentResultText = computed(() => (data.value.content as string) || '')

// markdownContent 优先级:外部传 > content_result > xiaohongshu(graphic) → 决定 dv-md 渲染什么
const markdownContent = computed(() => {
  if (props.markdownContent) return props.markdownContent
  if (props.kind === 'content_result') return contentResultText.value
  if (props.kind === 'markdown' || props.kind === 'text') return props.markdownContent || ''
  return ''
})

const renderedMarkdown = computed(() => {
  const raw = markdownContent.value
  if (!raw) return ''
  const html = marked.parse(raw, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
})

const renderedXiaohongshu = computed(() => {
  const raw = xiaohongshu.value
  if (!raw) return ''
  const html = marked.parse(raw, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
})

const renderedVideoScript = computed(() => {
  const raw = videoScript.value
  if (!raw) return ''
  const html = marked.parse(raw, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
})

// kind → 标题 / 图标 / 模块色
const TYPE_MAP: Record<string, { label: string; hue: string; icon: unknown }> = {
  exercise_complete: { label: '习题集', hue: 'chat', icon: GraduationCap },
  quiz_complete: { label: '课堂测验', hue: 'ppt', icon: ClipboardList },
  knowledge_card_complete: { label: '知识卡片', hue: 'library', icon: Lightbulb },
  mindmap_complete: { label: '思维导图', hue: 'memory', icon: Network },
  speech_complete: { label: '讲稿', hue: 'settings', icon: Megaphone },
  course_outline_complete: { label: '课程大纲', hue: 'dashboard', icon: ScrollText },
  lecture_complete: { label: '讲义', hue: 'chat', icon: BookOpen },
  content_complete: { label: '图文内容', hue: 'memory', icon: ImageIcon },
}

const meta = computed(() => {
  if (props.kind === 'graphic_image') return { label: '图文', hue: 'memory', icon: ImageIcon }
  if (props.kind === 'video_audio') return { label: '短视频脚本', hue: 'settings', icon: Music }
  if (props.kind === 'ppt_preview') return { label: 'PPT 预览', hue: 'ppt', icon: Presentation }
  return TYPE_MAP[completeType.value] || { label: '生成结果', hue: 'chat', icon: FileText }
})

const kindIcon = computed(() => meta.value.icon)
const kindHue = computed(() => meta.value.hue)
const title = computed(() => topic.value || meta.value.label)
const subtitle = computed(() => {
  if (topic.value && meta.value.label !== topic.value) return meta.value.label
  return ''
})

const downloadHref = computed(() =>
  filepath.value ? `/api/files/download?path=${encodeURIComponent(filepath.value)}` : '',
)
const downloadLabel = computed(() => {
  const p = filepath.value
  if (!p) return ''
  return p.split('.').pop()?.toUpperCase() || ''
})
const docxHref = computed(() =>
  docxFilepath.value
    ? `/api/files/download?path=${encodeURIComponent(docxFilepath.value)}`
    : '',
)

// kind for compute
const kind = computed(() => props.kind || '')
</script>

<style scoped>
.document-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgb(var(--bg-surface-rgb));
  border-left: 1px solid rgb(var(--line-rgb));
}

/* Header */
.dv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 12px;
  border-bottom: 1px solid rgb(var(--line-rgb));
  flex-shrink: 0;
}
.dv-title-block {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.dv-kind-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.hue-chat { color: rgb(var(--hue-chat-rgb)); }
.hue-ppt { color: rgb(var(--hue-ppt-rgb)); }
.hue-library { color: rgb(var(--hue-library-rgb)); }
.hue-memory { color: rgb(var(--hue-memory-rgb)); }
.hue-settings { color: rgb(var(--hue-settings-rgb)); }
.hue-dashboard { color: rgb(var(--hue-dashboard-rgb)); }

.dv-title-stack {
  min-width: 0;
}
.dv-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  letter-spacing: -0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dv-subtitle {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  margin-top: 2px;
}

.dv-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.dv-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
  text-decoration: none;
  cursor: pointer;
  transition: all 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.dv-action-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}
.dv-action-btn.primary {
  background: rgb(var(--accent-rgb));
  color: white;
  border-color: transparent;
}
.dv-action-btn.primary:hover {
  background: rgb(var(--accent-hover-rgb));
}
.dv-action-label {
  font-size: 12px;
}

/* Body */
.dv-body {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
}

/* MD 大方排版 */
.prose-doc {
  font-size: 15.5px;
  line-height: 1.8;
  color: rgb(var(--ink-2-rgb));
  letter-spacing: 0.01em;
  max-width: 720px;
  margin: 0 auto;
}
:deep(.prose-doc h1) {
  font-size: 1.5em;
  font-weight: 700;
  color: rgb(var(--ink-1-rgb));
  margin: 1.2em 0 0.6em;
  padding-left: 14px;
  border-left: 3px solid rgb(var(--accent-rgb));
  letter-spacing: -0.02em;
}
:deep(.prose-doc h2) {
  font-size: 1.25em;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 1em 0 0.5em;
}
:deep(.prose-doc h3) {
  font-size: 1.1em;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0.9em 0 0.4em;
}
:deep(.prose-doc p) {
  margin: 0.7em 0;
}
:deep(.prose-doc strong) {
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}
:deep(.prose-doc ul),
:deep(.prose-doc ol) {
  margin: 0.7em 0;
  padding-left: 1.6em;
}
:deep(.prose-doc li) {
  margin: 0.4em 0;
}
:deep(.prose-doc table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.8em 0;
  font-size: 0.94em;
}
:deep(.prose-doc th),
:deep(.prose-doc td) {
  border: 1px solid rgb(var(--line-rgb));
  padding: 0.55em 0.85em;
  text-align: left;
}
:deep(.prose-doc th) {
  background: rgb(var(--bg-subtle-rgb));
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}
:deep(.prose-doc tr:nth-child(even) td) {
  background: rgb(var(--bg-subtle-rgb) / 0.5);
}
:deep(.prose-doc pre) {
  background: rgb(var(--bg-inset-rgb));
  border: 1px solid rgb(var(--line-rgb));
  padding: 14px 16px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 0.8em 0;
  font-size: 13.5px;
}
:deep(.prose-doc code) {
  background: rgb(var(--bg-subtle-rgb));
  padding: 0.15em 0.4em;
  border-radius: 5px;
  font-size: 0.88em;
  font-family: 'JetBrains Mono', monospace;
  color: rgb(var(--accent-rgb));
}
:deep(.prose-doc pre code) {
  background: none;
  padding: 0;
  color: inherit;
}
:deep(.prose-doc blockquote) {
  border-left: 3px solid rgb(var(--accent-rgb) / 0.50);
  padding: 0.5em 1em;
  margin: 0.8em 0;
  color: rgb(var(--ink-3-rgb));
  background: rgb(var(--bg-subtle-rgb) / 0.5);
  border-radius: 0 8px 8px 0;
}

/* Graphic */
.dv-graphic {
  max-width: 720px;
  margin: 0 auto;
}
.dv-image {
  width: 100%;
  border-radius: 12px;
  margin-top: 20px;
  border: 1px solid rgb(var(--line-rgb));
}
.dv-prompt {
  margin-top: 14px;
  padding: 10px 14px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-subtle-rgb) / 0.5);
}
.dv-prompt summary {
  cursor: pointer;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  user-select: none;
}
.dv-prompt p {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: rgb(var(--ink-3-rgb));
  line-height: 1.6;
}

/* Audio */
.dv-audio {
  max-width: 720px;
  margin: 0 auto;
}
.dv-script-section {
  margin-bottom: 24px;
}
.dv-audio-player {
  padding: 16px 20px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
}
.dv-audio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-3-rgb));
  margin-bottom: 10px;
}
.dv-audio-el {
  width: 100%;
}
.dv-voiceover {
  margin-top: 20px;
  padding: 16px 20px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
  color: rgb(var(--ink-2-rgb));
  white-space: pre-wrap;
}

/* PPT */
.dv-ppt {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dv-slide {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  overflow: hidden;
  background: rgb(var(--bg-subtle-rgb));
}
.dv-slide-no {
  font-size: 11.5px;
  color: rgb(var(--ink-3-rgb));
  padding: 8px 14px;
  border-bottom: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
}
.dv-slide-img {
  width: 100%;
  display: block;
}
.dv-slide-title {
  padding: 10px 14px;
  font-size: 13px;
  color: rgb(var(--ink-2-rgb));
}

/* Empty */
.dv-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgb(var(--ink-3-rgb));
  gap: 12px;
}
.dv-empty-text {
  font-size: 13px;
}
</style>
