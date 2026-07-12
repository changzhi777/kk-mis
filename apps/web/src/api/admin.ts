/**
 * Admin 服务 API 客户端（企业管理 + 财务）
 * baseURL = BASE_URL + 'admin'（dev /admin/ → proxy 8300；生产 /oa/admin/ → nginx 反代）
 */
import axios from 'axios'

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
  async me(): Promise<UserInfo> {
    const { data } = await http.get('/api/v1/auth/me')
    return data
  },
  async fetchMenus(): Promise<any[]> {
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
  async permissionTree() {
    const { data } = await http.get('/api/v1/permissions/tree')
    return data.tree as any[]
  },
  async permissionFlat() {
    const { data } = await http.get('/api/v1/permissions/flat')
    return data.items as any[]
  },
  async reportSummary(params?: any) {
    const { data } = await http.get('/api/v1/finance/reports/summary', { params })
    return data as { income: number; expense: number; balance: number; count: number }
  },
  async reportByCategory(params?: any) {
    const { data } = await http.get('/api/v1/finance/reports/by-category', { params })
    return data.items as any[]
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
  async commissionSummary() { const { data } = await http.get('/api/v1/agent/commissions/summary'); return data.items as any[] },
  async settleCommission(agentId: number) { await http.post(`/api/v1/agent/commissions/settle`, null, { params: { agent_id: agentId } }) },
  // 工作汇报
  async allReports() { const { data } = await http.get('/api/v1/oa/reports/all'); return data.items as any[] },
  async readReport(id: number) { await http.put(`/api/v1/oa/reports/${id}/read`) },
  // 考勤打卡
  async attendanceToday() { const { data } = await http.get('/api/v1/oa/attendance/today'); return data },
  async clockIn() { const { data } = await http.post('/api/v1/oa/attendance/clock-in'); return data },
  async clockOut() { const { data } = await http.post('/api/v1/oa/attendance/clock-out'); return data },
  async attendanceMe(month: string) { const { data } = await http.get('/api/v1/oa/attendance/me', { params: { month } }); return data.items as any[] },
  async attendanceStats(month: string) { const { data } = await http.get('/api/v1/oa/attendance/stats', { params: { month } }); return data as any },
  // 通用资源 CRUD（企业/财务复用）
  resource<T = any>(path: string) {
    return {
      list: (params?: any) => http.get(path, { params }).then((r) => r.data),
      get: (id: number) => http.get(`${path}/${id}`).then((r) => r.data as T),
      create: (body: any) => http.post(path, body).then((r) => r.data as T),
      update: (id: number, body: any) => http.put(`${path}/${id}`, body).then((r) => r.data as T),
      remove: (id: number) => http.delete(`${path}/${id}`).then((r) => r.data),
    }
  },
}

export default adminApi
