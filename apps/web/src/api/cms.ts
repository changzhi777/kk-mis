/**
 * CMS 内容管理 API 客户端
 * 复用 admin.ts 的 http（JWT 拦截 + 401 跳登录）+ getApiError
 */
import type { AxiosProgressEvent } from 'axios'
import { http } from './admin'

// ===== 内容结构类型（对齐后端 schemas/cms.py）=====
export interface TourItinerary {
  day: number
  title: string
  transport: string
  spots: string[]
  meals: string
  hotel: string
  description: string
}

export interface TourBenefit {
  name: string
  value: string
  quantity: number
  merchant_id?: number
}

export interface TourCustom {
  itinerary: TourItinerary[]
  service_flow: unknown[]
  price_mode: 'inquiry' | 'tier'
  price_tiers: unknown[]
  consultant_ids: number[]
}

export interface TourPass {
  face_value: number
  total_worth: number
  valid_period?: string
  usage_rules?: string
  benefits: TourBenefit[]
  merchant_ids: number[]
}

export type TourProductType = 'custom' | 'pass'
export type TourProductStatus = 'draft' | 'published' | 'archived'

export interface TourProduct {
  id?: number
  title: string
  slug: string
  type: TourProductType
  destination?: string
  theme?: string
  category?: string
  tags?: string[]
  cover_image?: string
  gallery?: string[]
  video_url?: string
  summary?: string
  content?: string
  highlights?: string[]
  status?: TourProductStatus
  sort?: number
  view_count?: number
  card_type_id?: number
  seo_title?: string
  seo_description?: string
  published_at?: string
  created_at?: string
  updated_at?: string
  custom?: TourCustom
  pass_config?: TourPass
  reviews?: Review[]
}

export interface MediaAsset {
  id: number
  name: string
  type: 'image' | 'video'
  url: string
  size: number
  alt?: string
  tags?: string[]
  created_at: string
}

export interface Merchant {
  id?: number
  name: string
  logo?: string
  address?: string
  contact?: string
  benefit_desc?: string
  status?: boolean
  sort?: number
  created_at?: string
}

export type InquiryLeadStatus = 'new' | 'contacted' | 'converted' | 'closed'

export interface InquiryLead {
  id?: number
  product_id?: number
  name: string
  phone: string
  wechat?: string
  destination?: string
  travel_date?: string
  people?: number
  budget?: string
  remark?: string
  status?: InquiryLeadStatus
  created_at?: string
}

export type OrderPayStatus = 'pending' | 'paid' | 'cancelled'

export interface ProductOrder {
  id?: number
  product_id: number
  quantity: number
  unit_price: number | string
  original_total: number | string
  discount: number | string
  total: number | string
  coupon_code?: string
  buyer_name: string
  buyer_phone: string
  remark?: string
  pay_status?: OrderPayStatus
  paid_at?: string
  transaction_id?: string
  issued_card_no?: string
  issued_card_password?: string
  created_at?: string
}

export type CouponDiscountType = 'percent' | 'fixed'

export interface Coupon {
  id?: number
  code: string
  name: string
  discount_type: CouponDiscountType
  discount_value: number
  min_total?: number
  max_uses?: number
  used_count?: number
  valid_from?: string
  valid_until?: string
  status?: boolean
  created_at?: string
}

export interface CouponValidateResult {
  valid: boolean
  discount: number | string
  reason?: string
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected'

export interface Review {
  id?: number
  product_id: number
  author_name: string
  rating: number
  content: string
  status?: ReviewStatus
  created_at?: string
}

export interface DashboardStats {
  products_total: number
  products_published: number
  views_total: number
  top_products: { title: string; slug: string; view_count: number }[]
  leads_total: number
  leads_new: number
  orders_total: number
  orders_paid: number
  revenue: number | string
}

export interface EndUser {
  id: number
  phone: string
  nickname?: string
  created_at?: string
}

/** C 端 token header（与 admin token 分离，公开页 admin 未登录时手动注入） */
export function endHeaders(): Record<string, string> {
  const t = localStorage.getItem('kk-cms-end-user-token')
  return t ? { Authorization: `Bearer ${t}` } : {}
}

/** 和风 icon code → emoji（简化常用映射） */
export function iconEmoji(code?: string | number): string {
  const n = parseInt(String(code || '999'))
  if (n === 100) return '☀️'
  if (n < 105) return '⛅' // 101-104 多云/阴
  if (n < 200) return '🌤️'
  if (n < 400) return '🌧️' // 300-399 雨
  if (n < 500) return '❄️' // 400-499 雪
  if (n < 600) return '🌫️' // 500-599 雾霾
  return '🌤️'
}

export interface Weather {
  city: string
  text: string
  temperature: string | number
  feelsLike?: string | number
  humidity?: string | number
  icon?: string
  windDir?: string
  windScale?: string
}

export interface WeatherForecastDay {
  fxDate: string
  tempMax: string
  tempMin: string
  textDay: string
  textNight: string
  iconDay: string
  [k: string]: unknown
}

// ===== API =====
export const cmsApi = {
  // 产品
  listProducts(params?: { type?: TourProductType; status?: TourProductStatus; category?: string }) {
    return http.get('/api/v1/cms/products', { params }).then((r) => r.data.items as TourProduct[])
  },
  /** 管理详情（含 draft + 扩展，编辑页用） */
  getProduct(id: number) {
    return http.get(`/api/v1/cms/products/detail/${id}`).then((r) => r.data as TourProduct)
  },
  /** 公开介绍页（无需登录，仅 published） */
  getPublicProduct(slug: string) {
    return http.get(`/api/v1/cms/products/${encodeURIComponent(slug)}`).then((r) => r.data as TourProduct)
  },
  createProduct(data: TourProduct) {
    return http.post('/api/v1/cms/products', data).then((r) => r.data as TourProduct)
  },
  updateProduct(id: number, data: Partial<TourProduct>) {
    return http.put(`/api/v1/cms/products/${id}`, data).then((r) => r.data as TourProduct)
  },
  deleteProduct(id: number) {
    return http.delete(`/api/v1/cms/products/${id}`).then((r) => r.data)
  },

  // 素材
  uploadMedia(file: File, onProgress?: (e: AxiosProgressEvent) => void) {
    const fd = new FormData()
    fd.append('file', file)
    return http
      .post('/api/v1/cms/media/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: onProgress,
      })
      .then((r) => r.data as MediaAsset)
  },
  listMedia(params?: { type?: 'image' | 'video' }) {
    return http.get('/api/v1/cms/media', { params }).then((r) => r.data.items as MediaAsset[])
  },
  deleteMedia(id: number) {
    return http.delete(`/api/v1/cms/media/${id}`).then((r) => r.data)
  },

  // 商户
  listMerchants() {
    return http.get('/api/v1/cms/merchants').then((r) => r.data.items as Merchant[])
  },
  createMerchant(data: Merchant) {
    return http.post('/api/v1/cms/merchants', data).then((r) => r.data as Merchant)
  },
  updateMerchant(id: number, data: Partial<Merchant>) {
    return http.put(`/api/v1/cms/merchants/${id}`, data).then((r) => r.data as Merchant)
  },
  deleteMerchant(id: number) {
    return http.delete(`/api/v1/cms/merchants/${id}`).then((r) => r.data)
  },

  // 询价线索（订制游 A）
  /** 公开提交（无需登录） */
  submitLead(data: Partial<InquiryLead> & { name: string; phone: string }) {
    return http.post('/api/v1/cms/leads', data).then((r) => r.data as InquiryLead)
  },
  listLeads(params?: { status?: InquiryLeadStatus }) {
    return http.get('/api/v1/cms/leads', { params }).then((r) => r.data.items as InquiryLead[])
  },
  updateLeadStatus(id: number, status: InquiryLeadStatus) {
    return http.put(`/api/v1/cms/leads/${id}/status`, { status }).then((r) => r.data as InquiryLead)
  },
  deleteLead(id: number) {
    return http.delete(`/api/v1/cms/leads/${id}`).then((r) => r.data)
  },

  // 订单（权益卡 C）
  createOrder(data: {
    product_id: number
    quantity: number
    coupon_code?: string
    buyer_name: string
    buyer_phone: string
    remark?: string
  }) {
    return http.post('/api/v1/cms/orders', data).then((r) => r.data as ProductOrder)
  },
  payOrder(id: number) {
    return http.post(`/api/v1/cms/orders/${id}/pay`).then((r) => r.data as ProductOrder)
  },
  listOrders(params?: { pay_status?: OrderPayStatus }) {
    return http.get('/api/v1/cms/orders', { params }).then((r) => r.data.items as ProductOrder[])
  },

  // 优惠券
  validateCoupon(code: string, total: number) {
    return http.post('/api/v1/cms/coupons/validate', { code, total }).then((r) => r.data as CouponValidateResult)
  },
  listCoupons() {
    return http.get('/api/v1/cms/coupons').then((r) => r.data.items as Coupon[])
  },
  createCoupon(data: Coupon) {
    return http.post('/api/v1/cms/coupons', data).then((r) => r.data as Coupon)
  },
  updateCoupon(id: number, data: Partial<Coupon>) {
    return http.put(`/api/v1/cms/coupons/${id}`, data).then((r) => r.data as Coupon)
  },
  deleteCoupon(id: number) {
    return http.delete(`/api/v1/cms/coupons/${id}`).then((r) => r.data)
  },

  // 评论/评价
  submitReview(data: { product_id: number; author_name: string; rating: number; content: string }) {
    return http.post('/api/v1/cms/reviews', data).then((r) => r.data as Review)
  },
  listReviews(params?: { status?: ReviewStatus }) {
    return http.get('/api/v1/cms/reviews', { params }).then((r) => r.data.items as Review[])
  },
  updateReviewStatus(id: number, status: ReviewStatus) {
    return http.put(`/api/v1/cms/reviews/${id}/status`, { status }).then((r) => r.data as Review)
  },
  deleteReview(id: number) {
    return http.delete(`/api/v1/cms/reviews/${id}`).then((r) => r.data)
  },

  // 数据看板
  getDashboard() {
    return http.get('/api/v1/cms/stats/dashboard').then((r) => r.data as DashboardStats)
  },

  // 搜索 + 相关推荐
  searchProducts(q: string) {
    return http
      .get('/api/v1/cms/products/search/results', { params: { q } })
      .then((r) => r.data.items as TourProduct[])
  },
  getRelated(slug: string) {
    return http
      .get(`/api/v1/cms/products/related/${encodeURIComponent(slug)}`)
      .then((r) => r.data.items as TourProduct[])
  },

  // C 端终端用户
  registerEndUser(data: { phone: string; password: string; nickname?: string }) {
    return http
      .post('/api/v1/cms/auth/register', data)
      .then((r) => r.data as { token: string; user: EndUser })
  },
  loginEndUser(data: { phone: string; password: string }) {
    return http
      .post('/api/v1/cms/auth/login', data)
      .then((r) => r.data as { token: string; user: EndUser })
  },
  getEndUserMe() {
    return http
      .get('/api/v1/cms/auth/me', { headers: endHeaders() })
      .then((r) => r.data as EndUser)
  },

  // 天气（和风，公开）
  getWeather(city: string) {
    return http
      .get('/api/v1/cms/weather', { params: { city } })
      .then((r) => r.data as Weather)
  },
  getForecast(city: string, days = 3) {
    return http
      .get('/api/v1/cms/weather/forecast', { params: { city, days } })
      .then((r) => r.data as { city: string; daily: WeatherForecastDay[] })
  },
}

export default cmsApi
