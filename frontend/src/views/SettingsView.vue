<template>
  <div class="h-full flex flex-col">
    <PageHeader title="设置" description="自定义 AI 内容生成的偏好选项" />

    <div class="flex-1 overflow-y-auto p-6 settings-content">
      <div class="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- 对话模型 -->
        <section class="bg-bg-surface border border-line rounded-card shadow-card">
          <div class="px-5 py-4 border-b border-line/30">
            <SectionTitle :icon="MessageCircle" title="对话模型" subtitle="智能对话使用的模型" />
          </div>
          <div class="px-5 py-4 space-y-5">
            <div class="space-y-1.5">
              <label class="text-sm font-medium text-ink-2">服务商</label>
              <n-select v-model:value="settings.chat_provider" :options="providerOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onModuleProviderChange('chat', v)" />
            </div>
            <div class="space-y-1.5">
              <label class="text-sm font-medium text-ink-2">API Key<span v-if="chatProvider?.isServerConfigured" class="text-xs text-accent font-normal ml-1">(服务端已配置)</span></label>
              <div class="flex items-start gap-2">
                <div class="flex gap-2 flex-1 max-w-sm">
                  <n-input :value="chatConfig.apiKey" :type="showKey.chat ? 'text' : 'password'" :placeholder="chatProvider?.isServerConfigured ? '可选覆盖服务端 Key' : '请输入 API Key'" size="small" class="flex-1" autocomplete="new-password" @update:value="(v: string) => onModuleConfigChange('chat', 'apiKey', v)" />
                  <button class="btn-eye" @click="showKey.chat = !showKey.chat"><Eye v-if="!showKey.chat" class="w-3.5 h-3.5" /><EyeOff v-else class="w-3.5 h-3.5" /></button>
                </div>
                <button class="btn-outline" :disabled="verifying.chat || (!chatConfig.apiKey && !chatProvider?.isServerConfigured)" @click="onTestModuleConnection('chat')"><Loader2 v-if="verifying.chat" class="w-3.5 h-3.5 animate-spin" /><Zap v-else class="w-3.5 h-3.5" />{{ verifying.chat ? '测试中...' : '测试连接' }}</button>
              </div>
              <div v-if="verifyResults.chat" class="result-card" :class="verifyResults.chat!.success ? 'result-success' : 'result-error'"><CheckCircle2 v-if="verifyResults.chat!.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ verifyResults.chat!.message }}</span></div>
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
        </section>

        <!-- 内容生成 -->
        <section class="bg-bg-surface border border-line rounded-card shadow-card">
          <div class="px-5 py-4 border-b border-line/30">
            <SectionTitle :icon="FileText" title="内容生成模型" subtitle="讲稿、大纲、习题、测验、知识卡片、思维导图等" />
          </div>
          <div class="px-5 py-4 space-y-5">
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
        </section>

        <!-- PPT 生成 -->
        <section class="bg-bg-surface border border-line rounded-card shadow-card">
          <div class="px-5 py-4 border-b border-line/30">
            <SectionTitle :icon="Presentation" title="PPT 生成模型" subtitle="PPT 工作台使用的模型" />
          </div>
          <div class="px-5 py-4 space-y-5">
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
        </section>

        <!-- 语音合成 -->
        <section class="bg-bg-surface border border-line rounded-card shadow-card">
          <div class="px-5 py-4 border-b border-line/30">
            <SectionTitle :icon="Volume2" title="语音合成模型" subtitle="PPT 微课视频配音使用的 TTS 模型" />
          </div>
          <div class="px-5 py-4 space-y-5">
            <div class="space-y-1.5">
              <label class="text-sm font-medium text-ink-2">服务商</label>
              <n-select v-model:value="settings.tts_provider" :options="ttsProviderOptions" :render-label="renderProviderLabel" size="small" class="max-w-md" @update:value="(v: string) => onTTSProviderChange(v)" />
            </div>
            <template v-if="ttsProvider?.requiresApiKey">
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
            </template>
            <div class="space-y-1.5">
              <label class="text-sm font-medium text-ink-2">音色</label>
              <n-select v-model:value="settings.tts_voice" :options="ttsVoiceOptions" size="small" class="max-w-md" @update:value="onUpdate('tts_voice', $event)" />
            </div>
            <!-- TTS 测试 -->
            <div class="space-y-2 pt-3 border-t border-line/30 px-5 pb-5">
              <label class="text-sm font-medium text-ink-2">TTS 测试</label>
              <div class="flex items-start gap-2">
                <n-input v-model:value="ttsTestText" placeholder="输入要合成的文本..." size="small" class="flex-1 max-w-sm" @keyup.enter="onTestTtsPlay" />
                <button class="btn-outline" :disabled="ttsTesting || !ttsTestText.trim()" @click="onTestTtsPlay">
                  <Loader2 v-if="ttsTesting" class="w-3.5 h-3.5 animate-spin" /><Volume2 v-else class="w-3.5 h-3.5" />{{ ttsTesting ? '合成中...' : '播放' }}
                </button>
              </div>
              <audio ref="ttsAudioRef" :src="ttsAudioUrl" style="display:none" @ended="ttsAudioUrl = null" />
              <div v-if="ttsTestResult" class="result-card" :class="ttsTestResult.success ? 'result-success' : 'result-error'">
                <CheckCircle2 v-if="ttsTestResult.success" class="w-4 h-4 mt-0.5 shrink-0" /><XCircle v-else class="w-4 h-4 mt-0.5 shrink-0" /><span>{{ ttsTestResult.message }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 小红书封面 -->
        <section class="bg-bg-surface border border-line rounded-card shadow-card">
          <div class="px-5 py-4 border-b border-line/30">
            <SectionTitle :icon="ImageIcon" title="小红书封面" subtitle="封面图比例与风格" />
          </div>
          <div class="px-5 py-4 space-y-5">
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
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { NSelect, NRadioGroup, NRadioButton, NInput, useMessage } from 'naive-ui'
import { MessageCircle, FileText, Presentation, Volume2, Image as ImageIcon, Eye, EyeOff, Zap, Loader2, CheckCircle2, XCircle } from 'lucide-vue-next'
import PageHeader from '@/components/common/PageHeader.vue'
import SectionTitle from './_SettingsSection.vue'
import { useSettingStore } from '@/stores/settingStore'
import { verifyModel } from '@/api/providers'
import type { ProviderInfo, TTSProviderInfo } from '@/types'

const PROVIDER_LOGOS: Record<string, string> = {
  minimax: '/logos/minimax.svg', deepseek: '/logos/deepseek.svg', openai: '/logos/openai.svg',
  moonshot: '/logos/kimi.png', zhipu: '/logos/glm.svg', glm: '/logos/glm.svg',
  qwen: '/logos/qwen.svg', siliconflow: '/logos/siliconflow.svg',
  mimo: '/logos/xiaomi.svg', 'mimo-tts': '/logos/xiaomi.svg',
  'edge-tts': '/logos/edge.svg',
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

const store = useSettingStore()
const message = useMessage()
const settings = computed(() => store.settings)
type ModuleKey = 'chat' | 'content' | 'ppt' | 'tts'
const showKey = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifying = reactive<Record<ModuleKey, boolean>>({ chat: false, content: false, ppt: false, tts: false })
const verifyResults = reactive<Record<ModuleKey, { success: boolean; message: string } | null>>({ chat: null, content: null, ppt: null, tts: null })

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
  await store.updateSettings(patch as any)
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
// ─── TTS 测试 ───
const ttsTestText = ref('你好，这是一段测试语音')
const ttsTesting = ref(false)
const ttsTestResult = ref<{ success: boolean; message: string } | null>(null)
const ttsAudioUrl = ref<string | null>(null)
const ttsAudioRef = ref<HTMLAudioElement | null>(null)

async function onTestTtsPlay() {
  if (!ttsTestText.value.trim()) return
  ttsTesting.value = true; ttsTestResult.value = null; ttsAudioUrl.value = null
  try {
    const resp = await fetch('/api/tts-test', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        providerId: settings.value.tts_provider,
        apiKey: ttsConfigValue.value.apiKey,
        baseUrl: ttsConfigValue.value.baseUrl || ttsProvider.value?.defaultBaseUrl,
        model: settings.value.tts_model,
        voice: settings.value.tts_voice,
        text: ttsTestText.value,
      }),
    })
    const data = await resp.json()
    if (data.success && data.audio) {
      const byteChars = atob(data.audio); const bytes = new Uint8Array(byteChars.length)
      for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i)
      const url = URL.createObjectURL(new Blob([bytes], { type: `audio/${data.format || 'mp3'}` }))
      const audio = new Audio(url); audio.play().catch(() => {})
      ttsAudioUrl.value = url
      ttsTestResult.value = { success: true, message: '合成成功' }
    } else {
      ttsTestResult.value = { success: false, message: data.message || '合成失败' }
    }
  } catch (e) {
    ttsTestResult.value = { success: false, message: e instanceof Error ? e.message : '请求失败' }
  } finally { ttsTesting.value = false }
}

watch(ttsAudioUrl, async (url) => { if (url) { await nextTick(); if (ttsAudioRef.value) { ttsAudioRef.value.play().catch(() => {}) } } })

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
@media (max-width: 767px) { .result-card { padding: 10px; font-size: 12px; } }
</style>
