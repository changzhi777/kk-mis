<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span class="card-title">用户管理</span>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增用户</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column prop="phone" label="手机" width="130" />
      <el-table-column label="角色" width="140">
        <template #default="{ row }">
          {{ row.role_ids.map((id: number) => roleMap[id]?.name).filter(Boolean).join('、') || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button link type="warning" @click="resetPwd(row)">重置密码</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)">
            <template #reference>
              <el-button link type="danger" :disabled="row.username === 'admin'">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑用户' : '新增用户'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="密码" v-if="!form.id">
          <el-input v-model="form.password" type="password" placeholder="至少6位" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="手机"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_ids" multiple style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.status" /></el-form-item>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi from '@/api/admin'

const items = ref<any[]>([])
const roles = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const form = reactive<any>({
  id: null, username: '', password: '', name: '', email: '', phone: '', role_ids: [], status: true,
})
const roleMap = computed(() => Object.fromEntries(roles.value.map((r) => [r.id, r])))

const usersApi = adminApi.resource('/api/v1/users')

async function load() {
  loading.value = true
  try {
    const [u, r] = await Promise.all([
      adminApi.resource('/api/v1/roles').list(),
      Promise.resolve(),
    ])
    roles.value = u.items
    const data = await usersApi.list()
    items.value = data.items
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  if (row) {
    Object.assign(form, row, { password: '' })
  } else {
    Object.assign(form, {
      id: null, username: '', password: '', name: '', email: '', phone: '', role_ids: [], status: true,
    })
  }
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (form.id) {
      await usersApi.update(form.id, {
        name: form.name, email: form.email, phone: form.phone,
        role_ids: form.role_ids, status: form.status,
      })
    } else {
      await usersApi.create({
        username: form.username, password: form.password, name: form.name,
        email: form.email, phone: form.phone, role_ids: form.role_ids, status: form.status,
      })
    }
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
    await usersApi.remove(id)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function resetPwd(row: any) {
  const { value } = await ElMessageBox.prompt('输入新密码（至少6位）', `重置 ${row.username} 密码`, {
    inputPattern: /^.{6,}$/, inputErrorMessage: '至少6位',
  })
  await adminApi.resetUserPassword(row.id, value)
  ElMessage.success('密码已重置')
}

onMounted(load)
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--el-text-color-primary); }
</style>
