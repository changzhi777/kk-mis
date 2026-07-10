import { createApp } from 'vue'
import { createPinia } from 'pinia'

// ===== 样式（引入顺序重要）=====
// 1. Element Plus 暗色模式基础（必须在自定义 CSS 前）
import 'element-plus/theme-chalk/dark/css-vars.css'
// 2. 设计 Token：亮色
import '@/styles/theme/light.css'
// 3. 设计 Token：暗色
import '@/styles/theme/dark.css'
// 4. 侧边栏样式
import '@/styles/theme/sidebar.css'
// 5. 全局重置与基础样式
import '@/styles/base.scss'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
// 注：Element Plus 组件与 API 由 unplugin 按需引入，无需 app.use(ElementPlus)
app.mount('#app')
