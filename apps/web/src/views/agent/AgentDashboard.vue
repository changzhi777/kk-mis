<template>
  <el-card shadow="never">
    <template #header>
      <span class="ct">代理看板（A4）</span>
      <el-button size="small" :loading="loading" style="float: right" @click="load">刷新</el-button>
    </template>
    <el-row :gutter="16">
      <el-col :span="8">
        <div class="muted">订单统计（按状态张数）</div>
        <div ref="orderChart" class="chart" />
      </el-col>
      <el-col :span="8">
        <div class="muted">返佣统计（按状态金额）</div>
        <div ref="commChart" class="chart" />
      </el-col>
      <el-col :span="8">
        <div class="muted">区域排名 Top 10（订单总额）</div>
        <div ref="regionChart" class="chart" />
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup lang="ts">
// A4 代理看板：调 /api/v1/agent/commissions/dashboard → ECharts 三图（订单饼/返佣饼/区域柱）
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { http, getApiError } from '@/api/admin'

echarts.use([BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

interface DashboardData {
  orders: { status: string; count: number; total: number }[]
  commissions: { status: string; amount: number }[]
  regions: { region: string; total: number }[]
}

const loading = ref(false)
const orderChart = ref<HTMLElement | null>(null)
const commChart = ref<HTMLElement | null>(null)
const regionChart = ref<HTMLElement | null>(null)
let charts: echarts.ECharts[] = []

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<DashboardData>('/api/v1/agent/commissions/dashboard')
    render(data)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

function render(d: DashboardData) {
  const oc = echarts.init(orderChart.value!)
  oc.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['40%', '65%'], data: d.orders.map((o) => ({ name: o.status, value: o.count })) }],
  })
  const cc = echarts.init(commChart.value!)
  cc.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['40%', '65%'], data: d.commissions.map((c) => ({ name: c.status, value: c.amount })) }],
  })
  const rc = echarts.init(regionChart.value!)
  rc.setOption({
    tooltip: {},
    xAxis: { type: 'category', data: d.regions.map((r) => r.region), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: d.regions.map((r) => r.total) }],
  })
  charts = [oc, cc, rc]
}

onMounted(load)
onBeforeUnmount(() => charts.forEach((c) => c.dispose()))
</script>

<style scoped>
.chart { height: 300px; }
.muted { color: var(--el-text-color-secondary); margin-bottom: 8px; font-size: 13px; }
.ct { font-weight: 600; }
</style>
