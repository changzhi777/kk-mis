<template>
  <el-dialog v-model="visible" title="选择素材" width="780" @open="load">
    <div class="filter">
      <el-radio-group v-model="typeFilter" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="image">图片</el-radio-button>
        <el-radio-button value="video">视频</el-radio-button>
      </el-radio-group>
    </div>
    <div v-loading="loading" class="grid">
      <div
        v-for="a in items"
        :key="a.id"
        class="cell"
        :class="{ selected: selected.includes(a.url) }"
        @click="toggle(a)"
      >
        <img v-if="a.type === 'image'" :src="a.url" :alt="a.name" />
        <div v-else class="vc">🎬</div>
        <div class="nm" :title="a.name">{{ a.name }}</div>
        <el-icon v-if="selected.includes(a.url)" class="ck"><CircleCheck /></el-icon>
      </div>
      <el-empty v-if="!loading && !items.length" description="暂无素材" :image-size="60" />
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!selected.length" @click="confirm">
        确定（{{ selected.length }}）
      </el-button>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import cmsApi from '@/api/cms'
import { getApiError } from '@/api/admin'
import type { MediaAsset } from '@/api/cms'

const props = defineProps<{ modelValue: boolean; multiple?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  confirm: [urls: string[]]
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, (v) => (visible.value = v))
watch(visible, (v) => emit('update:modelValue', v))

const items = ref<MediaAsset[]>([])
const loading = ref(false)
const typeFilter = ref<'' | 'image' | 'video'>('')
const selected = ref<string[]>([])

async function load() {
  loading.value = true
  try {
    items.value = await cmsApi.listMedia(typeFilter.value ? { type: typeFilter.value } : undefined)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  } finally {
    loading.value = false
  }
}

function toggle(a: MediaAsset) {
  const i = selected.value.indexOf(a.url)
  if (i >= 0) selected.value.splice(i, 1)
  else if (props.multiple) selected.value.push(a.url)
  else selected.value = [a.url]
}

function confirm() {
  emit('confirm', selected.value)
  visible.value = false
  selected.value = []
}
</script>
<style scoped>
.filter { margin-bottom: 12px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; max-height: 460px; overflow-y: auto; }
.cell { border: 2px solid transparent; border-radius: 6px; overflow: hidden; cursor: pointer; position: relative; background: var(--el-fill-color-light); }
.cell.selected { border-color: var(--el-color-primary); }
.cell img { width: 100%; height: 100px; object-fit: cover; display: block; }
.vc { height: 100px; display: flex; align-items: center; justify-content: center; font-size: 28px; color: var(--el-text-color-secondary); }
.nm { font-size: 11px; padding: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--el-text-color-secondary); }
.ck { position: absolute; top: 4px; right: 4px; color: var(--el-color-primary); font-size: 22px; background: #fff; border-radius: 50%; }
</style>
