<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">权限菜单</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增权限</el-button>
      </div>
    </template>
    <el-table :data="tree" v-loading="loading" row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="code" label="编码" width="200" />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.type === 'menu' ? 'info' : row.type === 'api' ? 'success' : 'warning'">{{ typeText(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="path" label="路径" width="200" />
      <el-table-column prop="icon" label="图标" width="100" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑权限' : '新增权限'" width="520px">
      <el-form :model="form" label-width="72px">
        <el-form-item label="父级">
          <el-select v-model="form.parent_id" clearable placeholder="顶级">
            <el-option v-for="p in flat" :key="p.id" :label="p.name + ' (' + p.code + ')'" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" placeholder="如 system:user:list" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio value="menu">菜单</el-radio>
            <el-radio value="api">API</el-radio>
            <el-radio value="button">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="路径"><el-input v-model="form.path" placeholder="前端路由 或 后端 api" /></el-form-item>
        <el-form-item label="方法" v-if="form.type === 'api'">
          <el-select v-model="form.method" style="width: 120px">
            <el-option v-for="m in ['GET', 'POST', 'PUT', 'DELETE']" :key="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="图标"><el-input v-model="form.icon" placeholder="Element 图标名" /></el-form-item>
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

const tree = ref<any[]>([])
const flat = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive<any>({
  id: null, parent_id: null, name: '', code: '', type: 'menu', path: '', method: null, icon: '', sort: 0, visible: true,
})
const permsApi = adminApi.resource('/api/v1/permissions')
const typeText = (t: string) => ({ menu: '菜单', api: 'API', button: '按钮' }[t] || t)

async function load() {
  loading.value = true
  try {
    const [t, f] = await Promise.all([adminApi.permissionTree(), adminApi.permissionFlat()])
    tree.value = t
    flat.value = f
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) Object.assign(form, row)
  else Object.assign(form, { id: null, parent_id: null, name: '', code: '', type: 'menu', path: '', method: null, icon: '', sort: 0, visible: true })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form }
    if (payload.type !== 'api') payload.method = null
    if (form.id) await permsApi.update(form.id, payload)
    else await permsApi.create(payload)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '保存失败')) } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  try {
    await permsApi.remove(id)
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
