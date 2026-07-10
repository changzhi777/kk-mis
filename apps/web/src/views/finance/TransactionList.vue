<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">收支流水</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">录入流水</el-button>
      </div>
    </template>

    <div class="filter-bar">
      <el-radio-group v-model="filter.type" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="income">收入</el-radio-button>
        <el-radio-button value="expense">支出</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="日期" width="160">
        <template #default="{ row }"><TimeText :value="row.transaction_date" /></template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="row.type === 'income' ? 'success' : 'danger'" size="small">{{ row.type === 'income' ? '收入' : '支出' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="金额" width="120">
        <template #default="{ row }">
          <span :style="{ color: row.type === 'income' ? 'var(--el-color-success)' : 'var(--el-color-danger)', fontWeight: 600 }">
            {{ row.type === 'income' ? '+' : '-' }}¥{{ Number(row.amount).toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="账户" width="120">
        <template #default="{ row }">{{ accountMap[row.account_id]?.name || row.account_id }}</template>
      </el-table-column>
      <el-table-column label="科目" width="120">
        <template #default="{ row }">{{ categoryMap[row.category_id]?.name || row.category_id }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="140" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-popconfirm title="确定删除？（余额会回滚）" @confirm="remove(row.id)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无流水" :image-size="60" />
      </template>
    </el-table>

    <div v-if="total > pageSize" class="pagination">
      <el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" layout="prev, pager, next, total" background @current-change="load" />
    </div>

    <el-dialog v-model="dialogVisible" title="录入流水" width="480px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.type" @change="onTypeChange">
            <el-radio value="income">收入</el-radio>
            <el-radio value="expense">支出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="form.amount" :min="0.01" :precision="2" :step="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="账户">
          <el-select v-model="form.account_id" style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-select v-model="form.category_id" style="width: 100%">
            <el-option v-for="c in availableCategories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.transaction_date" type="datetime" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'

const items = ref<any[]>([])
const accounts = ref<any[]>([])
const categories = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filter = reactive<{ type: string }>({ type: '' })
const form = reactive<any>({
  type: 'expense', amount: 0, account_id: null, category_id: null,
  transaction_date: new Date().toISOString().slice(0, 19), remark: '',
})
const api = adminApi.resource('/api/v1/finance/transactions')

const accountMap = computed(() => Object.fromEntries(accounts.value.map((a) => [a.id, a])))
const categoryMap = computed(() => Object.fromEntries(categories.value.map((c) => [c.id, c])))
const availableCategories = computed(() => categories.value.filter((c) => c.type === form.type))

async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (filter.type) params.type = filter.type
    const data = await api.list(params)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const [accs, cats] = await Promise.all([
    adminApi.resource('/api/v1/finance/accounts').list(),
    adminApi.resource('/api/v1/finance/categories').list(),
  ])
  accounts.value = accs.items
  categories.value = cats.items
  if (accounts.value[0]) form.account_id = accounts.value[0].id
}

function onTypeChange() {
  form.category_id = availableCategories.value[0]?.id || null
}

function openDialog() {
  Object.assign(form, {
    type: 'expense', amount: 0, account_id: accounts.value[0]?.id || null,
    category_id: availableCategories.value[0]?.id || null,
    transaction_date: new Date().toISOString().slice(0, 19), remark: '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.amount || !form.account_id || !form.category_id) {
    ElMessage.warning('请填写完整')
    return
  }
  saving.value = true
  try {
    await api.create(form)
    ElMessage.success('录入成功')
    dialogVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '录入失败')
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  try {
    await api.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  await loadMeta()
  await load()
})
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--el-text-color-primary); }
.filter-bar { margin-bottom: 12px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
