/** 会议状态统一映射（消灭 List/Detail 重复定义） */

export interface StatusMeta {
  text: string
  type: '' | 'info' | 'warning' | 'success' | 'danger'
  hint: string
  progress: number
}

export const MEETING_STATUS: Record<string, StatusMeta> = {
  uploaded:     { text: '已上传', type: 'info',    hint: '等待 ASR 处理...',                progress: 10 },
  transcribing: { text: '转写中', type: 'warning', hint: '正在转写音频（本地 MLX Whisper）...', progress: 40 },
  transcribed:  { text: '已转写', type: 'warning', hint: '转写完成，正在整理纪要...',        progress: 70 },
  summarizing:  { text: '整理中', type: 'warning', hint: 'LLM 正在整理会议纪要...',          progress: 85 },
  completed:    { text: '已完成', type: 'success', hint: '',                                 progress: 100 },
  failed:       { text: '失败',   type: 'danger',  hint: '',                                 progress: 0 },
}

const DEFAULT_META: StatusMeta = { text: '', type: '', hint: '', progress: 0 }

export function getStatusMeta(status?: string): StatusMeta {
  if (!status) return DEFAULT_META
  return MEETING_STATUS[status] || { ...DEFAULT_META, text: status }
}

/** 行动项优先级 → tag 类型 */
export const PRIORITY_TYPE: Record<string, '' | 'info' | 'warning' | 'success' | 'danger'> = {
  P0: 'danger',
  P1: 'warning',
  P2: 'info',
}

/** 处理中的状态（需轮询） */
export const PROCESSING_STATUSES = ['uploaded', 'transcribing', 'transcribed', 'summarizing']
