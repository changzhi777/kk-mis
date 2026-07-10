/**
 * Vue Router 配置
 */
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/list'
    },
    {
      path: '/upload',
      name: 'upload',
      component: () => import('@/views/Upload.vue'),
      meta: { title: '上传会议' }
    },
    {
      path: '/list',
      name: 'list',
      component: () => import('@/views/List.vue'),
      meta: { title: '会议列表' }
    },
    {
      path: '/meetings/:id',
      name: 'detail',
      component: () => import('@/views/Detail.vue'),
      meta: { title: '会议详情' }
    }
  ]
})

router.beforeEach((to, _from, next) => {
  document.title = (to.meta.title as string) || 'kk-mis'
  next()
})

export default router