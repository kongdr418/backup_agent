<template>
  <div class="h-full overflow-y-auto bg-bg-surface border-r border-line">
    <div class="p-5 space-y-5">
      <!-- Topic -->
      <section>
        <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
          课程主题 <span class="text-rose-500">*</span>
        </label>
        <n-input
          v-model:value="local.topic"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="例如：神经网络入门、量子力学基础、营销心理学..."
          :disabled="disabled"
        />
      </section>

      <!-- Style -->
      <section>
        <div class="flex items-center justify-between mb-2">
          <label class="text-[12px] font-medium text-ink-2">设计风格</label>
        </div>
        <div class="flex flex-col gap-2">
          <StyleCard
            v-for="opt in styleOptions"
            :key="opt.value"
            :label="opt.label"
            :description="opt.desc"
            :icon="opt.icon"
            :tone="opt.tone"
            :selected="local.style === opt.value"
            @select="local.style = opt.value"
          />
        </div>
      </section>

      <!-- Pages -->
      <section>
        <div class="flex items-center justify-between mb-2">
          <label class="text-[12px] font-medium text-ink-2">页数</label>
          <span class="text-[12px] text-ink-3">{{ pageDisplay }}</span>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="px-2 py-1 rounded-md text-[12px] border transition-colors"
            :class="
              local.num_slides == null
                ? 'border-ink-1 bg-bg-subtle text-ink-1'
                : 'border-line text-ink-3 hover:border-ink-4'
            "
            @click="local.num_slides = undefined"
          >
            自动
          </button>
          <n-slider
            v-model:value="sliderValue"
            :min="3"
            :max="20"
            :step="1"
            class="flex-1"
          />
        </div>
      </section>

      <!-- Detail level -->
      <section>
        <label class="block text-[12px] font-medium text-ink-2 mb-2">详细程度</label>
        <n-radio-group v-model:value="local.detail_level" :disabled="disabled" size="small">
          <n-radio-button value="brief">简略</n-radio-button>
          <n-radio-button value="normal">正常</n-radio-button>
          <n-radio-button value="detailed">详细</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Language -->
      <section>
        <label class="block text-[12px] font-medium text-ink-2 mb-2">语言</label>
        <n-radio-group v-model:value="local.language" :disabled="disabled" size="small">
          <n-radio-button value="zh">中文</n-radio-button>
          <n-radio-button value="en">English</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Canvas format -->
      <section>
        <label class="block text-[12px] font-medium text-ink-2 mb-2">画布比例</label>
        <n-radio-group v-model:value="local.canvas_format" :disabled="disabled" size="small">
          <n-radio-button value="ppt169">16:9 (推荐)</n-radio-button>
          <n-radio-button value="ppt43">4:3</n-radio-button>
        </n-radio-group>
      </section>

      <!-- Advanced -->
      <details class="group">
        <summary
          class="cursor-pointer list-none text-[12px] text-ink-3 inline-flex items-center gap-1 hover:text-ink-1"
        >
          <ChevronRight
            class="w-3 h-3 transition-transform group-open:rotate-90"
          />
          高级设置
        </summary>
        <div class="mt-3 space-y-3">
          <div>
            <label class="block text-[12px] font-medium text-ink-2 mb-1.5">模型</label>
            <n-input v-model:value="local.model" placeholder="deepseek-v4-flash" :disabled="disabled" size="small" />
          </div>
          <div>
            <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
              API Key (可选,覆盖服务端)
            </label>
            <n-input
              v-model:value="local.api_key"
              placeholder="留空则使用服务端配置"
              type="password"
              show-password-on="click"
              :disabled="disabled"
              size="small"
            />
          </div>
        </div>
      </details>

      <!-- Action -->
      <div class="pt-2 sticky bottom-0 bg-bg-surface">
        <button
          v-if="!disabled"
          class="w-full h-10 rounded-lg bg-brand text-white text-[13.5px] font-medium hover:bg-brand-hover disabled:opacity-50 disabled:hover:bg-brand transition-colors inline-flex items-center justify-center gap-2"
          :disabled="!canSubmit"
          @click="$emit('generate')"
        >
          <Sparkles class="w-3.5 h-3.5" />
          开始生成
        </button>

        <button
          v-else
          class="w-full h-10 rounded-lg bg-rose-50 text-rose-600 text-[13.5px] font-medium hover:bg-rose-100 transition-colors inline-flex items-center justify-center gap-2"
          @click="$emit('cancel')"
        >
          <Square class="w-3.5 h-3.5" />
          停止生成
        </button>
        <p class="text-[11px] text-ink-4 mt-2 text-center leading-relaxed">
          生成耗时与页数相关，通常需要 6~7 分钟，页数较多时可能超过 10 分钟
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { NInput, NSlider, NRadioGroup, NRadioButton } from 'naive-ui'
import {
  GraduationCap,
  Microscope,
  Briefcase,
  Cpu,
  LayoutGrid,
  ChevronRight,
  Sparkles,
  Square,
} from 'lucide-vue-next'
import StyleCard from './StyleCard.vue'
import type { PptGenerateParams } from '@/types'

const props = defineProps<{
  modelValue: PptGenerateParams
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PptGenerateParams]
  generate: []
  cancel: []
}>()

const local = reactive<PptGenerateParams>({ ...props.modelValue })

watch(
  () => props.modelValue,
  (v) => {
    Object.assign(local, v)
  },
  { deep: true },
)

watch(local, (v) => emit('update:modelValue', { ...v }), { deep: true })

const styleOptions: Array<{
  value: 'education' | 'academic' | 'consulting' | 'tech' | 'general'
  label: string
  desc: string
  icon: typeof GraduationCap
  tone: 'slate' | 'emerald' | 'amber' | 'sky' | 'violet'
}> = [
  { value: 'education', label: '教育课件', desc: '简洁清晰,适合教学场景', icon: GraduationCap, tone: 'sky' },
  { value: 'academic', label: '学术', desc: '严谨规范,论文报告范式', icon: Microscope, tone: 'slate' },
  { value: 'consulting', label: '咨询', desc: '商务专业,数据驱动叙事', icon: Briefcase, tone: 'amber' },
  { value: 'tech', label: '科技', desc: '现代极简,产品介绍风', icon: Cpu, tone: 'violet' },
  { value: 'general', label: '通用', desc: '中性百搭,适配各类话题', icon: LayoutGrid, tone: 'emerald' },
]

const sliderValue = computed({
  get: () => local.num_slides ?? 8,
  set: (v: number) => {
    local.num_slides = v
  },
})

const pageDisplay = computed(() =>
  local.num_slides == null ? '由 AI 自动决定' : `${local.num_slides} 页`,
)

const canSubmit = computed(
  () => !!local.topic && local.topic.trim().length > 0 && !props.disabled,
)
</script>
