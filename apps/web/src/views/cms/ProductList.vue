<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">旅游产品</span>
        <el-button type="primary" :icon="Plus" @click="goNew">新增产品</el-button>
      </div>
    </template>
    <div class="filter">
      <el-radio-group v-model="typeFilter" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="custom">订制游</el-radio-button>
        <el-radio-button value="pass">权益卡</el-radio-button>
      </el-radio-group>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="标题" min-width="220">
        <template #default="{ row }">
          {{ row.title }}
          <el-tag size="small" :type="typeTag(row.type)" class="ml8">{{ typeText(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="destination" label="目的地" width="120" />
      <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag size="small" :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goEdit(row.id)">编辑</el-button>
          <el-button link v-if="row.status === 'published'" @click="preview(row.slug)">预览</el-button>
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import cmsApi from '@/api/cms'
import { getApiError } from '@/api/admin'
import type { TourProduct, TourProductType } from '@/api/cms'

const router = useRouter()
const items = ref<TourProduct[]>([])
const loading = ref(false)
const typeFilter = ref<'' | TourProductType>('')

const typeText = (t: string) => ({ custom: '订制游', pass: '权益卡' } as const)[t as 'custom' | 'pass']
const typeTag = (t: string) => ({ custom: 'warning', pass: 'success' } as const)[t as 'custom' | 'pass']
const statusText = (s: string) =>
  ({ draft: '草稿', published: '已发布', archived: '已归档' } as const)[s as 'draft' | 'published' | 'archived'] || s
const statusTag = (s: string) =>
  ({ draft: 'info', published: 'success', archived: 'warning' } as const)[s as 'draft' | 'published' | 'archived']

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listProducts(typeFilter.value ? { type: typeFilter.value } : undefined)
  } catch (e: unknown) { ElMessage.error(getApiError(e, '加载失败')) } finally { loading.value = false }
}
function goNew() { router.push('/cms/product/new') }
function goEdit(id: number) { router.push(`/cms/product/${id}`) }
function preview(slug: string) {
  // 公开介绍页（第三阶段落地）；现在先占位打开
  window.open(`${import.meta.env.BASE_URL}product/${slug}`, '_blank')
}
async function remove(id: number) {
  try { await cmsApi.deleteProduct(id); ElMessage.success('已删除'); load() }
  catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) }
}
onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.filter { margin-bottom: 12px; }
.ml8 { margin-left: 8px; }
</style>
