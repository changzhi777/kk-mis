<template>
  <div class="report-page">
    <el-card shadow="never" class="filter-card">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始"
        end-placeholder="结束"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DDTHH:mm:ss"
        @change="load"
      />
    </el-card>

    <el-row :gutter="16" class="stat-row">
      <el-col :span="8">
        <el-card shadow="never" class="stat-card income">
          <div class="stat-label">总收入</div>
          <div class="stat-value">¥ {{ summary.income.toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card expense">
          <div class="stat-label">总支出</div>
          <div class="stat-value">¥ {{ summary.expense.toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card balance">
          <div class="stat-label">结余</div>
          <div class="stat-value">¥ {{ summary.balance.toFixed(2) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header><span class="card-title">按科目分布</span></template>
      <div ref="chartRef" class="chart"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import adminApi from '@/api/admin'

// 按需注册（避免全量引入 1MB+）
echarts.use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const summary = ref({ income: 0, expense: 0, balance: 0, count: 0 })
const dateRange = ref<[string, string] | null>(null)
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function params() {
  const p: any = {}
  if (dateRange.value) {
    p.start_date = dateRange.value[0]
    p.end_date = dateRange.value[1]
  }
  return p
}

async function load() {
  const p = params()
  summary.value = await adminApi.reportSummary(p)
  const cats = await adminApi.reportByCategory(p)
  renderChart(cats)
}

function renderChart(cats: any[]) {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const income = cats.filter((c) => c.type === 'income')
  const expense = cats.filter((c) => c.type === 'expense')
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['收入', '支出'] },
    grid: { left: 40, right: 20, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: Array.from(new Set([...income.map((c) => c.category), ...expense.map((c) => c.category)])),
      axisLabel: { rotate: 20 },
    },
    yAxis: { type: 'value' },
    series: [
      { name: '收入', type: 'bar', data: income, itemStyle: { color: '#16a34a' } },
      { name: '支出', type: 'bar', data: expense, itemStyle: { color: '#dc2626' } },
    ],
  })
}

function onResize() {
  chart?.resize()
}

onMounted(async () => {
  await load()
  await nextTick()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<style scoped>
.report-page { display: flex; flex-direction: column; gap: 16px; }
.filter-card :deep(.el-card__body) { padding: 12px 16px; }
.stat-row { margin: 0; }
.stat-card { text-align: center; }
.stat-label { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 700; }
.stat-card.income .stat-value { color: var(--el-color-success); }
.stat-card.expense .stat-value { color: var(--el-color-danger); }
.stat-card.balance .stat-value { color: var(--el-color-primary); }
.card-title { font-weight: 600; color: var(--el-text-color-primary); }
.chart { height: 380px; }
</style>
