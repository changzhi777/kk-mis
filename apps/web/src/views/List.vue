<template>
  <div class="list-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <h2>会议列表</h2>
          <div>
            <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 150px; margin-right: 12px">
              <el-option label="已上传" value="uploaded" />
              <el-option label="转写中" value="transcribing" />
              <el-option label="已转写" value="transcribed" />
              <el-option label="整理中" value="summarizing" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-button type="primary" @click="$router.push('/upload')">
              <el-icon><Plus /></el-icon>上传会议
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="meetings" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <router-link :to="`/meetings/${row.id}`" class="title-link">
              {{ row.title }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="100">
          <template #default="{ row }">
            {{ row.duration ? `${row.duration.toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="语言" width="80">
          <template #default="{ row }">
            {{ row.language === 'zh' ? '中文' : row.language }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/meetings/${row.id}`)">
              查看
            </el-button>
            <el-popconfirm
              title="确定删除？"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="load"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import type { Meeting } from '@/types'

const meetings = ref<Meeting[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref<string>('')
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const resp = await meetingsApi.list(page.value, pageSize.value, statusFilter.value || undefined)
    meetings.value = resp.items
    total.value = resp.total
  } catch (e: any) {
    ElMessage.error('加载失败：' + e.message)
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
  } catch (e: any) {
    ElMessage.error('删除失败：' + e.message)
  }
}

function statusText(s: string): string {
  return {
    uploaded: '已上传',
    transcribing: '转写中',
    transcribed: '已转写',
    summarizing: '整理中',
    completed: '已完成',
    failed: '失败'
  }[s] || s
}

function statusType(s: string): string {
  return {
    uploaded: 'info',
    transcribing: 'warning',
    transcribed: 'warning',
    summarizing: 'warning',
    completed: 'success',
    failed: 'danger'
  }[s] || ''
}

function formatTime(s: string): string {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<style scoped>
.list-page {
  max-width: 1200px;
  margin: 0 auto;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-row h2 {
  margin: 0;
}
.title-link {
  color: #1890ff;
  text-decoration: none;
}
.title-link:hover {
  text-decoration: underline;
}
</style>