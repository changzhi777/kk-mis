<template>
  <div class="product-view" v-loading="loading">
    <div v-if="notFound" class="not-found"><el-empty description="产品不存在或未发布" /></div>
    <template v-else-if="p">
      <!-- Hero -->
      <div class="hero" :style="p.cover_image ? { backgroundImage: `url(${p.cover_image})` } : {}">
        <div class="hero-mask">
          <h1>{{ p.title }}</h1>
          <div class="meta">
            <el-tag v-if="p.destination" size="large" effect="dark">📍 {{ p.destination }}</el-tag>
            <el-tag v-if="p.category" size="large" type="info" effect="dark">{{ p.category }}</el-tag>
            <el-tag v-if="p.theme" size="large" type="warning" effect="dark">{{ p.theme }}</el-tag>
            <el-tag v-for="(t, i) in (p.tags || [])" :key="i" size="large" effect="dark">{{ t }}</el-tag>
            <el-tag size="large" :type="p.type === 'custom' ? 'warning' : 'success'" effect="dark">
              {{ p.type === 'custom' ? '高端订制游' : '旅游权益卡' }}
            </el-tag>
          </div>
          <p v-if="p.summary" class="summary">{{ p.summary }}</p>
        </div>
      </div>

      <div class="container">
        <!-- 目的地天气（行程参考） -->
        <section v-if="weather" class="block weather-card">
          <div class="w-now">
            <span class="w-icon">{{ iconEmoji(weather.icon) }}</span>
            <div class="w-temp">{{ weather.temperature }}°</div>
            <div class="w-detail">
              <div class="w-city">{{ weather.city }} · {{ weather.text }}</div>
              <div class="w-sub">体感 {{ weather.feelsLike }}° · 湿度 {{ weather.humidity }}% · {{ weather.windDir }}{{ weather.windScale }}级</div>
            </div>
          </div>
          <div v-if="forecast.length" class="w-forecast">
            <div v-for="f in forecast" :key="f.fxDate" class="w-day">
              <div class="w-date">{{ f.fxDate.slice(5) }}</div>
              <div class="w-d-icon">{{ iconEmoji(f.iconDay) }}</div>
              <div class="w-d-temp">{{ f.tempMax }}°/{{ f.tempMin }}°</div>
              <div class="w-d-text">{{ f.textDay }}</div>
            </div>
          </div>
        </section>

        <section v-if="p.highlights?.length" class="block">
          <h2>产品亮点</h2>
          <ul class="highlights"><li v-for="(h, i) in p.highlights" :key="i">{{ h }}</li></ul>
        </section>

        <section v-if="p.content" class="block">
          <h2>产品介绍</h2>
          <div class="rich-content" v-html="sanitizedContent"></div>
        </section>

        <!-- A 订制游：行程时间线 -->
        <section v-if="p.type === 'custom' && p.custom?.itinerary?.length" class="block">
          <h2>行程安排</h2>
          <div v-for="it in p.custom.itinerary" :key="it.day" class="itinerary">
            <div class="day-badge">Day {{ it.day }}</div>
            <div class="day-body">
              <h3>{{ it.title }}</h3>
              <div class="day-meta">
                <span v-if="it.transport">🚗 {{ it.transport }}</span>
                <span v-if="it.hotel">🏨 {{ it.hotel }}</span>
                <span v-if="it.meals">🍽️ {{ it.meals }}</span>
              </div>
              <div v-if="it.spots?.length" class="spots">
                <el-tag v-for="(s, si) in it.spots" :key="si" size="small" effect="plain">{{ s }}</el-tag>
              </div>
              <p v-if="it.description" class="desc">{{ it.description }}</p>
            </div>
          </div>
          <div v-if="p.custom.price_mode === 'inquiry'" class="price-note">💎 一单一议，按需定制报价</div>
        </section>

        <!-- C 权益卡 -->
        <section v-if="p.type === 'pass' && p.pass_config" class="block">
          <h2>权益清单</h2>
          <div class="pass-price">
            <div class="price-item"><span>卡面值</span><strong>¥{{ Number(p.pass_config.face_value).toFixed(2) }}</strong></div>
            <div class="price-item worth"><span>权益总价</span><strong>¥{{ Number(p.pass_config.total_worth).toFixed(2) }}</strong></div>
            <div v-if="p.pass_config.valid_period" class="price-item"><span>有效期</span><strong>{{ p.pass_config.valid_period }}</strong></div>
          </div>
          <div v-if="p.pass_config.benefits?.length" class="benefits">
            <div v-for="(b, i) in p.pass_config.benefits" :key="i" class="benefit">
              <div class="b-name">{{ b.name }}</div>
              <div class="b-val">¥{{ b.value }} × {{ b.quantity }}</div>
            </div>
          </div>
          <div v-if="p.pass_config.usage_rules" class="usage">
            <h3>使用规则</h3><p>{{ p.pass_config.usage_rules }}</p>
          </div>
        </section>

        <section v-if="p.gallery?.length" class="block">
          <h2>图集</h2>
          <div class="gallery"><img v-for="(g, i) in p.gallery" :key="i" :src="g" loading="lazy" class="gallery-img" /></div>
        </section>

        <!-- 用户评价 -->
        <section class="block">
          <h2>用户评价</h2>
          <div v-for="r in (p.reviews || [])" :key="r.id" class="review">
            <div class="r-head">
              <span class="r-name">{{ r.author_name }}</span>
              <span class="stars">{{ '★'.repeat(r.rating) }}{{ '☆'.repeat(5 - r.rating) }}</span>
            </div>
            <p class="r-content">{{ r.content }}</p>
          </div>
          <el-empty v-if="!(p.reviews || []).length" description="暂无评价，快来抢沙发" :image-size="60" />
          <el-divider />
          <div class="review-form">
            <h3>写评价</h3>
            <el-form :model="reviewForm" label-width="60px">
              <el-form-item label="昵称"><el-input v-model="reviewForm.author_name" style="width: 200px" /></el-form-item>
              <el-form-item label="评分"><el-rate v-model="reviewForm.rating" /></el-form-item>
              <el-form-item label="内容"><el-input v-model="reviewForm.content" type="textarea" :rows="2" /></el-form-item>
              <el-button type="primary" :loading="reviewing" @click="submitReviewForm">提交评价（审核后展示）</el-button>
            </el-form>
          </div>
        </section>
      </div>

      <!-- 相关产品 -->
      <div v-if="related.length" class="container">
        <section class="block">
          <h2>相关产品</h2>
          <div class="related-grid">
            <div v-for="r in related" :key="r.id" class="related-card" @click="goRelated(r.slug)">
              <img v-if="r.cover_image" :src="r.cover_image" class="rc-cover" />
              <div v-else class="rc-cover rc-ph">🏔</div>
              <div class="rc-title">{{ r.title }}</div>
              <div class="rc-meta">{{ r.destination || r.category || '' }}</div>
            </div>
          </div>
        </section>
      </div>

      <!-- CTA 浮动栏 -->
      <div class="cta-bar">
        <div class="cta-left">
          <span class="cta-type">{{ p.type === 'custom' ? '高端订制游' : '旅游权益卡' }}</span>
          <el-button v-if="!endUser.isLogin" link @click="authDialog = true">登录</el-button>
          <span v-else class="end-user">
            👤 {{ endUser.displayName }}
            <el-button link size="small" @click="endUser.logout()">退出</el-button>
          </span>
        </div>
        <el-button type="primary" size="large" @click="consult">{{ p.type === 'custom' ? '咨询定制' : '立即购买' }}</el-button>
      </div>

      <!-- C 端登录/注册弹窗 -->
      <el-dialog v-model="authDialog" :title="authMode === 'login' ? '登录' : '注册'" width="400">
        <el-form :model="authForm" label-width="70px">
          <el-form-item label="手机号"><el-input v-model="authForm.phone" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="authForm.password" type="password" show-password /></el-form-item>
          <el-form-item v-if="authMode === 'register'" label="昵称"><el-input v-model="authForm.nickname" placeholder="选填" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button link @click="toggleAuthMode">{{ authMode === 'login' ? '没账号？去注册' : '有账号？去登录' }}</el-button>
          <el-button @click="authDialog = false">取消</el-button>
          <el-button type="primary" :loading="authing" @click="doAuth">{{ authMode === 'login' ? '登录' : '注册' }}</el-button>
        </template>
      </el-dialog>

      <!-- 订制游询价表单 -->
      <el-dialog v-model="leadDialog" title="咨询定制" width="500">
        <el-form :model="lead" label-width="80px">
          <el-form-item label="姓名" required><el-input v-model="lead.name" /></el-form-item>
          <el-form-item label="电话" required><el-input v-model="lead.phone" /></el-form-item>
          <el-form-item label="微信"><el-input v-model="lead.wechat" /></el-form-item>
          <el-form-item label="目的地"><el-input v-model="lead.destination" /></el-form-item>
          <el-form-item label="出行日期"><el-input v-model="lead.travel_date" placeholder="如 2026-08" /></el-form-item>
          <el-form-item label="人数"><el-input-number v-model="lead.people" :min="1" controls-position="right" /></el-form-item>
          <el-form-item label="预算"><el-input v-model="lead.budget" placeholder="如 2万/人" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="lead.remark" type="textarea" :rows="3" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="leadDialog = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submit">提交咨询</el-button>
        </template>
      </el-dialog>

      <!-- 权益卡购买弹窗 -->
      <el-dialog v-model="buyDialog" title="购买权益卡" width="480">
        <el-form label-width="90px">
          <el-form-item label="数量"><el-input-number v-model="buyForm.quantity" :min="1" @change="recalc" /></el-form-item>
          <el-form-item label="优惠券码">
            <div class="row-line">
              <el-input v-model="buyForm.coupon_code" placeholder="选填" @change="recalc" />
          </el-form-item>
          <el-form-item label="推广码">
            <el-input v-model="buyForm.promo_code" placeholder="选填，代理推广码（享推荐关联）" />
              <el-button link type="primary" @click="recalc">应用</el-button>
            </div>
          </el-form-item>
          <el-form-item label="价格">
            <div>
              <div>原价 ¥{{ (unitPrice * buyForm.quantity).toFixed(2) }}</div>
              <div v-if="discountVal > 0" class="disc">优惠 -¥{{ discountVal.toFixed(2) }}</div>
              <div class="paid">实付 ¥{{ Math.max(unitPrice * buyForm.quantity - discountVal, 0).toFixed(2) }}</div>
            </div>
          </el-form-item>
          <el-form-item label="姓名" required><el-input v-model="buyForm.buyer_name" /></el-form-item>
          <el-form-item label="电话" required><el-input v-model="buyForm.buyer_phone" /></el-form-item>
        </el-form>
        <el-alert
          v-if="createdOrder"
          :title="createdOrder.pay_status === 'paid' ? '支付成功' : `订单 #${createdOrder.id} 已创建，实付 ¥${Number(createdOrder.total).toFixed(2)}`"
          :type="createdOrder.pay_status === 'paid' ? 'success' : 'info'"
          :closable="false"
          style="margin-bottom: 12px"
        />
        <div v-if="createdOrder?.issued_card_no" class="issued-card">
          <h3>🎉 支付成功，您的 VIP 卡</h3>
          <div class="card-row"><span>卡号</span><strong>{{ createdOrder.issued_card_no }}</strong></div>
          <div class="card-row"><span>密码</span><strong>{{ createdOrder.issued_card_password }}</strong></div>
        </div>
        <template #footer>
          <el-button @click="buyDialog = false">关闭</el-button>
          <el-button v-if="!createdOrder" type="primary" :loading="creating" @click="createOrd">创建订单</el-button>
          <el-button v-else-if="createdOrder.pay_status !== 'paid'" type="primary" :loading="paying" @click="payOrd">模拟支付</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
import cmsApi, { iconEmoji } from '@/api/cms'
import { getApiError } from '@/api/admin'
import { useEndUserStore } from '@/stores/endUser'
import type { InquiryLead, ProductOrder, TourProduct, Weather, WeatherForecastDay } from '@/api/cms'

const route = useRoute()
const router = useRouter()
const endUser = useEndUserStore()
const p = ref<TourProduct | null>(null)
const related = ref<TourProduct[]>([])
const weather = ref<Weather | null>(null)
const forecast = ref<WeatherForecastDay[]>([])
const loading = ref(false)
const notFound = ref(false)

const sanitizedContent = computed(() => (p.value?.content ? DOMPurify.sanitize(p.value.content) : ''))

// SEO meta（og:title/description/image，微信分享卡片用）
watch(
  p,
  (val) => {
    if (!val) return
    document.title = val.seo_title || val.title || '产品详情'
    setMeta('og:title', val.title || '')
    setMeta('og:description', val.seo_description || val.summary || '')
    if (val.cover_image) setMeta('og:image', val.cover_image)
  },
  { immediate: true }
)
function setMeta(prop: string, content: string) {
  let el = document.querySelector(`meta[property="${prop}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('property', prop)
    document.head.appendChild(el)
  }
  el.content = content
}

// 询价表单
const leadDialog = ref(false)
const submitting = ref(false)
const emptyLead = (): InquiryLead => ({ name: '', phone: '', wechat: '', destination: '', travel_date: '', people: 1, budget: '', remark: '' })
const lead = reactive<InquiryLead>(emptyLead())

async function load() {
  loading.value = true
  try {
    p.value = await cmsApi.getPublicProduct(route.params.slug as string)
    try {
      related.value = await cmsApi.getRelated(route.params.slug as string)
    } catch {
      related.value = []
    }
    // 目的地天气（实时 + 3d 预报，行程参考）
    if (p.value?.destination) {
      try {
        weather.value = await cmsApi.getWeather(p.value.destination)
        forecast.value = (await cmsApi.getForecast(p.value.destination)).daily
      } catch {
        /* 天气失败不阻塞 */
      }
    }
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

function goRelated(slug: string) {
  router.push(`/product/${slug}`)
}

function consult() {
  const phone = endUser.isLogin && endUser.user ? endUser.user.phone : ''
  const name = endUser.isLogin && endUser.user ? endUser.user.nickname || endUser.user.phone : ''
  if (p.value?.type === 'custom') {
    // 询价预填（登录态）
    if (name) lead.name = name
    if (phone) lead.phone = phone
    leadDialog.value = true
  } else {
    // 权益卡购买预填
    Object.assign(buyForm, { quantity: 1, coupon_code: '', promo_code: '', buyer_name: name, buyer_phone: phone })
    createdOrder.value = null
    discountVal.value = 0
    buyDialog.value = true
  }
}

// C 端登录/注册
const authDialog = ref(false)
const authMode = ref<'login' | 'register'>('login')
const authing = ref(false)
const authForm = reactive({ phone: '', password: '', nickname: '' })

function toggleAuthMode() {
  authMode.value = authMode.value === 'login' ? 'register' : 'login'
}

async function doAuth() {
  if (!authForm.phone || !authForm.password) {
    ElMessage.warning('请填写手机号和密码')
    return
  }
  authing.value = true
  try {
    const res =
      authMode.value === 'login'
        ? await cmsApi.loginEndUser({ phone: authForm.phone, password: authForm.password })
        : await cmsApi.registerEndUser({
            phone: authForm.phone,
            password: authForm.password,
            nickname: authForm.nickname || undefined,
          })
    endUser.setAuth(res.token, res.user)
    ElMessage.success(authMode.value === 'login' ? '登录成功' : '注册成功')
    authDialog.value = false
    // 预填评论昵称
    reviewForm.author_name = res.user.nickname || res.user.phone
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '操作失败'))
  } finally {
    authing.value = false
  }
}

async function submit() {
  if (!lead.name || !lead.phone) {
    ElMessage.warning('请填写姓名和电话')
    return
  }
  submitting.value = true
  try {
    await cmsApi.submitLead({ ...lead, product_id: p.value?.id })
    ElMessage.success('提交成功，客服将尽快联系您')
    leadDialog.value = false
    Object.assign(lead, emptyLead())
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '提交失败'))
  } finally {
    submitting.value = false
  }
}

// 权益卡购买
const unitPrice = computed(() => (p.value?.pass_config ? Number(p.value.pass_config.face_value) : 0))
const buyDialog = ref(false)
const creating = ref(false)
const paying = ref(false)
const discountVal = ref(0)
const createdOrder = ref<ProductOrder | null>(null)
const buyForm = reactive({ quantity: 1, coupon_code: '', promo_code: '', buyer_name: '', buyer_phone: '' })

async function recalc() {
  discountVal.value = 0
  if (!buyForm.coupon_code) return
  try {
    const res = await cmsApi.validateCoupon(buyForm.coupon_code, unitPrice.value * buyForm.quantity)
    if (res.valid) {
      discountVal.value = Number(res.discount)
    } else {
      ElMessage.warning(res.reason || '券无效')
    }
  } catch {
    /* 忽略校验错误 */
  }
}

async function createOrd() {
  if (!buyForm.buyer_name || !buyForm.buyer_phone) {
    ElMessage.warning('请填写姓名和电话')
    return
  }
  creating.value = true
  try {
    createdOrder.value = await cmsApi.createOrder({
      product_id: p.value?.id as number,
      quantity: buyForm.quantity,
      coupon_code: buyForm.coupon_code || undefined,
      promo_code: buyForm.promo_code || undefined,
      buyer_name: buyForm.buyer_name,
      buyer_phone: buyForm.buyer_phone,
    })
    ElMessage.success('订单已创建')
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '创建失败'))
  } finally {
    creating.value = false
  }
}

async function payOrd() {
  paying.value = true
  try {
    createdOrder.value = await cmsApi.payOrder(createdOrder.value?.id as number)
    ElMessage.success('支付成功')
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '支付失败'))
  } finally {
    paying.value = false
  }
}

// 评论
const reviewing = ref(false)
const reviewForm = reactive({ author_name: '', rating: 5, content: '' })
async function submitReviewForm() {
  if (!reviewForm.author_name || !reviewForm.content) {
    ElMessage.warning('请填写昵称和评价')
    return
  }
  reviewing.value = true
  try {
    await cmsApi.submitReview({ product_id: p.value?.id as number, ...reviewForm })
    ElMessage.success('评价已提交，审核后展示')
    reviewForm.content = ''
  } catch (e: unknown) {
    ElMessage.error(getApiError(e, '提交失败'))
  } finally {
    reviewing.value = false
  }
}

onMounted(load)
</script>
<style scoped>
.product-view { min-height: 100vh; background: var(--el-bg-color-page); padding-bottom: 70px; }
.not-found { display: flex; justify-content: center; padding: 80px 0; }
.hero { min-height: 360px; background-size: cover; background-position: center; background-color: var(--el-color-primary-light-9); display: flex; align-items: flex-end; }
.hero-mask { background: linear-gradient(transparent, rgba(0, 0, 0, 0.7)); padding: 50px 0 28px; width: 100%; }
.container { max-width: 900px; margin: 0 auto; padding: 20px 16px; }
.hero h1 { color: #fff; font-size: 30px; margin: 0 16px 12px; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5); }
.hero .meta { display: flex; gap: 8px; margin: 0 16px 10px; flex-wrap: wrap; }
.hero .summary { margin: 0 16px; color: rgba(255, 255, 255, 0.92); font-size: 15px; line-height: 1.6; }
.block { background: var(--el-bg-color); border-radius: 10px; padding: 20px; margin-bottom: 14px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
.block h2 { font-size: 19px; margin: 0 0 16px; color: var(--el-text-color-primary); border-left: 4px solid var(--el-color-primary); padding-left: 10px; }
.weather-card { background: linear-gradient(135deg, var(--el-color-primary-light-9), var(--el-bg-color)); }
.w-now { display: flex; align-items: center; gap: 14px; }
.w-icon { font-size: 40px; }
.w-temp { font-size: 36px; font-weight: 300; color: var(--el-color-primary); }
.w-city { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); }
.w-sub { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.w-forecast { display: flex; gap: 10px; margin-top: 14px; overflow-x: auto; }
.w-day { text-align: center; min-width: 70px; padding: 8px 4px; background: var(--el-bg-color); border-radius: 8px; }
.w-date { font-size: 12px; color: var(--el-text-color-secondary); }
.w-d-icon { font-size: 22px; margin: 4px 0; }
.w-d-temp { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); }
.w-d-text { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }
.highlights { list-style: none; padding: 0; margin: 0; }
.highlights li { padding: 9px 0; border-bottom: 1px dashed var(--el-border-color-lighter); color: var(--el-text-color-regular); }
.highlights li:before { content: '✓ '; color: var(--el-color-primary); font-weight: bold; }
.rich-content { line-height: 1.8; color: var(--el-text-color-regular); }
.rich-content :deep(h2), .rich-content :deep(h3) { color: var(--el-text-color-primary); margin: 0.8em 0 0.4em; }
.rich-content :deep(ul), .rich-content :deep(ol) { padding-left: 1.6em; }
.rich-content :deep(img) { max-width: 100%; border-radius: 6px; }
.itinerary { display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.day-badge { background: var(--el-color-primary); color: #fff; border-radius: 50%; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; font-size: 13px; }
.day-body { flex: 1; }
.day-body h3 { margin: 0 0 6px; font-size: 16px; }
.day-meta { display: flex; gap: 12px; color: var(--el-text-color-secondary); font-size: 13px; margin-bottom: 6px; flex-wrap: wrap; }
.spots { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0; }
.desc { color: var(--el-text-color-regular); font-size: 14px; margin: 6px 0 0; line-height: 1.6; }
.price-note { text-align: center; color: var(--el-color-primary); font-weight: 600; margin-top: 16px; }
.pass-price { display: flex; gap: 14px; margin-bottom: 16px; flex-wrap: wrap; }
.price-item { flex: 1; min-width: 120px; background: var(--el-fill-color-light); border-radius: 8px; padding: 14px; text-align: center; }
.price-item span { display: block; font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 6px; }
.price-item strong { font-size: 22px; color: var(--el-color-primary); }
.price-item.worth strong { color: var(--el-color-danger); text-decoration: line-through; font-size: 18px; }
.benefits { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.benefit { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; padding: 12px; }
.b-name { font-weight: 600; margin-bottom: 4px; color: var(--el-text-color-primary); }
.b-val { color: var(--el-text-color-secondary); font-size: 13px; }
.usage { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); }
.usage h3 { font-size: 15px; margin: 0 0 8px; }
.usage p { color: var(--el-text-color-regular); font-size: 14px; line-height: 1.7; white-space: pre-line; }
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.gallery-img { width: 100%; height: 160px; object-fit: cover; border-radius: 8px; }
.cta-bar { position: fixed; bottom: 0; left: 0; right: 0; background: var(--el-bg-color); border-top: 1px solid var(--el-border-color); padding: 10px 16px; display: flex; justify-content: center; align-items: center; gap: 16px; box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08); z-index: 10; }
.cta-bar .cta-left { display: flex; align-items: center; gap: 12px; }
.cta-bar .cta-type { font-weight: 600; color: var(--el-text-color-primary); }
.end-user { font-size: 13px; color: var(--el-text-color-regular); display: inline-flex; align-items: center; gap: 4px; }
.row-line { display: flex; gap: 6px; align-items: center; }
.disc { color: var(--el-color-danger); font-size: 13px; }
.paid { font-weight: 600; color: var(--el-color-primary); }
.issued-card { background: var(--el-color-success-light-9); border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.issued-card h3 { margin: 0 0 10px; font-size: 15px; color: var(--el-color-success); }
.card-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px dashed var(--el-border-color-lighter); }
.card-row span { color: var(--el-text-color-secondary); }
.card-row strong { font-size: 16px; letter-spacing: 1px; }
.review { padding: 10px 0; border-bottom: 1px dashed var(--el-border-color-lighter); }
.r-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.r-name { font-weight: 600; color: var(--el-text-color-primary); }
.stars { color: #f7ba2a; }
.r-content { margin: 0; color: var(--el-text-color-regular); font-size: 14px; line-height: 1.6; }
.review-form h3 { font-size: 15px; margin: 0 0 12px; color: var(--el-text-color-primary); }
.related-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.related-card { cursor: pointer; border-radius: 8px; overflow: hidden; background: var(--el-fill-color-light); }
.related-card:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
.rc-cover { width: 100%; height: 100px; object-fit: cover; display: block; }
.rc-ph { display: flex; align-items: center; justify-content: center; font-size: 28px; background: var(--el-color-primary-light-9); color: var(--el-text-color-secondary); }
.rc-title { padding: 6px 8px 2px; font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rc-meta { padding: 0 8px 8px; font-size: 11px; color: var(--el-text-color-secondary); }
/* 移动端 H5 响应式 */
@media (max-width: 768px) {
  .hero { min-height: 240px; }
  .hero h1 { font-size: 22px; }
  .container { padding: 14px 12px; }
  .block { padding: 14px; }
  .w-forecast, .benefits, .gallery, .related-grid { grid-template-columns: repeat(2, 1fr); }
  .cta-bar { padding: 8px 12px; gap: 8px; }
  .cta-bar .cta-type { font-size: 13px; }
  .itinerary { flex-direction: column; gap: 8px; }
  .day-badge { width: 40px; height: 40px; font-size: 11px; }
}
</style>
