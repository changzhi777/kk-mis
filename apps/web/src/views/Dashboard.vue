<template>
  <div class="dashboard">
    <el-row :gutter="16">
      <el-col :xs="12" :sm="6" v-for="t in todos" :key="t.type">
        <el-card shadow="hover" class="todo-card" @click="t.count > 0 && $router.push(t.link)">
          <div class="todo-count" :class="{ zero: t.count === 0 }">{{ t.count }}</div>
          <div class="todo-label">{{ t.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="hr">
          <span class="ct">最新公告</span>
          <router-link to="/oa/announcement" class="more">更多 →</router-link>
        </div>
      </template>
      <el-empty v-if="!latest.length" description="暂无公告" :image-size="60" />
      <div v-for="a in latest" :key="a.id" class="ann-item" @click="$router.push('/oa/announcement')">
        <span class="ann-title">{{ a.title }}</span>
        <TimeText :value="a.published_at" />
      </div>
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'

const todos = ref<any[]>([])
const latest = ref<any[]>([])

async function load() {
  const d = await adminApi.resource('/api/v1/dashboard').list()
  todos.value = d.todos
  latest.value = d.latest_announcements
}
onMounted(load)
</script>
<style scoped>
.todo-card { text-align: center; cursor: pointer; transition: transform 0.15s }
.todo-card:hover { transform: translateY(-2px) }
.todo-count { font-size: 32px; font-weight: 700; color: var(--el-color-primary) }
.todo-count.zero { color: var(--el-text-color-placeholder) }
.todo-label { color: var(--el-text-color-secondary); margin-top: 4px; font-size: 13px }
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.more { color: var(--el-color-primary); font-size: 13px; text-decoration: none }
.ann-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); cursor: pointer }
.ann-item:last-child { border-bottom: none }
.ann-title { color: var(--el-text-color-primary) }
</style>
