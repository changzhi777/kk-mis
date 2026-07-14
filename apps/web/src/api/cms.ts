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
  cover_image?: string
  gallery?: string[]
  video_url?: string
  summary?: string
  content?: string
  highlights?: string[]
  status?: TourProductStatus
  sort?: number
  seo_title?: string
  seo_description?: string
  published_at?: string
  created_at?: string
  updated_at?: string
  custom?: TourCustom
  pass_config?: TourPass
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

// ===== API =====
export const cmsApi = {
  // 产品
  listProducts(params?: { type?: TourProductType; status?: TourProductStatus }) {
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
}

export default cmsApi
