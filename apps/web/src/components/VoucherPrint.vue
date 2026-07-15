<template>
  <el-dialog v-model="visible" :title="`记账凭证 · ${voucher?.number || ''}`" width="820">
    <div ref="printArea" class="voucher-a4">
      <div class="vp-header">
        <h2>记 账 凭 证</h2>
        <div class="vp-meta">
          <span>凭证编号：{{ voucher?.number }}</span>
          <span>日期：{{ voucher?.voucher_date?.slice(0, 10) }}</span>
          <span>第 {{ voucher?.id }} 号</span>
        </div>
      </div>
      <table class="vp-table">
        <thead>
          <tr>
            <th class="col-summary">摘要</th>
            <th class="col-account">会计科目</th>
            <th class="col-amt">借方金额</th>
            <th class="col-amt">贷方金额</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(e, i) in entries" :key="i">
            <td>{{ voucher?.summary }}</td>
            <td>{{ accountName(e.account_id) }}</td>
            <td class="amt">{{ e.debit > 0 ? formatMoney(e.debit) : '' }}</td>
            <td class="amt">{{ e.credit > 0 ? formatMoney(e.credit) : '' }}</td>
          </tr>
          <tr v-for="n in emptyRows" :key="'e' + n" class="empty-row">
            <td>&nbsp;</td><td></td><td></td><td></td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="2" class="total-label">合 计</td>
            <td class="amt total">{{ formatMoney(debitTotal) }}</td>
            <td class="amt total">{{ formatMoney(creditTotal) }}</td>
          </tr>
        </tfoot>
      </table>
      <div class="vp-foot">
        <span>制单：____________</span>
        <span>审核：____________</span>
        <span>出纳：____________</span>
        <span>记账：____________</span>
      </div>
      <div class="vp-attach">附件 {{ voucher?.attachment_count || 0 }} 张</div>
    </div>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="doPrint">🖨 打印</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// 记账凭证 A4 打印组件（CSS @media print + window.print 新窗口）
import { computed, ref } from 'vue'

interface VoucherData {
  id: number
  number: string
  voucher_date: string
  summary: string
  attachment_count?: number
  entries: { account_id: number; debit: number; credit: number }[]
}

const props = defineProps<{
  modelValue: boolean
  voucher: VoucherData | null
  accounts: { id: number; name: string }[]
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()

const visible = ref(props.modelValue)
const printArea = ref<HTMLElement | null>(null)

const entries = computed(() => props.voucher?.entries || [])
const debitTotal = computed(() => entries.value.reduce((s, e) => s + (Number(e.debit) || 0), 0))
const creditTotal = computed(() => entries.value.reduce((s, e) => s + (Number(e.credit) || 0), 0))
const emptyRows = computed(() => Math.max(0, 5 - entries.value.length))

function accountName(id: number) {
  return props.accounts.find((a) => a.id === id)?.name || `账户${id}`
}

function formatMoney(n: number) {
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function doPrint() {
  const area = printArea.value
  if (!area) return
  const html = area.outerHTML
  const w = window.open('', '_blank', 'width=820,height=900')
  if (!w) return
  w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${props.voucher?.number || '记账凭证'}</title>
  <style>
    body { font-family: "SimSun", "FangSong", serif; margin: 30px; color: #000; }
    .voucher-a4 { max-width: 700px; margin: 0 auto; }
    .vp-header { text-align: center; margin-bottom: 16px; }
    .vp-header h2 { font-size: 22px; letter-spacing: 8px; margin: 0 0 8px; }
    .vp-meta { display: flex; justify-content: space-between; font-size: 13px; }
    .vp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .vp-table th, .vp-table td { border: 1px solid #000; padding: 6px 8px; text-align: left; }
    .vp-table th { background: #f5f5f5; text-align: center; }
    .col-summary { width: 30%; } .col-account { width: 30%; } .col-amt { width: 20%; text-align: right; }
    .amt { text-align: right; font-family: "Times New Roman", serif; }
    .empty-row td { height: 28px; }
    .total-label { text-align: center; font-weight: bold; }
    .total { font-weight: bold; }
    .vp-foot { display: flex; justify-content: space-between; margin-top: 24px; font-size: 13px; }
    .vp-attach { margin-top: 12px; font-size: 12px; color: #666; }
    @media print { body { margin: 0; } @page { size: A4; margin: 1.5cm; } }
  </style></head><body>${html}</body></html>`)
  w.document.close()
  w.focus()
  setTimeout(() => { w.print(); w.close() }, 300)
}
</script>

<style scoped>
.voucher-a4 { max-width: 720px; margin: 0 auto; }
.vp-header { text-align: center; margin-bottom: 16px; }
.vp-header h2 { font-size: 20px; letter-spacing: 6px; margin: 0 0 8px; }
.vp-meta { display: flex; justify-content: space-between; font-size: 13px; color: var(--el-text-color-secondary); }
.vp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.vp-table th, .vp-table td { border: 1px solid var(--el-border-color); padding: 6px 8px; }
.vp-table th { background: var(--el-fill-color-light); text-align: center; }
.col-amt { text-align: right; }
.amt { text-align: right; font-family: "Courier New", monospace; }
.empty-row td { height: 28px; }
.total-label { text-align: center; font-weight: bold; }
.total { font-weight: bold; }
.vp-foot { display: flex; justify-content: space-between; margin-top: 24px; font-size: 13px; color: var(--el-text-color-regular); }
.vp-attach { margin-top: 12px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
