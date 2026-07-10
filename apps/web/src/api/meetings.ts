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

// 会议纪要接入 admin JWT 统一认证：前端带 Authorization（登录态 token）
// nginx /oa/api/ 透传 Authorization 到 meeting-notes，后端 verify_jwt 校验
const api = axios.create({
  baseURL: import.meta.env.BASE_URL.replace(/\/$/, ''),
  timeout: 600000 // 10 分钟（长音频 ASR）
})

// 请求拦截：带 JWT（动态 import store 避免循环依赖）
api.interceptors.request.use(async (config) => {
  const { useUserStore } = await import('@/stores/user')
  const token = useUserStore().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 拦截：清登录态并跳登录
api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    if (error.response?.status === 401) {
      const { useUserStore } = await import('@/stores/user')
      useUserStore().logout()
      window.location.href = import.meta.env.BASE_URL + 'login'
    }
    return Promise.reject(error)
  }
)

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