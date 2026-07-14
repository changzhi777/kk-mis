<template>
  <div class="search-page">
    <div class="search-bar">
      <el-input v-model="q" placeholder="搜索目的地 / 主题 / 分类 / 关键词" clearable @keyup.enter="doSearch">
        <template #append><el-button :icon="Search" @click="doSearch">搜索</el-button></template>
      </el-input>
    </div>
    <div class="container" v-loading="loading">
      <div v-for="p in items" :key="p.id" class="card" @click="go(p.slug)">
        <img v-if="p.cover_image" :src="p.cover_image" class="cover" />
        <div v-else class="cover ph">🏔</div>
        <div class="info">
          <h3>{{ p.title }}</h3>
          <p class="summary">{{ p.summary }}</p>
          <div class="meta">
            <el-tag v-if="p.destination" size="small">{{ p.destination }}</el-tag>
            <el-tag v-if="p.category" size="small" type="info">{{ p.category }}</el-tag>
            <el-tag v-if="p.theme" size="small" type="warning">{{ p.theme }}</el-tag>
          </div>
        </div>
      </div>
      <el-empty v-if="!loading && searched && !items.length" description="无匹配产品" />
    </div>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import cmsApi from '@/api/cms'
import type { TourProduct } from '@/api/cms'

const route = useRoute()
const router = useRouter()
const q = ref((route.query.q as string) || '')
const items = ref<TourProduct[]>([])
const loading = ref(false)
const searched = ref(false)

async function doSearch() {
  if (!q.value.trim()) return
  router.replace({ query: { q: q.value } })
  loading.value = true
  searched.value = true
  try {
    items.value = await cmsApi.searchProducts(q.value.trim())
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function go(slug: string) {
  router.push(`/product/${slug}`)
}

onMounted(() => {
  if (q.value) doSearch()
})
</script>
<style scoped>
.search-page { min-height: 100vh; background: var(--el-bg-color-page); padding-bottom: 30px; }
.search-bar { max-width: 700px; margin: 0 auto; padding: 24px 16px 0; }
.container { max-width: 700px; margin: 0 auto; padding: 16px; }
.card { display: flex; gap: 12px; background: var(--el-bg-color); border-radius: 8px; overflow: hidden; margin-bottom: 12px; cursor: pointer; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.card:hover { box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); }
.cover { width: 150px; height: 104px; object-fit: cover; flex-shrink: 0; }
.cover.ph { display: flex; align-items: center; justify-content: center; background: var(--el-color-primary-light-9); font-size: 32px; color: var(--el-text-color-secondary); }
.info { padding: 10px 12px; flex: 1; min-width: 0; }
.info h3 { margin: 0 0 6px; font-size: 16px; color: var(--el-text-color-primary); }
.summary { margin: 0 0 8px; font-size: 13px; color: var(--el-text-color-secondary); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.meta { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
