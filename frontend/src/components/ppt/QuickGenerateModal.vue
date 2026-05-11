<template>
  <n-modal v-model:show="visible" preset="card" :style="{ width: '480px' }" title="快速生成 PPT">
    <div class="space-y-4">
      <div>
        <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
          课程主题 <span class="text-rose-500">*</span>
        </label>
        <n-input
          v-model:value="form.topic"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 3 }"
          placeholder="例如：神经网络入门"
        />
      </div>

      <div>
        <label class="block text-[12px] font-medium text-ink-2 mb-2">风格</label>
        <n-radio-group v-model:value="form.style" size="small">
          <n-radio-button value="education">教育</n-radio-button>
          <n-radio-button value="academic">学术</n-radio-button>
          <n-radio-button value="consulting">咨询</n-radio-button>
          <n-radio-button value="tech">科技</n-radio-button>
          <n-radio-button value="general">通用</n-radio-button>
        </n-radio-group>
      </div>

      <div>
        <label class="flex items-center justify-between text-[12px] font-medium text-ink-2 mb-2">
          <span>页数</span>
          <span class="text-ink-3 font-normal">{{ form.num_slides ?? '自动' }}</span>
        </label>
        <div class="flex items-center gap-2">
          <button
            class="px-2 py-1 rounded-md text-[12px] border transition-colors"
            :class="
              form.num_slides == null
                ? 'border-ink-1 bg-bg-subtle text-ink-1'
                : 'border-line text-ink-3 hover:border-ink-4'
            "
            @click="form.num_slides = undefined"
          >
            自动
          </button>
          <n-slider
            v-model:value="sliderValue"
            :min="3"
            :max="20"
            :step="1"
            :disabled="form.num_slides == null"
            class="flex-1"
          />
        </div>
      </div>

      <div class="text-[11.5px] text-ink-3 leading-relaxed bg-bg-subtle rounded-lg p-2.5">
        提示: 提交后将跳转 PPT 工作台并自动开始生成。完整参数 (语言、画布比例、API Key) 可在工作台调整。
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <n-button @click="visible = false">取消</n-button>
        <n-button type="primary" :disabled="!canSubmit" @click="onConfirm">
          <Sparkles class="w-3.5 h-3.5 mr-1" />
          生成
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { NModal, NInput, NRadioGroup, NRadioButton, NSlider, NButton } from 'naive-ui'
import { Sparkles } from 'lucide-vue-next'
import type { PptGenerateParams } from '@/types'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  'update:show': [v: boolean]
  submit: [v: PptGenerateParams]
}>()

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

const form = reactive<PptGenerateParams>({
  topic: '',
  style: 'education',
  num_slides: undefined,
  language: 'zh',
  detail_level: 'normal',
  canvas_format: 'ppt169',
  model: 'deepseek-v4-flash',
})

watch(visible, (v) => {
  if (v) {
    Object.assign(form, {
      topic: '',
      style: 'education',
      num_slides: undefined,
      language: 'zh',
      detail_level: 'normal',
      canvas_format: 'ppt169',
      model: 'deepseek-v4-flash',
    })
  }
})

const sliderValue = computed({
  get: () => form.num_slides ?? 8,
  set: (v: number) => {
    form.num_slides = v
  },
})

const canSubmit = computed(() => !!form.topic.trim())

function onConfirm() {
  if (!canSubmit.value) return
  emit('submit', { ...form })
  visible.value = false
}
</script>
