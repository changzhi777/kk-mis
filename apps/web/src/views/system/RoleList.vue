<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">角色管理</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增角色</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="name" label="名称" width="140" />
      <el-table-column prop="data_scope" label="数据范围" width="120" />
      <el-table-column label="权限数" width="100">
        <template #default="{ row }">{{ row.permission_ids?.length || 0 }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)">
            <template #reference>
              <el-button link type="danger" :disabled="row.code === 'super_admin'">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑角色' : '新增角色'" width="560px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="编码"><el-input v-model="form.code" :disabled="!!form.id" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="form.data_scope" style="width: 100%">
            <el-option label="全部数据" value="all" />
            <el-option label="本部门" value="dept" />
            <el-option label="本人" value="self" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
        <el-form-item label="权限分配">
          <el-tree
            ref="treeRef"
            :data="permissionTree"
            node-key="id"
            :props="{ label: 'name' }"
            show-checkbox
            :default-checked-keys="form.permission_ids"
            check-strictly
          />
        </el-form-item>
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
import { ElMessage, type ElTree } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'

const items = ref<any[]>([])
const permissionTree = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const treeRef = ref<InstanceType<typeof ElTree>>()
const form = reactive<any>({
  id: null, code: '', name: '', data_scope: 'all', remark: '', permission_ids: [],
})

const rolesApi = adminApi.resource('/api/v1/roles')

async function load() {
  loading.value = true
  try {
    const data = await rolesApi.list()
    items.value = data.items
    if (permissionTree.value.length === 0) {
      permissionTree.value = await adminApi.permissionTree()
    }
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) {
    Object.assign(form, row)
  } else {
    Object.assign(form, { id: null, code: '', name: '', data_scope: 'all', remark: '', permission_ids: [] })
  }
  dialogVisible.value = true
  setTimeout(() => treeRef.value?.setCheckedKeys(form.permission_ids || []))
}

async function save() {
  saving.value = true
  try {
    const checked = treeRef.value?.getCheckedKeys() || []
    const payload = {
      code: form.code, name: form.name, data_scope: form.data_scope,
      remark: form.remark, status: true, sort: 0, permission_ids: checked as number[],
    }
    if (form.id) {
      await rolesApi.update(form.id, payload)
    } else {
      await rolesApi.create(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '保存失败')) } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  try {
    await rolesApi.remove(id)
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
