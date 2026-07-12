<template>
  <div class="cb">
    <el-icon class="spin" :size="36"><Loading /></el-icon>
    <p class="msg">{{ msg }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const msg = ref('正在完成登录...')

onMounted(async () => {
  // 后端 302 到 /oa/oauth/callback#t=xxx&r=xxx 或 #error=xxx
  const raw = (route.hash || '').startsWith('#') ? route.hash.slice(1) : (route.hash || '')
  const params = new URLSearchParams(raw)
  const accessToken = params.get('t')
  const refreshToken = params.get('r')
  const error = params.get('error')

  if (error) {
    msg.value = error
    ElMessage.error(error)
    setTimeout(() => router.replace('/login'), 1500)
    return
  }
  if (!accessToken) {
    ElMessage.error('登录回调参数异常')
    router.replace('/login')
    return
  }
  try {
    await userStore.applyOAuthLogin(accessToken, refreshToken || '')
    ElMessage.success('登录成功')
    router.replace('/')
  } catch {
    msg.value = '登录失败，请重试'
    ElMessage.error('登录失败')
    setTimeout(() => router.replace('/login'), 1500)
  }
})
</script>

<style scoped>
.cb {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 14px;
}
.spin {
  animation: rot 1s linear infinite;
  color: var(--el-color-primary);
}
.msg {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
@keyframes rot {
  to { transform: rotate(360deg); }
}
</style>
