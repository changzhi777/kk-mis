<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">Univer Sheets · S2 可行性 Spike</span>
        <el-tag size="small" type="info">preset 0.25.1 · Vue3 原生集成</el-tag>
      </div>
    </template>
    <p class="tip">
      验证项：① 实例能挂载 ② 初始数据能渲染 ③ 单元格可编辑 ④ 与 Element Plus 共存无样式冲突。
      数据为 OA 报销示例（S2 接入点 <code>oa/Expense.vue</code> 的表格化形态）。
    </p>
    <div ref="container" class="univer-container" />
  </el-card>
</template>

<script setup lang="ts">
// Univer Sheets · Vue3 官方集成（onMounted 建实例 / onBeforeUnmount 释放）
// 依据：https://docs.univer.ai/guides/sheets/getting-started/integrations/vue
import type { Univer } from '@univerjs/presets'
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import '@univerjs/preset-sheets-core/lib/index.css'

const container = ref<HTMLElement | null>(null)
let univerInstance: Univer | null = null

onMounted(() => {
  const { univer, univerAPI } = createUniver({
    locale: LocaleType.ZH_CN,
    locales: { [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN) },
    presets: [UniverSheetsCorePreset({ container: container.value as HTMLElement })],
  })

  // 注入初始数据，验证 cellData 渲染能力（OA 报销示例：行=记录，列=类别/金额/事由）
  univerAPI.createWorkbook({
    sheets: {
      sheet1: {
        name: '报销明细',
        cellData: {
          0: { 0: { v: '类别' }, 1: { v: '金额' }, 2: { v: '事由' } },
          1: { 0: { v: '差旅' }, 1: { v: 1200 }, 2: { v: '北京出差' } },
          2: { 0: { v: '办公' }, 1: { v: 350 }, 2: { v: '耗材采购' } },
          3: { 0: { v: '招待' }, 1: { v: 880 }, 2: { v: '客户餐叙' } },
        },
      },
    },
  })

  univerInstance = univer
})

onBeforeUnmount(() => {
  univerInstance?.dispose()
  univerInstance = null
})
</script>

<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.tip { margin: 0 0 12px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6 }
.univer-container { height: 560px; width: 100%; border: 1px solid var(--el-border-color-light); border-radius: 4px }
</style>
