<template>
  <el-card shadow="never">
    <template #header><span class="ct">代理提现（A3）</span></template>
    <el-row :gutter="16" class="bal-row">
      <el-col :span="8"><div class="bal-item"><div class="bal-label">已结算返佣</div><div class="bal-val">¥{{ balance.settled.toFixed(2) }}</div></div></el-col>
      <el-col :span="8"><div class="bal-item"><div class="bal-label">申请中</div><div class="bal-val">¥{{ balance.pending.toFixed(2) }}</div></div></el-col>
      <el-col :span="8"><div class="bal-item"><div class="bal-label">可提现</div><div class="bal-val primary">¥{{ balance.available.toFixed(2) }}</div></div></el-col>
    </el-row>
    <el-form :model="form" label-width="70px" style="margin-top: 20px">
      <el-form-item label="金额">
        <el-input-number v-model="form.amount" :min="100" :precision="2" :step="100" style="width: 200px" />
        <span class="muted">最低 ¥100</span>
      </el-form-item>
      <el-form-item label="收款"><el-input v-model="form.bank_info" placeholder="银行卡号 / 微信账号" style="max-width: 360px" /></el-form-item>
      <el-button type="primary" :loading="submitting" @click="submit">申请提现</el-button>
    </el-form>

    <div class="ct" style="margin: 20px 0 8px">提现记录</div>
    <el-table :data="records" size="small" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="金额"><template #default="{ row }">¥{{ Number(row.amount).toFixed(2) }}</template></el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="bank_info" label="收款" />
      <el-table-column label="申请时间"><template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template></el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import adminApi, { getApiError } from '@/api/admin'

const balance = ref({ settled: 0, pending: 0, available: 0 })
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const records = ref<any[]>([])
const form = reactive({ amount: 100, bank_info: '' })
const submitting = ref(false)

function statusText(s: string) {
  return { pending: '待审核', approved: '已通过', rejected: '已拒绝', paid: '已打款' }[s] || s
}
function statusType(s: string) {
  return ({ pending: 'warning', approved: 'success', rejected: 'danger', paid: 'success' } as const)[s] || 'info'
}

async function load() {
  try {
    balance.value = await adminApi.withdrawalBalance()
    records.value = await adminApi.listWithdrawals()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '加载失败'))
  }
}

async function submit() {
  if (!form.bank_info) { ElMessage.warning('请填收款信息'); return }
  submitting.value = true
  try {
    await adminApi.requestWithdrawal(form.amount, form.bank_info)
    ElMessage.success('提现申请已提交')
    form.amount = 100
    form.bank_info = ''
    await load()
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '申请失败'))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ct { font-weight: 600; }
.muted { color: var(--el-text-color-secondary); font-size: 13px; margin-left: 8px; }
.bal-row { margin: 0; }
.bal-item { text-align: center; padding: 8px 0; }
.bal-label { color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; }
.bal-val { font-size: 22px; font-weight: 700; }
.bal-val.primary { color: var(--el-color-primary); }
</style>
