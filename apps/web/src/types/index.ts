/**
 * TypeScript 类型定义
 */

export interface ActionItem {
  id?: number
  task: string
  owner?: string
  deadline?: string
  priority?: string
  status?: string
}

export interface Segment {
  id: number
  start: number
  end: number
  text: string
  speaker?: string | null
}

export interface Meeting {
  id: number
  title: string
  description?: string
  meeting_date?: string
  duration?: number
  status: 'uploaded' | 'transcribing' | 'transcribed' | 'summarizing' | 'completed' | 'failed'
  raw_transcript?: string
  segments?: Segment[]
  summary?: string
  key_points?: string[]
  decisions?: string[]
  action_items?: ActionItem[]
  audio_filename?: string
  asr_model?: string
  llm_model?: string
  language?: string
  created_at: string
  updated_at: string
  completed_at?: string
  error_message?: string
}

export interface MeetingListResponse {
  total: number
  items: Meeting[]
  page: number
  page_size: number
}

export interface UploadResponse {
  meeting_id: number
  filename: string
  size_mb: number
  status: string
  message: string
}

export interface LLMProvider {
  name: string
  display_name: string
  configured: boolean
  model: string
  base_url: string
  supports_json_mode: boolean
  note?: string
}