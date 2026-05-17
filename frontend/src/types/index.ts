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
