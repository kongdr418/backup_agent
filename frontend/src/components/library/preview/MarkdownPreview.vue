<template>
  <div class="markdown-preview">
    <div v-if="loading" class="loading-state">
      <div class="loading-dots"><span /><span /><span /></div>
      <span>加载内容中...</span>
    </div>
    <div v-else-if="error" class="error-state">{{ error }}</div>
    <div v-else class="preview-body" v-html="html" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { readFile } from '@/api/files'

const props = defineProps<{ path: string }>()

const html = ref('')
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.path) return
  loading.value = true
  error.value = ''
  try {
    const { content } = await readFile(props.path)
    const { marked } = await import('marked')
    const { default: DOMPurify } = await import('dompurify')
    marked.setOptions({ gfm: true, breaks: true })
    const raw = marked.parse(content, { async: false }) as string
    html.value = DOMPurify.sanitize(raw, { ADD_ATTR: ['target'] })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.path, load)
</script>

<style scoped>
.markdown-preview {
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
  padding: 20px;
  text-align: center;
  color: rgb(var(--danger-rgb));
  font-size: 13px;
}

.preview-body {
  font-size: 15.5px;
  line-height: 1.8;
  color: rgb(var(--ink-1-rgb));
  word-break: break-word;
}

.preview-body :deep(h1) {
  font-size: 1.5em;
  font-weight: 700;
  margin: 1.2em 0 0.5em;
  padding-left: 12px;
  border-left: 3px solid rgb(var(--accent-rgb));
  line-height: 1.4;
}

.preview-body :deep(h2) {
  font-size: 1.25em;
  font-weight: 600;
  margin: 1em 0 0.4em;
  line-height: 1.4;
}

.preview-body :deep(h3) {
  font-size: 1.1em;
  font-weight: 600;
  margin: 0.8em 0 0.3em;
  line-height: 1.4;
}

.preview-body :deep(p) {
  margin: 0.6em 0;
}

.preview-body :deep(ul),
.preview-body :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.preview-body :deep(li) {
  margin: 0.3em 0;
}

.preview-body :deep(strong) {
  font-weight: 600;
}

.preview-body :deep(code) {
  background: rgb(var(--bg-subtle-rgb));
  padding: 0.15em 0.4em;
  border-radius: 5px;
  font-size: 0.88em;
  font-family: 'JetBrains Mono', monospace;
}

.preview-body :deep(pre) {
  background: rgb(var(--bg-inset-rgb));
  border: 1px solid rgb(var(--line-rgb));
  padding: 14px 16px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 0.8em 0;
  font-size: 13px;
  line-height: 1.6;
}

.preview-body :deep(pre code) {
  background: none;
  padding: 0;
  font-size: inherit;
}

.preview-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.8em 0;
  font-size: 0.92em;
}

.preview-body :deep(th),
.preview-body :deep(td) {
  border: 1px solid rgb(var(--line-rgb));
  padding: 8px 12px;
  text-align: left;
}

.preview-body :deep(th) {
  background: rgb(var(--bg-subtle-rgb));
  font-weight: 600;
}

.preview-body :deep(tr:nth-child(even)) {
  background: rgb(var(--bg-subtle-rgb) / 0.5);
}

.preview-body :deep(blockquote) {
  margin: 0.8em 0;
  padding: 12px 16px;
  border-left: 3px solid rgb(var(--accent-rgb));
  background: rgb(var(--accent-rgb) / 0.05);
  border-radius: 0 8px 8px 0;
  color: rgb(var(--ink-2-rgb));
}

.preview-body :deep(hr) {
  border: none;
  border-top: 1px solid rgb(var(--line-rgb));
  margin: 1.2em 0;
}

.preview-body :deep(a) {
  color: rgb(var(--accent-rgb));
  text-decoration: none;
}
.preview-body :deep(a:hover) {
  text-decoration: underline;
}
</style>