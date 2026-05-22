<template>
  <div class="docx-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>转换文档中...</span>
    </div>
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
    </div>
    <div v-else class="preview-body" v-html="html" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { fileDownloadUrl } from '@/api/files'

const props = defineProps<{ path: string; name: string }>()

const html = ref('')
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.path) return
  loading.value = true
  error.value = ''
  html.value = ''

  try {
    const res = await fetch(fileDownloadUrl(props.path))
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const buffer = await res.arrayBuffer()
    const mammoth = await import('mammoth')
    const result = await mammoth.convertToHtml({ arrayBuffer: buffer })
    html.value = result.value || '<p style="color:#9ca3af">文档内容为空</p>'
    if (result.messages.length) {
      console.warn('[DocxPreview] mammoth warnings:', result.messages)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'DOCX 转换失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.path, load)
</script>

<style scoped>
.docx-preview {
  width: 100%;
  min-height: 200px;
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
  color: rgb(var(--danger-rgb));
  font-size: 13px;
}

.preview-body {
  font-size: 15px;
  line-height: 1.75;
  color: rgb(var(--ink-1-rgb));
  word-break: break-word;
}

.preview-body :deep(h1) { font-size: 1.5em; font-weight: 700; margin: 1em 0 0.4em; }
.preview-body :deep(h2) { font-size: 1.25em; font-weight: 600; margin: 0.8em 0 0.3em; }
.preview-body :deep(h3) { font-size: 1.1em; font-weight: 600; margin: 0.6em 0 0.2em; }
.preview-body :deep(p) { margin: 0.5em 0; }
.preview-body :deep(ul),
.preview-body :deep(ol) { margin: 0.5em 0; padding-left: 1.5em; }
.preview-body :deep(li) { margin: 0.25em 0; }
.preview-body :deep(table) { width: 100%; border-collapse: collapse; margin: 0.8em 0; }
.preview-body :deep(th),
.preview-body :deep(td) { border: 1px solid rgb(var(--line-rgb)); padding: 6px 10px; text-align: left; }
.preview-body :deep(th) { background: rgb(var(--bg-subtle-rgb)); font-weight: 600; }
.preview-body :deep(img) { max-width: 100%; border-radius: 8px; }
</style>