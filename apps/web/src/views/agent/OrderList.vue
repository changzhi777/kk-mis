<template>
  <el-card shadow="never">
    <template #header><div class="hr"><span class="ct">订单管理</span><el-button type="primary" :icon="Plus" @click="open()">新增订单</el-button></div></template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="代理" width="100"><template #default="{ row }">{{ agentMap[row.agent_id]?.name || row.agent_id }}</template></el-table-column>
      <el-table-column label="批次" width="80"><template #default="{ row }">{{ row.batch_id }}</template></el-table-column>
      <el-table-column prop="quantity" label="数量" width="80" />
      <el-table-column label="总额" width="110"><template #default="{ row }">¥{{ Number(row.total).toFixed(2) }}</template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending'" link type="primary" @click="pay(row.id)">确认付款</el-button>
          <el-button v-if="row.status === 'paid'" link type="success" @click="complete(row.id)">完成(算分润)</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog v-model="dv" title="新增订单" width="460">
      <el-form :model="form" label-width="70px">
        <el-form-item label="代理"><el-select v-model="form.agent_id" style="width:100%"><el-option v-for="a in agents" :key="a.id" :label="a.name" :value="a.id" /></el-select></el-form-item>
        <el-form-item label="批次"><el-select v-model="form.batch_id" style="width:100%"><el-option v-for="b in batches" :key="b.id" :label="b.name" :value="b.id" /></el-select></el-form-item>
        <el-form-item label="数量"><el-input-number v-model="form.quantity" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="单价"><el-input-number v-model="form.unit_price" :precision="2" :step="1" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dv = false">取消</el-button><el-button type="primary" :loading="s" @click="save">保存</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
const items = ref<any[]>([]), agents = ref<any[]>([]), batches = ref<any[]>([]), loading = ref(false), dv = ref(false), s = ref(false)
const form = reactive<any>({ agent_id: null, batch_id: null, quantity: 100, unit_price: 10, remark: '' })
const api = adminApi.resource('/api/v1/agent/orders')
const agentMap = computed(() => Object.fromEntries(agents.value.map((a) => [a.id, a])))
const statusText = (s: string) => ({ pending: '待付款', paid: '已付款', completed: '已完成', cancelled: '已取消' }[s] || s)
const statusType = (s: string) => ({ pending: 'warning', paid: 'primary', completed: 'success', cancelled: 'info' }[s] || 'info') as any
async function load() {
  loading.value = true
  try {
    const [d, a, b] = await Promise.all([api.list(), adminApi.resource('/api/v1/agent/agents').list(), adminApi.resource('/api/v1/asset/batches').list()])
    items.value = d.items; agents.value = a.items; batches.value = b.items
    if (!form.agent_id && agents.value[0]) form.agent_id = agents.value[0].id
    if (!form.batch_id && batches.value[0]) form.batch_id = batches.value[0].id
  } finally { loading.value = false }
}
function open() { Object.assign(form, { agent_id: agents.value[0]?.id, batch_id: batches.value[0]?.id, quantity: 100, unit_price: 10, remark: '' }); dv.value = true }
async function save() { s.value = true; try { await api.create(form); ElMessage.success('订单已创建'); dv.value = false; load() } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false } }
async function pay(id: number) { await adminApi.payOrder(id); ElMessage.success('已确认付款'); load() }
async function complete(id: number) { await adminApi.completeOrder(id); ElMessage.success('订单完成，分润已计算'); load() }
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) }</style>
