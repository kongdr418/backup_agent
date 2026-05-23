<template>
  <div class="border-t border-line glass-chrome px-4 py-3">
    <div class="max-w-3xl mx-auto">
      <!-- Quick action chips -->
      <div v-if="!isLoading && !chatView.isSplit" class="quick-chips flex gap-1 mb-2">
        <button
          v-for="q in quickActions"
          :key="q.label"
          class="inline-flex items-center gap-1 px-2 py-0.5 text-[12px] rounded-full border border-line bg-bg-surface text-ink-2 hover:border-ink-4 hover:text-ink-1 transition-colors whitespace-nowrap"
          @click="apply(q)"
        >
          <component :is="q.icon" class="w-3.5 h-3.5" />
          {{ q.label }}
        </button>
      </div>

      <!-- Format selector + Input bar -->
      <div
        class="flex items-center gap-2 glass-thin rounded-xl p-1.5 transition-colors focus-within:border-accent/50"
      >
        <!-- Format toggle -->
        <div
          class="flex items-center gap-0.5 px-1 shrink-0"
          :title="docxAvailable ? '' : '当前内容类型不支持 DOCX 导出'"
        >
          <button
            v-for="fmt in formats"
            :key="fmt.value"
            class="px-2 py-1 text-[12px] rounded-md transition-all"
            :class="[
              selectedFormat === fmt.value
                ? 'bg-brand text-white shadow-sm'
                : 'text-ink-3 hover:text-ink-1',
              !docxAvailable && fmt.value === 'docx'
                ? 'opacity-40 cursor-not-allowed hover:text-ink-3'
                : ''
            ]"
            :disabled="!docxAvailable && fmt.value === 'docx'"
            @click="!docxAvailable && fmt.value === 'docx' ? null : selectedFormat = fmt.value"
          >
            {{ fmt.label }}
          </button>
        </div>

        <div class="w-px h-6 bg-line shrink-0" />

        <textarea
          ref="taRef"
          v-model="input"
          rows="1"
          class="flex-1 bg-transparent resize-none outline-none text-[14px] text-ink-1 placeholder-ink-4 py-1.5 px-1.5 max-h-40 leading-6"
          :placeholder="placeholder"
          :disabled="isLoading"
          @keydown.enter.prevent="onEnter"
          @input="autoResize"
        />

        <button
          v-if="isLoading"
          class="shrink-0 px-2.5 h-9 inline-flex items-center gap-1.5 rounded-lg bg-rose-50 text-rose-600 hover:bg-rose-100 transition-colors text-[13px]"
          @click="$emit('cancel')"
        >
          <Square class="w-3.5 h-3.5" />
          停止
        </button>

        <button
          v-else
          class="shrink-0 w-9 h-9 inline-flex items-center justify-center rounded-lg transition-colors disabled:opacity-40"
          :class="
            input.trim()
              ? 'bg-brand text-white hover:bg-brand-hover'
              : 'bg-ink-5 text-bg-surface cursor-not-allowed'
          "
          :disabled="!input.trim()"
          @click="send"
        >
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Send, Square, FileText, BookOpen, Image as ImageIcon, Video,
  GraduationCap, Lightbulb, List, ClipboardList, GitBranch
} from 'lucide-vue-next'
import { useChatViewStore } from '@/stores/chatViewStore'

defineProps<{ isLoading: boolean }>()
const emit = defineEmits<{ send: [text: string]; cancel: [] }>()

const chatView = useChatViewStore()

const input = ref('')
const taRef = ref<HTMLTextAreaElement | null>(null)

const formats = [
  { label: 'MD', value: 'md' },
  { label: 'DOCX', value: 'docx' },
]
const selectedFormat = ref('md')

// 不支持 DOCX 的触发词
const noDocxTriggers = [
  '生成讲义', '讲义',
  '思维导图', '导图',
  '生成图文',
  '生成短视频',
  '制作PPT',
]

const docxAvailable = computed(() => {
  const text = input.value.trim()
  if (!text) return true
  return !noDocxTriggers.some(t => text.includes(t))
})

// 当 DOCX 不可用时自动切回 MD
watch(docxAvailable, (available) => {
  if (!available && selectedFormat.value === 'docx') {
    selectedFormat.value = 'md'
  }
})

interface QuickAction {
  label: string
  prompt: string
  icon: any
  supportsDocx: boolean
}

const quickActions: QuickAction[] = [
  { label: '课程大纲', prompt: '课程大纲：', icon: List, supportsDocx: true },
  { label: '讲稿', prompt: '讲稿：', icon: FileText, supportsDocx: true },
  { label: '讲义', prompt: '生成讲义：', icon: BookOpen, supportsDocx: false },
  { label: '习题集', prompt: '习题集：', icon: GraduationCap, supportsDocx: true },
  { label: '课堂测验', prompt: '课堂测验：', icon: ClipboardList, supportsDocx: true },
  { label: '知识卡片', prompt: '知识卡片：', icon: Lightbulb, supportsDocx: true },
  { label: '思维导图', prompt: '思维导图：', icon: GitBranch, supportsDocx: false },
  { label: '图文', prompt: '生成图文：', icon: ImageIcon, supportsDocx: false },
  { label: '短视频脚本', prompt: '生成短视频：', icon: Video, supportsDocx: false },
]

const isMobile = ref(window.innerWidth <= 767)
const placeholder = computed(() =>
  isMobile.value
    ? '输入主题开始生成...'
    : '描述你想生成的内容，例如：生成讲义：神经网络入门',
)

function apply(q: QuickAction) {
  input.value = q.prompt
  // 点击不支持 docx 的快捷按钮时自动切回 MD
  if (!q.supportsDocx && selectedFormat.value === 'docx') {
    selectedFormat.value = 'md'
  }
  nextTick(() => {
    const t = taRef.value
    if (t) {
      t.focus()
      t.setSelectionRange(q.prompt.length, q.prompt.length)
      autoResize({ target: t } as unknown as Event)
    }
  })
}

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function onEnter(e: KeyboardEvent) {
  if (e.shiftKey) {
    // newline
    const t = e.target as HTMLTextAreaElement
    const start = t.selectionStart
    const end = t.selectionEnd
    input.value = `${input.value.slice(0, start)}\n${input.value.slice(end)}`
    nextTick(() => {
      t.selectionStart = t.selectionEnd = start + 1
      autoResize({ target: t } as unknown as Event)
    })
    return
  }
  send()
}

function send() {
  const text = input.value.trim()
  if (!text) return
  const fmt = selectedFormat.value
  // 安全检查：如果当前内容不支持 docx，强制使用 md
  const effectiveFmt = docxAvailable.value ? fmt : 'md'
  const msg = effectiveFmt === 'docx' && !/\s*docx\s*$/i.test(text)
    ? `${text} docx`
    : text
  emit('send', msg)
  input.value = ''
  selectedFormat.value = 'md'
  nextTick(() => {
    if (taRef.value) taRef.value.style.height = 'auto'
  })
}

function onResize() {
  isMobile.value = window.innerWidth <= 767
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
@media (max-width: 767px) {
  .quick-chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .quick-chips::-webkit-scrollbar {
    display: none;
  }
}
</style>