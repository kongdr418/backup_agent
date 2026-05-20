<template>
  <div class="border-t border-line glass-chrome px-4 py-3">
    <div class="max-w-3xl mx-auto">
      <!-- Quick action chips -->
      <div v-if="!isLoading" class="flex flex-wrap gap-1.5 mb-2">
        <button
          v-for="q in quickActions"
          :key="q.label"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 text-[12px] rounded-full border border-line bg-bg-surface text-ink-2 hover:border-ink-4 hover:text-ink-1 transition-colors"
          @click="apply(q.prompt)"
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
        <div class="flex items-center gap-0.5 px-1 shrink-0">
          <button
            v-for="fmt in formats"
            :key="fmt.value"
            class="px-2 py-1 text-[12px] rounded-md transition-all"
            :class="selectedFormat === fmt.value
              ? 'bg-brand text-white shadow-sm'
              : 'text-ink-3 hover:text-ink-1'"
            @click="selectedFormat = fmt.value"
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
import { nextTick, ref } from 'vue'
import { Send, Square, FileText, BookOpen, Image as ImageIcon, Video, GraduationCap, Lightbulb } from 'lucide-vue-next'

defineProps<{ isLoading: boolean }>()
const emit = defineEmits<{ send: [text: string]; cancel: [] }>()

const input = ref('')
const taRef = ref<HTMLTextAreaElement | null>(null)

const formats = [
  { label: 'MD', value: 'md' },
  { label: 'DOCX', value: 'docx' },
]
const selectedFormat = ref('md')

const quickActions = [
  { label: '讲义', prompt: '生成讲义：', icon: BookOpen },
  { label: '讲稿', prompt: '讲稿：', icon: FileText },
  { label: '习题集', prompt: '习题集：', icon: GraduationCap },
  { label: '知识卡片', prompt: '知识卡片：', icon: Lightbulb },
  { label: '图文', prompt: '生成图文：', icon: ImageIcon },
  { label: '短视频脚本', prompt: '生成短视频：', icon: Video },
]

const placeholder = '描述你想生成的内容,例如：生成讲义：神经网络入门'

function apply(p: string) {
  input.value = p
  nextTick(() => {
    const t = taRef.value
    if (t) {
      t.focus()
      t.setSelectionRange(p.length, p.length)
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
  // Append format suffix if not already present and not MD (default)
  const msg = fmt === 'docx' && !/\s*docx\s*$/i.test(text)
    ? `${text} docx`
    : text
  emit('send', msg)
  input.value = ''
  nextTick(() => {
    if (taRef.value) taRef.value.style.height = 'auto'
  })
}
</script>
