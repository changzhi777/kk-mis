<template>
  <el-card shadow="never" class="redeem-card">
    <template #header><span class="ct">卡券核销</span></template>
    <el-form :model="form" label-width="70px" @submit.prevent="redeem">
      <el-form-item label="卡号">
        <el-input v-model="form.card_no" placeholder="输入或扫码卡号" style="width:320px" @keyup.enter="redeem" autofocus />
      </el-form-item>
      <el-form-item label="核销方式">
        <el-radio-group v-model="form.method">
          <el-radio value="scan">扫码</el-radio>
          <el-radio value="manual">手动</el-radio>
          <el-radio value="self">自助(需密码)</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="密码" v-if="form.method === 'self'"><el-input v-model="form.password" style="width:160px" /></el-form-item>
      <el-form-item><el-button type="primary" :loading="s" @click="redeem">核销</el-button></el-form-item>
    </el-form>
  </el-card>

  <el-card shadow="never" style="margin-top:16px">
    <template #header><span class="ct">核销记录</span></template>
    <el-table :data="items" v-loading="loading" stripe size="small">
      <el-table-column label="时间" width="180"><template #default="{ row }"><TimeText :value="row.created_at" /></template></el-table-column>
      <el-table-column prop="card_id" label="卡券ID" width="90" />
      <el-table-column label="方式" width="90"><template #default="{ row }">{{ methodText(row.method) }}</template></el-table-column>
      <el-table-column label="金额" width="100"><template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template></el-table-column>
      <el-table-column prop="remark" label="备注" />
    </el-table>
    <div v-if="total > pageSize" class="page"><el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" layout="prev, pager, next" small background @current-change="loadRecords" /></div>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'
import TimeText from '@/components/TimeText.vue'
const form = reactive({ card_no: '', method: 'scan', password: '' })
const s = ref(false), items = ref<any[]>([]), loading = ref(false), page = ref(1), pageSize = ref(20), total = ref(0)
const methodText = (m: string) => ({ scan: '扫码', manual: '手动', batch: '批量', self: '自助' }[m] || m)
async function redeem() {
  if (!form.card_no) return
  s.value = true
  try {
    const r = await adminApi.redeemCard(form.card_no, form.method, form.password || undefined)
    ElMessage.success(`核销成功 ¥${Number(r.amount).toFixed(2)}`)
    form.card_no = ''; form.password = ''
    loadRecords()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '核销失败')) } finally { s.value = false }
}
async function loadRecords() {
  loading.value = true
  try { const api = adminApi.resource('/api/v1/asset/redemptions'); const d = await api.list({ page: page.value, page_size: pageSize.value }); items.value = d.items; total.value = d.total } finally { loading.value = false }
}
onMounted(loadRecords)
</script>
<style scoped>.ct { font-weight: 600; color: var(--el-text-color-primary) } .page { display: flex; justify-content: flex-end; margin-top: 12px }</style>
