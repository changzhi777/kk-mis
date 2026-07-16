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

      <!-- 行程攻略（tripgen 服务）-->
      <el-tab-pane label="行程攻略" name="tripgen">
        <div class="muted">调 admin tripgen 服务：载入示例 → 编辑行程 → 预览 HTML → 生成全部 docx/pdf/md 文件。</div>
        <div class="row" style="margin: 10px 0">
          <el-button :loading="tripLoadingExample" @click="loadTripExample">载入示例</el-button>
          <el-button type="primary" :loading="tripPreviewing" @click="doTripPreview">预览</el-button>
          <el-button type="success" :loading="tripGenerating" @click="doTripGenerate">生成全部</el-button>
        </div>
        <el-form label-width="78px">
          <el-form-item label="标题">
            <el-input v-model="tripForm.title" placeholder="如：深圳周边三日游" />
          </el-form-item>
          <el-form-item label="副标题">
            <el-input v-model="tripForm.subtitle" placeholder="可选，如：深度探索大鹏半岛" />
          </el-form-item>
          <el-form-item label="出发地">
            <el-input v-model="tripForm.origin" placeholder="如：深圳" />
          </el-form-item>
          <el-form-item label="出行人">
            <el-input v-model="tripForm.party" placeholder="如：2 大 1 小" />
          </el-form-item>
          <el-form-item label="日期">
            <el-input v-model="tripForm.dates" placeholder="如：2026-08-01 ~ 2026-08-03" />
          </el-form-item>
          <el-form-item label="日程">
            <div class="trip-days">
              <div v-for="(day, i) in tripForm.days" :key="i" class="trip-day">
                <el-input v-model="day.title" :placeholder="'第 ' + (i + 1) + ' 天标题'" style="width: 180px" />
                <el-input v-model="day.desc" placeholder="当日描述（景点/餐饮/住宿）" style="flex: 1; margin-left: 8px" />
                <el-button size="small" type="danger" plain @click="tripForm.days.splice(i, 1)" style="margin-left: 8px">删</el-button>
              </div>
              <el-button size="small" @click="tripForm.days.push({ title: '', desc: '' })">+ 加一天</el-button>
            </div>
          </el-form-item>
          <el-form-item label="景点">
            <el-select
              v-model="tripForm.attractions"
              multiple
              filterable
              allow-create
              default-first-option
              :reserve-key="false"
              placeholder="输入景点后回车，如：大梅沙 / 东部华侨城"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
        <div v-if="tripPreviewHtml" class="result">
          <div class="muted">预览：</div>
          <iframe :srcdoc="tripPreviewHtml" class="trip-frame"></iframe>
        </div>
        <div v-if="tripFiles.length" class="result">
          <div class="muted">生成文件（{{ tripFiles.length }}）：</div>
          <pre>{{ tripFiles.join('\n') }}</pre>
        </div>
      </el-tab-pane>

      <!-- 终端（快捷命令面板）-->
      <el-tab-pane label="终端" name="terminal">
        <div class="muted">快捷命令面板：本地 office 引擎直接生成文件（绕过 oa-agent，调 admin /api/v1/office/{pdf,excel,pptx,form,batch}，权限 office:tool:invoke）。</div>
        <div class="term-grid">
          <el-button type="primary" plain @click="openTerm('pdf')">PDF 转换</el-button>
          <el-button type="success" plain @click="openTerm('excel')">Excel 导出</el-button>
          <el-button type="warning" plain @click="openTerm('pptx')">PPT 生成</el-button>
          <el-button type="info" plain @click="openTerm('form')">表单填写</el-button>
          <el-button @click="openTerm('batch')">批量处理</el-button>
        </div>
        <div v-if="termLog" class="result">
          <div class="muted">最近结果：</div>
          <pre>{{ termLog }}</pre>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 终端命令 dialog 群（el-dialog 默认 teleport 到 body，不影响 tabs 布局）-->
    <el-dialog v-model="showPdfDlg" title="PDF 转换" width="480px">
      <div class="muted">上传 docx 或 html 文件 → PDF（mammoth + weasyprint，仅 .docx / .html / .htm）。</div>
      <div class="row" style="margin: 12px 0">
        <input type="file" accept=".docx,.html,.htm" @change="onPickFile($event, pdfForm)" />
      </div>
      <template #footer>
        <el-button @click="showPdfDlg = false">取消</el-button>
        <el-button type="primary" :loading="termBusy" @click="runPdf">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showExcelDlg" title="Excel 导出" width="560px">
      <div class="muted">JSON 二维数组或 dict 列表 → xlsx（openpyxl）。</div>
      <el-form label-width="82px" style="margin-top: 10px">
        <el-form-item label="工作表名">
          <el-input v-model="excelForm.sheetName" style="width: 160px" />
        </el-form-item>
        <el-form-item label="表头（可选）">
          <el-input v-model="excelForm.headers" placeholder='["姓名","年龄"]' />
        </el-form-item>
        <el-form-item label="数据 JSON">
          <el-input v-model="excelForm.dataJson" type="textarea" :rows="5" placeholder='[{"name":"张三","age":28}]' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExcelDlg = false">取消</el-button>
        <el-button type="primary" :loading="termBusy" @click="runExcel">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPptxDlg" title="PPT 生成" width="560px">
      <div class="muted">JSON slides → pptx（python-pptx）。</div>
      <el-form label-width="82px" style="margin-top: 10px">
        <el-form-item label="模板路径">
          <el-input v-model="pptxForm.template" placeholder="可选 pptx 模板路径（服务端本地路径）" />
        </el-form-item>
        <el-form-item label="幻灯片 JSON">
          <el-input v-model="pptxForm.slidesJson" type="textarea" :rows="6" placeholder='[{"title":"第一页","content":"..."}]' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPptxDlg = false">取消</el-button>
        <el-button type="primary" :loading="termBusy" @click="runPptx">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showFormDlg" title="表单填写" width="520px">
      <div class="muted">上传含变量占位的 docx 模板 + JSON 变量 → 填充后 docx（docxtpl）。</div>
      <div class="row" style="margin: 12px 0">
        <input type="file" accept=".docx" @change="onPickFile($event, formForm)" />
      </div>
      <el-form label-width="82px">
        <el-form-item label="变量 JSON">
          <el-input v-model="formForm.dataJson" type="textarea" :rows="5" placeholder='{"party_a":"大华"}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormDlg = false">取消</el-button>
        <el-button type="primary" :loading="termBusy" @click="runForm">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatchDlg" title="批量处理" width="520px">
      <div class="muted">文件夹批量处理（pdf / form / copy），返回处理结果路径列表。</div>
      <el-form label-width="82px" style="margin-top: 10px">
        <el-form-item label="输入目录">
          <el-input v-model="batchForm.inputDir" placeholder="服务端本地路径（如 /data/docs）" />
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="batchForm.operation" style="width: 140px">
            <el-option value="pdf" label="pdf" />
            <el-option value="form" label="form" />
            <el-option value="copy" label="copy" />
          </el-select>
        </el-form-item>
        <el-form-item label="输出目录">
          <el-input v-model="batchForm.outputDir" placeholder="可选，缺省在输入目录下 output_<op>" />
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-input v-model="batchForm.pattern" style="width: 140px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchDlg = false">取消</el-button>
        <el-button type="primary" :loading="termBusy" @click="runBatch">执行</el-button>
      </template>
    </el-dialog>

    <div class="muted small foot">
      底层链路：admin /api/v1/office/* → oa-agent /tools/{name}（直接调工具，不经 LLM）。
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { AxiosResponse } from 'axios'
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

// 终端（快捷命令面板）— 本地 office 引擎 5 个端点
type TermKind = 'pdf' | 'excel' | 'pptx' | 'form' | 'batch'
const termBusy = ref(false)
const termLog = ref('')
const showPdfDlg = ref(false)
const showExcelDlg = ref(false)
const showPptxDlg = ref(false)
const showFormDlg = ref(false)
const showBatchDlg = ref(false)

const pdfForm = reactive<{ file: File | null }>({ file: null })
const excelForm = reactive({
  dataJson: '[\n  {"name":"张三","age":28},\n  {"name":"李四","age":35}\n]',
  headers: '',
  sheetName: 'Sheet1',
})
const pptxForm = reactive({
  slidesJson: '[\n  {"title":"深圳大华天麓","content":"2026 Q3 业绩概览"},\n  {"title":"关键指标","content":"GMV / 客单价 / 续费率"}\n]',
  template: '',
})
const formForm = reactive<{ file: File | null; dataJson: string }>({
  file: null,
  dataJson: '{\n  "party_a": "深圳大华天麓",\n  "amount": "￥18,888"\n}',
})
const batchForm = reactive({
  inputDir: '',
  operation: 'pdf' as 'pdf' | 'form' | 'copy',
  outputDir: '',
  pattern: '*',
})

function openTerm(kind: TermKind) {
  termLog.value = ''
  if (kind === 'pdf') showPdfDlg.value = true
  else if (kind === 'excel') showExcelDlg.value = true
  else if (kind === 'pptx') showPptxDlg.value = true
  else if (kind === 'form') showFormDlg.value = true
  else if (kind === 'batch') showBatchDlg.value = true
}

function onPickFile(e: Event, target: { file: File | null }) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) target.file = f
}

function parseJsonSafe<T>(s: string, label: string): T | null {
  try {
    return JSON.parse(s) as T
  } catch {
    ElMessage.error(`${label} JSON 格式错误`)
    return null
  }
}

// 下载 office 端点返回的 FileResponse（参考 admin.ts::downloadCsv）
async function downloadOfficeFile(resp: AxiosResponse<Blob>, fallback: string) {
  const cd = String(resp.headers['content-disposition'] ?? '')
  const filename = (cd.match(/filename="?([^";]+)"?/) || [, fallback])[1]
  const url = URL.createObjectURL(new Blob([resp.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = decodeURIComponent(filename)
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

async function runPdf() {
  if (!pdfForm.file) {
    ElMessage.warning('请选择 docx 或 html 文件')
    return
  }
  termBusy.value = true
  try {
    const fd = new FormData()
    fd.append('file', pdfForm.file)
    const resp = await http.post('/api/v1/office/pdf', fd, {
      responseType: 'blob',
    })
    await downloadOfficeFile(resp as AxiosResponse<Blob>, 'converted.pdf')
    termLog.value = `PDF 转换成功，文件已下载。`
    showPdfDlg.value = false
  } catch (e: unknown) {
    termLog.value = `失败：${getApiError(e, 'PDF 转换失败')}`
  } finally {
    termBusy.value = false
  }
}

async function runExcel() {
  const data = parseJsonSafe<unknown[]>(excelForm.dataJson, '数据')
  if (data === null) return
  termBusy.value = true
  try {
    const body: Record<string, unknown> = { data, sheet_name: excelForm.sheetName }
    if (excelForm.headers) {
      const hs = parseJsonSafe<string[]>(excelForm.headers, '表头')
      if (hs === null) return
      body.headers = hs
    }
    const resp = await http.post('/api/v1/office/excel', body, {
      responseType: 'blob',
    })
    await downloadOfficeFile(resp as AxiosResponse<Blob>, 'data.xlsx')
    termLog.value = `Excel 生成成功，文件已下载。`
    showExcelDlg.value = false
  } catch (e: unknown) {
    termLog.value = `失败：${getApiError(e, 'Excel 生成失败')}`
  } finally {
    termBusy.value = false
  }
}

async function runPptx() {
  const slides = parseJsonSafe<Array<{ title?: string; content?: string; layout?: string }>>(
    pptxForm.slidesJson,
    '幻灯片',
  )
  if (slides === null) return
  termBusy.value = true
  try {
    const body: Record<string, unknown> = { slides }
    if (pptxForm.template) body.template = pptxForm.template
    const resp = await http.post('/api/v1/office/pptx', body, {
      responseType: 'blob',
    })
    await downloadOfficeFile(resp as AxiosResponse<Blob>, 'report.pptx')
    termLog.value = `PPT 生成成功，文件已下载。`
    showPptxDlg.value = false
  } catch (e: unknown) {
    termLog.value = `失败：${getApiError(e, 'PPT 生成失败')}`
  } finally {
    termBusy.value = false
  }
}

async function runForm() {
  if (!formForm.file) {
    ElMessage.warning('请选择 docx 模板')
    return
  }
  const data = parseJsonSafe<Record<string, unknown>>(formForm.dataJson, '变量')
  if (data === null) return
  termBusy.value = true
  try {
    const fd = new FormData()
    fd.append('file', formForm.file)
    fd.append('data', JSON.stringify(data))
    const resp = await http.post('/api/v1/office/form', fd, {
      responseType: 'blob',
    })
    await downloadOfficeFile(resp as AxiosResponse<Blob>, 'filled.docx')
    termLog.value = `表单填写成功，文件已下载。`
    showFormDlg.value = false
  } catch (e: unknown) {
    termLog.value = `失败：${getApiError(e, '表单填写失败')}`
  } finally {
    termBusy.value = false
  }
}

interface BatchResult {
  operation: string
  input_dir: string
  output_dir: string
  processed: string[]
  count: number
}

async function runBatch() {
  if (!batchForm.inputDir) {
    ElMessage.warning('请填输入目录')
    return
  }
  termBusy.value = true
  try {
    const body: Record<string, unknown> = {
      input_dir: batchForm.inputDir,
      operation: batchForm.operation,
      pattern: batchForm.pattern,
    }
    if (batchForm.outputDir) body.output_dir = batchForm.outputDir
    const { data } = await http.post<BatchResult>('/api/v1/office/batch', body)
    termLog.value = `批量 ${data.operation} 完成：${data.count} 个文件
输出目录：${data.output_dir}
${data.processed.join('\n')}`
    showBatchDlg.value = false
  } catch (e: unknown) {
    termLog.value = `失败：${getApiError(e, '批量处理失败')}`
  } finally {
    termBusy.value = false
  }
}

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

// 行程攻略（tripgen）— GET /example 预填 / POST /preview HTML / POST /generate 文件列表
interface TripDay {
  title: string
  desc: string
}
interface TripPayload {
  title: string
  subtitle?: string
  origin?: string
  party?: string
  dates?: string
  days: TripDay[]
  attractions: string[]
}
interface TripPreviewResp {
  html: string
}
interface TripGenerateResp {
  files: string[]
}

const tripLoadingExample = ref(false)
const tripPreviewing = ref(false)
const tripGenerating = ref(false)
const tripPreviewHtml = ref('')
const tripFiles = ref<string[]>([])
const tripForm = reactive<TripPayload>({
  title: '',
  subtitle: '',
  origin: '',
  party: '',
  dates: '',
  days: [],
  attractions: [],
})

// 兼容 {trip:{...}} 包裹或直接 Trip 对象两种响应
function applyTripExample(data: unknown) {
  const obj = (data || {}) as { trip?: TripPayload } & Partial<TripPayload>
  const trip = obj.trip || obj
  tripForm.title = trip.title || ''
  tripForm.subtitle = trip.subtitle || ''
  tripForm.origin = trip.origin || ''
  tripForm.party = trip.party || ''
  tripForm.dates = trip.dates || ''
  tripForm.days = Array.isArray(trip.days)
    ? trip.days.map((d) => ({ title: d.title || '', desc: d.desc || '' }))
    : []
  tripForm.attractions = Array.isArray(trip.attractions) ? [...trip.attractions] : []
}

async function loadTripExample() {
  tripLoadingExample.value = true
  try {
    const { data } = await http.get('/api/v1/tripgen/example')
    applyTripExample(data)
    tripPreviewHtml.value = ''
    tripFiles.value = []
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '载入示例失败'))
  } finally {
    tripLoadingExample.value = false
  }
}

async function doTripPreview() {
  if (!tripForm.title) {
    ElMessage.warning('请填标题或先载入示例')
    return
  }
  tripPreviewing.value = true
  tripPreviewHtml.value = ''
  try {
    const { data } = await http.post<TripPreviewResp>('/api/v1/tripgen/preview', tripForm)
    tripPreviewHtml.value = data.html || ''
    if (!tripPreviewHtml.value) ElMessage.warning('预览返回空 HTML')
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '预览失败'))
  } finally {
    tripPreviewing.value = false
  }
}

async function doTripGenerate() {
  if (!tripForm.title) {
    ElMessage.warning('请填标题或先载入示例')
    return
  }
  tripGenerating.value = true
  tripFiles.value = []
  try {
    const { data } = await http.post<TripGenerateResp>('/api/v1/tripgen/generate', tripForm)
    tripFiles.value = data.files || []
    ElMessage.success(`生成 ${tripFiles.value.length} 个文件`)
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '生成失败'))
  } finally {
    tripGenerating.value = false
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
.term-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 10px 0 4px;
}
.trip-days { display: flex; flex-direction: column; gap: 8px; width: 100% }
.trip-day { display: flex; align-items: center }
.trip-frame {
  width: 100%;
  height: 420px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: #fff;
}
</style>
