<template>
  <div class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="logo">
      <el-icon class="logo-icon"><Headset /></el-icon>
      <span v-show="!collapsed" class="logo-text">
        <strong>kk-mis</strong>
        <small>会议纪要 AI 整理</small>
      </span>
    </div>
    <el-menu
      :default-active="route.path"
      router
      :collapse="collapsed"
      :collapse-transition="false"
      class="sidebar-menu"
    >
      <el-menu-item index="/upload">
        <el-icon><Upload /></el-icon>
        <template #title>上传会议</template>
      </el-menu-item>
      <el-menu-item index="/list">
        <el-icon><Document /></el-icon>
        <template #title>会议列表</template>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { Upload, Document, Headset } from '@element-plus/icons-vue'

defineProps<{ collapsed?: boolean }>()
const route = useRoute()
</script>

<style scoped>
.app-sidebar {
  width: 220px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}
.app-sidebar.is-collapsed {
  width: 64px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  border-bottom: 1px solid var(--c-sidebar-border);
  overflow: hidden;
  white-space: nowrap;
}
.logo-icon {
  font-size: 26px;
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.logo-text strong {
  color: var(--c-sidebar-text-active);
  font-size: 16px;
}
.logo-text small {
  color: var(--c-sidebar-text);
  font-size: 11px;
}
.sidebar-menu {
  flex: 1;
  border-right: none;
  background: transparent;
}
.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}
</style>
