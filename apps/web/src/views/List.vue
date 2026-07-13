<template>
  <div class="list-page">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span class="card-title">会议列表</span>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 140px">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="$router.push('/upload')">上传会议</el-button>
          </div>
        </div>
      </template>

      <el-table :data="meetings" v-loading="loading" stripe class="meetings-table">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <router-link :to="`/meetings/${row.id}`" class="title-link">{{ row.title }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><StatusTag :status="row.status" /></template>
        </el-table-column>
        <el-table-column label="时长" width="90">
          <template #default="{ row }">{{ row.duration ? `${row.duration.toFixed(1)}s` : '-' }}</template>
        </el-table-column>
        <el-table-column label="语言" width="70">
          <template #default="{ row }">{{ row.language === 'zh' ? '中文' : row.language }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }"><TimeText :value="row.created_at" /></template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="$router.push(`/meetings/${row.id}`)">查看</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无会议记录" :image-size="80">
            <el-button type="primary" :icon="Plus" @click="$router.push('/upload')">上传第一份</el-button>
          </el-empty>
        </template>
      </el-table>

      <div v-if="total > pageSize" class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          background
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { getApiError } from '@/api/admin'
import { ref, watch, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import StatusTag from '@/components/StatusTag.vue'
import TimeText from '@/components/TimeText.vue'
import { MEETING_STATUS } from '@/composables/useMeetingStatus'
import type { Meeting } from '@/types'

const meetings = ref<Meeting[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref<string>('')
const loading = ref(false)

const statusOptions = Object.entries(MEETING_STATUS).map(([value, m]) => ({ value, label: m.text }))

async function load() {
  loading.value = true
  try {
    const resp = await meetingsApi.list(page.value, pageSize.value, statusFilter.value || undefined)
    meetings.value = resp.items
    total.value = resp.total
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

watch(statusFilter, () => {
  page.value = 1
  load()
})

async function handleDelete(id: number) {
  try {
    await meetingsApi.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '删除失败'))
  }
}

onMounted(load)
</script>

<style scoped>
.list-page {
  max-width: 1200px;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.header-actions {
  display: flex;
  gap: 10px;
}
.title-link {
  color: var(--el-color-primary);
  font-weight: 500;
}
.title-link:hover {
  text-decoration: underline;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
