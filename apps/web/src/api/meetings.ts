/**
 * Meeting API 客户端
 */
import axios from 'axios'
import type {
  Meeting,
  MeetingListResponse,
  UploadResponse,
  LLMProvider
} from '@/types'

// API Key 不在前端持有：Vite 的 VITE_* 变量会编译进 bundle，无法保密。
// 浏览器同源请求经 Nginx /oa/ 反代时，由 Nginx 服务端注入 X-API-Key。
const api = axios.create({
  baseURL: import.meta.env.BASE_URL.replace(/\/$/, ''),
  timeout: 600000 // 10 分钟（长音频 ASR）
})

export const meetingsApi = {
  /** 上传音频（支持进度回调） */
  async upload(
    audio: File,
    title: string,
    options: {
      description?: string
      meetingDate?: string
      language?: string
      llmProvider?: string
      onProgress?: (percent: number) => void
    } = {}
  ): Promise<UploadResponse> {
    const form = new FormData()
    form.append('audio', audio)
    form.append('title', title)
    if (options.description) form.append('description', options.description)
    if (options.meetingDate) form.append('meeting_date', options.meetingDate)
    form.append('language', options.language || 'zh')
    form.append('llm_provider', options.llmProvider || 'glm')

    const resp = await api.post<UploadResponse>('/api/v1/meetings/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && options.onProgress) {
          options.onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
    })
    return resp.data
  },

  /** 获取会议详情 */
  async get(id: number): Promise<Meeting> {
    const resp = await api.get<Meeting>(`/api/v1/meetings/${id}`)
    return resp.data
  },

  /** 列出会议 */
  async list(page = 1, pageSize = 20, status?: string): Promise<MeetingListResponse> {
    const resp = await api.get<MeetingListResponse>('/api/v1/meetings', {
      params: { page, page_size: pageSize, status }
    })
    return resp.data
  },

  /** 删除会议 */
  async remove(id: number): Promise<void> {
    await api.delete(`/api/v1/meetings/${id}`)
  },

  /** 列出 LLM providers */
  async listProviders(): Promise<LLMProvider[]> {
    const resp = await api.get<{ providers: LLMProvider[] }>('/llm/providers')
    return resp.data.providers
  }
}

export default meetingsApi