<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">优惠券</span><el-button type="primary" :icon="Plus" @click="open()">新增</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="code" label="券码" width="140" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="折扣" width="140">
        <template #default="{ row }">{{ row.discount_type === 'percent' ? row.discount_value + '%' : '¥' + Number(row.discount_value).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="门槛" width="100"><template #default="{ row }">满 ¥{{ Number(row.min_total || 0).toFixed(0) }}</template></el-table-column>
      <el-table-column label="用量" width="120">
        <template #default="{ row }">{{ row.used_count }}{{ row.max_uses > 0 ? ' / ' + row.max_uses : ' / ∞' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="open(row)">编辑</el-button>
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dv" :title="form.id ? '编辑券' : '新增券'" width="520">
      <el-form :model="form" label-width="90px">
        <el-form-item label="券码"><el-input v-model="form.code" :disabled="!!form.id" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="折扣类型"><el-select v-model="form.discount_type"><el-option label="百分比" value="percent" /><el-option label="固定金额" value="fixed" /></el-select></el-form-item>
        <el-form-item label="折扣值"><el-input-number v-model="form.discount_value" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="满减门槛"><el-input-number v-model="form.min_total" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="最大用量"><el-input-number v-model="form.max_uses" :min="0" /><span class="hint">（0=不限）</span></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.status" /></el-form-item>
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
import type { Coupon } from '@/api/cms'

const items = ref<Coupon[]>([])
const loading = ref(false)
const dv = ref(false)
const s = ref(false)

function empty(): Coupon {
  return { code: '', name: '', discount_type: 'percent', discount_value: 10, min_total: 0, max_uses: 0, status: true }
}
const form = reactive<Coupon>(empty())

async function load() {
  loading.value = true
  try { items.value = await cmsApi.listCoupons() } catch (e: unknown) { ElMessage.error(getApiError(e, '加载失败')) } finally { loading.value = false }
}
function open(row?: Record<string, unknown>) {
  Object.assign(form, row || empty())
  dv.value = true
}
async function save() {
  s.value = true
  try {
    if (form.id) await cmsApi.updateCoupon(form.id, form)
    else await cmsApi.createCoupon(form)
    ElMessage.success('保存成功'); dv.value = false; load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally { s.value = false }
}
async function remove(id: number) {
  await cmsApi.deleteCoupon(id); ElMessage.success('已删除'); load()
}
onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.hint { margin-left: 8px; color: var(--el-text-color-secondary); font-size: 12px }
</style>
