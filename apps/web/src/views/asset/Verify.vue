<template>
  <div class="verify-page">
    <el-card v-loading="loading" shadow="never" class="verify-card">
      <template v-if="result">
        <div v-if="result.verified" class="ok">
          <el-icon class="big-ok"><CircleCheckFilled /></el-icon>
          <h2>✓ 防伪验证通过</h2>
          <p class="sub">该卡券为正品，可放心使用</p>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="防伪码">
              <code>{{ result.unique_code }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="卡号">
              {{ result.card_no_prefix }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusType(result.status)" size="small">
                {{ statusText(result.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="链上 Hash">
              <code class="hash">{{ result.blockchain_tx_hash }}</code>
            </el-descriptions-item>
            <el-descriptions-item v-if="result.last_verified_at" label="最近核验">
              {{ formatTime(result.last_verified_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-else class="fail">
          <el-icon class="big-fail"><CircleCloseFilled /></el-icon>
          <h2>✗ 防伪验证未通过</h2>
          <p class="sub">{{ result.reason || '该防伪码无效或已被撤销' }}</p>
          <p class="warn">
            请勿使用此卡券。如有疑问请联系客服。
          </p>
        </div>
      </template>

      <template v-else-if="error">
        <div class="fail">
          <el-icon class="big-fail"><WarningFilled /></el-icon>
          <h2>验证失败</h2>
          <p class="sub">{{ error }}</p>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { getApiError } from '@/api/admin'
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { CircleCheckFilled, CircleCloseFilled, WarningFilled } from '@element-plus/icons-vue'
import { http } from '@/api/admin'

const route = useRoute()
const loading = ref(true)
const result = ref<any>(null)
const error = ref('')

const statusText = (s: string) =>
  ({ draft: '待发放', issued: '已发放', used: '已核销' }[s] || s)
const statusType = (s: string) =>
  ({ draft: 'info', issued: 'warning', used: 'success' } as const)[s] ?? 'info'

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('zh-CN')
}

async function load() {
  loading.value = true
  const code = String(route.params.code || '')
  if (!code || code.length !== 64) {
    error.value = '防伪码格式无效（应为 64 位）'
    loading.value = false
    return
  }
  try {
    const { data } = await http.get(`/api/v1/asset/cards/verify/${code}`)
    result.value = data
  } catch (e: unknown) {
    error.value = getApiError(e, '验证接口不可用')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.verify-page {
  max-width: 600px;
  margin: 40px auto;
  padding: 0 20px;
}
.verify-card {
  border-radius: 12px;
}
.ok,
.fail {
  text-align: center;
  padding: 32px 16px;
}
.ok h2 {
  color: var(--el-color-success);
  margin: 12px 0 8px;
}
.fail h2 {
  color: var(--el-color-danger);
  margin: 12px 0 8px;
}
.sub {
  color: var(--el-text-color-secondary);
  margin: 0 0 24px;
}
.warn {
  color: var(--el-color-warning);
  font-size: 13px;
  margin-top: 8px;
}
.big-ok {
  font-size: 64px;
  color: var(--el-color-success);
}
.big-fail {
  font-size: 64px;
  color: var(--el-color-danger);
}
.hash {
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 11px;
  word-break: break-all;
}
.el-descriptions {
  text-align: left;
  margin-top: 16px;
}
</style>