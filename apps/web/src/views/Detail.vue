<template>
  <div class="detail-page" v-loading="loading">
    <el-page-header @back="$router.back()" :title="'返回'" style="margin-bottom: 16px">
      <template #content>
        <span class="page-title">{{ meeting?.title || '加载中...' }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="16">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>📋 会议摘要</span>
              <el-tag v-if="meeting" :type="statusType(meeting.status)" size="small">
                {{ statusText(meeting.status) }}
              </el-tag>
            </div>
          </template>

          <div v-if="meeting?.status === 'completed'">
            <p class="summary-text">{{ meeting.summary || '无摘要' }}</p>

            <template v-if="meeting.key_points?.length">
              <h4>核心要点</h4>
              <ul class="points">
                <li v-for="(p, i) in meeting.key_points" :key="i">{{ p }}</li>
              </ul>
            </template>

            <template v-if="meeting.decisions?.length">
              <h4>决策事项</h4>
              <ul class="points">
                <li v-for="(d, i) in meeting.decisions" :key="i">{{ d }}</li>
              </ul>
            </template>

            <template v-if="meeting.action_items?.length">
              <h4>行动项 ({{ meeting.action_items.length }})</h4>
              <el-table :data="meeting.action_items" stripe size="small">
                <el-table-column prop="task" label="任务" min-width="200" />
                <el-table-column prop="owner" label="负责人" width="100" />
                <el-table-column prop="deadline" label="截止日期" width="120" />
                <el-table-column label="优先级" width="80">
                  <template #default="{ row }">
                    <el-tag :type="priorityType(row.priority)" size="small">
                      {{ row.priority || '-' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </template>

            <template v-if="meeting.error_message">
              <el-alert :title="meeting.error_message" type="error" :closable="false" />
            </template>
          </div>

          <el-empty v-else-if="meeting?.status === 'failed'" description="处理失败" />
          <div v-else class="processing">
            <el-progress :percentage="progressValue(meeting?.status)" />
            <p class="hint">{{ statusHint(meeting?.status) }}</p>
            <el-button size="small" @click="load">刷新状态</el-button>
          </div>
        </el-card>

        <el-card style="margin-top: 16px" v-if="meeting?.raw_transcript">
          <template #header><span>📝 完整转写</span></template>
          <pre class="transcript">{{ meeting.raw_transcript }}</pre>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header><span>📊 元信息</span></template>
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="ID">{{ meeting?.id }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ statusText(meeting?.status || '') }}</el-descriptions-item>
            <el-descriptions-item label="时长">
              {{ meeting?.duration ? `${meeting.duration.toFixed(1)} 秒` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="语言">
              {{ meeting?.language === 'zh' ? '中文' : meeting?.language }}
            </el-descriptions-item>
            <el-descriptions-item label="音频">
              {{ meeting?.audio_filename || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="ASR 模型">
              {{ meeting?.asr_model || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="LLM 模型">
              {{ meeting?.llm_model || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ meeting?.created_at ? new Date(meeting.created_at).toLocaleString('zh-CN') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ meeting?.completed_at ? new Date(meeting.completed_at).toLocaleString('zh-CN') : '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import type { Meeting } from '@/types'

const route = useRoute()
const meeting = ref<Meeting | null>(null)
const loading = ref(false)
let pollTimer: number | null = null

async function load() {
  loading.value = true
  try {
    meeting.value = await meetingsApi.get(Number(route.params.id))
    // 处理中则轮询
    if (['uploaded', 'transcribing', 'transcribed', 'summarizing'].includes(meeting.value?.status || '')) {
      if (!pollTimer) {
        pollTimer = window.setInterval(load, 3000)
      }
    } else {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }
  } catch (e: any) {
    ElMessage.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function statusText(s: string): string {
  return {
    uploaded: '已上传', transcribing: '转写中', transcribed: '已转写',
    summarizing: '整理中', completed: '已完成', failed: '失败'
  }[s] || s
}

function statusType(s: string): string {
  return {
    uploaded: 'info', transcribing: 'warning', transcribed: 'warning',
    summarizing: 'warning', completed: 'success', failed: 'danger'
  }[s] || ''
}

function statusHint(s: string | undefined): string {
  return {
    uploaded: '等待 ASR 处理...',
    transcribing: '正在转写音频（Mac 本地 MLX Whisper）...',
    transcribed: '转写完成，正在整理纪要...',
    summarizing: 'LLM 正在整理会议纪要...'
  }[s || ''] || ''
}

function progressValue(s: string | undefined): number {
  return {
    uploaded: 10, transcribing: 40, transcribed: 70, summarizing: 85, completed: 100, failed: 0
  }[s || ''] || 0
}

function priorityType(p?: string): string {
  return { P0: 'danger', P1: 'warning', P2: 'info' }[p || ''] || ''
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.detail-page {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  font-weight: 600;
  font-size: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.summary-text {
  font-size: 15px;
  line-height: 1.8;
  white-space: pre-wrap;
}
.points {
  padding-left: 20px;
}
.points li {
  margin-bottom: 8px;
}
.transcript {
  max-height: 500px;
  overflow-y: auto;
  background: #fafafa;
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.processing {
  text-align: center;
  padding: 24px 0;
}
.hint {
  margin: 12px 0;
  color: #999;
}
h4 {
  margin-top: 20px;
  margin-bottom: 8px;
  color: #303133;
}
</style>