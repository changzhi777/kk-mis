<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">订单管理</span>
        <el-button type="primary" :icon="Plus" @click="open()">新增订单</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="代理" width="120">
        <template #default="{ row }">{{ agentMap[row.agent_id]?.name || row.agent_id }} ({{ row.region_code || '-' }})</template>
      </el-table-column>
      <el-table-column label="批次" width="100">
        <template #default="{ row }">{{ row.batch_id }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="80" />
      <el-table-column label="折扣" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.discount_tier === 'full'" size="small">原价</el-tag>
          <el-tag v-else size="small" type="success">{{ row.discount_tier }} 折</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="单价" width="100">
        <template #default="{ row }">¥{{ Number(row.unit_price).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="总额" width="120">
        <template #default="{ row }">¥{{ Number(row.total).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" @click="pay(row.id)">确认付款</el-button>
          <el-button v-if="row.status === 'paid'" link type="success" @click="complete(row.id)">完成</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dv" title="新增订单（VIP 数量折扣）" width="520">
      <el-form :model="form" label-width="100px">
        <el-form-item label="代理">
          <el-select v-model="form.agent_id" style="width:100%">
            <el-option
              v-for="a in agents"
              :key="a.id"
              :label="`${a.name} (${a.region_code})`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="批次">
          <el-select v-model="form.batch_id" style="width:100%" @change="onBatchChange">
            <el-option
              v-for="b in batches"
              :key="b.id"
              :label="`${b.name}（¥${b.unit_price}/张）`"
              :value="b.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number
            v-model="form.quantity"
            :min="1"
            :step="10"
            style="width:100%"
            @change="refreshQuote"
          />
        </el-form-item>

        <!-- 折扣预览 -->
        <div v-if="quote" class="quote-box">
          <div class="quote-row">
            <span class="lbl">原价：</span>
            <span class="val-orig">¥{{ Number(quote.original_unit_price).toFixed(2) }}/张</span>
          </div>
          <div class="quote-row">
            <span class="lbl">折扣：</span>
            <el-tag :type="quote.discount_pct < 1 ? 'success' : 'info'" size="small">
              {{ Math.round(quote.discount_pct * 100) }} 折（{{ quote.tier }}）
            </el-tag>
          </div>
          <div class="quote-row">
            <span class="lbl">折后单价：</span>
            <span class="val-now">¥{{ Number(quote.unit_price).toFixed(2) }}/张</span>
          </div>
          <div class="quote-row total">
            <span class="lbl">订单总额：</span>
            <span class="val-total">¥{{ Number(quote.total).toFixed(2) }}</span>
          </div>
          <div class="quote-row tier-hint">
            <small v-if="form.quantity &lt; 100">提示：满 100 张享 6 折；满 1000 张享 5 折</small>
            <small v-else-if="form.quantity &lt; 1000">提示：满 1000 张享 5 折</small>
          </div>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dv = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi, { http, getApiError } from '@/api/admin'

const items = ref<any[]>([])
const agents = ref<any[]>([])
const batches = ref<any[]>([])
const loading = ref(false)
const dv = ref(false)
const saving = ref(false)
const quote = ref<any>(null)

const form = reactive<any>({
  agent_id: null,
  batch_id: null,
  quantity: 100,
  remark: '',
})

const api = adminApi.resource('/api/v1/agent/orders')
const agentMap = computed(() => Object.fromEntries(agents.value.map((a) => [a.id, a])))
const statusText = (s: string) =>
  ({ pending: '待付款', paid: '已付款', completed: '已完成', cancelled: '已取消' }[s] || s)
const statusType = (s: string) =>
  ({ pending: 'warning', paid: 'primary', completed: 'success', cancelled: 'info' } as const)[s] ?? 'info'

async function load() {
  loading.value = true
  try {
    const [d, a, b] = await Promise.all([
      api.list(),
      adminApi.resource('/api/v1/agent/agents').list(),
      adminApi.resource('/api/v1/asset/batches').list(),
    ])
    items.value = d.items
    agents.value = a.items
    batches.value = b.items
    if (!form.agent_id && agents.value[0]) form.agent_id = agents.value[0].id
    if (!form.batch_id && batches.value[0]) form.batch_id = batches.value[0].id
  } finally {
    loading.value = false
  }
  await refreshQuote()
}

async function refreshQuote() {
  if (!form.batch_id || !form.quantity) {
    quote.value = null
    return
  }
  try {
    const { data } = await http.get('/api/v1/agent/orders/quote', {
      params: { batch_id: form.batch_id, quantity: form.quantity },
    })
    quote.value = data
  } catch {
    quote.value = null
  }
}

function onBatchChange() {
  refreshQuote()
}

watch(() => form.quantity, refreshQuote)

function open() {
  Object.assign(form, {
    agent_id: agents.value[0]?.id,
    batch_id: batches.value[0]?.id,
    quantity: 100,
    remark: '',
  })
  dv.value = true
  refreshQuote()
}

async function save() {
  saving.value = true
  try {
    await api.create({
      agent_id: form.agent_id,
      batch_id: form.batch_id,
      quantity: form.quantity,
      remark: form.remark,
    })
    ElMessage.success('订单已创建（折扣已自动应用）')
    dv.value = false
    await load()
  } catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally {
    saving.value = false
  }
}

async function pay(id: number) {
  await adminApi.payOrder(id)
  ElMessage.success('已确认付款')
  await load()
}

async function complete(id: number) {
  await adminApi.completeOrder(id)
  ElMessage.success('订单完成，返佣已计算')
  await load()
}

onMounted(load)
</script>

<style scoped>
.hr {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ct {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.quote-box {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 12px 14px;
  margin: 8px 0 0;
}
.quote-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.quote-row.total {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.lbl {
  min-width: 80px;
  color: var(--el-text-color-secondary);
}
.val-orig {
  text-decoration: line-through;
  color: var(--el-text-color-placeholder);
}
.val-now {
  color: var(--el-color-primary);
  font-weight: 600;
}
.val-total {
  color: var(--el-color-primary);
  font-weight: 700;
  font-size: 15px;
}
.tier-hint {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  margin-top: 4px;
}
</style>