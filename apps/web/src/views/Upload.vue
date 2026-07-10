<template>
  <div class="upload-page">
    <el-card class="card-section" shadow="never">
      <template #header>
        <div class="card-title"><el-icon><UploadFilled /></el-icon><span>上传会议录音</span></div>
      </template>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-exceed="() => ElMessage.warning('只能上传一个文件')"
        drag
        class="uploader"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">将音频文件拖到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="upload-tip">支持 mp3 / wav / m4a / flac，最大 {{ maxMb }}MB</div>
        </template>
      </el-upload>
      <div v-if="file" class="file-info">
        <el-icon><Document /></el-icon>
        <span class="file-name">{{ file.name }}</span>
        <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }} MB</span>
      </div>
    </el-card>

    <el-card class="card-section" shadow="never">
      <template #header><div class="card-title"><span>会议信息</span></div></template>
      <el-form :model="form" label-width="80px" label-position="right" :disabled="uploading">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="例：2026-07 V2.0 需求评审会" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.meetingDate" type="datetime" placeholder="可选" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" maxlength="2000" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="card-section" shadow="never">
      <template #header><div class="card-title"><span>处理选项</span></div></template>
      <el-form :model="form" label-width="80px" :disabled="uploading">
        <el-form-item label="语言">
          <el-radio-group v-model="form.language">
            <el-radio value="zh">中文</el-radio>
            <el-radio value="en">英文</el-radio>
            <el-radio value="ja">日文</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="AI 模型">
          <el-select v-model="form.llmProvider" style="width: 100%">
            <el-option v-for="p in providers" :key="p.name" :label="p.display_name" :value="p.name" :disabled="!p.configured">
              <span style="float: left">{{ p.display_name }}</span>
              <span style="float: right; color: var(--el-text-color-secondary); font-size: 12px">{{ p.configured ? p.model : '未配置' }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="uploading" :disabled="!form.title || !file" @click="handleSubmit">
            {{ uploading ? '上传中...' : '上传并处理' }}
          </el-button>
          <el-button @click="handleReset" :disabled="uploading">重置</el-button>
        </el-form-item>
      </el-form>

      <el-progress v-if="uploading && uploadPercent > 0" :percentage="uploadPercent" :stroke-width="6" style="margin-top: 4px" />
    </el-card>

    <el-alert v-if="result" :title="result.message" type="success" show-icon :closable="false" class="result-alert">
      <template #default>
        会议已创建 (ID: {{ result.meeting_id }})，
        <router-link :to="`/meetings/${result.meeting_id}`">查看处理进度 →</router-link>
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { UploadFilled, Document } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import type { LLMProvider, UploadResponse } from '@/types'

const uploadRef = ref<UploadInstance>()
const file = ref<File | null>(null)
const uploading = ref(false)
const uploadPercent = ref(0)
const result = ref<UploadResponse | null>(null)
const providers = ref<LLMProvider[]>([])
const maxMb = 500

const form = reactive({
  title: '',
  description: '',
  meetingDate: '',
  language: 'zh',
  llmProvider: 'glm'
})

onMounted(async () => {
  try {
    providers.value = await meetingsApi.listProviders()
  } catch (e) {
    console.error(e)
  }
})

function handleFileChange(uploadFile: UploadFile) {
  file.value = uploadFile.raw || null
  uploadPercent.value = 0
}

async function handleSubmit() {
  if (!file.value || !form.title) {
    ElMessage.warning('请选择文件并填写标题')
    return
  }
  uploading.value = true
  result.value = null
  uploadPercent.value = 0
  try {
    result.value = await meetingsApi.upload(file.value, form.title, {
      description: form.description || undefined,
      meetingDate: form.meetingDate || undefined,
      language: form.language,
      llmProvider: form.llmProvider,
      onProgress: (p) => {
        uploadPercent.value = p
      }
    })
    ElMessage.success('上传成功，处理已启动')
  } catch (e: any) {
    ElMessage.error(`上传失败：${e.message}`)
  } finally {
    uploading.value = false
  }
}

function handleReset() {
  form.title = ''
  form.description = ''
  form.meetingDate = ''
  file.value = null
  uploadPercent.value = 0
  uploadRef.value?.clearFiles()
  result.value = null
}
</script>

<style scoped>
.upload-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.uploader {
  width: 100%;
}
.uploader :deep(.el-upload-dragger) {
  padding: 32px 20px;
  border-radius: 8px;
  transition: border-color 0.2s;
}
.upload-icon {
  font-size: 40px;
  color: var(--el-color-primary);
  margin-bottom: 8px;
}
.upload-text {
  color: var(--el-text-color-regular);
  font-size: 14px;
}
.upload-text em {
  color: var(--el-color-primary);
  font-style: normal;
}
.upload-tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 6px;
}
.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 13px;
}
.file-name {
  color: var(--el-text-color-primary);
  flex: 1;
}
.file-size {
  color: var(--el-text-color-secondary);
}
.result-alert {
  margin-top: 4px;
}
</style>
