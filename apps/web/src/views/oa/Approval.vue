<template>
  <el-card shadow="never">
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="待我审批" name="pending">
        <el-table :data="pending" v-loading="loading" stripe>
          <el-table-column label="类型" width="80"><template #default="{ row }">{{ row.business_type === 'leave' ? '请假' : '报销' }}</template></el-table-column>
          <el-table-column prop="applicant_id" label="申请人ID" width="100" />
          <el-table-column label="进度" width="100"><template #default="{ row }">节点 {{ row.current_node + 1 }}</template></el-table-column>
          <el-table-column label="提交时间" width="170"><template #default="{ row }"><TimeText :value="row.created_at" /></template></el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="success" @click="doApprove(row.id)">通过</el-button>
              <el-button link type="danger" @click="doReject(row.id)">驳回</el-button>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无待审批" :image-size="60" /></template>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="我的申请" name="mine">
        <el-table :data="mine" stripe>
          <el-table-column label="类型" width="80"><template #default="{ row }">{{ row.business_type === 'leave' ? '请假' : '报销' }}</template></el-table-column>
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="current_node" label="当前节点" width="90" />
          <el-table-column label="提交时间" width="170"><template #default="{ row }"><TimeText :value="row.created_at" /></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'
const tab = ref('pending'), pending = ref<any[]>([]), mine = ref<any[]>([]), loading = ref(false)
const statusText = (x: string) => ({ pending: '审批中', approved: '已通过', rejected: '已驳回' }[x] || x)
const statusType = (x: string) => ({ pending: 'warning', approved: 'success', rejected: 'danger' }[x] || '') as any
async function load() {
  loading.value = true
  try {
    const [p, m] = await Promise.all([
      adminApi.resource('/api/v1/oa/approvals/instances/pending').list(),
      adminApi.resource('/api/v1/oa/approvals/instances/mine').list(),
    ])
    pending.value = p.items; mine.value = m.items
  } finally { loading.value = false }
}
async function doApprove(id: number) {
  const { value } = await ElMessageBox.prompt('审批意见（可选）', '通过审批', { inputType: 'textarea' }).catch(() => ({ value: null as any }))
  if (value === null) return
  await adminApi.approveInstance(id, value || undefined)
  ElMessage.success('已通过'); load()
}
async function doReject(id: number) {
  const { value } = await ElMessageBox.prompt('驳回理由', '驳回', { inputType: 'textarea' }).catch(() => ({ value: null as any }))
  if (value === null) return
  await adminApi.rejectInstance(id, value)
  ElMessage.success('已驳回'); load()
}
onMounted(load)
</script>
