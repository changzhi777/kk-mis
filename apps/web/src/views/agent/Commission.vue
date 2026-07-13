<template>
  <div>
    <el-tabs v-model="activeTab" type="card">
      <!-- Tab 1: 单次返佣 -->
      <el-tab-pane label="单次返佣" name="single">
        <el-card shadow="never">
          <template #header><span class="ct">单次返佣记录（订单完成时生成）</span></template>
          <el-table :data="items" v-loading="loading" stripe size="small">
            <el-table-column prop="order_id" label="订单" width="80" />
            <el-table-column prop="agent_id" label="代理" width="80" />
            <el-table-column label="金额" width="120">
              <template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'settled' ? 'success' : 'warning'">
                  {{ statusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Tab 2: 年度累计返佣（新） -->
      <el-tab-pane label="年度累计返佣" name="yearly">
        <el-card shadow="never">
          <template #header>
            <div class="hdr">
              <span class="ct">年度累计返佣（按自然年）</span>
              <div>
                <el-select
                  v-model="year"
                  style="width:120px;margin-right:8px"
                  @change="loadYearly"
                >
                  <el-option
                    v-for="y in yearOptions"
                    :key="y"
                    :label="`${y}年`"
                    :value="y"
                  />
                </el-select>
                <el-button type="primary" :icon="Refresh" @click="settleYearly">触发结算</el-button>
              </div>
            </div>
          </template>

          <el-table :data="yearlyItems" v-loading="yearlyLoading" stripe size="small">
            <el-table-column label="区域" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.region_code || '-' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="agent_id" label="代理" width="100" />
            <el-table-column label="年度销售额" width="160">
              <template #default="{ row }">¥{{ Number(row.total_sales).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="订单数" prop="order_count" width="80" />
            <el-table-column label="阶梯" width="80">
              <template #default="{ row }">
                <el-tag size="small" type="success">{{ row.tier }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="返佣比例" width="120">
              <template #default="{ row }">{{ (Number(row.commission_pct) * 100).toFixed(0) }}%</template>
            </el-table-column>
            <el-table-column label="结算金额" width="140">
              <template #default="{ row }">
                <span class="amt">¥{{ Number(row.amount).toFixed(2) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.payout_status === 'settled' ? 'success' : 'warning'"
                >
                  {{ payoutText(row.payout_status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" style="margin-top:16px">
          <template #header><span class="ct">返佣阶梯规则（决策 #3 重构 2026-07-13）</span></template>
          <el-table :data="tierRules" stripe size="small">
            <el-table-column label="阶梯" prop="tier" width="80" />
            <el-table-column label="年度累计销售额">
              <template #default="{ row }">
                ¥{{ Number(row.min_sales).toLocaleString() }}
                <span v-if="row.max_sales"> ~ ¥{{ Number(row.max_sales).toLocaleString() }}</span>
                <span v-else> 以上</span>
              </template>
            </el-table-column>
            <el-table-column label="返佣比例">
              <template #default="{ row }">
                <el-tag type="success">{{ (Number(row.commission_pct) * 100).toFixed(0) }}%</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi, { http, getApiError } from '@/api/admin'

const activeTab = ref<'single' | 'yearly'>('yearly')
const items = ref<any[]>([])
const loading = ref(false)
const yearlyItems = ref<any[]>([])
const yearlyLoading = ref(false)
const year = ref(new Date().getFullYear())
const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2]
})
// 年度返佣阶梯规则（从后端 /rules 拉取，单一数据源，避免与 seed.py 漂移）
const tierRules = ref<any[]>([])

const statusText = (s: string) => ({ pending: '待结算', settled: '已结算' }[s] || s)
const payoutText = (s: string) =>
  ({ pending: '待打款', settled: '已打款', cancelled: '已取消' }[s] || s)

async function load() {
  loading.value = true
  try {
    const d = await adminApi.resource('/api/v1/agent/commissions/records').list()
    items.value = d.items
  } finally {
    loading.value = false
  }
  await loadYearly()
}

async function loadYearly() {
  yearlyLoading.value = true
  try {
    const { data } = await http.get('/api/v1/agent/yearly-commission', {
      params: { year: year.value },
    })
    yearlyItems.value = data.items || []
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载年度返佣失败'))
    yearlyItems.value = []
  } finally {
    yearlyLoading.value = false
  }
}

async function settleYearly() {
  try {
    const { data } = await http.post(
      '/api/v1/agent/yearly-commission/settle',
      null,
      { params: { year: year.value } },
    )
    ElMessage.success(`已结算 ${data.settled_count} 个 agent 的 ${year.value} 年度返佣`)
    await loadYearly()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '结算失败')) }
}

async function loadRules() {
  try {
    const { data } = await http.get('/api/v1/agent/yearly-commission/rules')
    tierRules.value = data.items || []
  } catch {
    tierRules.value = []
  }
}

onMounted(() => {
  load()
  loadRules()
})
</script>

<style scoped>
.ct {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.amt {
  font-weight: 600;
  color: var(--el-color-primary);
}
</style>