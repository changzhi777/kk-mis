/**
 * agent UI 状态映射纯函数测试（OrderList / Commission 内的 statusText / statusType / payoutText）。
 *
 * 复制实现（同 detail-export.test.ts 策略：避免 import 组件拉 view chunk）。
 * 覆盖业务映射：状态码 → 中文 / EP tag type。
 */
import { describe, expect, it } from 'vitest'

// OrderList 的状态映射（src/views/agent/OrderList.vue）
const orderStatusText = (s: string) =>
  ({ pending: '待付款', paid: '已付款', completed: '已完成', cancelled: '已取消' }[s] || s)
const orderStatusType = (s: string) =>
  ({ pending: 'warning', paid: 'primary', completed: 'success', cancelled: 'info' }[s] || 'info')

// Commission 的状态映射（src/views/agent/Commission.vue）
const commissionStatusText = (s: string) => ({ pending: '待结算', settled: '已结算' }[s] || s)
const payoutText = (s: string) =>
  ({ pending: '待打款', settled: '已打款', cancelled: '已取消' }[s] || s)

describe('OrderList 状态映射', () => {
  it('statusText：4 种订单状态 → 中文', () => {
    expect(orderStatusText('pending')).toBe('待付款')
    expect(orderStatusText('paid')).toBe('已付款')
    expect(orderStatusText('completed')).toBe('已完成')
    expect(orderStatusText('cancelled')).toBe('已取消')
  })

  it('statusText：未知状态 → 原值兜底', () => {
    expect(orderStatusText('unknown')).toBe('unknown')
  })

  it('statusType：4 种状态 → EP tag type', () => {
    expect(orderStatusType('pending')).toBe('warning')
    expect(orderStatusType('paid')).toBe('primary')
    expect(orderStatusType('completed')).toBe('success')
    expect(orderStatusType('cancelled')).toBe('info')
  })

  it('statusType：未知状态 → info（默认）', () => {
    expect(orderStatusType('unknown')).toBe('info')
  })
})

describe('Commission 状态映射', () => {
  it('statusText：单次返佣状态', () => {
    expect(commissionStatusText('pending')).toBe('待结算')
    expect(commissionStatusText('settled')).toBe('已结算')
  })

  it('payoutText：年度返佣打款状态', () => {
    expect(payoutText('pending')).toBe('待打款')
    expect(payoutText('settled')).toBe('已打款')
    expect(payoutText('cancelled')).toBe('已取消')
  })

  it('未知状态 → 原值兜底', () => {
    expect(commissionStatusText('foo')).toBe('foo')
    expect(payoutText('bar')).toBe('bar')
  })
})
