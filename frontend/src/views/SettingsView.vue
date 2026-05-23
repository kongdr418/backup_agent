<template>
  <div class="h-full flex flex-col">
    <PageHeader title="设置" description="自定义 AI 内容生成的偏好选项" />

    <div class="flex-1 overflow-y-auto p-6 settings-content">
      <div class="max-w-2xl mx-auto space-y-5">
        <!-- ==================== 对话模型 ==================== -->
        <section class="surface-card p-5">
          <SectionTitle :icon="MessageCircle" title="对话模型" subtitle="智能对话使用的模型" />
          <div class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">服务商</label>
              <n-select
                v-model:value="settings.chat_provider"
                :options="providerOptions"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleProviderChange('chat', v)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
                API Key
                <span v-if="chatProvider?.isServerConfigured" class="text-[10px] text-green-600 font-normal ml-1">(服务端已配置)</span>
              </label>
              <div class="flex gap-2" style="max-width: 420px">
                <n-input
                  :value="chatConfig.apiKey"
                  :type="showKey.chat ? 'text' : 'password'"
                  :placeholder="chatProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'"
                  size="small"
                  class="flex-1"
                  autocomplete="new-password"
                  @update:value="(v: string) => onModuleConfigChange('chat', 'apiKey', v)"
                />
                <button
                  class="w-8 h-8 rounded-md border border-line flex items-center justify-center shrink-0 hover:bg-bg-subtle transition-colors"
                  @click="showKey.chat = !showKey.chat"
                >
                  <Eye v-if="!showKey.chat" class="w-4 h-4 text-ink-3" />
                  <EyeOff v-else class="w-4 h-4 text-ink-3" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">Base URL</label>
              <n-input
                v-model:value="chatConfig.baseUrl"
                :placeholder="chatProvider?.defaultBaseUrl || ''"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleConfigChange('chat', 'baseUrl', v)"
              />
              <p v-if="chatProvider" class="text-[10px] text-ink-4 mt-1">默认：{{ chatProvider.defaultBaseUrl }}</p>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">模型</label>
              <n-select
                v-model:value="settings.chat_model"
                :options="chatModelOptions"
                size="small"
                style="max-width: 420px"
                @update:value="onUpdate('chat_model', $event)"
              />
              <p class="text-[11px] text-ink-3 mt-1.5">{{ chatModelHint }}</p>
            </div>
            <div class="flex items-center gap-3">
              <button
                class="h-8 px-4 rounded-md text-[12px] font-medium border border-line hover:bg-bg-subtle inline-flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="verifying.chat || (!chatConfig.apiKey && !chatProvider?.isServerConfigured)"
                @click="onTestModuleConnection('chat')"
              >
                <Loader2 v-if="verifying.chat" class="w-3.5 h-3.5 animate-spin" />
                <Zap v-else class="w-3.5 h-3.5" />
                {{ verifying.chat ? '测试中...' : '测试连接' }}
              </button>
              <div v-if="verifyResults.chat" class="flex items-center gap-1.5 text-[12px]" :class="verifyResults.chat!.success ? 'text-green-600' : 'text-red-500'">
                <CheckCircle2 v-if="verifyResults.chat!.success" class="w-4 h-4" />
                <XCircle v-else class="w-4 h-4" />
                <span>{{ verifyResults.chat!.message }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ==================== 内容生成模型 ==================== -->
        <section class="surface-card p-5">
          <SectionTitle :icon="FileText" title="内容生成模型" subtitle="讲稿、大纲、习题、测验、知识卡片、思维导图等（仅支持 OpenAI 兼容 API）" />
          <div class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">服务商</label>
              <n-select
                v-model:value="settings.content_provider"
                :options="openaiProviderOptions"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleProviderChange('content', v)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
                API Key
                <span v-if="contentProvider?.isServerConfigured" class="text-[10px] text-green-600 font-normal ml-1">(服务端已配置)</span>
              </label>
              <div class="flex gap-2" style="max-width: 420px">
                <n-input
                  :value="contentConfig.apiKey"
                  :type="showKey.content ? 'text' : 'password'"
                  :placeholder="contentProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'"
                  size="small"
                  class="flex-1"
                  autocomplete="new-password"
                  @update:value="(v: string) => onModuleConfigChange('content', 'apiKey', v)"
                />
                <button
                  class="w-8 h-8 rounded-md border border-line flex items-center justify-center shrink-0 hover:bg-bg-subtle transition-colors"
                  @click="showKey.content = !showKey.content"
                >
                  <Eye v-if="!showKey.content" class="w-4 h-4 text-ink-3" />
                  <EyeOff v-else class="w-4 h-4 text-ink-3" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">Base URL</label>
              <n-input
                v-model:value="contentConfig.baseUrl"
                :placeholder="contentProvider?.defaultBaseUrl || ''"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleConfigChange('content', 'baseUrl', v)"
              />
              <p v-if="contentProvider" class="text-[10px] text-ink-4 mt-1">默认：{{ contentProvider.defaultBaseUrl }}</p>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">模型</label>
              <n-select
                v-model:value="settings.content_model"
                :options="contentModelOptions"
                size="small"
                style="max-width: 420px"
                @update:value="onUpdate('content_model', $event)"
              />
              <p class="text-[11px] text-ink-3 mt-1.5">{{ contentModelHint }}</p>
            </div>
            <div class="flex items-center gap-3">
              <button
                class="h-8 px-4 rounded-md text-[12px] font-medium border border-line hover:bg-bg-subtle inline-flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="verifying.content || (!contentConfig.apiKey && !contentProvider?.isServerConfigured)"
                @click="onTestModuleConnection('content')"
              >
                <Loader2 v-if="verifying.content" class="w-3.5 h-3.5 animate-spin" />
                <Zap v-else class="w-3.5 h-3.5" />
                {{ verifying.content ? '测试中...' : '测试连接' }}
              </button>
              <div v-if="verifyResults.content" class="flex items-center gap-1.5 text-[12px]" :class="verifyResults.content!.success ? 'text-green-600' : 'text-red-500'">
                <CheckCircle2 v-if="verifyResults.content!.success" class="w-4 h-4" />
                <XCircle v-else class="w-4 h-4" />
                <span>{{ verifyResults.content!.message }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ==================== PPT 生成模型 ==================== -->
        <section class="surface-card p-5">
          <SectionTitle :icon="Presentation" title="PPT 生成模型" subtitle="PPT 工作台使用的模型（仅支持 OpenAI 兼容 API）" />
          <div class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">服务商</label>
              <n-select
                v-model:value="settings.ppt_provider"
                :options="openaiProviderOptions"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleProviderChange('ppt', v)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
                API Key
                <span v-if="pptProvider?.isServerConfigured" class="text-[10px] text-green-600 font-normal ml-1">(服务端已配置)</span>
              </label>
              <div class="flex gap-2" style="max-width: 420px">
                <n-input
                  :value="pptConfig.apiKey"
                  :type="showKey.ppt ? 'text' : 'password'"
                  :placeholder="pptProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'"
                  size="small"
                  class="flex-1"
                  autocomplete="new-password"
                  @update:value="(v: string) => onModuleConfigChange('ppt', 'apiKey', v)"
                />
                <button
                  class="w-8 h-8 rounded-md border border-line flex items-center justify-center shrink-0 hover:bg-bg-subtle transition-colors"
                  @click="showKey.ppt = !showKey.ppt"
                >
                  <Eye v-if="!showKey.ppt" class="w-4 h-4 text-ink-3" />
                  <EyeOff v-else class="w-4 h-4 text-ink-3" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">Base URL</label>
              <n-input
                v-model:value="pptConfig.baseUrl"
                :placeholder="pptProvider?.defaultBaseUrl || ''"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onModuleConfigChange('ppt', 'baseUrl', v)"
              />
              <p v-if="pptProvider" class="text-[10px] text-ink-4 mt-1">默认：{{ pptProvider.defaultBaseUrl }}</p>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">模型</label>
              <n-select
                v-model:value="settings.ppt_model"
                :options="pptModelOptions"
                size="small"
                style="max-width: 420px"
                @update:value="onUpdate('ppt_model', $event)"
              />
              <p class="text-[11px] text-ink-3 mt-1.5">{{ pptModelHint }}</p>
            </div>
            <div class="flex items-center gap-3">
              <button
                class="h-8 px-4 rounded-md text-[12px] font-medium border border-line hover:bg-bg-subtle inline-flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="verifying.ppt || (!pptConfig.apiKey && !pptProvider?.isServerConfigured)"
                @click="onTestModuleConnection('ppt')"
              >
                <Loader2 v-if="verifying.ppt" class="w-3.5 h-3.5 animate-spin" />
                <Zap v-else class="w-3.5 h-3.5" />
                {{ verifying.ppt ? '测试中...' : '测试连接' }}
              </button>
              <div v-if="verifyResults.ppt" class="flex items-center gap-1.5 text-[12px]" :class="verifyResults.ppt!.success ? 'text-green-600' : 'text-red-500'">
                <CheckCircle2 v-if="verifyResults.ppt!.success" class="w-4 h-4" />
                <XCircle v-else class="w-4 h-4" />
                <span>{{ verifyResults.ppt!.message }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ==================== TTS 语音合成模型 ==================== -->
        <section class="surface-card p-5">
          <SectionTitle :icon="Volume2" title="语音合成模型" subtitle="PPT 微课视频配音使用的 TTS 模型" />
          <div class="space-y-4">
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">服务商</label>
              <n-select
                v-model:value="settings.tts_provider"
                :options="ttsProviderOptions"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onTTSProviderChange(v)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">
                API Key
                <span v-if="ttsProvider?.isServerConfigured" class="text-[10px] text-green-600 font-normal ml-1">(服务端已配置)</span>
              </label>
              <div class="flex gap-2" style="max-width: 420px">
                <n-input
                  :value="ttsConfigValue.apiKey"
                  :type="showKey.tts ? 'text' : 'password'"
                  :placeholder="ttsProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'"
                  size="small"
                  class="flex-1"
                  autocomplete="new-password"
                  @update:value="(v: string) => onTTSConfigChange('apiKey', v)"
                />
                <button
                  class="w-8 h-8 rounded-md border border-line flex items-center justify-center shrink-0 hover:bg-bg-subtle transition-colors"
                  @click="showKey.tts = !showKey.tts"
                >
                  <Eye v-if="!showKey.tts" class="w-4 h-4 text-ink-3" />
                  <EyeOff v-else class="w-4 h-4 text-ink-3" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">Base URL</label>
              <n-input
                v-model:value="ttsConfigValue.baseUrl"
                :placeholder="ttsProvider?.defaultBaseUrl || ''"
                size="small"
                style="max-width: 420px"
                @update:value="(v: string) => onTTSConfigChange('baseUrl', v)"
              />
              <p v-if="ttsProvider" class="text-[10px] text-ink-4 mt-1">默认：{{ ttsProvider.defaultBaseUrl }}</p>
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">模型</label>
              <n-select
                v-model:value="settings.tts_model"
                :options="ttsModelOptions"
                size="small"
                style="max-width: 420px"
                @update:value="onUpdate('tts_model', $event)"
              />
            </div>
            <div>
              <label class="block text-[12px] font-medium text-ink-2 mb-1.5">音色</label>
              <n-select
                v-model:value="settings.tts_voice"
                :options="ttsVoiceOptions"
                size="small"
                style="max-width: 420px"
                @update:value="onUpdate('tts_voice', $event)"
              />
            </div>
            <div class="flex items-center gap-3">
              <button
                class="h-8 px-4 rounded-md text-[12px] font-medium border border-line hover:bg-bg-subtle inline-flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="verifying.tts || (!ttsConfigValue.apiKey && !ttsProvider?.isServerConfigured)"
                @click="onTestTTSConnection()"
              >
                <Loader2 v-if="verifying.tts" class="w-3.5 h-3.5 animate-spin" />
                <Zap v-else class="w-3.5 h-3.5" />
                {{ verifying.tts ? '测试中...' : '测试连接' }}
              </button>
              <div v-if="verifyResults.tts" class="flex items-center gap-1.5 text-[12px]" :class="verifyResults.tts!.success ? 'text-green-600' : 'text-red-500'">
                <CheckCircle2 v-if="verifyResults.tts!.success" class="w-4 h-4" />
                <XCircle v-else class="w-4 h-4" />
                <span>{{ verifyResults.tts!.message }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ==================== 小红书封面 ==================== -->
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
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NSelect,
  NRadioGroup,
  NRadioButton,
  NInput,
  useMessage,
} from 'naive-ui'
import {
  Volume2,
  Image as ImageIcon,
  Presentation,
  MessageCircle,
  FileText,
  Eye,
  EyeOff,
  Zap,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import SectionTitle from './_SettingsSection.vue'

import { useSettingStore } from '@/stores/settingStore'
import { verifyModel } from '@/api/providers'
import type { ProviderInfo, TTSProviderInfo } from '@/types'

const store = useSettingStore()
const message = useMessage()

const settings = computed(() => store.settings)

type ModuleKey = 'chat' | 'content' | 'ppt' | 'tts'

const showKey = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifying = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifyResults = reactive<Record<ModuleKey, { success: boolean; message: string } | null>>({ chat: null, content: null, ppt: null, tts: null })

// 通用 provider 选项（对话可用所有 provider，含 MiniMax）
const providerOptions = computed(() =>
  Object.values(store.providers).map((p: ProviderInfo) => ({
    label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`,
    value: p.id,
  })),
)

// 内容生成 / PPT 生成只能用 OpenAI 兼容的 provider
const openaiProviderOptions = computed(() =>
  Object.values(store.providers)
    .filter((p: ProviderInfo) => p.type === 'openai')
    .map((p) => ({
      label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`,
      value: p.id,
    })),
)

// --- 每个模块的 provider / config / model 计算属性 ---
function moduleProvider(module: ModuleKey) {
  const key = module === 'chat' ? 'chat_provider' : module === 'content' ? 'content_provider' : 'ppt_provider'
  return computed<ProviderInfo | null>(() => store.providers[settings.value[key]] || null)
}
function moduleConfig(module: ModuleKey) {
  const key = module === 'chat' ? 'chat_provider' : module === 'content' ? 'content_provider' : 'ppt_provider'
  return computed(() => store.providersConfig[settings.value[key]] || { apiKey: '', baseUrl: '' })
}
function moduleModelOptions(module: ModuleKey) {
  return computed(() => {
    const provider = moduleProvider(module).value
    if (!provider) return []
    return provider.models.map((m) => ({
      label: `${m.name} (${m.id})`,
      value: m.id,
    }))
  })
}
function moduleModelHint(module: ModuleKey) {
  const modelKey = module === 'chat' ? 'chat_model' : module === 'content' ? 'content_model' : 'ppt_model'
  return computed(() => {
    const provider = moduleProvider(module).value
    const model = provider?.models.find((m) => m.id === settings.value[modelKey])
    if (!model) return '请选择模型'
    return `${model.contextWindow ? `上下文 ${(model.contextWindow / 1024).toFixed(0)}K` : ''}${model.maxOutput ? ` · 最大输出 ${(model.maxOutput / 1024).toFixed(0)}K` : ''}`
  })
}

const chatProvider = moduleProvider('chat')
const chatConfig = moduleConfig('chat')
const chatModelOptions = moduleModelOptions('chat')
const chatModelHint = moduleModelHint('chat')

const contentProvider = moduleProvider('content')
const contentConfig = moduleConfig('content')
const contentModelOptions = moduleModelOptions('content')
const contentModelHint = moduleModelHint('content')

const pptProvider = moduleProvider('ppt')
const pptConfig = moduleConfig('ppt')
const pptModelOptions = moduleModelOptions('ppt')
const pptModelHint = moduleModelHint('ppt')

// --- TTS 模块 ---
const ttsProviderOptions = computed(() =>
  Object.values(store.ttsProviders).map((p: TTSProviderInfo) => ({
    label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`,
    value: p.id,
  })),
)
const ttsProvider = computed<TTSProviderInfo | null>(() => store.ttsProviders[settings.value.tts_provider] || null)
const ttsConfigValue = computed(() => store.ttsConfig[settings.value.tts_provider] || { apiKey: '', baseUrl: '' })
const ttsModelOptions = computed(() => {
  const p = ttsProvider.value
  if (!p) return []
  return p.models.map((m) => ({ label: `${m.name} (${m.id})`, value: m.id }))
})
const ttsVoiceOptions = computed(() => {
  const p = ttsProvider.value
  if (!p) return []
  return p.voices.map((v) => ({ label: v.name, value: v.id }))
})

function onTTSConfigChange(key: string, value: string) {
  verifyResults['tts'] = null
  store.setTTSConfig(settings.value.tts_provider, { [key]: value })
}

async function onTTSProviderChange(providerId: string) {
  verifyResults['tts'] = null
  const provider = store.ttsProviders[providerId]
  const patch: Record<string, string> = { tts_provider: providerId }
  if (provider && provider.models.length > 0) {
    patch['tts_model'] = provider.models[0].id
  }
  if (provider && provider.voices.length > 0) {
    patch['tts_voice'] = provider.voices[0].id
  }
  await store.updateSettings(patch as Partial<typeof settings.value>)
}

async function onTestTTSConnection() {
  const provider = ttsProvider.value
  const config = ttsConfigValue.value
  if (!provider) return
  if (!config.apiKey && !provider.isServerConfigured) {
    verifyResults['tts'] = { success: false, message: '请先填写 API Key' }
    return
  }

  verifying['tts'] = true
  verifyResults['tts'] = null

  try {
    const result = await verifyModel({
      apiKey: config.apiKey,
      baseUrl: config.baseUrl || provider.defaultBaseUrl,
      model: settings.value.tts_model,
      providerId: provider.id,
      providerType: provider.type,
    })
    verifyResults['tts'] = result
    if (result.success) {
      message.success('TTS 连接成功')
    } else {
      message.error(result.message)
    }
  } catch (e) {
    verifyResults['tts'] = { success: false, message: e instanceof Error ? e.message : '验证失败' }
  } finally {
    verifying['tts'] = false
  }
}

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

function onModuleConfigChange(module: ModuleKey, key: string, value: string) {
  verifyResults[module] = null
  const providerKey = module === 'chat' ? 'chat_provider' : module === 'content' ? 'content_provider' : 'ppt_provider'
  store.setProviderConfig(settings.value[providerKey], { [key]: value })
}

async function onModuleProviderChange(module: ModuleKey, providerId: string) {
  verifyResults[module] = null
  const providerKey = module === 'chat' ? 'chat_provider' : module === 'content' ? 'content_provider' : 'ppt_provider'
  const modelKey = module === 'chat' ? 'chat_model' : module === 'content' ? 'content_model' : 'ppt_model'
  const provider = store.providers[providerId]
  if (provider && provider.models.length > 0) {
    const firstModel = provider.models[0].id
    settings.value[modelKey] = firstModel
    await store.updateSettings({ [providerKey]: providerId, [modelKey]: firstModel })
  } else {
    await store.updateSettings({ [providerKey]: providerId })
  }
}

async function onTestModuleConnection(module: ModuleKey) {
  const provider = moduleProvider(module).value
  const config = moduleConfig(module).value
  const modelKey = module === 'chat' ? 'chat_model' : module === 'content' ? 'content_model' : 'ppt_model'
  const model = settings.value[modelKey]

  if (!provider) return
  if (!config.apiKey && !provider.isServerConfigured) {
    verifyResults[module] = { success: false, message: '请先填写 API Key' }
    return
  }

  verifying[module] = true
  verifyResults[module] = null

  try {
    const result = await verifyModel({
      apiKey: config.apiKey,
      baseUrl: config.baseUrl || provider.defaultBaseUrl,
      model,
      providerId: provider.id,
      providerType: provider.type,
    })
    verifyResults[module] = result
    if (result.success) {
      message.success('连接成功')
    } else {
      message.error(result.message)
    }
  } catch (e) {
    verifyResults[module] = { success: false, message: e instanceof Error ? e.message : '验证失败' }
  } finally {
    verifying[module] = false
  }
}

onMounted(() => {
  store.fetchSettings().catch((e) => {
    message.error(e instanceof Error ? e.message : '设置加载失败')
  })
  store.fetchProviders().catch(() => {
    // providers 加载失败不影响已有功能
  })
  store.fetchTTSProviders().catch(() => {
    // tts providers 加载失败不影响已有功能
  })
})
</script>

<style scoped>
/* ============ Mobile ============ */
@media (max-width: 767px) {
  .settings-content {
    padding: 14px;
  }

  .settings-content :deep(.surface-card) {
    padding: 16px !important;
  }

  .settings-content :deep(.grid) {
    grid-template-columns: 1fr;
  }
}
</style>
