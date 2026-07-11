<template>
  <!-- 登录页等 public 页面全屏 -->
  <router-view v-if="route.meta.public" />

  <el-container v-else class="layout">
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '220px'" class="layout-aside">
      <AppSidebar :collapsed="collapsed" />
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <el-button text circle :icon="isMobile ? Menu : collapsed ? Expand : Fold" @click="toggleSidebar" />
        <h3 class="header-title">{{ route.meta.title || 'kk-mis' }}</h3>
        <div class="header-right">
          <ThemeToggle />
          <el-dropdown v-if="userStore.userInfo" trigger="click">
            <span class="user-info">
              <el-avatar :size="28" class="avatar">{{ (userStore.userInfo.name || userStore.userInfo.username).slice(0, 1) }}</el-avatar>
              <span class="username">{{ userStore.userInfo.name || userStore.userInfo.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/list')">会议纪要</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="app-main">
        <div class="main-inner">
          <router-view />
        </div>
      </el-main>
    </el-container>

    <el-drawer v-model="drawerVisible" direction="ltr" :size="220" :with-header="false" class="mobile-drawer">
      <AppSidebar />
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Expand, Fold, Menu } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppSidebar from '@/components/AppSidebar.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const collapsed = ref(false)
const drawerVisible = ref(false)
const isMobile = ref(false)

function checkMobile() {
  isMobile.value = window.matchMedia('(max-width: 768px)').matches
  if (!isMobile.value) drawerVisible.value = false
}

function toggleSidebar() {
  if (isMobile.value) drawerVisible.value = !drawerVisible.value
  else collapsed.value = !collapsed.value
}

async function handleLogout() {
  try {
    await userStore.logout()
    router.push('/login')
    ElMessage.success('已退出')
  } catch {
    router.push('/login')
  }
}

// 登录态恢复：token 存在但 userInfo 缺失时拉取
onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  if (userStore.token) {
    try {
      if (!userStore.userInfo) await userStore.fetchMe()
      if (userStore.menus.length === 0) await userStore.fetchMenus()
    } catch {
      userStore.logout()
    }
  }
})

watch(() => route.path, () => {
  if (isMobile.value) drawerVisible.value = false
})
</script>

<style scoped>
.layout { height: 100vh; }
.layout-aside { transition: width 0.2s ease; overflow: hidden; }
.app-header {
  display: flex; align-items: center; gap: 12px; height: 56px;
  background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 16px;
}
.header-title { margin: 0; font-size: 16px; font-weight: 600; flex: 1; color: var(--el-text-color-primary); }
.header-right { display: flex; align-items: center; gap: 8px; }
.user-info { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.avatar { background: var(--el-color-primary); color: #fff; font-size: 13px; }
.username { font-size: 14px; color: var(--el-text-color-regular); }
.app-main { background: var(--el-bg-color-page); padding: 0; }
.main-inner { max-width: 1280px; margin: 0 auto; padding: 20px; }
</style>
