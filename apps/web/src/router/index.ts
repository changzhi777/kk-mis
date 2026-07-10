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
      path: '/',
      name: 'home',
      redirect: '/list',
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
