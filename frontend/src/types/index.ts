// =============================================================
// Domain types — keep aligned with backend (app.py) responses
// =============================================================

// ---------- Chat ----------

export type ChatRole = 'user' | 'assistant'

export type ChatMessageType =
  | 'text'
  | 'markdown'
  | 'ppt_preview'
  | 'graphic_image'
  | 'video_audio'
  | 'mindmap'
  | 'content_result'
  | 'progress'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: number
  type?: ChatMessageType
  data?: Record<string, unknown>
  status?: 'streaming' | 'done' | 'error' | 'cancelled'
  error?: string
}

export interface Session {
  id: string
  name: string
  createdAt: number
  updatedAt: number
}

// ---------- SSE event ----------

export interface SseEvent {
  // Generic stream chunks (chat)
  chunk?: string
  done?: boolean

  // Backend "type" tagging
  type?: string
  message?: string
  stage?: string
  progress?: number

  // Specific payloads
  total_pages?: number
  filename?: string
  page?: number
  base64?: string
  title?: string
  image_base64?: string
  prompt?: string
  audio_base64?: string
  voiceover_text?: string
  xiaohongshu?: string
  content?: string
  filepath?: string
  topic?: string
  data?: Record<string, unknown>

  // PPT-SVG specific
  slide?: { page: number; svg: string }
  output_path?: string
  job_id?: string
  total_slides?: number
  slide_count?: number
  pptx_filename?: string
  error?: string
}

// ---------- Files ----------

export type FileType =
  | 'ppt'
  | 'lecture'
  | 'outline'
  | 'speech'
  | 'exercise'
  | 'quiz'
  | 'card'
  | 'mindmap'
  | 'content_text'
  | 'content_audio'
  | 'content_image'
  | 'svg_ppt'
  | 'video'

export interface GeneratedFile {
  id: string
  name: string
  type: FileType | string
  type_label: string
  path: string
  size: number
  size_formatted: string
  created: string
  icon?: string
}

// ---------- Settings ----------

export interface ContentSettings {
  mimo_voice: string
  mimo_style: string
  aspect_ratio: string
  cover_style: string
  // 对话模型
  chat_model: string
  chat_provider: string
  // 内容生成模型（讲稿、大纲、习题、测验、知识卡片、思维导图等）
  content_model: string
  content_provider: string
  // PPT 生成模型
  ppt_model: string
  ppt_provider: string
  // TTS 语音合成模型
  tts_provider: string
  tts_model: string
  tts_voice: string
  // PPT defaults (frontend-only extension, persisted via memory_manager config)
  ppt_default_style?: string
  ppt_default_pages?: number
  ppt_default_detail?: string
  ppt_default_model?: string
}

export interface SettingsOption {
  value: string
  label: string
}

export interface SettingsResponse {
  settings: ContentSettings
  options: Record<keyof ContentSettings, SettingsOption[]>
}

// ---------- Models / Meta ----------

export interface ModelInfo {
  id: string
  name: string
  description?: string
  provider?: string
  contextWindow?: number
  maxOutput?: number
}

// ---------- Providers ----------

export interface ProviderInfo {
  id: string
  name: string
  type: 'minimax' | 'openai'
  defaultBaseUrl: string
  models: ModelInfo[]
  requiresApiKey: boolean
  isServerConfigured: boolean
}

export interface ProvidersResponse {
  providers: Record<string, ProviderInfo>
}

export interface TTSVoiceInfo {
  id: string
  name: string
}

export interface TTSProviderInfo {
  id: string
  name: string
  type: string
  defaultBaseUrl: string
  models: ModelInfo[]
  voices: TTSVoiceInfo[]
  requiresApiKey: boolean
  isServerConfigured: boolean
}

export interface TTSProvidersResponse {
  providers: Record<string, TTSProviderInfo>
}

export interface ProviderConfig {
  apiKey: string
  baseUrl: string
}

export interface VerifyModelRequest {
  apiKey: string
  baseUrl: string
  model: string
  providerId: string
  providerType: string
}

// ---------- Memory ----------

export interface MemorySummary {
  summary: string
}

// ---------- PPT SVG Engine ----------

export type PptStyle = 'education' | 'academic' | 'consulting' | 'tech' | 'general'
export type PptDetail = 'brief' | 'normal' | 'detailed'
export type PptLang = 'zh' | 'en'
export type PptCanvas = 'ppt169' | 'ppt43'

export interface PptGenerateParams {
  topic: string
  language?: PptLang
  num_slides?: number
  style?: PptStyle
  detail_level?: PptDetail
  model?: string
  api_key?: string
  canvas_format?: PptCanvas
}

export type PptStage =
  | 'content_planning'
  | 'design'
  | 'svg_generation'
  | 'export'
  | 'done'
  | 'error'

export interface PptStreamEvent {
  type: string
  stage?: string
  message?: string
  progress?: number
  slide?: { page: number; svg: string }
  job_id?: string
  pptx_filename?: string
  output_path?: string
  total_slides?: number
  slide_count?: number
  error?: string
}

export interface PptSlide {
  page: number
  svg: string
  filename?: string
}

export interface PptJob {
  job_id: string
  topic: string
  created_at: string
  num_slides?: number
  style?: string
  has_pptx: boolean
  pptx_filename?: string
}

export interface PptJobListResponse {
  jobs: PptJob[]
}

export interface PptPreviewAllResponse {
  job_id: string
  total_pages: number
  slides: PptSlide[]
}
