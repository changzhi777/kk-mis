<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">代理管理</span><el-button type="primary" :icon="Plus" @click="open()">新增代理</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column label="级别" width="80"><template #default="{ row }"><el-tag size="small" :type="row.level === 1 ? 'primary' : 'warning'">{{ row.level }}级</el-tag></template></el-table-column>
      <el-table-column label="上级" width="100"><template #default="{ row }">{{ agentMap[row.parent_id]?.name || '-' }}</template></el-table-column>
      <el-table-column prop="user_id" label="用户ID" width="80" />
      <el-table-column label="分润率" width="90"><template #default="{ row }">{{ (row.commission_rate * 100).toFixed(1) }}%</template></el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="open(row)">编辑</el-button>
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dv" :title="form.id ? '编辑代理' : '新增代理'" width="460">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="用户ID"><el-input-number v-model="form.user_id" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="级别"><el-select v-model="form.level" style="width:100%"><el-option :value="1" label="一级" /><el-option :value="2" label="二级" /></el-select></el-form-item>
        <el-form-item label="上级" v-if="form.level === 2"><el-select v-model="form.parent_id" style="width:100%"><el-option v-for="a in level1" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
        <el-form-item label="分润率"><el-input-number v-model="form.commission_rate" :precision="4" :step="0.05" :min="0" :max="1" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
const items = ref<any[]>([]), loading = ref(false), dv = ref(false), s = ref(false)
const form = reactive<any>({ id: null, user_id: 1, name: '', level: 1, parent_id: null, commission_rate: 0.2, status: true })
const api = adminApi.resource('/api/v1/agent/agents')
const agentMap = computed(() => Object.fromEntries(items.value.map((a) => [a.id, a])))
const level1 = computed(() => items.value.filter((a) => a.level === 1))
async function load() { loading.value = true; try { items.value = (await api.list()).items } finally { loading.value = false } }
function open(row?: any) { Object.assign(form, row || { id: null, user_id: 1, name: '', level: 1, parent_id: null, commission_rate: 0.2, status: true }); dv.value = true }
async function save() { s.value = true; try { if (form.id) await api.update(form.id, form); else await api.create(form); ElMessage.success('保存成功'); dv.value = false; load() } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false } }
async function remove(id: number) { await api.remove(id); ElMessage.success('已删除'); load() }
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) }</style>
