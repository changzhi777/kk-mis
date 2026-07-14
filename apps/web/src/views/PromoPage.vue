<template>
  <div class="promo-page">
    <el-card v-if="agent" shadow="never" class="card">
      <div class="muted">您的专属代理</div>
      <h2 class="name">{{ agent.name || `代理 #${agent.agent_id}` }}</h2>
      <div class="region">区域：{{ agent.region_name || agent.region_code }}</div>
      <el-button type="primary" class="btn" @click="goProducts">浏览旅游产品</el-button>
    </el-card>
    <el-empty v-else-if="loaded" description="推广码无效或已失效" />
  </div>
</template>

<script setup lang="ts">
// A1 推广码公开页 /promo/:code（无需登录，扫码看代理）
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { http } from '@/api/admin'

const route = useRoute()
const router = useRouter()
const agent = ref<{ agent_id: number; name: string | null; region_code: string; region_name: string | null } | null>(null)
const loaded = ref(false)

onMounted(async () => {
  try {
    const { data } = await http.get(`/api/v1/agent/promo/${route.params.code}`)
    agent.value = data
  } catch {
    agent.value = null
  } finally {
    loaded.value = true
  }
})

function goProducts() {
  router.push('/cms/products')
}
</script>

<style scoped>
.promo-page { max-width: 480px; margin: 60px auto; padding: 0 16px; }
.card { text-align: center; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.name { margin: 8px 0; color: var(--el-color-primary); }
.region { color: var(--el-text-color-regular); margin-bottom: 16px; }
.btn { margin-top: 8px; }
</style>
