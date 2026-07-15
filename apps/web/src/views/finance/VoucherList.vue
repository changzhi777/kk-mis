<template>
  <el-card shadow="never">
    <template #header>
      <span class="ct">记账凭证（复式记账）</span>
      <el-button type="primary" size="small" style="float: right" @click="openNew">新建凭证</el-button>
    </template>
    <el-table :data="items" v-loading="loading" stripe size="small">
      <el-table-column prop="number" label="凭证号" width="160" />
      <el-table-column label="日期" width="110">
        <template #default="{ row }">{{ row.voucher_date?.slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" />
      <el-table-column label="分录">
        <template #default="{ row }">
          <span v-for="(e, i) in row.entries" :key="i" class="entry">
            {{ accountName(e.account_id) }}{{ e.debit ? ` 借${e.debit}` : '' }}{{ e.credit ? ` 贷${e.credit}` : '' }};
          </span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'posted' ? 'success' : 'info'">{{ row.status === 'posted' ? '已过账' : '草稿' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.status === 'draft'" link type="primary" @click="post(row.id)">过账</el-button>
          <el-button link type="primary" @click="print(row)">打印</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dv" title="新建凭证（复式·借贷平衡）" width="720">
      <el-form label-width="60px">
        <el-form-item label="日期">
          <el-date-picker v-model="form.voucher_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 220px" />
        </el-form-item>
        <el-form-item label="摘要"><el-input v-model="form.summary" /></el-form-item>
      </el-form>
      <div class="muted">分录（借方合计必须等于贷方合计）</div>
      <el-table :data="form.entries" size="small" border>
        <el-table-column label="科目" min-width="220">
          <template #default="{ row }">
            <el-select v-model="row.account_id" placeholder="选科目" size="small">
              <el-option v-for="a in accounts" :key="a.id" :label="a.name" :value="a.id" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="借方" width="130">
          <template #default="{ row }"><el-input-number v-model="row.debit" :min="0" :controls="false" size="small" style="width: 110px" /></template>
        </el-table-column>
        <el-table-column label="贷方" width="130">
          <template #default="{ row }"><el-input-number v-model="row.credit" :min="0" :controls="false" size="small" style="width: 110px" /></template>
        </el-table-column>
        <el-table-column label="删" width="50">
          <template #default="{ $index }"><el-button link type="danger" size="small" @click="form.entries.splice($index, 1)">✕</el-button></template>
        </el-table-column>
      </el-table>
      <div class="bal">
        <el-button size="small" @click="form.entries.push({ account_id: null, debit: 0, credit: 0 })">+ 加分录</el-button>
        <span>借方合计 ¥{{ debitSum }} ｜ 贷方合计 ¥{{ creditSum }}</span>
        <el-tag size="small" :type="balanced ? 'success' : 'danger'">{{ balanced ? '借贷平衡' : '不平' }}</el-tag>
      </div>
      <template #footer>
        <el-button @click="dv = false">取消</el-button>
        <el-button type="primary" :disabled="!balanced" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <VoucherPrint v-model="printVisible" :voucher="printVoucher" :accounts="accounts" />
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError, http } from '@/api/admin'
import VoucherPrint from '@/components/VoucherPrint.vue'

const items = ref<{ id: number; number: string; voucher_date: string; status: string; entries: { account_id: number; debit: number; credit: number }[] }[]>([])
const accounts = ref<{ id: number; name: string }[]>([])
const loading = ref(false)
const dv = ref(false)
const form = reactive<{ voucher_date: string; summary: string; entries: { account_id: number | null; debit: number; credit: number }[] }>({
  voucher_date: '',
  summary: '',
  entries: [],
})

const debitSum = computed(() => form.entries.reduce((s, e) => s + (Number(e.debit) || 0), 0))
const creditSum = computed(() => form.entries.reduce((s, e) => s + (Number(e.credit) || 0), 0))
const balanced = computed(() => form.entries.length >= 2 && debitSum.value === creditSum.value && debitSum.value > 0)

function accountName(id: number) {
  return accounts.value.find((a) => a.id === id)?.name || `账户${id}`
}

async function load() {
  loading.value = true
  try {
    items.value = await adminApi.listVouchers()
    accounts.value = (await http.get<{ items: { id: number; name: string }[] }>('/api/v1/finance/accounts')).data.items
  } finally {
    loading.value = false
  }
}

function openNew() {
  form.voucher_date = new Date().toISOString().replace(/\.\d+Z$/, '')
  form.summary = ''
  form.entries = [
    { account_id: null, debit: 0, credit: 0 },
    { account_id: null, debit: 0, credit: 0 },
  ]
  dv.value = true
}

async function save() {
  try {
    const r = await adminApi.createVoucher(form as never)
    ElMessage.success(`凭证 ${r.number} 已创建（${r.status}）`)
    dv.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '创建失败'))
  }
}

async function post(id: number) {
  try {
    await adminApi.postVoucher(id)
    ElMessage.success('已过账')
    await load()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '过账失败'))
  }
}

// 打印凭证
const printVoucher = ref<{ id: number; number: string; voucher_date: string; summary: string; entries: { account_id: number; debit: number; credit: number }[] } | null>(null)
const printVisible = ref(false)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function print(row: any) {
  printVoucher.value = row
  printVisible.value = true
}

onMounted(load)
</script>

<style scoped>
.ct { font-weight: 600; }
.entry { display: inline-block; margin-right: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.muted { color: var(--el-text-color-secondary); margin: 8px 0; font-size: 13px; }
.bal { margin-top: 10px; display: flex; align-items: center; gap: 12px; }
</style>
