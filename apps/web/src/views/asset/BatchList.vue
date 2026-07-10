<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">卡券批次</span><el-button type="primary" :icon="Plus" @click="openBatch()">新增批次</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="name" label="批次名称" min-width="160" />
      <el-table-column label="类型" width="100"><template #default="{ row }">{{ typeMap[row.type_id] || row.type_id }}</template></el-table-column>
      <el-table-column prop="quantity" label="计划数量" width="100" />
      <el-table-column prop="generated" label="已生成" width="90" />
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openGen(row)">生成卡券</el-button>
          <router-link :to="`/asset/card?batch_id=${row.id}`" class="link">查看卡券</router-link>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="bdv" title="新增批次" width="460">
      <el-form :model="form" label-width="80px">
        <el-form-item label="类型"><el-select v-model="form.type_id" style="width:100%"><el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" /></el-select></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="bdv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="gdv" title="生成卡券（返回明文卡号密码，请导出保存）" width="600">
      <el-form label-width="80px">
        <el-form-item label="数量"><el-input-number v-model="genQty" :min="1" :max="10000" /></el-form-item>
      </el-form>
      <div v-if="genCards.length" class="gen-list">
        <p class="hint">生成 {{ genCards.length }} 张（仅本次显示明文密码）：</p>
        <el-table :data="genCards" size="small" max-height="240">
          <el-table-column prop="card_no" label="卡号" />
          <el-table-column prop="password" label="密码" width="100" />
        </el-table>
      </div>
      <template #footer><el-button @click="gdv = false">关闭</el-button><el-button type="primary" :loading="s" @click="doGen">生成</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
const items = ref<any[]>([]), types = ref<any[]>([]), loading = ref(false), s = ref(false)
const bdv = ref(false), gdv = ref(false), genQty = ref(10), genCards = ref<any[]>([])
const form = reactive<any>({ type_id: null, name: '', quantity: 100 })
const api = adminApi.resource('/api/v1/asset/batches')
const typeMap = computed(() => Object.fromEntries(types.value.map((t) => [t.id, t.name])))
async function load() {
  loading.value = true
  try {
    types.value = (await adminApi.resource('/api/v1/asset/card-types').list()).items
    if (!form.type_id && types.value[0]) form.type_id = types.value[0].id
    items.value = (await api.list()).items
  } finally { loading.value = false }
}
function openBatch() { Object.assign(form, { type_id: types.value[0]?.id, name: '', quantity: 100 }); bdv.value = true }
async function save() {
  s.value = true
  try { await api.create(form); ElMessage.success('批次已创建'); bdv.value = false; load() } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false }
}
function openGen(row: any) { genCards.value = []; genQty.value = 10; gdv.value = true; sessionStorage['genBatchId'] = row.id }
async function doGen() {
  s.value = true
  try { const r = await adminApi.generateCards(Number(sessionStorage['genBatchId']), genQty.value); genCards.value = r.cards; ElMessage.success(`生成 ${r.generated} 张`) } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false; load() }
}
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) } .link { color: var(--el-color-primary); margin-left: 8px } .gen-list { margin-top: 12px } .hint { color: var(--el-text-color-secondary); font-size: 12px; margin: 0 0 6px }</style>
