<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">账户管理</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增账户</el-button>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="账户名称" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ typeText(row.type) }}</template>
      </el-table-column>
      <el-table-column label="余额" width="140">
        <template #default="{ row }">
          <span :style="{ color: row.balance >= 0 ? 'var(--el-color-success)' : 'var(--el-color-danger)' }">
            ¥ {{ Number(row.balance).toFixed(2) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑账户' : '新增账户'" width="440px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option v-for="[v, l] in typeOptions" :key="v" :label="l" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="期初余额" v-if="!form.id">
          <el-input-number v-model="form.balance" :precision="2" :step="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'

const items = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive<any>({ id: null, name: '', type: 'cash', balance: 0, sort: 0, status: true })
const api = adminApi.resource('/api/v1/finance/accounts')
const typeOptions: [string, string][] = [['cash', '现金'], ['bank', '银行'], ['wechat', '微信'], ['alipay', '支付宝'], ['other', '其他']]
const typeText = (t: string) => typeOptions.find((x) => x[0] === t)?.[1] || t

async function load() {
  loading.value = true
  try {
    items.value = (await api.list()).items
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) Object.assign(form, row)
  else Object.assign(form, { id: null, name: '', type: 'cash', balance: 0, sort: 0, status: true })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (form.id) await api.update(form.id, { name: form.name, type: form.type, sort: form.sort, status: form.status })
    else await api.create({ name: form.name, type: form.type, balance: form.balance, sort: form.sort, status: true })
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '保存失败')) } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  try {
    await api.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '删除失败')) }
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--el-text-color-primary); }
</style>
