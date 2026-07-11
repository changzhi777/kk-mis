<template>
  <div>
    <el-card shadow="never">
      <template #header><span class="ct">分润规则 + 汇总</span></template>
      <div class="rules">
        <span>一级分润率</span><el-input-number :model-value="rules[1]" @change="(v:any)=>saveRule(1,v)" :precision="4" :step="0.05" :min="0" :max="1" size="small" />
        <span>二级分润率</span><el-input-number :model-value="rules[2]" @change="(v:any)=>saveRule(2,v)" :precision="4" :step="0.05" :min="0" :max="1" size="small" />
      </div>
      <div class="summary">
        <el-tag v-for="s in summary" :key="s.status" :type="s.status === 'settled' ? 'success' : 'warning'">
          {{ statusText(s.status) }}：¥{{ s.amount.toFixed(2) }}
        </el-tag>
        <div ref="chartRef" class="chart"></div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><span class="ct">分润记录</span></template>
      <el-table :data="items" v-loading="loading" stripe size="small">
        <el-table-column prop="order_id" label="订单" width="80" />
        <el-table-column prop="agent_id" label="代理" width="80" />
        <el-table-column label="级别" width="70"><template #default="{ row }">{{ row.level }}级</template></el-table-column>
        <el-table-column label="金额" width="110"><template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="row.status === 'settled' ? 'success' : 'warning'">{{ statusText(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><el-button v-if="row.status === 'pending'" link type="primary" @click="settle(row.agent_id)">结算</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import adminApi from '@/api/admin'

echarts.use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const items = ref<any[]>([]), loading = ref(false), summary = ref<any[]>([])
const rules = reactive<{ [k: number]: number }>({ 1: 0.2, 2: 0.1 })
const chartRef = ref<HTMLElement>()
let chart: any
const api = adminApi.resource('/api/v1/agent/commissions/records')
const statusText = (s: string) => ({ pending: '待结算', settled: '已结算' }[s] || s)

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const byLevel: Record<string, number> = {}
  items.value.forEach((r: any) => { byLevel[r.level] = (byLevel[r.level] || 0) + Number(r.amount) })
  chart.setOption({
    title: { text: '分润占比（按级别）', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: Object.entries(byLevel).map(([k, v]) => ({ name: k + '级', value: v })),
    }],
  })
}

async function load() {
  loading.value = true
  try {
    const [r, s, d] = await Promise.all([adminApi.resource('/api/v1/agent/commissions/rules').list(), adminApi.commissionSummary(), api.list()])
    r.items.forEach((x: any) => (rules[x.level] = Number(x.rate)))
    summary.value = s; items.value = d.items
    await nextTick(); renderChart()
  } finally { loading.value = false }
}
async function saveRule(level: number, rate: number) {
  await adminApi.resource('/api/v1/agent/commissions/rules').create({ level, rate, status: true })
  ElMessage.success(`${level}级规则已更新：${(rate * 100).toFixed(1)}%`)
}
async function settle(agentId: number) { await adminApi.settleCommission(agentId); ElMessage.success('已结算'); load() }
onMounted(load)
</script>
<style scoped>.ct { font-weight: 600; color: var(--el-text-color-primary) } .rules { display: flex; align-items: center; gap: 12px; margin-bottom: 16px } .summary { display: flex; gap: 12px; align-items: center; flex-wrap: wrap } .chart { width: 100%; height: 240px; margin-top: 8px }</style>
