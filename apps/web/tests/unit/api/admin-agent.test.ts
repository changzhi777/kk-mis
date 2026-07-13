/**
 * adminApi 代理相关方法 + 通用 resource CRUD 测试。
 *
 * 覆盖 agent UI（RegionList / OrderList / Commission）调用的 API 层。
 * mock axios，验证端点 + 参数正确（不调真实接口；不 mount 组件，遵循 setup.ts KISS 策略）。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { mockHttp } = vi.hoisted(() => ({
  mockHttp: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

vi.mock('axios', () => ({
  default: { create: vi.fn(() => mockHttp) },
}))

import { adminApi, http } from '@/api/admin'

describe('adminApi — 代理专用方法', () => {
  beforeEach(() => vi.clearAllMocks())

  it('payOrder 调 POST /api/v1/agent/orders/{id}/pay', async () => {
    vi.mocked(http.post).mockResolvedValue({} as any)
    await adminApi.payOrder(5)
    expect(http.post).toHaveBeenCalledWith('/api/v1/agent/orders/5/pay')
  })

  it('completeOrder 调 POST /api/v1/agent/orders/{id}/complete 返回 data', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { id: 5, status: 'completed' } } as any)
    const out = await adminApi.completeOrder(5)
    expect(http.post).toHaveBeenCalledWith('/api/v1/agent/orders/5/complete')
    expect(out).toEqual({ id: 5, status: 'completed' })
  })

  it('commissionSummary 调 GET 返回 items 数组', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { items: [{ agent_id: 1 }] } } as any)
    const out = await adminApi.commissionSummary()
    expect(http.get).toHaveBeenCalledWith('/api/v1/agent/commissions/summary')
    expect(out).toEqual([{ agent_id: 1 }])
  })

  it('settleCommission 调 POST + agent_id params', async () => {
    vi.mocked(http.post).mockResolvedValue({} as any)
    await adminApi.settleCommission(3)
    expect(http.post).toHaveBeenCalledWith('/api/v1/agent/commissions/settle', null, {
      params: { agent_id: 3 },
    })
  })
})

describe('adminApi.resource — 通用 CRUD 工厂（agent UI 复用）', () => {
  beforeEach(() => vi.clearAllMocks())

  it('list 调 GET path + params，返回 data', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { items: [{ id: 1 }] } } as any)
    const r = adminApi.resource('/api/v1/agent/agents')
    const out = await r.list({ page: 1 })
    expect(http.get).toHaveBeenCalledWith('/api/v1/agent/agents', { params: { page: 1 } })
    expect(out).toEqual({ items: [{ id: 1 }] })
  })

  it('get 调 GET path/{id}，返回 data', async () => {
    vi.mocked(http.get).mockResolvedValue({ data: { id: 3 } } as any)
    const r = adminApi.resource('/api/v1/agent/agents')
    const out = await r.get(3)
    expect(http.get).toHaveBeenCalledWith('/api/v1/agent/agents/3')
    expect(out).toEqual({ id: 3 })
  })

  it('create 调 POST path + body，返回 data', async () => {
    vi.mocked(http.post).mockResolvedValue({ data: { id: 1 } } as any)
    const r = adminApi.resource('/api/v1/agent/agents')
    const out = await r.create({ region_code: 'SH' })
    expect(http.post).toHaveBeenCalledWith('/api/v1/agent/agents', { region_code: 'SH' })
    expect(out).toEqual({ id: 1 })
  })

  it('update 调 PUT path/{id} + body', async () => {
    vi.mocked(http.put).mockResolvedValue({ data: { id: 1 } } as any)
    const r = adminApi.resource('/api/v1/agent/agents')
    await r.update(1, { status: false })
    expect(http.put).toHaveBeenCalledWith('/api/v1/agent/agents/1', { status: false })
  })

  it('remove 调 DELETE path/{id}', async () => {
    vi.mocked(http.delete).mockResolvedValue({ data: {} } as any)
    const r = adminApi.resource('/api/v1/agent/agents')
    await r.remove(2)
    expect(http.delete).toHaveBeenCalledWith('/api/v1/agent/agents/2')
  })
})
