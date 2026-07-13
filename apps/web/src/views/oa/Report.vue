<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <el-tabs v-model="tab" @tab-change="load" style="flex:1">
          <el-tab-pane label="我的汇报" name="mine" />
          <el-tab-pane label="全部汇报" name="all" />
        </el-tabs>
        <el-button type="primary" :icon="Plus" @click="open()">写汇报</el-button>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="类型" width="80">
        <template #default="{ row }"><el-tag size="small" :type="typeTag(row.type)">{{ typeText(row.type) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="周期" width="220">
        <template #default="{ row }">{{ row.period_start?.slice(0, 10) }} ~ {{ row.period_end?.slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column prop="content" label="本期完成" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="80">
        <template #default="{ row }"><el-tag size="small" :type="row.status === 'read' ? 'success' : 'info'">{{ row.status === 'read' ? '已读' : '已提交' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }"><el-button link type="primary" @click="view(row)">查看</el-button></template>
      </el-table-column>
      <template #empty><el-empty description="暂无汇报" :image-size="60" /></template>
    </el-table>

    <el-dialog v-model="dv" title="写工作汇报" width="640">
      <el-form :model="form" label-width="80px">
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width:160px">
            <el-option value="daily" label="日报" />
            <el-option value="weekly" label="周报" />
            <el-option value="monthly" label="月报" />
          </el-select>
        </el-form-item>
        <el-form-item label="周期">
          <el-date-picker v-model="period" type="daterange" value-format="YYYY-MM-DDT00:00:00" start-placeholder="开始" end-placeholder="结束" style="width:100%" />
        </el-form-item>
        <el-form-item label="本期完成"><el-input v-model="form.content" type="textarea" :rows="4" placeholder="完成了哪些工作…" /></el-form-item>
        <el-form-item label="遇到问题"><el-input v-model="form.problems" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
        <el-form-item label="下期计划"><el-input v-model="form.plan_next" type="textarea" :rows="2" placeholder="选填" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">提交</el-button></template>
    </el-dialog>

    <el-dialog v-model="vv" title="汇报详情" width="640">
      <el-descriptions v-if="cur" :column="1" border>
        <el-descriptions-item label="类型">{{ typeText(cur.type) }}</el-descriptions-item>
        <el-descriptions-item label="周期">{{ cur.period_start?.slice(0, 10) }} ~ {{ cur.period_end?.slice(0, 10) }}</el-descriptions-item>
        <el-descriptions-item label="本期完成">{{ cur.content }}</el-descriptions-item>
        <el-descriptions-item label="遇到问题">{{ cur.problems || '—' }}</el-descriptions-item>
        <el-descriptions-item label="下期计划">{{ cur.plan_next || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'

const items = ref<any[]>([])
const loading = ref(false)
const tab = ref<'mine' | 'all'>('mine')
const dv = ref(false), vv = ref(false), s = ref(false)
const form = reactive<any>({ type: 'daily', content: '', problems: '', plan_next: '' })
const period = ref<[string, string] | null>(null)
const cur = ref<any>(null)
const api = adminApi.resource('/api/v1/oa/reports')

const typeText = (t: string) => ({ daily: '日报', weekly: '周报', monthly: '月报' }[t] || t)
const typeTag = (t: string) => ({ weekly: 'warning', monthly: 'success' } as const)[t]

async function load() {
  loading.value = true
  try {
    const res = tab.value === 'mine'
      ? await api.list()
      : { items: await adminApi.allReports() }
    items.value = res.items
  } finally { loading.value = false }
}

function open() {
  Object.assign(form, { type: 'daily', content: '', problems: '', plan_next: '' })
  period.value = null
  dv.value = true
}

async function save() {
  if (!period.value) { ElMessage.warning('请选择周期'); return }
  if (!form.content.trim()) { ElMessage.warning('请填写本期完成'); return }
  s.value = true
  try {
    await api.create({ ...form, period_start: period.value[0], period_end: period.value[1] })
    ElMessage.success('已提交')
    dv.value = false
    load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally { s.value = false }
}

function view(row: any) {
  cur.value = row
  vv.value = true
  // 管理员查阅时自动标记已读
  if (tab.value === 'all' && row.status !== 'read') {
    adminApi.readReport(row.id).then(() => { row.status = 'read' })
  }
}

onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center; gap: 12px }</style>
