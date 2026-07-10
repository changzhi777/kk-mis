<template>
  <el-tooltip :content="theme === 'dark' ? '切换亮色' : '切换暗色'" placement="bottom">
    <el-button
      class="theme-toggle"
      circle
      text
      :icon="theme === 'dark' ? Sunny : Moon"
      @click="toggleTheme"
    />
  </el-tooltip>
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'
import { Sunny, Moon } from '@element-plus/icons-vue'

const { theme, toggleTheme } = useTheme()
</script>
