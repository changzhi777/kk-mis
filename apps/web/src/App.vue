<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>kk-mis</h2>
        <p class="subtitle">会议纪要 AI 整理</p>
      </div>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/upload">
          <el-icon><Upload /></el-icon>
          <span>上传会议</span>
        </el-menu-item>
        <el-menu-item index="/list">
          <el-icon><Document /></el-icon>
          <span>会议列表</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <h3>{{ route.meta.title || 'kk-mis' }}</h3>
        <div class="header-right">
          <el-tag size="small" type="success">v0.1.0</el-tag>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style>
.layout {
  height: 100vh;
}
.sidebar {
  background: #001529;
  color: #fff;
}
.logo {
  padding: 24px 16px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.logo h2 {
  margin: 0;
  color: #fff;
  font-size: 20px;
}
.subtitle {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}
.el-menu {
  background: transparent;
  border: none;
}
.el-menu-item {
  color: rgba(255, 255, 255, 0.8);
}
.el-menu-item.is-active {
  background: #1890ff !important;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  padding: 0 24px;
}
.main {
  background: #f5f7fa;
  padding: 24px;
}
</style>