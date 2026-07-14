<template>
  <div ref="container" class="univer-container" />
</template>

<script setup lang="ts">
// Univer Sheets 可复用组件（Sprint 2，基于 SheetSpike 参数化）
// 接 sheets prop（{sheetId: {name, cellData}}），onMounted 建实例 + createWorkbook
// 父组件改 sheets 时用 :key 重建（避免多次 createWorkbook）
import type { Univer } from '@univerjs/presets'
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import '@univerjs/preset-sheets-core/lib/index.css'

const props = defineProps<{
  sheets: Record<string, { name?: string; cellData?: Record<number, Record<number, { v: unknown }>> }>
}>()

const container = ref<HTMLElement | null>(null)
let univerInstance: Univer | null = null

onMounted(() => {
  const { univer, univerAPI } = createUniver({
    locale: LocaleType.ZH_CN,
    locales: { [LocaleType.ZH_CN]: mergeLocales(UniverPresetSheetsCoreZhCN) },
    presets: [UniverSheetsCorePreset({ container: container.value as HTMLElement })],
  })
  // Univer IWorksheetData/ICellData 类型链过深（v: Nullable<CellValue> + s/m/f...），
  // 与宽松 props 类型不完全匹配，as any 绕（框架限制，业界惯例）
  univerAPI.createWorkbook({ sheets: props.sheets as never })
  univerInstance = univer
})

onBeforeUnmount(() => {
  univerInstance?.dispose()
  univerInstance = null
})
</script>

<style scoped>
.univer-container { height: 520px; border: 1px solid var(--el-border-color); border-radius: 4px; }
</style>
