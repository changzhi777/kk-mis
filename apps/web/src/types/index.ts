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

// ===== Admin 域类型（对齐后端 admin schemas）=====

/** Element Plus el-tag/el-button type 联合类型（消除各 view 的 as any） */
export type EpTagType = '' | 'primary' | 'success' | 'warning' | 'danger' | 'info'

/** 菜单项（/auth/menus 树形，菜单节点必有路径） */
export interface MenuItem {
  id: number
  parent_id: number | null
  name: string
  path: string
  icon: string | null
  sort: number
  visible: boolean
  children?: MenuItem[]
}

/** 公告（/oa/announcements） */
export interface Announcement {
  id: number
  title: string
  content: string
  publisher_id: number | null
  scope: string
  dept_id: number | null
  status: string
  created_at: string
  published_at: string | null
}

/** 权限节点（/permissions/tree | /flat） */
export interface PermissionNode {
  id: number
  parent_id: number | null
  name: string
  code: string
  type: string
  path: string | null
  method: string | null
  icon: string | null
  sort: number
  visible: boolean
  children?: PermissionNode[]
}

/** 考勤记录（/oa/attendance/me） */
export interface AttendanceRecord {
  id: number
  user_id: number
  date: string
  clock_in: string | null
  clock_out: string | null
  status: string
  work_hours: number | null
}

/** 考勤统计（/oa/attendance/stats） */
export interface AttendanceStats {
  normal: number
  late: number
  early: number
  work_hours_sum: number
}

/** 单次返佣汇总项（/agent/commissions/summary） */
export interface CommissionSummaryItem {
  id: number
  order_id: number
  agent_id: number
  level: number | null
  amount: number
  status: string
  settled_at: string | null
  created_at: string
}

/** 工作汇报（/oa/reports/all） */
export interface WorkReport {
  id: number
  user_id: number
  type: string
  period_start: string
  period_end: string
  content: string
  plan_next: string | null
  problems: string | null
  status: string
  created_at: string
}

/** 财务分类报表项（/finance/reports/by-category） */
export interface CategoryReportItem {
  category_id: number
  category_name: string
  type: string
  amount: number
}