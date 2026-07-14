<template>
  <el-card shadow="never">
    <template #header><span class="ct">CMS 数据看板</span></template>
    <el-row :gutter="16" v-loading="loading">
      <el-col :span="6"><div class="stat"><div class="num">{{ stats?.products_published || 0 }}</div><div class="lbl">已发布产品</div></div></el-col>
      <el-col :span="6"><div class="stat"><div class="num">{{ stats?.views_total || 0 }}</div><div class="lbl">总浏览量</div></div></el-col>
      <el-col :span="6"><div class="stat"><div class="num">{{ stats?.leads_new || 0 }}<span class="sub">/{{ stats?.leads_total || 0 }}</span></div><div class="lbl">新线索 / 总线索</div></div></el-col>
      <el-col :span="6"><div class="stat"><div class="num">¥{{ n(stats?.revenue) }}</div><div class="lbl">已支付收入（{{ stats?.orders_paid || 0 }} 单）</div></div></el-col>
    </el-row>
    <div ref="chartEl" class="chart"></div>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import cmsApi from '@/api/cms'
import type { DashboardStats } from '@/api/cms'

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)
const chartEl = ref<HTMLElement | null>(null)
const n = (v: number | string | undefined) => Number(v || 0).toFixed(2)

async function load() {
  loading.value = true
  try {
    stats.value = await cmsApi.getDashboard()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartEl.value || !stats.value) return
  const chart = echarts.init(chartEl.value)
  chart.setOption({
    title: { text: '浏览量 Top 产品', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, bottom: 60, top: 40 },
    xAxis: {
      type: 'category',
      data: stats.value.top_products.map((p) => p.title || p.slug),
      axisLabel: { rotate: 20, interval: 0 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: stats.value.top_products.map((p) => p.view_count),
        itemStyle: { color: '#0d9488', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 48,
      },
    ],
  })
}

onMounted(load)
</script>
<style scoped>
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.stat { background: var(--el-fill-color-light); border-radius: 8px; padding: 16px; text-align: center; }
.stat .num { font-size: 22px; font-weight: 700; color: var(--el-color-primary); }
.stat .sub { font-size: 14px; color: var(--el-text-color-secondary); }
.stat .lbl { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.chart { height: 340px; margin-top: 16px; }
</style>
