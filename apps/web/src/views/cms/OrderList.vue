<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">产品订单</span>
        <div class="ops">
          <el-select v-model="statusFilter" clearable placeholder="支付状态" @change="load" style="width: 130px">
            <el-option v-for="[v, l] in statusOpts" :key="v" :label="l" :value="v" />
          </el-select>
          <el-button :icon="Download" @click="exportCsv">导出</el-button>
        </div>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="时间" width="160"><template #default="{ row }">{{ fmt(row.created_at) }}</template></el-table-column>
      <el-table-column prop="buyer_name" label="买家" width="100" />
      <el-table-column prop="buyer_phone" label="电话" width="130" />
      <el-table-column prop="quantity" label="数量" width="70" />
      <el-table-column label="金额" width="200">
        <template #default="{ row }">
          <div>原价 ¥{{ n(row.original_total) }}</div>
          <div v-if="Number(row.discount) > 0" class="disc">-¥{{ n(row.discount) }}（券 {{ row.coupon_code }}）</div>
          <div class="paid">实付 ¥{{ n(row.total) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="payTag(row.pay_status)">{{ payText(row.pay_status) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
    </el-table>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import cmsApi from '@/api/cms'
import adminApi from '@/api/admin'
import { getApiError } from '@/api/admin'
import type { OrderPayStatus, ProductOrder } from '@/api/cms'

const items = ref<ProductOrder[]>([])
const loading = ref(false)
const statusFilter = ref<OrderPayStatus | ''>('')
const statusOpts: [OrderPayStatus, string][] = [
  ['pending', '待支付'],
  ['paid', '已支付'],
  ['cancelled', '已取消'],
]
const fmt = (s: string) => (s ? new Date(s).toLocaleString('zh-CN', { hour12: false }) : '')
const n = (v: string | number) => Number(v).toFixed(2)
const payText = (s?: string) =>
  ({ pending: '待支付', paid: '已支付', cancelled: '已取消' } as const)[s as 'pending'] || s || ''
const payTag = (s?: string) =>
  ({ pending: 'warning', paid: 'success', cancelled: 'info' } as const)[s as 'pending'] || 'info'

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listOrders(statusFilter.value ? { pay_status: statusFilter.value } : undefined)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}
function exportCsv() {
  adminApi.downloadCsv('/api/v1/cms/orders/export', statusFilter.value ? { pay_status: statusFilter.value } : undefined)
}

onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.disc { color: var(--el-color-danger); font-size: 12px }
.paid { font-weight: 600; color: var(--el-color-primary) }
</style>
