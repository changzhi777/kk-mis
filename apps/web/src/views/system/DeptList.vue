<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">部门管理</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增部门</el-button>
      </div>
    </template>
    <el-table :data="treeData" v-loading="loading" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="leader" label="负责人" width="100" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑部门' : '新增部门'" width="460px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="父级">
          <el-select v-model="form.parent_id" clearable placeholder="顶级部门">
            <el-option v-for="d in items" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="负责人"><el-input v-model="form.leader" /></el-form-item>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'

const items = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive<any>({ id: null, parent_id: null, name: '', code: '', leader: '', sort: 0, status: true })
const api = adminApi.resource('/api/v1/departments')

const treeData = computed(() => buildTree(items.value))

function buildTree(list: any[]): any[] {
  const byId: Record<number, any> = {}
  list.forEach((x) => (byId[x.id] = { ...x, children: [] }))
  const roots: any[] = []
  list.forEach((x) => {
    const node = byId[x.id]
    if (x.parent_id && byId[x.parent_id]) byId[x.parent_id].children.push(node)
    else roots.push(node)
  })
  return roots
}

async function load() {
  loading.value = true
  try {
    const data = await api.list()
    items.value = data.items
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) Object.assign(form, row)
  else Object.assign(form, { id: null, parent_id: null, name: '', code: '', leader: '', sort: 0, status: true })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { name: form.name, parent_id: form.parent_id, code: form.code, leader: form.leader, sort: form.sort, status: form.status }
    if (form.id) await api.update(form.id, payload)
    else await api.create(payload)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
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

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--el-text-color-primary); }
</style>
