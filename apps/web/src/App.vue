<template>
  <el-container class="layout">
    <!-- 桌面侧边栏（PC/平板） -->
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '220px'" class="layout-aside">
      <AppSidebar :collapsed="collapsed" />
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <el-button
          text
          circle
          :icon="isMobile ? Menu : collapsed ? Expand : Fold"
          @click="toggleSidebar"
        />
        <h3 class="header-title">{{ route.meta.title || 'kk-mis · 会议纪要' }}</h3>
        <div class="header-right">
          <ThemeToggle />
        </div>
      </el-header>

      <el-main class="app-main">
        <div class="main-inner">
          <router-view />
        </div>
      </el-main>
    </el-container>

    <!-- 移动端抽屉侧边栏 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      :size="220"
      :with-header="false"
      class="mobile-drawer"
    >
      <AppSidebar />
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Menu, Fold, Expand } from '@element-plus/icons-vue'
import AppSidebar from '@/components/AppSidebar.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'

const route = useRoute()
const collapsed = ref(false)
const drawerVisible = ref(false)
const isMobile = ref(false)

function checkMobile() {
  isMobile.value = window.matchMedia('(max-width: 768px)').matches
  if (!isMobile.value) drawerVisible.value = false
}

function toggleSidebar() {
  if (isMobile.value) {
    drawerVisible.value = !drawerVisible.value
  } else {
    collapsed.value = !collapsed.value
  }
}

// 移动端导航后自动关抽屉
watch(() => route.path, () => {
  if (isMobile.value) drawerVisible.value = false
})

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
onUnmounted(() => window.removeEventListener('resize', checkMobile))
</script>

<style scoped>
.layout {
  height: 100vh;
}
.layout-aside {
  transition: width 0.2s ease;
  overflow: hidden;
}
.app-header {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 56px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 16px;
}
.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  flex: 1;
  color: var(--el-text-color-primary);
}
.header-right {
  display: flex;
  align-items: center;
}
.app-main {
  background: var(--el-bg-color-page);
  padding: 0;
}
.main-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 20px;
}
</style>
