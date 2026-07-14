<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">询价线索</span>
        <div class="ops">
          <el-select v-model="statusFilter" clearable placeholder="状态" @change="load" style="width: 130px">
            <el-option v-for="[v, l] in statusOpts" :key="v" :label="l" :value="v" />
          </el-select>
          <el-button :icon="Download" @click="exportCsv">导出</el-button>
        </div>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="时间" width="160"><template #default="{ row }">{{ fmt(row.created_at) }}</template></el-table-column>
      <el-table-column prop="name" label="联系人" width="100" />
      <el-table-column prop="phone" label="电话" width="130" />
      <el-table-column prop="destination" label="目的地" width="100" />
      <el-table-column label="出行详情" min-width="180">
        <template #default="{ row }">
          {{ [row.travel_date, row.people ? row.people + '人' : '', row.budget].filter(Boolean).join(' / ') || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-select v-model="row.status" size="small" @change="onStatus(row)">
            <el-option v-for="[v, l] in statusOpts" :key="v" :label="l" :value="v" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
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
import type { InquiryLead, InquiryLeadStatus } from '@/api/cms'

const items = ref<InquiryLead[]>([])
const loading = ref(false)
const statusFilter = ref<InquiryLeadStatus | ''>('')
const statusOpts: [InquiryLeadStatus, string][] = [
  ['new', '新线索'],
  ['contacted', '已联系'],
  ['converted', '已转化'],
  ['closed', '已关闭'],
]

const fmt = (s: string) => (s ? new Date(s).toLocaleString('zh-CN', { hour12: false }) : '')

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listLeads(statusFilter.value ? { status: statusFilter.value } : undefined)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function onStatus(row: Record<string, unknown>) {
  try {
    await cmsApi.updateLeadStatus(row.id as number, row.status as InquiryLeadStatus)
    ElMessage.success('状态已更新')
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '失败'))
    load()
  }
}

async function remove(id: number) {
  await cmsApi.deleteLead(id)
  ElMessage.success('已删除')
  load()
}

function exportCsv() {
  adminApi.downloadCsv('/api/v1/cms/leads/export', statusFilter.value ? { status: statusFilter.value } : undefined)
}

onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
</style>
