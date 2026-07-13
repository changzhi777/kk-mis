/**
 * OA Agent API 客户端 — 与 admin api 客户端类似但指向 /api/v1/oa-agent/
 * baseURL = BASE_URL + 'admin'（同 admin 服务的 oa_agent_bridge 路由）
 */
import axios from 'axios'

export interface OaAgentMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatStepOut {
  kind: string
  content: string
  tool_name?: string | null
  tool_error?: string | null
  duration_ms: number
}

export interface ChatSyncResponse {
  session_id: string
  final: string
  total_steps: number
  tools_used: string[]
  steps: ChatStepOut[]
}

export interface SkillSummary {
  name: string
  description: string
  tools: string[]
  version: string
  builtin: boolean
}

export interface SkillsResponse {
  count: number
  skills: SkillSummary[]
}

export interface SessionSummary {
  session_id: string
  user_msg: string
  final: string
  started_at: number
  total_steps: number
  tools_used: string[]
}

export interface SessionsResponse {
  count: number
  sessions: SessionSummary[]
}

export interface SessionDetail extends SessionSummary {
  steps: ChatStepOut[]
}

const http = axios.create({
  baseURL: import.meta.env.BASE_URL + 'admin',
  timeout: 120000,
})

/** 同步对话 — 一次完整 ReAct 后返回 */
export async function oaAgentChatSync(message: string, model?: string): Promise<ChatSyncResponse> {
  const resp = await http.post<ChatSyncResponse>('/api/v1/oa-agent/chat/sync', {
    message,
    ...(model ? { model } : {}),
  })
  return resp.data
}

/** 检 oa-agent 是否在线 */
export async function oaAgentHealth(): Promise<{ status: string; version: string }> {
  const resp = await http.get('/api/v1/oa-agent/healthz')
  return resp.data
}

/** 列 oa-agent 已加载 skills */
export async function oaAgentSkills(): Promise<SkillsResponse> {
  const resp = await http.get<SkillsResponse>('/api/v1/oa-agent/skills')
  return resp.data
}

/** 列最近 N 个 session（默认 20） */
export async function oaAgentSessions(limit = 20): Promise<SessionsResponse> {
  const resp = await http.get<SessionsResponse>('/api/v1/oa-agent/sessions', {
    params: { limit },
  })
  return resp.data
}

/** 读指定 session 的 trace（含 steps） */
export async function oaAgentSession(sessionId: string): Promise<SessionDetail> {
  const resp = await http.get<SessionDetail>(`/api/v1/oa-agent/sessions/${sessionId}`)
  return resp.data
}
