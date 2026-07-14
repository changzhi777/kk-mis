<template>
  <el-card shadow="never">
    <template #header>
      <div class="hr">
        <span class="ct">{{ form.id ? '编辑产品' : '新增产品' }}</span>
        <div>
          <el-button @click="back">返回</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </div>
    </template>
    <el-form v-loading="loading" :model="form" label-width="100px">
      <el-divider content-position="left">基本信息</el-divider>
      <el-row :gutter="16">
        <el-col :span="12"><el-form-item label="标题"><el-input v-model="form.title" /></el-form-item></el-col>
        <el-col :span="12"><el-form-item label="URL标识"><el-input v-model="form.slug" placeholder="如 shanghai-3day" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="产品类型"><el-select v-model="form.type" @change="onTypeChange"><el-option label="订制游" value="custom" /><el-option label="权益卡" value="pass" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="目的地"><el-input v-model="form.destination" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="主题"><el-input v-model="form.theme" placeholder="海岛/亲子/商务" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="分类"><el-select v-model="form.category" clearable><el-option v-for="c in categories" :key="c" :label="c" :value="c" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="标签"><el-input v-model="tagsText" placeholder="逗号分隔，如 蜜月,海岛" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="状态"><el-select v-model="form.status"><el-option label="草稿" value="draft" /><el-option label="已发布" value="published" /><el-option label="已归档" value="archived" /></el-select></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item></el-col>
        <el-col :span="8"><el-form-item label="封面图">
          <div class="row-line">
            <el-input v-model="form.cover_image" placeholder="URL 或素材库选" />
            <el-button link type="primary" @click="coverPickerVisible = true">选</el-button>
          </div>
        </el-form-item></el-col>
      </el-row>
      <el-form-item label="摘要"><el-input v-model="form.summary" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="亮点"><el-input v-model="highlightsText" type="textarea" :rows="2" placeholder="一行一个亮点" /></el-form-item>

      <el-divider content-position="left">产品介绍（富文本）</el-divider>
      <el-form-item label="内容"><RichEditor v-model="form.content" /></el-form-item>

      <el-divider content-position="left">图集</el-divider>
      <el-form-item label="图片">
        <div v-for="(_, i) in gallery" :key="i" class="row-line">
          <el-input v-model="gallery[i]" placeholder="图片 URL" />
          <el-button link type="danger" @click="gallery.splice(i, 1)">删</el-button>
        </div>
        <el-button link type="primary" @click="gallery.push('')">+ 手动添加</el-button>
        <el-button link type="primary" @click="galleryPickerVisible = true">从素材库多选</el-button>
      </el-form-item>

      <!-- A 订制游扩展 -->
      <template v-if="form.type === 'custom' && form.custom">
        <el-divider content-position="left">订制游详情</el-divider>
        <el-form-item label="报价模式"><el-radio-group v-model="form.custom.price_mode"><el-radio value="inquiry">询价</el-radio><el-radio value="tier">阶梯报价</el-radio></el-radio-group></el-form-item>
        <el-form-item label="行程安排">
          <div v-for="(it, i) in form.custom.itinerary" :key="i" class="row-line">
            <el-input-number v-model="it.day" :min="1" controls-position="right" style="width: 90px" />
            <el-input v-model="it.title" placeholder="标题（如：抵达上海）" />
            <el-input v-model="it.transport" placeholder="交通" />
            <el-input v-model="it.hotel" placeholder="住宿" />
            <el-button link type="danger" @click="form.custom?.itinerary.splice(i, 1)">删</el-button>
          </div>
          <el-button link type="primary" @click="addItinerary">+ 添加行程日</el-button>
        </el-form-item>
      </template>

      <!-- C 权益卡扩展 -->
      <template v-if="form.type === 'pass' && form.pass_config">
        <el-divider content-position="left">权益卡详情</el-divider>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="卡面值"><el-input-number v-model="form.pass_config.face_value" :precision="2" :step="100" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="权益总价"><el-input-number v-model="form.pass_config.total_worth" :precision="2" :step="100" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="有效期"><el-input v-model="form.pass_config.valid_period" placeholder="如 12个月" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="使用规则"><el-input v-model="form.pass_config.usage_rules" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="权益清单">
          <div v-for="(b, i) in form.pass_config.benefits" :key="i" class="row-line">
            <el-input v-model="b.name" placeholder="权益名" />
            <el-input v-model="b.value" placeholder="价值" />
            <el-input-number v-model="b.quantity" :min="1" controls-position="right" style="width: 110px" />
            <el-button link type="danger" @click="form.pass_config?.benefits.splice(i, 1)">删</el-button>
          </div>
          <el-button link type="primary" @click="form.pass_config?.benefits.push({ name: '', value: '', quantity: 1 })">+ 添加权益</el-button>
        </el-form-item>
      </template>
    </el-form>

    <MediaPicker v-model="coverPickerVisible" @confirm="onPickCover" />
    <MediaPicker v-model="galleryPickerVisible" multiple @confirm="onPickGallery" />
  </el-card>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import RichEditor from '@/components/RichEditor.vue'
import MediaPicker from '@/components/MediaPicker.vue'
import cmsApi from '@/api/cms'
import { getApiError } from '@/api/admin'
import type { TourProduct } from '@/api/cms'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)

/** 编辑表单类型：字段非可选（el-input v-model 需要 string，非 string|undefined） */
interface EditForm {
  id?: number
  title: string
  slug: string
  type: TourProduct['type']
  destination: string
  theme: string
  category: string
  tags: string[]
  cover_image: string
  summary: string
  content: string
  highlights: string[]
  status: NonNullable<TourProduct['status']>
  sort: number
  seo_title: string
  seo_description: string
  gallery: string[]
  custom?: TourProduct['custom']
  pass_config?: TourProduct['pass_config']
}

const categories = ['国内', '海外', '周边', '主题乐园', '邮轮', '其他']

function emptyForm(): EditForm {
  return {
    title: '', slug: '', type: 'custom',
    destination: '', theme: '', category: '', tags: [],
    cover_image: '',
    summary: '', content: '', highlights: [],
    status: 'draft', sort: 0, seo_title: '', seo_description: '',
    gallery: [],
    custom: { itinerary: [], service_flow: [], price_mode: 'inquiry', price_tiers: [], consultant_ids: [] },
    pass_config: { face_value: 0, total_worth: 0, valid_period: '', usage_rules: '', benefits: [], merchant_ids: [] },
  }
}
const form = reactive<EditForm>(emptyForm())

// highlights 文本双向（一行一个）
const highlightsText = computed({
  get: () => (form.highlights || []).join('\n'),
  set: (v: string) => { form.highlights = v.split('\n').filter((x) => x.trim()) },
})
// tags 文本双向（逗号分隔）
const tagsText = computed({
  get: () => (form.tags || []).join(', '),
  set: (v: string) => { form.tags = v.split(/[,，]/).map((x) => x.trim()).filter(Boolean) },
})
// gallery 只读代理（模板直接改数组项/push/splice，reactive 响应）
const gallery = computed(() => form.gallery ?? [])

// 素材选择器
const coverPickerVisible = ref(false)
const galleryPickerVisible = ref(false)
function onPickCover(urls: string[]) {
  if (urls[0]) form.cover_image = urls[0]
}
function onPickGallery(urls: string[]) {
  form.gallery.push(...urls)
}

const idParam = route.params.id as string
const isNew = idParam === 'new'

function onTypeChange(t: string) {
  if (t === 'custom' && !form.custom) form.custom = emptyForm().custom
  if (t === 'pass' && !form.pass_config) form.pass_config = emptyForm().pass_config
}

function addItinerary() {
  form.custom?.itinerary.push({
    day: (form.custom?.itinerary.length || 0) + 1,
    title: '', transport: '', spots: [], meals: '', hotel: '', description: '',
  })
}

async function load() {
  if (isNew) return
  loading.value = true
  try {
    const p = await cmsApi.getProduct(Number(idParam))
    Object.assign(form, p)
    onTypeChange(form.type)
    // Decimal 字段后端可能返回 string，转 number（el-input-number 需要）
    if (form.pass_config) {
      form.pass_config.face_value = Number(form.pass_config.face_value) || 0
      form.pass_config.total_worth = Number(form.pass_config.total_worth) || 0
    }
  } catch (e: unknown) { ElMessage.error(getApiError(e, '加载失败')) } finally { loading.value = false }
}

function back() { router.push('/cms/product') }

async function save() {
  saving.value = true
  try {
    const payload: TourProduct = { ...form }
    if (form.type === 'custom') payload.pass_config = undefined
    else payload.custom = undefined
    if (isNew) {
      const created = await cmsApi.createProduct(payload)
      ElMessage.success('创建成功')
      router.replace(`/cms/product/${created.id}`)
    } else {
      await cmsApi.updateProduct(form.id as number, payload)
      ElMessage.success('保存成功')
    }
  } catch (e: unknown) { ElMessage.error(getApiError(e, '失败')) } finally { saving.value = false }
}

onMounted(load)
</script>
<style scoped>
.hr { display: flex; justify-content: space-between; align-items: center }
.ct { font-weight: 600; color: var(--el-text-color-primary) }
.row-line { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
</style>
