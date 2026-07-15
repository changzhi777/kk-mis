/**
 * Admin 服务 API 客户端（企业管理 + 财务）
 * baseURL = BASE_URL + 'admin'（dev /admin/ → proxy 8300；生产 /oa/admin/ → nginx 反代）
 */
import axios from 'axios'
import type {
  AttendanceRecord,
  AttendanceStats,
  CategoryReportItem,
  CommissionSummaryItem,
  MenuItem,
  PermissionNode,
  WorkReport,
} from '@/types'

export interface UserInfo {
  id: number
  username: string
  name?: string
  email?: string
  phone?: string
  dept_id?: number
  status: boolean
  roles: string[]
  permissions: string[]
}

export interface LoginResult {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
}

const http = axios.create({
  baseURL: import.meta.env.BASE_URL + 'admin',
  timeout: 30000,
})

export { http }

/** 从 unknown 错误中提取后端 detail（axios 错误结构），DRY 统一处理 */
export function getApiError(e: unknown, fallback = '操作失败'): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: string } | undefined)?.detail
    return detail || fallback
  }
  if (e instanceof Error) return e.message || fallback
  return fallback
}

// 请求拦截：带 JWT（动态 import store 避免循环依赖）
http.interceptors.request.use(async (config) => {
  const { useUserStore } = await import('@/stores/user')
  const token = useUserStore().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 清登录态并跳登录
http.interceptors.response.use(
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

export const adminApi = {
  async login(username: string, password: string): Promise<LoginResult> {
    const { data } = await http.post('/api/v1/auth/login', { username, password })
    return data
  },
  async register(payload: {
    username: string; password: string; name: string; phone?: string; email?: string
  }): Promise<LoginResult> {
    const { data } = await http.post('/api/v1/auth/register', payload)
    return data
  },
  async me(): Promise<UserInfo> {
    const { data } = await http.get('/api/v1/auth/me')
    return data
  },
  async fetchMenus(): Promise<MenuItem[]> {
    const { data } = await http.get('/api/v1/auth/menus')
    return data
  },
  // 公告
  async publishAnnouncement(id: number) {
    const { data } = await http.post(`/api/v1/oa/announcements/${id}/publish`)
    return data
  },
  async archiveAnnouncement(id: number) {
    const { data } = await http.post(`/api/v1/oa/announcements/${id}/archive`)
    return data
  },
  async approveInstance(id: number, comment?: string) {
    await http.post(`/api/v1/oa/approvals/instances/${id}/approve`, { comment })
  },
  async rejectInstance(id: number, comment: string) {
    await http.post(`/api/v1/oa/approvals/instances/${id}/reject`, { comment })
  },
  async logout(): Promise<void> {
    await http.post('/api/v1/auth/logout')
  },
  async changePassword(oldPassword: string, newPassword: string) {
    await http.put('/api/v1/auth/password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
  async resetUserPassword(id: number, password: string) {
    await http.put(`/api/v1/users/${id}/password`, { password })
  },
  async permissionTree(): Promise<PermissionNode[]> {
    const { data } = await http.get('/api/v1/permissions/tree')
    return data.tree as PermissionNode[]
  },
  async permissionFlat(): Promise<PermissionNode[]> {
    const { data } = await http.get('/api/v1/permissions/flat')
    return data.items as PermissionNode[]
  },
  async reportSummary(params?: Record<string, unknown>) {
    const { data } = await http.get('/api/v1/finance/reports/summary', { params })
    return data as { income: number; expense: number; balance: number; count: number }
  },
  async reportByCategory(params?: Record<string, unknown>): Promise<CategoryReportItem[]> {
    const { data } = await http.get('/api/v1/finance/reports/by-category', { params })
    return data.items as CategoryReportItem[]
  },
  async reportByAccount(params?: Record<string, unknown>) {
    const { data } = await http.get('/api/v1/finance/reports/by-account', { params })
    return data.items as { account_id: number; account: string; income: number; expense: number; balance: number }[]
  },
  async reportByMonth(params?: Record<string, unknown>) {
    const { data } = await http.get('/api/v1/finance/reports/by-month', { params })
    return data.items as { month: string; income: number; expense: number; balance: number }[]
  },
  // 复式记账（凭证 + 分录 + 3 报表）
  async createVoucher(body: { voucher_date: string; summary?: string; entries: { account_id: number; debit?: number; credit?: number; summary?: string }[] }) {
    const { data } = await http.post('/api/v1/finance/vouchers', body)
    return data as { id: number; number: string; status: string; debit_total: number; credit_total: number }
  },
  async postVoucher(id: number) {
    const { data } = await http.post(`/api/v1/finance/vouchers/${id}/post`)
    return data as { success: boolean; posted: boolean }
  },
  async listVouchers() {
    const { data } = await http.get('/api/v1/finance/vouchers')
    return data.items as { id: number; number: string; voucher_date: string; summary: string; status: string; entries: { account_id: number; debit: number; credit: number }[] }[]
  },
  async trialBalance() {
    const { data } = await http.get('/api/v1/finance/reports/trial-balance')
    return data as { items: { code: string; name: string; account_type: string; debit: number; credit: number }[]; total_debit: number; total_credit: number; balanced: boolean }
  },
  async balanceSheet() {
    const { data } = await http.get('/api/v1/finance/reports/balance-sheet')
    return data as { assets: number; liabilities: number; equity: number; balanced: boolean }
  },
  async incomeStatement() {
    const { data } = await http.get('/api/v1/finance/reports/income-statement')
    return data as { revenue: number; expense: number; profit: number }
  },
  // A3 代理提现
  async withdrawalBalance() {
    const { data } = await http.get('/api/v1/agent/withdrawals/balance')
    return data as { settled: number; pending: number; available: number }
  },
  async listWithdrawals() {
    const { data } = await http.get('/api/v1/agent/withdrawals')
    return data.items as { id: number; amount: number; status: string; bank_info: string; reviewed_at: string | null; created_at: string }[]
  },
  async requestWithdrawal(amount: number, bankInfo: string) {
    const { data } = await http.post('/api/v1/agent/withdrawals', { amount, bank_info: bankInfo })
    return data as { id: number; status: string; amount: number }
  },
  async reviewWithdrawal(id: number, action: 'approve' | 'reject') {
    const { data } = await http.put(`/api/v1/agent/withdrawals/${id}/review`, { action })
    return data as { id: number; status: string }
  },
  // 资产专用
  async generateCards(batchId: number, quantity: number) {
    const { data } = await http.post(`/api/v1/asset/batches/${batchId}/generate`, { quantity })
    return data
  },
  async redeemCard(card_no: string, method: string, password?: string, remark?: string) {
    const { data } = await http.post('/api/v1/asset/redemptions/redeem', { card_no, method, password, remark })
    return data
  },
  async issueCard(id: number, holderUserId: number) {
    await http.post(`/api/v1/asset/cards/${id}/issue`, { holder_user_id: holderUserId })
  },
  async voidCard(id: number) {
    await http.post(`/api/v1/asset/cards/${id}/void`)
  },
  // 代理专用
  async payOrder(id: number) { await http.post(`/api/v1/agent/orders/${id}/pay`) },
  async completeOrder(id: number) { const { data } = await http.post(`/api/v1/agent/orders/${id}/complete`); return data },
  async commissionSummary(): Promise<CommissionSummaryItem[]> { const { data } = await http.get('/api/v1/agent/commissions/summary'); return data.items as CommissionSummaryItem[] },
  async settleCommission(agentId: number) { await http.post(`/api/v1/agent/commissions/settle`, null, { params: { agent_id: agentId } }) },
  // 工作汇报
  async allReports(): Promise<WorkReport[]> { const { data } = await http.get('/api/v1/oa/reports/all'); return data.items as WorkReport[] },
  async readReport(id: number) { await http.put(`/api/v1/oa/reports/${id}/read`) },
  // 考勤打卡
  async attendanceToday() { const { data } = await http.get('/api/v1/oa/attendance/today'); return data },
  async clockIn() { const { data } = await http.post('/api/v1/oa/attendance/clock-in'); return data },
  async clockOut() { const { data } = await http.post('/api/v1/oa/attendance/clock-out'); return data },
  async attendanceMe(month: string): Promise<AttendanceRecord[]> { const { data } = await http.get('/api/v1/oa/attendance/me', { params: { month } }); return data.items as AttendanceRecord[] },
  async attendanceStats(month: string): Promise<AttendanceStats> { const { data } = await http.get('/api/v1/oa/attendance/stats', { params: { month } }); return data as AttendanceStats },
  // CSV 导出下载（通用）
  async downloadCsv(path: string, params?: Record<string, unknown>) {
    const r = await http.get(path, { params, responseType: 'blob' })
    const cd = (r.headers['content-disposition'] || '') as string
    const filename = (cd.match(/filename="?([^";]+)"?/) || [, 'export.csv'])[1]
    const url = URL.createObjectURL(new Blob([r.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = decodeURIComponent(filename)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
  // 通用资源 CRUD（企业/财务复用）
  resource<T = unknown>(path: string) {
    return {
      list: (params?: Record<string, unknown>) => http.get(path, { params }).then((r) => r.data),
      get: (id: number) => http.get(`${path}/${id}`).then((r) => r.data as T),
      create: (body: Record<string, unknown>) => http.post(path, body).then((r) => r.data as T),
      update: (id: number, body: Record<string, unknown>) => http.put(`${path}/${id}`, body).then((r) => r.data as T),
      remove: (id: number) => http.delete(`${path}/${id}`).then((r) => r.data),
    }
  },
}

export default adminApi
