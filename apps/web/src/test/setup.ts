// Vitest 全局 setup — happy-dom 的 localStorage 注入时机不稳定，自己造一个内存版
// KISS: 不引入完整 Element Plus 渲染，单测聚焦 store/router 逻辑
import { afterEach, beforeEach } from 'vitest'

// 1) 内存版 localStorage（保证测试可重复）
const _ls = new Map<string, string>()
const lsMock = {
  getItem: (k: string) => (_ls.has(k) ? _ls.get(k)! : null),
  setItem: (k: string, v: string) => {
    _ls.set(k, v)
  },
  removeItem: (k: string) => {
    _ls.delete(k)
  },
  clear: () => {
    _ls.clear()
  },
  key: (i: number) => Array.from(_ls.keys())[i] ?? null,
  get length() {
    return _ls.size
  },
}
// 覆盖 happy-dom 默认 localStorage（顺序：setupFiles 先于 environment 注入可能漏，强制覆盖）
;(globalThis as any).localStorage = lsMock

// 2) DOMPurify 等 DOM 库依赖 globalThis.window/document。
//    vitest environment: 'happy-dom' 已注入，无需手动 new Window。
//    但若 lazy import 时 window 还未就绪，安全网：存在即用，不存在则懒构造。
if (typeof (globalThis as any).window === 'undefined') {
  ;(globalThis as any).window = { localStorage: lsMock } as any
}

beforeEach(() => _ls.clear())
afterEach(() => _ls.clear())