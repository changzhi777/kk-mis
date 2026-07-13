<template>
  <el-card shadow="never">
    <template #header><span class="ct">卡券列表（含防伪 QR）</span></template>
    <div class="filter">
      <el-input v-model="keyword" placeholder="卡号搜索" clearable style="width:200px" @clear="load" @keyup.enter="load" />
      <el-select v-model="status" placeholder="状态" clearable style="width:120px" @change="load">
        <el-option v-for="s in statusOpts" :key="s" :label="statusText(s)" :value="s" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="card_no" label="卡号" min-width="160" />
      <el-table-column label="防伪码" min-width="160">
        <template #default="{ row }">
          <code v-if="row.unique_code" class="uc">{{ row.unique_code.slice(0, 8) }}…{{ row.unique_code.slice(-8) }}</code>
          <span v-else style="color:var(--el-text-color-placeholder)">未生成</span>
        </template>
      </el-table-column>
      <el-table-column label="QR" width="100">
        <template #default="{ row }">
          <el-button v-if="row.unique_code" link size="small" @click="showQR(row)">查看</el-button>
          <span v-else style="color:var(--el-text-color-placeholder)">-</span>
        </template>
      </el-table-column>
      <el-table-column label="链上 Hash" width="180">
        <template #default="{ row }">
          <code v-if="row.blockchain_tx_hash" class="hash">{{ row.blockchain_tx_hash.slice(0, 8) }}…</code>
          <span v-else style="color:var(--el-text-color-placeholder)">-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="面值" width="100">
        <template #default="{ row }">¥{{ Number(row.face_value).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'draft'" link type="primary" @click="issue(row.id)">发放</el-button>
          <el-popconfirm
            v-if="row.status !== 'used' && row.status !== 'void'"
            title="作废？"
            @confirm="voidCard(row.id)"
          >
            <template #reference>
              <el-button link type="warning">作废</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="total > pageSize" class="page">
      <el-pagination
        v-model:current-page="page"
        :total="total"
        :page-size="pageSize"
        layout="prev, pager, next, total"
        background
        @current-change="load"
      />
    </div>

    <!-- QR 弹窗 -->
    <el-dialog v-model="qrVisible" title="防伪 QR" width="360">
      <div v-if="qrCard" class="qr-content">
        <p style="text-align:center;color:var(--el-text-color-secondary);font-size:12px;margin:0 0 8px">
          客户扫码核销
        </p>
        <p style="text-align:center">
          <QrCodeImg :value="qrCard.qr_url" :size="220" />
        </p>
        <p class="url-row">
          <small>{{ qrCard.qr_url }}</small>
        </p>
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="卡号">
            {{ qrCard.card_no.slice(0, 4) }}****{{ qrCard.card_no.slice(-4) }}
          </el-descriptions-item>
          <el-descriptions-item label="防伪码">
            <code>{{ qrCard.unique_code }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="链上 Hash">
            <code>{{ qrCard.blockchain_tx_hash }}</code>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi from '@/api/admin'
import QrCodeImg from '@/components/QrCodeImg.vue'

const route = useRoute()
const items = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref('')
const status = ref('')
const statusOpts = ['draft', 'issued', 'used', 'refunded', 'expired', 'void']
const api = adminApi.resource('/api/v1/asset/cards')

const qrVisible = ref(false)
const qrCard = ref<any>(null)

const statusText = (s: string) =>
  ({
    draft: '待发放',
    issued: '已发放',
    used: '已核销',
    refunded: '已退款',
    expired: '已过期',
    void: '已作废',
  }[s] || s)
const statusType = (s: string) =>
  ({
    draft: 'info',
    issued: 'warning',
    used: 'success',
    
    expired: 'info',
    void: 'danger',
  } as const)[s]

async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (status.value) params.status = status.value
    if (keyword.value) params.keyword = keyword.value
    if (route.query.batch_id) params.batch_id = route.query.batch_id
    const d = await api.list(params)
    items.value = d.items
    total.value = d.total
  } finally {
    loading.value = false
  }
}

function showQR(row: any) {
  qrCard.value = row
  qrVisible.value = true
}

async function issue(id: number) {
  const { value } = await ElMessageBox.prompt('输入持有人 user_id', '发放卡券', {
    inputPattern: /^\d+$/,
    inputErrorMessage: '数字',
  })
  await adminApi.issueCard(id, Number(value))
  ElMessage.success('已发放')
  load()
}

async function voidCard(id: number) {
  await adminApi.voidCard(id)
  ElMessage.success('已作废')
  load()
}

onMounted(load)
</script>

<style scoped>
.ct {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.filter {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.page {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.uc,
.hash {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 3px;
}
.url-row {
  word-break: break-all;
  text-align: center;
  color: var(--el-text-color-secondary);
  margin: 8px 0;
}
</style>