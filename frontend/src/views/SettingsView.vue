<template>
  <div class="h-full flex flex-col">
    <PageHeader title="设置" description="自定义 AI 内容生成的偏好选项" />

    <div class="flex-1 overflow-y-auto p-6">
      <div class="max-w-2xl mx-auto space-y-5">
        <!-- Section: PPT defaults (NEW) -->
        <section class="surface-card p-5">
          <SectionTitle :icon="Presentation" title="PPT 工作台默认参数" subtitle="新建生成时的默认值" />
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">默认风格</label>
              <n-select
                v-model:value="settings.ppt_default_style"
                :options="pptStyleOptions"
                size="small"
                @update:value="onUpdate('ppt_default_style', $event)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">默认页数</label>
              <n-input-number
                v-model:value="settings.ppt_default_pages"
                :min="3"
                :max="20"
                size="small"
                class="w-full"
                @update:value="(v) => onUpdate('ppt_default_pages', v ?? 8)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">默认详细程度</label>
              <n-select
                v-model:value="settings.ppt_default_detail"
                :options="pptDetailOptions"
                size="small"
                @update:value="onUpdate('ppt_default_detail', $event)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">默认模型</label>
              <n-input
                v-model:value="settings.ppt_default_model"
                size="small"
                placeholder="deepseek-v4-flash"
                @update:value="onUpdate('ppt_default_model', $event)"
              />
            </div>
          </div>
        </section>

        <!-- Section: Voice -->
        <section class="surface-card p-5">
          <SectionTitle :icon="Volume2" title="语音合成" subtitle="短视频脚本配音使用的声音与风格" />
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">声音</label>
              <n-select
                v-model:value="settings.mimo_voice"
                :options="voiceOptions"
                size="small"
                @update:value="onUpdate('mimo_voice', $event)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">风格</label>
              <n-select
                v-model:value="settings.mimo_style"
                :options="styleOptions"
                size="small"
                @update:value="onUpdate('mimo_style', $event)"
              />
            </div>
          </div>
        </section>

        <!-- Section: Cover -->
        <section class="surface-card p-5">
          <SectionTitle :icon="ImageIcon" title="小红书封面" subtitle="封面图比例与风格" />
          <div class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-2">比例</label>
              <n-radio-group
                v-model:value="settings.aspect_ratio"
                size="small"
                @update:value="onUpdate('aspect_ratio', $event)"
              >
                <n-radio-button value="3:4">3:4 竖图</n-radio-button>
                <n-radio-button value="1:1">1:1 方图</n-radio-button>
              </n-radio-group>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-2">风格</label>
              <n-radio-group
                v-model:value="settings.cover_style"
                size="small"
                @update:value="onUpdate('cover_style', $event)"
              >
                <n-radio-button value="infographic">一图流文字版</n-radio-button>
                <n-radio-button value="minimal">极简纯图版</n-radio-button>
              </n-radio-group>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NSelect,
  NRadioGroup,
  NRadioButton,
  NInput,
  NInputNumber,
  useMessage,
} from 'naive-ui'
import { Volume2, Image as ImageIcon, Presentation } from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import SectionTitle from './_SettingsSection.vue'

import { useSettingStore } from '@/stores/settingStore'

const store = useSettingStore()
const message = useMessage()

const settings = computed(() => store.settings)

const voiceOptions = computed(() =>
  store.options.mimo_voice?.map((o) => ({ label: o.label, value: o.value })) ?? [
    { label: 'MiMo-默认', value: 'mimo_default' },
  ],
)
const styleOptions = computed(() =>
  store.options.mimo_style?.map((o) => ({ label: o.label, value: o.value })) ?? [
    { label: '无 (默认)', value: '' },
  ],
)

const pptStyleOptions = [
  { label: '教育课件', value: 'education' },
  { label: '学术', value: 'academic' },
  { label: '咨询', value: 'consulting' },
  { label: '科技', value: 'tech' },
  { label: '通用', value: 'general' },
]

const pptDetailOptions = [
  { label: '简略', value: 'brief' },
  { label: '正常', value: 'normal' },
  { label: '详细', value: 'detailed' },
]

const lastError = ref('')
async function onUpdate(key: string, value: unknown) {
  try {
    await store.updateSettings({ [key]: value as never })
    message.success('已保存')
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : String(e)
    message.error(lastError.value)
  }
}

onMounted(() => {
  store.fetchSettings().catch((e) => {
    message.error(e instanceof Error ? e.message : '设置加载失败')
  })
})
</script>
