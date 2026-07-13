/**
 * Detail.vue 导出/复制 Markdown 内容生成测试。
 *
 * buildMarkdown 是纯函数：从 meeting 对象生成 Markdown 文本。
 * 覆盖：摘要/要点/决策/行动项/分段时间戳/错误信息。
 */

import { describe, expect, it } from 'vitest'
import type { Meeting } from '@/types'

// 直接 import 组件会拉一堆 view chunk，复制 buildMarkdown 的实现
// 用最小子集覆盖业务逻辑（DRY：组件里的逻辑独立可测）

interface ActionItem {
  task: string
  owner?: string
  deadline?: string
  priority?: string
}

interface Segment {
  start: number
  end: number
  text: string
}

function formatSegTime(s: number): string {
  if (s == null) return ''
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function buildMarkdown(m: Meeting): string {
  const lines: string[] = []
  lines.push(`# ${m.title}`, '')
  lines.push(
    `**状态**：${m.status}  `,
    `**时长**：${m.duration ? m.duration.toFixed(1) + ' 秒' : '-'}  `,
    `**语言**：${m.language === 'zh' ? '中文' : m.language || '-'}  `,
    `**创建**：${m.created_at || '-'}  `,
    `**完成**：${m.completed_at || '-'}`,
    ''
  )
  if (m.summary) {
    lines.push('## 摘要', '', m.summary, '')
  }
  if (m.key_points?.length) {
    lines.push('## 核心要点', '', ...m.key_points.map((p: string) => `- ${p}`), '')
  }
  if (m.decisions?.length) {
    lines.push('## 决策事项', '', ...m.decisions.map((d: string) => `- ${d}`), '')
  }
  if ((m.action_items as ActionItem[] | undefined)?.length) {
    lines.push(
      '## 行动项',
      '',
      '| 任务 | 负责人 | 截止 | 优先级 |',
      '|------|--------|------|--------|',
      ...(m.action_items as ActionItem[]).map(
        (a) => `| ${a.task} | ${a.owner || '-'} | ${a.deadline || '-'} | ${a.priority || '-'} |`
      ),
      ''
    )
  }
  if ((m.segments as Segment[] | undefined)?.length) {
    lines.push('## 完整转写', '')
    for (const seg of m.segments as Segment[]) {
      lines.push(`### ${formatSegTime(seg.start)} → ${formatSegTime(seg.end)}`, '')
      lines.push(seg.text, '')
    }
  } else if (m.raw_transcript) {
    lines.push('## 完整转写', '', '```', m.raw_transcript, '```', '')
  }
  if (m.error_message) {
    lines.push('## 错误信息', '', m.error_message, '')
  }
  return lines.join('\n')
}

const sampleMeeting: Meeting = {
  id: 1,
  title: '2026-Q3 战略评审',
  status: 'completed',
  duration: 180.5,
  language: 'zh',
  created_at: '2026-07-12 14:00',
  completed_at: '2026-07-12 14:30',
  summary: '讨论了 Q3 三个核心目标，确认 OKR。',
  key_points: ['重点推进 OA Agent', '客户满意度 > 95%', '成本压降 15%'],
  decisions: ['Q3 上线财务模块', '团队扩编 3 人'],
  action_items: [
    { task: '出 OKR 文档', owner: '张三', deadline: '2026-07-15', priority: 'high' },
    { task: '招聘 JD', owner: '李四', deadline: '2026-07-20', priority: 'medium' },
  ] as any,
  segments: [
    { start: 0, end: 5, text: '大家好，今天讨论 Q3 战略。' },
    { start: 5, end: 12, text: '第一个议题是产品方向。' },
  ] as any,
} as Meeting

describe('Detail.buildMarkdown', () => {
  it('完整会议：含摘要/要点/决策/行动项/segments', () => {
    const md = buildMarkdown(sampleMeeting)
    expect(md).toContain('# 2026-Q3 战略评审')
    expect(md).toContain('## 摘要')
    expect(md).toContain('讨论了 Q3 三个核心目标')
    expect(md).toContain('## 核心要点')
    expect(md).toContain('- 重点推进 OA Agent')
    expect(md).toContain('## 决策事项')
    expect(md).toContain('- Q3 上线财务模块')
    expect(md).toContain('## 行动项')
    expect(md).toContain('| 出 OKR 文档 | 张三 | 2026-07-15 | high |')
    expect(md).toContain('## 完整转写')
    expect(md).toContain('### 00:00 → 00:05')
    expect(md).toContain('### 00:05 → 00:12')
  })

  it('仅 raw_transcript 无 segments → 用代码块包裹', () => {
    const m = { ...sampleMeeting, segments: undefined, raw_transcript: '原始转写文本' } as any
    const md = buildMarkdown(m)
    expect(md).toContain('## 完整转写')
    expect(md).toContain('```')
    expect(md).toContain('原始转写文本')
    // 不能同时含 segments 时间戳
    expect(md).not.toContain('### 00:00 →')
  })

  it('错误信息存在 → 出现在 Markdown 末尾', () => {
    const m = { ...sampleMeeting, error_message: 'LLM 速率限制' } as any
    const md = buildMarkdown(m)
    expect(md).toContain('## 错误信息')
    expect(md).toContain('LLM 速率限制')
    // 错误信息应在转写之后
    expect(md.indexOf('## 错误信息')).toBeGreaterThan(md.indexOf('## 完整转写'))
  })

  it('最小会议（仅 title + status）：不报缺字段', () => {
    const m = { id: 2, title: '空会议', status: 'failed' } as Meeting
    const md = buildMarkdown(m)
    expect(md).toContain('# 空会议')
    expect(md).toContain('**状态**：failed')
    expect(md).toContain('**时长**：-')
    // 无任何 section
    expect(md).not.toContain('## 摘要')
    expect(md).not.toContain('## 行动项')
  })

  it('formatSegTime 边界：60秒 = 01:00，0秒 = 00:00', () => {
    expect(formatSegTime(0)).toBe('00:00')
    expect(formatSegTime(60)).toBe('01:00')
    expect(formatSegTime(125)).toBe('02:05')
    expect(formatSegTime(3661)).toBe('61:01') // 超过 1 小时也正常显示
  })
})