<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">办公协同 · Office 中心</span>
        <el-tag v-if="health" size="small" :type="health.ok ? 'success' : 'danger'">
          {{ health.ok ? `oa-agent 在线 · ${health.office_tools.length} 个 office 工具` : 'oa-agent 不可达' }}
        </el-tag>
        <el-button v-else size="small" :loading="loadingHealth" @click="loadHealth">重试</el-button>
      </div>
    </template>

    <div v-if="health && health.ok" class="tools">
      <el-tag v-for="t in health.office_tools" :key="t" size="small" class="tg">{{ t }}</el-tag>
    </div>
    <div v-else-if="health" class="err">{{ health.error }}</div>

    <el-tabs v-model="tab" class="tabs">
      <!-- 文档读取 -->
      <el-tab-pane label="文档读取" name="read">
        <div class="muted">调 oa-agent read_* 工具提取文档文本（md / docx / pdf / excel）。</div>
        <div class="row">
          <el-select v-model="readForm.format" style="width: 120px">
            <el-option value="md" label="md" />
            <el-option value="docx" label="docx" />
            <el-option value="pdf" label="pdf" />
            <el-option value="excel" label="excel" />
          </el-select>
          <el-input v-model="readForm.path" placeholder="文件路径（oa-agent workspace 内）" style="flex: 1" />
          <el-button type="primary" :loading="reading" @click="doRead">读取</el-button>
        </div>
        <div v-if="readResult" class="result">
          <div class="muted">提取结果（{{ readResult.ok ? '成功' : '失败' }}）：</div>
          <pre v-if="readResult.ok">{{ readResult.result?.content ?? JSON.stringify(readResult.result, null, 2) }}</pre>
          <div v-else class="err">{{ readResult.error }}</div>
        </div>
      </el-tab-pane>

      <!-- docx 预览 -->
      <el-tab-pane label="docx 预览" name="preview">
        <div class="muted">docx → HTML 预览（oa-agent docx_to_html / mammoth 渲染，DOMPurify 清洗后展示）。</div>
        <div class="row">
          <el-input v-model="previewPath" placeholder="docx 路径（oa-agent workspace 内）" style="flex: 1" />
          <el-button type="primary" :loading="previewing" @click="doPreview">预览</el-button>
        </div>
        <div v-if="previewError" class="err">{{ previewError }}</div>
        <div v-if="sanitizedPreview" class="preview-box" v-html="sanitizedPreview"></div>
      </el-tab-pane>

      <!-- 模板合并 -->
      <el-tab-pane label="模板合并" name="merge">
        <div class="muted">docx 模板变量填充（oa-agent merge_template / docxtpl），用于订单数据 → 合同等。</div>
        <el-form label-width="78px" style="margin-top: 10px">
          <el-form-item label="模板"><el-input v-model="mergeForm.template" placeholder="含 {{ var }} 占位的 docx 模板路径" /></el-form-item>
          <el-form-item label="输出"><el-input v-model="mergeForm.output" placeholder="输出 docx 路径（oa-agent workspace 内）" /></el-form-item>
          <el-form-item label="变量 JSON">
            <el-input v-model="mergeForm.contextJson" type="textarea" :rows="4" placeholder='{"client":"深圳大华天麓","amount":"￥18,888"}' />
          </el-form-item>
        </el-form>
        <el-button type="primary" :loading="merging" @click="doMerge">合并生成</el-button>
        <div v-if="mergeResult" class="result">
          <div class="muted">合并结果（{{ mergeResult.ok ? '成功' : '失败' }}）：</div>
          <pre>{{ mergeResult.ok ? JSON.stringify(mergeResult.result, null, 2) : mergeResult.error }}</pre>
        </div>
      </el-tab-pane>

      <!-- 表格编辑（Sprint 2 Univer）-->
      <el-tab-pane label="表格编辑" name="sheet">
        <div class="muted">上传 xlsx → Univer Sheets 编辑（本地 SheetJS 解析 → cellData → @univerjs/preset-sheets-core 渲染）。</div>
        <div class="row" style="margin: 10px 0">
          <input type="file" accept=".xlsx,.xls" @change="onXlsxChange" />
          <el-button v-if="sheetData" size="small" @click="sheetData = null">清空</el-button>
        </div>
        <UniverSheet v-if="sheetData" :key="sheetKey" :sheets="sheetData" />
      </el-tab-pane>
    </el-tabs>

    <div class="muted small foot">
      底层链路：admin /api/v1/office/* → oa-agent /tools/{name}（直接调工具，不经 LLM）。
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import * as XLSX from 'xlsx'
import { http, getApiError } from '@/api/admin'
import UniverSheet from '@/components/UniverSheet.vue'

interface OfficeHealth {
  ok: boolean
  oa_agent_url: string
  total_tools: number
  office_tools: string[]
  error?: string
}

interface ToolResult {
  tool: string
  ok: boolean
  error: string | null
  result: {
    content?: string
    html?: string
    output?: string
    keys?: string[]
    error?: string
    [k: string]: unknown
  } | null
}

const health = ref<OfficeHealth | null>(null)
const loadingHealth = ref(false)
const tab = ref('read')

// 文档读取
const readForm = reactive({ format: 'md', path: '' })
const reading = ref(false)
const readResult = ref<ToolResult | null>(null)

// docx 预览
const previewPath = ref('')
const previewing = ref(false)
const previewHtml = ref('')
const previewError = ref('')

// 模板合并
const mergeForm = reactive({
  template: '',
  output: '',
  contextJson: '{\n  "client": "深圳大华天麓",\n  "amount": "￥18,888"\n}',
})
const merging = ref(false)
const mergeResult = ref<ToolResult | null>(null)

// 表格编辑（Sprint 2 Univer）
const sheetData = ref<Record<string, { name?: string; cellData?: Record<number, Record<number, { v: unknown }>> }> | null>(null)
const sheetKey = ref(0)

// mammoth 输出的 html 经 DOMPurify 清洗后再 v-html（防 XSS，项目惯例同 Detail.vue）
const sanitizedPreview = computed(() =>
  previewHtml.value ? DOMPurify.sanitize(previewHtml.value) : '',
)

// xlsx → Univer cellData（SheetJS 解析 + 转 Univer {row:{col:{v}}} 格式）
function onXlsxChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const wb = XLSX.read(reader.result, { type: 'array' })
    const sheets: Record<string, { name?: string; cellData?: Record<number, Record<number, { v: unknown }>> }> = {}
    wb.SheetNames.forEach((name, i) => {
      const ws = wb.Sheets[name]
      const range = XLSX.utils.decode_range(ws['!ref'] || 'A1')
      const cellData: Record<number, Record<number, { v: unknown }>> = {}
      for (let r = range.s.r; r <= range.e.r; r++) {
        for (let c = range.s.c; c <= range.e.c; c++) {
          const cell = ws[XLSX.utils.encode_cell({ r, c })]
          if (cell) (cellData[r] ||= {})[c] = { v: cell.v }
        }
      }
      sheets[`sheet${i + 1}`] = { name, cellData }
    })
    sheetData.value = sheets
    sheetKey.value++
  }
  reader.readAsArrayBuffer(file)
}

async function loadHealth() {
  loadingHealth.value = true
  try {
    const { data } = await http.get<OfficeHealth>('/api/v1/office/health')
    health.value = data
  } catch (e: unknown) {
    health.value = {
      ok: false,
      oa_agent_url: '',
      total_tools: 0,
      office_tools: [],
      error: getApiError(e, '健康检查失败'),
    }
  } finally {
    loadingHealth.value = false
  }
}

async function doRead() {
  if (!readForm.path) {
    ElMessage.warning('请输入路径')
    return
  }
  reading.value = true
  readResult.value = null
  try {
    const { data } = await http.post<ToolResult>('/api/v1/office/read', {
      format: readForm.format,
      path: readForm.path,
    })
    readResult.value = data
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '读取失败'))
  } finally {
    reading.value = false
  }
}

async function doPreview() {
  if (!previewPath.value) {
    ElMessage.warning('请输入 docx 路径')
    return
  }
  previewing.value = true
  previewHtml.value = ''
  previewError.value = ''
  try {
    const { data } = await http.get<ToolResult>('/api/v1/office/preview', {
      params: { path: previewPath.value },
    })
    if (data.ok) {
      previewHtml.value = data.result?.html ?? ''
      if (!previewHtml.value) previewError.value = '预览返回空 html（可能 docx 无文本段落）'
    } else {
      previewError.value = data.error ?? '预览失败'
    }
  } catch (e: unknown) {
    previewError.value = getApiError(e, '预览失败')
  } finally {
    previewing.value = false
  }
}

async function doMerge() {
  let context: Record<string, unknown>
  try {
    context = JSON.parse(mergeForm.contextJson || '{}')
  } catch {
    ElMessage.error('变量 JSON 格式错误')
    return
  }
  if (!mergeForm.template || !mergeForm.output) {
    ElMessage.warning('请填模板与输出路径')
    return
  }
  merging.value = true
  mergeResult.value = null
  try {
    const { data } = await http.post<ToolResult>('/api/v1/office/merge', {
      template: mergeForm.template,
      output: mergeForm.output,
      context,
    })
    mergeResult.value = data
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '合并失败'))
  } finally {
    merging.value = false
  }
}

onMounted(loadHealth)
</script>

<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.tools { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px }
.tg { font-family: monospace }
.tabs { margin-top: 4px }
.muted { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 10px }
.small { font-size: 12px }
.foot { margin-top: 12px; line-height: 1.6 }
.err { color: var(--el-color-danger); font-size: 13px; margin-top: 8px }
.row { display: flex; gap: 8px; align-items: center }
.result { margin-top: 12px }
.result pre {
  background: var(--el-fill-color-light);
  padding: 10px;
  border-radius: 4px;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 13px;
}
.preview-box {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--el-bg-color);
  max-height: 420px;
  overflow: auto;
  line-height: 1.7;
}
.preview-box :deep(p) { margin: 0 0 8px }
</style>
