<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="login-header">
        <el-icon class="logo-icon"><Headset /></el-icon>
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

      <p class="hint">默认超管 admin / admin123</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Headset, Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useUserStore } from '@/stores/user'

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
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    135deg,
    var(--el-bg-color-page) 0%,
    var(--el-color-primary-light-9) 100%
  );
}
.login-card {
  width: 380px;
  border-radius: 10px;
  padding: 8px 12px;
}
.login-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.logo-icon {
  font-size: 40px;
  color: var(--el-color-primary);
}
.title-wrap h2 {
  margin: 0;
  font-size: 22px;
}
.title-wrap p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.login-btn {
  width: 100%;
  margin-top: 8px;
}
.hint {
  text-align: center;
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
