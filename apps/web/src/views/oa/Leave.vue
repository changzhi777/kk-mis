<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">请假申请</span><el-button type="primary" :icon="Plus" @click="open()">申请请假</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="类型" width="80"><template #default="{ row }">{{ typeText(row.type) }}</template></el-table-column>
      <el-table-column label="开始" width="160"><template #default="{ row }"><TimeText :value="row.start_date" /></template></el-table-column>
      <el-table-column label="结束" width="160"><template #default="{ row }"><TimeText :value="row.end_date" /></template></el-table-column>
      <el-table-column prop="days" label="天数" width="70" />
      <el-table-column prop="reason" label="事由" min-width="160" />
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
      <template #empty><el-empty description="暂无请假记录" :image-size="60" /></template>
    </el-table>
    <el-dialog v-model="dv" title="申请请假" width="480">
      <el-form :model="form" label-width="60px">
        <el-form-item label="类型"><el-select v-model="form.type" style="width:100%"><el-option value="personal" label="事假" /><el-option value="sick" label="病假" /><el-option value="annual" label="年假" /></el-select></el-form-item>
        <el-form-item label="开始"><el-date-picker v-model="form.start_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
        <el-form-item label="结束"><el-date-picker v-model="form.end_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
        <el-form-item label="天数"><el-input-number v-model="form.days" :precision="1" :step="0.5" :min="0.5" style="width:100%" /></el-form-item>
        <el-form-item label="事由"><el-input v-model="form.reason" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">提交</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'
const items = ref<any[]>([]), loading = ref(false), dv = ref(false), s = ref(false)
const form = reactive<any>({ type: 'personal', start_date: '', end_date: '', days: 1, reason: '' })
const api = adminApi.resource('/api/v1/oa/leaves')
const typeText = (t: string) => ({ personal: '事假', sick: '病假', annual: '年假' }[t] || t)
const statusText = (x: string) => ({ pending: '审批中', approved: '已批准', rejected: '已驳回' }[x] || x)
const statusType = (x: string) => ({ pending: 'warning', approved: 'success', rejected: 'danger' }[x] || '') as any
async function load() { loading.value = true; try { items.value = (await api.list()).items } finally { loading.value = false } }
function open() { Object.assign(form, { type: 'personal', start_date: '', end_date: '', days: 1, reason: '' }); dv.value = true }
async function save() {
  s.value = true
  try { await api.create(form); ElMessage.success('已提交，等待审批'); dv.value = false; load() }
  catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false }
}
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) }</style>
