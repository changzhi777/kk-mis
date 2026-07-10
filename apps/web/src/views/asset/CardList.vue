<template>
  <el-card shadow="never">
    <template #header><span class="ct">卡券列表</span></template>
    <div class="filter">
      <el-input v-model="keyword" placeholder="卡号搜索" clearable style="width:200px" @clear="load" @keyup.enter="load" />
      <el-select v-model="status" placeholder="状态" clearable style="width:120px" @change="load">
        <el-option v-for="s in statusOpts" :key="s" :label="statusText(s)" :value="s" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="card_no" label="卡号" min-width="180" />
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="面值" width="100"><template #default="{ row }">¥{{ Number(row.face_value).toFixed(2) }}</template></el-table-column>
      <el-table-column prop="holder_user_id" label="持有人" width="90"><template #default="{ row }">{{ row.holder_user_id || '-' }}</template></el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'draft'" link type="primary" @click="issue(row.id)">发放</el-button>
          <el-popconfirm v-if="row.status !== 'used' && row.status !== 'void'" title="作废？" @confirm="voidCard(row.id)"><template #reference><el-button link type="warning">作废</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="total > pageSize" class="page"><el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" layout="prev, pager, next, total" background @current-change="load" /></div>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi from '@/api/admin'
const route = useRoute()
const items = ref<any[]>([]), loading = ref(false), page = ref(1), pageSize = ref(20), total = ref(0)
const keyword = ref(''), status = ref('')
const statusOpts = ['draft', 'issued', 'used', 'refunded', 'expired', 'void']
const api = adminApi.resource('/api/v1/asset/cards')
const statusText = (s: string) => ({ draft: '待发放', issued: '已发放', used: '已核销', refunded: '已退款', expired: '已过期', void: '已作废' }[s] || s)
const statusType = (s: string) => ({ draft: 'info', issued: 'warning', used: 'success', refunded: '', expired: 'info', void: 'danger' }[s] || '') as any
async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (status.value) params.status = status.value
    if (keyword.value) params.keyword = keyword.value
    if (route.query.batch_id) params.batch_id = route.query.batch_id
    const d = await api.list(params); items.value = d.items; total.value = d.total
  } finally { loading.value = false }
}
async function issue(id: number) {
  const { value } = await ElMessageBox.prompt('输入持有人 user_id', '发放卡券', { inputPattern: /^\d+$/, inputErrorMessage: '数字' })
  await adminApi.issueCard(id, Number(value)); ElMessage.success('已发放'); load()
}
async function voidCard(id: number) { await adminApi.voidCard(id); ElMessage.success('已作废'); load() }
onMounted(load)
</script>
<style scoped>.ct { font-weight: 600; color: var(--el-text-color-primary) } .filter { display: flex; gap: 10px; margin-bottom: 12px } .page { display: flex; justify-content: flex-end; margin-top: 16px }</style>
