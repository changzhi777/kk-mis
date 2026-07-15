<template>
  <div class="dashboard">
    <div class="edit-bar">
      <el-switch v-model="editMode" active-text="编辑模块排序" />
      <el-button v-if="editMode" size="small" @click="resetOrder">重置默认</el-button>
      <span v-if="editMode" class="muted">拖动 ⋮⋮ 把手调整顺序，自动保存</span>
    </div>
    <draggable
      v-model="order"
      item-key="key"
      :disabled="!editMode"
      handle=".drag-handle"
      @end="saveOrder"
    >
      <template #item="{ element }">
        <div class="module-wrap">
          <div v-if="editMode" class="drag-handle">⋮⋮ 拖拽排序</div>
          <!-- 待办快捷 -->
          <el-row v-if="element.key === 'todo'" :gutter="16">
            <el-col :xs="12" :sm="6" v-for="t in todos" :key="t.type">
              <el-card shadow="hover" class="todo-card" @click="t.count > 0 && $router.push(t.link)">
                <div class="todo-count" :class="{ zero: t.count === 0 }">{{ t.count }}</div>
                <div class="todo-label">{{ t.label }}</div>
              </el-card>
            </el-col>
          </el-row>
          <!-- 我的概况 -->
          <el-card v-else-if="element.key === 'me'" shadow="never" class="me-card">
            <template #header><span class="ct">我的概况</span></template>
            <el-row :gutter="16">
              <el-col :xs="12" :sm="6">
                <div class="me-item">
                  <div class="me-label">今日打卡</div>
                  <div class="me-val">
                    <span v-if="me.clock_in">{{ me.clock_in.slice(11, 16) }}<span class="dim"> 上班</span></span>
                    <span v-else class="dim">未打卡</span>
                    <span v-if="me.clock_out" style="margin-left: 8px">{{ me.clock_out.slice(11, 16) }}<span class="dim"> 下班</span></span>
                  </div>
                  <el-tag v-if="me.attendance_status" size="small" :type="attType(me.attendance_status)" style="margin-top: 6px">{{ attText(me.attendance_status) }}</el-tag>
                </div>
              </el-col>
              <el-col :xs="12" :sm="6"><div class="me-item"><div class="me-label">本月已批报销</div><div class="me-val expense">¥{{ Number(me.month_expense || 0).toFixed(2) }}</div></div></el-col>
              <el-col :xs="12" :sm="6"><div class="me-item"><div class="me-label">我的汇报</div><div class="me-val">{{ me.report_count }} <span class="dim">篇</span></div></div></el-col>
              <el-col :xs="12" :sm="6"><div class="me-item"><div class="me-label">公告数</div><div class="me-val">{{ counts.announcements }}</div></div></el-col>
            </el-row>
          </el-card>
          <!-- 最新公告 -->
          <el-card v-else-if="element.key === 'announcement'" shadow="never" style="margin-top: 16px">
            <template #header>
              <div class="hr"><span class="ct">最新公告</span><router-link to="/announcement" class="more">更多 →</router-link></div>
            </template>
            <el-empty v-if="!latest.length" description="暂无公告" :image-size="60" />
            <div v-for="a in latest" :key="a.id" class="ann-item" @click="$router.push('/announcement')">
              <span class="ann-title">{{ a.title }}</span>
              <TimeText :value="a.published_at" />
            </div>
          </el-card>
        </div>
      </template>
    </draggable>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import draggable from 'vuedraggable'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError, http } from '@/api/admin'
import TimeText from '@/components/TimeText.vue'

const DEFAULT_ORDER = ['todo', 'me', 'announcement']
const order = ref(DEFAULT_ORDER.map((k) => ({ key: k })))
const editMode = ref(false)
const todos = ref<any[]>([])
const latest = ref<any[]>([])
const counts = reactive<any>({ announcements: 0 })
const me = reactive<any>({ clock_in: null, clock_out: null, attendance_status: null, month_expense: 0, report_count: 0 })

const attText = (x: string) => ({ normal: '正常', late: '迟到', early: '早退' }[x] || x)
const attType = (x: string) => ({ normal: 'success', late: 'warning', early: 'danger' } as const)[x]

async function load() {
  const d = await adminApi.resource('/api/v1/dashboard').list()
  todos.value = d.todos
  latest.value = d.latest_announcements
  Object.assign(counts, d.counts || {})
  Object.assign(me, d.me || {})
  // 加载用户偏好排序
  try {
    const prefs = await http.get<{ dashboard_order?: string[] }>('/api/v1/auth/preferences')
    const saved = prefs.data.dashboard_order
    if (saved && saved.length) order.value = saved.map((k) => ({ key: k }))
  } catch { /* 用默认 */ }
}

async function saveOrder() {
  try {
    await http.put('/api/v1/auth/preferences', { dashboard_order: order.value.map((o) => o.key) })
    ElMessage.success('排序已保存')
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '保存失败'))
  }
}

function resetOrder() {
  order.value = DEFAULT_ORDER.map((k) => ({ key: k }))
  saveOrder()
}

onMounted(load)
</script>

<style scoped>
.edit-bar { margin-bottom: 12px; display: flex; align-items: center; gap: 12px; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; }
.module-wrap { position: relative; }
.drag-handle { cursor: move; color: var(--el-text-color-secondary); font-size: 12px; padding: 4px 0; }
.todo-card { text-align: center; cursor: pointer; transition: transform 0.15s }
.todo-card:hover { transform: translateY(-2px) }
.todo-count { font-size: 32px; font-weight: 700; color: var(--el-color-primary) }
.todo-count.zero { color: var(--el-text-color-placeholder) }
.todo-label { color: var(--el-text-color-secondary); margin-top: 4px; font-size: 13px }
.me-card { margin-top: 16px }
.me-item { padding: 4px 0 }
.me-label { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 8px }
.me-val { font-size: 20px; font-weight: 600 }
.me-val.expense { color: var(--el-color-danger) }
.me-val .dim { font-size: 13px; font-weight: 400; color: var(--el-text-color-secondary) }
.dim { color: var(--el-text-color-placeholder); font-size: 14px }
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600 }
.more { color: var(--el-color-primary); font-size: 13px; text-decoration: none }
.ann-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); cursor: pointer }
.ann-item:last-child { border-bottom: none }
.ann-title { color: var(--el-text-color-primary) }
</style>
