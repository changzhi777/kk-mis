<template>
  <div class="col">
    <!-- 打卡卡片 -->
    <el-card shadow="never" class="mb">
      <div class="clock-stat">
        <div class="ci">
          <div class="lab">上班打卡</div>
          <div class="val">{{ today.clock_in ? today.clock_in.slice(11, 16) : '—' }}</div>
          <el-button type="primary" size="small" :disabled="!!today.clock_in" :loading="li" @click="doClockIn">
            {{ today.clock_in ? '已打卡' : '上班打卡' }}
          </el-button>
        </div>
        <el-divider direction="vertical" />
        <div class="ci">
          <div class="lab">下班打卡</div>
          <div class="val">{{ today.clock_out ? today.clock_out.slice(11, 16) : '—' }}</div>
          <el-button type="success" size="small" :disabled="!today.clock_in || !!today.clock_out" :loading="lo" @click="doClockOut">
            {{ today.clock_out ? '已打卡' : '下班打卡' }}
          </el-button>
        </div>
        <el-divider direction="vertical" />
        <div class="ci">
          <div class="lab">今日状态</div>
          <div class="val">
            <el-tag v-if="today.status" :type="statusType(today.status)" size="large">{{ statusText(today.status) }}</el-tag>
            <span v-else class="muted">未打卡</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 统计 -->
    <div class="stats mb">
      <el-card shadow="never"><div class="n ok">{{ stats.normal }}</div><div class="l">正常出勤</div></el-card>
      <el-card shadow="never"><div class="n warn">{{ stats.late }}</div><div class="l">迟到</div></el-card>
      <el-card shadow="never"><div class="n danger">{{ stats.early }}</div><div class="l">早退</div></el-card>
      <el-card shadow="never"><div class="n">{{ Number(stats.work_hours_sum || 0).toFixed(1) }}h</div><div class="l">本月工时</div></el-card>
    </div>

    <!-- 当月明细 -->
    <el-card shadow="never">
      <template #header>
        <div class="hr">
          <span class="ct">考勤记录</span>
          <div class="hdr-actions">
            <el-button :icon="Download" size="small" @click="exportCsv">导出</el-button>
            <el-date-picker v-model="month" type="month" value-format="YYYY-MM" @change="load" style="width:140px" />
          </div>
        </div>
      </template>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column label="日期" width="120"><template #default="{ row }">{{ row.date?.slice(0, 10) }}</template></el-table-column>
        <el-table-column label="上班" width="90"><template #default="{ row }">{{ row.clock_in?.slice(11, 16) || '—' }}</template></el-table-column>
        <el-table-column label="下班" width="90"><template #default="{ row }">{{ row.clock_out?.slice(11, 16) || '—' }}</template></el-table-column>
        <el-table-column label="工时" width="90"><template #default="{ row }">{{ row.work_hours ? Number(row.work_hours).toFixed(1) + 'h' : '—' }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
        <template #empty><el-empty description="本月无记录" :image-size="60" /></template>
      </el-table>
    </el-card>
  </div>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'

const month = ref(new Date().toISOString().slice(0, 7))
const today = reactive<any>({ clock_in: null, clock_out: null, status: null })
const stats = reactive<any>({ normal: 0, late: 0, early: 0, work_hours_sum: 0 })
const items = ref<any[]>([])
const loading = ref(false), li = ref(false), lo = ref(false)

const statusText = (x: string) => ({ normal: '正常', late: '迟到', early: '早退' }[x] || x)
const statusType = (x: string) => ({ normal: 'success', late: 'warning', early: 'danger' }[x] || undefined) as any

async function loadToday() {
  Object.assign(today, await adminApi.attendanceToday())
}

async function load() {
  loading.value = true
  try {
    const [it, st] = await Promise.all([
      adminApi.attendanceMe(month.value),
      adminApi.attendanceStats(month.value),
    ])
    items.value = it
    Object.assign(stats, st)
  } finally { loading.value = false }
}

async function doClockIn() {
  li.value = true
  try {
    await adminApi.clockIn()
    ElMessage.success('上班打卡成功')
    loadToday()
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '失败')
  } finally { li.value = false }
}

async function doClockOut() {
  lo.value = true
  try {
    await adminApi.clockOut()
    ElMessage.success('下班打卡成功')
    loadToday()
    load()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '失败')
  } finally { lo.value = false }
}

async function exportCsv() {
  try {
    await adminApi.downloadCsv('/api/v1/oa/attendance/export', { month: month.value })
    ElMessage.success('已导出')
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(() => { loadToday(); load() })
</script>
<style scoped>
.col { display: flex; flex-direction: column }
.mb { margin-bottom: 12px }
.clock-stat { display: flex; gap: 24px; align-items: center }
.ci { text-align: center; min-width: 140px }
.ci .lab { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 8px }
.ci .val { font-size: 28px; font-weight: 700; color: var(--el-text-color-primary); margin-bottom: 12px; min-height: 36px }
.muted { color: var(--el-text-color-placeholder); font-size: 16px }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px }
.stats .n { font-size: 28px; font-weight: 700; color: var(--el-text-color-primary) }
.stats .n.ok { color: var(--el-color-success) }
.stats .n.warn { color: var(--el-color-warning) }
.stats .n.danger { color: var(--el-color-danger) }
.stats .l { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 4px }
.hr { display: flex; justify-content: space-between; align-items: center }
.hdr-actions { display: flex; gap: 8px; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
</style>
