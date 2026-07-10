<template>
  <div class="upload-page">
    <el-card>
      <template #header>
        <h2>上传会议录音</h2>
      </template>

      <el-form :model="form" label-width="100px" :disabled="uploading">
        <el-form-item label="音频文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 mp3 / wav / m4a / flac，最大 500MB
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="会议标题" required>
          <el-input v-model="form.title" placeholder="例：2026-07 V2.0 需求评审会" />
        </el-form-item>

        <el-form-item label="会议描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="可选"
          />
        </el-form-item>

        <el-form-item label="会议日期">
          <el-date-picker
            v-model="form.meetingDate"
            type="datetime"
            placeholder="可选"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>

        <el-form-item label="音频语言">
          <el-radio-group v-model="form.language">
            <el-radio value="zh">中文</el-radio>
            <el-radio value="en">英文</el-radio>
            <el-radio value="ja">日文</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="LLM 提供商">
          <el-select v-model="form.llmProvider" style="width: 100%">
            <el-option
              v-for="p in providers"
              :key="p.name"
              :label="`${p.display_name} - ${p.model}`"
              :value="p.name"
              :disabled="!p.configured"
            >
              <span style="float: left">{{ p.display_name }}</span>
              <span style="float: right; color: #999; font-size: 12px">
                {{ p.configured ? p.model : '未配置' }}
              </span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="uploading"
            @click="handleSubmit"
            :disabled="!form.title || !file"
          >
            {{ uploading ? '上传中...' : '上传并处理' }}
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="result"
      :title="result.message"
      type="success"
      show-icon
      style="margin-top: 16px"
      :closable="false"
    >
      <template #default>
        会议已创建 (ID: {{ result.meeting_id }})，
        <router-link :to="`/meetings/${result.meeting_id}`">查看处理进度 →</router-link>
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile, UploadInstance } from 'element-plus'
import { ElMessage } from 'element-plus'
import meetingsApi from '@/api/meetings'
import type { LLMProvider, UploadResponse } from '@/types'

const uploadRef = ref<UploadInstance>()
const file = ref<File | null>(null)
const uploading = ref(false)
const result = ref<UploadResponse | null>(null)
const providers = ref<LLMProvider[]>([])

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
}

function handleExceed() {
  ElMessage.warning('只能上传一个文件')
}

async function handleSubmit() {
  if (!file.value || !form.title) {
    ElMessage.warning('请选择文件并填写标题')
    return
  }
  uploading.value = true
  result.value = null
  try {
    result.value = await meetingsApi.upload(file.value, form.title, {
      description: form.description || undefined,
      meetingDate: form.meetingDate || undefined,
      language: form.language,
      llmProvider: form.llmProvider
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
  uploadRef.value?.clearFiles()
  result.value = null
}
</script>

<style scoped>
.upload-page {
  max-width: 800px;
  margin: 0 auto;
}
</style>