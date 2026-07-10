<template>
  <div class="detail-page" v-loading="loading">
    <el-page-header title="返回" @back="$router.back()" class="page-header">
      <template #content>
        <span class="page-title">{{ meeting?.title || '加载中...' }}</span>
        <StatusTag v-if="meeting" :status="meeting.status" size="small" style="margin-left: 8px" />
      </template>
    </el-page-header>

    <el-row :gutter="16">
      <el-col :xs="24" :md="16">
        <!-- 摘要卡片 -->
        <el-card shadow="never">
          <template #header>
            <div class="card-title"><el-icon><Document /></el-icon><span>会议摘要</span></div>
          </template>

          <div v-if="meeting?.status === 'completed'">
            <p class="summary-text">{{ meeting.summary || '无摘要' }}</p>

            <template v-if="meeting.key_points?.length">
              <h4 class="section-title"><el-icon><List /></el-icon>核心要点</h4>
              <ul class="points">
                <li v-for="(p, i) in meeting.key_points" :key="i">{{ p }}</li>
              </ul>
            </template>

            <template v-if="meeting.decisions?.length">
              <h4 class="section-title"><el-icon><Checked /></el-icon>决策事项</h4>
              <ul class="points">
                <li v-for="(d, i) in meeting.decisions" :key="i">{{ d }}</li>
              </ul>
            </template>

            <template v-if="meeting.action_items?.length">
              <h4 class="section-title">
                <el-icon><Finished /></el-icon>行动项 ({{ meeting.action_items.length }})
              </h4>
              <el-table :data="meeting.action_items" stripe size="small">
                <el-table-column prop="task" label="任务" min-width="200" />
                <el-table-column prop="owner" label="负责人" width="100" />
                <el-table-column label="截止" width="110">
                  <template #default="{ row }"><TimeText :value="row.deadline" /></template>
                </el-table-column>
                <el-table-column label="优先级" width="80">
                  <template #default="{ row }">
                    <el-tag :type="priorityType(row.priority) || undefined" size="small">{{ row.priority || '-' }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </template>

            <el-alert v-if="meeting.error_message" :title="meeting.error_message" type="error" :closable="false" style="margin-top: 12px" />
          </div>

          <el-result v-else-if="meeting?.status === 'failed'" icon="error" title="处理失败" :sub-title="meeting?.error_message || '请重试或联系管理员'" />

          <div v-else class="processing">
            <el-progress :percentage="meta.progress" />
            <p class="hint">{{ meta.hint }}</p>
            <el-button size="small" :icon="Refresh" @click="load">刷新状态</el-button>
          </div>
        </el-card>

        <!-- 转写卡片 -->
        <el-card v-if="meeting?.raw_transcript" shadow="never" class="transcript-card">
          <template #header>
            <div class="card-title"><el-icon><ChatLineRound /></el-icon><span>完整转写</span></div>
          </template>
          <div v-if="meeting.segments?.length" class="segments">
            <div v-for="(seg, i) in meeting.segments" :key="i" class="segment">
              <span class="seg-time">{{ formatSegTime(seg.start) }} → {{ formatSegTime(seg.end) }}</span>
              <span class="seg-text">{{ seg.text }}</span>
            </div>
          </div>
          <pre v-else class="transcript">{{ meeting.raw_transcript }}</pre>
        </el-card>
      </el-col>

      <!-- 元信息 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <template #header>
            <div class="card-title"><el-icon><InfoFilled /></el-icon><span>元信息</span></div>
          </template>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="ID">{{ meeting?.id }}</el-descriptions-item>
            <el-descriptions-item label="时长">{{ meeting?.duration ? `${meeting.duration.toFixed(1)} 秒` : '-' }}</el-descriptions-item>
            <el-descriptions-item label="语言">{{ meeting?.language === 'zh' ? '中文' : meeting?.language }}</el-descriptions-item>
            <el-descriptions-item label="音频">{{ meeting?.audio_filename || '-' }}</el-descriptions-item>
            <el-descriptions-item label="ASR 模型">{{ meeting?.asr_model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="LLM 模型">{{ meeting?.llm_model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间"><TimeText :value="meeting?.created_at" /></el-descriptions-item>
            <el-descriptions-item label="完成时间"><TimeText :value="meeting?.completed_at" /></el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Document, List, Checked, Finished, ChatLineRound, InfoFilled, Refresh,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import StatusTag from '@/components/StatusTag.vue'
import TimeText from '@/components/TimeText.vue'
import { getStatusMeta, PRIORITY_TYPE, PROCESSING_STATUSES } from '@/composables/useMeetingStatus'
import type { Meeting } from '@/types'

const route = useRoute()
const meeting = ref<Meeting | null>(null)
const loading = ref(false)
let pollTimer: number | null = null

const meta = computed(() => getStatusMeta(meeting.value?.status))

async function load() {
  loading.value = true
  try {
    meeting.value = await meetingsApi.get(Number(route.params.id))
    if (PROCESSING_STATUSES.includes(meeting.value?.status || '')) {
      if (!pollTimer) pollTimer = window.setInterval(load, 3000)
    } else if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (e: any) {
    ElMessage.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function priorityType(p?: string) {
  return PRIORITY_TYPE[p || ''] || ''
}

function formatSegTime(s: number) {
  if (s == null) return ''
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

watch(() => route.params.id, load)
onMounted(load)
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.detail-page {
  max-width: 1280px;
}
.page-header {
  margin-bottom: 16px;
}
.page-title {
  font-weight: 600;
  font-size: 16px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 20px 0 10px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.points {
  padding-left: 20px;
  margin: 0;
  color: var(--el-text-color-regular);
}
.points li {
  margin-bottom: 6px;
  line-height: 1.6;
}
.summary-text {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  color: var(--el-text-color-regular);
}
.transcript-card {
  margin-top: 16px;
}
.processing {
  text-align: center;
  padding: 24px 0;
}
.hint {
  margin: 12px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.segments {
  max-height: 500px;
  overflow-y: auto;
}
.segment {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  line-height: 1.6;
}
.segment:last-child {
  border-bottom: none;
}
.seg-time {
  flex-shrink: 0;
  color: var(--el-color-primary);
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  padding-top: 1px;
}
.seg-text {
  color: var(--el-text-color-regular);
}
.transcript {
  max-height: 500px;
  overflow-y: auto;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0;
}
</style>
