<template>
  <div v-if="visible" class="fixed inset-0 isolate z-50 bg-black/10 supports-backdrop-filter:backdrop-blur-xs">
    <div class="flex items-center justify-center h-full p-6">
      <div class="bg-bg-surface border border-line rounded-xl shadow-elevated w-full max-w-5xl h-[85vh] flex overflow-hidden">
        <!-- Left Sidebar -->
        <aside class="w-[180px] shrink-0 bg-bg-subtle/40 flex flex-col border-r border-line">
          <div class="flex items-center gap-2 px-4 py-4 border-b border-line">
            <Settings class="w-4 h-4 text-ink-2" />
            <span class="text-sm font-medium text-ink-2">设置</span>
          </div>
          <nav class="flex-1 overflow-y-auto p-2 space-y-0.5">
            <button v-for="item in navItems" :key="item.id"
              class="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors"
              :class="activeSection === item.id ? 'bg-accent/10 text-accent font-medium' : 'text-ink-2 hover:bg-bg-surface hover:text-ink-1'"
              @click="activeSection = item.id"
            >
              <component :is="item.icon" class="w-4 h-4 shrink-0" />
              <span class="truncate">{{ item.label }}</span>
            </button>
          </nav>
        </aside>

        <!-- Right Panel -->
        <div class="flex-1 flex flex-col min-w-0">
          <!-- Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-line shrink-0">
            <div>
              <h2 class="text-base font-semibold text-ink-1">{{ currentSection?.label }}</h2>
              <p v-if="currentSection?.subtitle" class="text-xs text-ink-3 mt-0.5">{{ currentSection.subtitle }}</p>
            </div>
            <button @click="handleClose" class="w-8 h-8 rounded-lg flex items-center justify-center text-ink-3 hover:bg-bg-subtle hover:text-ink-1 transition-colors">
              <X class="w-4 h-4" />
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- ============ 对话模型 ============ -->
            <div v-if="activeSection === 'chat'" class="space-y-5 max-w-xl">
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">服务商</label>
                <n-select v-model:value="settings.chat_provider" :options="providerOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onModuleProviderChange('chat', v)" />
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">
                  API Key
                  <span v-if="chatProvider?.isServerConfigured" class="text-xs text-accent font-normal ml-1">(服务端已配置)</span>
                </label>
                <div class="flex items-start gap-2">
                  <div class="flex gap-2 flex-1 max-w-sm">
                    <n-input :value="chatConfig.apiKey" :type="showKey.chat ? 'text' : 'password'" :placeholder="chatProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'" size="small" class="flex-1" autocomplete="new-password" @update:value="(v: string) => onModuleConfigChange('chat', 'apiKey', v)" />
                    <button class="btn-eye" @click="showKey.chat = !showKey.chat"><Eye v-if="!showKey.chat" class="w-3.5 h-3.5" /><EyeOff v-else class="w-3.5 h-3.5" /></button>
                  </div>
                  <button class="btn-outline" :disabled="verifying.chat || (!chatConfig.apiKey && !chatProvider?.isServerConfigured)" @click="onTestModuleConnection('chat')"><Loader2 v-if="verifying.chat" class="w-3.5 h-3.5 animate-spin" /><Zap v-else class="w-3.5 h-3.5" />{{ verifying.chat ? '测试中...' : '测试连接' }}</button>
                </div>
                <div v-if="verifyResults.chat" class="result-card" :class="verifyResults.chat!.success ? 'result-success' : 'result-error'">
                  <CheckCircle2 v-if="verifyResults.chat!.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ verifyResults.chat!.message }}</span>
                </div>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">Base URL</label>
                <n-input v-model:value="chatConfig.baseUrl" :placeholder="chatProvider?.defaultBaseUrl || ''" size="small" class="max-w-md" @update:value="(v: string) => onModuleConfigChange('chat', 'baseUrl', v)" />
                <p v-if="chatProvider" class="text-xs text-ink-4">默认：{{ chatProvider.defaultBaseUrl }}</p>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">模型</label>
                <n-select v-model:value="settings.chat_model" :options="chatModelOptions" size="small" class="max-w-md" @update:value="onUpdate('chat_model', $event)" />
                <p class="text-xs text-ink-3">{{ chatModelHint }}</p>
              </div>
            </div>

            <!-- ============ 内容生成模型 ============ -->
            <div v-if="activeSection === 'content'" class="space-y-5 max-w-xl">
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">服务商</label>
                <n-select v-model:value="settings.content_provider" :options="openaiProviderOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onModuleProviderChange('content', v)" />
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">API Key<span v-if="contentProvider?.isServerConfigured" class="text-xs text-accent font-normal ml-1">(服务端已配置)</span></label>
                <div class="flex items-start gap-2">
                  <div class="flex gap-2 flex-1 max-w-sm">
                    <n-input :value="contentConfig.apiKey" :type="showKey.content ? 'text' : 'password'" :placeholder="contentProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'" size="small" class="flex-1" autocomplete="new-password" @update:value="(v: string) => onModuleConfigChange('content', 'apiKey', v)" />
                    <button class="btn-eye" @click="showKey.content = !showKey.content"><Eye v-if="!showKey.content" class="w-3.5 h-3.5" /><EyeOff v-else class="w-3.5 h-3.5" /></button>
                  </div>
                  <button class="btn-outline" :disabled="verifying.content || (!contentConfig.apiKey && !contentProvider?.isServerConfigured)" @click="onTestModuleConnection('content')"><Loader2 v-if="verifying.content" class="w-3.5 h-3.5 animate-spin" /><Zap v-else class="w-3.5 h-3.5" />{{ verifying.content ? '测试中...' : '测试连接' }}</button>
                </div>
                <div v-if="verifyResults.content" class="result-card" :class="verifyResults.content!.success ? 'result-success' : 'result-error'"><CheckCircle2 v-if="verifyResults.content!.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ verifyResults.content!.message }}</span></div>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">Base URL</label>
                <n-input v-model:value="contentConfig.baseUrl" :placeholder="contentProvider?.defaultBaseUrl || ''" size="small" class="max-w-md" @update:value="(v: string) => onModuleConfigChange('content', 'baseUrl', v)" />
                <p v-if="contentProvider" class="text-xs text-ink-4">默认：{{ contentProvider.defaultBaseUrl }}</p>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">模型</label>
                <n-select v-model:value="settings.content_model" :options="contentModelOptions" size="small" class="max-w-md" @update:value="onUpdate('content_model', $event)" />
                <p class="text-xs text-ink-3">{{ contentModelHint }}</p>
              </div>
            </div>

            <!-- ============ PPT 生成模型 ============ -->
            <div v-if="activeSection === 'ppt'" class="space-y-5 max-w-xl">
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">服务商</label>
                <n-select v-model:value="settings.ppt_provider" :options="openaiProviderOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onModuleProviderChange('ppt', v)" />
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">API Key<span v-if="pptProvider?.isServerConfigured" class="text-xs text-accent font-normal ml-1">(服务端已配置)</span></label>
                <div class="flex items-start gap-2">
                  <div class="flex gap-2 flex-1 max-w-sm">
                    <n-input :value="pptConfig.apiKey" :type="showKey.ppt ? 'text' : 'password'" :placeholder="pptProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'" size="small" class="flex-1" autocomplete="new-password" @update:value="(v: string) => onModuleConfigChange('ppt', 'apiKey', v)" />
                    <button class="btn-eye" @click="showKey.ppt = !showKey.ppt"><Eye v-if="!showKey.ppt" class="w-3.5 h-3.5" /><EyeOff v-else class="w-3.5 h-3.5" /></button>
                  </div>
                  <button class="btn-outline" :disabled="verifying.ppt || (!pptConfig.apiKey && !pptProvider?.isServerConfigured)" @click="onTestModuleConnection('ppt')"><Loader2 v-if="verifying.ppt" class="w-3.5 h-3.5 animate-spin" /><Zap v-else class="w-3.5 h-3.5" />{{ verifying.ppt ? '测试中...' : '测试连接' }}</button>
                </div>
                <div v-if="verifyResults.ppt" class="result-card" :class="verifyResults.ppt!.success ? 'result-success' : 'result-error'"><CheckCircle2 v-if="verifyResults.ppt!.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ verifyResults.ppt!.message }}</span></div>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">Base URL</label>
                <n-input v-model:value="pptConfig.baseUrl" :placeholder="pptProvider?.defaultBaseUrl || ''" size="small" class="max-w-md" @update:value="(v: string) => onModuleConfigChange('ppt', 'baseUrl', v)" />
                <p v-if="pptProvider" class="text-xs text-ink-4">默认：{{ pptProvider.defaultBaseUrl }}</p>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">模型</label>
                <n-select v-model:value="settings.ppt_model" :options="pptModelOptions" size="small" class="max-w-md" @update:value="onUpdate('ppt_model', $event)" />
                <p class="text-xs text-ink-3">{{ pptModelHint }}</p>
              </div>
            </div>

            <!-- ============ 语音合成模型 ============ -->
            <div v-if="activeSection === 'tts'" class="space-y-5 max-w-xl">
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">服务商</label>
                <n-select v-model:value="settings.tts_provider" :options="ttsProviderOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onTTSProviderChange(v)" />
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">API Key<span v-if="ttsProvider?.isServerConfigured" class="text-xs text-accent font-normal ml-1">(服务端已配置)</span></label>
                <div class="flex items-start gap-2">
                  <div class="flex gap-2 flex-1 max-w-sm">
                    <n-input :value="ttsConfigValue.apiKey" :type="showKey.tts ? 'text' : 'password'" :placeholder="ttsProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'" size="small" class="flex-1" autocomplete="new-password" @update:value="(v: string) => onTTSConfigChange('apiKey', v)" />
                    <button class="btn-eye" @click="showKey.tts = !showKey.tts"><Eye v-if="!showKey.tts" class="w-3.5 h-3.5" /><EyeOff v-else class="w-3.5 h-3.5" /></button>
                  </div>
                  <button class="btn-outline" :disabled="verifying.tts || (!ttsConfigValue.apiKey && !ttsProvider?.isServerConfigured)" @click="onTestTTSConnection()"><Loader2 v-if="verifying.tts" class="w-3.5 h-3.5 animate-spin" /><Zap v-else class="w-3.5 h-3.5" />{{ verifying.tts ? '测试中...' : '测试连接' }}</button>
                </div>
                <div v-if="verifyResults.tts" class="result-card" :class="verifyResults.tts!.success ? 'result-success' : 'result-error'"><CheckCircle2 v-if="verifyResults.tts!.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ verifyResults.tts!.message }}</span></div>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">Base URL</label>
                <n-input v-model:value="ttsConfigValue.baseUrl" :placeholder="ttsProvider?.defaultBaseUrl || ''" size="small" class="max-w-md" @update:value="(v: string) => onTTSConfigChange('baseUrl', v)" />
                <p v-if="ttsProvider" class="text-xs text-ink-4">默认：{{ ttsProvider.defaultBaseUrl }}</p>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">模型</label>
                <n-select v-model:value="settings.tts_model" :options="ttsModelOptions" size="small" class="max-w-md" @update:value="onUpdate('tts_model', $event)" />
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">音色</label>
                <n-select v-model:value="settings.tts_voice" :options="ttsVoiceOptions" size="small" class="max-w-md" @update:value="onUpdate('tts_voice', $event)" />
              </div>
            </div>

            <!-- ============ 小红书封面 ============ -->
            <div v-if="activeSection === 'cover'" class="space-y-5 max-w-xl">
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">比例</label>
                <n-radio-group v-model:value="settings.aspect_ratio" size="small" @update:value="onUpdate('aspect_ratio', $event)">
                  <n-radio-button value="3:4">3:4 竖图</n-radio-button>
                  <n-radio-button value="1:1">1:1 方图</n-radio-button>
                </n-radio-group>
              </div>
              <div class="space-y-1.5">
                <label class="text-sm font-medium text-ink-2">风格</label>
                <n-radio-group v-model:value="settings.cover_style" size="small" @update:value="onUpdate('cover_style', $event)">
                  <n-radio-button value="infographic">一图流文字版</n-radio-button>
                  <n-radio-button value="minimal">极简纯图版</n-radio-button>
                </n-radio-group>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end px-6 py-3 border-t border-line bg-bg-subtle/30 shrink-0">
            <button class="btn-outline" @click="handleClose">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NSelect, NRadioGroup, NRadioButton, NInput, useMessage } from 'naive-ui'
import { Settings, MessageCircle, FileText, Presentation, Volume2, Image as ImageIcon, X, Eye, EyeOff, Zap, Loader2, CheckCircle2, XCircle } from 'lucide-vue-next'
import { useSettingStore } from '@/stores/settingStore'
import { verifyModel } from '@/api/providers'
import type { ProviderInfo, TTSProviderInfo } from '@/types'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()
function handleClose() { emit('close') }

const store = useSettingStore()
const message = useMessage()
const settings = computed(() => store.settings)
type ModuleKey = 'chat' | 'content' | 'ppt' | 'tts'
const showKey = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifying = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifyResults = reactive<Record<ModuleKey, { success: boolean; message: string } | null>>({ chat: null, content: null, ppt: null, tts: null })

const activeSection = ref<string>('chat')
const navItems = [
  { id: 'chat', label: '对话模型', icon: MessageCircle, subtitle: '智能对话使用的模型' },
  { id: 'content', label: '内容生成', icon: FileText, subtitle: '讲稿、大纲、习题、测验等' },
  { id: 'ppt', label: 'PPT 生成', icon: Presentation, subtitle: 'PPT 工作台使用的模型' },
  { id: 'tts', label: '语音合成', icon: Volume2, subtitle: 'PPT 微课视频配音' },
  { id: 'cover', label: '小红书封面', icon: ImageIcon, subtitle: '封面图比例与风格' },
]
const currentSection = computed(() => navItems.find((n) => n.id === activeSection.value) ?? null)

const PROVIDER_LOGOS: Record<string, string> = {
  minimax: '/logos/minimax.svg', deepseek: '/logos/deepseek.svg', openai: '/logos/openai.svg',
  moonshot: '/logos/kimi.png', zhipu: '/logos/glm.svg', glm: '/logos/glm.svg',
  qwen: '/logos/qwen.svg', siliconflow: '/logos/siliconflow.svg',
  'minimax-tts': '/logos/xiaomi.svg',
}
const MONO_LOGOS = new Set(['openai', 'deepseek', 'siliconflow'])
function renderProviderLabel(option: { label: string; value: string }) {
  const rawId = option.value as string
  const icon = PROVIDER_LOGOS[rawId]
  if (icon) {
    const isMono = MONO_LOGOS.has(rawId)
    return h('div', { class: 'flex items-center gap-2' }, [
      h('img', { src: icon, alt: '', class: `w-4 h-4 rounded ${isMono ? 'dark:invert' : ''}`, style: 'display:block' }),
      h('span', null, option.label),
    ])
  }
  const fallbackId = rawId.replace(/-tts$/, '').replace(/-asr$/, '')
  const fallbackIcon = PROVIDER_LOGOS[fallbackId]
  if (fallbackIcon) {
    const isMono = MONO_LOGOS.has(fallbackId)
    return h('div', { class: 'flex items-center gap-2' }, [
      h('img', { src: fallbackIcon, alt: '', class: `w-4 h-4 rounded ${isMono ? 'dark:invert' : ''}`, style: 'display:block' }),
      h('span', null, option.label),
    ])
  }
  return option.label
}

const providerOptions = computed(() =>
  Object.values(store.providers).map((p: ProviderInfo) => ({
    label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`, value: p.id,
  })))
const openaiProviderOptions = computed(() =>
  Object.values(store.providers)
    .filter((p: ProviderInfo) => p.type === 'openai' || p.type === 'anthropic')
    .map((p) => ({ label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`, value: p.id })))

function moduleProvider(m: ModuleKey) {
  const k = m === 'chat' ? 'chat_provider' : m === 'content' ? 'content_provider' : 'ppt_provider'
  return computed<ProviderInfo | null>(() => store.providers[settings.value[k]] || null)
}
function moduleConfig(m: ModuleKey) {
  const k = m === 'chat' ? 'chat_provider' : m === 'content' ? 'content_provider' : 'ppt_provider'
  return computed(() => store.providersConfig[settings.value[k]] || { apiKey: '', baseUrl: '' })
}
function moduleModelOptions(m: ModuleKey) {
  return computed(() => moduleProvider(m).value?.models.map((x) => ({ label: `${x.name} (${x.id})`, value: x.id })) ?? [])
}
function moduleModelHint(m: ModuleKey) {
  const mk = m === 'chat' ? 'chat_model' : m === 'content' ? 'content_model' : 'ppt_model'
  return computed(() => {
    const p = moduleProvider(m).value; const model = p?.models.find((x) => x.id === settings.value[mk])
    if (!model) return '请选择模型'
    return `${model.contextWindow ? `上下文 ${(model.contextWindow / 1024).toFixed(0)}K` : ''}${model.maxOutput ? ` · 最大输出 ${(model.maxOutput / 1024).toFixed(0)}K` : ''}`
  })
}
const chatProvider = moduleProvider('chat'); const chatConfig = moduleConfig('chat'); const chatModelOptions = moduleModelOptions('chat'); const chatModelHint = moduleModelHint('chat')
const contentProvider = moduleProvider('content'); const contentConfig = moduleConfig('content'); const contentModelOptions = moduleModelOptions('content'); const contentModelHint = moduleModelHint('content')
const pptProvider = moduleProvider('ppt'); const pptConfig = moduleConfig('ppt'); const pptModelOptions = moduleModelOptions('ppt'); const pptModelHint = moduleModelHint('ppt')

const ttsProviderOptions = computed(() => Object.values(store.ttsProviders).map((p: TTSProviderInfo) => ({ label: `${p.name}${p.isServerConfigured ? ' · 已配置' : ''}`, value: p.id })))
const ttsProvider = computed<TTSProviderInfo | null>(() => store.ttsProviders[settings.value.tts_provider] || null)
const ttsConfigValue = computed(() => store.ttsConfig[settings.value.tts_provider] || { apiKey: '', baseUrl: '' })
const ttsModelOptions = computed(() => { const p = ttsProvider.value; return p ? p.models.map((m) => ({ label: `${m.name} (${m.id})`, value: m.id })) : [] })
const ttsVoiceOptions = computed(() => { const p = ttsProvider.value; return p ? p.voices.map((v) => ({ label: v.name, value: v.id })) : [] })

function onTTSConfigChange(k: string, v: string) { verifyResults['tts'] = null; store.setTTSConfig(settings.value.tts_provider, { [k]: v }) }
async function onTTSProviderChange(pid: string) {
  verifyResults['tts'] = null; const p = store.ttsProviders[pid]; const patch: Record<string, string> = { tts_provider: pid }
  if (p?.models.length) patch['tts_model'] = p.models[0].id; if (p?.voices.length) patch['tts_voice'] = p.voices[0].id
  await store.updateSettings(patch as Partial<typeof settings.value>)
}
async function onTestTTSConnection() {
  const p = ttsProvider.value; const c = ttsConfigValue.value; if (!p) return
  if (!c.apiKey && !p.isServerConfigured) { verifyResults['tts'] = { success: false, message: '请先填写 API Key' }; return }
  verifying['tts'] = true; verifyResults['tts'] = null
  try {
    const r = await verifyModel({ apiKey: c.apiKey, baseUrl: c.baseUrl || p.defaultBaseUrl, model: settings.value.tts_model, providerId: p.id, providerType: p.type })
    verifyResults['tts'] = r; r.success ? message.success('TTS 连接成功') : message.error(r.message)
  } catch (e) { verifyResults['tts'] = { success: false, message: e instanceof Error ? e.message : '验证失败' } }
  finally { verifying['tts'] = false }
}
const lastError = ref('')
async function onUpdate(k: string, v: unknown) {
  try { await store.updateSettings({ [k]: v as never }); message.success('已保存') }
  catch (e) { lastError.value = e instanceof Error ? e.message : String(e); message.error(lastError.value) }
}
function onModuleConfigChange(m: ModuleKey, k: string, v: string) {
  verifyResults[m] = null; store.setProviderConfig(settings.value[m === 'chat' ? 'chat_provider' : m === 'content' ? 'content_provider' : 'ppt_provider'], { [k]: v })
}
async function onModuleProviderChange(m: ModuleKey, pid: string) {
  verifyResults[m] = null; const pk = m === 'chat' ? 'chat_provider' : m === 'content' ? 'content_provider' : 'ppt_provider'
  const mk = m === 'chat' ? 'chat_model' : m === 'content' ? 'content_model' : 'ppt_model'; const p = store.providers[pid]
  if (p?.models.length) { settings.value[mk] = p.models[0].id; await store.updateSettings({ [pk]: pid, [mk]: p.models[0].id } as never) }
  else await store.updateSettings({ [pk]: pid } as never)
}
async function onTestModuleConnection(m: ModuleKey) {
  const p = moduleProvider(m).value; const c = moduleConfig(m).value; const mk = m === 'chat' ? 'chat_model' : m === 'content' ? 'content_model' : 'ppt_model'
  const model = settings.value[mk]; if (!p) return
  if (!c.apiKey && !p.isServerConfigured) { verifyResults[m] = { success: false, message: '请先填写 API Key' }; return }
  verifying[m] = true; verifyResults[m] = null
  try {
    const r = await verifyModel({ apiKey: c.apiKey, baseUrl: c.baseUrl || p.defaultBaseUrl, model, providerId: p.id, providerType: p.type })
    verifyResults[m] = r; r.success ? message.success('连接成功') : message.error(r.message)
  } catch (e) { verifyResults[m] = { success: false, message: e instanceof Error ? e.message : '验证失败' } }
  finally { verifying[m] = false }
}
onMounted(() => { store.fetchSettings().catch(() => {}); store.fetchProviders().catch(() => {}); store.fetchTTSProviders().catch(() => {}) })
</script>

<style scoped>
.btn-outline {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  height: 32px; padding: 0 12px; border-radius: 6px; font-size: 13px; font-weight: 500;
  transition: all 150ms var(--ease-out);
  border: 1px solid rgb(var(--line-rgb)); background: transparent; color: rgb(var(--ink-2-rgb));
  white-space: nowrap; flex-shrink: 0;
}
.btn-outline:hover { background: rgb(var(--bg-subtle-rgb)); color: rgb(var(--ink-1-rgb)); }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-eye {
  width: 32px; height: 32px; border-radius: 6px; border: 1px solid rgb(var(--line-rgb));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  color: rgb(var(--ink-3-rgb)); background: transparent; transition: all 150ms var(--ease-out); cursor: pointer;
}
.btn-eye:hover { background: rgb(var(--bg-subtle-rgb)); color: rgb(var(--ink-1-rgb)); }
.result-card { border-radius: 8px; border: 1px solid; padding: 12px; font-size: 13px; display: flex; align-items: flex-start; gap: 8px; }
.result-success { background: rgb(240 253 244); color: rgb(21 128 61); border-color: rgb(187 247 208); }
.result-error { background: rgb(254 242 242); color: rgb(185 28 28); border-color: rgb(254 202 202); }
:root.dark .result-success { background: rgb(22 40 26); color: rgb(74 222 128); border-color: rgb(34 84 49); }
:root.dark .result-error { background: rgb(40 22 22); color: rgb(248 113 113); border-color: rgb(84 34 34); }

@media (max-width: 767px) {
  .fixed { padding: 0; }
  .fixed .max-w-5xl { max-width: 100vw; height: 100vh; border-radius: 0; }
  .w-\[180px\] { display: none; }
}
</style>
