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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
const items = ref<any[]>([]), loading = ref(false), summary = ref<any[]>([])
const rules = reactive<{ [k: number]: number }>({ 1: 0.2, 2: 0.1 })
const api = adminApi.resource('/api/v1/agent/commissions/records')
const statusText = (s: string) => ({ pending: '待结算', settled: '已结算' }[s] || s)
async function load() {
  loading.value = true
  try {
    const [r, s, d] = await Promise.all([adminApi.resource('/api/v1/agent/commissions/rules').list(), adminApi.commissionSummary(), api.list()])
    r.items.forEach((x: any) => (rules[x.level] = Number(x.rate)))
    summary.value = s; items.value = d.items
  } finally { loading.value = false }
}
async function saveRule(level: number, rate: number) {
  await adminApi.resource('/api/v1/agent/commissions/rules').create({ level, rate, status: true })
  ElMessage.success(`${level}级规则已更新：${(rate * 100).toFixed(1)}%`)
}
async function settle(agentId: number) { await adminApi.settleCommission(agentId); ElMessage.success('已结算'); load() }
onMounted(load)
</script>
<style scoped>.ct { font-weight: 600; color: var(--el-text-color-primary) } .rules { display: flex; align-items: center; gap: 12px; margin-bottom: 16px } .summary { display: flex; gap: 12px }</style>
