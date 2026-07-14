<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">素材库</span>
        <el-upload :show-file-list="false" :before-upload="onUpload" :accept="accept">
          <el-button type="primary" :icon="Picture" :loading="uploading">上传素材</el-button>
        </el-upload>
      </div>
    </template>
    <div class="filter">
      <el-radio-group v-model="typeFilter" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="image">图片</el-radio-button>
        <el-radio-button value="video">视频</el-radio-button>
      </el-radio-group>
    </div>
    <div v-loading="loading" class="grid">
      <div v-for="a in items" :key="a.id" class="cell">
        <img v-if="a.type === 'image'" :src="a.url" :alt="a.name" class="thumb" />
        <div v-else class="video-cell">🎬<br />{{ a.name }}</div>
        <div class="meta">
          <span class="name" :title="a.name">{{ a.name }}</span>
          <div class="ops">
            <el-button link size="small" @click="copyUrl(a.url)">复制URL</el-button>
            <el-popconfirm title="删除？" @confirm="remove(a.id)"><template #reference><el-button link size="small" type="danger">删除</el-button></template></el-popconfirm>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无素材" />
    </div>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import cmsApi from '@/api/cms'
import { getApiError } from '@/api/admin'
import type { MediaAsset } from '@/api/cms'

const items = ref<MediaAsset[]>([])
const loading = ref(false)
const uploading = ref(false)
const typeFilter = ref<'' | 'image' | 'video'>('')
const accept = '.jpg,.jpeg,.png,.gif,.webp,.mp4,.mov,.webm'

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listMedia(typeFilter.value ? { type: typeFilter.value } : undefined)
  } catch (e: unknown) { ElMessage.error(getApiError(e, '加载失败')) } finally { loading.value = false }
}

async function onUpload(file: File) {
  uploading.value = true
  try {
    await cmsApi.uploadMedia(file)
    ElMessage.success('上传成功'); load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '上传失败')) } finally { uploading.value = false }
  return false // 阻止 el-upload 默认上传
}

async function copyUrl(url: string) {
  try { await navigator.clipboard.writeText(url); ElMessage.success('URL 已复制') }
  catch { ElMessage.warning(`URL: ${url}`) }
}

async function remove(id: number) {
  await cmsApi.deleteMedia(id); ElMessage.success('已删除'); load()
}

onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.filter { margin-bottom: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.cell { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; overflow: hidden; background: var(--el-bg-color); }
.thumb { width: 100%; height: 130px; object-fit: cover; display: block; }
.video-cell { height: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--el-fill-color-light); color: var(--el-text-color-secondary); font-size: 12px; text-align: center; padding: 8px; }
.meta { padding: 6px 8px; }
.name { display: block; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--el-text-color-regular); }
.ops { display: flex; gap: 4px; margin-top: 2px; }
</style>
