<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">报销申请</span><div class="hdr-actions"><el-button :icon="Download" @click="exportCsv">导出</el-button><el-button type="primary" :icon="Plus" @click="open()">申请报销</el-button></div></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="金额" width="120"><template #default="{ row }"><span class="amount">¥{{ Number(row.amount).toFixed(2) }}</span></template></el-table-column>
      <el-table-column label="类别" width="90"><template #default="{ row }">{{ catText(row.category) }}</template></el-table-column>
      <el-table-column label="日期" width="120"><template #default="{ row }">{{ row.expense_date?.slice(0, 10) }}</template></el-table-column>
      <el-table-column prop="reason" label="事由" min-width="160" />
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
      <template #empty><el-empty description="暂无报销" :image-size="60" /></template>
    </el-table>
    <el-dialog v-model="dv" title="申请报销" width="480">
      <el-form :model="form" label-width="60px">
        <el-form-item label="金额"><el-input-number v-model="form.amount" :precision="2" :step="100" :min="0.01" style="width:100%" /></el-form-item>
        <el-form-item label="类别"><el-select v-model="form.category" style="width:100%"><el-option value="travel" label="差旅" /><el-option value="office" label="办公" /><el-option value="entertainment" label="招待" /><el-option value="other" label="其他" /></el-select></el-form-item>
        <el-form-item label="日期"><el-date-picker v-model="form.expense_date" type="date" value-format="YYYY-MM-DDT00:00:00" style="width:100%" /></el-form-item>
        <el-form-item label="事由"><el-input v-model="form.reason" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">提交</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Download, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'
const items = ref<any[]>([]), loading = ref(false), dv = ref(false), s = ref(false)
const form = reactive<any>({ amount: 100, category: 'office', expense_date: '', reason: '' })
const api = adminApi.resource('/api/v1/oa/expenses')
const catText = (c: string) => ({ travel: '差旅', office: '办公', entertainment: '招待', other: '其他' }[c] || c)
const statusText = (x: string) => ({ pending: '审批中', approved: '已批准', rejected: '已驳回' }[x] || x)
const statusType = (x: string) => ({ pending: 'warning', approved: 'success', rejected: 'danger' } as const)[x]
async function load() { loading.value = true; try { items.value = (await api.list()).items } finally { loading.value = false } }
function open() { Object.assign(form, { amount: 100, category: 'office', expense_date: '', reason: '' }); dv.value = true }
async function save() {
  s.value = true
  try { await api.create(form); ElMessage.success('已提交，等待审批'); dv.value = false; load() }
  catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally { s.value = false }
}
async function exportCsv() {
  try {
    await adminApi.downloadCsv('/api/v1/oa/expenses/export')
    ElMessage.success('已导出')
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .hdr-actions { display: flex; gap: 8px; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) } .amount { font-weight: 600; color: var(--el-color-danger) }</style>
