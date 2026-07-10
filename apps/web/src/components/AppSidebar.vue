<template>
  <div class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="logo">
      <el-icon class="logo-icon"><Headset /></el-icon>
      <span v-show="!collapsed" class="logo-text">
        <strong>kk-mis</strong>
        <small>企业管理 · 财务</small>
      </span>
    </div>

    <el-scrollbar class="menu-scroll">
      <el-menu :default-active="route.path" router :collapse="collapsed" :collapse-transition="false" class="sidebar-menu">
        <!-- 会议纪要 -->
        <el-sub-menu index="meeting">
          <template #title><el-icon><Document /></el-icon><span>会议纪要</span></template>
          <el-menu-item index="/upload"><el-icon><Upload /></el-icon><template #title>上传会议</template></el-menu-item>
          <el-menu-item index="/list"><el-icon><List /></el-icon><template #title>会议列表</template></el-menu-item>
        </el-sub-menu>

        <!-- 企业管理 -->
        <el-sub-menu v-if="hasAnySystem" index="system">
          <template #title><el-icon><Setting /></el-icon><span>企业管理</span></template>
          <el-menu-item v-if="userStore.hasPermission('system:user:list')" index="/system/user"><el-icon><User /></el-icon><template #title>用户管理</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('system:role:save')" index="/system/role"><el-icon><UserFilled /></el-icon><template #title>角色管理</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('system:permission:save')" index="/system/permission"><el-icon><Key /></el-icon><template #title>权限菜单</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('system:dept:save')" index="/system/dept"><el-icon><OfficeBuilding /></el-icon><template #title>部门管理</template></el-menu-item>
        </el-sub-menu>

        <!-- 财务管理 -->
        <el-sub-menu v-if="hasAnyFinance" index="finance">
          <template #title><el-icon><Wallet /></el-icon><span>财务管理</span></template>
          <el-menu-item v-if="userStore.hasPermission('finance:transaction:save')" index="/finance/transaction"><el-icon><Money /></el-icon><template #title>收支流水</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('finance:account:save')" index="/finance/account"><el-icon><CreditCard /></el-icon><template #title>账户管理</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('finance:category:save')" index="/finance/category"><el-icon><Files /></el-icon><template #title>收支科目</template></el-menu-item>
          <el-menu-item v-if="userStore.hasPermission('finance:report:view')" index="/finance/report"><el-icon><DataAnalysis /></el-icon><template #title>统计报表</template></el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  CreditCard, DataAnalysis, Document, Files, Headset, Key, List, Money,
  OfficeBuilding, Setting, Upload, User, UserFilled, Wallet,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

defineProps<{ collapsed?: boolean }>()
const route = useRoute()
const userStore = useUserStore()

const systemPerms = ['system:user:list', 'system:role:save', 'system:permission:save', 'system:dept:save']
const financePerms = ['finance:transaction:save', 'finance:account:save', 'finance:category:save', 'finance:report:view']

const hasAnySystem = computed(() => systemPerms.some((p) => userStore.hasPermission(p)))
const hasAnyFinance = computed(() => financePerms.some((p) => userStore.hasPermission(p)))
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
