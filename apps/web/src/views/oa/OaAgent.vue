<template>
  <div class="oa-agent-page">
    <div class="oa-agent-layout">
      <!-- 左侧：session 列表 -->
      <el-card shadow="never" class="session-list-card">
        <template #header>
          <div class="header-row">
            <span class="card-title">
            <el-icon><ChatDotRound /></el-icon>
            会话
          </span>
            <el-button size="small" :icon="Refresh" @click="loadSessions">刷新</el-button>
          </div>
        </template>
        <el-button type="primary" size="small" :icon="Plus" class="new-session-btn" @click="newSession">
          新建会话
        </el-button>
        <div v-loading="sessionsLoading" class="session-list">
          <el-empty v-if="!sessionsLoading && sessions.length === 0" description="暂无会话" :image-size="60" />
          <div
            v-for="s in sessions"
            :key="s.session_id"
            :class="['session-item', { active: s.session_id === currentSessionId }]"
            @click="loadSession(s.session_id)"
          >
            <div class="session-msg">{{ truncate(s.user_msg, 40) }}</div>
            <div class="session-meta">
              <el-tag v-if="s.total_steps" size="small" type="info">{{ s.total_steps }} 步</el-tag>
              <span class="session-time">{{ formatTime(s.started_at) }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 右侧：聊天窗口 -->
      <el-card shadow="never" class="chat-card">
        <template #header>
          <div class="header-row">
            <span class="card-title">
              <el-icon><MagicStick /></el-icon>
              OA Agent
            </span>
            <div class="header-actions">
              <el-tag v-if="health" :type="health.status === 'ok' ? 'success' : 'danger'" size="small">
                oa-agent {{ health.status }}
              </el-tag>
              <el-button size="small" :icon="Refresh" @click="checkHealth">检健康</el-button>
            </div>
          </div>
        </template>

        <el-alert
          v-if="lastError"
          :title="lastError"
          type="error"
          show-icon
          :closable="false"
          class="error-alert"
        />

        <div ref="scrollRef" class="messages" v-loading="busy">
          <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
            <strong>{{ m.role === 'user' ? '你' : 'Agent' }}：</strong>
            <!-- assistant 用 v-html 渲染 Markdown；user 仍按文本 -->
            <div v-if="m.role === 'assistant'" class="msg-content md" v-html="renderMd(m.content)"></div>
            <div v-else class="msg-content">{{ m.content }}</div>
            <div v-if="m.tools?.length" class="tools-row">
              <el-tag
                v-for="t in m.tools"
                :key="t"
                size="small"
                type="info"
                effect="plain"
              >
                {{ t }}
              </el-tag>
            </div>
          </div>
          <div v-if="thinking" class="thinking">
            <el-icon class="is-loading"><Loading /></el-icon>
            {{ thinking }}
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="input"
            type="textarea"
            :rows="3"
            placeholder="如：把 /tmp/data.md 里的关键数字整理成 excel"
            @keydown.enter.exact.prevent="send"
            :disabled="busy"
          />
          <div class="input-actions">
            <el-checkbox v-model="useTools">启用工具调用</el-checkbox>
            <el-button type="primary" :icon="Promotion" :loading="busy" @click="send">发送</el-button>
          </div>
        </div>
      </el-card>
    </div>

    <el-card v-if="skills.length" shadow="never" class="skills-card">
      <template #header><span class="card-title">可用 Skill（{{ skills.length }}）</span></template>
      <el-collapse>
        <el-collapse-item
          v-for="s in skills"
          :key="s.name"
          :name="s.name"
          :title="s.name + (s.builtin ? ' (内置)' : ' (用户)')"
        >
          <p>{{ s.description }}</p>
          <div>
            <el-tag v-for="t in s.tools" :key="t" size="small" type="info" class="skill-tool">
              {{ t }}
            </el-tag>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { getApiError } from '@/api/admin'
import { onMounted, ref, nextTick } from 'vue'
import { Promotion, Refresh, Plus, ChatDotRound, MagicStick, Loading } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  oaAgentChatSync,
  oaAgentHealth,
  oaAgentSkills,
  oaAgentSessions,
  oaAgentSession,
  ChatSyncResponse,
  SkillsResponse,
  SessionsResponse,
} from '@/api/oaAgent'

interface UiMessage {
  role: 'user' | 'assistant'
  content: string
  tools?: string[]
}

const input = ref('')
const messages = ref<UiMessage[]>([])
const thinking = ref('')
const busy = ref(false)
const lastError = ref('')
const health = ref<{ status: string; version: string } | null>(null)
const skills = ref<SkillsResponse['skills']>([])
const useTools = ref(true)
const scrollRef = ref<HTMLElement | null>(null)

// Session 状态
const sessions = ref<SessionsResponse['sessions']>([])
const sessionsLoading = ref(false)
const currentSessionId = ref<string | null>(null)

// ── Markdown 渲染（marked + DOMPurify XSS 净化） ─────────────────────
marked.setOptions({ breaks: true, gfm: true })

// DOMPurify 在 happy-dom / jsdom 下需要显式 window 才能拿到 DOMParser
// 创建模块级 purify 实例（lazy 解析 window，避免 SSR 报错）
let _purifyFn: ((html: string, opts?: any) => string) | null = null
function getPurify(): (html: string, opts?: any) => string {
  if (_purifyFn) return _purifyFn
  // 浏览器 / jsdom / happy-dom window 全局可用
  const w = (typeof window !== 'undefined' ? window : (globalThis as any)) as any
  const result = DOMPurify(w).sanitize as (html: string, opts?: any) => string
  _purifyFn = result
  return result
}

function renderMd(content: string): string {
  if (!content) return ''
  // LLM 输出可能含 prompt injection 注入的 <script> / <img onerror> 等
  // DOMPurify 净化后再 v-html，防 XSS
  const html = marked.parse(content) as string
  return getPurify()(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'iframe', 'form', 'input', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'style'],
  })
}

// ── 工具 ────────────────────────────────────────────────────────────
function truncate(s: string, n: number): string {
  return (s || '').length > n ? (s || '').slice(0, n) + '…' : s || ''
}
function formatTime(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  return sameDay
    ? d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

// ── 健康 / Skills / Sessions ─────────────────────────────────────────
async function checkHealth() {
  lastError.value = ''
  try {
    health.value = await oaAgentHealth()
  } catch (err: unknown) {
    health.value = { status: 'down', version: '?' }
    lastError.value = `oa-agent 不可达：${getApiError(err)}`
  }
}

async function loadSkills() {
  try {
    const resp = await oaAgentSkills()
    skills.value = resp.skills
  } catch {
    /* 静默 — skills 卡片可隐藏 */
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const resp = await oaAgentSessions(20)
    sessions.value = resp.sessions
  } catch {
    /* 静默 */
  } finally {
    sessionsLoading.value = false
  }
}

async function loadSession(sessionId: string) {
  currentSessionId.value = sessionId
  messages.value = []
  try {
    const detail = await oaAgentSession(sessionId)
    messages.value = [
      { role: 'user', content: detail.user_msg },
      { role: 'assistant', content: detail.final, tools: detail.tools_used },
    ]
  } catch (err: unknown) {
    lastError.value = `加载会话失败：${getApiError(err)}`
  }
}

function newSession() {
  currentSessionId.value = null
  messages.value = []
  input.value = ''
  lastError.value = ''
}

// ── 发送消息 ─────────────────────────────────────────────────────────
async function send() {
  const msg = input.value.trim()
  if (!msg || busy.value) return
  messages.value.push({ role: 'user', content: msg })
  input.value = ''
  busy.value = true
  thinking.value = '思考中…'
  try {
    const resp: ChatSyncResponse = await oaAgentChatSync(msg)
    currentSessionId.value = resp.session_id
    messages.value.push({
      role: 'assistant',
      content: resp.final || '(无回复)',
      tools: resp.tools_used,
    })
    // 异步刷新 session 列表（不 await，避免阻塞 UI）
    loadSessions()
  } catch (err: unknown) {
    const detail = getApiError(err)
    lastError.value = `请求失败：${detail}`
    messages.value.push({ role: 'assistant', content: `[错误] ${detail}` })
  } finally {
    thinking.value = ''
    busy.value = false
    await nextTick()
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight })
  }
}

onMounted(() => {
  checkHealth()
  loadSkills()
  loadSessions()
})
</script>

<style lang="scss" scoped>
.oa-agent-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.oa-agent-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

.session-list-card,
.chat-card {
  margin: 0;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.new-session-btn {
  width: 100%;
  margin-bottom: 12px;
}

.session-list {
  max-height: 60vh;
  overflow-y: auto;
}

.session-item {
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  background: var(--el-fill-color-light);
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s;

  &:hover {
    background: var(--el-color-primary-light-9);
  }
  &.active {
    background: var(--el-color-primary-light-9);
    border-color: var(--el-color-primary);
  }
}

.session-msg {
  font-size: 13px;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.session-time {
  font-size: 11px;
}

.error-alert {
  margin-bottom: 12px;
}

.messages {
  min-height: 360px;
  max-height: 55vh;
  overflow-y: auto;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-lighter);
}

.msg {
  margin: 10px 0;
  padding: 10px 12px;
  border-radius: 6px;
}

.msg.user {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.msg.assistant {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
}

.msg-content {
  margin-left: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

// Markdown 渲染样式（assistant 消息）
.md {
  white-space: normal;
  line-height: 1.6;

  :deep(p) {
    margin: 0.4em 0;
  }
  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 0.6em 0 0.3em;
    font-weight: 600;
  }
  :deep(ul),
  :deep(ol) {
    padding-left: 1.5em;
    margin: 0.4em 0;
  }
  :deep(code) {
    background: var(--el-fill-color);
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 0.9em;
  }
  :deep(pre) {
    background: var(--el-color-info-dark, #1e1e1e);
    color: var(--el-color-info-light-7, #e6e6e6);
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    code {
      background: transparent;
      color: inherit;
      padding: 0;
    }
  }
  :deep(blockquote) {
    border-left: 3px solid var(--el-color-primary);
    padding-left: 10px;
    color: var(--el-text-color-regular);
    margin: 0.4em 0;
  }
  :deep(a) {
    color: var(--el-color-primary);
    text-decoration: underline;
  }
}

.tools-row {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-style: italic;
  margin-top: 8px;
}

.input-area {
  margin-top: 12px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.skills-card {
  margin-top: 16px;
}

.skill-tool {
  margin-right: 4px;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .oa-agent-layout {
    grid-template-columns: 1fr;
  }
}
</style>