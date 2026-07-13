<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <div class="login-header">
        <div class="logo-badge">
          <el-icon class="logo-icon"><Headset /></el-icon>
        </div>
        <div class="title-wrap">
          <h2>kk-mis</h2>
          <p>企业管理 · 会议纪要 · 财务</p>
        </div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="handleLogin"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :prefix-icon="User" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            :prefix-icon="Lock"
            type="password"
            show-password
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="login-btn" @click="handleLogin">
          登 录
        </el-button>
      </el-form>

      <p class="hint">默认超管 admin / admin1234</p>
      <p class="to-register">还没有账号？<router-link to="/register">立即注册 →</router-link></p>
      <el-divider>第三方登录</el-divider>
      <el-button class="oauth-btn" @click="oauthLogin('github')">GitHub 登录</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Headset, Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getApiError } from '@/api/admin'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.login(form.username, form.password)
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    } catch (e: unknown) { ElMessage.error(getApiError(e, '登录失败')) } finally {
      loading.value = false
    }
  })
}

function oauthLogin(provider: string) {
  window.location.href = import.meta.env.BASE_URL + 'admin/api/v1/auth/oauth/' + provider + '/authorize'
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: linear-gradient(
    135deg,
    var(--el-bg-color-page) 0%,
    var(--el-color-primary-light-9) 100%
  );
}
.login-card {
  width: 400px;
  border-radius: 12px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: var(--shadow-md);
}
.login-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}
.logo-badge {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-color-primary-light-9);
  flex-shrink: 0;
}
.logo-icon {
  font-size: 32px;
  color: var(--el-color-primary);
}
.title-wrap h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}
.title-wrap p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.login-btn {
  width: 100%;
  margin-top: 8px;
  height: 42px;
  font-size: 15px;
}
.hint {
  text-align: center;
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.to-register {
  text-align: center;
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.to-register a {
  color: var(--el-color-primary);
  text-decoration: none;
}
.oauth-btn { width: 100%; margin-top: 4px; }
</style>
