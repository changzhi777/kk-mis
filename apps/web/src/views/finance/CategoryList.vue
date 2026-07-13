<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">收支科目</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增科目</el-button>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="科目名称" min-width="160" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.type === 'income' ? 'success' : 'danger'" size="small">{{ row.type === 'income' ? '收入' : '支出' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="sort" label="排序" width="80" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑科目' : '新增科目'" width="440px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="income">收入</el-radio>
            <el-radio value="expense">支出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
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
const form = reactive<any>({ id: null, parent_id: null, name: '', type: 'expense', code: '', sort: 0, status: true })
const api = adminApi.resource('/api/v1/finance/categories')

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
  else Object.assign(form, { id: null, parent_id: null, name: '', type: 'expense', code: '', sort: 0, status: true })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { name: form.name, parent_id: form.parent_id, type: form.type, code: form.code, sort: form.sort, status: form.status }
    if (form.id) await api.update(form.id, payload)
    else await api.create(payload)
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
