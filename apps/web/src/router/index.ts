/**
 * Vue Router 配置
 */
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory('/oa/'),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/Register.vue'),
      meta: { public: true, title: '注册' },
    },
    {
      path: '/oauth/callback',
      name: 'oauth-callback',
      component: () => import('@/views/oauth/Callback.vue'),
      meta: { public: true, title: '登录中' },
    },
    // 防伪公开核销页（2026-07-13 决策 #3 重构）
    {
      path: '/verify/:code',
      name: 'verify-card',
      component: () => import('@/views/asset/Verify.vue'),
      meta: { public: true, title: '防伪核验' },
    },
    // 旅游产品公开介绍页（CMS，2026-07-14）
    {
      path: '/product/:slug',
      name: 'cms-product-view',
      component: () => import('@/views/cms/ProductView.vue'),
      meta: { public: true, title: '产品详情' },
    },
    // 公开搜索（CMS，2026-07-14）
    {
      path: '/search',
      name: 'cms-search',
      component: () => import('@/views/cms/Search.vue'),
      meta: { public: true, title: '搜索产品' },
    },
    {
      path: '/',
      name: 'home',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { title: '工作台' },
    },
    // 会议纪要（现有）
    {
      path: '/upload',
      name: 'upload',
      component: () => import('@/views/Upload.vue'),
      meta: { title: '上传会议', group: 'meeting' },
    },
    {
      path: '/list',
      name: 'list',
      component: () => import('@/views/List.vue'),
      meta: { title: '会议列表', group: 'meeting' },
    },
    {
      path: '/meetings/:id',
      name: 'detail',
      component: () => import('@/views/Detail.vue'),
      meta: { title: '会议详情', group: 'meeting' },
    },
    // OA Agent（独立服务，2026-07-12 接入）
    {
      path: '/oa-agent',
      name: 'oa-agent',
      component: () => import('@/views/oa/OaAgent.vue'),
      meta: { title: 'OA Agent', group: 'oa', permission: 'oa_agent' },
    },
    // 企业管理（阶段5 填充具体页面）
    {
      path: '/system/user',
      name: 'sys-user',
      component: () => import('@/views/system/UserList.vue'),
      meta: { title: '用户管理', group: 'system', permission: 'system:user:list' },
    },
    {
      path: '/system/role',
      name: 'sys-role',
      component: () => import('@/views/system/RoleList.vue'),
      meta: { title: '角色管理', group: 'system', permission: 'system:role:save' },
    },
    {
      path: '/system/permission',
      name: 'sys-perm',
      component: () => import('@/views/system/PermissionList.vue'),
      meta: { title: '权限菜单', group: 'system', permission: 'system:permission:save' },
    },
    {
      path: '/system/dept',
      name: 'sys-dept',
      component: () => import('@/views/system/DeptList.vue'),
      meta: { title: '部门管理', group: 'system', permission: 'system:dept:save' },
    },
    {
      path: '/system/audit',
      name: 'sys-audit',
      component: () => import('@/views/system/AuditLog.vue'),
      meta: { title: '审计日志', group: 'system', permission: 'system:audit:view' },
    },
    {
      path: '/announcement',
      name: 'oa-announcement',
      component: () => import('@/views/oa/Announcement.vue'),
      meta: { title: '公告管理', group: 'oa', permission: 'oa:announcement:save' },
    },
    {
      path: '/leave',
      name: 'oa-leave',
      component: () => import('@/views/oa/Leave.vue'),
      meta: { title: '请假申请', group: 'oa' },
    },
    {
      path: '/expense',
      name: 'oa-expense',
      component: () => import('@/views/oa/Expense.vue'),
      meta: { title: '报销申请', group: 'oa' },
    },
    {
      path: '/approval',
      name: 'oa-approval',
      component: () => import('@/views/oa/Approval.vue'),
      meta: { title: '审批中心', group: 'oa' },
    },
    {
      path: '/report',
      name: 'oa-report',
      component: () => import('@/views/oa/Report.vue'),
      meta: { title: '工作汇报', group: 'oa' },
    },
    {
      path: '/attendance',
      name: 'oa-attendance',
      component: () => import('@/views/oa/Attendance.vue'),
      meta: { title: '考勤打卡', group: 'oa' },
    },
    // 财务（阶段5 填充）
    {
      path: '/finance/transaction',
      name: 'fin-tx',
      component: () => import('@/views/finance/TransactionList.vue'),
      meta: { title: '收支流水', group: 'finance', permission: 'finance:transaction:save' },
    },
    {
      path: '/finance/account',
      name: 'fin-acc',
      component: () => import('@/views/finance/AccountList.vue'),
      meta: { title: '账户管理', group: 'finance', permission: 'finance:account:save' },
    },
    {
      path: '/finance/category',
      name: 'fin-cat',
      component: () => import('@/views/finance/CategoryList.vue'),
      meta: { title: '收支科目', group: 'finance', permission: 'finance:category:save' },
    },
    {
      path: '/finance/report',
      name: 'fin-rpt',
      component: () => import('@/views/finance/Report.vue'),
      meta: { title: '统计报表', group: 'finance', permission: 'finance:report:view' },
    },
    // 资产管理
    {
      path: '/asset/type',
      name: 'asset-type',
      component: () => import('@/views/asset/CardTypeList.vue'),
      meta: { title: '卡券类型', group: 'asset', permission: 'asset:type:list' },
    },
    {
      path: '/asset/batch',
      name: 'asset-batch',
      component: () => import('@/views/asset/BatchList.vue'),
      meta: { title: '卡券批次', group: 'asset', permission: 'asset:batch:list' },
    },
    {
      path: '/asset/card',
      name: 'asset-card',
      component: () => import('@/views/asset/CardList.vue'),
      meta: { title: '卡券列表', group: 'asset', permission: 'asset:card:list' },
    },
    {
      path: '/asset/redemption',
      name: 'asset-redemption',
      component: () => import('@/views/asset/Redemption.vue'),
      meta: { title: '卡券核销', group: 'asset', permission: 'asset:card:list' },
    },
    // 代理销售（RegionList 替代原 AgentList，2026-07-13 决策 #3 重构后统一入口）
    {
      path: '/agent/region',
      name: 'agent-region',
      component: () => import('@/views/agent/RegionList.vue'),
      meta: { title: '区域代理', group: 'agent', permission: 'agent:list' },
    },
    {
      path: '/agent/order',
      name: 'agent-order',
      component: () => import('@/views/agent/OrderList.vue'),
      meta: { title: '订单管理', group: 'agent', permission: 'agent:order:list' },
    },
    {
      path: '/agent/commission',
      name: 'agent-commission',
      component: () => import('@/views/agent/Commission.vue'),
      meta: { title: '分润报表', group: 'agent', permission: 'agent:commission:view' },
    },
    // 内容管理（CMS，2026-07-14：VIP 卡旅游产品介绍）
    {
      path: '/cms/product',
      name: 'cms-product',
      component: () => import('@/views/cms/ProductList.vue'),
      meta: { title: '旅游产品', group: 'cms', permission: 'cms:product:list' },
    },
    {
      path: '/cms/dashboard',
      name: 'cms-dashboard',
      component: () => import('@/views/cms/Dashboard.vue'),
      meta: { title: '数据看板', group: 'cms', permission: 'cms:product:list' },
    },
    {
      path: '/cms/product/:id',
      name: 'cms-product-edit',
      component: () => import('@/views/cms/ProductEdit.vue'),
      meta: { title: '编辑产品', group: 'cms', permission: 'cms:product:save' },
    },
    {
      path: '/cms/media',
      name: 'cms-media',
      component: () => import('@/views/cms/MediaLibrary.vue'),
      meta: { title: '素材库', group: 'cms', permission: 'cms:media:list' },
    },
    {
      path: '/cms/merchant',
      name: 'cms-merchant',
      component: () => import('@/views/cms/MerchantList.vue'),
      meta: { title: '合作商户', group: 'cms', permission: 'cms:merchant:list' },
    },
    {
      path: '/cms/lead',
      name: 'cms-lead',
      component: () => import('@/views/cms/LeadList.vue'),
      meta: { title: '询价线索', group: 'cms', permission: 'cms:lead:list' },
    },
    {
      path: '/cms/order',
      name: 'cms-order',
      component: () => import('@/views/cms/OrderList.vue'),
      meta: { title: '产品订单', group: 'cms', permission: 'cms:order:list' },
    },
    {
      path: '/cms/coupon',
      name: 'cms-coupon',
      component: () => import('@/views/cms/CouponList.vue'),
      meta: { title: '优惠券', group: 'cms', permission: 'cms:coupon:list' },
    },
    {
      path: '/cms/review',
      name: 'cms-review',
      component: () => import('@/views/cms/ReviewList.vue'),
      meta: { title: '评论管理', group: 'cms', permission: 'cms:review:list' },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = (to.meta.title as string) || 'kk-cms'
  const userStore = useUserStore()

  // 公开页面（登录页）直接放行
  if (to.meta.public) {
    next()
    return
  }
  // 未登录跳登录
  if (!userStore.token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  // 权限校验
  const perm = to.meta.permission as string | undefined
  if (perm && !userStore.hasPermission(perm)) {
    next('/')
    return
  }
  next()
})

export default router
