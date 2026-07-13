<template>
  <el-card shadow="never">
    <template #header>
      <div class="hdr">
        <span class="ct">区域代理管理（按 region_code 划分销售范围）</span>
        <el-button type="primary" :icon="Plus" @click="open()">新增区域代理</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="区域代码" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.region_code }}</el-tag>
          <span style="margin-left:8px;color:var(--el-text-color-secondary)">
            {{ row.region_name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="代理名称" width="140" />
      <el-table-column prop="user_id" label="用户ID" width="100" />
      <el-table-column label="单次返佣上限">
        <template #default="{ row }">
          {{ (Number(row.commission_rate) * 100).toFixed(0) }}%
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status ? 'success' : 'info'">
            {{ row.status ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">编辑</el-button>
          <el-button link type="danger" @click="del(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dv" :title="form.id ? '编辑区域代理' : '新增区域代理'" width="480">
      <el-form :model="form" label-width="100px">
        <el-form-item label="区域代码">
          <el-input v-model="form.region_code" maxlength="16" placeholder="如 SH / BJ / GZ" />
        </el-form-item>
        <el-form-item label="区域名称">
          <el-input v-model="form.region_name" maxlength="64" placeholder="如 上海" />
        </el-form-item>
        <el-form-item label="代理名称">
          <el-input v-model="form.name" maxlength="50" />
        </el-form-item>
        <el-form-item label="用户ID">
          <el-input-number v-model="form.user_id" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item label="单次返佣上限">
          <el-input-number
            v-model="form.commission_rate"
            :precision="2"
            :step="0.05"
            :min="0"
            :max="0.5"
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dv = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'

const items = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const dv = ref(false)

const form = reactive<any>({
  id: null,
  region_code: '',
  region_name: '',
  name: '',
  user_id: 1,
  commission_rate: 0.3,
  status: true,
  remark: '',
})

const api = adminApi.resource('/api/v1/agent/agents')

async function load() {
  loading.value = true
  try {
    const d = await api.list()
    items.value = d.items
  } finally {
    loading.value = false
  }
}

function open(row?: any) {
  if (row) {
    Object.assign(form, row)
  } else {
    Object.assign(form, {
      id: null,
      region_code: '',
      region_name: '',
      name: '',
      user_id: 1,
      commission_rate: 0.3,
      status: true,
      remark: '',
    })
  }
  dv.value = true
}

async function save() {
  if (!form.region_code || form.region_code.length < 2) {
    ElMessage.error('区域代码至少 2 个字符')
    return
  }
  saving.value = true
  try {
    if (form.id) {
      await api.update(form.id, form)
    } else {
      await api.create(form)
    }
    ElMessage.success('保存成功')
    dv.value = false
    await load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '保存失败')) } finally {
    saving.value = false
  }
}

async function del(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该区域代理？', '警告', { type: 'warning' })
  } catch {
    return // 用户取消
  }
  try {
    await api.remove(id)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '删除失败')) }
}

onMounted(load)
</script>

<style scoped>
.hdr {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ct {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>