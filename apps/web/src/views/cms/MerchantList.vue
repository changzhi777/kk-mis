<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">合作商户</span><el-button type="primary" :icon="Plus" @click="open()">新增</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="名称" min-width="160">
        <template #default="{ row }"><img v-if="row.logo" :src="row.logo" class="logo" />{{ row.name }}</template>
      </el-table-column>
      <el-table-column prop="address" label="地址" min-width="160" />
      <el-table-column prop="contact" label="联系方式" width="140" />
      <el-table-column prop="benefit_desc" label="权益内容" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">编辑</el-button>
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dv" :title="form.id ? '编辑商户' : '新增商户'" width="520">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="logo URL"><el-input v-model="form.logo" placeholder="可从素材库复制 URL" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
        <el-form-item label="联系方式"><el-input v-model="form.contact" /></el-form-item>
        <el-form-item label="权益内容"><el-input v-model="form.benefit_desc" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import cmsApi from '@/api/cms'
import { getApiError } from '@/api/admin'
import type { Merchant } from '@/api/cms'

const items = ref<Merchant[]>([])
const loading = ref(false)
const dv = ref(false)
const s = ref(false)

function empty(): Merchant {
  return { name: '', logo: '', address: '', contact: '', benefit_desc: '', status: true, sort: 0 }
}
const form = reactive<Merchant>(empty())

async function load() {
  loading.value = true
  try { items.value = await cmsApi.listMerchants() } catch (e: unknown) { ElMessage.error(getApiError(e, '加载失败')) } finally { loading.value = false }
}
function open(row?: Record<string, unknown>) {
  Object.assign(form, row || empty())
  dv.value = true
}
async function save() {
  s.value = true
  try {
    if (form.id) await cmsApi.updateMerchant(form.id, form)
    else await cmsApi.createMerchant(form)
    ElMessage.success('保存成功'); dv.value = false; load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally { s.value = false }
}
async function remove(id: number) {
  await cmsApi.deleteMerchant(id); ElMessage.success('已删除'); load()
}
onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.logo { width: 24px; height: 24px; object-fit: cover; vertical-align: middle; margin-right: 6px; border-radius: 4px; }
</style>
