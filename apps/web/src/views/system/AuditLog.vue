<template>
  <el-card shadow="never">
    <template #header><span class="ct">审计日志</span></template>
    <div class="filter">
      <el-select v-model="f.method" placeholder="方法" clearable style="width:100px" @change="load">
        <el-option v-for="m in ['POST', 'PUT', 'DELETE']" :key="m" :value="m" />
      </el-select>
      <el-input v-model="f.path" placeholder="路径搜索" clearable style="width:220px" @clear="load" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe size="small">
      <el-table-column label="时间" width="170"><template #default="{ row }"><TimeText :value="row.created_at" /></template></el-table-column>
      <el-table-column prop="username" label="用户" width="90"><template #default="{ row }">{{ row.username || row.user_id || '-' }}</template></el-table-column>
      <el-table-column label="方法" width="70"><template #default="{ row }"><el-tag size="small" :type="methodType(row.method)">{{ row.method }}</el-tag></template></el-table-column>
      <el-table-column prop="path" label="路径" min-width="220" />
      <el-table-column label="状态" width="70"><template #default="{ row }"><span :style="{color: row.status_code < 400 ? 'var(--el-color-success)' : 'var(--el-color-danger)'}">{{ row.status_code }}</span></template></el-table-column>
      <el-table-column prop="ip" label="IP" width="120" />
      <el-table-column label="耗时" width="80"><template #default="{ row }">{{ row.duration_ms }}ms</template></el-table-column>
    </el-table>
    <div v-if="total > pageSize" class="page"><el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" layout="prev, pager, next, total" background @current-change="load" /></div>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'
const items = ref<any[]>([]), loading = ref(false), page = ref(1), pageSize = ref(20), total = ref(0)
const f = reactive({ method: '', path: '' })
const api = adminApi.resource('/api/v1/audit')
const methodType = (m: string) => ({ POST: 'success', PUT: 'warning', DELETE: 'danger' } as const)[m]
async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (f.method) params.method = f.method
    if (f.path) params.path = f.path
    const d = await api.list(params); items.value = d.items; total.value = d.total
  } finally { loading.value = false }
}
onMounted(load)
</script>
<style scoped>.ct { font-weight: 600; color: var(--el-text-color-primary) } .filter { display: flex; gap: 10px; margin-bottom: 12px } .page { display: flex; justify-content: flex-end; margin-top: 16px }</style>
