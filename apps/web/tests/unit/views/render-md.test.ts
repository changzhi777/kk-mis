/**
 * OaAgent.vue renderMd XSS 防护测试（marked + DOMPurify）
 *
 * 关键：renderMd 必须净化 LLM 输出中的恶意 HTML/JS。
 * 覆盖：
 * - <script> 注入
 * - <img onerror=...> 事件处理器
 * - javascript: URL
 * - <iframe> 等危险标签
 * - 正常 Markdown 渲染（不退化）
 */

import { describe, expect, it } from 'vitest'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 复制 OaAgent.vue 里的实现（DRY 实际应提取到 utils/markdown.ts；这里先保证测试覆盖）
// jsdom 默认有 window 全局，DOMPurify 自动用
const _purify = DOMPurify(window).sanitize as (html: string, opts?: any) => string
marked.setOptions({ breaks: true, gfm: true })
function renderMd(content: string): string {
  if (!content) return ''
  const html = marked.parse(content) as string
  return _purify(html, {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['style', 'iframe', 'form', 'input', 'object', 'embed'],
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'style'],
  })
}

describe('renderMd XSS 防护', () => {
  it('空内容 → 空字符串', () => {
    expect(renderMd('')).toBe('')
  })

  it('普通 Markdown → 渲染 HTML（h1 保留）', () => {
    const out = renderMd('# 标题\n\n**粗体**')
    expect(out).toContain('<h1')
    expect(out).toContain('标题')
    expect(out).toContain('<strong>粗体</strong>')
  })

  it('代码块保留（不退化）', () => {
    const out = renderMd('```python\nprint("hi")\n```')
    expect(out).toContain('<code')
    expect(out).toContain('print')
  })

  it('剔除 <script> 注入（XSS 核心防护）', () => {
    const out = renderMd('正常文字\n\n<script>alert("xss")</script>\n\n更多文字')
    expect(out).not.toContain('<script>')
    expect(out).not.toContain('alert(')
    expect(out).toContain('正常文字')
    expect(out).toContain('更多文字')
  })

  it('剔除 <img onerror=...> 事件处理器', () => {
    const out = renderMd('<img src=x onerror="alert(1)">')
    expect(out).not.toContain('onerror')
    expect(out).not.toContain('alert')
  })

  it('剔除 javascript: URL（链接）', () => {
    const out = renderMd('[click](javascript:alert(1))')
    expect(out).not.toContain('javascript:')
  })

  it('剔除 <iframe>（FORBID_TAGS）', () => {
    const out = renderMd('<iframe src="evil.com"></iframe>')
    expect(out).not.toContain('<iframe')
  })

  it('剔除 <style>（FORBID_TAGS）', () => {
    const out = renderMd('<style>body{display:none}</style>')
    expect(out).not.toContain('<style')
  })

  it('多重嵌套 XSS 都被净化', () => {
    const malicious = `
# 标题

<script>steal()</script>

<img src=x onerror="bad()">

<a href="javascript:void(0)">link</a>

<iframe></iframe>

<object data="x"></object>

正常段落
    `
    const out = renderMd(malicious)
    expect(out).not.toContain('<script>')
    expect(out).not.toContain('onerror')
    expect(out).not.toContain('javascript:')
    expect(out).not.toContain('<iframe')
    expect(out).not.toContain('<object')
    expect(out).toContain('标题')
    expect(out).toContain('正常段落')
  })
})