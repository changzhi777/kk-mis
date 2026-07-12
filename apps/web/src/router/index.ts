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
    // 代理销售
    {
      path: '/agent/agent',
      name: 'agent-agent',
      component: () => import('@/views/agent/AgentList.vue'),
      meta: { title: '代理管理', group: 'agent', permission: 'agent:list' },
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
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = (to.meta.title as string) || 'kk-mis'
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
