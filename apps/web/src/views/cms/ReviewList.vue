<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">评论管理</span>
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
      <el-table-column prop="author_name" label="昵称" width="100" />
      <el-table-column label="评分" width="130">
        <template #default="{ row }"><span class="stars">{{ '★'.repeat(row.rating) }}</span></template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="tagOf(row.status)">{{ textOf(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'approved'" link type="success" @click="set(row, 'approved')">通过</el-button>
          <el-button v-if="row.status !== 'rejected'" link type="warning" @click="set(row, 'rejected')">拒绝</el-button>
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
import type { Review, ReviewStatus } from '@/api/cms'

const items = ref<Review[]>([])
const loading = ref(false)
const statusFilter = ref<ReviewStatus | ''>('')
const statusOpts: [ReviewStatus, string][] = [
  ['pending', '待审'],
  ['approved', '已通过'],
  ['rejected', '已拒绝'],
]
const fmt = (s: string) => (s ? new Date(s).toLocaleString('zh-CN', { hour12: false }) : '')
const textOf = (s?: string) =>
  ({ pending: '待审', approved: '已通过', rejected: '已拒绝' } as const)[s as 'pending'] || s || ''
const tagOf = (s?: string) =>
  ({ pending: 'warning', approved: 'success', rejected: 'danger' } as const)[s as 'pending'] || 'info'

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listReviews(statusFilter.value ? { status: statusFilter.value } : undefined)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

async function set(row: Record<string, unknown>, status: ReviewStatus) {
  try {
    await cmsApi.updateReviewStatus(row.id as number, status)
    ElMessage.success('已更新')
    load()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '失败'))
  }
}

async function remove(id: number) {
  await cmsApi.deleteReview(id)
  ElMessage.success('已删除')
  load()
}

function exportCsv() {
  adminApi.downloadCsv('/api/v1/cms/reviews/export', statusFilter.value ? { status: statusFilter.value } : undefined)
}

onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.stars { color: #f7ba2a; }
</style>
