<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">公告管理</span>
        <el-button type="primary" :icon="Plus" @click="open()">发布公告</el-button>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="标题" min-width="220">
        <template #default="{ row }"><el-button link type="primary" @click="view(row)">{{ row.title }}</el-button></template>
      </el-table-column>
      <el-table-column label="范围" width="90"><template #default="{ row }">{{ row.scope === 'all' ? '全员' : '部门' }}</template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="发布时间" width="170"><template #default="{ row }"><TimeText :value="row.published_at" /></template></el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'draft'" link type="success" @click="publish(row.id)">发布</el-button>
          <el-button v-if="row.status === 'published'" link type="warning" @click="archive(row.id)">归档</el-button>
          <el-popconfirm title="删除？" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无公告" :image-size="60" /></template>
    </el-table>

    <el-dialog v-model="dv" :title="form.id ? '编辑公告' : '发布公告'" width="600">
      <el-form :model="form" label-width="60px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="范围"><el-radio-group v-model="form.scope"><el-radio value="all">全员</el-radio></el-radio-group></el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="8" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dv = false">取消</el-button>
        <el-button :loading="s" @click="save(false)">存草稿</el-button>
        <el-button type="primary" :loading="s" @click="save(true)">保存并发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="vv" :title="viewing?.title" width="600">
      <pre class="content">{{ viewing?.content }}</pre>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import adminApi from '@/api/admin'
import TimeText from '@/components/TimeText.vue'

const items = ref<any[]>([]), loading = ref(false), dv = ref(false), vv = ref(false), s = ref(false), viewing = ref<any>(null)
const form = reactive<any>({ id: null, title: '', content: '', scope: 'all', status: 'draft' })
const api = adminApi.resource('/api/v1/oa/announcements')
const statusText = (x: string) => ({ draft: '草稿', published: '已发布', archived: '已归档' }[x] || x)
const statusType = (x: string) => ({ draft: 'info', published: 'success', archived: 'warning' }[x] || '') as any

async function load() { loading.value = true; try { items.value = (await api.list()).items } finally { loading.value = false } }
function open() { Object.assign(form, { id: null, title: '', content: '', scope: 'all', status: 'draft' }); dv.value = true }
async function save(publish: boolean) {
  s.value = true
  try {
    const r = form.id ? await api.update(form.id, form) : await api.create(form)
    if (publish) await adminApi.publishAnnouncement(r.id)
    ElMessage.success(publish ? '已发布' : '已存草稿')
    dv.value = false; load()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '失败') } finally { s.value = false }
}
function view(row: any) { viewing.value = row; vv.value = true }
async function publish(id: number) { await adminApi.publishAnnouncement(id); ElMessage.success('已发布'); load() }
async function archive(id: number) { await adminApi.archiveAnnouncement(id); ElMessage.success('已归档'); load() }
async function remove(id: number) { await api.remove(id); ElMessage.success('已删除'); load() }
onMounted(load)
</script>
<style scoped>.hr { display: flex; justify-content: space-between; align-items: center } .ct { font-weight: 600; color: var(--el-text-color-primary) } .content { white-space: pre-wrap; font-family: inherit; margin: 0; line-height: 1.8 }</style>
