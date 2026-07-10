<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">卡券类型</span><el-button type="primary" :icon="Plus" @click="open()">新增</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="类型" width="100"><template #default="{ row }"><el-tag size="small">{{ typeText(row.type) }}</el-tag></template></el-table-column>
      <el-table-column label="面值" width="110"><template #default="{ row }">¥{{ Number(row.face_value).toFixed(2) }}</template></el-table-column>
      <el-table-column prop="valid_days" label="有效天数" width="100" />
      <el-table-column prop="remark" label="备注" min-width="120" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="open(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dv" :title="form.id ? '编辑类型' : '新增类型'" width="460">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="form.type" style="width:100%"><el-option v-for="[v,l] in opts" :key="v" :label="l" :value="v" /></el-select></el-form-item>
        <el-form-item label="面值"><el-input-number v-model="form.face_value" :precision="2" :step="10" style="width:100%" /></el-form-item>
        <el-form-item label="有效天数"><el-input-number v-model="form.valid_days" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
const items = ref<any[]>([]), loading = ref(false), dv = ref(false), s = ref(false)
const form = reactive<any>({ id: null, name: '', type: 'vip', face_value: 0, valid_days: 365, remark: '', status: true, fields_config: null })
const api = adminApi.resource('/api/v1/asset/card-types')
const opts: [string, string][] = [['vip', 'VIP卡'], ['voucher', '代金券'], ['exchange', '兑换券'], ['stored', '储值卡']]
const typeText = (t: string) => opts.find((o) => o[0] === t)?.[1] || t
async function load() { loading.value = true; try { items.value = (await api.list()).items } finally { loading.value = false } }
function open(row?: any) { Object.assign(form, row || { id: null, name: '', type: 'vip', face_value: 0, valid_days: 365, remark: '', status: true, fields_config: null }); dv.value = true }
async function save() { s.value = true; try { if (form.id) await api.update(form.id, form); else await api.create(form); ElMessage.success('保存成功'); dv.value = false; load() } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false } }
async function remove(id: number) { await api.remove(id); ElMessage.success('已删除'); load() }
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) }</style>
