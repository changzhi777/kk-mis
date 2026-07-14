<template>
  <div class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="logo">
      <el-icon class="logo-icon"><Headset /></el-icon>
      <span v-show="!collapsed" class="logo-text">
        <strong>kk-CMS</strong>
        <small>企业管理 · 财务</small>
      </span>
    </div>

    <el-scrollbar class="menu-scroll">
      <el-menu
        :default-active="route.path"
        router
        :collapse="collapsed"
        :collapse-transition="false"
        :default-openeds="openedIds"
        class="sidebar-menu"
      >
        <template v-for="m in menus" :key="m.id">
          <!-- 有子菜单：分组 -->
          <el-sub-menu v-if="m.children && m.children.length" :index="String(m.id)">
            <template #title>
              <el-icon v-if="icon(m.icon)"><component :is="icon(m.icon)" /></el-icon>
              <span>{{ m.name }}</span>
            </template>
            <el-menu-item
              v-for="c in m.children"
              :key="c.id"
              :index="c.path"
            >
              <el-icon v-if="icon(c.icon)"><component :is="icon(c.icon)" /></el-icon>
              <template #title>{{ c.name }}</template>
            </el-menu-item>
          </el-sub-menu>
          <!-- 无子菜单：单页 -->
          <el-menu-item v-else :index="m.path">
            <el-icon v-if="icon(m.icon)"><component :is="icon(m.icon)" /></el-icon>
            <template #title>{{ m.name }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Headset } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useMenuIcon } from '@/composables/useMenuIcon'

defineProps<{ collapsed?: boolean }>()
const route = useRoute()
const userStore = useUserStore()
const icon = useMenuIcon()

const menus = computed(() => userStore.menus)
// 默认展开所有分组
const openedIds = computed(() =>
  menus.value.filter((m) => m.children && m.children.length).map((m) => String(m.id))
)
</script>

<style scoped>
.app-sidebar { width: 220px; height: 100%; display: flex; flex-direction: column; transition: width 0.2s ease; overflow: hidden; }
.app-sidebar.is-collapsed { width: 64px; }
.logo {
  display: flex; align-items: center; gap: 10px; padding: 18px 16px;
  border-bottom: 1px solid var(--c-sidebar-border); overflow: hidden; white-space: nowrap;
}
.logo-icon { font-size: 26px; color: var(--el-color-primary); flex-shrink: 0; }
.logo-text { display: flex; flex-direction: column; line-height: 1.3; }
.logo-text strong { color: var(--c-sidebar-text-active); font-size: 16px; }
.logo-text small { color: var(--c-sidebar-text); font-size: 11px; }
.menu-scroll { flex: 1; overflow-x: hidden; }
.sidebar-menu { border-right: none; background: transparent; }
.sidebar-menu:not(.el-menu--collapse) { width: 220px; }
</style>
